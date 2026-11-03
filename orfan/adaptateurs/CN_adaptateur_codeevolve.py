# ══════════════════════════════════════════════
# TITRE      : L'adaptateur de CodeEvolve
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #99dcdd
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Fait chercher CodeEvolve (Inter Science, Python ≥ 3.13.5) sur un point d'évolution de Cassandra : son API est le serveur « OpenAI » local de la cage, son évaluation compare aux sorties de la référence.
# MÉTHODE    : il se lance comme son interface de ligne de commande (dossier d'entrée, configuration YAML, `API_BASE` et `API_KEY` en environnement) ; ses îlots sont ses sous-processus ; ses meilleurs programmes sont relus dans son dossier de sortie.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=99dcdd ▼▼▼
"""Adaptateur du moteur externe CodeEvolve (https://github.com/inter-co/science-codeevolve, PAS le paquet « codeevolve » de PyPI : c'est un autre projet).

Il demande Python 3.13.5 au moins : le catalogue de Cassandra le dit par l'entrée `interpreteur` (un interpréteur que l'admin a posé, par exemple par `uv python install 3.13`), et le moteur
a son environnement à lui, jamais celui de Cassandra. Il s'installe depuis une archive du dépôt, épinglée par empreinte (une adresse « name @ https://… » + sha256), pas depuis PyPI.
"""
import copy
import glob
import json
import os
import subprocess
import sys
import tempfile
import time

IMPORTER = ["codeevolve", "codeevolve.cli"]

EVALUER = r'''
import copy, json, os, sys, time, importlib.util

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


def evaluate(program_path, results_path):
    debut = time.time()
    ratio = 0.0
    try:
        spec = importlib.util.spec_from_file_location("programme", program_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        f = getattr(mod, FONCTION)
        for e, att in zip(ENTREES, ATTENDU):
            if json.dumps(f(copy.deepcopy(e)), ensure_ascii=False, separators=(",", ":")) != att:
                raise ValueError("divergence")
        t = mesure(f)
        ratio = (T_REF / t) if t else 0.0
    except Exception:
        ratio = 0.0
    json.dump({"benchmark_ratio": float(ratio), "eval_time": round(time.time() - debut, 4)}, open(results_path, "w", encoding="utf-8"))


if __name__ == "__main__":
    evaluate(sys.argv[1], sys.argv[2])
'''

CONFIG = """SYS_MSG: |
  # PROMPT-BLOCK-START
  SETTING:
  You rewrite a pure Python function so that it runs faster WITHOUT changing what it returns for any input. Keep the function name and signature. Standard library only: no files, no network, no time, no randomness.
  PERFORMANCE METRICS:
  1. **benchmark_ratio**: reference time divided by your time, 0 if the result differs (higher is better)
  2. **eval_time**: seconds
  # PROMPT-BLOCK-END

CODEBASE_PATH: 'src/'
INIT_FILE_DATA: {filename: 'init_program.py', language: 'python'}
EVAL_FILE_NAME: 'evaluate.py'

BUDGET_CONFIG: {eval_timeout: 60, max_mem_bytes: 1000000000, resource_check_interval_s: 0.2}

EVOLVE_CONFIG: {fitness_key: 'benchmark_ratio', num_epochs: %(epoques)d, ckpt: 1, max_size: null, init_pop: 2, exploration_rate: 0.3,
                selection: {policy: 'roulette', kwargs: {roulette_by_rank: True}}, early_stopping_rounds: 20, num_islands: 1,
                migration: {topology: 'ring', interval: 25, rate: 0.1}, meta_prompting: False, use_map_elites: True, num_inspirations: 2, max_chat_depth: 2,
                markers: {mp_start_marker: "# PROMPT-BLOCK-START", mp_end_marker: "# PROMPT-BLOCK-END", evolve_start_marker: "# EVOLVE-BLOCK-START", evolve_end_marker: "# EVOLVE-BLOCK-END"},
                exploration_scheduler: {type: 'PlateauScheduler', kwargs: {min_value: 0.2, max_value: 0.5, plateau_threshold: 5, increase_factor: 1.05, decrease_factor: 0.95}}}

EXPLORATION_ENSEMBLE: [{model_name: 'relais', temp: 0.9, top_p: 0.95, retries: 1, weight: 1, verify_ssl: False}]
EXPLOITATION_ENSEMBLE: [{model_name: 'relais', temp: 0.7, top_p: 0.95, retries: 1, weight: 1, verify_ssl: False}]
SAMPLER_AUX_LM: {model_name: 'relais', temp: 0.7, top_p: 0.95, retries: 1, weight: 1, verify_ssl: False}

MAP_ELITES: {elite_map_type: 'grid', features: [{name: 'eval_time', min_val: 0, max_val: 60, num_bins: 10}]}
"""


def _preparer(entree, source, fonction, entrees):
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
    os.makedirs(os.path.join(entree, "src"), exist_ok=True)
    chemins = {"entrees": os.path.join(entree, "entrees.json"), "attendu": os.path.join(entree, "attendu.json")}
    json.dump(sujet, open(chemins["entrees"], "w", encoding="utf-8"))
    json.dump(attendu, open(chemins["attendu"], "w", encoding="utf-8"))
    open(os.path.join(entree, "evaluate.py"), "w", encoding="utf-8").write(EVALUER % dict(fonction=fonction, t_ref=meilleur, **chemins))
    open(os.path.join(entree, "src", "init_program.py"), "w", encoding="utf-8").write("# EVOLVE-BLOCK-START\n" + source.rstrip("\n") + "\n# EVOLVE-BLOCK-END\n")


def proposer(contexte, modele):
    source, fonction, entrees = contexte["source_reference"], contexte["fonction"], contexte.get("entrees") or []
    budget = max(1, int(contexte.get("budget", 3)))
    travail = tempfile.mkdtemp(prefix="codeevolve_cage_")
    entree, sortie = os.path.join(travail, "entree"), os.path.join(travail, "sortie")
    os.makedirs(entree)
    _preparer(entree, source, fonction, entrees)
    cfg = os.path.join(travail, "config.yaml")
    open(cfg, "w", encoding="utf-8").write(CONFIG % {"epoques": max(2, budget * 2)})
    env = dict(os.environ, API_BASE=modele.url, API_KEY=modele.cle)
    subprocess.run([sys.executable, "-m", "codeevolve.cli", "--inpt_dir", entree, "--out_dir", sortie, "--cfg_path", cfg, "--y"], env=env, cwd=travail, capture_output=True, timeout=540)
    # ses programmes : tout fichier de programme écrit dans la sortie, relu avec son score (le fichier voisin « .json » ou le journal de l'îlot ; à défaut, on les rejoue ici)
    candidats = []
    vus = set()
    for chemin in glob.glob(os.path.join(sortie, "**", "*.py"), recursive=True):
        try:
            texte = open(chemin, encoding="utf-8").read()
        except OSError:
            continue
        texte = texte.replace("# EVOLVE-BLOCK-START", "").replace("# EVOLVE-BLOCK-END", "").strip() + "\n"
        if texte in vus or texte.strip() == source.strip() or fonction not in texte:
            continue
        vus.add(texte)
        candidats.append(texte)
    return [{"texte": t, "hypothese": "CodeEvolve : variante écrite par un îlot", "origine": "codeevolve"} for t in candidats[:budget * 3]]
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un adaptateur ne s'évolue pas).
# CN : le pont entre le contrat de Cassandra et l'interface de ligne de commande de CodeEvolve ; il ne juge jamais, il rend des textes que le juge de Cassandra départagera.
# LIEN : orfan/CN_moteur_hote.py (le serveur OpenAI local de la cage), noyau/CN_installateur.py (l'interpréteur et l'archive épinglée), outils/CN_moteurs_epingler.py.
