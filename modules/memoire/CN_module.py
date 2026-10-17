# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La mémoire
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : CN
# VERSION CN : 0.1.0  #61c6ee
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La mémoire.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=61c6ee ▼▼▼
"""La mémoire.

Portée de la V18 (l'« îlot mémoire » : `memoire_*`, `perception_*`, `chaine_*`), avec ses leçons — elles sont payées :
  - UNE porte d'écriture. Rien d'autre n'écrit dans les souvenirs. Les gardes vont de la moins chère à la plus chère ; un refus s'écrit au journal avec sa raison, et se rend comme un
    RÉSULTAT (jamais une exception : un agent qui essuie des refus ne doit pas voir son palier baisser pour une garde qui a fait son travail) ;
  - la NATURE est exigée : « etat-courant » porte une sonde rejouable éprouvée à l'écriture, « constat » est daté et ne sera jamais relu. Le muet est refusé : ranger d'office serait décider
    à la place de celui qui écrit, en silence ;
  - rien ne se réécrit en place : une correction est une version nouvelle liée à l'ancienne (« plus récent et plus fort » : humain > preuve d'outil > observé > inféré) ; plus faible,
    la nouvelle entre CONTESTÉE et un doute s'ouvre ; la version d'avant reste lisible. La seule exception est la purge d'un secret entré par erreur, et le geste reste au journal ;
  - le MÊME FAIT SOUS UNE AUTRE CLÉ est une version, pas une fiche de plus (dix fiches pour un seul config.json vide) ;
  - un état passager n'écrase pas une catégorie stable ; un état se MESURE (perception), il ne se rappelle pas, et « je ne sais plus, dernier relevé à T » vaut mieux qu'un vieux fait servi
    comme présent ; chaque souvenir cité porte sa fraîcheur ;
  - le cloisonnement est DANS la requête : un souvenir hors de la portée n'existe pas (introuvable, jamais interdit) ; l'administrateur ne voit pas les comptes ;
  - le veto : une écriture critique d'un agent attend en quarantaine, l'ancienne version reste servie ; les gardes mécaniques ne sont qu'un SIGNAL pour le relecteur, ils ne décident seuls
    que lorsqu'il est absent ;
  - le doute est un objet : la contradiction ne dort pas dans un statut, elle se pose à un humain (deux par tour, jamais deux fois le même jour, trois fois au plus), en français ;
  - le journal est chaîné par empreintes depuis une genèse constante ; une altération se voit au recalcul, elle ne s'empêche pas ; ce qui se compte sans être un geste va au cadran ;
  - le modèle ne reçoit l'échange qu'en DONNÉES, jamais en instructions ; la distillation se fait hors du chemin de la réponse (file + moteur), jamais dans un fil.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone

from . import CN_outils as o
from . import CN_moteurs as page_moteurs

SYSTEME = ("cassandra", "itare", "noyau", "operateur")
RESTAURE = ("statut", "valide_a", "maj_le", "force", "confiance", "remplace", "version")


class Refus(Exception):
    def __init__(self, raison, detail=""):
        super().__init__(raison)
        self.raison, self.detail = raison, str(detail)[:160]


def brancher(ctx):
    db = ctx.stockage

    # ------------------------------------------------------------------ qui, et jusqu'où
    def compte_courant():
        return ctx.compte or ""

    def acteur_courant():
        return ctx.acteur or compte_courant() or "cassandra"

    def est_systeme(compte=None):
        c = compte_courant() if compte is None else compte
        return not c or c in SYSTEME

    def portee(compte=None):
        """Ce qu'un lecteur a le droit de rappeler. Le cloisonnement est DANS la requête, jamais dans la bonne volonté d'un agent."""
        c = compte_courant() if compte is None else compte
        if est_systeme(c):
            return ["itare", "partage", "cassandra"] if (c == "itare" or (not c and acteur_courant() == "itare")) else ["cassandra", "partage"]
        return ["compte:" + c, "partage", "cassandra"] if ctx.est_admin(c) else ["compte:" + c]

    def proprietaire_defaut(categorie):
        """Le propriétaire d'une écriture faite maintenant : « cassandra » hors compte, « itare » pour le second agent, « partage » pour un fait de machine appris au service d'un
        administrateur, « compte:x » pour tout le reste — et toujours pour la personne."""
        c = compte_courant()
        if est_systeme(c):
            return "itare" if (c == "itare" or acteur_courant() == "itare") else "cassandra"
        if categorie != "personne" and ctx.est_admin(c):
            return "partage"
        return "compte:" + c

    def lecture(cap, **a):
        try:
            return ctx.executer_lecture(cap, **a)
        except Exception:
            return None

    # ------------------------------------------------------------------ le journal chaîné
    def journal_cx(cx, verbe, memoire_id, details, acteur=""):
        """Une ligne chaînée. Dans la transaction de l'acte : rien de partiel si l'acte échoue."""
        d = details if isinstance(details, str) else json.dumps(details, ensure_ascii=False)
        d = d[:1500]
        ts = o.maintenant()
        r = cx.execute("SELECT hash FROM journal ORDER BY id DESC LIMIT 1").fetchone()
        prev = r["hash"] if r else o.GENESE
        cx.execute("INSERT INTO journal(ts, acteur, verbe, memoire_id, details, hash, previous_hash) VALUES (?,?,?,?,?,?,?)",
                   (ts, str(acteur or "cassandra")[:80], verbe, memoire_id, d, o.empreinte(prev, ts, str(acteur or "cassandra")[:80], verbe, memoire_id, d), prev))

    def journal(verbe, memoire_id, details, acteur=""):
        with db.transaction() as cx:
            journal_cx(cx, verbe, memoire_id, details, acteur or acteur_courant())

    def cadran_noter(cle, detail=None):
        """Un compteur, pas un geste : n augmente, le dernier détail reste lisible."""
        with db.transaction() as cx:
            cx.execute("INSERT INTO cadran(cle, n, dernier_ts, dernier) VALUES (?,1,?,?) ON CONFLICT(cle) DO UPDATE SET n=n+1, dernier_ts=excluded.dernier_ts, dernier=excluded.dernier",
                       (str(cle)[:40], o.maintenant(), json.dumps(detail, ensure_ascii=False)[:400] if detail is not None else None))

    def cadran():
        return {r["cle"]: {"n": r["n"], "dernier_ts": r["dernier_ts"]} for r in db.lire("SELECT cle, n, dernier_ts FROM cadran")}

    def chaine_verifier_coeur():
        prev, n, rupture = o.GENESE, 0, None
        for e in db.lire("SELECT id, ts, acteur, verbe, memoire_id, details, hash, previous_hash FROM journal ORDER BY id"):
            if e["previous_hash"] != prev or o.empreinte(prev, e["ts"], e["acteur"], e["verbe"], e["memoire_id"], e["details"] or "") != e["hash"]:
                rupture = e["id"]
                break
            prev = e["hash"]
            n += 1
        return {"ok": rupture is None, "n": n, "rupture": rupture, "dernier": prev, "verifie_le": o.maintenant()}

    # ------------------------------------------------------------------ les sondes de la péremption
    def manifeste_de(mid):
        for m in ctx.manifestes_actifs():
            if m.id == mid:
                return m
        return None

    def capacite_de(cle):
        mid, _, cid = str(cle).partition(".")
        m = manifeste_de(mid)
        return next((c for c in (m.capacites if m else ()) if c.id == cid), None)

    def sonde(nom, args):
        """(valeur, artefact, erreur). Une mesure REJOUABLE d'un vocabulaire FERMÉ, en lecture seule : jamais du texte libre — un souvenir qui porterait une commande rejouée par le système
        serait une porte d'exécution ouverte à quiconque sait écrire un souvenir. La VALEUR est le fait ; l'ARTEFACT est ce dont le mouvement déclenche la relecture."""
        a = [str(x).strip() for x in (args or [])]
        if nom not in o.SONDES:
            return None, "", "sonde inconnue : %s (les sondes sont %s)" % (nom, ", ".join(o.SONDES))
        if not a or not a[0]:
            return None, "", "cette sonde attend un nom en premier argument"
        if nom in ("capacite_existe", "capacite_absente"):
            if not re.match(r"^[a-z0-9_]+\.[a-z0-9_]+$", a[0]):
                return None, "", "une capacité s'écrit « module.capacité »"
            existe = capacite_de(a[0]) is not None
            return (existe if nom == "capacite_existe" else not existe), "capacite:" + a[0], ""
        if nom in ("module_actif", "module_version"):
            m = manifeste_de(a[0])
            if nom == "module_actif":
                return m is not None, "module:" + a[0], ""
            if len(a) < 2:
                return None, "module:" + a[0], "module_version attend la version attendue en second argument"
            if m is None:
                return None, "module:" + a[0], "le module %s n'est pas actif" % a[0]
            return m.version == a[1], "module:" + a[0], ""
        # objet_present / objet_etat : le registre des objets, tel que les modules l'ont posé
        if len(a) < 2:
            return None, "", "cette sonde attend un type puis un identifiant"
        artefact = "objet:%s/%s" % (a[0], a[1])
        obj = ctx.lire(a[0], a[1], portee=ctx.TOUT)
        if obj is None:
            return (False, artefact, "") if nom == "objet_present" else (None, artefact, "aucun objet %s « %s » au registre" % (a[0], a[1]))
        if nom == "objet_present":
            return True, artefact, ""
        if len(a) < 3:
            return None, artefact, "objet_etat attend l'état attendu en troisième argument"
        return str(obj.get("etat", "") if isinstance(obj, dict) else getattr(obj, "etat", "")) == a[2], artefact, ""

    def artefact_empreinte(artefact):
        """L'empreinte de l'ARTEFACT, jamais du fichier : un déclencheur grossier (un mouvement), le verdict est celui de la sonde."""
        if not artefact or ":" not in artefact:
            return ""
        sorte, nom = artefact.split(":", 1)
        if sorte == "capacite":
            c = capacite_de(nom)
            return hashlib.md5(("%s|%s|%s|%s|%s" % (c.id, c.libelle, c.risque, ",".join(c.paliers), ",".join(c.qui))).encode("utf-8", "replace")).hexdigest()[:12] if c else ""
        if sorte == "module":
            m = manifeste_de(nom)
            return hashlib.md5(("%s|%s" % (m.id, m.version)).encode()).hexdigest()[:12] if m else ""
        if sorte == "objet":
            t, _, i = nom.partition("/")
            obj = ctx.lire(t, i, portee=ctx.TOUT)
            if obj is None:
                return ""
            etat = obj.get("etat", "") if isinstance(obj, dict) else getattr(obj, "etat", "")
            return hashlib.md5(str(etat).encode("utf-8", "replace")).hexdigest()[:12]      # l'empreinte EST l'état : elle ne bouge qu'au changement
        return ""

    # ------------------------------------------------------------------ la porte
    def proche(cx, prop, cat, cle, val):
        """La clé active, même propriétaire et même catégorie, dont la valeur dit la même chose — ou None."""
        moi = o.jetons(cle.replace("-", " ") + " " + val)
        mes_n = o.nombres(cle.replace("-", " ") + " " + val)
        meilleur, cle_m = 0.0, None
        for r in cx.execute("SELECT cle, valeur FROM memoires WHERE proprietaire=? AND categorie=? AND statut='actif' AND cle<>? ORDER BY maj_le DESC LIMIT 500", (prop, cat, cle)).fetchall():
            texte = str(r["cle"]).replace("-", " ") + " " + str(r["valeur"])
            ses_n = o.nombres(texte)
            if mes_n and ses_n and mes_n != ses_n:
                continue                                           # des nombres différents des deux côtés : deux faits, pas deux versions
            s = o.proximite(moi, o.jetons(texte))
            if s > meilleur:
                meilleur, cle_m = s, r["cle"]
        return cle_m

    def domaine_etranger(compte, texte):
        """La garde propriétaire-sujet : un compte n'écrit pas sur un site qu'il ne touche pas."""
        v = lecture("sites.vue") if compte == compte_courant() else None
        siens = {str(s.get("domaine", "")).lower() for s in ((v or {}).get("sites") or []) if s.get("domaine")}
        if not siens:
            return None
        for d in set(o.RE_DOMAINE.findall((texte or "").lower())):
            if re.match(r"^\d+(\.\d+){3}$", d):
                continue
            if d not in siens and not any(d.endswith("." + s) for s in siens):
                return d
        return None

    def copies_retirer_cx(cx, source_id, raison, acteur):
        """L'original corrigé ou retiré : ses copies données passent en expiré, tracées."""
        now = o.maintenant()
        rows = cx.execute("SELECT id FROM memoires WHERE don_de=? AND statut IN ('actif','conteste','quarantaine')", (int(source_id),)).fetchall()
        for r in rows:
            cx.execute("UPDATE memoires SET statut='expire', valide_a=?, maj_le=? WHERE id=?", (now, now, r["id"]))
            journal_cx(cx, "don_retire", r["id"], {"raison": raison, "de": source_id}, acteur)
        return [r["id"] for r in rows]

    def est_critique(cat, force, prov):
        return False if prov in ("dit", "decision") else (cat in o.CRITIQUES or float(force or 0) >= 0.9)

    def ecrire_coeur(categorie, cle, valeur, proprietaire=None, provenance="infere", confiance=0.5, piece=None, declencheur="", acteur=None, force=None, valide_a=None,
                     nature=None, sonde_nom=None, sonde_args=None, interne=False):
        """LA porte d'écriture. Rend {ok, id, action (ecriture|remplace|conteste|quarantaine|inchange|refus), refus, ...} + `crees` / `avant` pour le retour."""
        acteur = acteur or acteur_courant()
        cat0 = str(categorie or "").strip().lower()
        cat = cat0 if cat0 in o.CATEGORIES else o.CATEGORIE_ALIAS.get(cat0, "")
        if not cat and cat0.startswith("itare_"):
            cat = "lecon"
        prov = str(provenance or "infere").strip().lower()
        prov = prov if prov in o.PROVENANCES else o.PROVENANCE_ALIAS.get(prov, "infere")
        val = o.desechapper(" ".join(str(valeur or "").split()).strip())        # les entités HTML d'un écrivain qui lisait un corps nettoyé : défaites ici, à la porte unique
        cle = o.desechapper(str(cle or ""))
        prop = str(proprietaire or proprietaire_defaut(cat))
        decl = str(declencheur or "")[:40]
        if proprietaire and not interne and proprietaire not in portee():         # `interne` : le don et l'échange distillé écrivent chez un autre propriétaire, jamais une capacité
            return {"ok": False, "id": None, "action": "refus", "refus": "proprietaire", "detail": "hors de ta portée", "crees": [], "avant": []}

        def refus(raison, detail=""):
            try:
                journal("refus_garde", None, {"raison": raison, "categorie": cat0[:40], "cle": str(cle)[:80], "proprietaire": prop, "declencheur": decl, "detail": str(detail)[:160]}, acteur)
            except Exception:
                pass
            return {"ok": False, "id": None, "action": "refus", "refus": raison, "detail": str(detail)[:160], "crees": [], "avant": []}

        if not cat:
            return refus("categorie", cat0)
        if not val:
            return refus("vide")
        nat = str(nature or "").strip().lower()
        if nat not in o.NATURES:
            return refus("nature", "dis si ce souvenir est « etat-courant » (il porte une sonde rejouable) ou « constat » (daté, jamais relu) — un souvenir muet sur sa nature serait rangé "
                                   "d'office, et personne ne saurait qu'on a choisi pour lui")
        art, art_emp, s_val = "", "", None
        if nat == "etat-courant":
            if not sonde_nom:
                return refus("nature", "« etat-courant » sans sonde : c'est la sonde qui rend le souvenir relisable ; sans elle, écris « constat »")
            s_val, art, err = sonde(sonde_nom, sonde_args)
            if err:
                return refus("sonde", err)               # une sonde qui ne répond pas À L'ÉCRITURE ne répondra pas mieux dans un mois : on refuse la promesse
            if s_val is not True:                        # la sonde EST le fait : un fait qu'on écrit est un fait vrai MAINTENANT
                return refus("sonde", "la sonde %s%s répond NON : ce fait n'est pas vrai maintenant" % (sonde_nom, tuple(sonde_args or ())))
            art_emp = artefact_empreinte(art)
        val = val[:o.VALEUR_MAX]
        if len(str(cle or "").split()) > 8 or len(str(cle or "")) > 120:
            return refus("cle", "phrase libre")
        k = o.cle_de(cle)
        if not k:
            return refus("cle", "vide")
        if o.a_un_secret(val) or o.a_un_secret(str(cle or "")):
            return refus("secret")
        if o.RE_CONSIGNE.search(val):
            return refus("consigne")
        if o.RE_SPI.search(val):
            return refus("spi")
        if len(re.sub(r"[\W_]+", "", val)) < 8 or o.RE_CREUX.search(val):       # une note creuse n'apprend rien à qui la relit
            return refus("creux", val[:80])
        if prop.startswith("compte:"):
            etranger = domaine_etranger(prop[7:], k + " " + val)
            if etranger:
                return refus("sujet", etranger)
        niveau, _direct, plafond = o.PROVENANCES[prov]
        try:
            conf = max(0.0, min(float(confiance), plafond))
        except (TypeError, ValueError):
            conf = min(0.5, plafond)
        now = o.maintenant()
        pour_veto = False
        try:
            with db.transaction() as cx:
                n_h = cx.execute("SELECT COUNT(*) FROM journal WHERE verbe IN ('ecriture','remplace','conteste') AND ts >= datetime('now','-1 hour')").fetchone()[0]
                if n_h >= o.QUOTA_GLOBAL_HEURE:
                    raise Refus("quota", "global %d/h" % n_h)
                if prop.startswith("compte:"):
                    n_j = cx.execute("SELECT COUNT(*) FROM journal j JOIN memoires m ON m.id=j.memoire_id WHERE j.verbe IN ('ecriture','remplace','conteste') AND m.proprietaire=? "
                                     "AND j.ts >= datetime('now','-1 day')", (prop,)).fetchone()[0]
                    if n_j >= o.QUOTA_COMPTE_JOUR:
                        raise Refus("quota", "compte %d/j" % n_j)
                if decl and decl not in ("manuel", "outil_remember"):
                    n_d = cx.execute("SELECT COUNT(*) FROM journal WHERE verbe IN ('ecriture','remplace','conteste') AND ts >= datetime('now','-1 hour') AND details LIKE ?",
                                     ('%"declencheur": "' + decl + '"%',)).fetchone()[0]
                    if n_d >= o.QUOTA_DECLENCHEUR_HEURE:
                        raise Refus("quota", "déclencheur %s %d/h" % (decl, n_d))
                actif = cx.execute("SELECT * FROM memoires WHERE proprietaire=? AND cle=? AND statut='actif'", (prop, k)).fetchone()
                rapproche = None
                if not actif:
                    k_proche = proche(cx, prop, cat, k, val)
                    if k_proche:
                        rapproche, k = k, k_proche
                        actif = cx.execute("SELECT * FROM memoires WHERE proprietaire=? AND cle=? AND statut='actif'", (prop, k)).fetchone()
                if actif and piece and piece.get("date") and str(piece["date"]) < str(actif["cree_le"]):
                    raise Refus("piece_ancienne", "pièce %s antérieure à la version active %s" % (piece["date"], actif["cree_le"]))
                if actif and actif["valeur"] == val:
                    return {"ok": True, "id": actif["id"], "action": "inchange", "refus": None, "crees": [], "avant": []}
                action, remplace, version, statut = "ecriture", None, 1, "actif"
                f = float(force) if force is not None else 0.0
                avant = []
                if actif:
                    n_old = o.PROVENANCES.get(actif["provenance"], (2, 0, 0.8))[0]
                    if force is None:
                        f = float(actif["force"] or 0)
                    if actif["categorie"] in o.CATEGORIES_STABLES and cat not in o.CATEGORIES_STABLES and niveau <= n_old:
                        action, statut = "conteste", "conteste"          # un état passager n'écrase pas une catégorie stable
                    elif niveau < n_old:
                        action, statut = "conteste", "conteste"          # plus faible que l'actif : mis en doute, jamais servi en tête
                    else:
                        action, remplace, version = "remplace", actif["id"], int(actif["version"] or 1) + 1
                # Le veto : une écriture critique qui ne vient pas de l'humain attend en quarantaine ; l'active reste active jusqu'à la levée (hors du chemin de la réponse).
                if statut == "actif" and est_critique(cat, f, prov) and bool(ctx.reglage("veto_actif")):
                    action, statut, remplace, pour_veto = "quarantaine", "quarantaine", None, True
                elif action == "remplace":
                    avant.append(dict(actif))
                    cx.execute("UPDATE memoires SET statut='expire', valide_a=?, maj_le=? WHERE id=?", (now, now, actif["id"]))
                    copies_retirer_cx(cx, actif["id"], "original corrigé", acteur)
                piece_id = None
                if piece:
                    contenu = str(piece.get("contenu") or "")[:2000]
                    piece_id = cx.execute("INSERT INTO pieces(type, proprietaire, source, contenu, empreinte, date_piece, cree_le) VALUES (?,?,?,?,?,?,?)",
                                          (str(piece.get("type") or "message")[:24], prop, piece.get("source"), contenu,
                                           piece.get("empreinte") or hashlib.sha256(contenu.encode("utf-8", "replace")).hexdigest()[:24], piece.get("date") or now, now)).lastrowid
                mid = cx.execute(
                    "INSERT INTO memoires(proprietaire, categorie, cle, valeur, provenance, confiance, force, statut, langue, piece_id, valide_de, valide_a, remplace, version, cree_le, maj_le, "
                    "nature, sonde, sonde_args, sonde_valeur, artefact, artefact_empreinte) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (prop, cat, k, val, prov, round(conf, 3), f, statut, o.langue(val), piece_id, now, valide_a, remplace, version, now, now, nat, sonde_nom or None,
                     json.dumps(list(sonde_args or []), ensure_ascii=False) if sonde_nom else None, json.dumps(s_val) if nat == "etat-courant" else None, art or None, art_emp or None)).lastrowid
                journal_cx(cx, action, mid, {"cle": k, "proprietaire": prop, "provenance": prov, "confiance": round(conf, 3), "declencheur": decl, "remplace": remplace, "piece": piece_id,
                                              **({"rapproche_de": rapproche} if rapproche else {})}, acteur)
                if action == "conteste" and actif:           # le doute est un objet : la contradiction ne dort pas dans un statut, elle se pose
                    douter_cx(cx, "reconciliation", o.question_de("reconciliation", val, ancienne=actif["valeur"]), prop, memoire_id=mid, memoire_id_2=actif["id"], acteur=acteur)
                res = {"ok": True, "id": mid, "action": action, "refus": None, "remplace": remplace, "conteste": statut == "conteste", "quarantaine": statut == "quarantaine",
                       "cle": k, "rapproche_de": rapproche, "crees": [mid], "avant": avant, "proprietaire": prop}
        except Refus as r:
            return refus(r.raison, r.detail)
        if decl == "outil_remember":
            tour_noter_ecrit(res["id"])
        if res["action"] in ("ecriture", "remplace"):
            ctx.emettre("souvenir.ecrit", objet=("souvenir", str(res["id"])), donnees={"id": res["id"], "categorie": cat, "cle": k, "action": res["action"]}, compte=prop[7:] if prop.startswith("compte:") else None)
        return res

    # ------------------------------------------------------------------ lire une fiche, dans la portée
    def visible(mid, pt=None):
        pt = pt or portee()
        try:
            r = db.lire("SELECT * FROM memoires WHERE id=? AND proprietaire IN (%s)" % ",".join("?" * len(pt)), [int(mid)] + list(pt))
        except (TypeError, ValueError):
            return None
        return r[0] if r else None

    def exiger(mid):
        m = visible(mid)
        if m is None:
            raise ValueError("souvenir introuvable")
        return m

    def avec_ref(r):
        d = dict(r)
        d["ref"] = "M:%d" % d["id"]
        return d

    def expirer_cx(cx, m, raison, acteur, verbe="expire"):
        now = o.maintenant()
        cx.execute("UPDATE memoires SET statut='expire', valide_a=?, maj_le=? WHERE id=?", (now, now, m["id"]))
        journal_cx(cx, verbe, m["id"], {"raison": str(raison or "")[:200], "cle": m["cle"]}, acteur)

    def annuler(res):
        """Le retour générique : les souvenirs créés par l'acte expirent (jamais de DELETE : la pierre reste au journal), puis les lignes touchées reprennent leur état d'avant."""
        with db.transaction() as cx:
            for mid in res.get("crees") or []:
                r = cx.execute("SELECT * FROM memoires WHERE id=?", (mid,)).fetchone()
                if r and r["statut"] != "expire":
                    expirer_cx(cx, r, "acte annulé", "retour", "annule")
            for a in res.get("avant") or []:
                cx.execute("UPDATE memoires SET statut=?, valide_a=?, maj_le=?, force=?, confiance=?, remplace=?, version=? WHERE id=?",
                           tuple(a[k] for k in RESTAURE) + (a["id"],))
                journal_cx(cx, "annule", a["id"], {"cle": a["cle"], "remis": a["statut"]}, "retour")
            d = res.get("doute")
            if d:
                cx.execute("UPDATE doutes SET statut=?, resolution=?, resolu_le=?, resolu_par=?, differe=?, echeance=?, dernier_pose=? WHERE id=?",
                           (d["statut"], d["resolution"], d["resolu_le"], d["resolu_par"], d["differe"], d["echeance"], d["dernier_pose"], d["id"]))

    def defaire_annuler(c, res):
        annuler(res)

    def prouver_ecrit(c, res):
        if not res.get("ok") or res.get("action") in ("inchange", "refus"):
            return True                                        # un refus est un résultat : il n'y a rien à prouver
        r = db.lire("SELECT statut FROM memoires WHERE id=?", (res["id"],))
        return bool(r) and r[0]["statut"] in ("actif", "conteste", "quarantaine", "expire")

    def defaire_ecrit(c, res):
        if res.get("ok") and res.get("action") not in ("inchange", "refus"):
            annuler(res)

    def ecrire(c, categorie="", cle="", valeur="", provenance="infere", confiance=0.5, piece=None, declencheur="", force=None, valide_a=None, nature=None, sonde=None, sonde_args=None, proprietaire=None):
        if piece is not None and not isinstance(piece, dict):
            piece = {"contenu": str(piece)}
        return ecrire_coeur(categorie, cle, valeur, proprietaire or None, provenance, confiance, piece, declencheur, None, force, valide_a, nature, sonde, sonde_args)

    # ------------------------------------------------------------------ corriger, oublier, restaurer, forcer
    def corriger(c, id=0, valeur="", provenance="dit", confiance=0.9):
        m = exiger(id)
        # Corriger ne change pas la nature : on la transporte (sinon un « etat-courant » corrigé perdrait sa sonde).
        r = ecrire_coeur(m["categorie"], m["cle"], valeur, m["proprietaire"], provenance, confiance, None, "correction", None, m["force"], None,
                         m["nature"] or "constat", m["sonde"], json.loads(m["sonde_args"]) if m["sonde_args"] else None)
        if r.get("ok") and r.get("action") in ("ecriture", "remplace"):
            journal("correction", r["id"], {"depuis": m["id"], "cle": m["cle"]})
        return r

    def oublier(c, id=0, raison="oubli sur ordre de l'utilisateur"):
        m = exiger(id)
        if m["statut"] == "expire":
            return {"id": m["id"], "deja": True, "avant": []}
        with db.transaction() as cx:
            expirer_cx(cx, m, raison, acteur_courant(), "oubli")
        return {"id": m["id"], "avant": [m], "crees": []}

    def prouver_oublie(c, res):
        return res.get("deja") or db.lire("SELECT statut FROM memoires WHERE id=?", (res["id"],))[0]["statut"] == "expire"

    def defaire_oublie(c, res):
        if not res.get("deja"):
            annuler(res)

    def restaurer(c, id=0):
        m = exiger(id)
        if m["statut"] == "actif":
            return {"id": m["id"], "deja": True, "avant": []}
        occupe = db.lire("SELECT id FROM memoires WHERE proprietaire=? AND cle=? AND statut='actif'", (m["proprietaire"], m["cle"]))
        if occupe:
            raise ValueError("une version plus récente occupe cette clé [M:%d]" % occupe[0]["id"])
        with db.transaction() as cx:
            cx.execute("UPDATE memoires SET statut='actif', valide_a=NULL, maj_le=? WHERE id=?", (o.maintenant(), m["id"]))
            journal_cx(cx, "restaure", m["id"], {"cle": m["cle"]}, acteur_courant())
        return {"id": m["id"], "avant": [m], "crees": []}

    def prouver_restaure(c, res):
        return res.get("deja") or db.lire("SELECT statut FROM memoires WHERE id=?", (res["id"],))[0]["statut"] == "actif"

    def forcer(c, id=0, force=0.0):
        m = exiger(id)
        try:
            f = max(0.0, min(1.0, float(force)))
        except (TypeError, ValueError):
            raise ValueError("force entre 0 et 1")
        with db.transaction() as cx:
            cx.execute("UPDATE memoires SET force=?, maj_le=? WHERE id=?", (f, o.maintenant(), m["id"]))
            journal_cx(cx, "force", m["id"], {"force": f, "cle": m["cle"]}, acteur_courant())
        return {"id": m["id"], "force": f, "avant": [m], "crees": []}

    def prouver_force(c, res):
        return abs(float(db.lire("SELECT force FROM memoires WHERE id=?", (res["id"],))[0]["force"]) - res["force"]) < 1e-9

    # ------------------------------------------------------------------ don, prêt
    def donner(c, id=0, destinataire="", type_don="don", jours=None):
        dest = str(destinataire or "").strip()
        if dest and dest != "partage" and not dest.startswith("compte:"):
            dest = "compte:" + dest
        if not dest:
            raise ValueError("destinataire requis")
        if dest.startswith("compte:") and not ctx.est_admin(compte_courant()):
            raise ValueError("un compte ne donne qu'au partagé")
        m = visible(id)
        if m is None or m["statut"] != "actif":
            raise ValueError("souvenir introuvable ou inactif")
        if m["proprietaire"] == dest:
            raise ValueError("déjà chez ce propriétaire")
        valide_a = None
        if type_don == "pret":
            j = max(1, min(int(jours or o.PRET_JOURS), o.PRET_JOURS_MAX))
            valide_a = (datetime.now(timezone.utc) + timedelta(days=j)).strftime("%Y-%m-%d %H:%M:%S")
        # Donner ne change pas la nature non plus : la copie vaut ce que valait l'original. Elle traverse les gardes comme tout souvenir.
        r = ecrire_coeur(m["categorie"], m["cle"], m["valeur"], dest, m["provenance"], m["confiance"], None, "don", None, None, valide_a,
                         m["nature"] or "constat", m["sonde"], json.loads(m["sonde_args"]) if m["sonde_args"] else None, interne=True)
        if not r.get("ok"):
            raise ValueError("refusé par la porte : %s" % r.get("refus"))
        if r.get("action") == "inchange":
            return {"id": r["id"], "deja": True, "crees": [], "avant": []}
        with db.transaction() as cx:
            cx.execute("UPDATE memoires SET don_de=? WHERE id=?", (m["id"], r["id"]))
            journal_cx(cx, "don", m["id"], {"vers": dest, "copie": r["id"], "type": type_don, "echeance": valide_a}, acteur_courant())
            journal_cx(cx, "don_recu", r["id"], {"de": m["id"], "donateur": m["proprietaire"], "type": type_don, "echeance": valide_a}, acteur_courant())
        return {"id": r["id"], "action": r.get("action"), "echeance": valide_a, "quarantaine": r.get("quarantaine", False), "crees": [r["id"]], "avant": r.get("avant", [])}

    def prouver_don(c, res):
        return res.get("deja") or bool(db.lire("SELECT 1 FROM memoires WHERE id=? AND don_de IS NOT NULL", (res["id"],)))

    def don_retirer(c, copie_id=0):
        pt = portee()
        r = db.lire("SELECT * FROM memoires WHERE id=?", (int(copie_id or 0),))
        if not r or not r[0]["don_de"] or visible(r[0]["don_de"], pt) is None:
            raise ValueError("copie introuvable")
        cp = r[0]
        if cp["statut"] == "expire":
            return {"id": cp["id"], "deja": True, "avant": [], "crees": []}
        with db.transaction() as cx:
            now = o.maintenant()
            cx.execute("UPDATE memoires SET statut='expire', valide_a=?, maj_le=? WHERE id=?", (now, now, cp["id"]))
            journal_cx(cx, "don_retire", cp["id"], {"raison": "don retiré", "de": cp["don_de"]}, acteur_courant())
        return {"id": cp["id"], "avant": [cp], "crees": []}

    def prouver_don_retire(c, res):
        return res.get("deja") or db.lire("SELECT statut FROM memoires WHERE id=?", (res["id"],))[0]["statut"] == "expire"

    def purger_secret(c, id=0):
        """Un secret entré par erreur : expiré tout de suite ET sa valeur retirée de la ligne, de la pièce et de l'index — la seule réécriture en place que la mémoire admet, parce qu'une
        trace de contenu serait ici la faute. Le geste, lui, reste au journal."""
        m = exiger(id)
        with db.transaction() as cx:
            now = o.maintenant()
            cx.execute("UPDATE memoires SET statut='expire', valide_a=?, maj_le=? WHERE id=?", (now, now, m["id"]))
            cx.execute("UPDATE memoires SET valeur='[valeur retirée : secret]' WHERE id=?", (m["id"],))
            if m["piece_id"]:
                cx.execute("UPDATE pieces SET contenu='[retiré : secret]' WHERE id=?", (m["piece_id"],))
            journal_cx(cx, "purge_secret", m["id"], {"cle": m["cle"], "raison": "secret entré par erreur"}, acteur_courant())
        return {"id": m["id"]}

    def prouver_purge(c, res):
        return db.lire("SELECT valeur FROM memoires WHERE id=?", (res["id"],))[0]["valeur"] == "[valeur retirée : secret]"

    def defaire_purge(c, res):
        """Aucun retour, voulu : la valeur d'un secret ne revient pas."""
        return None

    # ------------------------------------------------------------------ doutes
    def douter_cx(cx, source, question, proprietaire, memoire_id=None, memoire_id_2=None, options=None, priorite=1, acteur=None):
        """Ouvre un doute (ou rend celui déjà ouvert sur le même souvenir et la même source). Échéance à sept jours : le silence ne vaut ni oui ni non, le doute expire sans effet."""
        if source not in o.DOUTE_SOURCES:
            return None
        if memoire_id is not None:
            deja = cx.execute("SELECT id FROM doutes WHERE statut='ouvert' AND source=? AND memoire_id=?", (source, int(memoire_id))).fetchone()
            if deja:
                return deja["id"]
        opts = options or o.OPTIONS_DOUTE.get(source) or o.OPTIONS_DOUTE["agent"]
        ech = (datetime.now(timezone.utc) + timedelta(days=o.DOUTE_ECHEANCE_J)).strftime("%Y-%m-%d %H:%M:%S")
        did = cx.execute("INSERT INTO doutes(ts, proprietaire, source, question, options, priorite, memoire_id, memoire_id_2, echeance) VALUES (?,?,?,?,?,?,?,?,?)",
                         (o.maintenant(), proprietaire, source, str(question)[:800], json.dumps(opts, ensure_ascii=False), int(priorite), memoire_id, memoire_id_2, ech)).lastrowid
        journal_cx(cx, "doute", memoire_id, {"doute": did, "source": source, "question": str(question)[:120]}, acteur or acteur_courant())
        return did

    def doutes_expirer():
        """Les doutes échus expirent, tracés, sans effet sur la mémoire."""
        now = o.maintenant()
        rows = db.lire("SELECT id, memoire_id FROM doutes WHERE statut='ouvert' AND echeance < ?", (now,))
        if rows:
            with db.transaction() as cx:
                for r in rows:
                    cx.execute("UPDATE doutes SET statut='expire', resolu_le=? WHERE id=?", (now, r["id"]))
                    journal_cx(cx, "doute_expire", r["memoire_id"], {"doute": r["id"]}, "systeme")
        return len(rows)

    def doute_dict(r):
        d = dict(r)
        try:
            d["options"] = json.loads(d.get("options") or "[]")
        except ValueError:
            d["options"] = []
        return d

    def doutes(c, statut="ouvert", limite=50):
        pt = portee()
        doutes_expirer()
        sql = "SELECT * FROM doutes WHERE proprietaire IN (%s)" % ",".join("?" * len(pt))
        args = list(pt)
        if statut and statut != "tous":
            sql += " AND statut=?"
            args.append(statut)
        return {"doutes": [doute_dict(r) for r in db.lire(sql + " ORDER BY priorite DESC, id ASC LIMIT ?", args + [int(limite)])]}

    def doutes_a_poser(pt, n=o.DOUTES_PAR_TOUR):
        """Au plus deux, jamais deux fois le même jour, jamais plus de trois fois ; le fait de les poser se note."""
        doutes_expirer()
        with db.transaction() as cx:
            rows = cx.execute("SELECT * FROM doutes WHERE statut='ouvert' AND proprietaire IN (%s) AND nb_poses < 3 AND (dernier_pose IS NULL OR dernier_pose < datetime('now','-1 day')) "
                              "ORDER BY priorite DESC, id ASC LIMIT ?" % ",".join("?" * len(pt)), list(pt) + [int(n)]).fetchall()
            now = o.maintenant()
            for r in rows:
                cx.execute("UPDATE doutes SET dernier_pose=?, nb_poses=nb_poses+1 WHERE id=?", (now, r["id"]))
            return [doute_dict(r) for r in rows]

    def doute_bloc(pt):
        d = doutes_a_poser(pt)
        if not d:
            return ""
        lignes = ["— doutes à poser à l'utilisateur (au plus deux, une phrase chacun, À LA FIN de ta réponse, avec leurs choix ; il répond « doute N : choix ») —"]
        for x in d:
            lignes.append("[D:%d] %s · choix : %s" % (x["id"], x["question"], " / ".join("%s (%s)" % (a[0], a[1]) for a in x["options"])))
        return "\n".join(lignes)

    def resoudre_coeur(did, choix, note=""):
        pt = portee()
        acteur = acteur_courant()
        choix = ALIAS_CHOIX_LOCAL.get(str(choix or "").strip().lower(), str(choix or "").strip().lower())
        d = db.lire("SELECT * FROM doutes WHERE id=? AND proprietaire IN (%s)" % ",".join("?" * len(pt)), [int(did)] + list(pt))
        if not d:
            raise ValueError("doute introuvable")
        d = d[0]
        if d["statut"] != "ouvert":
            raise ValueError("doute déjà %s" % d["statut"])
        now = o.maintenant()
        avant_doute = {k: d[k] for k in ("id", "statut", "resolution", "resolu_le", "resolu_par", "differe", "echeance", "dernier_pose")}
        if choix == "plus_tard":
            if d["differe"]:
                raise ValueError("déjà différé une fois : il faut répondre, ou annuler")
            with db.transaction() as cx:
                cx.execute("UPDATE doutes SET differe=1, echeance=?, dernier_pose=? WHERE id=?", ((datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"), now, d["id"]))
                journal_cx(cx, "doute_differe", d["memoire_id"], {"doute": d["id"]}, acteur)
            return {"id": d["id"], "statut": "ouvert", "differe": True, "doute": avant_doute, "avant": [], "crees": []}
        opts = {x[0] for x in (json.loads(d["options"] or "[]") or [])}
        if choix in ("oui", "non"):                                # la réponse naturelle, traduite selon la question posée
            choix = "faux" if choix == "non" else ("ecrire" if "ecrire" in opts else ("vrai" if "vrai" in opts else choix))
        if choix != "annule" and choix not in opts:
            raise ValueError("choix inconnu : %s (attendus : %s)" % (choix, ", ".join(sorted(opts))))
        m1 = db.lire("SELECT * FROM memoires WHERE id=?", (d["memoire_id"],)) if d["memoire_id"] else []
        m2 = db.lire("SELECT * FROM memoires WHERE id=?", (d["memoire_id_2"],)) if d["memoire_id_2"] else []
        m1, m2 = (m1[0] if m1 else None), (m2[0] if m2 else None)
        avant = [x for x in (m1, m2) if x]
        with db.transaction() as cx:
            if choix in ("faux", "perime"):
                for m in (m1, m2) if choix == "faux" else (m1,):
                    if m and m["statut"] != "expire":
                        cx.execute("UPDATE memoires SET statut='expire', valide_a=?, maj_le=? WHERE id=?", (now, now, m["id"]))
                        journal_cx(cx, "expire", m["id"], {"raison": "arbitrage : %s" % choix, "doute": d["id"], "note": note[:200]}, acteur)
            elif choix == "active":
                if m1 and m1["statut"] != "expire":
                    cx.execute("UPDATE memoires SET statut='expire', valide_a=?, maj_le=? WHERE id=?", (now, now, m1["id"]))
                    journal_cx(cx, "expire", m1["id"], {"raison": "arbitrage : version active confirmée", "doute": d["id"]}, acteur)
                if m2:
                    journal_cx(cx, "revalide", m2["id"], {"doute": d["id"], "note": note[:200]}, acteur)
            elif choix == "vrai" and m1:
                # « Toujours vrai » rafraîchit la date et la confiance : sans cela la même question revenait au rappel suivant, puisque rien n'avait changé dans ce qui l'avait fait poser.
                cx.execute("UPDATE memoires SET maj_le=?, confiance=MAX(COALESCE(confiance,0), 0.6) WHERE id=?", (now, m1["id"]))
                journal_cx(cx, "revalide", m1["id"], {"doute": d["id"], "note": note[:200]}, acteur)
            cx.execute("UPDATE doutes SET statut=?, resolution=?, resolu_le=?, resolu_par=? WHERE id=?",
                       ("annule" if choix == "annule" else "resolu", choix + (" · " + note[:200] if note else ""), now, acteur, d["id"]))
            journal_cx(cx, "doute_resolu", d["memoire_id"], {"doute": d["id"], "choix": choix}, acteur)
        crees, effet = [], choix
        # Les écritures passent par la porte, hors transaction du doute : l'arbitrage humain est une décision.
        if choix == "nouvelle" and m1:
            r = ecrire_coeur(m1["categorie"], m1["cle"], m1["valeur"], m1["proprietaire"], "decision", 1.0, None, "arbitrage", acteur, m1["force"], None,
                             m1["nature"] or "constat", m1["sonde"], json.loads(m1["sonde_args"]) if m1["sonde_args"] else None)
            crees += r.get("crees", [])
            avant += r.get("avant", [])
            effet = r
            if r.get("ok") and r.get("id") != m1["id"]:
                with db.transaction() as cx:
                    cur = cx.execute("SELECT * FROM memoires WHERE id=?", (m1["id"],)).fetchone()
                    if cur and cur["statut"] != "expire":
                        expirer_cx(cx, cur, "arbitrage : reprise en version %s" % r.get("id"), acteur)
        elif choix == "ecrire" and m1:
            effet = lever_coeur(m1["id"], "arbitrage de l'utilisateur")
            avant += effet.get("avant", [])
        return {"id": d["id"], "statut": "annule" if choix == "annule" else "resolu", "effet": effet, "doute": avant_doute, "avant": avant, "crees": crees}

    ALIAS_CHOIX_LOCAL = o.ALIAS_CHOIX

    def douter_resoudre(c, id=0, choix="", note=""):
        return resoudre_coeur(id, choix, note)

    def prouver_resolu(c, res):
        return res.get("differe") or db.lire("SELECT statut FROM doutes WHERE id=?", (res["id"],))[0]["statut"] in ("resolu", "annule")

    def doutes_depuis_reponse(c, texte=""):
        out = []
        for m in o.RE_DOUTE_REPONSE.finditer(texte or ""):
            try:
                out.append(resoudre_coeur(int(m.group(1)), m.group(2)))
            except ValueError as e:
                out.append({"id": int(m.group(1)), "erreur": str(e)[:120], "avant": [], "crees": []})
        return {"resolus": out, "avant": [], "crees": []}

    def prouver_depuis_reponse(c, res):
        return all(("erreur" in r) or r.get("differe") or db.lire("SELECT statut FROM doutes WHERE id=?", (r["id"],))[0]["statut"] in ("resolu", "annule") for r in res["resolus"])

    def defaire_depuis_reponse(c, res):
        for r in reversed(res["resolus"]):
            if "erreur" not in r:
                annuler(r)

    # ------------------------------------------------------------------ le veto
    def lever_coeur(mid, note="", acteur=None):
        """La quarantaine (ou le contesté) devient la version active : l'active précédente expire avec remplace."""
        acteur = acteur or acteur_courant()
        with db.transaction() as cx:
            m = cx.execute("SELECT * FROM memoires WHERE id=? AND statut IN ('quarantaine','conteste')", (int(mid),)).fetchone()
            if not m:
                raise ValueError("rien à lever sous cet id")
            now = o.maintenant()
            actif = cx.execute("SELECT * FROM memoires WHERE proprietaire=? AND cle=? AND statut='actif'", (m["proprietaire"], m["cle"])).fetchone()
            remplace, version, avant = None, 1, [dict(m)]
            if actif:
                remplace, version = actif["id"], int(actif["version"] or 1) + 1
                avant.append(dict(actif))
                cx.execute("UPDATE memoires SET statut='expire', valide_a=?, maj_le=? WHERE id=?", (now, now, actif["id"]))
                copies_retirer_cx(cx, actif["id"], "original corrigé", acteur)
            cx.execute("UPDATE memoires SET statut='actif', remplace=?, version=?, valide_de=?, maj_le=? WHERE id=?", (remplace, version, now, now, m["id"]))
            journal_cx(cx, "veto_leve", m["id"], {"note": note[:200], "remplace": remplace}, acteur)
        return {"id": m["id"], "remplace": remplace, "version": version, "avant": avant, "crees": []}

    def veto_lever(c, id=0, note=""):
        exiger(id)
        return lever_coeur(id, note)

    def prouver_leve(c, res):
        return db.lire("SELECT statut FROM memoires WHERE id=?", (res["id"],))[0]["statut"] == "actif"

    def examiner_veto(mid):
        """Les gardes mécaniques d'abord (SIGNAL, pas juge), le relecteur ensuite s'il est lié ; sans lui, mécaniques seules. Levée ou refus, tout au journal."""
        r = db.lire("SELECT * FROM memoires WHERE id=? AND statut='quarantaine'", (int(mid),))
        if not r:
            return {"ok": False, "erreur": "rien en quarantaine sous cet id"}
        m = r[0]
        piece = db.lire("SELECT * FROM pieces WHERE id=?", (m["piece_id"],)) if m["piece_id"] else []
        actif = db.lire("SELECT valeur, provenance, confiance FROM memoires WHERE proprietaire=? AND cle=? AND statut='actif'", (m["proprietaire"], m["cle"]))
        contenu = str(piece[0]["contenu"] or "") if piece else ""
        signal = ""
        if len(contenu) >= 40:
            t = o.jetons(m["valeur"])
            if t and not (t & o.jetons(contenu)):
                signal = "aucun terme du fait n'est dans la pièce"
        verdict, sans_verdict, raison = None, None, ""
        brut = completer("second_avis", [{"role": "user", "content": o.PROMPT_VETO.format(
            categorie=m["categorie"], provenance=m["provenance"], confiance=m["confiance"], cle=m["cle"], valeur=str(m["valeur"])[:600],
            piece=(contenu[:1500] or "aucune") + ("\n(Signal du garde mécanique : %s. Ce n'est qu'un indice — juge sur le fond.)" % signal if signal else ""),
            active=("« %s » (%s, conf %s)" % (str(actif[0]["valeur"])[:300], actif[0]["provenance"], actif[0]["confiance"])) if actif else "aucune")}],
            "Tu réponds en JSON strict, une ligne.", 300, allow_reasoning=False, timeout=60)
        if brut is not None:
            obj = o.json_extraire(brut, ctx.point) or {}
            if isinstance(obj, dict) and "ok" in obj:
                verdict = bool(obj.get("ok"))
                if not verdict:
                    raison = "veto d'Itare : %s" % str(obj.get("raison") or "sans raison")[:200]
            else:
                sans_verdict = (brut or "")[:200]       # un relecteur qui répond sans verdict lisible ne vaut pas un relecteur absent : le brut est au journal
        if verdict is None and signal:
            raison = signal
        if raison:
            with db.transaction() as cx:
                cx.execute("UPDATE memoires SET statut='conteste', maj_le=? WHERE id=? AND statut='quarantaine'", (o.maintenant(), m["id"]))
                journal_cx(cx, "veto", m["id"], {"raison": raison, "cle": m["cle"]}, "itare" if verdict is False else "garde")
                douter_cx(cx, "veto", o.question_de("veto", m["valeur"], raison=raison), m["proprietaire"], memoire_id=m["id"], acteur="itare" if verdict is False else "garde")
            return {"ok": False, "id": m["id"], "raison": raison}
        note = "levé" + (" par Itare" if verdict else (" par les gardes mécaniques, Itare sans verdict lisible : " + sans_verdict) if sans_verdict else " par les gardes mécaniques (relecteur non lié)")
        lever_coeur(m["id"], note, "itare" if verdict else "garde")
        return {"ok": True, "id": m["id"]}

    def completer(role, messages, systeme, max_tokens, allow_reasoning=True, timeout=75.0, temperature=None):
        """Le texte d'un modèle lié au rôle, ou None si le rôle n'est pas lié ou le modèle ne répond pas (le repli est l'affaire de l'appelant)."""
        r = lecture("modeles.completer", messages=messages, systeme=systeme, max_tokens=max_tokens, role=role, allow_reasoning=allow_reasoning, timeout=timeout, temperature=temperature)
        return r["texte"] if isinstance(r, dict) and r.get("ok") and r.get("texte") else None

    # ------------------------------------------------------------------ le tour, la distillation
    def tour_courant(compte=None):
        r = db.lire("SELECT * FROM tours WHERE compte=?", (compte_courant() if compte is None else compte,))
        return r[0] if r else {}

    def tour_noter_ecrit(mid):
        c = compte_courant()
        t = tour_courant(c)
        if t:
            db.ecrire("UPDATE tours SET ecrits=? WHERE compte=?", (json.dumps(json.loads(t["ecrits"] or "[]") + [mid]), c))

    def tour_commencer(c, question=""):
        compte = compte_courant()
        avant = tour_courant(compte)
        db.ecrire("INSERT OR REPLACE INTO tours(compte, question, debut, ecrits, cites) VALUES (?,?,?,?,?)", (compte, str(question or "")[:300], o.maintenant(), "[]", "[]"))
        return {"compte": compte, "avant": dict(avant) if avant else None}

    def prouver_tour(c, res):
        return bool(db.lire("SELECT 1 FROM tours WHERE compte=?", (res["compte"],)))

    def defaire_tour(c, res):
        if res["avant"]:
            a = res["avant"]
            db.ecrire("INSERT OR REPLACE INTO tours(compte, question, debut, ecrits, cites) VALUES (?,?,?,?,?)", (a["compte"], a["question"], a["debut"], a["ecrits"], a["cites"]))
        else:
            db.ecrire("DELETE FROM tours WHERE compte=?", (res["compte"],))

    def apres_echange(c, session_id="", question="", reponse="", actes=0, commandes=""):
        """La fin d'un échange : l'épisode s'allonge, les messages sont gardés, et une distillation est mise en file SEULEMENT si un déclencheur a eu lieu. Les doutes se résolvent à part
        (`doutes_depuis_reponse`) : chacun a son retour."""
        compte = compte_courant()
        prop = ("compte:" + compte) if not est_systeme(compte) else proprietaire_defaut("fact")
        ep = episode_toucher(session_id, prop)
        mids = []
        with db.transaction() as cx:
            for role, texte in (("user", question), ("assistant", reponse)):
                if str(texte or "").strip():
                    mids.append(cx.execute("INSERT INTO messages(episode_id, role, contenu, ts) VALUES (?,?,?,?)", (ep["id"], role, str(texte)[:4000], o.maintenant())).lastrowid)
        decl = o.declencheur_de(question, int(actes or 0))
        if decl in ("reponse_utilisateur", "correction") and json.loads(tour_courant(compte).get("ecrits") or "[]"):
            decl = None                # un seul chemin : si l'outil « retenir » a déjà écrit dans ce tour, la distillation ne repasse pas derrière lui
        fid = None
        if decl:
            morceaux = [str(question or "")[:600]]
            if commandes:
                morceaux.append(("— commandes du tour : " + str(commandes))[:900])
            if reponse:
                morceaux.append("— réponse : " + str(reponse)[:500])
            fid = db.ecrire("INSERT INTO file(compte, acteur, declencheur, question, reponse, piece, ts) VALUES (?,?,?,?,?,?,?)",
                            (compte, acteur_courant(), decl, str(question or "")[:1500], str(reponse or "")[:3000], "\n".join(morceaux), o.maintenant()))
        return {"episode": ep["id"], "declencheur": decl, "file": fid, "messages": mids}

    def prouver_apres(c, res):
        return bool(db.lire("SELECT 1 FROM episodes WHERE id=?", (res["episode"],)))

    def defaire_apres(c, res):
        for m in res["messages"]:
            db.ecrire("DELETE FROM messages WHERE id=?", (m,))
        if res["file"]:
            db.ecrire("DELETE FROM file WHERE id=? AND etat='attente'", (res["file"],))

    def deja_su(texte, pt, n=8):
        """Les fiches actives proches de l'échange : le distillateur ne voyait rien de la mémoire, et inventait une clé neuve pour un fait connu."""
        ts = o.termes(texte, 10)
        if not ts:
            return "(rien)"
        try:
            rows = db.lire("SELECT m.categorie, m.cle, m.valeur FROM memoires_fts JOIN memoires m ON m.id = memoires_fts.rowid WHERE memoires_fts MATCH ? AND m.proprietaire IN (%s) "
                           "AND m.statut='actif' ORDER BY bm25(memoires_fts) LIMIT ?" % ",".join("?" * len(pt)), [o.requete_fts(ts)] + list(pt) + [int(n)])
        except Exception:
            return "(rien)"
        return "\n".join("- [%s] %s : %s" % (r["categorie"], r["cle"], str(r["valeur"])[:160]) for r in rows) or "(rien)"

    def distiller_une(f):
        """Un candidat par le modèle, puis LA porte : chaque souvenir proposé traverse ses gardes. Provenance selon le déclencheur : ce que l'utilisateur affirme est « dit »."""
        decl = f["declencheur"]
        prov = {"reponse_utilisateur": "dit", "correction": "dit", "geste_cage": "observe", "incident_clos": "observe", "decision_fil": "decision"}.get(decl, "infere")
        consigne = {"correction": "- l'utilisateur CORRIGE : retiens la version corrigée, pas l'ancienne.",
                    "reponse_utilisateur": "- l'utilisateur DEMANDE de retenir : retiens exactement ce qu'il dit de retenir.",
                    "geste_cage": "- des commandes ont été exécutées : retiens ce qu'elles ont ÉTABLI (configuration, correction, architecture), pas leur sortie brute."}.get(decl, "")
        pt = portee(f["compte"])
        prompt = o.PROMPT_DISTILLATION.format(declencheur=decl, max=5, consigne=consigne, deja_su=deja_su("%s %s" % (f["question"], (f["reponse"] or "")[:1500]), pt),
                                              question=f["question"][:1500], reponse=f["reponse"][:3000])
        brut = completer("principal", [{"role": "user", "content": prompt}], "", 1200, True, 40, 0.1)
        if brut is None:
            return {"ok": False, "raison": "modèle non prêt"}
        obj = o.json_extraire(brut, ctx.point) or {}
        ecrits, refus, ids = 0, 0, []
        piece = {"type": "message" if decl != "geste_cage" else "geste_cage", "source": "echange", "contenu": f["piece"], "date": o.maintenant()}
        for s in (obj.get("souvenirs") or [])[:5]:
            if not isinstance(s, dict):
                continue
            try:
                conf = float(s.get("confiance", 0.7))
            except (TypeError, ValueError):
                conf = 0.7
            r = ecrire_pour_compte(f, s, prov, conf, piece)       # ce qu'un échange distille est un relevé daté : on ne sait pas le rejouer (constat)
            if r.get("ok") and r.get("action") != "inchange":
                ecrits += 1
                ids.append(r["id"])
            elif not r.get("ok"):
                refus += 1
        return {"ok": True, "ecrits": ecrits, "refus": refus, "ids": ids}

    def ecrire_pour_compte(f, s, prov, conf, piece):
        """Écrit au nom du compte de l'échange (le moteur n'a pas de compte : la portée et le propriétaire sont ceux de l'échange)."""
        prop = ("compte:" + f["compte"]) if not est_systeme(f["compte"]) else ("itare" if f["acteur"] == "itare" else "cassandra")
        if prop.startswith("compte:") and ctx.est_admin(f["compte"]) and str(s.get("categorie")) != "personne":
            prop = "partage"
        return ecrire_coeur(s.get("categorie") or "fact", str(s.get("cle") or "")[:120], str(s.get("valeur") or "")[:400], prop, prov, conf, piece, f["declencheur"], f["acteur"] or f["compte"],
                            None, None, "constat", interne=True)

    def moteur_distiller(c):
        """Un modèle absent n'est pas une raison de perdre l'échange : il reste en file (un jour au plus), puis il est abandonné, dit."""
        n = 0
        for f in db.lire("SELECT * FROM file WHERE etat='attente' ORDER BY id LIMIT 5"):
            r = distiller_une(f)
            if r["ok"]:
                db.ecrire("UPDATE file SET etat='fait', resultat=? WHERE id=?", (json.dumps(r, ensure_ascii=False)[:500], f["id"]))
                n += 1
            elif (o.age(f["ts"]) or 0) > 86400:
                db.ecrire("UPDATE file SET etat='abandon', resultat=? WHERE id=?", (r.get("raison", "")[:200], f["id"]))
                journal("distillation_abandonnee", None, {"file": f["id"], "raison": r.get("raison", "")}, "systeme")
        return {"traitees": n}

    # ------------------------------------------------------------------ épisodes
    def episode_toucher(session_id, prop):
        """À chaque tour : l'épisode ouvert de la session s'allonge, ou se ferme (90 min de silence) et un nouveau s'ouvre."""
        now = o.maintenant()
        ep = db.lire("SELECT id, fin FROM episodes WHERE session_id=? AND statut='ouvert' ORDER BY id DESC LIMIT 1", (str(session_id),))
        with db.transaction() as cx:
            if ep and (o.age(ep[0]["fin"]) or 0) <= o.EPISODE_SILENCE_S:
                cx.execute("UPDATE episodes SET fin=?, n_messages=n_messages+1 WHERE id=?", (now, ep[0]["id"]))
                return {"id": ep[0]["id"]}
            return {"id": cx.execute("INSERT INTO episodes(proprietaire, session_id, debut, fin, n_messages, cree_le) VALUES (?,?,?,?,1,?)", (prop, str(session_id), now, now, now)).lastrowid}

    def fermer_episode(eid):
        """Idempotente ; le résumé par le modèle, ou un repli honnête (la première question, marquée « résumé indisponible »)."""
        r = db.lire("SELECT * FROM episodes WHERE id=? AND statut='ouvert'", (int(eid),))
        if not r:
            return None
        ep = r[0]
        hist = db.lire("SELECT role, contenu FROM messages WHERE episode_id=? ORDER BY id DESC LIMIT 40", (ep["id"],))[::-1]
        texte = "\n".join("%s : %s" % ("Utilisateur" if h["role"] == "user" else "Agent", h["contenu"][:700]) for h in hist)
        resume, ts = "", []
        if texte.strip():
            brut = completer("principal", [{"role": "user", "content": o.PROMPT_EPISODE.format(n=len(hist), texte=texte[:6000])}], "", 1200, True, 40, 0.1)
            if brut:
                obj = o.json_extraire(brut, ctx.point) or {}
                resume = " ".join(str(obj.get("resume") or "").split())[:1500]
                ts = [str(t)[:40] for t in (obj.get("termes") or []) if str(t).strip()][:12]
        if not resume:
            premiere = next((h["contenu"][:300] for h in hist if h["role"] == "user"), "")
            resume = "(résumé indisponible, modèle non prêt) " + premiere if premiere else "(épisode sans contenu lisible)"
        if o.a_un_secret(resume):
            resume, ts = "(résumé retiré : il contenait un secret)", []
        with db.transaction() as cx:
            cx.execute("UPDATE episodes SET statut='ferme', resume=?, termes=? WHERE id=? AND statut='ouvert'", (resume, " ".join(ts), ep["id"]))
            journal_cx(cx, "episode_ferme", None, {"episode": ep["id"], "messages": ep["n_messages"], "termes": ts[:6]}, "systeme")
        return {"id": ep["id"], "resume": resume, "termes": ts}

    def episodes_chercher(question, pt, limite=3):
        ts = o.termes(question, 6)
        ph = ",".join("?" * len(pt))
        if ts:
            try:
                rows = db.lire("SELECT e.id, e.debut, e.fin, e.n_messages, e.resume, e.termes, bm25(episodes_fts) AS rang FROM episodes_fts JOIN episodes e ON e.id = episodes_fts.rowid "
                               "WHERE episodes_fts MATCH ? AND e.proprietaire IN (%s) AND e.statut='ferme' ORDER BY rang ASC, e.id DESC LIMIT ?" % ph, [o.requete_fts(ts)] + list(pt) + [int(limite)])
                if rows:
                    return rows
            except Exception:
                pass
        return db.lire("SELECT id, debut, fin, n_messages, resume, termes FROM episodes WHERE proprietaire IN (%s) AND statut='ferme' ORDER BY id DESC LIMIT ?" % ph, list(pt) + [int(limite)])

    def episodes_bloc(question, pt):
        eps = episodes_chercher(question, pt)
        if not eps:
            return "— épisodes : aucun épisode fermé ne parle de ça —"
        return "\n".join(["— épisodes (la dernière fois) —"] + ["[E:%d] du %s au %s · %s message(s) : %s" % (e["id"], (e["debut"] or "")[:16], (e["fin"] or "")[:16], e["n_messages"], str(e["resume"] or "")[:400])
                                                             for e in eps])

    def episodes(c, question="", limite=20):
        pt = portee()
        if question:
            return {"episodes": episodes_chercher(question, pt, min(int(limite or 3), 20))}
        return {"episodes": db.lire("SELECT id, proprietaire, session_id, debut, fin, n_messages, statut, resume, termes FROM episodes WHERE proprietaire IN (%s) ORDER BY id DESC LIMIT ?" % ",".join("?" * len(pt)),
                                    list(pt) + [int(limite)])}

    # ------------------------------------------------------------------ rappels conditionnés aux capteurs
    def rappel_poser(c, cle="", metrique="", op="", seuil=None, message="", proprietaire=None):
        acteur = acteur_courant()
        prop = proprietaire or proprietaire_defaut("perception")
        if prop not in portee():
            raise ValueError("hors de ta portée")
        metrique, op = str(metrique or "").strip(), str(op or "").strip()
        msg = " ".join(str(message or "").split())[:400]
        k = o.cle_de(cle)
        if not k:
            raise ValueError("clé vide")
        if not (metrique in o.METRIQUES or metrique.startswith(("machine_hors_ligne:", "site_hors_ligne:"))):
            raise ValueError("métrique inconnue (attendues : %s, machine_hors_ligne:<nom>, site_hors_ligne:<domaine>)" % ", ".join(o.METRIQUES))
        if op not in o.RAPPEL_OPS:
            raise ValueError("opérateur inconnu")
        try:
            seuil = float(seuil)
        except (TypeError, ValueError):
            raise ValueError("seuil non numérique")
        if not msg:
            raise ValueError("message vide")
        if o.a_un_secret(msg):
            raise ValueError("le message contient un secret")
        if o.RE_CONSIGNE.search(msg):
            raise ValueError("le message est une consigne d'injection")
        deja = db.lire("SELECT * FROM rappels WHERE proprietaire=? AND cle=? AND actif=1", (prop, k))
        with db.transaction() as cx:
            if deja:
                cx.execute("UPDATE rappels SET metrique=?, op=?, seuil=?, message=?, acteur=? WHERE id=?", (metrique, op, seuil, msg, acteur, deja[0]["id"]))
                rid, action = deja[0]["id"], "remplace"
            else:
                rid, action = cx.execute("INSERT INTO rappels(proprietaire, cle, metrique, op, seuil, message, acteur, cree_le) VALUES (?,?,?,?,?,?,?,?)", (prop, k, metrique, op, seuil, msg, acteur, o.maintenant())).lastrowid, "ecriture"
            journal_cx(cx, "rappel_pose", None, {"rappel": rid, "cle": k, "condition": "%s %s %s" % (metrique, op, seuil), "proprietaire": prop}, acteur)
        return {"id": rid, "action": action, "cle": k, "avant_rappel": dict(deja[0]) if deja else None}

    def prouver_rappel_pose(c, res):
        r = db.lire("SELECT actif FROM rappels WHERE id=?", (res["id"],))
        return bool(r) and r[0]["actif"] == 1

    def defaire_rappel_pose(c, res):
        a = res["avant_rappel"]
        if a:
            db.ecrire("UPDATE rappels SET metrique=?, op=?, seuil=?, message=?, acteur=? WHERE id=?", (a["metrique"], a["op"], a["seuil"], a["message"], a["acteur"], a["id"]))
        else:
            db.ecrire("UPDATE rappels SET actif=0 WHERE id=?", (res["id"],))

    def rappel_oter(c, id=0):
        pt = portee()
        r = db.lire("SELECT id FROM rappels WHERE id=? AND proprietaire IN (%s)" % ",".join("?" * len(pt)), [int(id or 0)] + list(pt))
        if not r:
            raise ValueError("rappel introuvable")
        with db.transaction() as cx:
            cx.execute("UPDATE rappels SET actif=0 WHERE id=?", (r[0]["id"],))
            journal_cx(cx, "rappel_ote", None, {"rappel": r[0]["id"]}, acteur_courant())
        return {"id": r[0]["id"]}

    def prouver_rappel_ote(c, res):
        return db.lire("SELECT actif FROM rappels WHERE id=?", (res["id"],))[0]["actif"] == 0

    def defaire_rappel_ote(c, res):
        db.ecrire("UPDATE rappels SET actif=1 WHERE id=?", (res["id"],))

    def rappels(c, actifs_seuls=False):
        pt = portee()
        return {"rappels": db.lire("SELECT * FROM rappels WHERE proprietaire IN (%s)%s ORDER BY id DESC LIMIT 100" % (",".join("?" * len(pt)), " AND actif=1" if actifs_seuls else ""), list(pt))}

    def mesures():
        """Les mesures des capteurs, lues dans le modèle du monde du sensorium (un état se mesure, il ne se rappelle pas)."""
        out = {}
        for r in lignes_monde():
            wk, val = str(r.get("wkey") or ""), str(r.get("value") or "")
            nb = re.search(r"-?\d+(?:[.,]\d+)?", val)
            x = float(nb.group(0).replace(",", ".")) if nb else None
            if wk == "disk./.usage" and x is not None:
                out["disk_pct"] = x
            elif wk == "disk./.free" and x is not None:
                out["disk_free_gb"] = x
            elif wk == "ram.usage" and x is not None:
                out["ram_pct"] = x
            elif wk == "load.1m" and x is not None:
                out["load1"] = x
            elif wk.startswith("fleet."):
                out["machine_hors_ligne:" + wk[6:]] = 0.0 if val.startswith("en ligne") else 1.0
            elif wk.startswith("web."):
                out["site_hors_ligne:" + wk[4:]] = 1.0 if re.search(r"(?i)ne r[ée]pond pas|hors|down|inaccessible", val) else 0.0
        return out

    def evaluer_rappels(metriques=None):
        """Chaque rappel actif contre la dernière mesure ; vrai = un constat, au plus un par jour et par rappel ; tout au journal. Rien n'est exécuté."""
        rs = db.lire("SELECT * FROM rappels WHERE actif=1")
        if not rs:
            return []
        m = dict(metriques if metriques is not None else mesures())
        tires = []
        for r in rs:
            v = m.get(r["metrique"])
            if v is None or not o.rappel_vrai(r["op"], float(v), float(r["seuil"])):
                continue
            if r["dernier_declenche"] and (o.age(r["dernier_declenche"]) or 0) < 86400:
                continue
            with db.transaction() as cx:
                cx.execute("UPDATE rappels SET dernier_declenche=?, nb_declenches=nb_declenches+1 WHERE id=?", (o.maintenant(), r["id"]))
                journal_cx(cx, "rappel_declenche", None, {"rappel": r["id"], "cle": r["cle"], "valeur": v, "condition": "%s %s %s" % (r["metrique"], r["op"], r["seuil"])}, "systeme")
            tires.append({"id": r["id"], "cle": r["cle"], "valeur": v, "message": r["message"], "metrique": r["metrique"], "op": r["op"], "seuil": r["seuil"], "proprietaire": r["proprietaire"]})
        return tires

    # ------------------------------------------------------------------ la péremption : « etat-courant » relu quand son artefact bouge
    def relire(limite=200):
        """Trois issues et un cas à part : l'artefact a DISPARU (expire sans re-mesure) ; l'empreinte a bougé et la sonde CONFIRME (reste actif) ; l'empreinte a bougé et la sonde CONTREDIT
        (expire, avec la raison) ; la sonde ne répond plus (on ne conclut RIEN : ne pas savoir n'est pas une réfutation)."""
        out = {"vus": 0, "immobiles": 0, "confirmes": 0, "contredits": 0, "disparus": 0, "muets": 0}
        for r in db.lire("SELECT * FROM memoires WHERE statut='actif' AND nature='etat-courant' AND COALESCE(artefact,'')<>'' ORDER BY id LIMIT ?", (int(limite),)):
            out["vus"] += 1
            neuve = artefact_empreinte(r["artefact"])
            if not neuve:
                out["disparus"] += 1
                with db.transaction() as cx:
                    expirer_cx(cx, r, "l'artefact %s a disparu : le fait n'a plus où se tenir" % r["artefact"], "systeme", "oubli")
                continue
            if neuve == (r["artefact_empreinte"] or ""):
                out["immobiles"] += 1
                continue
            val, _a, err = sonde(r["sonde"], json.loads(r["sonde_args"] or "[]"))
            if err:
                out["muets"] += 1
                continue
            if val == json.loads(r["sonde_valeur"] or "null"):
                out["confirmes"] += 1
                db.ecrire("UPDATE memoires SET artefact_empreinte=?, maj_le=? WHERE id=?", (neuve, o.maintenant(), r["id"]))
            else:
                out["contredits"] += 1
                with db.transaction() as cx:
                    expirer_cx(cx, r, "re-mesuré après un changement de %s : la sonde %s rend %r au lieu de %r" % (r["artefact"], r["sonde"], val, json.loads(r["sonde_valeur"] or "null")), "systeme", "oubli")
        return out

    def prets_echus():
        n = 0
        with db.transaction() as cx:
            for r in cx.execute("SELECT * FROM memoires WHERE statut='actif' AND valide_a IS NOT NULL AND valide_a < ?", (o.maintenant(),)).fetchall():
                expirer_cx(cx, r, "prêt échu", "systeme")
                n += 1
        return n

    # ------------------------------------------------------------------ le rappel
    def lignes_monde():
        r = lecture("sensorium.monde")
        rows = r.get("rows") if isinstance(r, dict) else r
        return [x for x in (rows or []) if isinstance(x, dict)]

    def perception_bloc(question="", limite=12):
        q = (question or "").lower()
        lignes = o.perception_monde(lignes_monde(), q, set(), ctx.point, limite)
        if not lignes:
            return "— perception : aucun relevé disponible ; mesure avant de répondre —"
        return "— perception (mesurée à l'instant, jamais rappelée) —\n" + "\n".join(lignes[:limite * 2])

    def perception(c, question=""):
        return {"bloc": perception_bloc(question)}

    def rappeler(c, question="", limite=12, plafond=o.BLOC_MAX, avec_doutes=True):
        t0 = time.time()
        pt = portee()
        route = o.routage(question)
        out = {"route": route, "cites": [], "bloc": "", "n": 0, "ms": 0, "perception": "", "episodes": ""}
        now = o.maintenant()
        ph = ",".join("?" * len(pt))
        lignes, cites, taille, plafond = [], [], 0, int(plafond or o.BLOC_MAX)
        noyau = db.lire("SELECT id, categorie, cle, valeur, confiance, provenance, force, proprietaire, cree_le, nature, maj_le FROM memoires WHERE proprietaire IN (%s) AND statut='actif' "
                        "AND (valide_a IS NULL OR valide_a > ?) AND (force >= 1 OR categorie='personne') ORDER BY force DESC, maj_le DESC LIMIT 8" % ph, list(pt) + [now])
        vus, trouves = set(), []
        for r in noyau:
            vus.add(r["id"])
            cites.append((r["id"], r["categorie"], r["cle"], float(r["confiance"] or 0), r["provenance"], 1.0))
        if route == "episode":
            out["episodes"] = episodes_bloc(question, pt)
        if route == "perception":
            out["perception"] = perception_bloc(question)
        else:
            # Une question qui NOMME une chose que le sensorium mesure reçoit la mesure à côté des souvenirs : sinon un vieux souvenir répondait seul, là où un relevé de la minute existait.
            pm = o.perception_monde(lignes_monde(), (question or "").lower(), set(), ctx.point, 6, True) if question else []
            if pm:
                out["perception"] = "— perception (mesurée à l'instant, prime sur tout souvenir) —\n" + "\n".join(pm)
            ts = o.termes(question, 8)
            if ts:
                sl = o.seuil(route, question, int(ctx.reglage("seuil_rappel_pct") or 40) / 100.0)
                try:
                    rows = db.lire("SELECT m.id, m.categorie, m.cle, m.valeur, m.confiance, m.provenance, m.force, m.proprietaire, m.cree_le, m.nature, m.maj_le, bm25(memoires_fts) AS rang "
                                   "FROM memoires_fts JOIN memoires m ON m.id = memoires_fts.rowid WHERE memoires_fts MATCH ? AND m.proprietaire IN (%s) AND m.statut='actif' "
                                   "AND (m.valide_a IS NULL OR m.valide_a > ?) ORDER BY rang ASC, m.force DESC, m.dernier_rappel DESC LIMIT ?" % ph,
                                   [o.requete_fts(ts)] + list(pt) + [now, int(limite) * 2])
                except Exception:
                    rows = []
                for r in rows:
                    s = max(o.score(r["rang"]), o.couverture(ts, r["cle"] + " " + r["valeur"]))
                    if r["id"] in vus or s < sl:
                        continue
                    vus.add(r["id"])
                    trouves.append((r, s))
                    if len(trouves) >= int(limite):
                        break
        for r, s in trouves:
            cites.append((r["id"], r["categorie"], r["cle"], float(r["confiance"] or 0), r["provenance"], round(s, 2)))
        for r in list(noyau) + [t[0] for t in trouves]:
            v = str(r["valeur"] or "")
            v = v if len(v) <= 200 else v[:197] + "…"
            l1 = "[M:%d] %s · %s · conf %s · %s%s · %s" % (r["id"], r["categorie"], r["cle"], ("%.2f" % float(r["confiance"] or 0)).replace(".", ","), r["provenance"],
                                                         " · épinglé" if (r["force"] or 0) >= 1 else "", o.fraicheur(r))
            l2 = "  « %s »" % v
            if taille + len(l1) + len(l2) + 2 > plafond:
                break
            lignes += [l1, l2]
            taille += len(l1) + len(l2) + 2
        n = len(lignes) // 2
        cites = cites[:n]
        if n:
            out["bloc"] = "\n".join(["— mémoire : %d souvenir%s (route %s) — un [M:id] cité se met en pied de réponse —" % (n, "s" if n > 1 else "", route)] + lignes)
        elif route != "perception":
            out["bloc"] = "— mémoire : rien de connu sur ce sujet ; « je ne sais pas » vaut mieux qu'une invention —"
        if out["perception"]:
            out["bloc"] = (out["perception"] + ("\n" + out["bloc"] if out["bloc"] else "")).strip()
        if out["episodes"]:
            out["bloc"] = (out["episodes"] + ("\n" + out["bloc"] if out["bloc"] else "")).strip()
        # Le doute de l'agent sur lui-même : inféré, sous 0,5, vieux de 30 jours, et cité ; et l'ÉTAT DE MACHINE noté une fois, cité après quinze jours sans confirmation, on demande.
        with db.transaction() as cx:
            for r in list(noyau) + [t[0] for t in trouves]:
                if (r["provenance"] == "infere" and float(r["confiance"] or 0) < 0.5 and (o.age(r["cree_le"]) or 0) > 30 * 86400) or o.a_reverifier(r):
                    douter_cx(cx, "revalidation", o.question_de("revalidation", r["valeur"], age_txt=o.duree_txt(o.age(r["cree_le"]))), r["proprietaire"], memoire_id=r["id"])
            if cites:
                ids = [x[0] for x in cites]
                cx.execute("UPDATE memoires SET nb_rappels=nb_rappels+1, dernier_rappel=? WHERE id IN (%s)" % ",".join("?" * len(ids)), [now] + ids)
                journal_cx(cx, "rappel_cite", None, {"question": (question or "")[:120], "ids": ids, "route": route}, acteur_courant())
        # Les doutes se posent à un humain seulement (jamais à Itare, jamais à un fil de fond).
        if avec_doutes and not est_systeme() and "itare" not in pt:
            bd = doute_bloc(pt)
            if bd:
                out["bloc"] = (out["bloc"] + "\n" + bd).strip()
                out["doutes"] = True
        out["cites"] = [{"id": x[0], "categorie": x[1], "cle": x[2], "confiance": x[3], "provenance": x[4], "score": x[5]} for x in cites]
        out["n"] = len(out["cites"])
        out["ms"] = int((time.time() - t0) * 1000)
        # Le cadran du rappel : un rappel qui ne rend RIEN et un rappel qui SATURE son bloc sont les deux seules mesures capables de justifier qu'on touche au seuil ou à la taille du bloc.
        if not out["cites"]:
            cadran_noter("rappel_vide", {"question": str(question)[:120] or "(portée seule)", "sans_question": not bool(question), "ms": out["ms"]})
        elif len(out.get("bloc") or "") >= int(plafond * 0.95):
            cadran_noter("rappel_plein", {"octets": len(out.get("bloc") or ""), "plafond": plafond, "n": out["n"]})
        if not est_systeme():
            db.ecrire("UPDATE tours SET cites=? WHERE compte=?", (json.dumps(out["cites"]), compte_courant()))
        return out

    # ------------------------------------------------------------------ lectures simples
    def lister(c, statut="actif", categorie=None, limite=200):
        pt = portee()
        sql = "SELECT * FROM memoires WHERE proprietaire IN (%s)" % ",".join("?" * len(pt))
        args = list(pt)
        if statut and statut != "tous":
            sql += " AND statut=?"
            args.append(statut)
        if categorie:
            sql += " AND categorie=?"
            args.append(categorie)
        return {"souvenirs": [avec_ref(r) for r in db.lire(sql + " ORDER BY force DESC, maj_le DESC LIMIT ?", args + [int(limite)])]}

    def chercher(c, question="", statut="actif", limite=20):
        pt = portee()
        ts = o.termes(question, 8)
        ph = ",".join("?" * len(pt))
        if statut == "actif" and ts:
            rows = db.lire("SELECT m.*, bm25(memoires_fts) AS rang FROM memoires_fts JOIN memoires m ON m.id = memoires_fts.rowid WHERE memoires_fts MATCH ? AND m.proprietaire IN (%s) AND m.statut='actif' "
                           "ORDER BY rang ASC, m.force DESC LIMIT ?" % ph, [o.requete_fts(ts)] + list(pt) + [int(limite)])
            return {"souvenirs": [avec_ref(r) for r in rows]}
        like = "%" + (ts[0] if ts else "") + "%"
        sql, args = "SELECT * FROM memoires WHERE proprietaire IN (%s) AND (valeur LIKE ? OR cle LIKE ?)" % ph, list(pt) + [like, like]
        if statut and statut != "tous":
            sql += " AND statut=?"
            args.append(statut)
        return {"souvenirs": [avec_ref(r) for r in db.lire(sql + " ORDER BY maj_le DESC LIMIT ?", args + [int(limite)])]}

    def lire(c, id=0):
        m = exiger(id)
        d = avec_ref(m)
        d["versions"] = [avec_ref(r) for r in db.lire("SELECT * FROM memoires WHERE proprietaire=? AND cle=? AND id<>? ORDER BY version DESC, id DESC LIMIT 12", (m["proprietaire"], m["cle"], m["id"]))]
        d["piece"] = (db.lire("SELECT * FROM pieces WHERE id=?", (m["piece_id"],)) or [None])[0] if m["piece_id"] else None
        d["donne_par"] = None
        if m["don_de"]:
            src = db.lire("SELECT id, proprietaire FROM memoires WHERE id=?", (m["don_de"],))
            d["donne_par"] = {"id": m["don_de"], "proprietaire": src[0]["proprietaire"] if src else "?"}
        d["copies"] = db.lire("SELECT id, proprietaire, statut, valide_a FROM memoires WHERE don_de=? ORDER BY id", (m["id"],))
        d["journal"] = db.lire("SELECT ts, acteur, verbe, details FROM journal WHERE memoire_id=? ORDER BY id DESC LIMIT 20", (m["id"],))
        return {"souvenir": d}

    def journal_lire(c, limite=100, verbe=None):
        """Le journal, borné à la portée du lecteur : les gestes sur SES souvenirs, et les refus de garde qui le concernent (le propriétaire est dans les détails du refus)."""
        pt = set(portee())
        sql, args = "SELECT j.id, j.ts, j.acteur, j.verbe, j.memoire_id, j.details, m.proprietaire, m.cle FROM journal j LEFT JOIN memoires m ON m.id = j.memoire_id", []
        if verbe:
            sql += " WHERE j.verbe = ?"
            args.append(verbe)
        out = []
        for r in db.lire(sql + " ORDER BY j.id DESC LIMIT ?", args + [int(limite) * 4]):
            prop = r["proprietaire"]
            if prop is None:
                try:
                    prop = (json.loads(r["details"] or "{}") or {}).get("proprietaire")
                except (ValueError, AttributeError):
                    prop = None
            if prop is not None and prop not in pt:
                continue
            out.append({k: r[k] for k in ("id", "ts", "acteur", "verbe", "memoire_id", "cle", "details")})
            if len(out) >= int(limite):
                break
        return {"journal": out}

    def exporter(c):
        pt = portee()
        rows = [avec_ref(r) for r in db.lire("SELECT * FROM memoires WHERE proprietaire IN (%s) ORDER BY id" % ",".join("?" * len(pt)), list(pt))]
        return {"n": len(rows), "sha256": hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(), "souvenirs": rows}

    def etat(c):
        pt = portee()
        ph = ",".join("?" * len(pt))
        doutes_expirer()
        dernieres = []
        for r in db.lire("SELECT j.ts, j.acteur, j.verbe, j.memoire_id, j.details, m.proprietaire AS prop FROM journal j LEFT JOIN memoires m ON m.id = j.memoire_id "
                         "WHERE j.verbe IN ('ecriture','remplace','conteste','oubli','correction','restaure') ORDER BY j.id DESC LIMIT 150"):
            prop = r.pop("prop")
            if prop is None:
                try:
                    prop = (json.loads(r.get("details") or "{}") or {}).get("proprietaire")
                except (ValueError, AttributeError):
                    prop = None
            if prop in pt:
                dernieres.append(r)
            if len(dernieres) >= 30:
                break
        ch = db.lire("SELECT verbe, ts, details FROM journal WHERE verbe IN ('chaine_verifiee','chaine_rompue') ORDER BY id DESC LIMIT 1")
        return {"statuts": {r["statut"]: r["n"] for r in db.lire("SELECT statut, COUNT(*) AS n FROM memoires WHERE proprietaire IN (%s) GROUP BY statut" % ph, list(pt))},
                "categories": {r["categorie"]: r["n"] for r in db.lire("SELECT categorie, COUNT(*) AS n FROM memoires WHERE proprietaire IN (%s) AND statut='actif' GROUP BY categorie" % ph, list(pt))},
                "proprietaires": {r["proprietaire"]: r["n"] for r in db.lire("SELECT proprietaire, COUNT(*) AS n FROM memoires WHERE proprietaire IN (%s) AND statut='actif' GROUP BY proprietaire" % ph, list(pt))},
                "refus_7j": [r for r in db.lire("SELECT ts, acteur, details FROM journal WHERE verbe='refus_garde' AND ts >= datetime('now','-7 days') ORDER BY id DESC LIMIT 60")
                             if (lambda p: p is None or p in pt)(_prop_de(r["details"]))][:30],
                "doutes_ouverts": db.lire("SELECT COUNT(*) AS n FROM doutes WHERE statut='ouvert' AND proprietaire IN (%s)" % ph, list(pt))[0]["n"],
                "chaine": ch[0] if ch else None, "cadran": cadran(), "derniers_gestes": dernieres, "portee": pt}

    def _prop_de(details):
        try:
            return (json.loads(details or "{}") or {}).get("proprietaire")
        except (ValueError, AttributeError):
            return None

    def chaine_verifier(c):
        return chaine_verifier_coeur()

    # ------------------------------------------------------------------ moteurs et détecteur
    def moteur_veto(c):
        n = 0
        for r in db.lire("SELECT id FROM memoires WHERE statut='quarantaine' ORDER BY id LIMIT 5"):
            examiner_veto(r["id"])
            n += 1
        return {"examines": n}

    def moteur_entretien(c):
        out = {"doutes_expires": doutes_expirer(), "prets_echus": prets_echus(), "relecture": relire()}
        for t in evaluer_rappels():
            ctx.emettre("souvenir.rappel", objet=("souvenir", "rappel-%d" % t["id"]), donnees={"message": t["message"][:200], "valeur": t["valeur"], "condition": "%s %s %s" % (t["metrique"], t["op"], t["seuil"])},
                        compte=t["proprietaire"][7:] if t["proprietaire"].startswith("compte:") else None)
        echus = [r["id"] for r in db.lire("SELECT id FROM episodes WHERE statut='ouvert' AND fin < datetime('now', ?) ORDER BY id LIMIT 3", ("-%d seconds" % o.EPISODE_SILENCE_S,))]
        for eid in echus:
            fermer_episode(eid)
        out["episodes_fermes"] = len(echus)
        last = db.lire("SELECT ts FROM journal WHERE verbe IN ('chaine_verifiee','chaine_rompue') ORDER BY id DESC LIMIT 1")
        if not last or (o.age(last[0]["ts"]) or 0) > 86400:               # une fois par jour, pas à chaque redémarrage
            v = chaine_verifier_coeur()
            journal("chaine_verifiee" if v["ok"] else "chaine_rompue", None, {"n": v["n"], "rupture": v["rupture"]}, "systeme")
        return out

    def det_chaine(c):
        v = chaine_verifier_coeur()
        if v["ok"]:
            return []
        return [{"objet": ("souvenir", "chaine"), "titre": "Mémoire : la chaîne du journal est rompue à l'entrée %s" % v["rupture"], "niveau": "critique",
                 "detail": "Le journal de la mémoire a été altéré hors de sa porte (ou corrompu) : %d entrées vérifiées avant la rupture." % v["n"]}]

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.moteur("entretien", moteur_entretien)
    c.moteur("veto", moteur_veto)
    c.moteur("distiller", moteur_distiller)
    c.detecteur("chaine_rompue", det_chaine)
    for cid, f in (("rappeler", rappeler), ("lister", lister), ("chercher", chercher), ("lire", lire), ("etat", etat), ("journal", journal_lire), ("exporter", exporter), ("doutes", doutes),
                   ("episodes", episodes), ("rappels", rappels), ("perception", perception), ("chaine_verifier", chaine_verifier), ("moteurs", lambda c: page_moteurs.page(o))):
        c.implementer(cid, f)
    c.implementer("ecrire", ecrire, prouver_ecrit, defaire_ecrit, simuler=lambda x, cle="", **_: "écrirait le souvenir « %s »" % cle)
    c.implementer("corriger", corriger, prouver_ecrit, defaire_ecrit, simuler=lambda x, id="", **_: "corrigerait le souvenir %s par une version nouvelle" % id)
    c.implementer("oublier", oublier, prouver_oublie, defaire_oublie, simuler=lambda x, id="", **_: "expirerait le souvenir %s" % id)
    c.implementer("restaurer", restaurer, prouver_restaure, defaire_annuler, simuler=lambda x, id="", **_: "restaurerait le souvenir %s" % id)
    c.implementer("forcer", forcer, prouver_force, defaire_annuler, simuler=lambda x, id="", force="", **_: "mettrait la force du souvenir %s à %s" % (id, force))
    c.implementer("donner", donner, prouver_don, defaire_annuler, simuler=lambda x, id="", destinataire="", **_: "donnerait le souvenir %s à %s" % (id, destinataire))
    c.implementer("don_retirer", don_retirer, prouver_don_retire, defaire_annuler, simuler=lambda x, copie_id="", **_: "retirerait la copie %s" % copie_id)
    c.implementer("purger_secret", purger_secret, prouver_purge, defaire_purge, simuler=lambda x, id="", **_: "effacerait la valeur du souvenir %s (irréversible)" % id)
    c.implementer("douter_resoudre", douter_resoudre, prouver_resolu, defaire_annuler, simuler=lambda x, id="", choix="", **_: "répondrait « %s » au doute %s" % (choix, id))
    c.implementer("doutes_depuis_reponse", doutes_depuis_reponse, prouver_depuis_reponse, defaire_depuis_reponse, simuler=lambda x, **_: "résoudrait les doutes cités dans la réponse")
    c.implementer("veto_lever", veto_lever, prouver_leve, defaire_annuler, simuler=lambda x, id="", **_: "lèverait la quarantaine du souvenir %s" % id)
    c.implementer("rappel_poser", rappel_poser, prouver_rappel_pose, defaire_rappel_pose, simuler=lambda x, cle="", **_: "poserait le rappel « %s »" % cle)
    c.implementer("rappel_oter", rappel_oter, prouver_rappel_ote, defaire_rappel_ote, simuler=lambda x, id="", **_: "ôterait le rappel %s" % id)
    c.implementer("tour_commencer", tour_commencer, prouver_tour, defaire_tour, simuler=lambda x, **_: "ouvrirait un tour")
    c.implementer("apres_echange", apres_echange, prouver_apres, defaire_apres, simuler=lambda x, **_: "garderait l'échange et mettrait sa distillation en file")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Refus, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
