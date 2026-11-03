# ══════════════════════════════════════════════
# TITRE      : Les moteurs de génomes texte : prompts et politiques
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #78cae5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Propose des réécritures de prompts (réflexion par un modèle) et des réglages de politiques (recherche locale sur ce que l'utilisateur a acquitté sans agir), chacune jugée par le juge qui lui correspond avant d'être rendue.
# MÉTHODE    : un moteur propose, un juge décide, rien n'est écrit : le résultat est une liste de propositions jugées ; la mise en service d'un prompt ou d'une politique reste un geste à part.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=78cae5 ▼▼▼
"""Le genome texte a ses moteurs (docs/CN_maquette-evolution-moteurs.html, vue Juges).

PROMPTS : `proposer_prompt` demande au modèle (rôle « stratège ») de réécrire un prompt selon une consigne, en gardant ses variables et ses clauses d'interdiction ; chaque réécriture
passe par `juger_prompt` (contrôles sans modèle, puis cas piégés à canari). Seules les réécritures ACCEPTÉES sont rendues comme propositions ; les refusées sont rendues avec leur raison.

POLITIQUES : `proposer_politique` fait une recherche LOCALE sur un seuil : l'historique dit, pour chaque mesure passée, si l'utilisateur a AGI ou a acquitté sans agir (fausse alerte). Le meilleur
seuil dans l'intervalle autorisé (et au-dessus du plancher du noyau) est celui qui ne rate AUCUNE alerte suivie d'une action et fait taire le plus de fausses alertes. Aucun modèle : déterministe.
"""
from __future__ import annotations

import re

try:
    from . import CN_juge_prompt as JP
except ImportError:                                                  # chargé par son chemin
    from noyau import CN_juge_prompt as JP                           # type: ignore


def _bloc(texte: str) -> str:
    """Le prompt réécrit : le bloc ``` s'il y en a un, sinon la réponse entière."""
    m = re.search(r"```(?:[a-z]*)\s*\n(.*?)```", texte, re.S)
    return (m.group(1) if m else texte).strip()


def construire_consigne(reference: str, consigne: str, ancien: list | None = None) -> str:
    interdits = JP.clauses_interdiction(reference)
    lignes = ["Tu réécris un prompt d'agent pour l'améliorer selon une consigne, SANS en affaiblir les protections.", "", "Prompt à améliorer :", "```", reference.strip(), "```", "",
              "Consigne : " + consigne.strip(), "", "Règles strictes :",
              "- garde EXACTEMENT les mêmes variables entre accolades : %s ;" % (", ".join("{%s}" % v for v in sorted(JP.variables(reference))) or "aucune"),
              "- garde, mot pour mot, chaque clause d'interdiction : %s ;" % (" / ".join("« %s »" % c for c in interdits) or "aucune dans l'original"),
              "- n'ajoute aucune capacité, aucun droit, aucune levée de frein ; rends UNIQUEMENT le prompt réécrit dans un bloc ```."]
    if ancien:
        lignes += ["", "Ces réécritures ont déjà été refusées par le juge, ne les redis pas : " + " | ".join(a[:80] for a in ancien[:3])]
    return "\n".join(lignes)


def proposer_prompt(reference: str, consigne: str, appeler_modele, contrat_sortie: dict | None = None, valeurs: dict | None = None, poison: str | None = None, combien: int = 2,
                    max_chars: int = JP.MAX_CHARS_DEFAUT) -> dict:
    """Rend {propositions:[{texte, jugement}], refusees:[{texte, raison, jugement}], appels}. Un modèle absent ou muet est une erreur DITE."""
    if not str(reference).strip() or not str(consigne).strip():
        raise ValueError("un prompt de référence et une consigne sont nécessaires")
    combien = max(1, min(int(combien), 4))
    acceptees, refusees, refus_texte, appels = [], [], [], 0
    for _ in range(combien):
        brut = appeler_modele(construire_consigne(reference, consigne, refus_texte))
        appels += 1
        texte = _bloc(str(brut or ""))
        if not texte or texte.strip() == reference.strip() or any(texte == x["texte"] for x in acceptees + refusees):
            refusees.append({"texte": texte, "raison": "vide ou identique à ce qui existe déjà", "jugement": None})
            continue
        j = JP.juger_prompt(reference, texte, appeler_modele, contrat_sortie, valeurs, poison, max_chars)
        appels += 1 + (len(j["pieges"]) if j["pieges"] else 0)
        if j["verdict"] == "accepte":
            acceptees.append({"texte": texte, "jugement": j})
        else:
            raison = next((c["detail"] for c in j["controles"] if not c["ok"]), "") or next((p["detail"] for p in j["pieges"] if not p["ok"]), "") or "verdict : " + j["verdict"]
            refusees.append({"texte": texte, "raison": raison, "jugement": j})
            refus_texte.append(texte)
    return {"propositions": acceptees, "refusees": refusees, "appels": appels}


def proposer_politique(reference: dict, intervalles: dict | None, planchers: dict | None, historique: list, pas: int = 40) -> dict:
    """`historique` : [{"cle": "seuil_alerte", "mesure": 87, "agi": true}, …] — `agi` faux : l'utilisateur a acquitté sans agir (fausse alerte). Rend {politique, changements:[…], jugement}."""
    politique = dict(reference)
    changements = []
    for cle, valeur in reference.items():
        mesures = [h for h in historique if h.get("cle") == cle and isinstance(h.get("mesure"), (int, float))]
        if not mesures or isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
            continue
        bas, haut = (intervalles or {}).get(cle, [min(h["mesure"] for h in mesures), max(h["mesure"] for h in mesures)])
        plancher = (planchers or {}).get(cle)
        suivies = [h["mesure"] for h in mesures if h.get("agi")]
        # une alerte part quand mesure >= seuil : le seuil le plus haut qui garde TOUTES les alertes suivies d'une action ne dépasse pas la plus petite mesure suivie
        plafond = min(suivies) if suivies else haut
        candidats = sorted({round(bas + (haut - bas) * i / pas, 4) for i in range(pas + 1)} | {valeur})
        valables = [c for c in candidats if c <= plafond and (plancher is None or c >= plancher)] or [valeur]

        def fausses(seuil):
            return sum(1 for h in mesures if not h.get("agi") and h["mesure"] >= seuil)
        meilleur = min(valables, key=lambda c: (fausses(c), -c if c <= plafond else c, abs(c - valeur)))   # le moins de fausses alertes ; à égalité, le seuil le plus haut qui garde les suivies
        meilleur = int(meilleur) if isinstance(valeur, int) and float(meilleur).is_integer() else meilleur
        if meilleur != valeur and fausses(meilleur) < fausses(valeur) and all(m >= meilleur for m in suivies):
            changements.append({"cle": cle, "avant": valeur, "apres": meilleur, "fausses_avant": fausses(valeur), "fausses_apres": fausses(meilleur), "alertes_suivies_gardees": len(suivies)})
            politique[cle] = meilleur
    cles = {c["cle"] for c in changements}

    def decider(pol, entree):
        return entree["mesure"] >= pol[entree["cle"]]
    rejeu = [{"entree": h, "decision": bool(h.get("agi"))} for h in historique if h.get("cle") in reference]
    jugement = JP.juger_politique(politique, reference, intervalles=intervalles, planchers=planchers, tolerance_pct=100.0)
    return {"politique": politique, "changements": changements, "cles_touchees": sorted(cles), "jugement": jugement,
            "rejeu_suivies_gardees": all(decider(politique, h["entree"]) for h in rejeu if h["decision"])}
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (qui propose un prompt ou une politique ne s'évolue pas : le juge, lui, est le garde).
# CN : la réflexion sur un prompt, la recherche locale sur un seuil ; chaque proposition passe par son juge ; aucune écriture, aucune mise en service.
# LIEN : noyau/CN_juge_prompt.py (les juges), modules/evolution (les capacités proposer_prompt et proposer_politique), docs/CN_maquette-evolution-moteurs.html (la vue Juges).
