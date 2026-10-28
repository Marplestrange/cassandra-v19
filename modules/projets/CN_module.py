# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les projets
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : projets
# ZONE       : CN
# VERSION CN : 0.1.1  #1c82d8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les projets.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=1c82d8 ▼▼▼
"""Les projets.

Porté de la V18 (`pj_*`, `projet_*`), avec ses leçons :
  - UN projet appartient à UN compte ; les autres y entrent par invitation, avec un rôle. Chaque porte vérifie le rôle (un numéro forgé dans une requête
    rendait la fiche de quelqu'un d'autre) ; l'administrateur n'a pas accès aux projets d'autrui (administrer n'est pas voir) ;
  - un projet archivé n'accepte plus d'écriture, mais sa fiche reste modifiable (pour le rouvrir) ;
  - créer depuis un modèle pose ses phases, sans lien qui subsiste : changer le modèle plus tard ne réécrit pas les projets passés ;
  - le PLAN DE RÉFÉRENCE se fige explicitement et l'ancien part au journal : sans cette trace, un projet qui glisse par petits décalages successifs paraît
    toujours à l'heure, parce que chaque replanification efface la précédente ;
  - une date fausse dans un plan est pire qu'une date absente : seules les dates ISO passent ;
  - supprimer = corbeille (rien n'est effacé : phases, jalons, décisions, équipe restent), restaurable sous le même numéro ; les TÂCHES ne sont pas au projet,
    elles sont à la personne : elles ne sont jamais emportées ;
  - le journal est une colonne de lignes datées, écrites par la personne, par Itare ou par le moteur ; ce qui n'a pas de date est rendu tel quel ;
  - l'avancement est pondéré par la CHARGE (trois broutilles faites ne valent pas la moitié d'un projet dont le gros n'a pas commencé) ; sans charge, chaque ligne pèse un.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime

MODELES = {
    "livre": {"nom": "Livre", "ic": "\U0001F4D6", "phases": ["Écriture", "Relecture", "Édition"]},
    "client": {"nom": "Prestation client", "ic": "\U0001F91D", "phases": ["Cadrage", "Conception", "Réalisation", "Recette", "Livraison"]},
    "travaux": {"nom": "Travaux / projet", "ic": "\U0001F9F1", "phases": ["Étude", "Devis", "Commande", "Exécution", "Réception"]},
    "infra": {"nom": "Infrastructure", "ic": "\U0001F5A5", "phases": ["Étude", "Préparation", "Bascule", "Vérification", "Clôture"]},
    "creation": {"nom": "Création", "ic": "\U0001F3A8", "phases": ["Idée", "Écriture", "Production", "Diffusion"]},
    "event": {"nom": "Événement", "ic": "\U0001F3AA", "phases": ["Cadrage", "Logistique", "Communication", "Jour J", "Bilan"]},
    "vide": {"nom": "Vierge", "ic": "▫️", "phases": ["À définir"]},
}
ETATS_PHASE = ("À venir", "En cours", "Terminée", "Suspendue")
ETATS_JALON = ("prevu", "tenu", "manque", "reporte")
ETATS_DECISION = ("ouverte", "tranchee", "abandonnee")
PRIORITES = ("Basse", "Normale", "Haute", "Critique")
STATUTS = ("actif", "en pause", "terminé")
GENRES = ("perso", "infra", "mixte")
ROLES = ("lecteur", "auteur", "coproprietaire")
NIVEAU = {"lecteur": 1, "auteur": 2, "coproprietaire": 3, "proprietaire": 4}
GESTES = {"lire": 1, "ecrire": 2, "fiche": 3, "equipe": 3, "supprimer": 4}
GESTE_DIT = {"lire": "voir ce projet", "ecrire": "écrire dans ce projet", "fiche": "modifier la fiche du projet", "equipe": "gérer l'équipe du projet", "supprimer": "supprimer le projet"}
ROLE_DIT = {"lecteur": "lecteur", "auteur": "auteur", "coproprietaire": "co-propriétaire", "proprietaire": "propriétaire", "": "aucun"}
CHAMPS_FICHE = ("nom", "statut", "genre", "modele", "priorite", "debut", "fin", "resume", "objectif", "perimetre_in", "perimetre_out", "reussite", "domaine", "serveur")
TAILLES = {"nom": 160, "resume": 2000, "objectif": 2000, "perimetre_in": 4000, "perimetre_out": 4000, "reussite": 4000, "domaine": 200, "serveur": 200}
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ENFANTS = {
    "phase": ("phases", ("nom", "ordre", "debut", "fin", "etat", "charge")),
    "jalon": ("jalons", ("date", "nom", "etat", "tenu_le")),
    "decision": ("decisions", ("question", "reponse", "raison", "etat", "seuil", "ferme", "auteur")),
}


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


def date_ok(v):
    """Une date ISO, ou ''. Jamais une approximation. Le calcul est un POINT D'ÉVOLUTION : points/EC_date_ok.py."""
    return _appeler_point("date_ok", {"v": v})["valeur"]


def journal(notes):
    sortie = []
    for l in [x.strip() for x in str(notes or "").replace("\r", "").split("\n") if x.strip()]:
        m = re.match(r"^\[(\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?)\]\s*(.*)$", l)
        sortie.append({"quand": m.group(1) if m else "", "texte": (m.group(2) if m else l).strip()})
    sortie.sort(key=lambda j: j["quand"])
    return sortie


def jours_entre(a, b):
    try:
        return (datetime.strptime(b, "%Y-%m-%d") - datetime.strptime(a, "%Y-%m-%d")).days
    except ValueError:
        return 0


def brancher(ctx):
    global _point
    _point = ctx.point
    db = ctx.stockage

    def compte_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("un projet est celui d'un compte : aucun compte n'agit")
        return c

    def comptes_connus():
        r = ctx.executer_lecture("comptes.lister")
        return None if r is None else {x["compte"] for x in r.get("comptes", [])}

    # ------------------------------------------------------------------ rôles
    def entete(pid):
        try:
            r = db.lire("SELECT * FROM projets WHERE id=?", (int(pid),))
        except (TypeError, ValueError):
            return None
        return r[0] if r else None

    def role_de(pid, compte):
        p = entete(pid)
        if p is None:
            return ""
        if p["compte"] == compte:
            return "proprietaire"
        m = db.lire("SELECT role FROM membres WHERE projet_id=? AND compte=? AND etat='actif'", (p["id"], compte))
        return m[0]["role"] if m and m[0]["role"] in NIVEAU else ""

    def peut(pid, geste, compte):
        p = entete(pid)
        if p is None:
            return False
        ok = NIVEAU.get(role_de(pid, compte), 0) >= GESTES.get(geste, 99)
        return False if (ok and geste == "ecrire" and p["archive"]) else ok

    def exiger(pid, geste, compte, hors_corbeille=True):
        """L'en-tête SI le compte y a droit, sinon une raison dite : jamais d'indice sur l'existence d'un projet qu'on ne voit pas."""
        p = entete(pid)
        if p is None or NIVEAU.get(role_de(pid, compte), 0) < GESTES["lire"] or (hors_corbeille and p["supprime_at"] is not None and geste != "supprimer"):
            raise ValueError("projet introuvable")
        if not peut(pid, geste, compte):
            if geste == "ecrire" and p["archive"] and NIVEAU.get(role_de(pid, compte), 0) >= GESTES["ecrire"]:
                raise ValueError("projet archivé : rouvrez-le pour y écrire")
            raise ValueError("ton rôle (%s) ne permet pas de %s" % (ROLE_DIT.get(role_de(pid, compte), "aucun"), GESTE_DIT.get(geste, geste)))
        return p

    # ------------------------------------------------------------------ instantanés
    def instantane(pid):
        return {"projet": dict(entete(pid)),
                "phases": [dict(r) for r in db.lire("SELECT * FROM phases WHERE projet_id=?", (pid,))],
                "jalons": [dict(r) for r in db.lire("SELECT * FROM jalons WHERE projet_id=?", (pid,))],
                "decisions": [dict(r) for r in db.lire("SELECT * FROM decisions WHERE projet_id=?", (pid,))],
                "membres": [dict(r) for r in db.lire("SELECT * FROM membres WHERE projet_id=?", (pid,))]}

    def reposer(snap):
        p = snap["projet"]
        with db.transaction() as cx:
            cx.execute("DELETE FROM projets WHERE id=?", (p["id"],))
            for t in ("phases", "jalons", "decisions", "membres"):
                cx.execute("DELETE FROM %s WHERE projet_id=?" % t, (p["id"],))
            cols = list(p)
            cx.execute("INSERT INTO projets(%s) VALUES (%s)" % (",".join(cols), ",".join("?" * len(cols))), [p[c] for c in cols])
            for t in ("phases", "jalons", "decisions", "membres"):
                for l in snap[t]:
                    k = list(l)
                    cx.execute("INSERT INTO %s(%s) VALUES (%s)" % (t, ",".join(k), ",".join("?" * len(k))), [l[c] for c in k])

    def effacer(pid):
        with db.transaction() as cx:
            for t in ("phases", "jalons", "decisions", "membres"):
                cx.execute("DELETE FROM %s WHERE projet_id=?" % t, (pid,))
            cx.execute("DELETE FROM projets WHERE id=?", (pid,))

    # ------------------------------------------------------------------ lectures
    def modeles(c):
        return {"modeles": [dict(v, cle=k) for k, v in MODELES.items()]}

    def visibles(compte, archives=False):
        return db.lire("SELECT p.*, (CASE WHEN p.compte=? THEN 'proprietaire' ELSE m.role END) AS mon_role, "
                       "(SELECT COUNT(*) FROM phases WHERE projet_id=p.id) AS n_phases, (SELECT COUNT(*) FROM phases WHERE projet_id=p.id AND etat='Terminée') AS n_phases_finies, "
                       "(SELECT COUNT(*) FROM jalons WHERE projet_id=p.id) AS n_jalons, (SELECT COUNT(*) FROM jalons WHERE projet_id=p.id AND etat='prevu' AND date<>'' AND date<?) AS n_jalons_depasses, "
                       "(SELECT COUNT(*) FROM decisions WHERE projet_id=p.id AND etat='ouverte') AS n_decisions_ouvertes "
                       "FROM projets p LEFT JOIN membres m ON m.projet_id=p.id AND m.compte=? AND m.etat='actif' "
                       "WHERE p.supprime_at IS NULL AND p.archive=? AND (p.compte=? OR m.compte IS NOT NULL) ORDER BY (p.statut='terminé'), p.maj DESC",
                       (compte, time.strftime("%Y-%m-%d"), compte, 1 if archives else 0, compte))

    def lister(c, archives=False):
        compte = compte_agit()
        return {"projets": [{k: v for k, v in dict(r).items() if k not in ("notes",)} for r in visibles(compte, bool(archives))]}

    def trouver(c, nom=""):
        compte = compte_agit()
        n = str(nom or "").strip().lower()
        if not n:
            raise ValueError("un nom est attendu")
        tous = visibles(compte) + visibles(compte, True)
        exact = [p for p in tous if p["nom"].strip().lower() == n]
        partiel = [p for p in tous if n in p["nom"].strip().lower()]
        trouve = (exact or partiel or [None])[0]
        return {"projet": None if trouve is None else {"id": trouve["id"], "nom": trouve["nom"], "statut": trouve["statut"], "mon_role": trouve["mon_role"]}, "candidats": len(exact or partiel)}

    def avancement(phases):
        """Pondéré par la CHARGE ; sans charge, chaque phase pèse un. 100 si toutes sont terminées."""
        poids = lambda p: max(int(p["charge"] or 0), 1)
        total = sum(poids(p) for p in phases)
        fait = sum(poids(p) for p in phases if p["etat"] == "Terminée")
        return {"global": int(round(fait * 100.0 / total)) if total else 0, "fait": fait, "total": total, "mesure": "phases" if total else "",
                "detail": ("%d sur %d (phases, pondérées par leur charge)" % (fait, total)) if total else ""}

    def glissement(p, phases, jalons):
        """glissement. Le calcul est un POINT D'ÉVOLUTION : points/EC_glissement.py."""
        return ctx.point("glissement", {"p": p, "phases": phases, "jalons": jalons})["valeur"]

    def voir(c, id=0):
        compte = compte_agit()
        p0 = entete(id)
        p = exiger(id, "lire", compte, hors_corbeille=not (p0 is not None and p0["compte"] == compte))       # la corbeille n'est visible que de son propriétaire
        phases = [dict(r) for r in db.lire("SELECT * FROM phases WHERE projet_id=? ORDER BY ordre, id", (p["id"],))]
        jalons = [dict(r) for r in db.lire("SELECT * FROM jalons WHERE projet_id=? ORDER BY CASE WHEN date='' THEN 1 ELSE 0 END, date, id", (p["id"],))]
        aujourdhui = time.strftime("%Y-%m-%d")
        for j in jalons:
            j["depasse"] = j["etat"] == "prevu" and bool(j["date"]) and j["date"] < aujourdhui
        fiche = dict(p)
        fiche["journal"] = journal(p["notes"])
        fiche.pop("notes", None)
        fiche["mon_role"] = role_de(p["id"], compte)
        fiche["corbeille"] = p["supprime_at"] is not None
        return {"projet": fiche, "phases": phases, "jalons": jalons, "decisions": [dict(r) for r in db.lire("SELECT * FROM decisions WHERE projet_id=? ORDER BY id", (p["id"],))],
                "avancement": avancement(phases), "glissement": glissement(p, phases, jalons), "equipe": equipe_de(p)}

    # ------------------------------------------------------------------ le contexte d'une fiche, et le portefeuille
    def lignes_de(texte):
        return [re.sub(r"^\s*[-*•]\s*", "", l).strip() for l in str(texte or "").splitlines() if l.strip()]

    def jours_depuis(quand):
        try:
            return (datetime.now() - datetime.strptime(str(quand)[:10], "%Y-%m-%d")).days
        except Exception:
            return None

    def sig_retard(x):
        tk = [t for t in x["taches"] if t["statut"] not in ("fait", "abandonnee") and t.get("echeance")]
        if not tk:
            return None, "aucune tâche datée", 0
        tard = [t for t in tk if str(t["echeance"]) < datetime.now().strftime("%Y-%m-%d %H:%M")]
        if not tard:
            return "ok", "%d tâche(s) datée(s), aucune en retard" % len(tk), 0
        return "dgr", "%d en retard sur %d, la plus ancienne du %s" % (len(tard), len(tk), min(str(t["echeance"])[:10] for t in tard)), -min(30, 7 * len(tard))

    def sig_attente(x):
        att = [t for t in x["taches"] if t["statut"] == "en attente"]
        if not att:
            return "ok", "aucune attente de tiers", 0
        return "warn", "%d tâche(s) suspendue(s) à quelqu'un d'autre" % len(att), -min(20, 5 * len(att))

    def sig_fraicheur(x):
        """Le dernier mouvement : la dernière ligne datée du journal, ou la mise à jour de l'en-tête — la plus récente des deux."""
        ts = [j["quand"] for j in x["journal"] if j.get("quand")]
        if x["projet"].get("maj"):
            ts.append(datetime.fromtimestamp(x["projet"]["maj"]).strftime("%Y-%m-%d %H:%M"))
        if not ts:
            return None, "aucun mouvement daté", 0
        d = jours_depuis(max(ts))
        if d is None:
            return None, "date du dernier mouvement illisible", 0
        if d <= 7:
            return "ok", "dernier mouvement il y a %d jour(s)" % d, 5
        if d <= 21:
            return "warn", "rien depuis %d jours" % d, -8
        return "dgr", "endormi depuis %d jours" % d, -18

    def sig_jalons(x):
        if not x["jalons"]:
            return None, "aucune étape posée, rien à tenir", 0
        passes = [j for j in x["jalons"] if j["etat"] in ("tenu", "manque")]
        if not passes:
            return None, "aucune étape encore échue", 0
        tenus = len([j for j in passes if j["etat"] == "tenu"])
        return ("ok" if tenus == len(passes) else "warn"), "%d sur %d livrés à la date prévue" % (tenus, len(passes)), 6 if tenus == len(passes) else -6

    def sig_derive(x):
        ec = []
        for ph in x["phases"]:
            if ph.get("fin") and ph.get("ref_fin"):
                try:
                    ec.append((datetime.strptime(ph["fin"][:10], "%Y-%m-%d") - datetime.strptime(ph["ref_fin"][:10], "%Y-%m-%d")).days)
                except ValueError:
                    pass
        if not ec:
            return None, "aucun plan de référence figé — rien à comparer", 0
        m = max(ec)
        if m <= 0:
            return "ok", "conforme au plan de référence", 4
        return ("warn" if m <= 14 else "dgr"), "la fin de phase la plus décalée glisse de %d jour(s)" % m, -min(20, m)

    SANTE = (("Tâches en retard", sig_retard), ("Attente de tiers", sig_attente), ("Fraîcheur", sig_fraicheur), ("Étapes tenues", sig_jalons), ("Dérive au plan de référence", sig_derive))

    def sante_de(x):
        """Le score ET sa composition. Un signal qui n'avait rien à regarder est rendu tel quel (« muet ») : c'est l'information la plus honnête de la liste, et celle qu'un score seul efface."""
        score, sig, evalues = 100, [], 0
        for nom, fn in SANTE:
            try:
                niveau, detail, poids = fn(x)
            except Exception as ex:
                niveau, detail, poids = None, "signal indisponible : %s" % str(ex)[:60], 0
            if niveau is None:
                sig.append({"nom": nom, "niveau": "muet", "detail": detail, "poids": None})
                continue
            evalues += 1
            score += poids
            sig.append({"nom": nom, "niveau": niveau, "detail": detail, "poids": poids})
        score = max(0, min(100, score))
        return {"score": score, "signaux": sig, "evalues": evalues, "muets": len(SANTE) - evalues,
                "verdict": "En bonne santé" if score >= 80 else "À surveiller" if score >= 60 else "Fragile"}

    def contexte(c, id=0):
        """L'appel unique dont la fiche a besoin : en-tête, plan, étapes, décisions, tâches, rendez-vous, journal, santé, équipe. Chaque source est isolée : une qui échoue ne vide pas la fiche."""
        v = voir(c, id)
        p = v["projet"]
        try:
            taches = (ctx.executer_lecture("taches.lister", projet_id=p["id"], inclure_faites=True, limite=400) or {}).get("taches", [])
        except Exception:
            taches = []
        try:
            evs = [e for e in (ctx.executer_lecture("agenda.evenements") or {}).get("evenements", []) if e.get("projet_id") == p["id"]]
        except Exception:
            evs = []
        mod = MODELES.get(p["modele"] or "vide", MODELES["vide"])
        x = {"projet": p, "phases": v["phases"], "jalons": v["jalons"], "decisions": v["decisions"], "taches": taches, "journal": p["journal"]}
        ouvertes = [t for t in taches if t["statut"] not in ("fait", "abandonnee")]
        maintenant = datetime.now().strftime("%Y-%m-%d %H:%M")
        proches = [j for j in v["jalons"] if j["etat"] in ("", "prevu", None)]
        membres = [m for m in v["equipe"]["membres"] if m.get("etat") == "actif"]
        return {"projet": p, "modele": dict(mod, cle=p["modele"] or "vide"), "role": p["mon_role"], "equipe": membres, "n_membres": len(membres),
                "phases": v["phases"], "jalons": v["jalons"], "decisions": v["decisions"], "taches": taches, "avancement": v["avancement"], "glissement": v["glissement"],
                "evenements": evs, "perimetre_in": lignes_de(p["perimetre_in"]), "perimetre_out": lignes_de(p["perimetre_out"]), "reussite": lignes_de(p["reussite"]),
                "journal": p["journal"], "sante": sante_de(x),
                "comptes": {"taches_ouvertes": len(ouvertes), "taches_total": len(taches), "attente": len([t for t in ouvertes if t["statut"] == "en attente"]),
                            "retard": len([t for t in ouvertes if t.get("echeance") and str(t["echeance"]) < maintenant]), "jalons": len(v["jalons"]),
                            "jalons_proches": len(proches), "decisions_ouvertes": len([d for d in v["decisions"] if d.get("etat") == "ouverte"])}}

    def portefeuille(c, archives=False):
        """Le portefeuille du compte, avec la santé de chacun : de quoi trier par ce qui réclame un geste plutôt que par ordre alphabétique."""
        out = []
        for ligne in lister(c, archives=archives)["projets"]:
            try:
                x = contexte(c, ligne["id"])
            except Exception:
                continue
            p = x["projet"]
            out.append({"id": p["id"], "nom": p["nom"], "modele": p["modele"], "ic": x["modele"]["ic"], "modele_nom": x["modele"]["nom"], "statut": p["statut"], "priorite": p["priorite"],
                        "debut": p["debut"], "fin": p["fin"], "resume": p["resume"], "domaine": p["domaine"], "serveur": p["serveur"],
                        "avance": x["avancement"]["global"], "avance_mesure": x["avancement"].get("mesure") or "", "avance_detail": x["avancement"].get("detail") or "",
                        "sante": x["sante"]["score"], "verdict": x["sante"]["verdict"], "muets": x["sante"]["muets"], "proprietaire": p["compte"], "role": x["role"],
                        "membres": x["n_membres"], "objectif": (p["objectif"] or "")[:200], "archive": bool(p["archive"])})
        return {"projets": out}

    def equipe_de(p):
        return {"proprietaire": p["compte"], "membres": [dict(r) for r in db.lire("SELECT compte, role, etat, invite_par, ts FROM membres WHERE projet_id=? ORDER BY etat, ts", (p["id"],))]}

    def equipe(c, id=0):
        compte = compte_agit()
        p = exiger(id, "lire", compte)
        e = equipe_de(p)
        e["mon_role"] = role_de(p["id"], compte)
        e["projet"] = p["nom"]
        return e

    def invitations(c):
        compte = compte_agit()
        return {"invitations": [dict(r) for r in db.lire("SELECT m.projet_id AS id, p.nom AS projet, p.compte AS proprietaire, m.role, m.invite_par, m.ts FROM membres m "
                                                        "JOIN projets p ON p.id=m.projet_id WHERE m.compte=? AND m.etat='invite' AND p.supprime_at IS NULL ORDER BY m.ts DESC", (compte,))]}

    def corbeille(c):
        compte = compte_agit()
        return {"projets": [{"id": r["id"], "nom": r["nom"], "supprime_at": r["supprime_at"], "phases": r["n"]}
                            for r in db.lire("SELECT p.id, p.nom, p.supprime_at, (SELECT COUNT(*) FROM phases WHERE projet_id=p.id) n FROM projets p WHERE p.compte=? AND p.supprime_at IS NOT NULL ORDER BY p.supprime_at DESC", (compte,))]}

    def det_jalons(c):
        auj = time.strftime("%Y-%m-%d")
        return [{"objet": ("projet", "%d:j%d" % (r["pid"], r["jid"])), "compte": r["compte"], "titre": "Jalon dépassé : %s (%s)" % (r["nom"], r["projet"]),
                 "detail": "prévu le %s, ni tenu ni reporté" % r["date"], "niveau": "attention"}
                for r in db.lire("SELECT p.id pid, p.compte, p.nom projet, j.id jid, j.nom, j.date FROM jalons j JOIN projets p ON p.id=j.projet_id "
                                 "WHERE j.etat='prevu' AND j.date<>'' AND j.date<? AND p.archive=0 AND p.supprime_at IS NULL AND p.statut<>'terminé'", (auj,))]

    # ------------------------------------------------------------------ la fiche
    def valeurs_fiche(d):
        v = {}
        for k in CHAMPS_FICHE:
            if d.get(k) is None:
                continue
            x = str(d[k]).strip()
            if k == "statut":
                if x.lower() not in STATUTS:
                    raise ValueError("statut : %s" % " | ".join(STATUTS))
                x = x.lower()
            elif k == "genre":
                if x.lower() not in GENRES:
                    raise ValueError("genre : %s" % " | ".join(GENRES))
                x = x.lower()
            elif k == "modele":
                if x not in MODELES:
                    raise ValueError("modèle : %s" % " | ".join(MODELES))
            elif k == "priorite":
                if x not in PRIORITES:
                    raise ValueError("priorité : %s" % " | ".join(PRIORITES))
            elif k in ("debut", "fin"):
                x = date_ok(x)
            elif k == "domaine":
                x = re.sub(r"^[a-z]+://", "", x.lower()).split("/")[0]
                x = x[4:] if x.startswith("www.") else x
            v[k] = x[:TAILLES.get(k, 200)]
        return v

    def ajouter_ligne(notes, texte):
        return (str(notes or "") + "\n[%s] %s" % (time.strftime("%Y-%m-%d %H:%M"), str(texte).strip()[:500])).strip()

    def poser_phases(cx, pid, cle):
        for i, nom in enumerate(MODELES.get(cle, MODELES["vide"])["phases"]):
            cx.execute("INSERT INTO phases(projet_id, nom, ordre, etat) VALUES (?,?,?,?)", (pid, nom, i, "En cours" if i == 0 else "À venir"))

    def creer(c, nom="", modele="vide", statut="actif", genre="perso", priorite="Normale", debut="", fin="", resume="", objectif="", perimetre_in="", perimetre_out="", reussite="",
              domaine="", serveur=""):
        compte = compte_agit()
        v = valeurs_fiche({"nom": nom, "modele": modele, "statut": statut, "genre": genre, "priorite": priorite, "debut": debut, "fin": fin, "resume": resume, "objectif": objectif,
                           "perimetre_in": perimetre_in, "perimetre_out": perimetre_out, "reussite": reussite, "domaine": domaine, "serveur": serveur})
        if not v.get("nom"):
            raise ValueError("un projet a besoin d'un nom")
        maintenant = time.time()
        notes = "[%s] Projet ouvert — modèle %s" % (time.strftime("%Y-%m-%d %H:%M"), MODELES[v["modele"]]["nom"])
        cols = list(v)
        with db.transaction() as cx:
            cur = cx.execute("INSERT INTO projets(compte, notes, cree, maj, %s) VALUES (?,?,?,?,%s)" % (",".join(cols), ",".join("?" * len(cols))), [compte, notes, maintenant, maintenant] + [v[k] for k in cols])
            pid = cur.lastrowid
            poser_phases(cx, pid, v["modele"])
        c.emettre("projet.cree", objet=("projet", str(pid)), donnees={"id": pid, "modele": v["modele"]})
        return {"id": pid, "compte": compte, "nom": v["nom"], "modele": v["modele"]}

    def prouver_cree(c, res):
        p = entete(res["id"])
        return p is not None and p["nom"] == res["nom"] and db.lire("SELECT COUNT(*) n FROM phases WHERE projet_id=?", (res["id"],))[0]["n"] == len(MODELES[res["modele"]]["phases"])

    def defaire_cree(c, res):
        effacer(res["id"])

    def modifier(c, id=0, **champs):
        compte = compte_agit()
        p = exiger(id, "fiche", compte)
        v = valeurs_fiche(champs)
        inconnus = [k for k in champs if k not in CHAMPS_FICHE and champs[k] is not None]
        if inconnus:
            raise ValueError("champ inconnu : %s" % ", ".join(sorted(inconnus)))
        if "nom" in v and not v["nom"]:
            v.pop("nom")
        avant = {k: p[k] for k in v}
        if v:
            db.ecrire("UPDATE projets SET %s, maj=? WHERE id=?" % ",".join("%s=?" % k for k in v), list(v.values()) + [time.time(), p["id"]])
        c.emettre("projet.modifie", objet=("projet", str(p["id"])), donnees={"id": p["id"], "champs": sorted(v)})
        return {"id": p["id"], "compte": compte, "avant": avant, "apres": v}

    def prouver_modifie(c, res):
        p = entete(res["id"])
        return all(p[k] == v for k, v in res["apres"].items())

    def defaire_modifie(c, res):
        if res["avant"]:
            db.ecrire("UPDATE projets SET %s WHERE id=?" % ",".join("%s=?" % k for k in res["avant"]), list(res["avant"].values()) + [res["id"]])

    def noter(c, id=0, texte=""):
        compte = compte_agit()
        p = exiger(id, "ecrire", compte)
        t = str(texte or "").strip()
        if not t:
            raise ValueError("une note vide n'est pas une note")
        nouveau = ajouter_ligne(p["notes"], t)
        db.ecrire("UPDATE projets SET notes=?, maj=? WHERE id=?", (nouveau, time.time(), p["id"]))
        return {"id": p["id"], "avant": p["notes"], "apres": nouveau}

    def prouver_note(c, res):
        return entete(res["id"])["notes"] == res["apres"]

    def defaire_note(c, res):
        db.ecrire("UPDATE projets SET notes=? WHERE id=?", (res["avant"], res["id"]))

    def archiver(c, id=0, archive=True):
        compte = compte_agit()
        p = exiger(id, "fiche", compte)
        db.ecrire("UPDATE projets SET archive=?, maj=? WHERE id=?", (1 if archive else 0, time.time(), p["id"]))
        return {"id": p["id"], "avant": p["archive"], "archive": 1 if archive else 0}

    def prouver_archive(c, res):
        return entete(res["id"])["archive"] == res["archive"]

    def defaire_archive(c, res):
        db.ecrire("UPDATE projets SET archive=? WHERE id=?", (res["avant"], res["id"]))

    def supprimer(c, id=0):
        compte = compte_agit()
        p = exiger(id, "supprimer", compte)
        db.ecrire("UPDATE projets SET supprime_at=?, maj=? WHERE id=?", (time.time(), time.time(), p["id"]))
        c.emettre("projet.supprime", objet=("projet", str(p["id"])), donnees={"id": p["id"]})
        return {"id": p["id"], "compte": compte}

    def prouver_supprime(c, res):
        return entete(res["id"])["supprime_at"] is not None

    def defaire_supprime(c, res):
        db.ecrire("UPDATE projets SET supprime_at=NULL WHERE id=?", (res["id"],))

    def restaurer(c, id=0):
        compte = compte_agit()
        p = entete(id)
        if p is None or p["compte"] != compte or p["supprime_at"] is None:
            raise ValueError("projet introuvable dans la corbeille")
        db.ecrire("UPDATE projets SET supprime_at=NULL, maj=? WHERE id=?", (time.time(), p["id"]))
        c.emettre("projet.restaure", objet=("projet", str(p["id"])), donnees={"id": p["id"]})
        return {"id": p["id"], "compte": compte, "supprime_at": p["supprime_at"]}

    def prouver_restaure(c, res):
        return entete(res["id"])["supprime_at"] is None

    def defaire_restaure(c, res):
        db.ecrire("UPDATE projets SET supprime_at=? WHERE id=?", (res["supprime_at"], res["id"]))

    def purger(c, id=0):
        compte = compte_agit()
        p = entete(id)
        if p is None or p["compte"] != compte or p["supprime_at"] is None:
            raise ValueError("projet introuvable dans la corbeille")
        snap = instantane(p["id"])
        effacer(p["id"])
        return {"id": p["id"], "compte": compte, "copie": snap}

    def prouver_purge(c, res):
        return entete(res["id"]) is None

    def defaire_purge(c, res):
        reposer(res["copie"])

    # ------------------------------------------------------------------ phases, jalons, décisions
    def valeurs_enfant(genre, d):
        table, cols = ENFANTS[genre]
        v = {}
        for k in cols:
            if d.get(k) is None:
                continue
            x = d[k]
            if k in ("debut", "fin", "date", "tenu_le", "ferme"):
                x = date_ok(x)
            elif k == "etat":
                admis = {"phase": ETATS_PHASE, "jalon": ETATS_JALON, "decision": ETATS_DECISION}[genre]
                if x not in admis:
                    raise ValueError("état : %s" % " | ".join(admis))
            elif k in ("ordre", "charge"):
                try:
                    x = max(0, min(int(x), 10 ** 6))
                except (TypeError, ValueError):
                    raise ValueError("%s : un entier est attendu" % k)
            else:
                x = str(x).strip()[:2000 if k in ("question", "reponse", "raison") else 200]
            v[k] = x
        return v

    def enfant_enregistrer(genre, c, id, ligne, champs):
        compte = compte_agit()
        p = exiger(id, "ecrire", compte)
        table, cols = ENFANTS[genre]
        v = valeurs_enfant(genre, champs)
        if ligne:
            avant = db.lire("SELECT * FROM %s WHERE id=? AND projet_id=?" % table, (int(ligne), p["id"]))
            if not avant:
                raise ValueError("%s introuvable" % genre)
            if v:
                db.ecrire("UPDATE %s SET %s WHERE id=?" % (table, ",".join("%s=?" % k for k in v)), list(v.values()) + [int(ligne)])
            rid, avant = int(ligne), dict(avant[0])
        else:
            if not v.get("nom" if genre != "decision" else "question"):
                raise ValueError("un nom est requis" if genre != "decision" else "une question est requise")
            if genre == "decision":
                v.setdefault("auteur", compte)
                v["quand"] = time.time()
            else:
                pass
            ks = list(v)
            rid = db.ecrire("INSERT INTO %s(projet_id, %s) VALUES (?,%s)" % (table, ",".join(ks), ",".join("?" * len(ks))), [p["id"]] + [v[k] for k in ks])
            avant = None
        if genre == "decision" and v.get("etat") == "tranchee" and not (v.get("ferme") or (avant or {}).get("ferme")):
            db.ecrire("UPDATE decisions SET ferme=? WHERE id=?", (time.strftime("%Y-%m-%d"), rid))
        db.ecrire("UPDATE projets SET maj=? WHERE id=?", (time.time(), p["id"]))
        return {"projet": p["id"], "ligne": rid, "genre": genre, "avant": avant, "compte": compte, "apres": v}

    def prouver_enfant(c, res):
        table = ENFANTS[res["genre"]][0]
        r = db.lire("SELECT * FROM %s WHERE id=? AND projet_id=?" % table, (res["ligne"], res["projet"]))
        return bool(r) and all(r[0][k] == v for k, v in res["apres"].items() if k != "quand")

    def defaire_enfant(c, res):
        table = ENFANTS[res["genre"]][0]
        if res["avant"] is None:
            db.ecrire("DELETE FROM %s WHERE id=? AND projet_id=?" % table, (res["ligne"], res["projet"]))
        else:
            a = res["avant"]
            db.ecrire("UPDATE %s SET %s WHERE id=?" % (table, ",".join("%s=?" % k for k in a if k != "id")), [a[k] for k in a if k != "id"] + [res["ligne"]])

    def enfant_supprimer(genre, c, id, ligne):
        compte = compte_agit()
        p = exiger(id, "ecrire", compte)
        table = ENFANTS[genre][0]
        avant = db.lire("SELECT * FROM %s WHERE id=? AND projet_id=?" % table, (int(ligne), p["id"]))
        if not avant:
            raise ValueError("%s introuvable" % genre)
        db.ecrire("DELETE FROM %s WHERE id=?" % table, (int(ligne),))
        db.ecrire("UPDATE projets SET maj=? WHERE id=?", (time.time(), p["id"]))
        return {"projet": p["id"], "ligne": int(ligne), "genre": genre, "ligne_avant": dict(avant[0])}

    def prouver_enfant_supprime(c, res):
        return not db.lire("SELECT 1 FROM %s WHERE id=?" % ENFANTS[res["genre"]][0], (res["ligne"],))

    def defaire_enfant_supprime(c, res):
        a = res["ligne_avant"]
        ks = list(a)
        db.ecrire("INSERT OR REPLACE INTO %s(%s) VALUES (%s)" % (ENFANTS[res["genre"]][0], ",".join(ks), ",".join("?" * len(ks))), [a[k] for k in ks])

    def phase_enregistrer(c, id=0, ligne=None, **champs):
        return enfant_enregistrer("phase", c, id, ligne, champs)

    def jalon_enregistrer(c, id=0, ligne=None, **champs):
        return enfant_enregistrer("jalon", c, id, ligne, champs)

    def decision_enregistrer(c, id=0, ligne=None, **champs):
        return enfant_enregistrer("decision", c, id, ligne, champs)

    def phase_supprimer(c, id=0, ligne=0):
        return enfant_supprimer("phase", c, id, ligne)

    def jalon_supprimer(c, id=0, ligne=0):
        return enfant_supprimer("jalon", c, id, ligne)

    def decision_supprimer(c, id=0, ligne=0):
        return enfant_supprimer("decision", c, id, ligne)

    # ------------------------------------------------------------------ le plan de référence
    def refiger(c, id=0):
        compte = compte_agit()
        p = exiger(id, "fiche", compte)
        phases = [dict(r) for r in db.lire("SELECT id, nom, debut, fin, ref_debut, ref_fin FROM phases WHERE projet_id=? ORDER BY ordre, id", (p["id"],))]
        jalons = [dict(r) for r in db.lire("SELECT id, ref_date FROM jalons WHERE projet_id=?", (p["id"],))]
        ancien = "; ".join("%s %s→%s" % (x["nom"], x["ref_debut"] or "?", x["ref_fin"] or "?") for x in phases if x["ref_fin"])
        note = "Plan de référence refigé — référence précédente : " + ancien if ancien else "Plan de référence posé."
        with db.transaction() as cx:
            cx.execute("UPDATE phases SET ref_debut=debut, ref_fin=fin WHERE projet_id=?", (p["id"],))
            cx.execute("UPDATE jalons SET ref_date=date WHERE projet_id=? AND ref_date=''", (p["id"],))
            cx.execute("UPDATE projets SET ref_date=?, notes=?, maj=? WHERE id=?", (time.strftime("%Y-%m-%d"), ajouter_ligne(p["notes"], note), time.time(), p["id"]))
        return {"id": p["id"], "phases_avant": phases, "jalons_avant": jalons, "ref_date_avant": p["ref_date"], "notes_avant": p["notes"]}

    def prouver_refige(c, res):
        return all(r["ref_fin"] == r["fin"] and r["ref_debut"] == r["debut"] for r in db.lire("SELECT debut, fin, ref_debut, ref_fin FROM phases WHERE projet_id=?", (res["id"],)))

    def defaire_refige(c, res):
        with db.transaction() as cx:
            for x in res["phases_avant"]:
                cx.execute("UPDATE phases SET ref_debut=?, ref_fin=? WHERE id=?", (x["ref_debut"], x["ref_fin"], x["id"]))
            for x in res["jalons_avant"]:
                cx.execute("UPDATE jalons SET ref_date=? WHERE id=?", (x["ref_date"], x["id"]))
            cx.execute("UPDATE projets SET ref_date=?, notes=? WHERE id=?", (res["ref_date_avant"], res["notes_avant"], res["id"]))

    # ------------------------------------------------------------------ l'équipe
    def membre(pid, compte):
        r = db.lire("SELECT * FROM membres WHERE projet_id=? AND compte=?", (pid, compte))
        return dict(r[0]) if r else None

    def inviter(c, id=0, compte="", role=""):
        moi = compte_agit()
        p = exiger(id, "equipe", moi)
        cible = str(compte or "").strip().lower()
        if not ctx.dans_ma_societe(cible):
            raise ValueError("ce compte n'a pas accès à cette société : on ne partage qu'avec les siens")
        r = str(role or "").strip().lower().replace("-", "")
        if r not in ROLES:
            raise ValueError("rôle inconnu (lecteur, auteur, coproprietaire)")
        connus = comptes_connus()
        if not cible or (connus is not None and cible not in connus):
            raise ValueError("aucun compte « %s »" % cible)
        if cible == p["compte"]:
            raise ValueError("c'est le propriétaire du projet")
        avant = membre(p["id"], cible)
        if avant:
            db.ecrire("UPDATE membres SET role=? WHERE projet_id=? AND compte=?", (r, p["id"], cible))
        else:
            db.ecrire("INSERT INTO membres(projet_id, compte, role, etat, invite_par, ts) VALUES (?,?,?,?,?,?)", (p["id"], cible, r, "invite", moi, time.time()))
            c.emettre("projet.invitation", objet=("projet", str(p["id"])), donnees={"id": p["id"], "projet": p["nom"], "role": r, "par": moi}, compte=cible)
        return {"id": p["id"], "compte": cible, "role": r, "avant": avant, "moi": moi}

    def prouver_membre(c, res):
        m = membre(res["id"], res["compte"])
        return m is not None and m["role"] == res["role"]

    def defaire_membre(c, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM membres WHERE projet_id=? AND compte=?", (res["id"], res["compte"]))
        else:
            db.ecrire("UPDATE membres SET role=? WHERE projet_id=? AND compte=?", (res["avant"]["role"], res["id"], res["compte"]))

    def repondre_invitation(c, id=0, accepter=True):
        moi = compte_agit()
        m = membre(int(id), moi)
        if m is None or m["etat"] != "invite":
            raise ValueError("aucune invitation en attente pour ce projet")
        p = entete(id)
        if accepter:
            db.ecrire("UPDATE membres SET etat='actif', ts=? WHERE projet_id=? AND compte=?", (time.time(), m["projet_id"], moi))
        else:
            db.ecrire("DELETE FROM membres WHERE projet_id=? AND compte=?", (m["projet_id"], moi))
        if m["invite_par"]:
            c.emettre("projet.reponse", objet=("projet", str(m["projet_id"])), donnees={"id": m["projet_id"], "projet": p["nom"] if p else "", "compte": moi, "accepte": bool(accepter)}, compte=m["invite_par"])
        return {"id": m["projet_id"], "compte": moi, "accepte": bool(accepter), "avant": m}

    def prouver_reponse(c, res):
        m = membre(res["id"], res["compte"])
        return (m is not None and m["etat"] == "actif") if res["accepte"] else m is None

    def defaire_reponse(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO membres(projet_id, compte, role, etat, invite_par, ts) VALUES (?,?,?,?,?,?)", (a["projet_id"], a["compte"], a["role"], a["etat"], a["invite_par"], a["ts"]))

    def retirer_membre(c, id=0, compte=""):
        moi = compte_agit()
        cible = str(compte or "").strip().lower() or moi
        p = entete(id)
        if p is None:
            raise ValueError("projet introuvable")
        if cible != moi:
            exiger(id, "equipe", moi)
        avant = membre(p["id"], cible)
        if avant is None:
            raise ValueError("ce compte n'est pas membre")
        db.ecrire("DELETE FROM membres WHERE projet_id=? AND compte=?", (p["id"], cible))
        return {"id": p["id"], "compte": cible, "avant": avant}

    def prouver_retire(c, res):
        return membre(res["id"], res["compte"]) is None

    def defaire_retire(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO membres(projet_id, compte, role, etat, invite_par, ts) VALUES (?,?,?,?,?,?)", (a["projet_id"], a["compte"], a["role"], a["etat"], a["invite_par"], a["ts"]))

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.detecteur("jalon_depasse", det_jalons)
    for cid, f in (("modeles", modeles), ("lister", lister), ("voir", voir), ("trouver", trouver), ("equipe", equipe), ("invitations", invitations), ("corbeille", corbeille), ("contexte", contexte), ("portefeuille", portefeuille)):
        c.implementer(cid, f)
    c.implementer("creer", creer, prouver_cree, defaire_cree, simuler=lambda x, nom="", **_: "créerait le projet « %s »" % nom)
    c.implementer("modifier", modifier, prouver_modifie, defaire_modifie, simuler=lambda x, id="", **_: "modifierait la fiche du projet %s" % id)
    c.implementer("noter", noter, prouver_note, defaire_note, simuler=lambda x, id="", **_: "ajouterait une note au journal du projet %s" % id)
    c.implementer("archiver", archiver, prouver_archive, defaire_archive, simuler=lambda x, id="", **_: "archiverait (ou rouvrirait) le projet %s" % id)
    c.implementer("supprimer", supprimer, prouver_supprime, defaire_supprime, simuler=lambda x, id="", **_: "mettrait le projet %s à la corbeille" % id)
    c.implementer("restaurer", restaurer, prouver_restaure, defaire_restaure, simuler=lambda x, id="", **_: "sortirait le projet %s de la corbeille" % id)
    c.implementer("purger", purger, prouver_purge, defaire_purge, simuler=lambda x, id="", **_: "effacerait le projet %s de la corbeille" % id)
    c.implementer("phase_enregistrer", phase_enregistrer, prouver_enfant, defaire_enfant, simuler=lambda x, id="", **_: "enregistrerait une phase du projet %s" % id)
    c.implementer("jalon_enregistrer", jalon_enregistrer, prouver_enfant, defaire_enfant, simuler=lambda x, id="", **_: "enregistrerait un jalon du projet %s" % id)
    c.implementer("decision_enregistrer", decision_enregistrer, prouver_enfant, defaire_enfant, simuler=lambda x, id="", **_: "enregistrerait une décision du projet %s" % id)
    c.implementer("phase_supprimer", phase_supprimer, prouver_enfant_supprime, defaire_enfant_supprime, simuler=lambda x, id="", **_: "supprimerait une phase du projet %s" % id)
    c.implementer("jalon_supprimer", jalon_supprimer, prouver_enfant_supprime, defaire_enfant_supprime, simuler=lambda x, id="", **_: "supprimerait un jalon du projet %s" % id)
    c.implementer("decision_supprimer", decision_supprimer, prouver_enfant_supprime, defaire_enfant_supprime, simuler=lambda x, id="", **_: "supprimerait une décision du projet %s" % id)
    c.implementer("refiger", refiger, prouver_refige, defaire_refige, simuler=lambda x, id="", **_: "figerait le plan de référence du projet %s" % id)
    c.implementer("inviter", inviter, prouver_membre, defaire_membre, simuler=lambda x, compte="", **_: "inviterait %s dans le projet" % compte)
    c.implementer("repondre_invitation", repondre_invitation, prouver_reponse, defaire_reponse, simuler=lambda x, id="", **_: "répondrait à l'invitation du projet %s" % id)
    c.implementer("retirer_membre", retirer_membre, prouver_retire, defaire_retire, simuler=lambda x, compte="", **_: "retirerait %s du projet" % compte)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : date_ok, journal, jours_entre, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
