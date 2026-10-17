"""Le chargeur : découvre les modules, vérifie leur isolation, les branche dans l'ordre de leurs dépendances.

Règle d'or : un module n'importe JAMAIS un autre module. Il parle par événements et par capacités,
jamais par import. C'est ce qui empêche de reconstruire un monolithe en morceaux.

Deux provenances de modules :
  - `modules/`     livrés avec le noyau (confiance « interne » permise) ;
  - `extensions/`  greffés après coup, hors des versions du noyau : un déploiement n'y touche jamais, et ils
                   ne peuvent pas se déclarer « interne ». On y dépose un dossier, on l'ajoute aux modules
                   actifs, et le noyau le branche à chaud.

Surcharge (comme `custom` l'emporte sur `htdocs` dans Dolibarr) : une extension qui porte l'identifiant d'un module livré LE REMPLACE.
Le module livré est alors mis de côté, jamais perdu : si le remplaçant est écarté, il revient. Un module ESSENTIEL (le « core/ » de Cassandra,
que Dolibarr exclut de la surcharge) ne se remplace que si l'administrateur l'a décidé ([surcharge] essentiels = ["droits"]) : un réglage, pas un interdit.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

from . import CN_manifeste as mf


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
    chemin = dossier / "CN_module.py"
    if not chemin.exists():
        return None
    nom = "cassandra_module_%s" % mid
    for k in [k for k in sys.modules if k == nom or k.startswith(nom + ".")]:
        del sys.modules[k]                                          # un rechargement ne doit pas retrouver les fichiers d'avant
    # Le module est un PAQUET de son dossier : `from . import outils` y trouve ses fichiers d'aide, et rien d'autre (pas de collision entre modules).
    spec = importlib.util.spec_from_file_location(nom, chemin, submodule_search_locations=[str(dossier)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nom] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(nom, None)
        raise
    return mod


def decouvrir_tout(racines, surcharges=(), remplaces=None):
    """`racines` : liste de (dossier, est_extension). Rend (manifestes, refus).
    `surcharges` : les modules essentiels que l'administrateur autorise à remplacer. `remplaces` (un dict, s'il est donné) reçoit
    {id: manifeste livré mis de côté} pour chaque module livré qu'une extension remplace.
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
            for f in sorted(d.glob("*/CN_manifeste.toml")):
                try:
                    m = mf.charger(f)
                    if m.id != f.parent.name:
                        raise mf.ManifesteInvalide(["module.id « %s » différent du dossier « %s »" % (m.id, f.parent.name)], f)
                    trouves.append(m)
                except mf.ManifesteInvalide as ex:
                    refus.append({"module": f.parent.name, "raisons": ex.erreurs})
        for m in trouves:
            if m.id in vus:
                if not extension:
                    erreurs.append("module « %s » présent dans %s et dans %s" % (m.id, vus[m.id], dossier))
                    continue
                livre = next(x for x, e in ms if x.id == m.id)
                if m.confiance == "interne":
                    refus.append({"module": m.id, "raisons": ["la confiance « interne » est réservée aux modules livrés avec le noyau"]})
                elif vus[m.id] in [r for r, e in racines if e]:
                    refus.append({"module": m.id, "raisons": ["déjà présent dans %s" % vus[m.id]]})      # deux extensions de même nom
                elif livre.essentiel and m.id not in set(surcharges):
                    refus.append({"module": m.id, "raisons": [
                        "« %s » est un module essentiel : le remplacer est un réglage de l'administrateur ([surcharge] essentiels = [\"%s\"])" % (m.id, m.id)]})
                else:
                    ms[:] = [(x, e) for x, e in ms if x.id != m.id]          # le module livré est mis de côté, pas perdu
                    if remplaces is not None:
                        remplaces[m.id] = livre
                    vus[m.id] = dossier
                    ms.append((m, extension))
                continue
            if extension and m.confiance == "interne":
                refus.append({"module": m.id, "raisons": ["la confiance « interne » est réservée aux modules livrés avec le noyau"]})
                continue
            vus[m.id] = dossier
            ms.append((m, extension))
    if erreurs:
        raise mf.ManifesteInvalide(erreurs)
    return ms, refus


def _ecarter(ms, refus, motifs, extension_ids, remplaces=None):
    """Écarte les extensions citées dans `motifs` (« id »). Rend True si quelque chose a bougé.
    Un remplaçant écarté rend sa place au module livré qu'il remplaçait."""
    cites = {i for i in extension_ids if any("« %s »" % i in x for x in motifs)}
    if not cites:
        return False
    for m, ext in list(ms):
        if m.id in cites:
            ms.remove((m, ext))
            raisons = [x for x in motifs if "« %s »" % m.id in x][:3]
            if remplaces and m.id in remplaces:
                ms.append((remplaces.pop(m.id), False))
                raisons.append("le module livré « %s » reprend sa place" % m.id)
            refus.append({"module": m.id, "raisons": raisons})
    return True


def brancher(racines, fabriquer_contexte, catalogue, registre, actifs=None, deja=frozenset(), tolerant=False, surcharges=()) -> dict:
    """Branche les modules ACTIFS (`actifs=None` : tous, pour le développement) qui ne le sont pas encore (`deja`).
    `racines` : un dossier, ou une liste de (dossier, est_extension). Rend un rapport : ordre, branches (les nouveaux),
    refuses (extensions écartées, avec leurs raisons), capacités non portées, modules sans code."""
    if isinstance(racines, (str, Path)):
        racines = [(racines, False)]
    remplaces = {}
    ms, refus = decouvrir_tout(racines, surcharges, remplaces)
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
            if m.id in remplaces:
                ms.append((remplaces.pop(m.id), False))
                iso = iso + ["le module livré « %s » reprend sa place" % m.id]
            refus.append({"module": m.id, "raisons": iso})
        elif iso:
            raise mf.ManifesteInvalide(iso)
    ext_ids = {m.id for m, e in ms if e}
    while True:
        defauts = mf.verifier_ensemble([m for m, _ in ms])
        if not defauts:
            break
        if not _ecarter(ms, refus, defauts, ext_ids, remplaces):
            raise mf.ManifesteInvalide(defauts)
        ext_ids = {m.id for m, e in ms if e}
    mods = [m for m, _ in ms]
    ordre = mf.ordre_installation(mods)
    par_id = {m.id: m for m in mods}
    rapport = {"ordre": ordre, "branches": [], "refuses": refus, "sans_code": [], "a_porter": [],
               "remplaces": {i: {"livre": l.version, "extension": par_id[i].version} for i, l in remplaces.items() if i in par_id},
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
        try:
            code.brancher(ctx)
        except Exception as ex:                  # un module qui ne se branche pas est écarté ET dit ; il n'empêche pas les autres de démarrer
            rapport["branches"].remove(mid)
            catalogue.desactiver_module(mid)
            refus.append({"module": mid, "raisons": ["le branchement a échoué : %s" % str(ex)[:300]]})
    rapport["a_porter"] = [e.cle for e in catalogue.lister() if not e.implementee and e.actif]
    return rapport
