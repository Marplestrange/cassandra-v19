# ═══════════════════════════════════════════════════════════════════════════
# TITRE      : La bibliothèque d'Amizo
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : bibliotheque
# ZONE       : CN
# VERSION CN : 0.1.0  #6aa0e4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La bibliothèque.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ═══════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=6aa0e4 ▼▼▼
"""La bibliothèque d'Amizo : la connaissance SOURCÉE, dans sa propre base.

  - une fiche est un document avec sa provenance (adresse, date de lecture), découpé en passages dont la position est gardée ; un souvenir (module Mémoire) est
    une phrase retenue : les deux ne se mélangent pas ;
  - deux étagères : `interne` (lu dans un espace partagé de la société : déjà de confiance) et `externe` (lu sur le web : QUARANTAINE jusqu'à vérification) ;
  - états : quarantaine -> verifie | bloque ; « perime » n'est jamais écrit, il se lit (lu_le de plus de 90 jours) ; un contenu externe n'est « vérifié » que par l'accord
    d'un utilisateur qui a le droit `verifier`, ou par DEUX domaines différents qui ont porté exactement le même contenu (l'empreinte) ;
  - un contenu qui change repart en quarantaine (la vérification valait pour l'ancien texte) et l'ancienne version est gardée ;
  - la seule capacité qui écrit une fiche est `noter`, réservée à l'agent Amizo (acteur « agent » ET compte désigné par le réglage `compte_amizo`) ; vérifier, bloquer
    et retirer sont des gestes d'utilisateur, jamais d'un agent ;
  - tout est cloisonné par société : un identifiant d'une autre société se lit comme une fiche introuvable ;
  - aucune capacité ne lit ni n'écrit un bureau personnel.
Recherche : plein texte (FTS5), classée par pertinence, fraîcheur et confiance de la source. La recherche par le sens (vecteurs) est PRÉVUE : son modèle est écrit dans
la base, rien n'est calculé tant que le modèle n'est pas prêt.
"""
from __future__ import annotations

import array
import hashlib
import re
import time
from urllib.parse import urlsplit

ETATS_LUS = ("verifie", "quarantaine", "perime")
ETAGERES = ("interne", "externe")
JOURS_PEREMPTION = 90
PASSAGE_CIBLE, PASSAGE_MAX = 900, 1400
MAX_CORPS, MAX_TITRE, MAX_SOURCE = 400000, 200, 500
CONFIANCE = {"inconnue": 0.4, "autorisee": 0.8, "bloquee": 0.0}
POIDS = (0.70, 0.15, 0.15)                       # pertinence, fraîcheur, confiance
RE_MOT = re.compile(r"\w+", re.U)
RE_REF = re.compile(r"^(?:B-?)?0*(\d+)$", re.I)

_HORLOGE = [time.time]                           # un banc la remplace pour vieillir une fiche sans attendre
_VECTEURS = {"fournisseur": None}                # posé par brancher_vecteurs() quand le service d'encodage partagé existe


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)
_REFERENCES = {}


def _appeler_point(point, entree):
    """Appelle le point d'évolution du module. Sans brancher() (un banc qui appelle la fonction seule), la RÉFÉRENCE du dépôt répond : points/EC_<point>.py, chargée par son chemin."""
    if _point is not None:
        return _point(point, entree)
    if point not in _REFERENCES:
        import importlib.util as _iu
        import pathlib as _pl
        chemin = _pl.Path(__file__).resolve().parent / "points" / ("EC_%s.py" % point)
        spec = _iu.spec_from_file_location("ec_ref_" + point, str(chemin))
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _REFERENCES[point] = getattr(mod, "point_" + point)
    return _REFERENCES[point](entree)


def maintenant():
    return _HORLOGE[0]()


def ref_dite(i):
    return "B-%04d" % int(i)


def empreinte_de(texte):
    """Le contenu, rendu comparable (casse, espaces) : deux copies du même texte ont la même empreinte."""
    return hashlib.sha256(" ".join(str(texte or "").casefold().split()).encode("utf-8")).hexdigest()


def domaine_de(adresse):
    h = (urlsplit(str(adresse or "").strip()).hostname or "").lower().rstrip(".")
    return h[4:] if h.startswith("www.") else h


def etat_effectif(etat, lu_le, now, jours=JOURS_PEREMPTION):
    """« périmée » se calcule : seule une fiche non bloquée peut le devenir."""
    return "perime" if etat != "bloque" and now - lu_le > jours * 86400 else etat


def requete_fts(q):
    """Les mots de la question, entre guillemets, reliés par OU : le classement (bm25) fait le tri ; aucun opérateur FTS ne vient de l'extérieur."""
    return " OR ".join('"%s"' % m for m in RE_MOT.findall(str(q or ""))[:24])


def decouper(corps, titre=''):
    """Le texte en passages ordonnés : les paragraphes s'additionnent jusqu'à ~900 caractères ; un paragraphe trop long se coupe à une fin de phrase. Le calcul est un POINT D'ÉVOLUTION : points/EC_decouper.py."""
    return _appeler_point("decouper", {"corps": corps, "titre": titre})["valeur"]


def note_de(pertinence, age_jours, confiance, jours=JOURS_PEREMPTION):
    """Pertinence (0..1 du meilleur), fraîcheur (demi-vie = le délai de péremption) et confiance de la source."""
    fraicheur = 0.5 ** (max(0.0, age_jours) / float(jours))
    return round(POIDS[0] * pertinence + POIDS[1] * fraicheur + POIDS[2] * confiance, 4)


def brancher_vecteurs(fournisseur):
    """Le service d'encodage partagé (un objet : `nom`, `pret()`, `encoder(textes)`). Tant qu'il n'est pas posé, aucun vecteur n'est calculé."""
    _VECTEURS["fournisseur"] = fournisseur


def brancher(ctx):
    global _point
    _point = ctx.point
    db = ctx.stockage

    # ------------------------------------------------------------------ gardes
    def soc():
        return ctx.societe or "1"

    def qui():
        return ctx.compte or ""

    def jours():
        try:
            return int(ctx.reglage("jours_peremption") or JOURS_PEREMPTION)
        except (TypeError, ValueError):
            return JOURS_PEREMPTION

    def exiger_amizo():
        """La seule porte d'écriture d'une fiche : l'acteur « amizo » (le noyau ne le laisse porter que cette écriture), ou un agent invité dont le compte est celui que le réglage désigne comme Amizo (vide : personne d'autre n'écrit)."""
        if (ctx.acteur or "") == "amizo":
            return
        amizo = str(ctx.reglage("compte_amizo") or "").strip()
        if (ctx.acteur or "") != "agent" or not amizo or qui() != amizo:
            raise PermissionError("seul Amizo écrit dans la bibliothèque")

    def trace(cx, fid, quoi, det=""):
        cx.execute("INSERT INTO journal(ts, societe, fiche_id, quoi, par, det) VALUES(?,?,?,?,?,?)", (maintenant(), soc(), fid, quoi, (ctx.acteur or "") + ":" + qui(), str(det)[:300]))

    def dire(type_, fid, **donnees):
        try:
            ctx.emettre(type_, objet=("fiche", str(fid)), donnees=donnees, compte=qui() or None)
        except Exception:                           # le récit ne fait jamais échouer un geste
            pass

    # ------------------------------------------------------------------ accès
    def fiche_de(ref, avec_retirees=False):
        m = RE_REF.match(str(ref or "").strip())
        if not m:
            raise ValueError("référence de fiche invalide (attendu B-0007)")
        rows = db.lire("SELECT * FROM fiches WHERE id=? AND societe=?" + ("" if avec_retirees else " AND retire_le IS NULL"), (int(m.group(1)), soc()))
        if not rows:
            raise ValueError("fiche introuvable")
        return rows[0]

    def source_de(domaine):
        rows = db.lire("SELECT * FROM sources WHERE societe=? AND domaine=?", (soc(), domaine))
        if rows:
            return rows[0]
        return {"societe": soc(), "domaine": domaine, "statut": "inconnue", "confiance": CONFIANCE["inconnue"], "note": "", "maj": 0, "par": ""}

    def vue(f, now=None):
        now = now or maintenant()
        return {"ref": ref_dite(f["id"]), "titre": f["titre"], "etagere": f["etagere"], "etat": etat_effectif(f["etat"], f["lu_le"], now, jours()), "etat_stocke": f["etat"],
                "source": f["source"], "domaine": f["domaine"], "lu_le": f["lu_le"], "age_jours": int((now - f["lu_le"]) // 86400), "version": f["version"],
                "verifie_par": f["verifie_par"], "verifie_le": f["verifie_le"], "motif": f["motif"], "empreinte": f["empreinte"][:16]}

    def reecrire_passages(cx, fid, titre, corps):
        cx.execute("DELETE FROM passages WHERE fiche_id=?", (fid,))
        for pos, texte in enumerate(decouper(corps, titre)):
            cx.execute("INSERT INTO passages(fiche_id, position, titre, texte) VALUES(?,?,?,?)", (fid, pos, titre, texte))

    def concordance(cx, fid):
        """Deux domaines DIFFÉRENTS qui ont porté exactement ce contenu."""
        return cx.execute("SELECT COUNT(DISTINCT domaine) FROM attestations WHERE fiche_id=? AND domaine<>''", (fid,)).fetchone()[0]

    # ------------------------------------------------------------------ écrire (Amizo seule)
    def noter(c, etagere="externe", source="", titre="", corps="", lu_le=None):
        exiger_amizo()
        etagere = str(etagere or "").strip()
        if etagere not in ETAGERES:
            raise ValueError("étagère : interne ou externe")
        source, titre, corps = str(source or "").strip(), " ".join(str(titre or "").split()), str(corps or "").strip()
        if not source or len(source) > MAX_SOURCE:
            raise ValueError("la source (adresse ou espace:chemin) est obligatoire, %d caractères au plus" % MAX_SOURCE)
        if not titre or len(titre) > MAX_TITRE:
            raise ValueError("un titre est obligatoire (%d caractères au plus)" % MAX_TITRE)
        if not corps or len(corps) > MAX_CORPS:
            raise ValueError("le texte est obligatoire (%d caractères au plus)" % MAX_CORPS)
        if etagere == "externe":
            if urlsplit(source).scheme not in ("http", "https") or not domaine_de(source):
                raise ValueError("une fiche externe a pour source une adresse http(s)")
            dom = domaine_de(source)
            if source_de(dom)["statut"] == "bloquee":
                raise ValueError("source bloquée : %s" % dom)
        else:
            if "://" in source:
                raise ValueError("une fiche interne a pour source un espace partagé (espace:chemin), pas une adresse web")
            dom = ""
        now = float(lu_le) if lu_le else maintenant()
        if now > maintenant() + 3600:
            raise ValueError("la date de lecture est dans le futur")
        emp = empreinte_de(corps)
        etat0 = "verifie" if etagere == "interne" else "quarantaine"
        with db.transaction() as cx:
            f = cx.execute("SELECT * FROM fiches WHERE societe=? AND source=? AND retire_le IS NULL", (soc(), source)).fetchone()
            if f is not None and f["empreinte"] == emp:                       # relu à l'identique : seule la date de lecture avance
                cx.execute("UPDATE fiches SET lu_le=?, maj=? WHERE id=?", (now, maintenant(), f["id"]))
                cx.execute("UPDATE attestations SET lu_le=? WHERE fiche_id=? AND source=?", (now, f["id"], source))
                trace(cx, f["id"], "relue")
                return {"id": f["id"], "ref": ref_dite(f["id"]), "action": "rafraichi", "etat": etat_effectif(f["etat"], now, maintenant(), jours()), "avant_lu_le": f["lu_le"]}
            if f is not None:                                                  # la même adresse, un autre texte : nouvelle version
                autre = cx.execute("SELECT id FROM fiches WHERE societe=? AND empreinte=? AND retire_le IS NULL AND id<>?", (soc(), emp, f["id"])).fetchone()
                if autre is not None:
                    raise ValueError("ce texte est déjà dans la bibliothèque (%s)" % ref_dite(autre["id"]))
                cx.execute("INSERT INTO versions(fiche_id, numero, titre, corps, empreinte, lu_le, auteur, ts) VALUES(?,?,?,?,?,?,?,?)",
                           (f["id"], f["version"], f["titre"], f["corps"], f["empreinte"], f["lu_le"], f["auteur"], maintenant()))
                vid = cx.execute("SELECT last_insert_rowid()").fetchone()[0]
                nouvel = "bloque" if f["etat"] == "bloque" else etat0
                cx.execute("UPDATE fiches SET titre=?, corps=?, empreinte=?, etat=?, lu_le=?, maj=?, auteur=?, version=version+1, verifie_par='', verifie_le=NULL WHERE id=?",
                           (titre, corps, emp, nouvel, now, maintenant(), qui(), f["id"]))
                cx.execute("DELETE FROM attestations WHERE fiche_id=?", (f["id"],))
                cx.execute("INSERT INTO attestations(fiche_id, source, domaine, lu_le) VALUES(?,?,?,?)", (f["id"], source, dom, now))
                reecrire_passages(cx, f["id"], titre, corps)
                trace(cx, f["id"], "version", "v%d" % (f["version"] + 1))
                res = {"id": f["id"], "ref": ref_dite(f["id"]), "action": "version", "etat": nouvel, "version": f["version"] + 1, "version_gardee": vid,
                       "avant": {"etat": f["etat"], "verifie_par": f["verifie_par"], "verifie_le": f["verifie_le"], "maj": f["maj"], "auteur": f["auteur"]}}
            else:
                d = cx.execute("SELECT * FROM fiches WHERE societe=? AND empreinte=? AND retire_le IS NULL", (soc(), emp)).fetchone()
                if d is not None:                                              # le même contenu, une autre adresse : une attestation, pas une fiche
                    deja = cx.execute("SELECT 1 FROM attestations WHERE fiche_id=? AND source=?", (d["id"], source)).fetchone()
                    if not deja:
                        cx.execute("INSERT INTO attestations(fiche_id, source, domaine, lu_le) VALUES(?,?,?,?)", (d["id"], source, dom, now))
                    cx.execute("UPDATE fiches SET lu_le=MAX(lu_le, ?), maj=? WHERE id=?", (now, maintenant(), d["id"]))
                    etat, auto = d["etat"], False
                    if etat == "quarantaine" and d["etagere"] == "externe" and concordance(cx, d["id"]) >= 2:
                        cx.execute("UPDATE fiches SET etat='verifie', verifie_par='concordance', verifie_le=?, motif='' WHERE id=?", (maintenant(), d["id"]))
                        etat, auto = "verifie", True
                    trace(cx, d["id"], "doublon", source[:200] + (" -> verifie par concordance" if auto else ""))
                    res = {"id": d["id"], "ref": ref_dite(d["id"]), "action": "doublon", "etat": etat, "concordance": concordance(cx, d["id"]), "auto_verifie": auto,
                           "attestation": None if deja else source, "avant_etat": d["etat"], "avant_lu_le": d["lu_le"], "avant_verifie_par": d["verifie_par"], "avant_verifie_le": d["verifie_le"]}
                else:
                    cx.execute("INSERT INTO fiches(societe, etagere, source, domaine, titre, corps, empreinte, etat, lu_le, cree, maj, auteur) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                               (soc(), etagere, source, dom, titre, corps, emp, etat0, now, maintenant(), maintenant(), qui()))
                    fid = cx.execute("SELECT last_insert_rowid()").fetchone()[0]
                    cx.execute("INSERT INTO attestations(fiche_id, source, domaine, lu_le) VALUES(?,?,?,?)", (fid, source, dom, now))
                    if dom and not cx.execute("SELECT 1 FROM sources WHERE societe=? AND domaine=?", (soc(), dom)).fetchone():
                        cx.execute("INSERT INTO sources(societe, domaine, statut, confiance, maj, par) VALUES(?,?,?,?,?,?)", (soc(), dom, "inconnue", CONFIANCE["inconnue"], maintenant(), qui()))
                    reecrire_passages(cx, fid, titre, corps)
                    trace(cx, fid, "creee", etagere)
                    res = {"id": fid, "ref": ref_dite(fid), "action": "cree", "etat": etat0}
            res["passages"] = cx.execute("SELECT COUNT(*) FROM passages WHERE fiche_id=?", (res["id"],)).fetchone()[0]
        dire("fiche.ecrite", res["id"], action=res["action"], etagere=etagere)
        return res

    def prouver_noter(c, res):
        r = db.lire("SELECT (SELECT COUNT(*) FROM passages p WHERE p.fiche_id=f.id) AS n FROM fiches f WHERE f.id=? AND f.societe=? AND f.retire_le IS NULL", (res["id"], soc()))
        return bool(r) and r[0]["n"] >= 1

    def defaire_noter(c, res):
        fid, act = res["id"], res["action"]
        with db.transaction() as cx:
            if act == "cree":
                for t in ("passages", "attestations", "versions", "journal"):
                    cx.execute("DELETE FROM %s WHERE fiche_id=?" % t, (fid,))
                cx.execute("DELETE FROM fiches WHERE id=?", (fid,))
            elif act == "rafraichi":
                cx.execute("UPDATE fiches SET lu_le=? WHERE id=?", (res["avant_lu_le"], fid))
            elif act == "doublon":
                if res.get("attestation"):
                    cx.execute("DELETE FROM attestations WHERE fiche_id=? AND source=?", (fid, res["attestation"]))
                cx.execute("UPDATE fiches SET etat=?, lu_le=?, verifie_par=?, verifie_le=? WHERE id=?", (res["avant_etat"], res["avant_lu_le"], res["avant_verifie_par"], res["avant_verifie_le"], fid))
            elif act == "version":
                v = cx.execute("SELECT * FROM versions WHERE id=? AND fiche_id=?", (res["version_gardee"], fid)).fetchone()
                if v is None:
                    raise ValueError("version gardée introuvable")
                a = res["avant"]
                cx.execute("UPDATE fiches SET titre=?, corps=?, empreinte=?, lu_le=?, version=?, etat=?, verifie_par=?, verifie_le=?, maj=?, auteur=? WHERE id=?",
                           (v["titre"], v["corps"], v["empreinte"], v["lu_le"], v["numero"], a["etat"], a["verifie_par"], a["verifie_le"], a["maj"], a["auteur"], fid))
                cx.execute("DELETE FROM versions WHERE id=?", (res["version_gardee"],))
                reecrire_passages(cx, fid, v["titre"], v["corps"])

    # ------------------------------------------------------------------ gestes d'utilisateur
    def verifier(c, ref="", source="", confiance=None):
        """Une fiche (quarantaine ou bloquée) devient vérifiée ; ou un domaine devient une source autorisée (sa confiance monte, ses fiches ne sont PAS vérifiées pour autant)."""
        if bool(ref) == bool(source):
            raise ValueError("une fiche (ref) ou une source (domaine), pas les deux ni aucune")
        if source:
            dom = str(source).strip().lower()
            avant = source_de(dom)
            conf = CONFIANCE["autorisee"] if confiance in (None, "") else max(0.0, min(1.0, float(confiance)))
            with db.transaction() as cx:
                cx.execute("INSERT INTO sources(societe, domaine, statut, confiance, maj, par) VALUES(?,?,?,?,?,?) ON CONFLICT(societe, domaine) DO UPDATE SET statut='autorisee', confiance=?, maj=?, par=?",
                           (soc(), dom, "autorisee", conf, maintenant(), qui(), conf, maintenant(), qui()))
                trace(cx, None, "source_autorisee", dom)
            return {"source": dom, "statut": "autorisee", "confiance": conf, "avant": {"statut": avant["statut"], "confiance": avant["confiance"], "existait": avant["maj"] > 0}}
        f = fiche_de(ref)
        if etat_effectif(f["etat"], f["lu_le"], maintenant(), jours()) == "perime":
            raise ValueError("fiche périmée : Amizo doit la relire avant qu'on la vérifie")
        if f["etat"] == "verifie":
            raise ValueError("fiche déjà vérifiée")
        if f["etagere"] == "externe" and source_de(f["domaine"])["statut"] == "bloquee":
            raise ValueError("la source %s est bloquée : l'autoriser d'abord" % f["domaine"])
        with db.transaction() as cx:
            cx.execute("UPDATE fiches SET etat='verifie', verifie_par=?, verifie_le=?, motif='', maj=? WHERE id=?", (qui(), maintenant(), maintenant(), f["id"]))
            trace(cx, f["id"], "verifiee")
        dire("fiche.verifiee", f["id"], par=qui())
        return {"ref": ref_dite(f["id"]), "etat": "verifie", "avant": {"etat": f["etat"], "verifie_par": f["verifie_par"], "verifie_le": f["verifie_le"], "motif": f["motif"]}}

    def bloquer(c, ref="", source="", motif=""):
        """Une fiche, ou un domaine entier : sa confiance tombe à zéro, ses fiches se bloquent, plus rien n'en entre."""
        if bool(ref) == bool(source):
            raise ValueError("une fiche (ref) ou une source (domaine), pas les deux ni aucune")
        motif = " ".join(str(motif or "").split())[:300]
        if not motif:
            raise ValueError("dis pourquoi (motif)")
        dom, avant_s = None, None
        with db.transaction() as cx:
            if source:
                dom = str(source).strip().lower()
                avant_s = source_de(dom)
                cx.execute("INSERT INTO sources(societe, domaine, statut, confiance, note, maj, par) VALUES(?,?,?,?,?,?,?) ON CONFLICT(societe, domaine) DO UPDATE SET statut='bloquee', confiance=0, note=?, maj=?, par=?",
                           (soc(), dom, "bloquee", 0.0, motif, maintenant(), qui(), motif, maintenant(), qui()))
                cibles = [tuple(r) for r in cx.execute("SELECT id, etat, verifie_par, verifie_le, motif FROM fiches WHERE societe=? AND domaine=? AND retire_le IS NULL AND etat<>'bloque'", (soc(), dom)).fetchall()]
            else:
                f = fiche_de(ref)
                if f["etat"] == "bloque":
                    raise ValueError("fiche déjà bloquée")
                cibles = [(f["id"], f["etat"], f["verifie_par"], f["verifie_le"], f["motif"])]
            for fid, _, _, _, _ in cibles:
                cx.execute("UPDATE fiches SET etat='bloque', motif=?, maj=? WHERE id=?", (motif, maintenant(), fid))
                trace(cx, fid, "bloquee", motif)
            trace(cx, None, "source_bloquee" if source else "fiche_bloquee", dom or ref)
        for x in cibles:
            dire("fiche.bloquee", x[0], par=qui())
        res = {"bloquees": [ref_dite(x[0]) for x in cibles], "avant": [list(x) for x in cibles]}
        if source:
            res.update({"source": dom, "avant_source": {"statut": avant_s["statut"], "confiance": avant_s["confiance"], "note": avant_s["note"], "existait": avant_s["maj"] > 0}})
        return res

    def retirer(c, ref="", motif=""):
        """Sort la fiche de la bibliothèque (plus de recherche, plus de passages) ; son texte et ses versions restent, donc le retour est entier."""
        f = fiche_de(ref)
        with db.transaction() as cx:
            cx.execute("UPDATE fiches SET retire_le=?, motif=?, maj=? WHERE id=?", (maintenant(), " ".join(str(motif or "").split())[:300], maintenant(), f["id"]))
            cx.execute("DELETE FROM passages WHERE fiche_id=?", (f["id"],))
            trace(cx, f["id"], "retiree", motif)
        dire("fiche.retiree", f["id"], par=qui())
        return {"ref": ref_dite(f["id"]), "retiree": True, "motif_avant": f["motif"]}

    def prouver_verifier(c, res):
        if "source" in res:
            return db.lire("SELECT statut FROM sources WHERE societe=? AND domaine=?", (soc(), res["source"]))[0]["statut"] == "autorisee"
        return db.lire("SELECT etat FROM fiches WHERE id=? AND societe=?", (int(res["ref"][2:]), soc()))[0]["etat"] == "verifie"

    def restaurer_source(cx, dom, a):
        if a["existait"]:
            cx.execute("UPDATE sources SET statut=?, confiance=?, note=? WHERE societe=? AND domaine=?", (a["statut"], a["confiance"], a.get("note", ""), soc(), dom))
        else:
            cx.execute("DELETE FROM sources WHERE societe=? AND domaine=?", (soc(), dom))

    def defaire_verifier(c, res):
        with db.transaction() as cx:
            if "source" in res:
                restaurer_source(cx, res["source"], res["avant"])
            else:
                a = res["avant"]
                cx.execute("UPDATE fiches SET etat=?, verifie_par=?, verifie_le=?, motif=? WHERE id=? AND societe=?", (a["etat"], a["verifie_par"], a["verifie_le"], a["motif"], int(res["ref"][2:]), soc()))

    def prouver_bloquer(c, res):
        return all(db.lire("SELECT etat FROM fiches WHERE id=? AND societe=?", (int(r[2:]), soc()))[0]["etat"] == "bloque" for r in res["bloquees"])

    def defaire_bloquer(c, res):
        with db.transaction() as cx:
            for fid, etat, vp, vl, mo in res["avant"]:
                cx.execute("UPDATE fiches SET etat=?, verifie_par=?, verifie_le=?, motif=? WHERE id=? AND societe=?", (etat, vp, vl, mo, fid, soc()))
            if "source" in res:
                restaurer_source(cx, res["source"], res["avant_source"])

    def prouver_retirer(c, res):
        fid = int(res["ref"][2:])
        r = db.lire("SELECT retire_le FROM fiches WHERE id=? AND societe=?", (fid, soc()))
        return bool(r) and r[0]["retire_le"] is not None and not db.lire("SELECT 1 FROM passages WHERE fiche_id=?", (fid,))

    def defaire_retirer(c, res):
        fid = int(res["ref"][2:])
        f = fiche_de(res["ref"], avec_retirees=True)
        with db.transaction() as cx:
            cx.execute("UPDATE fiches SET retire_le=NULL, motif=? WHERE id=?", (res.get("motif_avant", ""), fid))
            reecrire_passages(cx, fid, f["titre"], f["corps"])

    # ------------------------------------------------------------------ lire
    def chercher(c, q="", etagere="", etats=None, limite=10):
        """Plein texte classé : pertinence (bm25), fraîcheur, confiance de la source. Par défaut seules les fiches vérifiées répondent ; quarantaine et périmées sur demande ; une fiche bloquée jamais."""
        mots = requete_fts(q)
        if not mots:
            raise ValueError("une question est obligatoire")
        if isinstance(etats, str):
            etats = [e for e in re.split(r"[,\s]+", etats) if e]
        etats = list(etats or ["verifie"])
        if any(e not in ETATS_LUS for e in etats):
            raise ValueError("états lisibles : %s (une fiche bloquée ne se cherche pas)" % ", ".join(ETATS_LUS))
        if etagere and etagere not in ETAGERES:
            raise ValueError("étagère : interne ou externe")
        limite = max(1, min(int(limite or 10), 50))
        sql = ("SELECT p.id AS pid, p.position, p.texte, f.*, bm25(passages_fts, 3.0, 1.0) AS r FROM passages_fts JOIN passages p ON p.id = passages_fts.rowid "
               "JOIN fiches f ON f.id = p.fiche_id WHERE passages_fts MATCH ? AND f.societe=? AND f.retire_le IS NULL AND f.etat<>'bloque'"
               + (" AND f.etagere=?" if etagere else "") + " ORDER BY r LIMIT 120")
        lignes = db.lire(sql, (mots, soc()) + ((etagere,) if etagere else ()))
        now, j = maintenant(), jours()
        meilleurs = {}
        for r in lignes:
            if etat_effectif(r["etat"], r["lu_le"], now, j) in etats and (r["id"] not in meilleurs or r["r"] < meilleurs[r["id"]]["r"]):
                meilleurs[r["id"]] = r
        if not meilleurs:
            return {"resultats": [], "total": 0, "mode": "plein_texte"}
        pic = max(-m["r"] for m in meilleurs.values())
        pic = pic if pic > 0 else 1.0
        sources_ = {s["domaine"]: s for s in db.lire("SELECT * FROM sources WHERE societe=?", (soc(),))}
        out = []
        for m in meilleurs.values():
            conf = 1.0 if m["etagere"] == "interne" else float(sources_.get(m["domaine"], {"confiance": CONFIANCE["inconnue"]})["confiance"]) * (1.0 if m["etat"] == "verifie" else 0.5)
            age = (now - m["lu_le"]) / 86400.0
            pert = max(0.0, -m["r"]) / pic
            v = vue(m, now)
            v.update({"passage": {"position": m["position"], "texte": m["texte"][:600]}, "pertinence": round(pert, 4), "confiance": round(conf, 3),
                      "fraicheur": round(0.5 ** (max(0.0, age) / j), 3), "score": note_de(pert, age, conf, j), "fiable": v["etat"] == "verifie"})
            out.append(v)
        out.sort(key=lambda x: -x["score"])
        return {"resultats": out[:limite], "total": len(out), "mode": "plein_texte"}

    def fiche(c, ref=""):
        f = fiche_de(ref)
        v = vue(f)
        v["corps"] = f["corps"]
        v["passages"] = [{"position": p["position"], "texte": p["texte"]} for p in db.lire("SELECT position, texte FROM passages WHERE fiche_id=? ORDER BY position", (f["id"],))]
        v["attestations"] = db.lire("SELECT source, domaine, lu_le FROM attestations WHERE fiche_id=? ORDER BY lu_le", (f["id"],))
        v["versions"] = db.lire("SELECT numero, titre, lu_le, auteur, ts FROM versions WHERE fiche_id=? ORDER BY numero DESC", (f["id"],))
        s = source_de(f["domaine"]) if f["domaine"] else None
        v["source_info"] = {k: s[k] for k in ("statut", "confiance", "note")} if s else None
        return v

    def etagere(c, nom="", etat="", limite=50, decalage=0):
        if nom and nom not in ETAGERES:
            raise ValueError("étagère : interne ou externe")
        if etat and etat not in ETATS_LUS + ("bloque",):
            raise ValueError("état : quarantaine, verifie, perime ou bloque")
        now, j = maintenant(), jours()
        toutes = db.lire("SELECT * FROM fiches WHERE societe=? AND retire_le IS NULL" + (" AND etagere=?" if nom else "") + " ORDER BY lu_le DESC, id DESC", (soc(),) + ((nom,) if nom else ()))
        comptes = {e: {s: 0 for s in ("quarantaine", "verifie", "perime", "bloque")} for e in ETAGERES}
        gardees = []
        for f in toutes:
            eff = etat_effectif(f["etat"], f["lu_le"], now, j)
            comptes[f["etagere"]][eff] += 1
            if not etat or eff == etat:
                gardees.append(vue(f, now))
        limite, decalage = max(1, min(int(limite or 50), 200)), max(0, int(decalage or 0))
        return {"comptes": comptes, "total": len(gardees), "fiches": gardees[decalage:decalage + limite],
                "index": {"passages": db.lire("SELECT COUNT(*) AS n FROM passages")[0]["n"], "recherche": "plein_texte",
                          "vecteurs": {"modele": meta("modele_vecteurs"), "calcules": db.lire("SELECT COUNT(*) AS n FROM vecteurs")[0]["n"], "actif": False, "pret": vecteurs_prets()}}}

    def sources(c, statut="", limite=100):
        if statut and statut not in CONFIANCE:
            raise ValueError("statut : inconnue, autorisee ou bloquee")
        lignes = db.lire("SELECT * FROM sources WHERE societe=?" + (" AND statut=?" if statut else "") + " ORDER BY domaine LIMIT ?",
                         (soc(),) + ((statut,) if statut else ()) + (max(1, min(int(limite or 100), 500)),))
        for s in lignes:
            s["fiches"] = db.lire("SELECT COUNT(*) AS n FROM fiches WHERE societe=? AND domaine=? AND retire_le IS NULL", (soc(), s["domaine"]))[0]["n"]
        return {"sources": lignes, "total": len(lignes)}

    # ------------------------------------------------------------------ vecteurs (prévus, pas actifs)
    def meta(cle):
        r = db.lire("SELECT valeur FROM meta WHERE cle=?", (cle,))
        return r[0]["valeur"] if r else ""

    def vecteurs_prets():
        f = _VECTEURS["fournisseur"]
        try:
            return bool(f is not None and f.nom == meta("modele_vecteurs") and f.pret())
        except Exception:
            return False

    def rattraper_vecteurs(lot=32):
        """Calcule les vecteurs des passages qui n'en ont pas, SEULEMENT quand le modèle est prêt (le premier usage le charge ; avant, rien ne se calcule)."""
        if not vecteurs_prets():
            return 0
        f, fait = _VECTEURS["fournisseur"], 0
        while True:
            reste = db.lire("SELECT p.id, p.texte FROM passages p LEFT JOIN vecteurs v ON v.passage_id=p.id WHERE v.passage_id IS NULL LIMIT ?", (int(lot),))
            if not reste:
                return fait
            vecs = f.encoder([r["texte"] for r in reste])
            with db.transaction() as cx:
                for r, v in zip(reste, vecs):
                    cx.execute("INSERT OR REPLACE INTO vecteurs(passage_id, modele, dim, vecteur, ts) VALUES(?,?,?,?,?)", (r["id"], f.nom, len(v), array.array("f", v).tobytes(), maintenant()))
            fait += len(reste)

    brancher.rattraper_vecteurs = rattraper_vecteurs   # le moteur qui rattrape l'appellera quand le service d'encodage dira « prêt »

    # ------------------------------------------------------------------ inscription
    for cid, f in (("chercher", chercher), ("fiche", fiche), ("etagere", etagere), ("sources", sources)):
        ctx.implementer(cid, f)
    ctx.implementer("noter", noter, prouver_noter, defaire_noter, simuler=lambda x, source="", **_: "noterait la fiche de %s (quarantaine si elle vient du web)" % source)
    ctx.implementer("verifier", verifier, prouver_verifier, defaire_verifier, simuler=lambda x, ref="", source="", **_: "vérifierait %s" % (ref or source))
    ctx.implementer("bloquer", bloquer, prouver_bloquer, defaire_bloquer, simuler=lambda x, ref="", source="", **_: "bloquerait %s" % (ref or source))
    ctx.implementer("retirer", retirer, prouver_retirer, defaire_retirer, simuler=lambda x, ref="", **_: "retirerait la fiche %s de la bibliothèque" % ref)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : empreinte_de, domaine_de, etat_effectif, requete_fts, decouper, note_de …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
