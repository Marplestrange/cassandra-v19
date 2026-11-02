# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les mandats d'envoi
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : mandats
# ZONE       : CN
# VERSION CN : 0.2.0  #4742c6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les mandats d'envoi : l'autorisation d'envoyer, avec ses bornes.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=4742c6 ▼▼▼
"""Les mandats d'envoi : l'autorisation d'envoyer, avec ses bornes.

Porté de la V18 (`mandat_*`), avec ses leçons :
  - l'adresse ne vient JAMAIS de la demande (une adresse libre impose le mode « accord requis ») ;
  - un mandat se relit à voix haute : un réglage de permission qu'on ne peut pas relire n'est jamais vérifié ;
  - une variable employée mais non déclarée partirait littéralement dans le message : refusée à l'écriture ;
  - le journal des envois survit au mandat.

Le destinataire se résout depuis le carnet et le courrier (jamais depuis la demande), la pièce depuis le carnet de fichiers (confinement des racines, type, taille, signature),
et l'envoi réel passe par la capacité `courrier.envoyer_mandat`, qui ne reçoit qu'un numéro d'envoi : rien du contenu ne vient de l'appelant.

La vie d'un envoi : `attente` (l'accord est requis) ou `differe` (part seul à l'heure dite, sauf arrêt) ou `autorise` (l'accord est donné, le courrier poste)
-> `envoye` | `echec` ; `refuse` (une tentative interdite, consignée) ; `annule`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from email.utils import parseaddr

DECLENCHEURS = ("chat", "regle", "horaire")
SOURCES_DST = ("document", "liste", "domaine", "fil", "libre")
CONTROLES = ("auto", "differe", "accord")
TYPES_VAR = ("texte", "nombre", "date", "entier")
VAR_RE = re.compile(r"\{\{([a-z_][a-z0-9_]{0,29})\}\}")


EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VAL_INTERDIT = re.compile(r"(https?://|www\.|@|[\r\n])", re.I)       # une valeur de variable ne doit pas pouvoir réécrire le message : ni adresse, ni lien, ni saut de ligne


def _lignes(v):
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


def brancher(ctx):
    db = ctx.stockage

    def _get(mid):
        r = db.lire("SELECT * FROM mandats WHERE id=?", (int(mid),))
        return dict(r[0]) if r else None

    def _maj(sql, params):
        """Une mise à jour qui dit combien de lignes elle a touchées : de quoi réclamer un envoi sans qu'un autre geste le prenne en même temps."""
        with db.transaction() as cx:
            return cx.execute(sql, params).rowcount

    # ── lectures ─────────────────────────────────────────────────────────────
    def mandats(c):
        return {"mandats": db.lire("SELECT * FROM mandats ORDER BY id")}

    def plan(c, mid=0):
        m = _get(int(mid))
        if not m:
            raise ValueError("mandat introuvable")
        d = {"chat": "je le demande dans le chat", "regle": "une règle le décide", "horaire": "l'horaire arrive"}
        src = {"document": "contact rattaché au document", "liste": "une liste fermée",
               "domaine": "un domaine autorisé", "fil": "l'expéditeur du fil", "libre": "une adresse libre"}
        ctl = {"auto": "sans moi", "differe": "après %d min pendant lesquelles je peux l'arrêter" % int(m.get("differe_min") or 10),
               "accord": "après mon accord"}
        return {"id": m["id"], "nom": m["nom"],
                "quand": " ou ".join(d.get(x, x) for x in _lignes(m.get("declencheurs"))) or "jamais",
                "qui": src.get(m.get("dst_source"), "?") + ((" (%s)" % m["dst_valeur"]) if m.get("dst_valeur") else ""),
                "quoi": m.get("objet") or "(sans objet)",
                "piece": m.get("pj_motif") or "aucune pièce",
                "controle": ctl.get(m.get("controle"), "?"),
                "limite": "%d fois par jour" % int(m.get("quota_jour") or 0),
                "suspendu": bool(m.get("suspendu"))}

    def envois(c, mid=0, limite=100, etat=""):
        lim = max(1, min(int(limite or 100), 500))
        cond, args = [], []
        if int(mid or 0):
            cond.append("e.mandat_id=?")
            args.append(int(mid))
        etats = _lignes(etat)
        if etats:
            cond.append("e.etat IN (%s)" % ",".join("?" * len(etats)))
            args += etats
        rows = db.lire("SELECT e.*, COALESCE(m.nom,'mandat supprimé') AS mandat FROM mandat_envois e LEFT JOIN mandats m ON m.id=e.mandat_id"
                       + (" WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY e.id DESC LIMIT ?", tuple(args) + (lim,))
        out = []
        for r in rows:
            r = dict(r)
            try:
                r["variables"] = json.loads(r.get("variables") or "{}")
            except ValueError:
                r["variables"] = {}
            t = int(r.get("pj_taille") or 0)
            r["pj_taille_h"] = ("%d o" % t) if t < 1024 else (("%.0f Ko" % (t / 1024)) if t < 1048576 else ("%.1f Mo" % (t / 1048576)))
            out.append(r)
        return {"envois": out}

    # ── la préparation : tous les verrous, aucun envoi ───────────────────────
    def _mandat(ref):
        ref = str(ref or "").strip()
        if ref.isdigit():
            return _get(int(ref))
        r = db.lire("SELECT * FROM mandats WHERE nom=? COLLATE NOCASE", (ref,))
        return dict(r[0]) if r else None

    def _remplir(gabarit, vals):
        return VAR_RE.sub(lambda mm: vals.get(mm.group(1), ""), str(gabarit or ""))

    def _fiches(designation):
        try:
            r = ctx.executer_lecture("contacts.adresses_pour_mandat", reference=str(designation or "")) or {}
        except PermissionError:                                                      # le carnet n'est pas installé : aucune fiche n'adresse rien
            return []
        return [f for f in (r.get("fiches") or []) if f.get("emails")]

    def _fiche_de(adresse):
        """L'adresse donne la fiche, jamais l'inverse : enrichir un message ne change donc pas à qui l'on écrit."""
        try:
            f = _fiches(adresse)
            return f[0] if f else {}
        except Exception:
            return {}

    def _destinataire(m, cx):
        src = m.get("dst_source")
        if src == "liste":
            adrs = [a for a in _lignes(m.get("dst_valeur")) if EMAIL.match(a)]
            if not adrs:
                return None, "la liste du mandat ne contient aucune adresse valide"
            return {"adresses": adrs[:int(m.get("dst_max") or 1)], "via": "liste fermée du mandat", "fiche": _fiche_de(adrs[0])}, ""
        if src == "domaine":
            a = str(cx.get("destinataire", "")).strip().lower()
            dom = str(m.get("dst_valeur", "")).strip().lstrip("@").lower()
            if not EMAIL.match(a):
                return None, "adresse absente ou invalide"
            if not a.endswith("@" + dom):
                return None, "« %s » n'est pas dans le domaine autorisé @%s" % (a, dom)
            return {"adresses": [a], "via": "domaine autorisé @" + dom, "fiche": _fiche_de(a)}, ""
        if src == "fil":
            uid = str(cx.get("uid", "")).strip()
            if not uid:
                return None, "aucun message d'origine"
            try:
                r = ctx.executer_lecture("courrier.lire", uid=uid, dossier=str(cx.get("dossier") or "INBOX"))
            except Exception:
                r = None
            if not r:
                return None, "message d'origine illisible"
            a = (parseaddr(r.get("repondre_a") or r.get("de") or "")[1] or "").strip()
            if not EMAIL.match(a):
                return None, "expéditeur du fil illisible"
            return {"adresses": [a], "via": "expéditeur du fil", "uid": uid, "fiche": _fiche_de(a)}, ""
        if src == "libre":
            a = str(cx.get("destinataire", "")).strip()
            if not EMAIL.match(a):
                return None, "adresse invalide"
            return {"adresses": [a], "via": "adresse libre — accord requis", "fiche": _fiche_de(a)}, ""
        ref = str(cx.get("contact") or cx.get("reference") or "").strip()
        if not ref:
            return None, "aucune référence de contact ou de document"
        fiches = _fiches(ref)
        if not fiches:
            return None, "« %s » ne correspond à aucune fiche du carnet — un mandat n'invente pas d'adresse" % ref[:60]
        if len(fiches) > 1:
            return None, "« %s » désigne plusieurs fiches (%s) : précisez" % (ref[:40], ", ".join(str(f.get("display_name") or "?") for f in fiches[:4]))
        f = fiches[0]
        adrs = [a for a in f["emails"] if EMAIL.match(str(a or ""))]
        if not adrs:
            return None, "la fiche « %s » n'a pas d'adresse" % (f.get("display_name") or ref)
        return {"adresses": adrs[:1], "via": "fiche « %s »" % (f.get("display_name") or ref), "contact_id": str(f.get("id") or ""), "fiche": f}, ""

    def _valeurs(m, cx, fiche):
        vals, manque = {}, []
        fournies = cx.get("variables") or {}
        try:
            declarees = json.loads(m.get("variables") or "[]")
        except ValueError:
            declarees = []
        for v in declarees:
            n, t = v["nom"], v.get("type", "texte")
            if v.get("source") == "fiche":
                brut = (fiche or {}).get(n) or (fiche or {}).get({"prenom": "display_name", "societe": "company"}.get(n, n)) or ""
                if n == "prenom" and brut:
                    brut = str(brut).split()[0]
            else:
                brut = fournies.get(n, "")
            brut = str(brut or "").strip()
            if not brut:
                manque.append(n)
                continue
            if len(brut) > int(v.get("max") or 60):
                return None, "{{%s}} dépasse %s signes" % (n, v.get("max"))
            if v.get("source") != "fiche" and VAL_INTERDIT.search(brut):
                return None, "{{%s}} ne peut contenir ni adresse, ni lien, ni retour à la ligne" % n      # sans cela, une variable suffirait à réécrire le message
            if t == "nombre" and not re.match(r"^-?\d+([.,]\d+)?$", brut):
                return None, "{{%s}} doit être un nombre" % n
            if t == "entier" and not re.match(r"^-?\d+$", brut):
                return None, "{{%s}} doit être un entier" % n
            if t == "date" and not re.match(r"^\d{4}-\d{2}-\d{2}$", brut):
                return None, "{{%s}} doit être une date AAAA-MM-JJ" % n
            vals[n] = brut
        if manque:
            return None, "valeurs manquantes : %s" % ", ".join("{{%s}}" % x for x in manque)
        return vals, ""

    def _piece(m, vals):
        """Un dossier et un motif. L'agent ne choisit pas de fichier : il fournit des valeurs, et le motif désigne un fichier — s'il existe, au bon endroit."""
        if not (m.get("pj_dossier") and m.get("pj_motif")):
            return None, ""
        nom = _remplir(m["pj_motif"], vals)
        if not nom or "/" in nom or "\\" in nom or ".." in nom:
            return None, "nom de pièce jointe invalide : « %s »" % nom[:60]
        source = "local:" + str(m["pj_dossier"]).strip()
        try:
            d = ctx.executer_lecture("ged.telecharger", source=source, chemin=nom)
        except Exception:
            d = None
        if not d or not d.get("chemin") or not os.path.isfile(d["chemin"]):
            if m.get("pj_obligatoire"):
                return None, "pièce « %s » introuvable (ou hors des racines déclarées) — le message annoncerait une pièce absente" % nom
            return None, ""
        ext = os.path.splitext(d["chemin"])[1].lstrip(".").lower()
        types = [x.lower() for x in _lignes(m.get("pj_types") or "pdf")]
        if types and ext not in types:
            return None, "type « %s » non autorisé (attendu : %s)" % (ext, ", ".join(types))
        taille = os.path.getsize(d["chemin"])
        if taille > int(m.get("pj_max") or 2097152):
            return None, "pièce trop lourde (%d Ko)" % (taille // 1024)
        with open(d["chemin"], "rb") as f:
            emp = hashlib.sha256(f.read()).hexdigest()[:16]
        return {"source": source, "chemin": nom, "nom": nom, "taille": taille, "empreinte": emp}, ""

    def _limites(m, cle):
        n = db.lire("SELECT COUNT(*) AS n FROM mandat_envois WHERE mandat_id=? AND etat='envoye' AND date(ts)=date('now')", (m["id"],))[0]["n"]
        if cle:
            deja = db.lire("SELECT ts, etat FROM mandat_envois WHERE cle=? AND etat IN ('envoye','attente','differe','autorise')", (cle,))
            if deja:
                return "double", "déjà %s le %s — un mandat n'envoie pas deux fois la même chose" % ("parti" if deja[0]["etat"] == "envoye" else deja[0]["etat"], str(deja[0]["ts"])[:16])
        q = int(m.get("quota_jour") or 0)
        if q and n >= q:
            return "quota", "quota du jour atteint (%d/%d)" % (n, q)
        h, d0, f0 = datetime.now().strftime("%H:%M"), (m.get("heure_debut") or "00:00"), (m.get("heure_fin") or "23:59")
        if not (d0 <= h <= f0):
            return "heure", "hors de la plage autorisée (%s–%s)" % (d0, f0)
        return "", ""

    def _incident(m, origine, acteur, motif, suspendre):
        db.ecrire("INSERT INTO mandat_envois (mandat_id, etat, origine, acteur, motif, compte) VALUES (?,?,?,?,?,?)",
                  (m.get("id"), "refuse", str(origine)[:20], str(acteur)[:40], str(motif)[:300], ctx.compte or ""))
        if suspendre and m.get("suspendre_incident"):
            db.ecrire("UPDATE mandats SET suspendu=? WHERE id=?", ("tentative d'origine interdite le %s" % datetime.now().strftime("%d/%m %H:%M"), m["id"]))

    def _preparer(mandat, contexte, origine, ecrire):
        """Résout un envoi sans rien envoyer : un envoi prêt, ou un refus motivé (`ok` faux, `refus`, `reason`). Tout se joue ici ; l'envoi ne fait que poster ce que cette fonction a produit."""
        cx = dict(contexte or {})
        m = _mandat(mandat)
        if not m:
            return {"ok": False, "refus": "inconnu", "reason": "mandat inconnu : « %s »" % str(mandat)[:60]}
        refus = lambda code, texte: {"ok": False, "refus": code, "mandat": m["nom"], "reason": texte}
        if ctx.frein_actif("gel") or ctx.frein_actif("envois"):
            return refus("gel", "l'autonomie est gelée ou les envois sont coupés — aucun envoi ne part")
        origine = str(origine or "chat")
        if origine not in DECLENCHEURS:
            if ecrire:
                _incident(m, origine, ctx.acteur, "origine refusée : %s" % origine, True)
            return refus("origine", "un envoi ne part jamais sur l'ordre d'un contenu lu (origine : %s)" % origine)
        if origine not in _lignes(m.get("declencheurs")):
            return refus("declencheur", "ce mandat n'accepte pas d'être déclenché par « %s »" % origine)
        if not m.get("actif"):
            return refus("inactif", "mandat inactif")
        if m.get("suspendu"):
            return refus("suspendu", "mandat suspendu : %s" % m["suspendu"])
        d, raison = _destinataire(m, cx)
        if d is None:
            return refus("destinataire", raison)
        vals, raison = _valeurs(m, cx, d.get("fiche") or {})
        if vals is None:
            return refus("variables", raison)
        objet = _remplir(m.get("objet"), vals) or "(sans objet)"
        corps = _remplir(m.get("corps"), vals)
        if m.get("libre") and cx.get("libre"):
            libre = str(cx["libre"])[:int(m.get("libre_max") or 400)]
            if VAL_INTERDIT.search(libre.replace("\n", " ")):
                return refus("libre", "le paragraphe libre ne peut contenir ni adresse ni lien")
            corps = corps.replace("{{libre}}", libre) if "{{libre}}" in corps else (corps.rstrip() + "\n\n" + libre)
        pj, raison = _piece(m, vals)
        if raison:
            return refus("piece", raison)
        cle = ("%s:%s" % (m["id"], vals.get(m["unique_par"], "") or "-")) if m.get("unique_par") else ""
        code, raison = _limites(m, cle)
        if code:
            return refus(code, raison)
        return {"ok": True, "mandat_id": m["id"], "mandat": m["nom"], "destinataires": d["adresses"], "via": d["via"], "contact_id": d.get("contact_id", ""),
                "objet": objet, "corps": corps, "piece": pj, "variables": vals, "cle": cle, "controle": m.get("controle"), "origine": origine, "acteur": ctx.acteur,
                "differe_min": int(m.get("differe_min") or 10)}

    def essai(c, mandat="", contexte=None, origine="chat"):
        """L'essai à blanc : tous les verrous joués, rien mis en file, rien envoyé."""
        return _preparer(mandat, contexte, origine, False)

    # ── la file ───────────────────────────────────────────────────────────────
    def _etat(eid, etat, motif="", message_id=""):
        db.ecrire("UPDATE mandat_envois SET etat=?, motif=?, message_id=?, ts=CASE WHEN ?='envoye' THEN datetime('now') ELSE ts END WHERE id=?",
                  (etat, str(motif)[:300], str(message_id)[:200], etat, int(eid)))

    def _suspendre_sur_echec(e, raison):
        m = _get(e["mandat_id"])
        if m and m.get("suspendre_incident"):
            db.ecrire("UPDATE mandats SET suspendu=? WHERE id=?", ("échec d'envoi : %s" % str(raison)[:120], m["id"]))

    def _poster(eid, acteur="itare"):
        """Fait poster par le courrier un envoi déjà `autorise`. Rend (issue, détail) : `envoye`, `echec`, ou `retenu` (le courrier ne part pas seul : l'envoi retourne à l'accord)."""
        r = ctx.agir("courrier.envoyer_mandat", {"envoi": int(eid)}, acteur=acteur)
        st = r.get("statut")
        e = db.lire("SELECT * FROM mandat_envois WHERE id=?", (int(eid),))[0]
        if st == "faite":
            mid = (r.get("resultat") or {}).get("message_id", "")
            _etat(eid, "envoye", "", mid)
            return "envoye", mid
        if st in ("racontee", "simulee"):
            _etat(eid, "attente", "le courrier ne part pas seul (palier de courrier.envoyer_mandat) : l'accord est requis")
            return "retenu", ""
        raison = r.get("erreur") or r.get("raison") or r.get("motif") or st or "envoi impossible"
        _etat(eid, "echec", raison)
        _suspendre_sur_echec(e, raison)
        return "echec", str(raison)[:200]

    def declencher(c, mandat="", contexte=None, origine="chat"):
        """Le point d'entrée unique (chat, règle, horaire, outil d'agent) : selon le contrôle du mandat, l'envoi part, attend une minuterie ou attend l'accord."""
        p = _preparer(mandat, contexte, origine, True)
        if not p.get("ok"):
            return p
        ctl = p["controle"]
        etat = {"differe": "differe", "accord": "attente"}.get(ctl, "autorise")
        part_a = (datetime.now() + timedelta(minutes=p["differe_min"])).strftime("%Y-%m-%d %H:%M:%S") if ctl == "differe" else ""
        pj = p.get("piece") or {}
        try:
            eid = db.ecrire("INSERT INTO mandat_envois (mandat_id, etat, origine, acteur, destinataire, contact_id, objet, corps, pj_source, pj_chemin, pj_nom, pj_taille, pj_empreinte, "
                            "variables, cle, part_a, compte) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (p["mandat_id"], etat, p["origine"], p["acteur"], ", ".join(p["destinataires"]), p["contact_id"], p["objet"], p["corps"], pj.get("source", ""),
                             pj.get("chemin", ""), pj.get("nom", ""), pj.get("taille", 0), pj.get("empreinte", ""), json.dumps(p["variables"], ensure_ascii=False), p["cle"], part_a, ctx.compte or ""))
        except Exception as ex:
            if "UNIQUE" in str(ex).upper():
                return {"ok": False, "refus": "double", "mandat": p["mandat"], "reason": "un envoi identique est déjà en cours ou déjà parti"}
            raise
        sortie = {"ok": True, "envoi_id": eid, "mandat": p["mandat"], "controle": ctl, "etat": etat, "part_a": part_a, "destinataires": p["destinataires"],
                  "objet": p["objet"], "attente": ctl == "accord"}
        if etat == "autorise":
            issue, detail = _poster(eid, "itare")
            sortie.update(etat={"envoye": "envoye", "echec": "echec", "retenu": "attente"}[issue], attente=issue == "retenu")
            if issue == "envoye":
                sortie["message_id"] = detail
            elif issue == "echec":
                sortie.update(ok=False, reason=detail)
        return sortie

    def prouver_declencher(c, res):
        return (not res.get("ok") and not res.get("envoi_id")) or bool(db.lire("SELECT 1 FROM mandat_envois WHERE id=?", (int(res.get("envoi_id") or 0),)))

    def defaire_declencher(c, res):
        if res.get("envoi_id"):
            db.ecrire("UPDATE mandat_envois SET etat='annule', motif='retour arrière' WHERE id=? AND etat IN ('attente','differe')", (int(res["envoi_id"]),))

    def accord(c, envoi=0):
        """L'accord d'un humain sur un envoi qui attend : il devient `autorise`, et l'écran le fait poster par le courrier (puis déclare l'issue par `sortie`)."""
        eid = int(envoi or 0)
        e = db.lire("SELECT * FROM mandat_envois WHERE id=?", (eid,))
        if not e:
            raise ValueError("envoi introuvable")
        e = dict(e[0])
        if e["etat"] not in ("attente", "differe"):
            raise ValueError("cet envoi est déjà %s" % e["etat"])
        m = _get(e["mandat_id"])
        if m and m.get("suspendu"):
            raise ValueError("le mandat est suspendu : %s" % m["suspendu"])
        if not _maj("UPDATE mandat_envois SET etat='autorise', motif=?, compte=? WHERE id=? AND etat IN ('attente','differe')", ("accord de %s" % (ctx.compte or "un humain"), ctx.compte or e.get("compte") or "", eid)):
            raise ValueError("cet envoi vient d'être pris par un autre geste")
        return {"envoi_id": eid, "a": e["destinataire"], "objet": e["objet"]}

    def prouver_accord(c, res):
        return db.lire("SELECT etat FROM mandat_envois WHERE id=?", (res["envoi_id"],))[0]["etat"] == "autorise"

    def defaire_accord(c, res):
        db.ecrire("UPDATE mandat_envois SET etat='attente' WHERE id=? AND etat='autorise'", (res["envoi_id"],))

    def sortie(c, envoi=0, message_id="", erreur=""):
        """L'issue d'un envoi autorisé : parti (avec l'identifiant du message) ou échoué (avec la raison ; le mandat se suspend s'il le demande)."""
        eid = int(envoi or 0)
        e = db.lire("SELECT * FROM mandat_envois WHERE id=?", (eid,))
        if not e or e[0]["etat"] != "autorise":
            raise ValueError("cet envoi n'attend pas son issue")
        if erreur:
            _etat(eid, "echec", erreur)
            _suspendre_sur_echec(dict(e[0]), erreur)
            return {"envoi_id": eid, "etat": "echec"}
        _etat(eid, "envoye", "", message_id)
        return {"envoi_id": eid, "etat": "envoye"}

    def prouver_sortie(c, res):
        return db.lire("SELECT etat FROM mandat_envois WHERE id=?", (res["envoi_id"],))[0]["etat"] == res["etat"]

    def defaire_sortie(c, res):
        db.ecrire("UPDATE mandat_envois SET etat='autorise', message_id='' WHERE id=?", (res["envoi_id"],))      # le constat se retire ; ce que le courrier a posté, lui, ne se rappelle pas

    def annuler(c, envoi=0):
        eid = int(envoi or 0)
        if not _maj("UPDATE mandat_envois SET etat='annule', motif=? WHERE id=? AND etat IN ('attente','differe')", ("arrêté par %s" % (ctx.compte or "vous"), eid)):
            raise ValueError("cet envoi n'attendait plus — trop tard, ou déjà arrêté")
        return {"envoi_id": eid}

    def prouver_annule(c, res):
        return db.lire("SELECT etat FROM mandat_envois WHERE id=?", (res["envoi_id"],))[0]["etat"] == "annule"

    def defaire_annule(c, res):
        db.ecrire("UPDATE mandat_envois SET etat='attente' WHERE id=? AND etat='annule'", (res["envoi_id"],))

    def envoi_a_poster(c, envoi=0):
        """Pour le courrier seulement : l'envoi autorisé, tel qu'il doit partir (rien d'autre n'est posté)."""
        r = db.lire("SELECT * FROM mandat_envois WHERE id=? AND etat='autorise'", (int(envoi or 0),))
        if not r:
            return None
        e = dict(r[0])
        return {"destinataire": e["destinataire"].split(",")[0].strip(), "objet": e["objet"], "corps": e["corps"],
                "pj_source": e.get("pj_source") or "", "pj_chemin": e.get("pj_chemin") or "", "pj_empreinte": e.get("pj_empreinte") or ""}

    def minuterie(cx):
        """Fait partir ce dont la minuterie est écoulée (un envoi différé qui n'a pas été arrêté part : c'est le sens du mode), et clôt ce qu'un accord a laissé sans issue."""
        db.ecrire("UPDATE mandat_envois SET etat='echec', motif='envoi interrompu avant son issue' WHERE etat='autorise' AND ts < datetime('now','-10 minutes')")
        for d in db.lire("SELECT * FROM mandat_envois WHERE etat='differe' AND part_a<>'' AND part_a<=datetime('now') ORDER BY id LIMIT 20"):
            if not _maj("UPDATE mandat_envois SET etat='autorise', motif='la minuterie est écoulée' WHERE id=? AND etat='differe'", (d["id"],)):
                continue
            # le compte qui a demandé l'envoi : son serveur d'envoi, ses droits (même procédé que les tâches des agents)
            avant = (ctx._compte.valeur, ctx._societe.valeur)
            ctx._compte.valeur, ctx._societe.valeur = d["compte"] or "", (ctx.societe_de(d["compte"]) if d["compte"] else "")
            try:
                if not d["compte"]:
                    _etat(d["id"], "echec", "aucun compte n'a demandé cet envoi")
                else:
                    _poster(d["id"], "itare")
            except Exception as ex:
                _etat(d["id"], "echec", "minuterie : %s" % str(ex)[:200])
            finally:
                ctx._compte.valeur, ctx._societe.valeur = avant

    # ── écritures réversibles ────────────────────────────────────────────────
    def save(c, **d):
        if d.get("id") and not _get(d.get("id")):
            raise ValueError("mandat introuvable")
        nom = str(d.get("nom", "")).strip()[:80]
        if not nom:
            raise ValueError("nom du mandat requis")
        dec = [x for x in (d.get("declencheurs") or []) if x in DECLENCHEURS]
        if not dec:
            raise ValueError("au moins un déclencheur (%s)" % ", ".join(DECLENCHEURS))
        src = str(d.get("dst_source", "document"))
        if src not in SOURCES_DST:
            raise ValueError("source de destinataire inconnue")
        ctl = str(d.get("controle", "accord"))
        if ctl not in CONTROLES:
            raise ValueError("mode de contrôle inconnu")
        if src in ("liste", "domaine") and not str(d.get("dst_valeur", "")).strip():
            raise ValueError("cette source exige une valeur (liste ou domaine)")
        if src == "libre" and ctl != "accord":
            raise ValueError("une adresse libre impose le mode « accord requis » : sans cela le destinataire viendrait de la demande")
        variables, declarees = [], set()
        for v in (d.get("variables") or [])[:12]:
            n = str((v or {}).get("nom", "")).strip().lower()
            if not re.match(r"^[a-z_][a-z0-9_]{0,29}$", n):
                raise ValueError("nom de variable invalide : « %s »" % n)
            t = str(v.get("type", "texte"))
            if t not in TYPES_VAR:
                raise ValueError("type inconnu pour {{%s}}" % n)
            declarees.add(n)
            variables.append({"nom": n, "type": t, "source": str(v.get("source", "agent"))[:40],
                              "max": min(200, int(v.get("max", 60) or 60))})
        utilisees = set(VAR_RE.findall(str(d.get("objet", "")) + "\n" + str(d.get("corps", ""))))
        manquantes = utilisees - declarees
        if manquantes:
            raise ValueError("variables employées mais non déclarées : %s" % ", ".join("{{%s}}" % x for x in sorted(manquantes)))
        champs = ("nom", "actif", "declencheurs", "dst_source", "dst_valeur", "objet", "corps",
                  "variables", "libre", "libre_max", "pj_dossier", "pj_motif", "pj_types",
                  "pj_max", "pj_obligatoire", "controle", "differe_min",
                  "quota_jour", "dst_max", "heure_debut", "heure_fin", "unique_par", "suspendre_incident")
        vals = (nom, 1 if d.get("actif", 1) else 0, ",".join(dec), src,
                str(d.get("dst_valeur", ""))[:400], str(d.get("objet", ""))[:300], str(d.get("corps", ""))[:8000],
                json.dumps(variables, ensure_ascii=False),
                1 if d.get("libre") else 0, min(2000, int(d.get("libre_max", 400) or 400)),
                str(d.get("pj_dossier", "")).strip(), str(d.get("pj_motif", ""))[:200],
                str(d.get("pj_types", "pdf"))[:80], int(d.get("pj_max", 2097152) or 2097152),
                1 if d.get("pj_obligatoire", 1) else 0, ctl,
                max(1, min(1440, int(d.get("differe_min", 10) or 10))),
                max(0, min(200, int(d.get("quota_jour", 5) or 5))),
                max(1, min(20, int(d.get("dst_max", 1) or 1))),
                str(d.get("heure_debut", "08:00"))[:5], str(d.get("heure_fin", "19:00"))[:5],
                str(d.get("unique_par", ""))[:40], 1 if d.get("suspendre_incident", 1) else 0)
        avant = _get(int(d["id"])) if d.get("id") else None
        if d.get("id"):
            db.ecrire("UPDATE mandats SET " + ", ".join("%s=?" % c for c in champs) + ", suspendu='' WHERE id=?", vals + (int(d["id"]),))
            mid = int(d["id"])
        else:
            mid = db.ecrire("INSERT INTO mandats (" + ",".join(champs) + ") VALUES (" + ",".join("?" * len(champs)) + ")", vals)
        return {"id": mid, "avant": avant}

    def prouver_save(c, res):
        return bool(_get(res["id"]))

    def defaire_save(c, res):
        if res.get("avant") is None:
            db.ecrire("DELETE FROM mandats WHERE id=?", (res["id"],))
        else:
            a = res["avant"]
            champs = ("nom", "actif", "declencheurs", "dst_source", "dst_valeur", "objet", "corps",
                      "variables", "libre", "libre_max", "pj_dossier", "pj_motif", "pj_types",
                      "pj_max", "pj_obligatoire", "controle", "differe_min",
                      "quota_jour", "dst_max", "heure_debut", "heure_fin", "unique_par", "suspendre_incident", "suspendu")
            db.ecrire("UPDATE mandats SET " + ", ".join("%s=?" % c for c in champs) + " WHERE id=?",
                      tuple(a.get(c) for c in champs) + (res["id"],))

    def delete(c, mid=0):
        avant = _get(int(mid))
        if not avant:
            raise ValueError("mandat introuvable")
        db.ecrire("DELETE FROM mandats WHERE id=?", (int(mid),))
        db.ecrire("UPDATE mandat_envois SET etat='annule' WHERE mandat_id=? AND etat IN ('attente','differe')", (int(mid),))
        return {"id": int(mid), "avant": avant}

    def prouver_delete(c, res):
        return not _get(res["id"])

    def defaire_delete(c, res):
        a = res["avant"]
        champs = ("id", "nom", "actif", "declencheurs", "dst_source", "dst_valeur", "objet", "corps",
                  "variables", "libre", "libre_max", "pj_dossier", "pj_motif", "pj_types",
                  "pj_max", "pj_obligatoire", "controle", "differe_min",
                  "quota_jour", "dst_max", "heure_debut", "heure_fin", "unique_par", "suspendre_incident", "suspendu", "cree_le")
        db.ecrire("INSERT INTO mandats (" + ",".join(champs) + ") VALUES (" + ",".join("?" * len(champs)) + ")",
                  tuple(a.get(c) for c in champs))

    def suspendre(c, mid=0, motif="", reprendre=False):
        avant = _get(int(mid))
        if not avant:
            raise ValueError("mandat introuvable")
        db.ecrire("UPDATE mandats SET suspendu=? WHERE id=?",
                  ("" if reprendre else (str(motif)[:200] or "suspendu à la main"), int(mid)))
        return {"id": int(mid), "avant_suspendu": avant.get("suspendu")}

    def prouver_suspendre(c, res):
        return bool(_get(res["id"]))

    def defaire_suspendre(c, res):
        db.ecrire("UPDATE mandats SET suspendu=? WHERE id=?", (res.get("avant_suspendu") or "", res["id"]))

    for cid, f in (("mandats", mandats), ("plan", plan), ("envois", envois), ("essai", essai), ("envoi_a_poster", envoi_a_poster)):
        ctx.implementer(cid, f)
    ctx.moteur("minuterie", minuterie)
    ctx.implementer("declencher", declencher, prouver_declencher, defaire_declencher,
                    simuler=lambda x, mandat="", **_: "déclencherait le mandat « %s » (rien ne part avant le contrôle prévu)" % mandat)
    ctx.implementer("accord", accord, prouver_accord, defaire_accord, simuler=lambda x, envoi=0, **_: "donnerait l'accord à l'envoi %s" % envoi)
    ctx.implementer("sortie", sortie, prouver_sortie, defaire_sortie, simuler=lambda x, envoi=0, **_: "déclarerait l'issue de l'envoi %s" % envoi)
    ctx.implementer("annuler", annuler, prouver_annule, defaire_annule, simuler=lambda x, envoi=0, **_: "arrêterait l'envoi %s" % envoi)
    ctx.implementer("save", save, prouver_save, defaire_save,
                    simuler=lambda x, nom="", **_: "enregistrerait le mandat « %s »" % nom)
    ctx.implementer("delete", delete, prouver_delete, defaire_delete,
                    simuler=lambda x, mid=0, **_: "supprimerait le mandat %s" % mid)
    ctx.implementer("suspendre", suspendre, prouver_suspendre, defaire_suspendre,
                    simuler=lambda x, mid=0, **_: "suspendrait le mandat %s" % mid)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _lignes, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
