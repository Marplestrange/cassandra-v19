"""Le chargeur : découvre les modules, vérifie leur isolation, les branche dans l'ordre de leurs dépendances.

Règle d'or : un module n'importe JAMAIS un autre module. Il parle par événements et par capacités,
jamais par import. C'est ce qui empêche de reconstruire un monolithe en morceaux.
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


def brancher(racine_modules, fabriquer_contexte, catalogue, registre, actifs=None) -> dict:
    """Branche les modules ACTIFS (`actifs=None` : tous, pour le développement). `fabriquer_contexte(manifeste)`
    rend le Contexte du module. Rend un rapport : ordre, capacités non portées, modules sans code."""
    racine = Path(racine_modules)
    ms = mf.decouvrir(racine)
    if actifs is not None:
        inconnus = sorted(set(actifs) - {m.id for m in ms})
        if inconnus:
            raise mf.ManifesteInvalide(["module actif introuvable dans modules/ : " + ", ".join(inconnus)], racine)
        ms = [m for m in ms if m.id in set(actifs)]
    defauts = mf.verifier_ensemble(ms)
    ids = [m.id for m in ms]
    for m in ms:
        defauts += verifier_isolation(racine / m.id, [i for i in ids if i != m.id])
    if defauts:
        raise mf.ManifesteInvalide(defauts, racine)
    ordre = mf.ordre_installation(ms)
    par_id = {m.id: m for m in ms}
    rapport = {"ordre": ordre, "sans_code": [], "a_porter": []}
    for mid in ordre:
        m = par_id[mid]
        for o in m.objets:
            registre.declarer(m.id, o.type)
        catalogue.inscrire(m)
        ctx = fabriquer_contexte(m)
        code = charger_module_py(racine / mid, mid)
        if code is None or not hasattr(code, "brancher"):
            rapport["sans_code"].append(mid)
            continue
        code.brancher(ctx)
    rapport["a_porter"] = [e.cle for e in catalogue.lister() if not e.implementee]
    return rapport
