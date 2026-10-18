# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'extracteur proactif
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #e9525e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'extracteur proactif : trouve dans les fichiers CN des modules les fonctions éligibles à l'évolution (EC) et les en sort, sans qu'on les désigne.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e9525e ▼▼▼
"""L'extracteur proactif : trouve dans les fichiers CN des modules les fonctions éligibles à l'évolution (EC) et les en sort, sans qu'on les désigne.

   python outils/CN_auto_extraire.py lister   [--module M]            ce qui est éligible, et pourquoi le reste ne l'est pas (n'écrit rien)
   python outils/CN_auto_extraire.py extraire [--module M] [--max N]  extrait les éligibles dont les entrées se synthétisent et se prouvent

Une fonction est ÉLIGIBLE quand : sa fermeture (les noms de premier niveau dont elle dépend) passe les règles de pureté du noyau, ne partage aucun
état modifiable, n'est ni décorée ni déjà un point, a des paramètres ordinaires, rend une valeur, et fait au moins MIN_LIGNES lignes.
Elle est EXTRAYABLE quand, en plus, un corpus d'entrées (récoltées dans les appels littéraux du dépôt, puis synthétisées par type) prouve
qu'elle est déterministe, qu'elle ne modifie pas ses entrées, que sa sortie survit exactement au tour JSON, et que le corpus la couvre assez.
L'extraction écrit l'EC, son contrat, son corpus, la déclaration au manifeste, la façade ; elle revient en arrière (octet pour octet) si les bancs
du module ou la mesure échouent. Rien n'est commité, rien n'est déployé."""
import ast
import copy
import hashlib
import itertools
import json
import random
import re
import subprocess
import sys
import textwrap
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils"))
from noyau.CN_points import STDLIB_PURE, analyser_purete  # noqa: E402
import CN_extraire_point as X  # noqa: E402

MIN_LIGNES = 8                       # en dessous, le passage par ctx.point coûte plus que la fonction
MAX_FERMETURE = 320                  # lignes de la fermeture copiée dans l'EC
COUVERTURE_MIN = 0.6
CAS_MIN, SORTIES_MIN, CAS_MAX = 4, 3, 36
MUTATEURS = {"append", "extend", "insert", "pop", "popitem", "clear", "update", "setdefault", "add", "discard", "remove", "sort", "reverse"}
# Le code qui DÉCIDE, AUTORISE ou PROUVE reste au nexus même quand il est pur : une variante plus rapide qui diverge sur une entrée que le corpus ne couvre pas
# changerait une décision de sécurité. L'évolution d'une EC est bornée par l'équivalence sur le corpus, pas par l'intention.
DECISIONNELS = {"droits", "urgence", "webauthn", "coffre", "comptes", "mandats", "identite", "certificats"}
EXCEPTIONS = RACINE / "outils" / "CN_auto_extraire.exceptions.json"

PRELUDE = '''_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)
_REFERENCES = {}


def _appeler_point(point, entree):
    """Appelle le point d'évolution du module. Sans brancher() (un banc qui appelle la fonction seule), la RÉFÉRENCE du dépôt répond : points/EC_<point>.py, chargée par son chemin."""
    if _point is not None:
        return _point(point, entree)
    if point not in _REFERENCES:
        import importlib.util as _iu
        import pathlib as _pl
        chemin = _pl.Path(__file__).resolve().parent / "points" / ("EC_%s.py" % point)
        spec = _iu.spec_from_file_location("ec_ref_" + point, str(chemin))
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _REFERENCES[point] = getattr(mod, "point_" + point)
    return _REFERENCES[point](entree)
'''
PRELUDE_SANS_POINT = PRELUDE.replace('_point = None          # posé par brancher() : les points d\'évolution du module (ctx.point)\n', "")


def lire(p):
    return Path(p).read_bytes().decode("utf-8").replace("\r\n", "\n")


def git(*args):
    return subprocess.run(["git", "-C", str(RACINE)] + list(args), capture_output=True, text=True, encoding="utf-8").stdout


# ── 1. la détection statique ───────────────────────────────────────────────────
def modules():
    return sorted(p.name for p in (RACINE / "modules").iterdir() if (p / "CN_manifeste.toml").exists())


def en_cours_ailleurs(module):
    """Des fichiers du module modifiés et non commités : un autre fil y travaille, on n'y touche pas."""
    return bool(git("status", "--porcelain", "--", "modules/" + module).strip())


def fichiers(module):
    d = RACINE / "modules" / module
    return sorted(p for p in d.glob("CN_*.py") if not p.name.startswith("CN_test"))


def branchement(module):
    """Comment une façade reçoit ctx.point : {fichier: objet} (« ce module » pour CN_module.py lui-même) ; None si CN_module.py n'a pas de brancher(ctx)."""
    f = RACINE / "modules" / module / "CN_module.py"
    if not f.exists():
        return None
    arbre = ast.parse(lire(f))
    b = next((n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == "brancher"), None)
    if b is None or [a.arg for a in b.args.args] != ["ctx"]:
        return None
    res = {"CN_module.py": "ce module"}
    for n in arbre.body:
        if isinstance(n, ast.ImportFrom) and n.level >= 1 and not n.module:
            for a in n.names:
                res.setdefault(a.name + ".py", a.asname or a.name)
    return res


def _locaux(fn):
    noms = {a.arg for a in fn.args.args + fn.args.kwonlyargs + fn.args.posonlyargs}
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            noms.add(n.id)
        elif isinstance(n, ast.arg):
            noms.add(n.arg)
    return noms


def _etat_partage(vus, noms):
    """Une fonction de la fermeture qui MODIFIE un nom de premier niveau (un cache, un compteur) n'est pas pure, même si elle n'a ni `global` ni entrée/sortie."""
    for nom, (noeud, rang) in vus.items():
        if not isinstance(noeud, ast.FunctionDef):
            continue
        loc = _locaux(noeud)
        for n in ast.walk(noeud):
            cible = None
            if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Delete)):
                cs = n.targets if isinstance(n, (ast.Assign, ast.Delete)) else [n.target]
                for c in cs:
                    while isinstance(c, (ast.Subscript, ast.Attribute)):
                        c = c.value
                    if isinstance(c, ast.Name) and c.id in noms and c.id not in loc and not isinstance(n.targets[0] if isinstance(n, ast.Assign) else None, ast.Name):
                        cible = c.id
                    elif isinstance(c, ast.Name) and c.id in noms and c.id not in loc and isinstance(n, ast.AugAssign):
                        cible = c.id
            elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in MUTATEURS:
                c = n.func.value
                while isinstance(c, (ast.Subscript, ast.Attribute)):
                    c = c.value
                if isinstance(c, ast.Name) and c.id in noms and c.id not in loc and not isinstance(noms[c.id][0], (ast.FunctionDef, ast.ClassDef)):
                    cible = c.id
            if cible:
                return cible
    return None


def examiner(module, chemin):
    """Rend (candidats, rejets) pour un fichier : candidat = dict ; rejet = (fonction, raison)."""
    src = lire(chemin)
    rel = str(Path(chemin).relative_to(RACINE)).replace("\\", "/")
    try:
        arbre = ast.parse(src)
    except SyntaxError:
        return [], []
    noms, imports = X._niveau_module(arbre)
    cand, rejets = [], []
    for n in arbre.body:
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fn = n.name
        a = n.args

        def non(raison):
            rejets.append((fn, raison))
        if isinstance(n, ast.AsyncFunctionDef):
            non("asynchrone")
            continue
        if n.end_lineno - n.lineno + 1 < MIN_LIGNES:
            non("trop courte (moins de %d lignes)" % MIN_LIGNES)
            continue
        if n.decorator_list:
            non("décorée")
            continue
        seg = ast.get_source_segment(src, n) or ""
        if "_appeler_point(" in seg or "_point(" in seg or "ctx.point" in seg or any(x.arg in ("appeler", "ctx") for x in a.args):
            non("déjà un point (ou branchée au contexte)")
            continue
        if a.vararg or a.kwarg or a.kwonlyargs:
            non("paramètres *args / **kwargs / nommés seuls")
            continue
        if not any(isinstance(x, ast.Return) and x.value is not None for x in ast.walk(n)):
            non("ne rend aucune valeur")
            continue
        try:
            vus, utilises = X._fermeture(noms, imports, [fn])
        except SystemExit:
            non("fermeture illisible")
            continue
        base_impure = next((x for x in sorted(utilises) if (imports[x].names[0].name if isinstance(imports[x], ast.Import) else imports[x].module or "").split(".")[0] not in STDLIB_PURE
                            and not (isinstance(imports[x], ast.ImportFrom) and imports[x].level)), None)
        if base_impure:
            non("import non pur : " + base_impure)
            continue
        if any(isinstance(imports[x], ast.ImportFrom) and imports[x].level for x in utilises):
            non("importe un voisin du module")
            continue
        try:
            lignes_imports, morceaux = X.corps_de_reference({"source": rel, "fonctions": [fn]})
        except SystemExit as e:
            non("fermeture : %s" % e)
            continue
        texte = "\n".join(lignes_imports + [""] + ["\n\n\n".join(morceaux)]) + "\n"
        fautes = analyser_purete(texte)
        if fautes:
            non("impure : " + fautes[0])
            continue
        if texte.count("\n") > MAX_FERMETURE:
            non("fermeture trop grosse (%d lignes)" % texte.count("\n"))
            continue
        if any("_appeler_point(" in (ast.get_source_segment(src, nd) or "") for nd, _ in vus.values()):
            non("appelle un point déjà extrait")
            continue
        partage = _etat_partage(vus, noms)
        if partage:
            non("état partagé : " + partage)
            continue
        params = [x.arg for x in a.args]
        cand.append({"module": module, "fichier": rel, "fn": fn, "params": params, "lignes": n.end_lineno - n.lineno + 1, "texte": texte,
                     "defauts": {params[len(params) - len(a.defaults) + i]: ast.unparse(d) for i, d in enumerate(a.defaults)},
                     "annotations": {x.arg: ast.unparse(x.annotation) for x in a.args if x.annotation}, "doc": (ast.get_docstring(n) or "").split("\n")[0].rstrip(".")})
    return cand, rejets


def balayer(seulement=None):
    """Toutes les fonctions éligibles, module par module : {module: {"candidats": [...], "rejets": [...], "ignore": raison}}."""
    sortie = {}
    for m in modules():
        if seulement and m != seulement:
            continue
        if m in DECISIONNELS:
            sortie[m] = {"candidats": [], "rejets": [], "ignore": "décisionnel : décide, autorise ou prouve, il reste au nexus"}
            continue
        if en_cours_ailleurs(m):
            sortie[m] = {"candidats": [], "rejets": [], "ignore": "modifié et non commité : un autre fil y travaille"}
            continue
        br = branchement(m)
        cs, rs = [], []
        for f in fichiers(m):
            c, r = examiner(m, f)
            for x in c:
                if br is None:
                    rs.append((x["fn"], "le module n'a pas de brancher(ctx)"))
                elif Path(x["fichier"]).name not in br:
                    rs.append((x["fn"], "le fichier n'est pas importé par CN_module.py (pas de ctx.point)"))
                else:
                    cs.append(x)
            rs += [(f.name + ":" + fn, raison) for fn, raison in r]
        sortie[m] = {"candidats": cs, "rejets": rs, "ignore": ""}
    return sortie


# ── 2. la synthèse du corpus ───────────────────────────────────────────────────
TEXTES = ["", " ", "a", "abc", "Bonjour le monde", "ligne1\nligne2\n", "  espaces  ", "a,b;c", "https://exemple.test/x?y=1", "2026-10-17T12:00:00", "2026-10-17 12:00", "a@exemple.test",
          "é à ü", "x" * 40, "-1", "42", "3.14", "true", '{"a": 1}', "# titre\ntexte", "<b>gras</b> et <i>x</i>", "tab\tsep", "/var/www/x/y.txt", "CLE=valeur\n#c\nAUTRE=2",
          "Nom Prénom <a@exemple.test>", "exemple.test", "127.0.0.1", "10:30", "1h30", "oui", "non", "a.b.c", "2026-10-17", "../x", "a/b/c", "C:\\x"]
ENTIERS = [0, 1, 2, 3, -1, 5, 10, 60, 100, 1024, 3600, 86400, 1760000000]
REELS = [0.0, 0.5, 1.5, -2.25, 100.0, 1e6, 2.0 / 3]
LISTES = [[], [1, 2, 3], ["a", "b"], ["a", "b", "a"], [{"a": 1}, {"a": 2}], [[1, 2], [3, 4]], [0.5, 1.5], ["x", 1, None], ["un", "deux", "trois", "quatre"], [3, 1, 2]]
DICTS = [{}, {"a": 1}, {"a": 1, "b": "x"}, {"nom": "n", "valeur": 3}, {"id": 1, "name": "x", "items": [1, 2]}, {"a": {"b": [1, 2]}}, {"k": None}, {"x": "1", "y": "2", "z": ""}]
BOOLS = [True, False]
NOM_TEXTE = re.compile(r"(texte|text|txt|^s$|^t$|ligne|line|nom|name|chaine|msg|message|corps|body|html|url|path|chemin|mot|motif|cle|key|sujet|titre|adresse|email|mail|domaine|host|raw|brut|out|sortie|src|source|contenu|code|cmd|commande|label|libelle|desc|prefixe|suffixe|fmt|format|ip$|iso|date|heure)", re.I)
NOM_ENTIER = re.compile(r"(^n$|^i$|^j$|^k$|nb|nombre|count|port|taille|size|secondes|^sec|ms$|jours|heures|minutes|duree|^ts|instant|^now|delta|limite|^max|^min|seuil|pct|ratio|total|pos$|index|idx|rang|niveau|age|annee|mois)", re.I)
NOM_LISTE = re.compile(r"(liste|lst|items|rows|lignes|elements|^els|noms$|ids$|args|parts|champs|tous|resultats|results|entries|events|evenements|cles$|keys|mots$|valeurs|values|^xs$|seq)", re.I)
NOM_DICT = re.compile(r"(^d$|dic|data|donnees|cfg|conf|config|obj|objet|fiche|entree|row|record|enregistrement|etat|mapping|table|index$|meta|infos?$|options?|params?$)", re.I)
METHODES_TEXTE = {"split", "strip", "lstrip", "rstrip", "lower", "upper", "startswith", "endswith", "replace", "splitlines", "encode", "format", "find", "isdigit", "title", "capitalize", "partition", "rsplit", "zfill", "casefold"}
METHODES_DICT = {"get", "items", "keys", "values", "setdefault", "update"}
FONCTIONS_TEXTE = {"match", "search", "fullmatch", "findall", "sub", "split", "finditer"}
_LITTERAUX = {}


def litteraux(module):
    """Les valeurs JSON que le module et ses bancs écrivent en toutes lettres : des textes, des listes, des dictionnaires RÉELS (un message, une fiche, une règle), meilleures que n'importe quelle devinette."""
    if module in _LITTERAUX:
        return _LITTERAUX[module]
    res = {"str": [], "int": [], "list": [], "dict": []}
    vus = set()
    fich = list((RACINE / "tests").glob("CN_test_%s*.py" % module)) + [f for f in (RACINE / "modules" / module).rglob("*.py") if "points" not in f.parts]
    for f in fich:
        try:
            arbre = ast.parse(lire(f))
        except SyntaxError:
            continue
        for n in ast.walk(arbre):
            if not isinstance(n, (ast.Constant, ast.Dict, ast.List)):
                continue
            try:
                v = ast.literal_eval(n)
            except Exception:
                continue
            k = type(v).__name__
            if k not in res or isinstance(v, bool) or not _exact(v):
                continue
            if k == "str" and not (0 < len(v) <= 160):
                continue
            if k in ("list", "dict") and (not v or len(json.dumps(v, ensure_ascii=False)) > 600):
                continue
            cle = json.dumps(v, sort_keys=True, ensure_ascii=False)
            if (k, cle) in vus:
                continue
            vus.add((k, cle))
            if len(res[k]) < 400:
                res[k].append(v)
    _LITTERAUX[module] = res
    return res


def _usage(fn, nom):
    """Ce que le code fait du paramètre : traité comme un texte, un dictionnaire (et quelles clés il lit), une liste, un nombre."""
    ev = {"texte": 0, "dict": 0, "liste": 0, "nombre": 0, "cles": []}
    for n in ast.walk(fn):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == nom:
            if n.attr in METHODES_TEXTE:
                ev["texte"] += 1
            elif n.attr in METHODES_DICT:
                ev["dict"] += 1
            elif n.attr in ("append", "extend", "sort", "index", "count"):
                ev["liste"] += 1
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == nom and n.func.attr == "get" and n.args and isinstance(n.args[0], ast.Constant):
            ev["cles"].append(n.args[0].value)
        elif isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == nom:
            sl = n.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                ev["dict"] += 1
                ev["cles"].append(sl.value)
            elif (isinstance(sl, ast.Constant) and isinstance(sl.value, int)) or isinstance(sl, ast.Slice):
                ev["liste"] += 1
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "re" and n.func.attr in FONCTIONS_TEXTE and any(isinstance(a, ast.Name) and a.id == nom for a in n.args):
            ev["texte"] += 1
        elif isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == nom and any(isinstance(c, ast.Constant) and isinstance(c.value, (int, float)) and not isinstance(c.value, bool) for c in n.comparators):
            ev["nombre"] += 1
        elif isinstance(n, ast.BinOp) and any(isinstance(x, ast.Name) and x.id == nom for x in (n.left, n.right)) and any(isinstance(x, ast.Constant) and isinstance(x.value, (int, float)) for x in (n.left, n.right)):
            ev["nombre"] += 1
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("len", "sorted", "set", "list", "tuple", "enumerate", "zip", "sum", "any", "all", "max", "min", "reversed") and any(isinstance(a, ast.Name) and a.id == nom for a in n.args):
            ev["liste"] += 1
        elif isinstance(n, ast.For) and isinstance(n.iter, ast.Name) and n.iter.id == nom:
            ev["liste"] += 1
    return ev


def _constantes(arbre):
    textes, entiers = [], []
    for n in ast.walk(arbre):
        if isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, str) and 0 < len(v) <= 60 and v not in textes:
                textes.append(v)
            elif isinstance(v, int) and not isinstance(v, bool) and v not in entiers:
                entiers.append(v)
    return textes, entiers


def _dedupe(valeurs):
    vus, res = set(), []
    for v in valeurs:
        try:
            k = json.dumps(v, sort_keys=True, ensure_ascii=False)
        except (TypeError, ValueError):
            continue
        if k not in vus:
            vus.add(k)
            res.append(v)
    return res


def _piscine(nom, defaut, annotation, usage, lit, consts, hasard):
    """Les valeurs à essayer pour un paramètre, les plus plausibles d'abord : défaut, annotation, usage dans le code, nom ; puis les valeurs littérales du dépôt ; puis un peu de tout."""
    ctext, cint = consts
    pref = []
    t = (annotation or "").lower()
    if defaut is not None:
        try:
            v = ast.literal_eval(defaut)
            t = t or type(v).__name__
            pref.append(v)
        except Exception:
            pass
    famille = None
    if t.startswith("str"):
        famille = "texte"
    elif t.startswith(("int", "float")):
        famille = "nombre"
    elif t.startswith(("list", "tuple", "set")):
        famille = "liste"
    elif t.startswith("dict"):
        famille = "dict"
    elif t.startswith("bool"):
        famille = "bool"
    if not famille:
        pts = {"texte": usage["texte"], "dict": usage["dict"] * 1.2, "liste": usage["liste"], "nombre": usage["nombre"]}
        if max(pts.values()) > 0:
            famille = max(pts, key=pts.get)
        elif NOM_TEXTE.search(nom):
            famille = "texte"
        elif NOM_ENTIER.search(nom):
            famille = "nombre"
        elif NOM_LISTE.search(nom):
            famille = "liste"
        elif NOM_DICT.search(nom):
            famille = "dict"
    textes = ctext + [x + "x" for x in ctext[:6]] + [" " + x + " " for x in ctext[:4]] + lit["str"][:120] + TEXTES
    if famille == "texte":
        pref += textes
    elif famille == "nombre":
        pref += _dedupe([c + d for c in consts[1][:6] for d in (-1, 0, 1)] + lit["int"][:20] + ENTIERS + REELS)
    elif famille == "liste":
        pref += lit["list"][:100] + LISTES + [[x] for x in ctext[:6]]
    elif famille == "dict":
        pref += lit["dict"][:100]
        cles = _dedupe(usage["cles"])
        if cles:
            valeurs = ctext + lit["str"][:20] + [None, "", 0, 1, True, False, [], {}, ["a", "b"], {"a": 1}] + TEXTES[:6]
            for _ in range(80):
                k = hasard.sample(cles, hasard.randint(0, len(cles)))
                pref.append({c: hasard.choice(valeurs) for c in k})
        pref += DICTS
    elif famille == "bool":
        pref += BOOLS
    reste = textes[:10] + ENTIERS[:5] + REELS[:3] + (lit["list"][:6] or LISTES[:5]) + (lit["dict"][:6] or DICTS[:4]) + BOOLS + [None]
    return _dedupe(pref + reste), len(_dedupe(pref))


def recolter(c):
    """Les appels LITTÉRAUX de la fonction dans le dépôt (le module et ses bancs) : des entrées réelles, écrites par quelqu'un qui savait ce qu'il testait."""
    trouves = []
    dossiers = [RACINE / "modules" / c["module"], RACINE / "tests"]
    for d in dossiers:
        for f in d.rglob("*.py"):
            if "points" in f.parts:
                continue
            try:
                arbre = ast.parse(lire(f))
            except SyntaxError:
                continue
            for n in ast.walk(arbre):
                if not isinstance(n, ast.Call):
                    continue
                nom = n.func.id if isinstance(n.func, ast.Name) else (n.func.attr if isinstance(n.func, ast.Attribute) else None)
                if nom != c["fn"] or len(n.args) > len(c["params"]):
                    continue
                try:
                    args = dict(zip(c["params"], [ast.literal_eval(a) for a in n.args]))
                    for k in n.keywords:
                        if k.arg is None:
                            raise ValueError
                        args[k.arg] = ast.literal_eval(k.value)
                except Exception:
                    continue
                if all(p in args or p in c["defauts"] for p in c["params"]) and set(args) <= set(c["params"]):
                    complet = {p: args[p] if p in args else ast.literal_eval(c["defauts"][p]) for p in c["params"]}
                    if _exact(complet):
                        trouves.append(complet)
    return trouves


class Delai(Exception):
    pass


def _executer(f, kw, secondes, lignes):
    """Appelle f(**kw) avec un délai et relève les lignes du code `<candidat>` parcourues (la couverture)."""
    limite = time.perf_counter() + secondes

    def local(frame, event, arg):
        if event == "line":
            lignes.add((frame.f_code.co_name, frame.f_lineno))
        if time.perf_counter() > limite:
            raise Delai()
        return local

    def globale(frame, event, arg):
        return local if frame.f_code.co_filename == "<candidat>" else None
    ancien = sys.gettrace()
    sys.settrace(globale)
    try:
        return f(**kw)
    finally:
        sys.settrace(ancien)


def _exact(sortie):
    """La valeur survit-elle EXACTEMENT au tour JSON (ni tuple, ni ensemble, ni octets, ni clé entière, ni nombre spécial) ?"""
    try:
        return json.loads(json.dumps(sortie, ensure_ascii=False)) == sortie
    except (TypeError, ValueError, RecursionError):
        return False


def synthetiser(c, capturees=(), budget_s=8.0):
    """Cherche un corpus qui PROUVE la fonction. Rend {"ok": bool, "cas": [(nom, [args])], "raison": str, "couverture": float, "sorties": int}."""
    ns = {}
    vide = {"ok": False, "cas": [], "couverture": 0, "sorties": 0}
    try:
        exec(compile(c["texte"], "<candidat>", "exec"), ns)
        f = ns[c["fn"]]
    except Exception as e:
        return dict(vide, raison="la fermeture ne s'exécute pas seule : %s" % type(e).__name__)
    arbre = ast.parse(c["texte"])
    fn = next(n for n in arbre.body if isinstance(n, ast.FunctionDef) and n.name == c["fn"])
    attendues = {x.lineno for x in ast.walk(fn) if isinstance(x, ast.stmt) and x is not fn and not (isinstance(x, ast.Expr) and isinstance(x.value, ast.Constant))}
    graine = int(hashlib.sha256((c["module"] + c["fn"]).encode()).hexdigest()[:8], 16)
    hasard = random.Random(graine)
    lit = litteraux(c["module"])
    consts = _constantes(arbre)
    piscines = [_piscine(p, c["defauts"].get(p), c["annotations"].get(p), _usage(fn, p), lit, consts, hasard) for p in c["params"]]
    candidats = [dict(x) for x in list(capturees) + recolter(c)]
    total = 1
    for v, _ in piscines:
        total *= max(1, len(v))
    if not piscines:
        combos = [{}]
    elif total <= 2000:
        combos = [dict(zip(c["params"], v)) for v in itertools.product(*[p[0] for p in piscines])]
        hasard.shuffle(combos)
    else:
        combos = []
        for _ in range(3000):
            kw = {}
            for p, (valeurs, npref) in zip(c["params"], piscines):
                kw[p] = valeurs[hasard.randrange(npref)] if npref and hasard.random() < 0.85 else valeurs[hasard.randrange(len(valeurs))]
            combos.append(kw)
    reussis, vus = [], set()
    debut = time.perf_counter()
    for kw in candidats + combos:
        if time.perf_counter() - debut > budget_s or len(reussis) >= 400:
            break
        cle = json.dumps(kw, sort_keys=True, ensure_ascii=False, default=repr)
        if cle in vus:
            continue
        vus.add(cle)
        avant = copy.deepcopy(kw)
        lignes = set()
        copie = copy.deepcopy(kw)
        try:
            r1 = _executer(f, copie, 0.5, lignes)
            if copie != avant:
                return dict(vide, raison="modifie ses entrées")
            r2 = _executer(f, copy.deepcopy(kw), 0.5, set())
        except Exception:
            continue
        if r1 != r2 or not _exact(r1):
            continue
        reussis.append((kw, r1, {l[1] for l in lignes if l[1] in attendues}, kw in candidats))
    if not reussis:
        return dict(vide, raison="entrées introuvables (aucun des %d essais ne rend un résultat exact)" % len(vus))
    # le choix : d'abord ce qui AJOUTE de la couverture, puis les sorties encore jamais vues, puis de quoi élargir le corpus
    garde, couvertes, sorties = [], set(), set()
    for kw, r, ls, _ in sorted(reussis, key=lambda t: (not t[3], -len(t[2]))):
        sk = json.dumps(r, sort_keys=True, ensure_ascii=False)
        if (ls - couvertes) or sk not in sorties:
            garde.append(kw)
            couvertes |= ls
            sorties.add(sk)
        if len(garde) >= CAS_MAX:
            break
    for kw, r, ls, _ in reussis:
        if len(garde) >= 14:
            break
        if kw not in garde:
            garde.append(kw)
            sorties.add(json.dumps(r, sort_keys=True, ensure_ascii=False))
    couv = len(couvertes) / max(1, len(attendues))
    toutes_bool = all(isinstance(r, bool) for _, r, _, _ in reussis)
    if len(garde) < CAS_MIN:
        return dict(vide, raison="entrées introuvables (%d cas valides sur %d essais)" % (len(reussis), len(vus)), couverture=round(couv, 2), sorties=len(sorties))
    if len(sorties) < 2:
        return dict(vide, raison="sorties trop uniformes (%d distinctes)" % len(sorties), couverture=round(couv, 2), sorties=len(sorties))
    if couv < COUVERTURE_MIN:
        return dict(vide, raison="couverture insuffisante (%d %%)" % int(couv * 100), couverture=round(couv, 2), sorties=len(sorties))
    cas = [("cas %02d" % (i + 1), [kw[p] for p in c["params"]]) for i, kw in enumerate(garde)]
    return {"ok": True, "raison": "", "cas": cas, "couverture": round(couv, 2), "sorties": len(sorties)}



# ── 2 bis. la capture des appels réels ──────────────────────────────────────────
def capturer(module, candidats, delai=420):
    """Rejoue les bancs du module en observant les appels des fonctions candidates : leurs arguments RÉELS (un message lu, une fiche, une règle), la meilleure matière d'un corpus. Dans un sous-processus."""
    tests = sorted((RACINE / "tests").glob("CN_test_%s*.py" % module))
    if not tests or not candidats:
        return {}
    import tempfile
    sortie = Path(tempfile.mkdtemp()) / "captures.json"
    cibles = {c["fn"]: {"fichier": c["fichier"], "params": c["params"]} for c in candidats}
    try:
        subprocess.run([sys.executable, str(Path(__file__).resolve()), "--capture", module, str(sortie), json.dumps(cibles)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=str(RACINE), timeout=delai)
    except subprocess.TimeoutExpired:
        print("  (capture de %s : bancs trop longs sous observation, entrées synthétisées seulement)" % module)
        return {}
    if sortie.exists():
        return json.loads(sortie.read_text(encoding="utf-8"))
    return {}


def _capture_interne(module, sortie, cibles):
    import os
    import unittest
    captures = {fn: [] for fn in cibles}
    vus = {fn: set() for fn in cibles}
    suffixes = {fn: "/" + c["fichier"] for fn, c in cibles.items()}

    def profil(frame, event, arg):
        if event != "call":
            return
        co = frame.f_code
        fn = co.co_name
        if fn not in cibles or len(captures[fn]) >= 120 or not co.co_filename.replace("\\", "/").endswith(suffixes[fn]):
            return
        try:
            kw = {p: copy.deepcopy(frame.f_locals[p]) for p in cibles[fn]["params"]}
            if not _exact(kw):
                return
            cle = json.dumps(kw, sort_keys=True, ensure_ascii=False)
        except Exception:
            return
        if cle not in vus[fn]:
            vus[fn].add(cle)
            captures[fn].append(kw)
    tests = sorted((RACINE / "tests").glob("CN_test_%s*.py" % module))
    suite = unittest.TestLoader().loadTestsFromNames(["tests." + t.stem for t in tests])
    sys.setprofile(profil)
    try:
        unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(suite)
    finally:
        sys.setprofile(None)
    Path(sortie).write_text(json.dumps(captures, ensure_ascii=False), encoding="utf-8")


# ── 3. l'extraction ────────────────────────────────────────────────────────────
def nom_de_point(module, fn, fichier):
    base = re.sub(r"[^a-z0-9_]", "_", fn.strip("_").lower()) or "point"
    manifeste = lire(RACINE / "modules" / module / "CN_manifeste.toml")
    pris = lambda p: ('id = "%s"' % p) in manifeste or (RACINE / "modules" / module / "points" / ("EC_%s.py" % p)).exists()
    if pris(base):
        base = base + "_" + re.sub(r"[^a-z0-9]", "", Path(fichier).stem.lower().replace("cn_", ""))
    n, p = 2, base
    while pris(p):
        p = "%s_%d" % (base, n)
        n += 1
    return p


def _entete_def(n):
    ret = (" -> " + ast.unparse(n.returns)) if n.returns else ""
    return "def %s(%s)%s:" % (n.name, ast.unparse(n.args), ret)


def poser_facade(c, point, objet):
    """Remplace la fonction par sa façade (signature gardée, appel du point) ; pose, une fois par fichier, `_point` et `_appeler_point` ; branche ctx.point. Rend les chemins touchés."""
    f = RACINE / c["fichier"]
    brut = f.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in brut else "\n"
    src = brut.replace("\r\n", "\n")
    arbre = ast.parse(src)
    n = next(x for x in arbre.body if isinstance(x, ast.FunctionDef) and x.name == c["fn"])
    lignes = src.split("\n")
    corps = '    return _appeler_point("%s", {%s})["valeur"]' % (point, ", ".join('"%s": %s' % (p, p) for p in c["params"]))
    doc = c["doc"] or c["fn"]
    fac = [_entete_def(n), '    """%s. Le calcul est un POINT D\'ÉVOLUTION : points/EC_%s.py."""' % (doc.replace('"""', "'''"), point), corps]
    premiere = min(x.lineno for x in arbre.body if isinstance(x, ast.FunctionDef))
    lignes[n.lineno - 1:n.end_lineno] = fac
    texte = "\n".join(lignes)
    if "def _appeler_point(" not in texte:
        a_definir = any(isinstance(x, ast.FunctionDef) and x.name == "_point" for x in arbre.body) or re.search(r"^_point\s*=", texte, re.M)
        prelude = (PRELUDE_SANS_POINT if a_definir else PRELUDE).rstrip("\n").split("\n")
        l2 = texte.split("\n")
        pos = min(x.lineno for x in ast.parse(texte).body if isinstance(x, ast.FunctionDef)) - 1
        pos = max(pos, 0)
        while pos > 0 and l2[pos - 1].lstrip().startswith("#"):
            pos -= 1
        l2[pos:pos] = prelude + ["", ""]
        texte = "\n".join(l2)
    ast.parse(texte)
    f.write_bytes(texte.replace("\n", nl).encode("utf-8"))
    touches = [f]
    g = RACINE / "modules" / c["module"] / "CN_module.py"
    b = g.read_bytes().decode("utf-8")
    nl2 = "\r\n" if "\r\n" in b else "\n"
    t2 = b.replace("\r\n", "\n")
    ligne = "    global _point\n    _point = ctx.point" if objet == "ce module" else "    %s._point = ctx.point" % objet
    if ligne not in t2:
        marque = "def brancher(ctx):\n"
        t2 = t2.replace(marque, marque + ligne + "\n", 1)
        ast.parse(t2)
        g.write_bytes(t2.replace("\n", nl2).encode("utf-8"))
    if g not in touches:
        touches.append(g)
    return touches


def _mettre_a_jour_version(module):
    """Une version corrective de plus pour le module touché (le déploiement vérifie les modules qui ont changé)."""
    m = re.search(r'^version\s*=\s*"(\d+)\.(\d+)\.(\d+)"', lire(RACINE / "modules" / module / "CN_manifeste.toml"), re.M)
    if not m:
        return
    a, b, c = (int(x) for x in m.groups())
    subprocess.run([sys.executable, str(RACINE / "outils" / "CN_bornes.py"), "--monter", module, "%d.%d.%d" % (a, b, c + 1)], capture_output=True, cwd=str(RACINE))


def extraire_un(c, objet, capturees=(), verbeux=True):
    """Extrait UNE fonction ; revient en arrière si quoi que ce soit échoue. Rend (point, resume) ou (None, raison)."""
    s = synthetiser(c, capturees)
    if not s["ok"]:
        return None, s["raison"]
    point = nom_de_point(c["module"], c["fn"], c["fichier"])
    suivis = [RACINE / c["fichier"], RACINE / "modules" / c["module"] / "CN_module.py", RACINE / "modules" / c["module"] / "CN_manifeste.toml", RACINE / "tests" / "CN_test_points_reels.py"]
    avant = {p: p.read_bytes() for p in suivis}
    crees = [RACINE / "modules" / c["module"] / "points" / ("EC_%s.py" % point), RACINE / "modules" / c["module"] / "contrats" / ("CN_%s.json" % point),
             RACINE / "modules" / c["module"] / "contrats" / ("CN_%s.corpus.json" % point)]

    def revenir(raison):
        for p, o in avant.items():
            p.write_bytes(o)
        for p in crees:
            if p.exists():
                p.unlink()
        return None, raison
    spec = {"module": c["module"], "point": point, "titre": c["doc"] or c["fn"], "source": c["fichier"], "fonctions": [c["fn"]],
            "appel": {"fn": c["fn"], "params": c["params"], "sortie": "valeur"}, "cas": s["cas"],
            "libelle": "%s (extrait automatiquement de %s)" % (c["doc"] or c["fn"], Path(c["fichier"]).name),
            "role": (c["doc"] or c["fn"]) + ".", "methode": "fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.",
            "invariants": ["la sortie est identique à celle de l'ancien code sur chaque cas du corpus", "aucune entrée n'est modifiée", "la sortie survit exactement au tour JSON"]}
    try:
        X.extraire(spec)
    except SystemExit as e:
        return revenir("mesure : %s" % e)
    except Exception as e:
        return revenir("extraction : %s %s" % (type(e).__name__, e))
    try:
        poser_facade(c, point, objet)
    except Exception as e:
        return revenir("façade : %s %s" % (type(e).__name__, e))
    ok, sortie = bancs_du_module(c["module"])
    if not ok:
        return revenir("bancs du module : " + sortie)
    return point, "%d cas · couverture %d %% · %d sorties distinctes" % (len(s["cas"]), int(s["couverture"] * 100), s["sorties"])


def bancs_du_module(module, delai=600):
    tests = sorted((RACINE / "tests").glob("CN_test_%s*.py" % module))
    if not tests:
        return True, ""
    noms = ["tests." + t.stem for t in tests]
    r = subprocess.run([sys.executable, "-m", "unittest"] + noms, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(RACINE), timeout=delai)
    if r.returncode != 0:
        fins = [l for l in (r.stderr or "").splitlines() if l.startswith(("FAIL:", "ERROR:"))]
        return False, "; ".join(fins[:2]) or (r.stderr or "")[-200:]
    return True, ""


def sceller(fichiers_touches, module):
    chemins = sorted({str(p.relative_to(RACINE)).replace("\\", "/") for p in fichiers_touches})
    subprocess.run(["git", "-C", str(RACINE), "add", "--"] + chemins, capture_output=True)
    for p in chemins:
        subprocess.run([sys.executable, str(RACINE / "outils" / "CN_bornes.py"), "--sceller", p], capture_output=True, cwd=str(RACINE))
    subprocess.run([sys.executable, str(RACINE / "outils" / "CN_entete.py"), "--ecrire"], capture_output=True, cwd=str(RACINE))


# ── 4. la ligne de commande ────────────────────────────────────────────────────
def charger_exceptions():
    return json.loads(EXCEPTIONS.read_text(encoding="utf-8")) if EXCEPTIONS.exists() else {}


def principal(argv):
    if len(argv) < 2 or argv[1] not in ("lister", "extraire"):
        print(__doc__)
        return 2
    args = argv[2:]
    seul = args[args.index("--module") + 1] if "--module" in args else None
    maxi = int(args[args.index("--max") + 1]) if "--max" in args else 10 ** 6
    bal = balayer(seul)
    if argv[1] == "lister":
        raisons = {}
        for m, d in bal.items():
            for fn, r in d["rejets"]:
                k = re.sub(r"\(.*?\)|: .*", "", r).strip()
                raisons[k] = raisons.get(k, 0) + 1
        n = sum(len(d["candidats"]) for d in bal.values())
        print("%d fonctions éligibles dans %d modules" % (n, sum(1 for d in bal.values() if d["candidats"])))
        for m, d in bal.items():
            if d["ignore"]:
                print("  %-14s IGNORÉ : %s" % (m, d["ignore"]))
            elif d["candidats"]:
                print("  %-14s %3d : %s" % (m, len(d["candidats"]), ", ".join(x["fn"] for x in d["candidats"][:8]) + (" …" if len(d["candidats"]) > 8 else "")))
        print("\nraisons de rejet (toutes fonctions) :")
        for k, v in sorted(raisons.items(), key=lambda t: -t[1])[:14]:
            print("  %5d  %s" % (v, k))
        return 0
    fait, rate, vus = 0, {}, 0
    for m, d in bal.items():
        if d["ignore"] or not d["candidats"]:
            continue
        br = branchement(m)
        touches = []
        captures = capturer(m, d["candidats"])
        for c in d["candidats"]:
            if vus >= maxi:
                break
            vus += 1
            if en_cours_ailleurs(m) and not touches:
                break
            objet = br[Path(c["fichier"]).name]
            t0 = time.perf_counter()
            point, resume = extraire_un(c, objet, captures.get(c["fn"], ()))
            if point:
                fait += 1
                touches += [RACINE / c["fichier"], RACINE / "modules" / m / "CN_module.py", RACINE / "modules" / m / "CN_manifeste.toml", RACINE / "tests" / "CN_test_points_reels.py",
                            RACINE / "modules" / m / "points" / ("EC_%s.py" % point), RACINE / "modules" / m / "contrats" / ("CN_%s.json" % point), RACINE / "modules" / m / "contrats" / ("CN_%s.corpus.json" % point)]
                print("  ✓ %s.%s  %s  (%.1f s)" % (m, point, resume, time.perf_counter() - t0))
            else:
                rate["%s:%s:%s" % (m, c["fichier"].split("/")[-1], c["fn"])] = resume
                print("  · %s.%s  non extraite : %s" % (m, c["fn"], resume))
        if touches:
            sceller(touches, m)
            _mettre_a_jour_version(m)
            sceller([RACINE / "modules" / m / "CN_manifeste.toml"], m)
    print("\n%d extraites ; %d laissées au nexus, avec leur raison" % (fait, len(rate)))
    if "--exceptions" in args:
        scannes = {m for m, d in bal.items() if not d["ignore"]}
        ex = {k: r for k, r in charger_exceptions().items() if k.split(":")[0] not in scannes}
        ex.update(rate)
        EXCEPTIONS.write_text(json.dumps(ex, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 4 and sys.argv[1] == "--capture":
        _capture_interne(sys.argv[2], sys.argv[3], json.loads(sys.argv[4]))
        sys.exit(0)
    sys.exit(principal(sys.argv))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : lire, git, modules, en_cours_ailleurs, fichiers, branchement, _locaux, _etat_partage …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
