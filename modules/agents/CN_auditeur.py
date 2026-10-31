# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'Auditeur, un service agentique
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : CN
# VERSION CN : 0.4.0  #bde975
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'Auditeur, un service agentique : il relit le journal et signale les dérives, indépendamment des agents qu'il regarde.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.0 empreinte=bde975 ▼▼▼
# ▼▼▼ BORNE CN version=0.4.0 empreinte=000000 ▼▼▼
"""L'Auditeur, un service agentique : il relit le journal et signale les dérives, indépendamment des agents qu'il regarde.

  - LECTURE SEULE : aucun outil (`acteur_outils` vide), aucune écriture ; `auditer` est une capacité de lecture réservée à l'administrateur (le journal d'instance, jamais un bureau).
  - Il SIGNALE, il ne corrige pas : un signal rend ce qu'il a vu et la ligne qui le prouve (une ligne du journal, ou une ligne des tables de l'équipe) ; le geste est à l'administrateur.
  - Trois regards : un COÛT qui dérive (un jour bien au-dessus des précédents), un PALIER trop généreux (une capacité en `auto` qu'on défait à répétition), des tentatives d'INJECTION
    répétées (le Relecteur a retenu des réponses porteuses d'un ordre caché).
  - PLAFONDS (`services.auditeur.plafonds` de l'équipe) : jours regardés, lignes lues, signaux rendus. Il ne lit pas plus que cela, quel que soit l'appel.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

from .CN_equipe import DONNEES

PLAFONDS_DEFAUT = {"jours_max": 30, "lignes_max": 5000, "signaux_max": 20}
SEUIL_COUT = 2.0                 # un jour qui coûte plus du double de la moyenne des précédents…
PLANCHER_COUT_CTS = 5.0          # … et d'au moins cette somme (centimes) : une dérive de quelques centimes n'est pas un signal
SEUIL_DEFAITES = 2               # une capacité défaite au moins deux fois
SEUIL_INJECTIONS = 3             # trois retenues pour ordre caché, même agent, même compte


def analyser(couts, defaites, paliers_auto, relectures, plafonds=None):
    """Le calcul, sans accès au monde (testable à part) : trois listes de lignes en entrée, une liste de signaux en sortie.
    couts : [{jour, agent, centimes}] ; defaites : [{id, capacite, agent}] ; paliers_auto : {(agent, capacite)} ; relectures : [{id, agent, compte, motifs:[...]}]."""
    p = dict(PLAFONDS_DEFAUT, **(plafonds or {}))
    signaux = []
    par_agent = {}
    for c in couts:
        par_agent.setdefault(c["agent"], {}).setdefault(c["jour"], 0.0)
        par_agent[c["agent"]][c["jour"]] += float(c["centimes"] or 0)
    for agent, jours in sorted(par_agent.items()):
        ordre = sorted(jours)
        if len(ordre) < 2:
            continue
        dernier, avant = ordre[-1], ordre[:-1]
        moyenne = sum(jours[j] for j in avant) / len(avant)
        if jours[dernier] >= PLANCHER_COUT_CTS and jours[dernier] > SEUIL_COUT * moyenne:
            signaux.append({"type": "cout_derive", "agent": agent, "ref": "agent_couts:%s:%s" % (dernier, agent),
                            "phrase": "%s a coûté %.1f centimes le %s, pour %.1f en moyenne les %d jours d'avant." % (agent, jours[dernier], dernier, moyenne, len(avant))})
    comptes = {}
    for d in defaites:
        comptes.setdefault((d["agent"], d["capacite"]), []).append(d["id"])
    for (agent, capacite), ids in sorted(comptes.items()):
        if len(ids) >= SEUIL_DEFAITES and (agent, capacite) in paliers_auto:
            signaux.append({"type": "palier_large", "agent": agent, "capacite": capacite, "journal": ids[-1],
                            "phrase": "%s fait %s en autonomie, et on l'a défait %d fois : le palier « raconter » serait plus sûr." % (agent, capacite, len(ids))})
    inj = {}
    for r in relectures:
        if "ordre_cache" in (r.get("motifs") or []):
            inj.setdefault((r["agent"], r["compte"]), []).append(r["id"])
    for (agent, compte), ids in sorted(inj.items()):
        if len(ids) >= SEUIL_INJECTIONS:
            signaux.append({"type": "injection_repetee", "agent": agent, "compte": compte, "ref": "relectures:%d" % ids[-1],
                            "phrase": "%d réponses de %s ont été retenues pour un ordre caché : une source répète la tentative." % (len(ids), agent)})
    return signaux[:int(p["signaux_max"])]


def brancher_auditeur(ctx, E, db, compte_agit):
    """La capacité `agents.auditer` (lecture) : lit le journal et les tables de l'équipe, rend les signaux. Administrateur seulement."""
    p = dict(PLAFONDS_DEFAUT, **DONNEES.get("services", {}).get("auditeur", {}).get("plafonds", {}))

    def auditer(c, jours=7):
        compte = compte_agit()
        if not E.admin(compte):
            raise PermissionError("l'Auditeur lit le journal d'instance : administrateur seulement")
        jours = max(1, min(int(jours or 7), int(p["jours_max"])))
        debut = time.time() - jours * 86400
        premier = (datetime.now(timezone.utc) - timedelta(days=jours)).strftime("%Y-%m-%d")
        couts = db.lire("SELECT jour, agent, centimes FROM agent_couts WHERE jour>=? ORDER BY jour LIMIT ?", (premier, int(p["lignes_max"])))
        faits = {e["id"]: e for e in ctx.evenements("capacite.faite", int(p["lignes_max"]))}
        actes = {a["evenement"]: a for a in db.lire("SELECT evenement, agent, capacite, palier FROM agent_actes WHERE ts>=? LIMIT ?", (debut, int(p["lignes_max"])))}
        defaites = []
        for e in ctx.evenements("capacite.defaite", int(p["lignes_max"])):
            if e["ts"] < debut:
                continue
            fait = faits.get(e.get("cause"))
            acte = actes.get(fait.get("cause")) if fait else None
            if acte:
                defaites.append({"id": e["id"], "agent": acte["agent"], "capacite": acte["capacite"]})
        auto = {(r["agent"], r["outil"]) for r in db.lire("SELECT agent, outil FROM agent_paliers WHERE palier='auto'")}
        auto |= {(a["agent"], a["capacite"]) for a in actes.values() if a.get("palier") == "auto"}
        relectures = []
        for r in db.lire("SELECT id, agent, compte, motifs FROM relectures WHERE ts>=? ORDER BY id LIMIT ?", (debut, int(p["lignes_max"]))):
            try:
                motifs = json.loads(r["motifs"] or "[]")
            except ValueError:
                motifs = []
            relectures.append({"id": r["id"], "agent": r["agent"], "compte": r["compte"], "motifs": motifs})
        signaux = analyser(couts, defaites, auto, relectures, p)
        return {"jours": jours, "signaux": signaux, "lecture_seule": True, "regards": ["cout_derive", "palier_large", "injection_repetee"]}

    ctx.implementer("auditer", auditer)
# ▲▲▲ FIN BORNE CN ▲▲▲
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : analyser, brancher_auditeur
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
