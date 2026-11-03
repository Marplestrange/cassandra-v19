# ══════════════════════════════════════════════
# TITRE      : L'adaptateur d'OpenEvolve
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #00ef08
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Fait chercher OpenEvolve (le projet externe) sur un point d'évolution de Cassandra : ses modèles sont le relais de la cage, son évaluation est une comparaison locale aux sorties de la référence.
# MÉTHODE    : `proposer(contexte, modele)` ; OpenEvolve tourne dans l'environnement du moteur ; son « serveur OpenAI » est celui de la cage (modele.url) ; son score est le rapport de temps d'une variante ÉQUIVALENTE.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=00ef08 ▼▼▼
"""Adaptateur du moteur externe OpenEvolve (https://github.com/algorithmicsuperintelligence/openevolve, paquet `openevolve`).

Contrat des adaptateurs (orfan/CN_moteur_hote.py) : un module qui expose `proposer(contexte, modele) -> [{"texte", "hypothese"}]`. `modele.url` est un serveur compatible OpenAI sur la
boucle locale de la cage : OpenEvolve n'a aucune autre route vers un modèle, ni clé, ni réseau. Ses appels deviennent des demandes de modèle comptées et plafonnées par Cassandra.

Le juge de Cassandra décide ensuite, sur tout le corpus et le jeu réservé : ce que rend cet adaptateur n'est qu'une PROPOSITION, comme celle de tout moteur.
"""
import copy
import json
import os
import tempfile
import time

IMPORTER = ["openevolve", "openevolve.api", "openevolve.config"]          # ce que le banc d'import de l'installateur doit pouvoir charger dans l'environnement du moteur


def _evaluateur(source, fonction, entrees):
    """La fonction d'évaluation d'OpenEvolve : un programme n'a de score que s'il répond comme la référence sur les entrées visibles ; son score est alors le rapport des temps."""
    sujet = [copy.deepcopy(e) for e in entrees[:24]]

    def canon(v):
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))

    def charger(texte):
        ns = {}
        exec(compile(texte, "<programme>", "exec"), ns)
        return ns[fonction]

    ref = charger(source)
    attendu = [canon(ref(copy.deepcopy(e))) for e in sujet]

    def mesure(f):
        meilleur = None
        for _ in range(2):
            t = 0
            for e in sujet:
                x = copy.deepcopy(e)
                d0 = time.perf_counter_ns()
                f(x)
                t += time.perf_counter_ns() - d0
            meilleur = t if meilleur is None else min(meilleur, t)
        return meilleur

    t_ref = mesure(ref)

    def evaluer(chemin_programme):
        try:
            texte = open(chemin_programme, encoding="utf-8").read()
            cand = charger(texte)
            for e, a in zip(sujet, attendu):
                if canon(cand(copy.deepcopy(e))) != a:
                    return {"combined_score": 0.0, "equivalent": 0.0}
            t = mesure(cand)
        except Exception:
            return {"combined_score": 0.0, "equivalent": 0.0}
        rapport = (t_ref / t) if t else 0.0
        return {"combined_score": round(rapport, 4), "equivalent": 1.0, "rapport_de_temps": round(rapport, 4)}
    return evaluer


def proposer(contexte, modele):
    from openevolve.api import run_evolution
    from openevolve.config import Config, LLMModelConfig

    source, fonction, entrees = contexte["source_reference"], contexte["fonction"], contexte.get("entrees") or []
    budget = max(1, int(contexte.get("budget", 3)))
    cfg = Config()
    cfg.llm.models = [LLMModelConfig(name="relais", api_base=modele.url, api_key=modele.cle, weight=1.0, timeout=120, retries=1, retry_delay=1, temperature=0.2)]
    cfg.diff_based_evolution = False                       # le modèle rend la fonction entière dans un bloc ```python : le format de tous les moteurs de Cassandra
    cfg.evaluator.parallel_evaluations = 1
    cfg.evaluator.cascade_evaluation = False
    cfg.database.num_islands = 1
    cfg.database.population_size = max(4, budget * 2)
    cfg.max_iterations = max(1, budget * 2)
    sortie = tempfile.mkdtemp(prefix="openevolve_cage_")
    res = run_evolution(source, _evaluateur(source, fonction, entrees), config=cfg, iterations=cfg.max_iterations, output_dir=sortie, cleanup=False)
    candidats = []
    for programme in _programmes(res):
        texte = programme.code.rstrip("\n") + "\n"
        score = (programme.metrics or {}).get("combined_score", 0.0)
        if score > 1.0 and (programme.metrics or {}).get("equivalent") == 1.0 and texte.strip() != source.strip():
            candidats.append((score, texte))
    candidats.sort(key=lambda x: -x[0])
    vus, rendus = set(), []
    for score, texte in candidats:
        if texte not in vus:
            vus.add(texte)
            rendus.append({"texte": texte, "hypothese": "OpenEvolve : variante ×%.2f sur le vu" % score, "origine": "openevolve"})
    return rendus[:budget]


def _programmes(res):
    """Les programmes de la population finale (le meilleur d'abord), lus dans le dossier de sortie d'OpenEvolve."""
    from openevolve.database import Program
    sortie = res.output_dir or ""
    vus = []
    if res.best_program is not None:
        vus.append(res.best_program)
    racine = os.path.join(sortie, "checkpoints")
    if os.path.isdir(racine):
        for nom in sorted(os.listdir(racine), reverse=True)[:1]:
            dossier = os.path.join(racine, nom, "programs")
            if os.path.isdir(dossier):
                for f in os.listdir(dossier):
                    if f.endswith(".json"):
                        try:
                            vus.append(Program.from_dict(json.load(open(os.path.join(dossier, f), encoding="utf-8"))))
                        except Exception:
                            continue
    return vus
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un adaptateur ne s'évolue pas).
# CN : le pont entre le contrat de Cassandra et l'API d'OpenEvolve ; il ne juge jamais, il rend des textes.
# LIEN : orfan/CN_moteur_hote.py (le relais « OpenAI » de la cage), noyau/CN_installateur.py (qui installe openevolve), noyau/CN_moteurs.py.
