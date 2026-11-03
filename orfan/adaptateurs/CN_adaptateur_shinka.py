# ══════════════════════════════════════════════
# TITRE      : L'adaptateur de ShinkaEvolve
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #839958
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Fait chercher ShinkaEvolve (Sakana AI) sur un point d'évolution de Cassandra : son modèle est le serveur « OpenAI » local de la cage, son évaluation compare aux sorties de la référence.
# MÉTHODE    : `local/<modèle>@<url>` est la façon native de Shinka de parler à un serveur compatible OpenAI ; son script d'évaluation est écrit à la volée ; ses programmes sont relus dans sa base SQLite.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=839958 ▼▼▼
"""Adaptateur du moteur externe ShinkaEvolve (paquet `shinka-evolve`, https://github.com/SakanaAI/ShinkaEvolve).

Shinka lance un script d'évaluation par programme (`evaluate.py --program_path … --results_dir …`, qui écrit `metrics.json` et `correct.json`). Ce script est écrit ici : il charge la
fonction du programme, la compare aux sorties de la RÉFÉRENCE sur les entrées visibles, et rend comme score le rapport des temps. Aucun plongement (embedding) n'est demandé : il aurait besoin d'un
service que la cage ne donne pas.
"""
import json
import os
import sqlite3
import sys
import tempfile

IMPORTER = ["shinka", "shinka.core"]

EVALUER = r'''
import argparse, copy, importlib.util, json, os, time

FONCTION = %(fonction)r
ENTREES = json.load(open(%(entrees)r, encoding="utf-8"))
ATTENDU = json.load(open(%(attendu)r, encoding="utf-8"))
T_REF = %(t_ref)r


def mesure(f):
    meilleur = None
    for _ in range(2):
        t = 0
        for e in ENTREES:
            x = copy.deepcopy(e)
            d0 = time.perf_counter_ns()
            f(x)
            t += time.perf_counter_ns() - d0
        meilleur = t if meilleur is None else min(meilleur, t)
    return meilleur


ap = argparse.ArgumentParser()
ap.add_argument("--program_path", required=True)
ap.add_argument("--results_dir", required=True)
a = ap.parse_args()
os.makedirs(a.results_dir, exist_ok=True)
correct, erreur, score, retour = False, None, 0.0, ""
try:
    spec = importlib.util.spec_from_file_location("programme", a.program_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    f = getattr(mod, FONCTION)
    for i, (e, att) in enumerate(zip(ENTREES, ATTENDU)):
        obtenu = json.dumps(f(copy.deepcopy(e)), ensure_ascii=False, separators=(",", ":"))
        if obtenu != att:
            raise ValueError("divergence à l'entrée %%d : attendu %%s, obtenu %%s" %% (i, att[:100], obtenu[:100]))
    t = mesure(f)
    score = (T_REF / t) if t else 0.0
    correct = True
    retour = "équivalent, ×%%.2f sur le vu" %% score
except Exception as e:
    erreur = "%%s : %%s" %% (type(e).__name__, str(e)[:300])
    retour = erreur
json.dump({"combined_score": float(score), "public": {"rapport_de_temps": round(score, 4)}, "private": {}, "extra_data": {}, "text_feedback": retour},
          open(os.path.join(a.results_dir, "metrics.json"), "w", encoding="utf-8"))
json.dump({"correct": correct, "error": erreur}, open(os.path.join(a.results_dir, "correct.json"), "w", encoding="utf-8"))
'''


def _preparer(dossier, source, fonction, entrees):
    import copy
    import time
    sujet = [copy.deepcopy(e) for e in entrees[:24]]
    ns = {}
    exec(compile(source, "<reference>", "exec"), ns)
    ref = ns[fonction]
    attendu = [json.dumps(ref(copy.deepcopy(e)), ensure_ascii=False, separators=(",", ":")) for e in sujet]
    meilleur = None
    for _ in range(2):
        t = 0
        for e in sujet:
            x = copy.deepcopy(e)
            d0 = time.perf_counter_ns()
            ref(x)
            t += time.perf_counter_ns() - d0
        meilleur = t if meilleur is None else min(meilleur, t)
    chemins = {"entrees": os.path.join(dossier, "entrees.json"), "attendu": os.path.join(dossier, "attendu.json")}
    json.dump(sujet, open(chemins["entrees"], "w", encoding="utf-8"))
    json.dump(attendu, open(chemins["attendu"], "w", encoding="utf-8"))
    return EVALUER % dict(fonction=fonction, entrees=chemins["entrees"], attendu=chemins["attendu"], t_ref=meilleur)


def _a_des_programmes(chemin):
    try:
        con = sqlite3.connect(chemin)
        try:
            return con.execute("SELECT COUNT(*) FROM programs").fetchone()[0] > 0
        finally:
            con.close()
    except sqlite3.Error:
        return False


def proposer(contexte, modele):
    from shinka.core import EvolutionConfig, ShinkaEvolveRunner
    from shinka.database import DatabaseConfig
    from shinka.launch import LocalJobConfig

    source, fonction, entrees = contexte["source_reference"], contexte["fonction"], contexte.get("entrees") or []
    budget = max(1, int(contexte.get("budget", 3)))
    dossier = tempfile.mkdtemp(prefix="shinka_cage_")
    evaluer = _preparer(dossier, source, fonction, entrees)
    programme = "# EVOLVE-BLOCK-START\n" + source.rstrip("\n") + "\n# EVOLVE-BLOCK-END\n"
    base = os.path.join(dossier, "base.sqlite")
    evo = EvolutionConfig(num_generations=max(2, budget * 2), llm_models=["local/relais@" + modele.url], llm_dynamic_selection=None, embedding_model=None, meta_rec_interval=None,
                          results_dir=os.path.join(dossier, "resultats"), init_program_path=os.path.join(dossier, "initial.py"), job_type="local", language="python", max_novelty_attempts=1,
                          patch_types=["full"], patch_type_probs=[1.0])
    runner = ShinkaEvolveRunner(evo_config=evo, job_config=LocalJobConfig(eval_program_path=os.path.join(dossier, "evaluate.py"), python_executable=sys.executable),
                                db_config=DatabaseConfig(db_path=base, num_islands=1, archive_size=max(8, budget * 3)), verbose=False, max_evaluation_jobs=1, max_proposal_jobs=1,
                                init_program_str=programme, evaluate_str=evaluer)
    runner.run()
    sortie = []
    try:
        base = next((c for c in (os.path.join(evo.results_dir, "programs.sqlite"), base) if os.path.exists(c) and os.path.getsize(c) > 0 and _a_des_programmes(c)), base)       # Shinka range sa base dans le dossier des résultats
        con = sqlite3.connect(base)
        for code, score, correct in con.execute("SELECT code, combined_score, correct FROM programs WHERE correct=1 ORDER BY combined_score DESC"):
            texte = code.replace("# EVOLVE-BLOCK-START", "").replace("# EVOLVE-BLOCK-END", "").strip() + "\n"
            if score and score > 1.0 and texte.strip() != source.strip() and all(t["texte"] != texte for t in sortie):
                sortie.append({"texte": texte, "hypothese": "ShinkaEvolve : variante ×%.2f sur le vu" % score, "origine": "shinka"})
        con.close()
    except sqlite3.Error:
        pass
    return sortie[:budget]
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un adaptateur ne s'évolue pas).
# CN : le pont entre le contrat de Cassandra et le runner de ShinkaEvolve ; il ne juge jamais, il rend des textes.
# LIEN : orfan/CN_moteur_hote.py (le serveur OpenAI local de la cage), noyau/CN_installateur.py, outils/CN_moteurs_epingler.py.
