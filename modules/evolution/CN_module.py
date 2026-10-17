# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Évolution : le pilotage de l'évolution de Cassandra
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : evolution
# ZONE       : CN
# VERSION CN : 0.2.0  #a59144
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : expose l'évolution du noyau comme capacités de Cassandra : cibles, état, proposer, retour, visiter, et un moteur qui fait avancer les paliers.
# MÉTHODE    : une coquille mince : tout ce qui décide vit dans noyau/CN_evolution.py ; le moteur de recherche est chargé par son chemin d'import (le contrat d'adaptateur).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=a59144 ▼▼▼
"""Le module « Évolution » : la coquille entre Cassandra (droits, paliers, preuves, retours, réglages) et le service d'évolution du noyau.

Il ne propose rien lui-même et ne juge rien : le moteur de recherche (Orfan) rend du texte, l'évaluateur du noyau le juge, le routage du noyau le met en service.
Ce module ne fait que donner à ces gestes leurs droits, leur preuve et leur retour, comme à tout geste de Cassandra qui écrit.
"""
from __future__ import annotations

import importlib


def brancher(ctx):
    evo = ctx.evolution()

    def reglage(nom, defaut):
        try:
            v = ctx.reglage(nom)
        except Exception:
            v = None
        return defaut if v in (None, "") else v

    def appeler_modele(prompt):
        """Le modèle du rôle choisi, par le module Modèles (une lecture). Un modèle muet ou absent est une erreur DITE, jamais une réponse inventée."""
        r = ctx.executer_lecture("modeles.completer", messages=[{"role": "user", "content": prompt}], role=str(reglage("modele_role", "evolution")),
                                 max_tokens=3000, temperature=0.2)
        if not r or not r.get("ok"):
            raise RuntimeError((r or {}).get("erreur") or "le modèle n'a pas répondu (module Modèles absent, ou rôle « %s » sans modèle)" % reglage("modele_role", "evolution"))
        return r.get("texte") or ""

    def moteur_de_recherche(choix):
        orfan = importlib.import_module(str(reglage("moteur_orfan", "orfan.CN_orfan")))
        if choix == "modele":
            return orfan.MoteurModele(appeler_modele)
        if choix == "les_deux":
            return orfan.MoteurComposite(orfan.MoteurDeterministe(), orfan.MoteurModele(appeler_modele))
        return orfan.MoteurDeterministe()

    def decouper(point):
        gid = str(point or "").strip()
        if gid not in evo.points.points():
            raise ValueError("point d'évolution inconnu : « %s » (voir evolution.cibles)" % gid)
        return gid.split(".", 1)

    # ── les lectures ─────────────────────────────────────────────────────
    def cibles(c):
        return {"cibles": evo.cibles()}

    def etat(c):
        points = []
        for gid in evo.points.points():
            m, p = gid.split(".", 1)
            points.append(dict(evo.points.etat(m, p), corpus=evo.rejeu.stats(gid)))
        return {"cibles": evo.cibles(), "pieces": evo.pieces(), "points": points, "chaine": evo.verifier_chaine(), "journal": evo.chaine(None, 40), "seuils": {k: (list(v) if isinstance(v, tuple) else v) for k, v in evo.seuils.items()},
                "tombes": {gid: len(evo.tombes(gid)) for gid in evo.points.points()}}

    # ── les gestes ───────────────────────────────────────────────────────
    def proposer(c, point="", moteur="", budget=0):
        m, p = decouper(point)
        choix = str(moteur or reglage("moteur_defaut", "deterministe"))
        if choix not in ("deterministe", "modele", "les_deux"):
            raise ValueError("moteur inconnu : « %s » (deterministe, modele, les_deux)" % choix)
        r = evo.proposer(m, p, moteur_de_recherche(choix), int(budget) or int(reglage("budget_essais", 3)))
        r["moteur"] = choix
        return r

    def prouver_proposition(c, res):
        if not res.get("piece"):
            return True                                        # rien n'a été écrit : rien à prouver, et rien à défaire
        piece = res["piece"]
        vivante = [x for x in evo.pieces(piece["gid"]) if x["num"] == piece["num"] and x["etat"] == "ombre"]
        return bool(vivante) and evo.verifier_chaine()["ok"]

    def defaire_proposition(c, res):
        if res.get("piece"):
            evo.retour(res["piece"]["gid"], "retour arrière de la proposition")

    def retour(c, point="", raison="retour demandé"):
        decouper(point)
        return {"point": point, "retraits": evo.retour(point, str(raison or "retour demandé"))}

    def prouver_retour(c, res):
        m, p = res["point"].split(".", 1)
        e = evo.points.etat(m, p)
        return (e["routage"] or {}).get("mode") in (None, "arret") and not any(x["etat"] in ("ombre", "palier_10", "palier_50", "en_service") for x in evo.pieces(res["point"]))

    def sans_retour(c, res):
        raise ValueError("aucun retour automatique : une pièce retirée se propose de nouveau (evolution.proposer)")

    def visiter(c):
        return {"visites": evo.visiter()}

    def prouver_visite(c, res):
        return all(v.get("verdict") for v in res["visites"])

    # ── le moteur périodique : les paliers avancent seulement si les preuves le permettent ──
    def tick(c):
        avances = evo.tick()
        visites = evo.visiter()
        return {"avances": avances, "visites": visites}

    ctx.implementer("cibles", cibles)
    ctx.implementer("etat", etat)
    ctx.implementer("proposer", proposer, prouver_proposition, defaire_proposition)
    ctx.implementer("retour", retour, prouver_retour, sans_retour)
    ctx.implementer("visiter", visiter, prouver_visite, sans_retour)
    ctx.moteur("tick", tick)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : la coquille du module Évolution (capacités, preuves, retours, moteur périodique). Aucune logique d'évolution ici.
# EC : néant. Le module qui pilote l'évolution ne s'évolue pas (docs/CN_NEXUS.md §4).
# LIEN : noyau/CN_evolution.py (le service), noyau/CN_evaluateur.py (le juge), orfan/CN_orfan.py (le moteur de recherche), modules/modeles (les modèles par rôle).
