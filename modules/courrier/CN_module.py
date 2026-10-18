# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le courrier
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : CN
# VERSION CN : 0.1.1  #00ade6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le courrier : la boîte IMAP de chaque compte, son cache, ses gestes, l'envoi.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=00ade6 ▼▼▼
"""Le courrier : la boîte IMAP de chaque compte, son cache, ses gestes, l'envoi.

Porté de la V18 (`_imap_*`, `itare_mail_*`, `mail_*`, `_courrier_*`), avec ses leçons :
  - UNE boîte appartient à UNE personne : ses identifiants sont des réglages secrets PAR COMPTE, chiffrés au repos ; il n'y a plus de boîte du serveur que
    deux comptes sans identifiants lisaient ensemble sans que rien ne le dise (décision d'août 2026 en V18) ;
  - une session IMAP par boîte, avec son verrou : deux personnes ne se volent plus la session, et une passe de fond ne coupe pas la lecture à l'écran ; une
    session qui échoue est jetée (une session à moitié morte produit des erreurs incompréhensibles très loin de la cause), avec UNE reprise ;
  - ouvrir un message ne le marque pas lu (BODY.PEEK) : c'est un geste explicite ;
  - un jeu d'UID n'accepte que des entiers (une valeur libre concaténée dans une commande IMAP y injecterait une commande) ;
  - un rôle de dossier (corbeille, envoyés...) appartient à UN dossier : le drapeau du serveur tranche, le nom n'est qu'une supposition ;
  - supprimer = corbeille ; sans corbeille sur le serveur on REFUSE (la suppression définitive d'une boîte n'est pas portée : elle ne se défait pas) ;
  - déplacer utilise MOVE si le serveur l'annonce, sinon COPY + \\Deleted + EXPUNGE ; le retour retrouve les messages par leur Message-ID (l'UID change de dossier) ;
  - le cache est un cache : le serveur reste la référence, les drapeaux sont relus à chaque liste ; un message parti du serveur sort du cache ;
  - le port décide du mode SMTP (465 : SSL dès la connexion ; sinon STARTTLS) ;
  - le fournisseur exige que l'expéditeur soit le compte authentifié (sinon un courrier de retour arrive plus tard, sans erreur à l'envoi) : on signe du compte ;
  - un courriel LU ne fait jamais partir un courriel : l'envoi est réservé à un humain ou à son compte, un agent prépare un BROUILLON (qui se défait) ;
  - un envoi, réussi ou non, laisse une ligne au journal des envois (destinataire, objet, extrait : pas le corps entier).
Nouveautés V19 : nettoyage du HTML par liste blanche (CN_outils.py), noms de dossiers lisibles (UTF-7 modifié décodé), une classification technique/à traiter/en attente.
"""
from __future__ import annotations

import base64
import email
import imaplib
import re
import smtplib
import threading
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from . import CN_outils as o

EMAIL = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
POOLS = {}                    # compte -> {conn, last, dossier, rw, lock, cle}
IDLE_MAX = 240.0              # au-delà, le serveur aurait coupé de toute façon
CORPS_MAX = 60000
PIECE_MAX = 25 * 1024 * 1024
DRAPEAUX = {"seen": "\\Seen", "flagged": "\\Flagged", "answered": "\\Answered", "draft": "\\Draft"}
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
BOUCLE_LOCALE = ("127.0.0.1", "localhost", "::1")
ENTETES = "(FLAGS RFC822.SIZE BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES)])"


class CourrierErreur(Exception):
    pass


def brancher(ctx):
    o._point = ctx.point
    db = ctx.stockage

    # ------------------------------------------------------------------ réglages et identifiants (par compte)
    def reglage(nom, compte, defaut=""):
        v = ctx.reglage(nom, compte)
        return defaut if v in (None, "") else v

    def entier(nom, defaut):
        try:
            return int(ctx.reglage(nom, "") or defaut)
        except (TypeError, ValueError):
            return defaut

    def identifiants(compte):
        """(hôte, port, identifiant, mot de passe, chiffré) de la boîte de CE compte, ou None. Jamais d'autre boîte."""
        hote = str(reglage("imap_hote", compte)).strip()
        ident = str(reglage("imap_identifiant", compte)).strip()
        mdp = str(reglage("imap_mot_de_passe", compte))
        if not hote or not ident or not mdp:
            return None
        return hote, int(reglage("imap_port", compte, 993)), ident, mdp, bool(reglage("imap_chiffre", compte, True))

    def compte_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("une boîte est celle d'un compte : aucun compte n'agit")
        return c

    def boite_de(compte):
        cr = identifiants(compte)
        if cr is None:
            raise CourrierErreur("aucune boîte n'est rattachée à ce compte (réglages courrier.imap_*)")
        return cr

    # ------------------------------------------------------------------ la session IMAP
    def case(compte):
        cr = boite_de(compte)
        cle = "%s|%s|%s|%s" % (cr[0], cr[1], cr[2], hash(cr[3]))
        c = POOLS.get(compte)
        if c is None or c["cle"] != cle:
            if c is not None:
                abandonner(c)
            c = POOLS[compte] = {"conn": None, "last": 0.0, "dossier": None, "rw": None, "lock": threading.RLock(), "cle": cle}
        return c

    def abandonner(c):
        m = c.get("conn")
        c.update({"conn": None, "dossier": None, "rw": None})
        if m is not None:
            try:
                m.logout()
            except Exception:
                pass

    def ouvrir(compte):
        hote, port, ident, mdp, chiffre = boite_de(compte)
        delai = entier("delai_s", 20)
        if not chiffre and hote not in BOUCLE_LOCALE:
            raise CourrierErreur("connexion IMAP non chiffrée refusée : le mot de passe passerait en clair (seule la boucle locale s'en passe)")
        try:
            m = imaplib.IMAP4_SSL(hote, port, timeout=delai) if chiffre else imaplib.IMAP4(hote, port, timeout=delai)
            m.login(ident, mdp)
            return m
        except Exception as ex:
            raise CourrierErreur("connexion IMAP échouée : %s" % str(ex).replace(mdp, "***")[:200])

    def session(c, compte):
        maintenant = time.time()
        if c["conn"] is not None and maintenant - c["last"] > IDLE_MAX:
            abandonner(c)
        if c["conn"] is not None:
            try:
                c["conn"].noop()                      # la session est-elle encore vivante ?
            except Exception:
                abandonner(c)
        if c["conn"] is None:
            c["conn"] = ouvrir(compte)
            c["dossier"] = c["rw"] = None
        c["last"] = maintenant
        return c["conn"]

    def selectionner(m, c, dossier, lecture_seule):
        if c["dossier"] == dossier and c["rw"] == (not lecture_seule):
            return
        typ, d = m.select(o.citer(dossier), readonly=lecture_seule)
        if typ != "OK":
            raise CourrierErreur("dossier « %s » inaccessible" % dossier)
        c["dossier"], c["rw"] = dossier, not lecture_seule

    def cmd(compte, fn, dossier="INBOX", lecture_seule=True):
        """Exécute fn(M) sur la session de la boîte du compte, avec UNE reprise si la session est tombée entre deux appels (cas courant : le serveur coupe une
        session inactive juste avant notre commande). Le verrou est celui de la boîte."""
        c = case(compte)
        with c["lock"]:
            derniere = None
            for tentative in (1, 2):
                try:
                    m = session(c, compte)
                    selectionner(m, c, dossier, lecture_seule)
                    return fn(m)
                except CourrierErreur as ex:
                    abandonner(c)
                    derniere = ex
                    if "aucune boîte" in str(ex) or "connexion IMAP échouée" in str(ex):
                        break
                except Exception as ex:
                    abandonner(c)
                    derniere = CourrierErreur(str(ex)[:200])
            raise derniere or CourrierErreur("IMAP indisponible")

    # ------------------------------------------------------------------ dossiers
    def lister_dossiers(m):
        typ, data = m.list()
        if typ != "OK":
            raise CourrierErreur("LIST refusé par le serveur")
        sortie = []
        for ligne in data or []:
            s = ligne.decode(errors="replace") if isinstance(ligne, bytes) else str(ligne)
            mm = re.match(r'^\((?P<flags>[^)]*)\)\s+"?(?P<sep>[^" ]*)"?\s+(?P<nom>.+)$', s)
            if not mm:
                continue
            brut = mm.group("nom").strip().strip('"')
            flags = mm.group("flags").lower()
            if "\\noselect" in flags:
                continue
            nom = o.utf7_decoder(brut)
            sortie.append({"nom": nom, "brut": brut, "sep": mm.group("sep") or "/", "role": o.role_du_dossier(nom, flags), "role_flag": bool(o.role_drapeau(flags)),
                           "profondeur": nom.count(mm.group("sep") or "/")})
        sortie.sort(key=lambda x: (0 if x["nom"].upper() == "INBOX" else 1, x["nom"].lower()))
        return o.roles_uniques(sortie, ctx.point)

    def statut(m, brut):
        try:
            typ, d = m.status(o.citer(brut), "(MESSAGES UNSEEN)")
            if typ == "OK" and d:
                s = d[0].decode(errors="replace") if isinstance(d[0], bytes) else str(d[0])
                mt, mu = re.search(r"MESSAGES\s+(\d+)", s), re.search(r"UNSEEN\s+(\d+)", s)
                return int(mt.group(1)) if mt else 0, int(mu.group(1)) if mu else 0
        except Exception:
            pass
        return 0, 0

    def dossiers_vivants(compte):
        """Les dossiers avec leurs compteurs, lus à l'instant."""
        def run(m):
            ds = lister_dossiers(m)
            for d in ds:
                d["total"], d["non_lus"] = statut(m, d["brut"])
            return ds
        ds = cmd(compte, run, "INBOX", True)
        case(compte)["dossiers"] = (time.time(), [{k: v for k, v in d.items() if k not in ("total", "non_lus")} for d in ds])
        return ds

    def dossiers_connus(compte):
        """Les dossiers sans compteurs, d'une liste gardée deux minutes : trouver LE dossier « corbeille » ne doit pas refaire LIST et STATUS à chaque geste."""
        c = case(compte)
        t, liste = c.get("dossiers", (0, None))
        if liste is None or time.time() - t > 120:
            liste = cmd(compte, lister_dossiers, "INBOX", True)
            c["dossiers"] = (time.time(), liste)
        return liste

    def oublier_dossiers(compte):
        case(compte).pop("dossiers", None)

    def dossier_du_role(compte, role):
        for d in dossiers_connus(compte):
            if d["role"] == role:
                return d
        return None

    def brut_du_dossier(compte, nom):
        """Le nom tel que le serveur l'attend : d'après la liste, sinon encodé en UTF-7 modifié."""
        for d in dossiers_connus(compte):
            if nom in (d["nom"], d["brut"]):
                return d["brut"]
        return o.utf7_encoder(nom)

    def nom_dossier(nom):
        nom = str(nom or "INBOX").strip() or "INBOX"
        return o.utf7_decoder(nom)

    # ------------------------------------------------------------------ le cache
    def cache_ecrire(compte, dossier, lignes):
        if not lignes:
            return
        with db.transaction() as cx:
            for v in lignes:
                cx.execute("INSERT OR REPLACE INTO messages(compte, dossier, uid, msg_id, fil, de_addr, de_nom, a_addr, objet, date_brute, date_iso, lu, suivi, repondu, pj, taille, vu_le) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (compte, dossier, v["uid"], v["msg_id"], v["fil"], v["de_addr"], v["de_nom"], v["a_addr"], v["objet"], v["date_brute"], v["date_iso"], v["lu"], v["suivi"],
                            v["repondu"], v["pj"], v["taille"], time.time()))

    def cache_oublier(compte, dossier, uids):
        propres = o.ensemble_uid(uids)
        if propres:
            db.ecrire("DELETE FROM messages WHERE compte=? AND dossier=? AND uid IN (%s)" % ",".join("?" * len(propres)), [compte, dossier] + propres)

    def cache_drapeau(compte, dossier, uids, champ, valeur):
        col = {"seen": "lu", "flagged": "suivi", "answered": "repondu"}.get(champ)
        propres = o.ensemble_uid(uids)
        if col and propres:
            db.ecrire("UPDATE messages SET %s=? WHERE compte=? AND dossier=? AND uid IN (%s)" % (col, ",".join("?" * len(propres))), [1 if valeur else 0, compte, dossier] + propres)

    def analyser_entetes(donnees):
        """{uid: ligne de cache} d'après une réponse FETCH d'en-têtes. La lecture est un POINT D'ÉVOLUTION : points/EC_entetes.py (opération « cache »)."""
        items = []
        for item in donnees or []:
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            meta = item[0].decode(errors="replace") if isinstance(item[0], bytes) else str(item[0])
            items.append({"meta": meta, "raw": base64.b64encode(bytes(item[1])).decode("ascii")})
        return ctx.point("entetes", {"op": "cache", "items": items})["valeur"]

    def ligne_message(v):
        """La ligne que lit l'écran. Le calcul est un POINT D'ÉVOLUTION : points/EC_entetes.py (opération « ligne »)."""
        return ctx.point("entetes", {"op": "ligne", "v": v})["valeur"]

    # ------------------------------------------------------------------ lectures
    def etat(c):
        compte = compte_agit()
        if identifiants(compte) is None:
            return {"configuree": False, "non_lus": 0, "dossiers": [], "recents": [], "passe": None, "gardes": {"total": 0, "avec_texte": 0}}
        ds = db.lire("SELECT nom, role, total, non_lus, maj FROM dossiers WHERE compte=? ORDER BY CASE WHEN upper(nom)='INBOX' THEN 0 ELSE 1 END, nom", (compte,))
        non_lus = next((d["non_lus"] for d in ds if d["nom"].upper() == "INBOX"), 0)
        recents = [{"uid": r["uid"], "de_nom": r["de_nom"], "de_addr": r["de_addr"], "objet": r["objet"], "date_iso": r["date_iso"], "apercu": (r["texte"] or "")[:160]}
                   for r in db.lire("SELECT uid, de_nom, de_addr, objet, date_iso, texte FROM messages WHERE compte=? AND dossier='INBOX' AND lu=0 ORDER BY date_iso DESC LIMIT 5", (compte,))]
        p = db.lire("SELECT ts, duree_ms, nouveaux, textes, dossiers, erreur FROM passes WHERE compte=?", (compte,))
        limite = (datetime.now() - timedelta(days=entier("jours_gardes", 90))).strftime("%Y-%m-%d")
        q = db.lire("SELECT COUNT(*) n, SUM(CASE WHEN texte_le IS NOT NULL THEN 1 ELSE 0 END) t FROM messages WHERE compte=? AND dossier='INBOX' AND date_iso>=?", (compte, limite))[0]
        return {"configuree": True, "boite": identifiants(compte)[2], "non_lus": non_lus, "dossiers": ds, "recents": recents, "passe": p[0] if p else None,
                "gardes": {"total": q["n"] or 0, "avec_texte": q["t"] or 0}}

    def tester_boite(c):
        compte = compte_agit()
        try:
            def run(m):
                ds = lister_dossiers(m)
                return {"ok": True, "dossiers": len(ds), "capacites": " ".join(x.decode() if isinstance(x, bytes) else str(x) for x in (m.capabilities or ()))}
            return cmd(compte, run, "INBOX", True)
        except CourrierErreur as ex:
            return {"ok": False, "erreur": str(ex)}

    def dossiers(c):
        compte = compte_agit()
        try:
            ds = dossiers_vivants(compte)
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        return {"dossiers": [{k: d[k] for k in ("nom", "role", "role_ecarte", "total", "non_lus", "profondeur") if k in d} for d in ds]}

    def lister(c, dossier="INBOX", limite=25, non_lus=False, decalage=0, requete="", etat=""):
        compte = compte_agit()
        dossier = nom_dossier(dossier)
        limite, decalage = max(1, min(int(limite or 25), 200)), max(0, int(decalage or 0))

        def run(m):
            crit = []
            if non_lus:
                crit.append("UNSEEN")
            q = str(requete or "").strip()
            if q:
                crit += ["OR", "OR", "FROM", o.citer(q.replace('"', "")), "SUBJECT", o.citer(q.replace('"', "")), "TEXT", o.citer(q.replace('"', ""))]
            typ, data = m.uid("search", None, *(crit or ["ALL"]))
            if typ != "OK":
                raise CourrierErreur("recherche refusée par le serveur")
            tous = [u.decode() for u in (data[0].split() if data and data[0] else [])]
            connus = {r["uid"]: r for r in db.lire("SELECT * FROM messages WHERE compte=? AND dossier=?", (compte, dossier))}
            classes = {"traiter": 0, "attente": 0, "tech": 0}
            for u in tous:
                if u in connus:
                    classes[o.etat_du_message({"from_addr": connus[u]["de_addr"], "subject": connus[u]["objet"], "answered": connus[u]["repondu"]})] += 1
            filtre = str(etat or "").strip().lower()
            if filtre in classes:
                tous = [u for u in tous if u in connus and o.etat_du_message({"from_addr": connus[u]["de_addr"], "subject": connus[u]["objet"], "answered": connus[u]["repondu"]}) == filtre]
            total = len(tous)
            fenetre = tous[::-1][decalage:decalage + limite]
            manquants = [u for u in fenetre if u not in connus]
            nouveaux = {}
            if manquants:
                typ, d = m.uid("fetch", ",".join(manquants).encode(), ENTETES)
                nouveaux = analyser_entetes(d)
                cache_ecrire(compte, dossier, list(nouveaux.values()))
            drapeaux = {}
            presents = [u for u in fenetre if u in connus]
            if presents:
                typ, d = m.uid("fetch", ",".join(presents).encode(), "(FLAGS)")
                for item in d or []:
                    s = item.decode(errors="replace") if isinstance(item, bytes) else str(item)
                    mu = re.search(r"UID (\d+)", s)
                    if mu:
                        drapeaux[mu.group(1)] = s
            sortie, maj = [], []
            for u in fenetre:
                v = nouveaux.get(u) or (dict(connus[u]) if u in connus else None)
                if v is None:
                    continue
                s = drapeaux.get(u)
                if s is not None:
                    f = (1 if "\\Seen" in s else 0, 1 if "\\Flagged" in s else 0, 1 if "\\Answered" in s else 0)
                    if (v["lu"], v["suivi"], v["repondu"]) != f:
                        maj.append(f + (compte, dossier, u))
                    v = dict(v, lu=f[0], suivi=f[1], repondu=f[2])
                sortie.append(ligne_message(v))
            for f in maj:
                db.ecrire("UPDATE messages SET lu=?, suivi=?, repondu=? WHERE compte=? AND dossier=? AND uid=?", f)
            return {"dossier": dossier, "messages": sortie, "total": total, "decalage": decalage, "limite": limite, "classes": classes, "encore": decalage + len(sortie) < total}
        try:
            return cmd(compte, run, brut_du_dossier(compte, dossier), True)
        except CourrierErreur as ex:
            raise ValueError(str(ex))

    def lire(c, uid="", dossier="INBOX", html=False, images=False):
        compte = compte_agit()
        dossier = nom_dossier(dossier)
        propres = o.ensemble_uid(uid)
        if len(propres) != 1:
            raise ValueError("un message se désigne par un seul UID numérique")
        u = propres[0]

        def run(m):
            typ, d = m.uid("fetch", u.encode(), "(BODY.PEEK[])")            # ouvrir ne marque pas lu : c'est un geste explicite
            if not d or not d[0] or not isinstance(d[0], tuple):
                raise CourrierErreur("message introuvable")
            msg = email.message_from_bytes(d[0][1])
            texte, page = o.corps(msg)
            r = {"uid": u, "dossier": dossier, "de": o.decoder_entete(msg.get("From")), "a": o.decoder_entete(msg.get("To")), "cc": o.decoder_entete(msg.get("Cc")),
                 "repondre_a": o.decoder_entete(msg.get("Reply-To")), "objet": o.decoder_entete(msg.get("Subject")) or "(sans objet)", "date": o.decoder_entete(msg.get("Date")),
                 "date_iso": o.date_iso(o.decoder_entete(msg.get("Date"))), "message_id": (msg.get("Message-ID") or "").strip(), "references": (msg.get("References") or "").strip(),
                 "fil": o.cle_de_fil(msg), "texte": texte, "pieces": o.pieces_jointes(msg)}
            if html and page:
                r["html"], r["images_distantes"] = o.assainir_html(page, bool(images))
            return r
        try:
            return cmd(compte, run, brut_du_dossier(compte, dossier), True)
        except CourrierErreur as ex:
            raise ValueError(str(ex))

    def piece(c, uid="", index=0, dossier="INBOX"):
        compte = compte_agit()
        dossier = nom_dossier(dossier)
        propres = o.ensemble_uid(uid)
        if len(propres) != 1:
            raise ValueError("un message se désigne par un seul UID numérique")

        def run(m):
            typ, d = m.uid("fetch", propres[0].encode(), "(BODY.PEEK[])")
            if not d or not d[0] or not isinstance(d[0], tuple):
                raise CourrierErreur("message introuvable")
            r = o.piece_numero(email.message_from_bytes(d[0][1]), index)
            if r is None:
                raise CourrierErreur("pièce jointe introuvable")
            if len(r[2]) > PIECE_MAX:
                raise CourrierErreur("pièce jointe trop grosse (%d Mo au plus)" % (PIECE_MAX // 1048576))
            return {"nom": r[0], "type": r[1], "taille": len(r[2]), "donnees_b64": base64.b64encode(r[2]).decode("ascii")}
        try:
            return cmd(compte, run, brut_du_dossier(compte, dossier), True)
        except CourrierErreur as ex:
            raise ValueError(str(ex))

    def envoyes(c, limite=50):
        compte = compte_agit()
        return {"envois": db.lire("SELECT ts, a, cc, objet, extrait, ok, raison FROM envoyes WHERE compte=? ORDER BY id DESC LIMIT ?", (compte, max(1, min(int(limite or 50), 500))))}

    # ------------------------------------------------------------------ gestes sur les messages
    def msgids(m, uids):
        sortie = {}
        typ, d = m.uid("fetch", ",".join(uids).encode(), "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
        for item in d or []:
            if isinstance(item, tuple) and len(item) > 1:
                mu = re.search(r"UID (\d+)", item[0].decode(errors="replace"))
                mm = email.message_from_bytes(item[1])
                if mu and (mm.get("Message-ID") or "").strip():
                    sortie[mu.group(1)] = mm.get("Message-ID").strip()
        return sortie

    def uids_par_msgid(m, ids):
        trouves = []
        for i in ids:
            typ, d = m.uid("search", None, "HEADER", "Message-ID", o.citer(i.replace('"', "")))
            if typ == "OK" and d and d[0]:
                trouves += [u.decode() for u in d[0].split()]
        return trouves

    def drapeau(c, uids=None, champ="seen", valeur=True, dossier="INBOX"):
        compte = compte_agit()
        dossier = nom_dossier(dossier)
        fl = DRAPEAUX.get(str(champ or "").lower())
        if not fl:
            raise ValueError("drapeau inconnu (%s)" % ", ".join(sorted(DRAPEAUX)))
        jeu = o.ensemble_uid(uids)
        if not jeu:
            raise ValueError("aucun message valide")

        def run(m):
            avant = {}
            typ, d = m.uid("fetch", ",".join(jeu).encode(), "(FLAGS)")
            for item in d or []:
                s = item.decode(errors="replace") if isinstance(item, bytes) else str(item)
                mu = re.search(r"UID (\d+)", s)
                if mu:
                    avant[mu.group(1)] = fl in s
            typ, _ = m.uid("store", ",".join(jeu).encode(), "+FLAGS" if valeur else "-FLAGS", "(%s)" % fl)
            if typ != "OK":
                raise CourrierErreur("le serveur a refusé la modification")
            return {"avant": avant}
        try:
            r = cmd(compte, run, brut_du_dossier(compte, dossier), False)
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        cache_drapeau(compte, dossier, jeu, str(champ).lower(), bool(valeur))
        return {"compte": compte, "dossier": dossier, "champ": str(champ).lower(), "valeur": bool(valeur), "uids": jeu, "avant": r["avant"]}

    def prouver_drapeau(c, res):
        fl = DRAPEAUX[res["champ"]]

        def run(m):
            typ, d = m.uid("fetch", ",".join(res["uids"]).encode(), "(FLAGS)")
            etats = {}
            for item in d or []:
                s = item.decode(errors="replace") if isinstance(item, bytes) else str(item)
                mu = re.search(r"UID (\d+)", s)
                if mu:
                    etats[mu.group(1)] = fl in s
            return all(etats.get(u) == res["valeur"] for u in res["uids"])
        return cmd(res["compte"], run, brut_du_dossier(res["compte"], res["dossier"]), True)

    def defaire_drapeau(c, res):
        fl = DRAPEAUX[res["champ"]]

        def run(m):
            for u, etait in res["avant"].items():
                m.uid("store", u.encode(), "+FLAGS" if etait else "-FLAGS", "(%s)" % fl)
        cmd(res["compte"], run, brut_du_dossier(res["compte"], res["dossier"]), False)
        for u, etait in res["avant"].items():
            cache_drapeau(res["compte"], res["dossier"], [u], res["champ"], etait)

    def deplacer_vers(compte, jeu, source, destination):
        """Déplace ; rend les Message-ID (pour le retour : l'UID change de dossier) et la méthode."""
        dest_brut = brut_du_dossier(compte, destination)

        def run(m):
            ids = msgids(m, jeu)
            capa = " ".join(x.decode() if isinstance(x, bytes) else str(x) for x in (m.capabilities or ())).upper()
            ensemble = ",".join(jeu).encode()
            if "MOVE" in capa:
                typ, _ = m.uid("move", ensemble, o.citer(dest_brut))
                if typ == "OK":
                    return {"methode": "MOVE", "ids": list(ids.values())}
            typ, _ = m.uid("copy", ensemble, o.citer(dest_brut))
            if typ != "OK":
                raise CourrierErreur("copie vers « %s » refusée" % destination)
            m.uid("store", ensemble, "+FLAGS", "(\\Deleted)")
            try:
                m.expunge()
            except Exception:
                pass
            return {"methode": "COPY", "ids": list(ids.values())}
        r = cmd(compte, run, brut_du_dossier(compte, source), False)
        cache_oublier(compte, source, jeu)
        return r

    def deplacer(c, uids=None, destination="", dossier="INBOX"):
        compte = compte_agit()
        dossier, destination = nom_dossier(dossier), nom_nonvide(destination)
        jeu = o.ensemble_uid(uids)
        if not jeu:
            raise ValueError("aucun message valide")
        if destination == dossier:
            raise ValueError("la destination est le dossier d'origine")
        try:
            r = deplacer_vers(compte, jeu, dossier, destination)
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        return {"compte": compte, "source": dossier, "destination": destination, "uids": jeu, "ids": r["ids"], "methode": r["methode"]}

    def nom_nonvide(nom):
        n = str(nom or "").strip()
        if not n:
            raise ValueError("dossier de destination requis")
        return o.utf7_decoder(n)

    def prouver_deplace(c, res):
        def run(m):
            return len(uids_par_msgid(m, res["ids"])) >= len(res["ids"]) if res["ids"] else True
        return cmd(res["compte"], run, brut_du_dossier(res["compte"], res["destination"]), True)

    def defaire_deplace(c, res):
        if not res["ids"]:
            return
        src = o.citer(brut_du_dossier(res["compte"], res["source"]))
        dest = brut_du_dossier(res["compte"], res["destination"])

        def run(m):
            uids = uids_par_msgid(m, res["ids"])
            if uids:
                ensemble = ",".join(uids).encode()
                capa = " ".join(x.decode() if isinstance(x, bytes) else str(x) for x in (m.capabilities or ())).upper()
                if "MOVE" in capa:
                    m.uid("move", ensemble, src)
                else:
                    m.uid("copy", ensemble, src)
                    m.uid("store", ensemble, "+FLAGS", "(\\Deleted)")
                    m.expunge()
        cmd(res["compte"], run, dest, False)

    def supprimer(c, uids=None, dossier="INBOX"):
        compte = compte_agit()
        dossier = nom_dossier(dossier)
        jeu = o.ensemble_uid(uids)
        if not jeu:
            raise ValueError("aucun message valide")
        try:
            corbeille = dossier_du_role(compte, "trash")
            if corbeille is None:
                raise ValueError("ce serveur n'expose pas de corbeille : une suppression définitive ne se défait pas, elle n'est pas portée (utilisez le webmail du fournisseur)")
            if corbeille["nom"] == dossier:
                raise ValueError("ces messages sont déjà dans la corbeille")
            r = deplacer_vers(compte, jeu, dossier, corbeille["nom"])
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        return {"compte": compte, "source": dossier, "destination": corbeille["nom"], "uids": jeu, "ids": r["ids"], "methode": r["methode"]}

    def archiver(c, uids=None, dossier="INBOX"):
        compte = compte_agit()
        dossier = nom_dossier(dossier)
        jeu = o.ensemble_uid(uids)
        if not jeu:
            raise ValueError("aucun message valide")
        try:
            cible = dossier_du_role(compte, "archive")
            if cible is None:
                cible = {"nom": "Archive"}
                creer_dossier(compte, "Archive", tolerer_existant=True)
            r = deplacer_vers(compte, jeu, dossier, cible["nom"])
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        return {"compte": compte, "source": dossier, "destination": cible["nom"], "uids": jeu, "ids": r["ids"], "methode": r["methode"]}

    def copier(c, uids=None, destination="", dossier="INBOX"):
        compte = compte_agit()
        dossier, destination = nom_dossier(dossier), nom_nonvide(destination)
        jeu = o.ensemble_uid(uids)
        if not jeu:
            raise ValueError("aucun message valide")

        def run(m):
            ids = msgids(m, jeu)
            typ, _ = m.uid("copy", ",".join(jeu).encode(), o.citer(brut_du_dossier(compte, destination)))
            if typ != "OK":
                raise CourrierErreur("copie vers « %s » refusée" % destination)
            return list(ids.values())
        try:
            ids = cmd(compte, run, brut_du_dossier(compte, dossier), True)
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        return {"compte": compte, "source": dossier, "destination": destination, "uids": jeu, "ids": ids}

    def prouver_copie(c, res):
        def run(m):
            return len(uids_par_msgid(m, res["ids"])) >= len(res["ids"]) if res["ids"] else True
        return cmd(res["compte"], run, brut_du_dossier(res["compte"], res["destination"]), True)

    def defaire_copie(c, res):
        """Retire les copies faites : celles de la destination qui portent ces Message-ID — la source n'est pas touchée."""
        def run(m):
            uids = uids_par_msgid(m, res["ids"])
            if uids:
                ensemble = ",".join(uids).encode()
                m.uid("store", ensemble, "+FLAGS", "(\\Deleted)")
                m.expunge()
        cmd(res["compte"], run, brut_du_dossier(res["compte"], res["destination"]), False)

    # ------------------------------------------------------------------ dossiers : créer, renommer
    def creer_dossier(compte, nom, tolerer_existant=False):
        def run(m):
            typ, d = m.create(o.citer(o.utf7_encoder(nom)))
            if typ != "OK":
                detail = b" ".join(x for x in (d or []) if isinstance(x, bytes)).decode(errors="replace")
                if tolerer_existant and "exist" in detail.lower():
                    return False
                raise CourrierErreur(detail or "création refusée")
            try:
                m.subscribe(o.citer(o.utf7_encoder(nom)))
            except Exception:
                pass
            return True
        r = cmd(compte, run, "INBOX", True)
        oublier_dossiers(compte)
        return r

    def dossier_creer(c, nom=""):
        compte = compte_agit()
        nom = str(nom or "").strip()
        if not nom or len(nom) > 120:
            raise ValueError("nom de dossier requis (120 caractères au plus)")
        try:
            creer_dossier(compte, nom)
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        return {"compte": compte, "nom": nom}

    def prouver_dossier(c, res):
        return any(d["nom"] == res["nom"] for d in dossiers_vivants(res["compte"]))

    def defaire_dossier_cree(c, res):
        """Le dossier que cet acte vient de créer est vide : on le retire (et lui seul)."""
        def run(m):
            m.unsubscribe(o.citer(o.utf7_encoder(res["nom"])))
            m.delete(o.citer(o.utf7_encoder(res["nom"])))
        cmd(res["compte"], run, "INBOX", True)
        oublier_dossiers(res["compte"])

    def dossier_renommer(c, ancien="", nouveau=""):
        compte = compte_agit()
        ancien, nouveau = str(ancien or "").strip(), str(nouveau or "").strip()
        if not ancien or not nouveau or ancien.upper() == "INBOX":
            raise ValueError("ancien et nouveau nom requis (la boîte de réception ne se renomme pas)")

        def run(m):
            typ, d = m.rename(o.citer(brut_du_dossier(compte, ancien)), o.citer(o.utf7_encoder(nouveau)))
            if typ != "OK":
                raise CourrierErreur(b" ".join(x for x in (d or []) if isinstance(x, bytes)).decode(errors="replace") or "renommage refusé")
        try:
            cmd(compte, run, "INBOX", True)
            oublier_dossiers(compte)
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        return {"compte": compte, "ancien": ancien, "nouveau": nouveau}

    def prouver_renomme(c, res):
        noms = {d["nom"] for d in dossiers_vivants(res["compte"])}
        return res["nouveau"] in noms and res["ancien"] not in noms

    def defaire_renomme(c, res):
        def run(m):
            m.rename(o.citer(o.utf7_encoder(res["nouveau"])), o.citer(o.utf7_encoder(res["ancien"])))
        cmd(res["compte"], run, "INBOX", True)
        oublier_dossiers(res["compte"])

    # ------------------------------------------------------------------ écrire : brouillon et envoi
    def liste_adresses(texte, nom):
        adresses = [a.strip() for a in re.split(r"[,;]", str(texte or "")) if a.strip()]
        if len(adresses) > 20:
            raise ValueError("%s : 20 adresses au plus" % nom)
        for a in adresses:
            if not EMAIL.match(a):
                raise ValueError("%s : adresse invalide « %s »" % (nom, a))
        return adresses

    def construire(compte, a, objet, texte, cc="", repond_a_message="", references=""):
        destinataires, copies = liste_adresses(a, "destinataire"), liste_adresses(cc, "copie")
        if not destinataires:
            raise ValueError("un destinataire au moins")
        corps = str(texte or "")
        if len(corps) > 200000:
            raise ValueError("message trop long (200 000 caractères au plus)")
        expediteur = str(reglage("smtp_expediteur", compte) or reglage("imap_identifiant", compte)).strip()
        if not EMAIL.match(expediteur):
            expediteur = str(reglage("imap_identifiant", compte)).strip()
        msg = EmailMessage()
        msg["From"] = expediteur
        msg["To"] = ", ".join(destinataires)
        if copies:
            msg["Cc"] = ", ".join(copies)
        msg["Subject"] = (str(objet or "").strip() or "(sans objet)")[:300]
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        if repond_a_message:
            msg["In-Reply-To"] = repond_a_message
            msg["References"] = references or repond_a_message
        msg.set_content(corps)
        return msg, destinataires + copies

    def brouillon_creer(c, a="", objet="", texte="", cc="", repond_a_message="", references=""):
        compte = compte_agit()
        msg, _ = construire(compte, a, objet, texte, cc, repond_a_message, references)
        try:
            dossier = dossier_du_role(compte, "drafts")
            if dossier is None:
                raise ValueError("ce serveur n'expose pas de dossier de brouillons")

            def run(m):
                typ, _ = m.append(o.citer(dossier["brut"]), "\\Draft", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
                if typ != "OK":
                    raise CourrierErreur("le serveur a refusé le brouillon")
            cmd(compte, run, "INBOX", True)
        except CourrierErreur as ex:
            raise ValueError(str(ex))
        return {"compte": compte, "dossier": dossier["nom"], "message_id": msg["Message-ID"]}

    def prouver_brouillon(c, res):
        return bool(cmd(res["compte"], lambda m: uids_par_msgid(m, [res["message_id"]]), brut_du_dossier(res["compte"], res["dossier"]), True))

    def defaire_brouillon(c, res):
        def run(m):
            uids = uids_par_msgid(m, [res["message_id"]])
            if uids:
                m.uid("store", ",".join(uids).encode(), "+FLAGS", "(\\Deleted)")
                m.expunge()
        cmd(res["compte"], run, brut_du_dossier(res["compte"], res["dossier"]), False)

    def smtp_ouvrir(hote, port, delai):
        """Le port décide : 465 parle SSL dès la connexion (s'y présenter en clair fait attendre le serveur puis « Connection unexpectedly closed »), les autres en STARTTLS.
        Sans chiffrement, on ne présente jamais un mot de passe : seule la boucle locale (un relais sur la machine) s'en passe."""
        if int(port) == 465:
            return smtplib.SMTP_SSL(hote, int(port), timeout=delai), False
        return smtplib.SMTP(hote, int(port), timeout=delai), hote not in BOUCLE_LOCALE

    def journal_envoi(compte, a, cc, objet, texte, ok, raison):
        db.ecrire("INSERT INTO envoyes(ts, compte, a, cc, objet, extrait, ok, raison) VALUES (?,?,?,?,?,?,?,?)",
                  (time.time(), compte, str(a)[:300], str(cc)[:300], str(objet)[:300], str(texte)[:500], 1 if ok else 0, str(raison)[:300]))

    def envoyer(c, a="", objet="", texte="", cc="", repond_a_message="", references=""):
        compte = compte_agit()
        hote = str(reglage("smtp_hote", compte)).strip()
        ident = str(reglage("smtp_identifiant", compte) or reglage("imap_identifiant", compte)).strip()
        mdp = str(reglage("smtp_mot_de_passe", compte) or reglage("imap_mot_de_passe", compte))
        if not hote or not ident or not mdp:
            raise ValueError("le serveur d'envoi n'est pas réglé (réglages courrier.smtp_*)")
        msg, destinataires = construire(compte, a, objet, texte, cc, repond_a_message, references)
        port = int(reglage("smtp_port", compte, 587))
        try:
            srv, tls = smtp_ouvrir(hote, port, entier("delai_s", 20))
            with srv as s:
                if tls:
                    s.starttls()
                s.login(ident, mdp)
                s.send_message(msg, from_addr=ident if EMAIL.match(ident) else None, to_addrs=destinataires)
        except Exception as ex:
            raison = str(ex).replace(mdp, "***")[:200]
            journal_envoi(compte, a, cc, objet, texte, False, raison)
            raise ValueError("envoi impossible : %s" % raison)
        journal_envoi(compte, a, cc, objet, texte, True, "")
        copie = False
        try:
            envoyes_d = dossier_du_role(compte, "sent")
            if envoyes_d is not None:
                cmd(compte, lambda m: m.append(o.citer(envoyes_d["brut"]), "\\Seen", imaplib.Time2Internaldate(time.time()), msg.as_bytes()), "INBOX", True)
                copie = True
        except Exception:
            copie = False
        return {"compte": compte, "a": destinataires, "objet": msg["Subject"], "message_id": msg["Message-ID"], "copie_gardee": copie}

    def prouver_envoye(c, res):
        return bool(db.lire("SELECT 1 FROM envoyes WHERE compte=? AND ok=1 AND objet=? ORDER BY id DESC LIMIT 1", (res["compte"], res["objet"])))

    def defaire_envoye(c, res):
        return None                 # un courriel parti ne se rappelle pas : le retour est de ne pas en envoyer sans l'avoir relu (brouillon d'abord)

    # ------------------------------------------------------------------ la passe de fond
    def comptes_avec_boite():
        r = ctx.executer_lecture("comptes.lister") or {}
        return [x["compte"] for x in r.get("comptes", []) if identifiants(x["compte"]) is not None]

    def passe_compte(compte):
        t0 = time.time()
        maintenant = time.time()
        limite = (datetime.now() - timedelta(days=entier("jours_gardes", 90))).strftime("%Y-%m-%d")
        lot = entier("lot_corps", 25)
        bilan = {"nouveaux": [], "textes": 0, "dossiers": 0, "erreur": "", "partis": 0}
        try:
            ds = dossiers_vivants(compte)
            with db.transaction() as cx:
                cx.execute("DELETE FROM dossiers WHERE compte=?", (compte,))
                for d in ds:
                    cx.execute("INSERT INTO dossiers(compte, nom, role, total, non_lus, maj) VALUES (?,?,?,?,?,?)", (compte, d["nom"], d["role"], d["total"], d["non_lus"], maintenant))
            bilan["dossiers"] = len(ds)
            suivis = ["INBOX"] + [d["nom"] for d in ds if d["role"] == "sent"][:1]
            for dossier in suivis:
                connus = {r["uid"] for r in db.lire("SELECT uid FROM messages WHERE compte=? AND dossier=?", (compte, dossier))}
                brut = brut_du_dossier(compte, dossier)

                def run(m, connus=connus, dossier=dossier):
                    typ, data = m.uid("search", None, "ALL")
                    if typ != "OK":
                        raise CourrierErreur("SEARCH refusé")
                    tous = [u.decode() for u in (data[0].split() if data and data[0] else [])]
                    recents = tous[-60:]
                    manquants = [u for u in recents if u not in connus]
                    nouveaux = {}
                    if manquants:
                        typ, d = m.uid("fetch", ",".join(manquants).encode(), ENTETES)
                        nouveaux = analyser_entetes(d)
                    return {"tous": set(tous), "nouveaux": nouveaux}
                r = cmd(compte, run, brut, True)
                cache_ecrire(compte, dossier, list(r["nouveaux"].values()))
                if dossier == "INBOX":
                    for v in r["nouveaux"].values():
                        if not v["lu"]:
                            bilan["nouveaux"].append({"uid": v["uid"], "de": v["de_nom"] or v["de_addr"], "objet": v["objet"]})
                partis = [u for u in connus if u not in r["tous"]]
                if partis and r["tous"]:
                    cache_oublier(compte, dossier, partis)
                    bilan["partis"] += len(partis)
                a_lire = [x["uid"] for x in db.lire("SELECT uid FROM messages WHERE compte=? AND dossier=? AND texte_le IS NULL AND date_iso>=? ORDER BY date_iso DESC LIMIT ?", (compte, dossier, limite, lot))]
                if not a_lire:
                    continue

                def lire_lot(m, a_lire=a_lire):
                    sortie = {}
                    typ, d = m.uid("fetch", ",".join(a_lire).encode(), "(BODY.PEEK[])")
                    for item in d or []:
                        if not isinstance(item, tuple) or len(item) < 2:
                            continue
                        mu = re.search(r"UID (\d+)", item[0].decode(errors="replace"))
                        if not mu:
                            continue
                        try:
                            sortie[mu.group(1)] = o.corps(email.message_from_bytes(item[1]))[0][:CORPS_MAX]
                        except Exception:
                            sortie[mu.group(1)] = ""
                    return sortie
                textes = cmd(compte, lire_lot, brut, True)
                with db.transaction() as cx:
                    for u in a_lire:
                        cx.execute("UPDATE messages SET texte=?, texte_le=? WHERE compte=? AND dossier=? AND uid=?", (textes.get(u, ""), maintenant, compte, dossier, u))
                bilan["textes"] += len(textes)
            db.ecrire("UPDATE messages SET texte='' WHERE compte=? AND texte<>'' AND date_iso<?", (compte, limite))       # le cache n'est pas une archive : trois mois
        except CourrierErreur as ex:
            bilan["erreur"] = str(ex)[:200]
        except Exception as ex:
            bilan["erreur"] = "passe interrompue : %s" % str(ex)[:160]
        bilan["duree_ms"] = int((time.time() - t0) * 1000)
        db.ecrire("INSERT OR REPLACE INTO passes(compte, ts, duree_ms, nouveaux, textes, dossiers, erreur) VALUES (?,?,?,?,?,?,?)",
                  (compte, maintenant, bilan["duree_ms"], len(bilan["nouveaux"]), bilan["textes"], bilan["dossiers"], bilan["erreur"]))
        return bilan

    def passe(c):
        for compte in comptes_avec_boite():
            bilan = passe_compte(compte)
            for n in bilan["nouveaux"][:5]:
                c.emettre("courrier.nouveau", objet=("courrier", compte), donnees={"uid": n["uid"], "de": n["de"], "objet": n["objet"]}, compte=compte)
            if bilan["erreur"]:
                c.poser("courrier", compte, "Boîte de %s" % compte, etat="en_panne", donnees={"erreur": bilan["erreur"]})
            else:
                c.poser("courrier", compte, "Boîte de %s" % compte, etat="ok", donnees={"non_lus": next((d["non_lus"] for d in db.lire("SELECT non_lus FROM dossiers WHERE compte=? AND nom='INBOX'", (compte,))), 0)})

    def det_boite(c):
        """La boîte d'un compte ne se lit plus : le constat n'est visible que de ce compte (son courrier n'est pas l'affaire des autres)."""
        return [{"objet": ("courrier", x["id"]), "compte": x["id"], "titre": "Votre boîte mail ne se lit plus", "detail": x["donnees"].get("erreur", "")}
                for x in c.lister(portee=c.TOUT, type="courrier", etat="en_panne")]

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.moteur("passe", passe)
    c.detecteur("boite_en_panne", det_boite)
    def jours_de(quand):
        """Le nombre de jours entre aujourd'hui et une date « AAAA-MM-JJ… » (négatif : dépassée) ; None si elle est illisible."""
        s = str(quand or "")[:10]
        try:
            t = time.mktime(time.strptime(s, "%Y-%m-%d"))
        except Exception:
            return None
        return int(round((t - time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))) / 86400))

    def item_jour(bande, quoi, titre, detail="", nat="", ref="", poids=0, ou="", geste=("Ouvrir", "ouvrir")):
        return {"bande": bande, "quoi": quoi, "titre": str(titre or "")[:160], "detail": str(detail or "")[:200], "nat": nat, "ref": str(ref or ""), "poids": int(poids), "ou": ou,
                "geste": list(geste) if geste else None}

    def signal_jour(c):
        """Le courrier non lu, depuis ce que la passe a gardé : jamais l'IMAP ici."""
        e = etat(c)
        if not e.get("configuree"):
            return {"items": [], "meta": {"configuree": False}}
        out = []
        for m in (e.get("recents") or [])[:3]:
            out.append(item_jour("jour", "mail", "%s — %s" % (m.get("de_nom") or m.get("de_addr") or "?", m.get("objet") or "(sans objet)"), "Non lu.", "mail", m.get("uid"), 25, "mail", geste=("Lire", "ouvrir")))
        n = int(e.get("non_lus") or 0)
        if n > 3:
            out.append(item_jour("regarder", "mail", "%d courriels non lus" % n, "Dans l'INBOX.", "mail", "", 20, "mail", geste=("Lire", "ouvrir")))
        return {"items": out, "meta": {"configuree": True, "non_lus": n, "gardes": (e.get("gardes") or {}).get("total", 0)}}

    for cid, f in (("etat", etat), ("signal_jour", signal_jour), ("tester_boite", tester_boite), ("dossiers", dossiers), ("lister", lister), ("lire", lire), ("piece", piece), ("envoyes", envoyes)):
        c.implementer(cid, f)
    c.implementer("drapeau", drapeau, prouver_drapeau, defaire_drapeau, simuler=lambda x, champ="seen", valeur=True, **_: "poserait/retirerait le drapeau %s" % champ)
    c.implementer("deplacer", deplacer, prouver_deplace, defaire_deplace, simuler=lambda x, destination="", **_: "déplacerait les messages vers %s" % destination)
    c.implementer("supprimer", supprimer, prouver_deplace, defaire_deplace, simuler=lambda x, **_: "mettrait les messages à la corbeille")
    c.implementer("archiver", archiver, prouver_deplace, defaire_deplace, simuler=lambda x, **_: "rangerait les messages à l'archive")
    c.implementer("copier", copier, prouver_copie, defaire_copie, simuler=lambda x, destination="", **_: "copierait les messages vers %s" % destination)
    c.implementer("dossier_creer", dossier_creer, prouver_dossier, defaire_dossier_cree, simuler=lambda x, nom="", **_: "créerait le dossier %s" % nom)
    c.implementer("dossier_renommer", dossier_renommer, prouver_renomme, defaire_renomme, simuler=lambda x, ancien="", nouveau="", **_: "renommerait %s en %s" % (ancien, nouveau))
    c.implementer("brouillon_creer", brouillon_creer, prouver_brouillon, defaire_brouillon, simuler=lambda x, objet="", **_: "préparerait le brouillon « %s »" % objet)
    c.implementer("envoyer", envoyer, prouver_envoye, defaire_envoye, simuler=lambda x, a="", objet="", **_: "enverrait « %s » à %s" % (objet, a))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : CourrierErreur, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
