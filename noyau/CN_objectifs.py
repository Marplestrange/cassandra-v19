# ══════════════════════════════════════════════
# TITRE      : Les objectifs multiples et la frontière de Pareto
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #a6714b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Choisit parmi des variantes prouvées équivalentes quand plusieurs objectifs comptent (latence, mémoire, taille) : frontière de Pareto, poids, tolérance de régression.
# MÉTHODE    : tout est déterministe et sans horloge : une variante est admise si aucun objectif pesé ne régresse au-delà de la tolérance ; on garde la frontière, puis le meilleur score pesé.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a6714b ▼▼▼
"""Objectifs multiples (maquette d'Évolution, vue Juges).

Un objectif est un GAIN en pourcentage : positif = mieux que la référence. Les trois que le juge mesure : `latence` (à froid, déjà là), `memoire` (pic d'allocation d'une
entrée), `taille` (nombre de nœuds de l'arbre syntaxique). Un POIDS de zéro l'ignore : par défaut, seule la latence pèse, et le choix est exactement celui d'avant.

Une variante est ADMISE si, pour chaque objectif pesé, son gain n'est pas pire que `-tolerance` % (une variante deux fois plus rapide qui triple la mémoire n'est pas adoptée si
la mémoire pèse). Parmi les admises, la FRONTIÈRE de Pareto (aucune autre ne la domine sur tous les objectifs pesés) ; sur la frontière, le meilleur score pesé gagne.
"""
from __future__ import annotations

OBJECTIFS = ("latence", "memoire", "taille")
POIDS_DEFAUT = {"latence": 1.0, "memoire": 0.0, "taille": 0.0}
TOLERANCE_DEFAUT = 25.0


def poids_valides(poids: dict | None) -> dict:
    """Les poids retenus : les trois objectifs, chacun un nombre >= 0 ; un nom inconnu ou un poids négatif est refusé (une faute de frappe ne se tait pas)."""
    sortie = dict(POIDS_DEFAUT)
    for k, v in (poids or {}).items():
        if k not in OBJECTIFS:
            raise ValueError("objectif inconnu : « %s » (%s)" % (k, ", ".join(OBJECTIFS)))
        try:
            x = float(v)
        except (TypeError, ValueError):
            raise ValueError("poids invalide pour « %s » : %r" % (k, v))
        if x < 0 or x != x or x == float("inf"):
            raise ValueError("poids invalide pour « %s » : %r (>= 0 exigé)" % (k, v))
        sortie[k] = x
    if not any(sortie.values()):
        raise ValueError("au moins un objectif doit peser")
    return sortie


def _val(obj: dict, nom: str) -> float:
    v = (obj or {}).get(nom)
    return 0.0 if v is None else float(v)


def admise(obj: dict, poids: dict, tolerance: float = TOLERANCE_DEFAUT) -> bool:
    return all(_val(obj, k) >= -float(tolerance) for k, w in poids.items() if w > 0)


def score(obj: dict, poids: dict) -> float:
    return sum(w * _val(obj, k) for k, w in poids.items() if w > 0)


def domine(a: dict, b: dict, poids: dict) -> bool:
    """`a` domine `b` : au moins aussi bon sur chaque objectif pesé, strictement meilleur sur un."""
    ks = [k for k, w in poids.items() if w > 0]
    return all(_val(a, k) >= _val(b, k) for k in ks) and any(_val(a, k) > _val(b, k) for k in ks)


def frontiere(candidats: list, poids: dict) -> list:
    """Les indices des candidats (liste de dicts d'objectifs) qu'aucun autre ne domine."""
    return [i for i, a in enumerate(candidats) if not any(domine(b, a, poids) for j, b in enumerate(candidats) if j != i)]


def choisir(candidats: list, poids: dict | None = None, tolerance: float = TOLERANCE_DEFAUT) -> dict:
    """`candidats` : liste de dicts {"objectifs": {...}, ...}. Rend {"meilleur": index|None, "frontiere": [index], "ecartes": [{"index", "raison"}]}."""
    poids = poids_valides(poids)
    admis, ecartes = [], []
    for i, c in enumerate(candidats):
        if admise(c.get("objectifs"), poids, tolerance):
            admis.append(i)
        else:
            pire = min((k for k, w in poids.items() if w > 0), key=lambda k: _val(c.get("objectifs"), k))
            ecartes.append({"index": i, "raison": "%s régresse de %s %% (tolérance %s %%)" % (pire, round(-_val(c.get("objectifs"), pire), 1), tolerance)})
    if not admis:
        return {"meilleur": None, "frontiere": [], "ecartes": ecartes}
    objs = [candidats[i].get("objectifs") for i in admis]
    front = [admis[k] for k in frontiere(objs, poids)]
    meilleur = max(front, key=lambda i: (score(candidats[i].get("objectifs"), poids), -i))
    return {"meilleur": meilleur, "frontiere": front, "ecartes": ecartes}


def taille_ast(source: str) -> int:
    """Le nombre de nœuds de l'arbre syntaxique : une mesure de taille qui ne dépend ni des espaces ni des commentaires."""
    import ast
    return sum(1 for _ in ast.walk(ast.parse(source)))


def gain_pct(avant: float, apres: float):
    """Le gain d'un objectif où MOINS est mieux : (avant - après) / avant. None si la référence est nulle (rien à comparer)."""
    if not avant:
        return None
    return round(100.0 * (avant - apres) / avant, 2)
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (le choix entre variantes est une décision du noyau, pas une chose qu'on évolue).
# CN : les poids, la tolérance, la frontière de Pareto, le score ; aucune mesure ici, seulement des décisions sur des mesures.
# LIEN : noyau/CN_evaluateur.py (qui mesure), noyau/CN_evolution.py (qui choisit), modules/evolution (le réglage des poids).
