# ══════════════════════════════════════════════
# TITRE      : Le répertoire des chercheurs proposés
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #92d23f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La liste des chercheurs qu'on peut installer depuis l'écran (ce qu'ils font, ce qu'ils coûtent, d'où ils viennent, quel adaptateur les porte) ; le catalogue scellé, lui, ne contient que ce qui a été épinglé.
# MÉTHODE    : une donnée, aucune exécution ; un chercheur est proposé ici AVANT d'être épinglé : « préparer » résout son paquet et calcule ses empreintes, puis l'installateur n'installe que ce qui est épinglé.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=92d23f ▼▼▼
"""Le répertoire : ce qui est PROPOSÉ. Le catalogue (noyau/CN_installateur.py) : ce qui est ÉPINGLÉ et scellé. On passe de l'un à l'autre en « préparant » un chercheur.

Un chercheur du répertoire a :
  - `paquet` : le nom du paquet sur PyPI, ou `github` : « propriétaire/dépôt » (le commit est résolu et épinglé à la préparation) ; ou rien : la méthode est réimplémentée par Cassandra ;
  - `adaptateur` : le module d'adaptateur ÉCRIT À LA MAIN (orfan/adaptateurs/) s'il existe, sinon `None` : Cassandra en génère un à l'installation (repli) ;
  - `python` : la version exacte d'interpréteur qu'il exige, si le Python du serveur ne convient pas (Cassandra le pose, par exemple avec `uv`).
"""
from __future__ import annotations

REPERTOIRE = [
    {"id": "openevolve", "nom": "OpenEvolve", "qui": "Projet open source", "cible": "code", "cout": "gourmand", "paquet": "openevolve", "adaptateur": "CN_adaptateur_openevolve",
     "desc": "Version open source d'AlphaEvolve : îlots de populations et MAP-Elites, évaluation en parallèle, plusieurs objectifs à la fois.",
     "force": ["Très complet, multi-objectifs", "Grande communauté"], "lien": "https://github.com/algorithmicsuperintelligence/openevolve"},
    {"id": "shinka", "nom": "ShinkaEvolve", "qui": "Sakana AI · Apache 2.0", "cible": "code", "cout": "sobre", "paquet": "shinka-evolve", "adaptateur": "CN_adaptateur_shinka",
     "desc": "Sobre en essais : îlots, archive et sélection dynamique du modèle. Annonce de bons résultats en moins de 150 évaluations.",
     "force": ["Peu d'essais nécessaires", "Fonctionne avec des modèles locaux"], "lien": "https://github.com/SakanaAI/ShinkaEvolve"},
    {"id": "codeevolve", "nom": "CodeEvolve", "qui": "Projet open source", "cible": "code", "cout": "gourmand", "github": "inter-co/science-codeevolve", "paquet_nom": "codeevolve", "python": "3.13.5", "adaptateur": "CN_adaptateur_codeevolve",
     "desc": "Cadre évolutionnaire à îlots. Ses auteurs annoncent de bons résultats face à OpenEvolve et ShinkaEvolve (chiffres publiés par eux-mêmes).",
     "force": ["Résultats publiés élevés", "Mécanisme d'îlots"], "lien": "https://github.com/inter-co/science-codeevolve"},
    {"id": "gepa", "nom": "GEPA", "qui": "Projet open source", "cible": "texte", "cout": "sobre", "paquet": "gepa", "adaptateur": "CN_adaptateur_gepa",
     "desc": "Améliore des consignes et des politiques d'agents : il joue le candidat, lit ce qui a échoué, demande une réécriture, garde la frontière de Pareto.",
     "force": ["Pour les textes, pas le code", "Apprend des traces d'échec"], "lien": "https://github.com/gepa-ai/gepa"},
    {"id": "llm4ad", "nom": "LLM4AD", "qui": "Plateforme de recherche", "cible": "code", "cout": "inconnu", "paquet": "llm4ad", "memoire_mo": 4096, "reimplemente": "recherche d'heuristiques par grand modèle : plusieurs stratégies de réécriture, une réponse structurée, des variantes comparées entre elles", "adaptateur": None, "importer": ["llm4ad"],
     "desc": "Plateforme de conception d'algorithmes par grands modèles de langage (citée dans l'article de ShinkaEvolve).",
     "force": ["Pensée pour découvrir des algorithmes", "Plusieurs méthodes de recherche réunies"], "lien": "https://pypi.org/project/llm4ad/"},
    {"id": "openelm", "nom": "OpenELM", "qui": "CarperAI", "cible": "code", "cout": "inconnu", "paquet": "openelm", "memoire_mo": 4096, "reimplemente": "opérateur de mutation écrit par un modèle (ELM) : on mute la fonction de référence de plusieurs façons distinctes, en gardant des variantes de tailles de code différentes pour la diversité (idée de MAP-Elites)", "adaptateur": None, "importer": ["openelm"],
     "desc": "Boîte à outils d'évolution par grands modèles de langage : des opérateurs de mutation écrits par un modèle.",
     "force": ["Mutations écrites par un modèle", "Boîte à outils modulaire"], "lien": "https://pypi.org/project/openelm/"},
    {"id": "dspy", "nom": "DSPy", "qui": "Stanford", "cible": "texte", "cout": "sobre", "paquet": "dspy", "adaptateur": None, "importer": ["dspy"],
     "desc": "Cadre pour programmer des modèles de langage et optimiser automatiquement leurs consignes.",
     "force": ["Optimise des consignes sur des exemples", "Très répandu"], "lien": "https://pypi.org/project/dspy/"},
    {"id": "textgrad", "nom": "TextGrad", "qui": "Recherche", "cible": "texte", "cout": "sobre", "paquet": "textgrad", "adaptateur": None, "importer": ["textgrad"],
     "desc": "Optimisation de texte par retours en langage naturel, à la façon d'une descente de gradient.",
     "force": ["Améliore un texte pas à pas", "Idée simple et lisible"], "lien": "https://github.com/zou-group/textgrad"},
    {"id": "evoprompt", "nom": "EvoPrompt", "qui": "Article de recherche", "cible": "texte", "cout": "gourmand", "paquet": None, "adaptateur": None,
     "methode": "Évolution de consignes : une population de textes que l'on croise et fait muter (algorithme génétique ou évolution différentielle), chaque génération jugée sur des exemples.",
     "desc": "Évolution de consignes par algorithmes évolutionnaires : une population de textes qui se croisent et mutent. Il n'y a pas de paquet à installer : Cassandra réimplémente la méthode de l'article.",
     "force": ["Explore beaucoup de formulations", "Adapté aux consignes d'agents"], "lien": "https://github.com/beeevita/EvoPrompt"},
]
LIVRES = [
    {"id": "orfan", "nom": "Orfan", "qui": "Cassandra", "cible": "code", "cout": "sobre", "desc": "Le moteur de la maison : des recettes gratuites d'abord, puis un modèle guidé par la façon dont la fonction est appelée.",
     "force": ["Gratuit tant que les recettes suffisent", "Le plus testé : il tourne déjà"]},
    {"id": "frugal", "nom": "Frugal", "qui": "Cassandra", "cible": "code", "cout": "sobre", "desc": "Le chercheur économe : recettes d'abord ; sinon un modèle fort propose des idées, un modèle économe écrit le code.",
     "force": ["Dépense peu de jetons", "Ne s'active que sur les fonctions chaudes"]},
    {"id": "sedal", "nom": "Sedal", "qui": "Cassandra", "cible": "code", "cout": "gourmand", "desc": "Des générations de versions qui se croisent et mutent, avec une archive par taille de code.",
     "force": ["Explore largement", "Garde une archive de niches"]},
]


def trouver(ident: str) -> dict | None:
    return next((e for e in REPERTOIRE if e["id"] == ident), None)
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════
# EC : néant (c'est de la donnée : ce que l'écran propose).
# CN : le répertoire des chercheurs ; il ne décide de rien (le catalogue scellé et l'installateur gardent).
# LIEN : noyau/CN_epinglage.py (le répertoire devient catalogue), noyau/CN_installateur.py, modules/evolution (la coquille), interface/CN_evolution-ecran.js.
