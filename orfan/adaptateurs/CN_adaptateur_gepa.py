# ══════════════════════════════════════════════
# TITRE      : L'adaptateur de GEPA
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #1edd6c
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Fait chercher GEPA (optimisation réflexive de texte, frontière de Pareto) sur un point d'évolution de Cassandra : sa réflexion passe par le relais de modèles de la cage.
# MÉTHODE    : `optimize_anything` ; la graine est la fonction de référence ; le score est le rapport de temps d'une variante ÉQUIVALENTE ; une variante fausse dit POURQUOI (la première entrée divergente) : c'est ce que la réflexion lit.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1edd6c ▼▼▼
"""Adaptateur du moteur externe GEPA (paquet `gepa`, https://github.com/gepa-ai/gepa).

GEPA améliore un texte par réflexion : il joue le candidat, lit ce qui a échoué, demande à un modèle de réécrire, et garde la frontière de Pareto. Ici le texte est le code d'une fonction.
Son « modèle de réflexion » est une simple fonction qui demande le relais (`modele(prompt, "strategie")`) : il n'a ni clé ni réseau. Le juge de Cassandra décide ensuite de tout.
"""
import copy
import json
import re
import time

IMPORTER = ["gepa", "gepa.optimize_anything"]


def _canon(v):
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def _code(texte):
    """GEPA peut rendre le code entouré de prose ou de ``` : on garde le bloc python s'il y en a un."""
    m = re.search(r"```(?:python)?\s*\n(.*?)```", texte, re.S)
    return (m.group(1) if m else texte).strip() + "\n"


def _evaluateur(source, fonction, entrees):
    sujet = [copy.deepcopy(e) for e in entrees[:24]]

    def charger(texte):
        ns = {}
        exec(compile(texte, "<gepa>", "exec"), ns)
        return ns[fonction]

    ref = charger(source)
    attendu = [_canon(ref(copy.deepcopy(e))) for e in sujet]

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

    def evaluer(candidat):
        texte = _code(candidat if isinstance(candidat, str) else next(iter(candidat.values())))
        try:
            cand = charger(texte)
            for i, (e, a) in enumerate(zip(sujet, attendu)):
                obtenu = _canon(cand(copy.deepcopy(e)))
                if obtenu != a:
                    return 0.0, {"erreur": "divergence à l'entrée %d : attendu %s, obtenu %s" % (i, a[:120], obtenu[:120])}
            t = mesure(cand)
        except Exception as e:
            return 0.0, {"erreur": "%s : %s" % (type(e).__name__, str(e)[:200])}
        rapport = (t_ref / t) if t else 0.0
        return float(rapport), {"rapport_de_temps": round(rapport, 3), "equivalent": True}
    return evaluer


def proposer(contexte, modele):
    from gepa.optimize_anything import EngineConfig, GEPAConfig, ReflectionConfig, optimize_anything

    source, fonction, entrees = contexte["source_reference"], contexte["fonction"], contexte.get("entrees") or []
    budget = max(1, int(contexte.get("budget", 3)))
    vus = {}
    evaluer = _evaluateur(source, fonction, entrees)

    def evaluer_et_noter(candidat):
        score, info = evaluer(candidat)
        texte = _code(candidat if isinstance(candidat, str) else next(iter(candidat.values())))
        if info.get("equivalent") and score > 1.0:
            vus[texte] = max(vus.get(texte, 0.0), score)
        return score, info

    def reflexion(prompt):
        if not isinstance(prompt, str):
            prompt = "\n\n".join(str(m.get("content", "")) for m in prompt)
        return modele(prompt, "strategie")                    # le relais : compté, plafonné, sans clé

    cfg = GEPAConfig(engine=EngineConfig(max_metric_calls=budget * 6, parallel=False, display_progress_bar=False, raise_on_exception=False, use_cloudpickle=False),
                     reflection=ReflectionConfig(reflection_lm=reflexion))
    optimize_anything(seed_candidate=source, evaluator=evaluer_et_noter, objective="Réécris la fonction pour qu'elle s'exécute plus vite SANS changer ce qu'elle rend pour aucune entrée ; rends le code complet.",
                      background="Python pur : bibliothèque standard seulement, ni fichier, ni réseau, ni heure, ni hasard. Le nom et la signature de la fonction ne changent pas.", config=cfg)
    classes = sorted(vus.items(), key=lambda kv: -kv[1])
    return [{"texte": t, "hypothese": "GEPA : variante ×%.2f sur le vu" % s, "origine": "gepa"} for t, s in classes[:budget] if t.strip() != source.strip()]
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un adaptateur ne s'évolue pas).
# CN : le pont entre le contrat de Cassandra et optimize_anything de GEPA ; il ne juge jamais, il rend des textes.
# LIEN : orfan/CN_moteur_hote.py (le relais), noyau/CN_installateur.py, outils/CN_moteurs_epingler.py.
