"""Le chargeur : découvre les modules, vérifie leur isolation, les branche dans l'ordre de leurs dépendances.

Règle d'or : un module n'importe JAMAIS un autre module. Il parle par événements et par capacités,
jamais par import. C'est ce qui empêche de reconstruire un monolithe en morceaux.

Deux provenances de modules :
  - `modules/`     livrés avec le noyau (confiance « interne » permise) ;
  - `extensions/`  greffés après coup, hors des versions du noyau : un déploiement n'y touche jamais, et ils
                   ne peuvent pas se déclarer « interne ». On y dépose un dossier, on l'ajoute aux modules
                   actifs, et le noyau le branche à chaud.
"""
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

from . import manifeste as mf


def verifier_isolation(dossier: Path, autres_modules) -> list:
    """Défauts d'import : un module qui en cite un autre (import modules.x, from x import …)."""
    defauts, autres = [], set(autres_modules)
    for p in sorted(dossier.rglob("*.py")):
        try:
            arbre = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except SyntaxError as ex:
            defauts.append("%s : syntaxe invalide (%s)" % (p.name, ex.msg))
            continue
        for n in ast.walk(arbre):
            noms = []
            if isinstance(n, ast.Import):
                noms = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                noms = [("." * n.level) + (n.module or "")]
            for nom in noms:
                racine = nom.lstrip(".").split(".")[0]
                if racine == "modules" or racine in autres:
                    defauts.append("%s : importe « %s » (un module ne dépend d'un autre que par événements et capacités)" % (p.name, nom))
    return defauts


def charger_module_py(dossier: Path, mid: str):
    chemin = dossier / "module.py"
    if not chemin.exists():
        return None
    spec = importlib.util.spec_from_file_location("cassandra_module_%s" % mid, chemin)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def decouvrir_tout(racines):
    """`racines` : liste de (dossier, est_extension). Rend (manifestes, refus).
    Un défaut dans un module LIVRÉ avec le noyau est une erreur de développement : on lève. Un défaut dans une
    EXTENSION (manifeste illisible, confiance « interne », id déjà pris) ne doit jamais empêcher le noyau de
    démarrer : l'extension est écartée, et le refus est rendu pour être dit au bus."""
    ms, refus, vus, erreurs = [], [], {}, []
    for dossier, extension in racines:
        d = Path(dossier)
        if not d.is_dir():
            continue
        if not extension:
            try:
                trouves = mf.decouvrir(d)
            except mf.ManifesteInvalide as ex:
                erreurs.append(str(ex))
                continue
        else:
            trouves = []
            for f in sorted(d.glob("*/manifeste.toml")):
                try:
                    m = mf.charger(f)
                    if m.id != f.parent.name:
                        raise mf.ManifesteInvalide(["module.id « %s » différent du dossier « %s »" % (m.id, f.parent.name)], f)
                    trouves.append(m)
                except mf.ManifesteInvalide as ex:
                    refus.append({"module": f.parent.name, "raisons": ex.erreurs})
        for m in trouves:
            if m.id in vus:
                if extension:
                    refus.append({"module": m.id, "raisons": ["déjà présent dans %s" % vus[m.id]]})
                else:
                    erreurs.append("module « %s » présent dans %s et dans %s" % (m.id, vus[m.id], dossier))
                continue
            if extension and m.confiance == "interne":
                refus.append({"module": m.id, "raisons": ["la confiance « interne » est réservée aux modules livrés avec le noyau"]})
                continue
            vus[m.id] = dossier
            ms.append((m, extension))
    if erreurs:
        raise mf.ManifesteInvalide(erreurs)
    return ms, refus


def _ecarter(ms, refus, motifs, extension_ids):
    """Écarte les extensions citées dans `motifs` (« id »). Rend True si quelque chose a bougé."""
    cites = {i for i in extension_ids if any("« %s »" % i in x for x in motifs)}
    if not cites:
        return False
    for m, ext in list(ms):
        if m.id in cites:
            ms.remove((m, ext))
            refus.append({"module": m.id, "raisons": [x for x in motifs if "« %s »" % m.id in x][:3]})
    return True


def brancher(racines, fabriquer_contexte, catalogue, registre, actifs=None, deja=frozenset(), tolerant=False) -> dict:
    """Branche les modules ACTIFS (`actifs=None` : tous, pour le développement) qui ne le sont pas encore (`deja`).
    `racines` : un dossier, ou une liste de (dossier, est_extension). Rend un rapport : ordre, branches (les nouveaux),
    refuses (extensions écartées, avec leurs raisons), capacités non portées, modules sans code."""
    if isinstance(racines, (str, Path)):
        racines = [(racines, False)]
    ms, refus = decouvrir_tout(racines)
    refuses_ids = {r["module"] for r in refus}
    if actifs is not None:
        inconnus = sorted(set(actifs) - {m.id for m, _ in ms} - refuses_ids)
        if inconnus and not tolerant:
            raise mf.ManifesteInvalide(["module actif introuvable : " + ", ".join(inconnus)])
        ms = [(m, e) for m, e in ms if m.id in set(actifs)]
    # isolation : une extension qui en importe une autre est écartée ; pour un module livré, c'est une erreur
    for m, ext in list(ms):
        iso = verifier_isolation(Path(m.source).parent, [x.id for x, _ in ms if x.id != m.id])
        if iso and ext:
            ms.remove((m, ext))
            refus.append({"module": m.id, "raisons": iso})
        elif iso:
            raise mf.ManifesteInvalide(iso)
    ext_ids = {m.id for m, e in ms if e}
    while True:
        defauts = mf.verifier_ensemble([m for m, _ in ms])
        if not defauts:
            break
        if not _ecarter(ms, refus, defauts, ext_ids):
            raise mf.ManifesteInvalide(defauts)
        ext_ids = {m.id for m, e in ms if e}
    mods = [m for m, _ in ms]
    ordre = mf.ordre_installation(mods)
    par_id = {m.id: m for m in mods}
    rapport = {"ordre": ordre, "branches": [], "refuses": refus, "sans_code": [], "a_porter": [],
               "introuvables": sorted(set(actifs or ()) - {m.id for m, _ in ms} - refuses_ids) if tolerant else []}
    for mid in ordre:
        if mid in deja:
            continue
        m = par_id[mid]
        for o in m.objets:
            registre.declarer(m.id, o.type)
        catalogue.inscrire(m)
        ctx = fabriquer_contexte(m)
        code = charger_module_py(Path(m.source).parent, mid)
        rapport["branches"].append(mid)
        if code is None or not hasattr(code, "brancher"):
            rapport["sans_code"].append(mid)
            continue
        code.brancher(ctx)
    rapport["a_porter"] = [e.cle for e in catalogue.lister() if not e.implementee and e.actif]
    return rapport
