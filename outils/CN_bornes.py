#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Outil de bornes : contrôle du format universel des fichiers
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #abf851
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : lit tous les fichiers suivis par git et dit s'ils respectent docs/CN_FORMAT.md (nom, en-tête, bornes, pureté des EC).
# MÉTHODE    : analyse textuelle et arbre syntaxique Python ; mode audit par défaut (rien ne bloque), --strict pour l'intégration continue.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=abf851 ▼▼▼
"""Outil de bornes. Usage :
    python outils/CN_bornes.py                 audit de tout le dépôt (résumé par module)
    python outils/CN_bornes.py --module vue    un seul module
    python outils/CN_bornes.py --fichier F     un fichier, avec le détail
    python outils/CN_bornes.py --json          sortie lisible par un programme
    python outils/CN_bornes.py --strict        code de sortie 1 s'il reste des erreurs (intégration continue)
    python outils/CN_bornes.py --sceller [F]   recalcule et écrit les empreintes (un fichier, ou tous)
    python outils/CN_bornes.py --monter M V    monte la version du module M à V partout (manifeste, en-têtes, marqueurs), puis scelle
Le mode par défaut est l'AUDIT : il informe, il ne bloque rien.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Seule liste fermée : les noms imposés par un outil extérieur (docs/CN_FORMAT.md §3 bis).
NOMS_IMPOSES = {"__init__.py", "LICENSE", "README.md", ".gitignore", ".gitattributes", "__pycache__"}
PREFIXES = ("CN_", "EC_")
CHAMPS = ("TITRE", "LICENCE", "AUTEUR", "GIT", "MAIL", "MODULE", "ZONE", "VERSION CN", "VERSION EC", "RÔLE", "MÉTHODE")
CHAMPS_EC = ("RUNTIME", "HÔTE CN")                  # en plus, pour un fichier de ZONE EC : l'environnement d'exécution (python, wasm, node, php…) et l'hôte
CONSTANTES = {"LICENCE": "AGPL-3.0", "AUTEUR": "Atek Drisse", "GIT": "github.com/Marplestrange", "MAIL": "marplestrange@cassandra.center"}
COMMENTAIRE = {".py": "#", ".sh": "#", ".toml": "#", ".yml": "#", ".yaml": "#", ".js": "//", ".mjs": "//", ".ts": "//", ".php": "//", ".rs": "//", ".go": "//",
               ".c": "//", ".css": "/*", ".html": "<!--", ".md": "<!--", ".service": "#", ".path": "#", ".in": "#", ".wat": ";;"}
# Fichiers qui ne portent pas leur en-tête : le JSON n'a pas de commentaires ; le SQL des migrations est IMMUABLE (somme de contrôle du contenu) ;
# le binaire (.wasm) n'est pas du texte. Un fichier compagnon « nom.ext.borne » porte alors l'en-tête.
SANS_COMMENTAIRE = {".json", ".sql", ".wasm", ".bin"}
STDLIB_PURE = {"__future__", "math", "re", "json", "itertools", "functools", "collections", "dataclasses", "typing", "enum", "fractions",
               "decimal", "string", "textwrap", "unicodedata", "operator", "copy", "heapq", "bisect", "statistics", "hashlib", "base64",
               "struct", "ec_api", "abc", "numbers", "ipaddress", "datetime", "shlex"}
ATTRIBUTS_INTERDITS = {"now", "today", "utcnow", "fromtimestamp", "utcfromtimestamp", "monotonic", "perf_counter", "random", "randint", "choice", "shuffle", "uuid4", "urandom"}
NOMS_INTERDITS = {"ctx", "self", "cls", "open", "print", "input", "exec", "eval", "__import__", "compile", "globals", "locals"}
INDICES_DECISIFS = ("verif", "signature", "droit", "secret", "mdp", "password", "token", "jeton", "auth", "permission", "autoris", "chiffr", "empreinte", "hash")
IGNORER_DOSSIERS = {".git", "__pycache__", "brouillons", "donnees", "node_modules", ".venv", "venv", ".pytest_cache"}      # sans git (le dépôt arrive par tar), ce que git ignorerait

RE_CHAMP = re.compile(r"^\s*(?:#|//|--|/\*|<!--|\*)?\s*(" + "|".join(re.escape(c) for c in CHAMPS + ("EC LIÉES", "HÔTE CN", "NEXUS VISÉ", "CONTRAT PROUVÉ", "RUNTIME")) + r")\s*:\s*(.*?)\s*(?:-->|\*/)?\s*$")
RE_BORNE_CN = re.compile(r"BORNE CN version=(\S+) empreinte=([0-9a-f]+)")
RE_BORNE_EC = re.compile(r"BORNE EC point=(\S+) contrat=@(\S+) version=(\S+) empreinte=([0-9a-f]+)")


def fichiers_suivis() -> list[str]:
    try:
        sortie = subprocess.run(["git", "ls-files"], cwd=RACINE, capture_output=True, text=True, check=True).stdout
        return [l for l in sortie.splitlines() if l]
    except Exception:
        out = []
        for r, ds, fs in os.walk(RACINE):
            ds[:] = [d for d in ds if d not in IGNORER_DOSSIERS and not d.startswith(".")]      # un dossier caché (.porte, .claude) n'est pas du projet
            out += [str(Path(r, f).relative_to(RACINE)).replace(os.sep, "/") for f in fs]
        return out


def marqueur(l: str, ext: str = "") -> str | None:
    """Rend le texte d'un marqueur si la ligne est une vraie ligne de commentaire de marqueur DU LANGAGE DU FICHIER, sinon None.
    (Une chaîne de caractères, ou un exemple cité dans une documentation Markdown, qui reprend les mots d'un marqueur n'en est pas un.)"""
    s = l.strip()
    jetons = (COMMENTAIRE[ext],) if ext in COMMENTAIRE else ("<!--", "/*", "//", ";;", "--", "#")
    for jeton in jetons:
        if s.startswith(jeton):
            s = s[len(jeton):].strip(" ▼▲═─*	")
            if s.startswith(("BORNE CN", "FIN BORNE", "BORNE EC", "EXPLICATIF CN / EC")):
                return s.rstrip(" ▼▲═─*>-/")
            return None
    return None


def empreinte(lignes: list[str]) -> str:
    return hashlib.sha256("\n".join(l.rstrip() for l in lignes).encode("utf-8")).hexdigest()[:6]


def module_de(chemin: str) -> str:
    p = chemin.split("/")
    return p[1] if p[0] == "modules" and len(p) > 2 else p[0] if len(p) > 1 else "(racine)"


def lire(chemin: str) -> str | None:
    try:
        return (RACINE / chemin).read_text(encoding="utf-8")
    except Exception:
        return None


def analyser(chemin: str) -> dict:
    """Rend {chemin, module, erreurs:[...], infos:[...], zone, ...} pour un fichier."""
    nom = Path(chemin).name
    ext = Path(chemin).suffix
    r = {"chemin": chemin, "module": module_de(chemin), "erreurs": [], "infos": [], "zone": None, "points": []}
    if nom in NOMS_IMPOSES or any(p in IGNORER_DOSSIERS for p in Path(chemin).parts):
        r["infos"].append("nom imposé de l'extérieur : hors format")
        r["exempt"] = True
        return r
    prefixe = nom[:3] if nom[:3] in PREFIXES else None
    if not prefixe:
        r["erreurs"].append("nommage : pas de préfixe CN_ / EC_")
    texte = lire(chemin)
    if texte is None:
        r["infos"].append("binaire ou illisible : ignoré")
        r["exempt"] = True
        return r
    if ext in SANS_COMMENTAIRE:
        compagnon = RACINE / (chemin + ".borne")
        if not compagnon.exists():
            r["erreurs"].append("fichier compagnon .borne absent (en-tête porté à part)")
            return r
        champs_c: dict[str, str] = {}
        for l in compagnon.read_text(encoding="utf-8").splitlines():
            m = RE_CHAMP.match(l)
            if m:
                champs_c[m.group(1)] = m.group(2)
        manque = [c for c in CHAMPS if c not in champs_c]
        if manque:
            r["erreurs"].append("compagnon .borne incomplet : manque " + ", ".join(manque))
        r["zone"] = champs_c.get("ZONE")
        r["infos"].append("en-tête porté par le fichier compagnon .borne")
        return r
    if ext not in COMMENTAIRE:
        r["infos"].append("extension non gérée par le format")
        return r
    lignes = texte.splitlines()

    # ── en-tête ──────────────────────────────────────────────────────
    champs: dict[str, str] = {}
    for l in lignes[:60]:
        m = RE_CHAMP.match(l)
        if m:
            champs.setdefault(m.group(1), m.group(2))              # le PREMIER gagne : un exemple d'en-tête cité plus bas (dans une chaîne) ne l'écrase pas
    manquants = [c for c in CHAMPS if c not in champs]
    if manquants:
        r["erreurs"].append("en-tête incomplet : manque " + ", ".join(manquants))
    for c, v in CONSTANTES.items():
        if c in champs and champs[c] != v:
            r["erreurs"].append(f"en-tête : {c} doit valoir « {v} »")
    zone = champs.get("ZONE")
    r["zone"] = zone
    if zone not in (None, "CN", "EC"):
        r["erreurs"].append("en-tête : ZONE doit valoir CN ou EC")
    if prefixe and zone in ("CN", "EC") and prefixe[:2] != zone:
        r["erreurs"].append(f"nommage : préfixe {prefixe} différent de ZONE {zone}")

    # ── bornes ───────────────────────────────────────────────────────
    ouvertes, bornes, expl = None, [], False
    hors_borne = 0
    for i, l in enumerate(lignes, 1):
        mk = marqueur(l, ext)
        mcn, mec = (RE_BORNE_CN.search(mk), RE_BORNE_EC.search(mk)) if mk else (None, None)
        if mk and mk.startswith("FIN BORNE"):
            if ouvertes is None:
                r["erreurs"].append(f"ligne {i} : fin de borne sans ouverture")
            else:
                ouvertes["fin"] = i
                ouvertes["corps"] = lignes[ouvertes["debut"]:i - 1]
                bornes.append(ouvertes)
                ouvertes = None
        elif mcn or mec:
            if ouvertes is not None:
                r["erreurs"].append(f"ligne {i} : borne ouverte dans une borne")
            ouvertes = {"debut": i, "type": "CN" if mcn else "EC", "m": (mcn or mec).groups()}
        elif mk and mk.startswith("EXPLICATIF CN / EC"):
            expl = True
        elif ouvertes is None and not expl:
            s = l.strip()
            if s and not s.startswith(("#", "//", ";;", "--", "/*", "*", "<!--", "-->")) and not (i <= 2 and (s.startswith("#!") or s.lower().startswith(("<!doctype", "@charset")) or "coding" in s)):      # lignes qui doivent rester en tête (shebang, encodage, doctype, @charset)
                hors_borne += 1
    if ouvertes is not None:
        r["erreurs"].append("borne ouverte jamais fermée")
    if not bornes:
        r["erreurs"].append("aucune borne")
    if len(bornes) > 1:
        r["erreurs"].append("plus d'une borne : un fichier = une zone")
    if hors_borne:
        r["erreurs"].append(f"{hors_borne} ligne(s) de code hors borne")
    if not expl:
        r["erreurs"].append("explicatif CN / EC absent")
    for b in bornes:
        if zone in ("CN", "EC") and b["type"] != zone:
            r["erreurs"].append(f"borne {b['type']} dans un fichier de ZONE {zone}")
        if b["type"] == "CN":                                    # la version dit la même chose partout : en-tête, marqueur, manifeste du module
            v_tete = champs.get("VERSION CN", "").split()[0] if champs.get("VERSION CN", "").split() else ""
            if v_tete and v_tete != "néant" and v_tete != b["m"][0]:
                r["erreurs"].append("version : l'en-tête dit %s, le marqueur de borne %s" % (v_tete, b["m"][0]))
            v_mod = version_du_module(module_de(chemin)) if chemin.startswith("modules/") else None
            if v_mod and v_tete and v_tete != "néant" and v_tete != v_mod:
                r["erreurs"].append("version : le fichier dit %s, le manifeste du module %s (python outils/CN_bornes.py --monter MODULE VERSION)" % (v_tete, v_mod))
        calc = empreinte(b["corps"])
        declaree = b["m"][1] if b["type"] == "CN" else b["m"][3]
        if declaree != calc:
            r["infos"].append(f"empreinte à recalculer (déclarée {declaree}, calculée {calc})")
        if b["type"] == "EC":
            r["points"].append(b["m"][0])
            if ext == ".py" and champs.get("RUNTIME", "python") == "python":
                r["erreurs"] += [f"pureté : {e}" for e in pureté("\n".join(b["corps"]))]
            else:
                r["infos"].append(f"pureté non vérifiable par analyse : runtime {champs.get('RUNTIME', ext)} (bac isolé exigé à l'exécution)")
    # ── renvois ──────────────────────────────────────────────────────
    if zone == "CN" and "EC LIÉES" in champs and champs["EC LIÉES"] not in ("néant", ""):
        for lien in re.findall(r"->\s*(\S+)", champs["EC LIÉES"]):
            base = RACINE / Path(chemin).parent
            existe = any(True for _ in base.glob(lien)) if "*" in lien else (base / lien).exists()
            if not existe:
                r["erreurs"].append(f"EC LIÉES : fichier introuvable {lien} (une EC peut avoir n'importe quelle extension : écrire « points/EC_x.* »)")
    if zone == "EC":
        for c in CHAMPS_EC:
            if c not in champs:
                r["erreurs"].append(f"fichier EC sans {c}")
        r["runtime"] = champs.get("RUNTIME")
    return r


def pureté(source: str) -> list[str]:
    """Règles d'une borne EC (docs/CN_NEXUS.md §3, condition 1 et 2)."""
    try:
        arbre = ast.parse(source)
    except SyntaxError as e:
        return [f"syntaxe illisible ({e.msg})"]
    fautes: set[str] = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] not in STDLIB_PURE:
                    fautes.add(f"import interdit : {a.name}")
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] not in STDLIB_PURE:
                fautes.add(f"import interdit : {n.module}")
        elif isinstance(n, ast.Name) and n.id in NOMS_INTERDITS:
            fautes.add(f"nom interdit : {n.id}")
        elif isinstance(n, ast.Attribute) and n.attr in ATTRIBUTS_INTERDITS:
            fautes.add(f"horloge ou hasard : .{n.attr}")
        elif isinstance(n, ast.arg) and n.arg in NOMS_INTERDITS:
            fautes.add(f"paramètre interdit : {n.arg}")
        elif isinstance(n, (ast.Global, ast.Nonlocal, ast.Await, ast.Yield)):
            fautes.add("global / nonlocal / await / yield")
    return sorted(fautes)


def candidats_points(chemin: str) -> list[tuple[str, int, bool]]:
    """Fonctions de tête pures (>= 8 lignes) d'un fichier Python : candidates à devenir des points. Le booléen dit « semble décisive »."""
    texte = lire(chemin)
    if texte is None or not chemin.endswith(".py") or chemin.startswith("tests/"):
        return []
    try:
        arbre = ast.parse(texte)
    except SyntaxError:
        return []
    modules_impurs = set()
    for x in arbre.body:
        if isinstance(x, ast.Import):
            modules_impurs |= {(a.asname or a.name.split(".")[0]) for a in x.names if a.name.split(".")[0] not in STDLIB_PURE}
        elif isinstance(x, ast.ImportFrom) and (x.module or "").split(".")[0] not in STDLIB_PURE:
            modules_impurs |= {(a.asname or a.name) for a in x.names}
    out = []
    for f in arbre.body:
        if not isinstance(f, ast.FunctionDef):
            continue
        n = f.end_lineno - f.lineno + 1
        if n < 8:
            continue
        sale = False
        for z in ast.walk(f):
            if isinstance(z, ast.Name) and (z.id in NOMS_INTERDITS or z.id in modules_impurs):
                sale = True
            if isinstance(z, (ast.Global, ast.Nonlocal, ast.Await, ast.Yield)):
                sale = True
        if not sale:
            out.append((f.name, n, any(k in f.name.lower() for k in INDICES_DECISIFS)))
    return out


def audit(filtre_module: str | None = None, fichier: str | None = None) -> dict:
    tous = [fichier] if fichier else [c for c in fichiers_suivis() if (RACINE / c).is_file()]
    res = [analyser(c) for c in tous]
    if filtre_module:
        res = [r for r in res if r["module"] == filtre_module]
    modules: dict[str, dict] = {}
    for r in res:
        m = modules.setdefault(r["module"], {"fichiers": 0, "exempts": 0, "conformes": 0, "erreurs": 0, "candidats": 0, "lignes_candidates": 0, "decisifs": 0})
        if r.get("exempt"):
            m["exempts"] += 1
            continue
        m["fichiers"] += 1
        m["erreurs"] += len(r["erreurs"])
        if not r["erreurs"]:
            m["conformes"] += 1
        for nom, n, dec in candidats_points(r["chemin"]):
            m["candidats"] += 1
            m["lignes_candidates"] += n
            m["decisifs"] += 1 if dec else 0
    return {"modules": modules, "fichiers": res}


def afficher(a: dict, detail: bool = False) -> None:
    tot = {"fichiers": 0, "conformes": 0, "erreurs": 0, "candidats": 0, "lignes_candidates": 0, "exempts": 0}
    print(f"{'module':14} {'fichiers':>8} {'conformes':>10} {'erreurs':>8} {'points possibles':>17} {'lignes':>7}")
    for m, d in sorted(a["modules"].items()):
        print(f"{m:14} {d['fichiers']:>8} {d['conformes']:>10} {d['erreurs']:>8} {d['candidats']:>17} {d['lignes_candidates']:>7}")
        for k in tot:
            tot[k] += d[k]
    print("-" * 62)
    print(f"{'TOTAL':14} {tot['fichiers']:>8} {tot['conformes']:>10} {tot['erreurs']:>8} {tot['candidats']:>17} {tot['lignes_candidates']:>7}   ({tot['exempts']} fichiers hors format : noms imposés)")
    if detail:
        for r in a["fichiers"]:
            if r.get("exempt"):
                continue
            print(f"\n{r['chemin']}  [zone {r['zone'] or '?'}]")
            for e in r["erreurs"]:
                print("   ERREUR  ", e)
            for i in r["infos"]:
                print("   info    ", i)
            for nom, n, dec in candidats_points(r["chemin"]):
                print(f"   point possible : {nom} ({n} l.){' — semble décisive' if dec else ''}")


def version_du_module(module: str) -> str | None:
    """La version dépôt du module, lue dans son manifeste."""
    for nom in ("CN_manifeste.toml", "manifeste.toml"):
        f = RACINE / "modules" / module / nom
        if f.exists():
            m = re.search(r'^version\s*=\s*"([^"]+)"', f.read_text(encoding="utf-8"), re.M)
            if m:
                return m.group(1)
    return None


def monter(module: str, version: str) -> list:
    """Monte la version d'un module PARTOUT d'un seul geste : manifeste, en-tête et marqueur de chaque fichier CN, mention de la référence des points ; puis scelle.
    Rend la liste des fichiers modifiés. Une version se monte quand le contenu du module change (le déploiement le rappelle)."""
    ancienne = version_du_module(module)
    if not ancienne:
        raise ValueError("module introuvable : " + module)
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        raise ValueError("version « majeure.mineure.correctif », ex. 0.2.0")
    modifies = []
    dossier = RACINE / "modules" / module
    for f in sorted(dossier.rglob("*")):
        if not f.is_file() or "__pycache__" in f.parts:
            continue
        texte = f.read_text(encoding="utf-8") if f.suffix in COMMENTAIRE or f.suffix == ".borne" else None
        if texte is None:
            continue
        neuf = texte
        if f.name in ("CN_manifeste.toml", "manifeste.toml"):
            neuf = re.sub(r'^version\s*=\s*"[^"]+"', 'version = "%s"' % version, neuf, count=1, flags=re.M)
        neuf = re.sub(r"(VERSION CN\s*:\s*)" + re.escape(ancienne), lambda m: m.group(1) + version, neuf)
        neuf = re.sub(r"(BORNE CN version=)" + re.escape(ancienne), lambda m: m.group(1) + version, neuf)
        neuf = neuf.replace("(référence %s)" % ancienne, "(référence %s)" % version)
        if neuf != texte:
            f.write_text(neuf, encoding="utf-8", newline="\n")
            modifies.append(str(f.relative_to(RACINE)).replace(os.sep, "/"))
    for c in modifies:
        sceller(c)
    return modifies


def sceller(chemin: str) -> bool:
    """Recalcule l'empreinte de la borne et l'écrit dans le marqueur et dans l'en-tête. Rend True si le fichier a changé."""
    texte = lire(chemin)
    if texte is None:
        return False
    lignes = texte.split("\n")
    debut = fin = None
    for i, l in enumerate(lignes):
        mk = marqueur(l, Path(chemin).suffix)
        if mk and mk.startswith(("BORNE CN", "BORNE EC")) and debut is None:
            debut = i
        elif mk and mk.startswith("FIN BORNE") and debut is not None and fin is None:
            fin = i
    if debut is None or fin is None:
        return False
    h = empreinte(lignes[debut + 1:fin])
    lignes[debut] = re.sub(r"empreinte=[0-9a-f]+", "empreinte=" + h, lignes[debut])
    for i, l in enumerate(lignes[:60]):
        if re.match(r"^\s*(#|//|;;|--)\s*VERSION (CN|EC)\s*:", l) and "#" in l.split(":", 1)[1] and "néant" not in l:
            lignes[i] = re.sub(r"#[0-9a-f]{6}", "#" + h, l, count=1)
    neuf = "\n".join(lignes)
    if neuf != texte:
        (RACINE / chemin).write_text(neuf, encoding="utf-8", newline="\n")
        return True
    return False


def principal(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = argv[1:]
    if "--monter" in args:
        i = args.index("--monter")
        mods = monter(args[i + 1], args[i + 2])
        print("%d fichier(s) mis à la version %s" % (len(mods), args[i + 2]))
        return 0
    if "--sceller" in args:
        cibles = [args[args.index("--sceller") + 1]] if args.index("--sceller") + 1 < len(args) and not args[args.index("--sceller") + 1].startswith("--") else [c for c in fichiers_suivis() if (RACINE / c).is_file()]
        n = sum(1 for c in cibles if sceller(c))
        print(f"{n} fichier(s) scellé(s)")
        return 0
    module = args[args.index("--module") + 1] if "--module" in args else None
    fichier = args[args.index("--fichier") + 1] if "--fichier" in args else None
    a = audit(module, fichier)
    if "--json" in args:
        print(json.dumps({"modules": a["modules"], "erreurs": sum(len(r["erreurs"]) for r in a["fichiers"])}, ensure_ascii=False, indent=1))
    else:
        afficher(a, detail=bool(fichier) or "--detail" in args)
    erreurs = sum(len(r["erreurs"]) for r in a["fichiers"])
    return 1 if ("--strict" in args and erreurs) else 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus (outil du dépôt, jamais évolutif).
# EC : néant. Il lit les autres fichiers ; il n'en modifie aucun.
# LIEN : docs/CN_FORMAT.md (la spécification qu'il vérifie), docs/CN_NEXUS.md (les six conditions d'un point d'évolution).
