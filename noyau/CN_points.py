# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les points d'évolution : résolution, garde de contrat, disjoncteur
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #310ef2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : appelle un point d'évolution (données en entrée, données en sortie), sert l'EC en service si elle est saine, sinon la référence du dépôt.
# MÉTHODE    : valide l'entrée et la sortie par le contrat, copie les données à chaque frontière, compte les fautes d'une EC et la suspend au troisième écart en dix minutes.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=310ef2 ▼▼▼
"""Les points d'évolution (docs/CN_NEXUS.md, docs/CN_FORMAT.md, docs/CN_EVOLUTION.md §2 sexies).

Un module déclare des points ([[points_evolution]]) : des fonctions PURES dont le dépôt écrit la RÉFÉRENCE. Une EC (évoluée, rangée dans le stock, jamais dans
le dossier du module) peut la remplacer. Ici vit tout ce qui garantit que, quoi que fasse l'EC, l'utilisateur ne voit jamais une réponse non conforme :

  1. DONNÉES en entrée, DONNÉES en sortie : chaque appel passe par une copie JSON (aucun objet partagé, aucun état de l'EC ne fuit) ;
  2. le CONTRAT (un schéma JSON neutre) valide l'entrée et la sortie ;
  3. le RÉSOLVEUR STATIQUE : une EC n'est servie que si son contrat prouvé est compatible avec celui du nexus (même majeure, mineure <=) ;
  4. le DISJONCTEUR : une sortie hors contrat, une exception, un délai dépassé, une dérive de sens (comparaison par échantillon) comptent une faute ;
     la référence répond DANS LE MÊME APPEL ; trois fautes en dix minutes suspendent l'EC (conservée, jamais détruite) ;
  5. l'EC n'est jamais chargée si elle est impure (analyse de l'arbre syntaxique) ou si son environnement d'exécution n'a pas d'hôte.
Aucune EC n'existe encore : le stock est vide, c'est la référence qui sert. Le mécanisme est en place avant la première EC.
"""
from __future__ import annotations

import ast
import atexit
import hashlib
import hmac
import json
import os
import queue
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import types
import time
import uuid
from collections import deque
from pathlib import Path

SEUIL_FAUTES = 3                   # fautes d'une EC avant suspension
FENETRE_S = 600                    # ... dans cette fenêtre (dix minutes)
MAX_ELEMENTS_VALIDES = 1000        # éléments d'une liste vérifiés un à un (au-delà : une faute, jamais un « conforme » partiel)
MEMOIRE_EC_MO = 1024               # plafond d'adresses d'un travailleur d'EC (POSIX)
DEMARRAGE_EC_S = 5.0               # temps minimal laissé à un travailleur pour démarrer et charger l'EC (au moins le double du délai d'un appel)
FLUSH_STATS_S = 1.0                # une statistique d'appels est écrite au plus toutes les secondes
DISTINCTS_MAX = 400                # entrées distinctes retenues par l'ombre (empreintes)
ECHANTILLON_DEFAUT = 50            # en service, un appel sur N est comparé à la référence (dérive de sens que le schéma ne voit pas)

STDLIB_PURE = {"__future__", "math", "re", "json", "itertools", "functools", "collections", "dataclasses", "typing", "enum", "fractions", "decimal", "string",
               "textwrap", "unicodedata", "operator", "copy", "heapq", "bisect", "statistics", "hashlib", "base64", "struct", "abc", "numbers", "ipaddress", "datetime", "shlex", "email", "html", "quopri", "binascii"}
# Une horloge ou un hasard lu par un attribut (datetime.now(), random.choice…) rendrait l'EC non déterministe : refusé même si le module est pur.
ATTRIBUTS_INTERDITS = {"now", "today", "utcnow", "fromtimestamp", "utcfromtimestamp", "monotonic", "perf_counter", "random", "randint", "choice", "shuffle", "uuid4", "urandom"}
NOMS_INTERDITS = {"ctx", "self", "cls", "open", "print", "input", "exec", "eval", "__import__", "compile", "globals", "locals",
                  "__builtins__", "getattr", "setattr", "delattr", "vars", "dir", "type", "object", "breakpoint", "help", "memoryview", "hasattr"}
# La cage de l'EC (audit C2) : l'analyse refuse ce qui sort de l'EC par réflexion, l'exécution la prive des fonctions natives dangereuses. Aucun des deux ne suffit seul,
# et aucun ne remplace un processus séparé (docs/CN_EVOLUTION.md) : tant qu'il n'existe pas, seules des EC de référence signées doivent être chargées.
ATTRIBUTS_REFLEXION = {"mro", "attrgetter", "methodcaller", "Formatter", "format_map", "vformat", "get_field", "ForwardRef", "get_type_hints", "make_dataclass", "gi_frame", "gi_code"}
PREFIXES_REFLEXION = ("f_", "gi_", "cr_", "ag_", "tb_", "co_")      # cadres, générateurs, traces et code : f_globals, f_back, tb_frame, co_code…
_FORMAT_ATTRIBUT = re.compile(r"\{[^{}:!]*\.[^{}]*\}")                 # « {0.__class__} » : une chaîne de format qui lit un attribut


def _dunder(nom: str) -> bool:
    return len(nom) > 4 and nom.startswith("__") and nom.endswith("__")


class PointInconnu(KeyError):
    """Ce point n'est déclaré par aucun module actif."""


class ContratViole(ValueError):
    """L'ENTRÉE ne respecte pas le contrat : c'est l'appelant qui se trompe, pas l'EC."""


class PointDefaillant(RuntimeError):
    """La RÉFÉRENCE du dépôt échoue ou viole son propre contrat : un défaut du dépôt, jamais masqué."""


class DelaiEC(RuntimeError):
    """Une EC n'a pas rendu la main dans son délai : son processus a été tué (une boucle sans fin, une expression régulière catastrophique)."""


class ErreurEC(RuntimeError):
    """L'EC, dans son processus, a échoué (impure au chargement, exception, mémoire épuisée)."""


# ── le contrat : un sous-ensemble volontairement petit de JSON Schema ─────────
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def _est(valeur, t: str) -> bool:
    if t == "number":
        return isinstance(valeur, (int, float)) and not isinstance(valeur, bool)
    if t == "integer":
        return isinstance(valeur, int) and not isinstance(valeur, bool)
    return isinstance(valeur, _TYPES[t])


def valider(schema, valeur, chemin: str = "$") -> list:
    """Rend la liste des écarts entre `valeur` et `schema` (vide : conforme). Lecteur TOLÉRANT : un champ en plus n'est jamais une faute.
    Pris en charge : type, enum, required, properties, items."""
    if not schema:
        return []
    fautes = []
    t = schema.get("type")
    if t is not None:
        types = [t] if isinstance(t, str) else list(t)
        if not any(_est(valeur, x) for x in types):
            return ["%s : attendu %s" % (chemin, " ou ".join(types))]
    if "enum" in schema and valeur not in schema["enum"]:
        fautes.append("%s : valeur hors de %s" % (chemin, schema["enum"]))
    if isinstance(valeur, dict):
        for k in schema.get("required", []):
            if k not in valeur:
                fautes.append("%s.%s : champ obligatoire absent" % (chemin, k))
        propres = schema.get("properties") or {}
        for k, sous in propres.items():
            if k in valeur:
                fautes += valider(sous, valeur[k], "%s.%s" % (chemin, k))
        if schema.get("additionalProperties") is False:
            fautes += ["%s.%s : champ non prévu par le contrat" % (chemin, k) for k in valeur if k not in propres][:3]
    if isinstance(valeur, list):
        if "maxItems" in schema and len(valeur) > schema["maxItems"]:
            fautes.append("%s : %d éléments pour un maximum de %s" % (chemin, len(valeur), schema["maxItems"]))
        if schema.get("items"):
            for i, x in enumerate(valeur[:MAX_ELEMENTS_VALIDES]):
                fautes += valider(schema["items"], x, "%s[%d]" % (chemin, i))
            if len(valeur) > MAX_ELEMENTS_VALIDES:
                fautes.append("%s : %d éléments, trop pour être validés (plafond %d)" % (chemin, len(valeur), MAX_ELEMENTS_VALIDES))
    if isinstance(valeur, str) and "maxLength" in schema and len(valeur) > schema["maxLength"]:
        fautes.append("%s : %d caractères pour un maximum de %s" % (chemin, len(valeur), schema["maxLength"]))
    return fautes


def compatible(prouve: str, courant: str) -> bool:
    """Le résolveur statique : une EC prouvée sur le contrat `prouve` sert un nexus au contrat `courant` si c'est la même majeure et que sa mineure n'est pas plus récente."""
    try:
        a, b = (tuple(int(x) for x in v.split(".")) for v in (prouve, courant))
    except ValueError:
        return False
    return a[0] == b[0] and a[1] <= b[1]


def analyser_purete(source: str) -> list:
    """Les règles d'une EC Python : aucune entrée/sortie, aucun état, ni ctx ni heure ni hasard (docs/CN_NEXUS.md §3, conditions 1 et 2)."""
    try:
        arbre = ast.parse(source)
    except SyntaxError as e:
        return ["syntaxe illisible (%s)" % e.msg]
    fautes = set()
    dans_classe = {id(x) for c in ast.walk(arbre) if isinstance(c, ast.ClassDef) for x in ast.walk(c)}       # `self` et `cls` ne sont interdits qu'HORS d'une classe du fichier : un module n'a pas de « self »
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] not in STDLIB_PURE:
                    fautes.add("import interdit : " + a.name)
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] not in STDLIB_PURE:
                fautes.add("import interdit : %s" % n.module)
        elif isinstance(n, ast.Name) and n.id in NOMS_INTERDITS and not (n.id in ("self", "cls") and id(n) in dans_classe):
            fautes.add("nom interdit : " + n.id)
        elif isinstance(n, ast.Attribute) and n.attr in ATTRIBUTS_INTERDITS:
            fautes.add("horloge ou hasard : ." + n.attr)
        elif isinstance(n, ast.arg) and n.arg in NOMS_INTERDITS and not (n.arg in ("self", "cls") and id(n) in dans_classe):
            fautes.add("paramètre interdit : " + n.arg)
        elif isinstance(n, (ast.Global, ast.Nonlocal, ast.Await, ast.Yield)):
            fautes.add("global / nonlocal / await / yield")
    fautes |= _fautes_reflexion(arbre)
    return sorted(fautes)


def _fautes_reflexion(arbre) -> set:
    """Ce qui permet à une EC de sortir d'elle-même sans importer ni ouvrir quoi que ce soit : tout nom ou attribut `__xxx__`, la lecture d'attributs par une chaîne,
    les cadres d'exécution, les décorateurs et les métaclasses."""
    fautes = set()
    appels_super = {id(c.func) for c in ast.walk(arbre) if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute) and c.func.attr == "__init__"
                    and isinstance(c.func.value, ast.Call) and isinstance(c.func.value.func, ast.Name) and c.func.value.func.id == "super"}      # le SEUL `__x__` toléré : l'appel `super().__init__(…)`
    for n in ast.walk(arbre):
        if isinstance(n, ast.Name) and _dunder(n.id):
            fautes.add("réflexion interdite : " + n.id)
        elif isinstance(n, ast.arg) and _dunder(n.arg):
            fautes.add("réflexion interdite : " + n.arg)
        elif isinstance(n, ast.Attribute):
            if id(n) in appels_super:
                continue
            if _dunder(n.attr):
                fautes.add("réflexion interdite : ." + n.attr)
            elif n.attr in ATTRIBUTS_REFLEXION or n.attr.startswith(PREFIXES_REFLEXION):
                fautes.add("réflexion interdite : ." + n.attr)
            elif n.attr == "format" and not (isinstance(n.value, ast.Constant) and isinstance(n.value.value, str)):
                fautes.add("format interdit : .format sur autre chose qu'une chaîne littérale")
            elif n.attr == "format" and _FORMAT_ATTRIBUT.search(n.value.value):
                fautes.add("format interdit : la chaîne lit un attribut")
        elif isinstance(n, ast.ImportFrom):
            if any(a.name == "*" or _dunder(a.name) or a.name in ATTRIBUTS_REFLEXION for a in n.names):
                fautes.add("import interdit : from %s import * / réflexion" % n.module)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.decorator_list:
            fautes.add("décorateur interdit : " + n.name)
        elif isinstance(n, ast.AsyncFunctionDef):
            fautes.add("fonction asynchrone interdite : " + n.name)
        elif isinstance(n, ast.ClassDef) and any(k.arg in (None, "metaclass") for k in n.keywords):
            fautes.add("métaclasse interdite : " + n.name)
    return fautes


# ── l'exécution : des fonctions natives en liste blanche, des imports filtrés ─
_NATIVES_SURES = ("len range min max sum sorted reversed enumerate zip map filter any all abs round divmod pow int float str bool list dict set tuple frozenset bytes "
                  "bytearray complex slice isinstance issubclass callable iter next repr ascii chr ord hex bin oct hash format super property staticmethod classmethod").split()
_EXCEPTIONS_SURES = ("Exception ValueError TypeError KeyError IndexError LookupError ArithmeticError ZeroDivisionError OverflowError AttributeError RuntimeError "
                     "NotImplementedError StopIteration AssertionError UnicodeError UnicodeDecodeError UnicodeEncodeError RecursionError").split()


def _vue(module):
    """Une VUE d'un module importé : ses noms publics, sans les modules qu'il a lui-même importés (email.utils.os, functools.sys…). Seuls ses propres sous-modules passent."""
    nom = module.__name__

    class Vue:
        __slots__ = ()

        def __getattr__(self, attr):
            if attr.startswith("_") and attr not in ("_",):
                raise AttributeError(attr)
            v = getattr(module, attr)
            if isinstance(v, types.ModuleType):
                if v.__name__.startswith(nom + "."):
                    return _vue(v)
                raise AttributeError(attr)
            return v

        def __repr__(self):
            return "<module %s>" % nom
    return Vue()


# Les deux seuls modules que la bibliothèque standard autorisée importe pour son PROPRE compte quand une EC appelle datetime.strptime (_strptime)
# ou strftime/timestamp (time). MESURÉ en instrumentant le filtre : aucun autre nom n'est demandé. Ils ne s'ouvrent jamais à une instruction
# `import` écrite dans l'EC (refusée aussi par l'analyse statique) : voir _import_interne.
IMPORTS_INTERNES = frozenset({"_strptime", "time"})


def _import_interne(nom, liste, niveau) -> bool:
    """Vrai si l'import vient d'un appel de la bibliothèque autorisée (CALL), faux s'il vient d'une instruction `import` de l'EC (IMPORT_NAME)."""
    if niveau or liste or nom not in IMPORTS_INTERNES:
        return False
    try:
        import dis
        import sys
        f = sys._getframe(2)               # 0 = ici, 1 = _import_filtre, 2 = le code de l'EC (l'appelant, directement ou par une fonction C)
        return f.f_code.co_code[f.f_lasti] != dis.opmap["IMPORT_NAME"]
    except Exception:
        return False                       # dans le doute : refusé


def _import_filtre(nom, globaux=None, locaux=None, liste=(), niveau=0):
    import builtins as _b
    if _import_interne(nom, liste, niveau):
        return _b.__import__(nom, None, None, (), 0)       # le module réel : la bibliothèque appelle ses fonctions privées (_strptime._strptime_datetime)
    if niveau or nom.split(".")[0] not in STDLIB_PURE:
        raise ImportError("import interdit dans une EC : " + nom)
    return _vue(_b.__import__(nom, None, None, liste, 0))


def builtins_restreints() -> dict:
    """Le `__builtins__` d'une EC : la liste blanche des natives et des exceptions, un import filtré (STDLIB_PURE, modules rendus en vue). Ni open, ni getattr, ni type."""
    import builtins as _b
    d = {k: getattr(_b, k) for k in _NATIVES_SURES + _EXCEPTIONS_SURES if hasattr(_b, k)}
    d.update({"__build_class__": _b.__build_class__, "__import__": _import_filtre, "NotImplemented": NotImplemented, "Ellipsis": Ellipsis, "True": True, "False": False, "None": None})
    return d


def executer_ec(texte: str, nom: str, espace: dict) -> None:
    """Le SEUL endroit où le noyau exécute le texte d'une EC : `espace` reçoit les natives restreintes avant l'exécution."""
    espace["__builtins__"] = builtins_restreints()
    exec(compile(texte, nom, "exec"), espace)


def _champs(texte: str) -> dict:
    """L'en-tête d'un fichier (docs/CN_FORMAT.md §2), lu dans ses soixante premières lignes."""
    out = {}
    for l in texte.splitlines()[:60]:
        m = re.match(r"^\s*(?:#|//|;;|--)\s*([A-ZÉÔÈ][A-ZÉÔÈ ]{1,14}?)\s*:\s*(.*?)\s*$", l)
        if m:
            out.setdefault(m.group(1).strip(), m.group(2))
    return out


# ── les hôtes d'exécution : un par langage, derrière la même interface ───────
class HotePython:
    """Charge un fichier Python par son chemin (jamais par un import de package) et rend sa fonction. Le noyau ne suppose pas que l'EC est du Python : cet hôte
    n'est que le premier ; d'autres (wasm, node, php) se brancheront derrière la même interface sans changer un seul module."""

    def __init__(self):
        self._cache = {}
        self._verrou = threading.Lock()

    def appelable_verifie(self, chemin: Path, fonction: str, empreinte: str):
        """Comme appelable, mais le texte lu doit avoir l'empreinte de celui qui a été VÉRIFIÉ (pureté, contrat) : sinon le fichier a changé entre-temps."""
        return self._charger(chemin, fonction, empreinte)

    def appelable(self, chemin: Path, fonction: str):
        return self._charger(chemin, fonction, "")

    def _charger(self, chemin: Path, fonction: str, attendue: str):
        """Compile le TEXTE lu, jamais le bytecode du disque : Python réutilise un .pyc si la date (à la seconde) et la taille du source n'ont pas changé, et une EC
        réécrite de même taille servirait alors l'ancien code. Le cache est clé sur le contenu (empreinte du texte), pas sur une date."""
        octets = chemin.read_bytes()
        texte = octets.decode("utf-8")
        emp = hashlib.sha256(octets).hexdigest()
        if attendue and emp != attendue:
            raise RuntimeError("le fichier d'EC a changé entre sa vérification et son chargement")
        cle = (str(chemin), emp)
        with self._verrou:
            if cle not in self._cache:
                mod = types.ModuleType("cassandra_point_" + hashlib.sha1(str(chemin).encode()).hexdigest()[:10])
                mod.__file__ = str(chemin)
                executer_ec(texte, str(chemin), mod.__dict__)
                self._cache[cle] = getattr(mod, fonction)
            return self._cache[cle]


class BacIndisponible(ErreurEC):
    """Le bac à sable exigé (mode « requis ») n'existe pas sur cette machine : l'EC ne sert pas, la référence répond. Ce n'est pas une faute de l'EC."""


_BAC: dict = {}
_BAC_VERROU = threading.Lock()


def _candidats_bac() -> list:
    """Les enveloppes Linux possibles, de la plus stricte à la plus simple : (nom, préfixe de commande). Rien d'autre que des outils déjà là (pas d'installation, pas de root)."""
    racine = str(Path(__file__).resolve().parent)
    out = []
    b = shutil.which("bwrap")
    if b:
        lie, vus = ["--tmpfs", "/tmp"], set()                   # le /tmp vide d'abord : un dossier lié PLUS BAS (le code lui-même sous /tmp) reste visible, jamais recouvert
        for p in (sys.base_prefix, sys.prefix, sys.exec_prefix, "/usr", "/lib", "/lib64", "/bin", "/etc/alternatives", racine):
            if p not in vus and os.path.exists(p):
                vus.add(p)
                lie += ["--ro-bind", p, p]
        out.append(("bwrap", [b, "--unshare-all", "--die-with-parent", "--new-session", "--clearenv", *lie, "--proc", "/proc", "--dev", "/dev", "--chdir", "/tmp"]))
    u = shutil.which("unshare")
    if u:
        out.append(("unshare", [u, "--user", "--map-root-user", "--net", "--ipc", "--uts", "--pid", "--fork", "--kill-child"]))
    return out


def _bac_marche(prefixe: list) -> bool:
    """Un bac n'est cru qu'après avoir fait tourner le TRAVAILLEUR dedans (il se charge, charge une fonction et répond) : un outil présent mais inutilisable, ou un bac qui cache le code du travailleur, ne compte pas."""
    racine = Path(__file__).resolve().parent
    dossier = tempfile.mkdtemp(prefix="cn_ec_bac_")
    proc = None
    try:
        proc = subprocess.Popen([*prefixe, sys.executable, "-I", str(racine / "CN_ec_worker.py"), str(racine / "CN_points.py"), str(256 * 1024 * 1024)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=dossier, bufsize=0, start_new_session=(os.name == "posix"))
        msg = {"op": "charger", "texte": "def f(x):\n    return x\n", "fonction": "f"}
        proc.stdin.write((json.dumps(msg) + "\n").encode("ascii"))
        proc.stdin.flush()
        reponse = queue.Queue()
        threading.Thread(target=lambda: reponse.put(proc.stdout.readline()), daemon=True).start()
        ligne = reponse.get(timeout=20)
        return json.loads(ligne.decode("ascii")).get("ok") is True
    except Exception:
        return False
    finally:
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        shutil.rmtree(dossier, ignore_errors=True)


def bac_os_mode_valide(mode) -> bool:
    return mode in ("aucun", "auto", "requis")


def bac_os(mode: str = "auto") -> tuple:
    """(préfixe de commande, nom du bac). `mode` : « aucun » (rien), « auto » (le meilleur qui marche, sinon rien), « requis » (le meilleur qui marche, sinon BacIndisponible :
    l'EC ne s'exécute pas sans). Linux seulement ; ailleurs, seuls le processus à part, le délai et le plafond de ressources gardent."""
    if mode not in ("aucun", "auto", "requis"):
        raise ValueError("bac_os inconnu : %r (aucun, auto, requis)" % (mode,))
    if mode == "aucun":
        return [], "aucun"
    with _BAC_VERROU:                       # un seul essai à la fois : deux fils qui démarrent ensemble n'éprouvent pas le bac deux fois
        if "choisi" not in _BAC:
            choisi = ([], "aucun")
            if sys.platform.startswith("linux"):
                for nom, prefixe in _candidats_bac():
                    if _bac_marche(prefixe):
                        choisi = (prefixe, nom)
                        break
            _BAC["choisi"] = choisi
    prefixe, nom = _BAC["choisi"]
    if mode == "requis" and nom == "aucun":
        raise BacIndisponible("bac à sable requis, introuvable (bwrap ou unshare utilisables, sous Linux) : l'EC ne s'exécute pas")
    return list(prefixe), nom


class _Travailleur:
    """Un processus Python à part qui a chargé UNE EC. Un seul échange à la fois ; au délai, le processus est tué (jamais attendu)."""

    def __init__(self, memoire_mo: int, bac: str = "auto"):
        racine = Path(__file__).resolve().parent
        prefixe, self.bac = bac_os(bac)                                   # lève BacIndisponible AVANT de créer quoi que ce soit si le bac exigé manque
        self._dossier = tempfile.mkdtemp(prefix="cn_ec_")
        env = {k: v for k, v in os.environ.items() if k in ("SYSTEMROOT", "PATH", "TEMP", "TMP", "LANG", "LC_ALL")}      # rien d'autre du serveur : pas de clé, pas de jeton
        self.proc = subprocess.Popen([*prefixe, sys.executable, "-I", str(racine / "CN_ec_worker.py"), str(racine / "CN_points.py"), str(int(memoire_mo) * 1024 * 1024)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=self._dossier, env=env, bufsize=0,
                                     start_new_session=(os.name == "posix"))       # son propre groupe : on tue aussi ce que l'enveloppe a lancé
        self._q: queue.Queue = queue.Queue()
        self._verrou = threading.Lock()
        threading.Thread(target=self._lire, daemon=True, name="ec-lecteur").start()

    def _lire(self):
        try:
            for ligne in iter(self.proc.stdout.readline, b""):
                self._q.put(ligne)
        except Exception:
            pass
        self._q.put(None)

    def vivant(self) -> bool:
        return self.proc.poll() is None

    def echange(self, msg: dict, delai_s: float) -> dict:
        with self._verrou:
            if not self.vivant():
                raise ErreurEC("le processus de l'EC n'est plus là")
            try:
                self.proc.stdin.write((json.dumps(msg) + "\n").encode("ascii"))
            except (OSError, ValueError) as e:
                self.tuer()
                raise ErreurEC("le processus de l'EC ne répond plus (%s)" % e)
            try:
                ligne = self._q.get(timeout=max(0.05, delai_s))
            except queue.Empty:
                self.tuer()
                raise DelaiEC("délai de %.1f s dépassé : processus de l'EC tué" % delai_s)
            if ligne is None:
                raise ErreurEC("le processus de l'EC s'est arrêté (mémoire épuisée ou fin brutale)")
            return json.loads(ligne.decode("utf-8"))

    def tuer(self):
        try:
            if os.name == "posix":
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except OSError:
                    pass
            self.proc.kill()
            self.proc.wait(timeout=5)
        except Exception:
            pass
        try:
            self.proc.stdin.close()
            self.proc.stdout.close()
        except Exception:
            pass
        try:
            os.rmdir(self._dossier)
        except OSError:
            pass


class HoteProcessus:
    """L'hôte des EC dans un PROCESSUS À PART par fichier d'EC : la seule vraie frontière entre ce que le noyau exécute et ce qu'un modèle a écrit.
    Délai tenu par la mort du processus, mémoire plafonnée (POSIX), environnement vidé. Même interface que HotePython."""

    def __init__(self, memoire_mo: int = MEMOIRE_EC_MO, bac: str = "auto"):
        self.memoire_mo = int(memoire_mo)
        self.bac = bac
        self._delai_s = 2.0
        self._travailleurs: dict = {}
        self._verrou = threading.RLock()
        atexit.register(self.fermer)

    def appelable_verifie(self, chemin: Path, fonction: str, empreinte: str, delai_ms: int = 2000):
        return self._appelable(chemin, fonction, empreinte, delai_ms)

    def appelable(self, chemin: Path, fonction: str, delai_ms: int = 2000):
        return self._appelable(chemin, fonction, "", delai_ms)

    def _travailleur(self, chemin: Path, fonction: str, attendue: str) -> tuple:
        cle = (str(chemin), attendue)
        with self._verrou:
            t = self._travailleurs.get(cle) if attendue else None
            if t is not None and t.vivant():
                return cle, t
        octets = chemin.read_bytes()
        emp = hashlib.sha256(octets).hexdigest()
        if attendue and emp != attendue:
            raise RuntimeError("le fichier d'EC a changé entre sa vérification et son chargement")
        cle = (str(chemin), emp)
        with self._verrou:
            t = self._travailleurs.get(cle)
            if t is not None and t.vivant():
                return cle, t
            for autre in [k for k in self._travailleurs if k[0] == str(chemin) and k != cle]:        # une autre version du même fichier : l'ancienne s'en va
                self._travailleurs.pop(autre).tuer()
            t = _Travailleur(self.memoire_mo, self.bac)
            try:
                r = t.echange({"op": "charger", "texte": octets.decode("utf-8"), "fonction": fonction}, max(DEMARRAGE_EC_S, 2 * self._delai_s))
            except Exception:
                t.tuer()
                raise
            if not r.get("ok"):
                t.tuer()
                raise ErreurEC(r.get("erreur") or "chargement refusé")
            self._travailleurs[cle] = t
            return cle, t

    def _appelable(self, chemin: Path, fonction: str, attendue: str, delai_ms: int):
        delai_s = max(0.05, float(delai_ms) / 1000.0)
        self._delai_s = delai_s
        cle, t = self._travailleur(chemin, fonction, attendue)           # le démarrage se paie ici, hors du délai de l'appel

        def appeler(entree):
            nonlocal t
            if not t.vivant():                                           # tué au dernier délai : un neuf, chargé du même texte
                _, t = self._travailleur(chemin, fonction, cle[1])
            try:
                r = t.echange({"op": "appeler", "entree": entree}, delai_s)
            except DelaiEC:
                with self._verrou:
                    self._travailleurs.pop(cle, None)
                raise
            if not r.get("ok"):
                raise ErreurEC(r.get("erreur") or "échec de l'EC")
            return r["sortie"]
        return appeler

    def fermer(self):
        with self._verrou:
            for t in list(self._travailleurs.values()):
                t.tuer()
            self._travailleurs.clear()


class CandidatIsole:
    """Un candidat (du texte que personne n'a relu) chargé dans son PROCESSUS, pour l'évaluateur : jamais exécuté dans le serveur.
    Le chargement, chaque appel et le chronométrage ont un délai ; au délai, le processus est tué. `fermer()` le libère toujours."""

    def __init__(self, texte: str | None = None, fonction: str = "", delai_ms: int = 2000, memoire_mo: int = MEMOIRE_EC_MO, bac: str = "auto"):
        """Sans `texte`, ne fait que préparer le processus : `charger` y met ensuite des candidats l'un après l'autre (les pièges en essaient quarante)."""
        self.delai_s = max(0.05, float(delai_ms) / 1000.0)
        self._memoire, self._bac = memoire_mo, bac
        self._t = _Travailleur(memoire_mo, bac)
        if texte is not None:
            try:
                self.charger(texte, fonction)
            except Exception:
                self.fermer()
                raise

    def charger(self, texte: str, fonction: str) -> None:
        """Charge un candidat (le précédent est oublié). Un processus tué au dernier délai est remplacé par un neuf. Lève DelaiEC (boucle au chargement) ou ErreurEC (impur, illisible)."""
        if not self._t.vivant():
            self._t = _Travailleur(self._memoire, self._bac)
        r = self._t.echange({"op": "charger", "texte": texte, "fonction": fonction}, max(DEMARRAGE_EC_S, 2 * self.delai_s))
        if not r.get("ok"):
            raise ErreurEC(r.get("erreur") or "chargement refusé")

    def __call__(self, entree):
        if not self._t.vivant():
            raise ErreurEC("le processus du candidat est mort")
        r = self._t.echange({"op": "appeler", "entree": entree}, self.delai_s)
        if not r.get("ok"):
            raise ErreurEC(r.get("erreur") or "échec du candidat")
        return r["sortie"]

    def chrono(self, ref: str, cand: str, fonction: str, entrees: list, passes: int, delai_total_s: float) -> list:
        """Les durées (référence, candidat, référence bis) de chaque entrée, en ms, mesurées À FROID dans le processus du candidat."""
        r = self._t.echange({"op": "chrono", "ref": ref, "cand": cand, "fonction": fonction, "entrees": entrees, "passes": int(passes)}, delai_total_s)
        if not r.get("ok"):
            raise ErreurEC(r.get("erreur") or "chronométrage refusé")
        return r["t"]

    def fermer(self):
        self._t.tuer()


HOTES = {"python": HotePython}
HOTES_ISOLES = {"python": HoteProcessus}


def _tranche(entree) -> int:
    """Une tranche de 0 à 99, STABLE pour une entrée donnée : le routage par part envoie toujours la même entrée du même côté."""
    return int(hashlib.sha256(json.dumps(entree, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:8], 16) % 100


def _canon(valeur) -> str:
    """Le texte JSON d'une valeur, ordre des clés CONSERVÉ : deux sorties sont les mêmes si elles s'écrivent pareil (1 et 1.0, True et 1, deux ordres de clés ne le sont pas)."""
    return json.dumps(valeur, ensure_ascii=False, separators=(",", ":"))


def _copie(valeur):
    """Une frontière de données : ce qui passe est du JSON, copié. Un objet qui n'en est pas lève TypeError."""
    return json.loads(json.dumps(valeur))


class _Declare:
    def __init__(self, module: str, p, dossier: Path, contrat: dict, reference):
        self.module, self.p, self.dossier, self.contrat, self.reference = module, p, dossier, contrat, reference
        self.gid = "%s.%s" % (module, p.id)
        self.fautes = deque()
        self.suspendue = None
        self.appels = 0
        self.ec_appels = 0
        self.refus = ""
        self.ombre = None                  # {"gen", "appels", "ecarts", "erreurs", "ms_ref", "ms_ec", "distincts"} de CE processus, pour la génération d'ombre en cours
        self.dernier_flush = 0.0
        self.flushe = False                # ce processus a-t-il écrit son fichier de statistiques ?


def _vide_ombre(gen) -> dict:
    return {"gen": gen, "appels": 0, "ecarts": 0, "erreurs": 0, "ms_ref": deque(maxlen=100), "ms_ec": deque(maxlen=100), "distincts": []}


class ServicePoints:
    def __init__(self, stock=None, enregistreur=None, alerte=None, horloge=time.monotonic, echantillon: int = 0, isolation: str = "processus",
                 memoire_mo: int = MEMOIRE_EC_MO, exiger_sceau: bool = False, cle: bytes | None = None, bac_os: str = "auto"):
        """`stock` : le dossier des EC (jamais dans modules/). `enregistreur(gid, entree, sortie, duree_ms, source)` : la matière du rejeu.
        `alerte(gid, texte)` : appelé à la suspension d'une EC. `echantillon` : un appel sur N compare l'EC à la référence (0 : jamais).
        `isolation` : « processus » (une EC tourne dans un processus à part, tué au délai) ou « fil » (dans le serveur : pour des EC de référence signées et des bancs).
        `bac_os` : l'enveloppe du système autour du processus d'EC (« auto », « requis » = pas de bac, pas d'EC, « aucun »).
        `exiger_sceau` : une EC ne sert que si elle porte le sceau (HMAC) posé par l'évolution, et le routage n'est cru que signé ; la clé est `cle` ou <stock>.cle."""
        self.stock = Path(stock) if stock else None
        self.enregistreur, self.alerte, self._horloge, self.echantillon = enregistreur, alerte, horloge, int(echantillon)
        self.isolation, self.memoire_mo, self.exiger_sceau, self.bac_os = isolation, int(memoire_mo), bool(exiger_sceau), bac_os
        self._cle_val = cle
        self._ident = "%d-%s" % (os.getpid(), uuid.uuid4().hex[:8])        # une instance = un fichier de statistiques à elle (deux processus, ou deux démarrages, ne s'écrasent pas)
        self._points: dict = {}
        self._erreurs: dict = {}
        self._hotes: dict = {}
        self._hotes_ec: dict = {}
        self._verrou = threading.RLock()
        self._vstat = threading.Lock()
        self._decisions: dict = {}
        self._routes: dict = {}
        if self.isolation == "processus" and bac_os_mode_valide(self.bac_os) and self.bac_os != "aucun" and sys.platform.startswith("linux"):
            threading.Thread(target=self._eprouver_bac, daemon=True, name="ec-bac").start()      # le bac s'éprouve au démarrage, pas au premier appel d'un utilisateur

    def _eprouver_bac(self):
        try:
            bac_os(self.bac_os)
        except Exception:
            pass

    def fermer(self):
        """Arrête les processus d'EC (à l'arrêt du serveur, ou quand on veut repartir de zéro)."""
        for h in list(self._hotes_ec.values()):
            h.fermer()
        self._hotes_ec.clear()

    def __del__(self):
        try:
            self.fermer()                                 # un service qu'on lâche (un banc, un rechargement) ne laisse pas ses processus d'EC derrière lui
        except Exception:
            pass

    # ── la clé et les sceaux : ce qui lie un fichier du stock à la décision de l'évolution ──
    def _cle(self):
        if self._cle_val is not None:
            return self._cle_val
        if not (self.exiger_sceau and self.stock):
            return None
        f = self.stock.parent / (self.stock.name + ".cle")
        try:
            self._cle_val = f.read_bytes()
        except OSError:
            f.parent.mkdir(parents=True, exist_ok=True)
            try:
                fd = os.open(str(f), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as h:
                    h.write(os.urandom(32))
            except FileExistsError:
                pass
            self._cle_val = f.read_bytes()
        return self._cle_val

    def _mac(self, *parties) -> str:
        return hmac.new(self._cle(), "|".join(str(x) for x in parties).encode("utf-8"), hashlib.sha256).hexdigest()

    def sceller(self, module: str, point: str, nom: str) -> dict:
        """Pose le sceau d'un fichier d'EC du stock : son nom et l'empreinte de son contenu, signés. Appelé par l'évolution qui vient de le prouver."""
        d = self._points.get("%s.%s" % (module, point))
        if d is None:
            raise PointInconnu("%s.%s" % (module, point))
        s = self._dossier_stock(d)
        emp = hashlib.sha256((s / nom).read_bytes()).hexdigest()
        sceau = {"fichier": nom, "sha256": emp, "mac": self._mac("sceau", d.gid, nom, emp) if self._cle() is not None else ""}
        self._ecrire_atomique(s / "SCEAU.json", json.dumps(sceau))
        return sceau

    def _sceau_ok(self, d: _Declare, s: Path, nom: str, emp: str) -> str:
        """Vide si le sceau convient, sinon la raison du refus."""
        if not self.exiger_sceau:
            return ""
        try:
            sc = json.loads((s / "SCEAU.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "aucun sceau : cette EC n'a pas été posée par l'évolution"
        if sc.get("fichier") != nom or sc.get("sha256") != emp:
            return "le fichier d'EC n'est pas celui qui a été prouvé (sceau)"
        if not hmac.compare_digest(str(sc.get("mac", "")), self._mac("sceau", d.gid, nom, emp)):
            return "sceau invalide"
        return ""

    @staticmethod
    def _ecrire_atomique(chemin: Path, texte: str):
        tmp = chemin.with_name(chemin.name + ".tmp")
        tmp.write_text(texte, encoding="utf-8")
        tmp.replace(chemin)

    # ── déclaration ──────────────────────────────────────────────────────
    def declarer(self, manifeste, dossier) -> list:
        """Enregistre les points d'un module. Rend la liste des défauts (référence ou contrat introuvables) : un point défaillant refuse d'être appelé, il ne se tait pas."""
        dossier = Path(dossier)
        defauts = []
        for p in getattr(manifeste, "points_evolution", ()):
            gid = "%s.%s" % (manifeste.id, p.id)
            ref = [f for f in dossier.glob(p.reference + ".*") if f.suffix not in (".borne", ".pyc")]
            fichier_contrat = dossier / "contrats" / ("CN_%s.json" % p.id.replace(".", "_"))
            try:
                if len(ref) != 1:
                    raise PointDefaillant("%s : la référence « %s.* » doit être UN fichier (trouvé %d)" % (gid, p.reference, len(ref)))
                if not fichier_contrat.exists():
                    raise PointDefaillant("%s : contrat introuvable (%s) : sans contrat rien ne se vérifie, le point refuse d'exister" % (gid, fichier_contrat.name))
                contrat = json.loads(fichier_contrat.read_text(encoding="utf-8"))
                if not isinstance(contrat, dict) or not contrat.get("sortie"):
                    raise PointDefaillant("%s : le contrat doit décrire une sortie" % gid)
                self._points[gid] = _Declare(manifeste.id, p, dossier, contrat, ref[0])
                self._erreurs.pop(gid, None)
            except (PointDefaillant, ValueError) as e:
                self._erreurs[gid] = str(e)
                defauts.append(str(e))
        return defauts

    def points(self, module: str | None = None) -> list:
        return sorted(g for g, d in self._points.items() if module is None or d.module == module)

    def reference(self, module: str, point: str) -> dict:
        """Ce que l'évaluateur compare à un candidat : le fichier de la référence, sa fonction, son contrat, et l'appelable de la référence (la spécification)."""
        d = self._points.get("%s.%s" % (module, point))
        if d is None:
            raise PointInconnu("%s.%s" % (module, point))
        return {"gid": d.gid, "fichier": d.reference, "fonction": d.p.fonction, "runtime": d.p.runtime, "contrat": d.contrat, "version_contrat": d.p.contrat,
                "appelable": self._executer(d, d.reference, d.p.runtime)}

    # ── le stock : l'EC en service ───────────────────────────────────────
    def _dossier_stock(self, d: _Declare):
        return self.stock / d.module / d.p.id if self.stock else None

    @staticmethod
    def _stat_cle(chemin: Path):
        try:
            st = chemin.stat()
            return (st.st_mtime_ns, st.st_size, getattr(st, "st_ino", 0))
        except OSError:
            return None

    def _ec_en_service(self, d: _Declare):
        """Rend (fichier, version, runtime, empreinte) de l'EC à servir, ou None. Toute raison de ne pas la servir est gardée dans d.refus (visible par etat()).
        La décision est mémorisée tant que ni l'EC, ni son sceau, ni son contrat ne bougent (un appel ne relit pas et ne rehache pas le fichier)."""
        d.refus = ""
        s = self._dossier_stock(d)
        if s is None:
            return None
        try:
            nom = (s / "ACTIVE").read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if d.suspendue or (s / "SUSPENDUE.json").exists():
            d.refus = "suspendue"
            return None
        if not nom or Path(nom).name != nom:
            d.refus = "ACTIVE désigne un chemin qui sort du dossier de l'EC"
            return None
        f = s / nom
        sf = self._stat_cle(f)
        if sf is None or not f.is_file():
            d.refus = "le fichier d'EC désigné est introuvable"
            return None
        ck = (str(f), sf, self._stat_cle(s / "SCEAU.json"), d.p.contrat)
        dec = self._decisions.get(d.gid)
        if dec is not None and dec[0] == ck:
            d.refus = dec[2]
            return dec[1]
        resultat, refus = self._decider(d, s, nom, f)
        self._decisions[d.gid] = (ck, resultat, refus)
        d.refus = refus
        return resultat

    def _decider(self, d: _Declare, s: Path, nom: str, f: Path):
        if os.name == "posix" and f.stat().st_mode & 0o022:
            return None, "le fichier d'EC est modifiable par d'autres que son propriétaire"
        octets = f.read_bytes()
        emp = hashlib.sha256(octets).hexdigest()
        ok, raison, version, runtime = self._verifier_ec(d, f, octets)
        if ok:
            raison = self._sceau_ok(d, s, nom, emp)
            ok = not raison
        if not ok:
            if raison.startswith("impure"):
                self._suspendre(d, raison, version)
            return None, raison
        return (f, version, runtime, emp), ""

    def _verifier_ec(self, d: _Declare, f: Path, octets: bytes):
        try:
            texte = octets.decode("utf-8")
        except UnicodeDecodeError:
            return (False, "fichier binaire : en-tête requis dans un compagnon .borne", "", "")
        champs = _champs(texte)
        version = champs.get("VERSION EC", "EC?").split()[0]
        if champs.get("ZONE") != "EC":
            return (False, "le fichier n'est pas de ZONE EC", version, "")
        runtime = champs.get("RUNTIME", "")
        if runtime not in HOTES:
            return (False, "environnement d'exécution sans hôte : « %s »" % runtime, version, runtime)
        prouve = champs.get("CONTRAT PROUVÉ", "").lstrip("@").strip()
        if not compatible(prouve, d.p.contrat):
            return (False, "contrat prouvé « %s » incompatible avec le contrat du nexus « %s »" % (prouve or "?", d.p.contrat), version, runtime)
        if runtime == "python":
            fautes = analyser_purete(texte)
            if fautes:
                return (False, "impure : " + " ; ".join(fautes[:3]), version, runtime)
        return (True, "", version, runtime)

    # ── l'appel ──────────────────────────────────────────────────────────
    def _executer(self, d: _Declare, fichier: Path, runtime: str, empreinte: str = "", ec: bool = False):
        """L'appelable d'un fichier. Pour une EC (`ec`) en mode « processus », c'est un appel vers SON processus, tué au délai du contrat.
        Avec `empreinte` (celle du contenu VÉRIFIÉ), l'hôte refuse un fichier qui a changé entre la vérification et le chargement."""
        if ec and self.isolation == "processus" and runtime in HOTES_ISOLES:       # un autre langage a son hôte, derrière la même interface
            hote = self._hotes_ec.get(runtime) or self._hotes_ec.setdefault(runtime, HOTES_ISOLES[runtime](self.memoire_mo, self.bac_os))
            return hote.appelable_verifie(fichier, d.p.fonction, empreinte, self._delai(d)) if empreinte else hote.appelable(fichier, d.p.fonction, self._delai(d))
        hote = self._hotes.get(runtime) or self._hotes.setdefault(runtime, HOTES[runtime]())
        if empreinte and hasattr(hote, "appelable_verifie"):
            return hote.appelable_verifie(fichier, d.p.fonction, empreinte)
        return hote.appelable(fichier, d.p.fonction)

    @staticmethod
    def _delai(d: _Declare) -> int:
        return int(d.contrat.get("delai_ms") or d.p.delai_ms)

    def appeler(self, module: str, point: str, entree, compte: str | None = None):
        """`compte` : le compte au nom duquel on appelle (rien si c'est le noyau) ; il n'est transmis qu'au corpus de rejeu, pour que ses entrées restent rattachées à qui les a produites."""
        gid = "%s.%s" % (module, point)
        with self._verrou:
            d = self._points.get(gid)
        if d is None:
            if gid in self._erreurs:
                raise PointDefaillant(self._erreurs[gid])
            raise PointInconnu(gid)
        try:
            entree = _copie(entree)
        except (TypeError, ValueError) as e:
            raise ContratViole("%s : l'entrée n'est pas du JSON (%s)" % (gid, e)) from e
        fautes = valider(d.contrat.get("entree"), entree)
        if fautes:
            raise ContratViole("%s : %s" % (gid, " ; ".join(fautes[:3])))
        t0 = time.perf_counter()
        sortie, source = None, "reference"
        ec = self._ec_en_service(d)
        route = self._routage(d) if ec else None
        servir_ec = bool(ec) and route["mode"] == "service" and (route["part"] >= 100 or _tranche(entree) < route["part"])      # une tranche STABLE : la même entrée va toujours du même côté
        if servir_ec:
            fichier, version, runtime, emp = ec
            with self._vstat:
                d.ec_appels += 1
            try:
                brute = self._executer(d, fichier, runtime, emp, ec=True)(_copie(entree))
                candidate = _copie(brute)
                ecarts = valider(d.contrat.get("sortie"), candidate)
                if ecarts:
                    raise ContratViole("sortie hors contrat : " + " ; ".join(ecarts[:3]))
                ms = (time.perf_counter() - t0) * 1000
                delai = self._delai(d)
                if ms > delai:
                    self._faute(d, "délai dépassé : %d ms pour un plafond de %d ms" % (ms, delai), version)
                sortie, source = candidate, version
            except BacIndisponible:                      # le bac exigé manque : ce n'est pas la faute de l'EC, la référence répond
                sortie = None
            except Exception as e:                       # toute faute d'une EC, de quelque nature : la référence répond DANS LE MÊME APPEL
                self._faute(d, "%s : %s" % (type(e).__name__, e), version)
                sortie = None
        if sortie is None:
            try:
                ref = self._executer(d, d.reference, d.p.runtime)(_copie(entree))
                sortie = _copie(ref)
            except Exception as e:
                raise PointDefaillant("%s : la référence du dépôt a échoué (%s : %s)" % (gid, type(e).__name__, e)) from e
            ecarts = valider(d.contrat.get("sortie"), sortie)
            if ecarts:
                raise PointDefaillant("%s : la référence viole son propre contrat : %s" % (gid, " ; ".join(ecarts[:3])))
            source = "reference"
        ms_ref = (time.perf_counter() - t0) * 1000
        if ec and route["mode"] == "ombre":                       # l'ombre : la RÉFÉRENCE a répondu ; l'EC calcule à côté sur le même appel et on compare
            self._ombre(d, ec, entree, sortie, ms_ref, route.get("gen"))
        with self._vstat:
            d.appels += 1
            n = d.appels
        if source != "reference" and self.echantillon and n % self.echantillon == 0:
            self._comparer(d, entree, sortie, source)
        self._flush(d)
        ms = (time.perf_counter() - t0) * 1000
        if self.enregistreur:
            try:
                try:
                    self.enregistreur(gid, entree, sortie, ms, source, compte=compte)
                except TypeError as e:
                    if "compte" not in str(e):
                        raise
                    self.enregistreur(gid, entree, sortie, ms, source)          # un enregistreur d'avant les comptes
            except Exception:
                pass
        return sortie

    # ── le routage : ombre, puis une part croissante du trafic ──────────────
    def _routage(self, d: _Declare) -> dict:
        """Où en est la mise en service de l'EC : « ombre » (elle calcule, la référence répond), « service » avec une part de 0 à 100 % des appels, ou « arret ».
        Sans fichier de routage, un fichier illisible ou un fichier au sceau faux : « arret ». Une EC n'est jamais servie sans qu'on l'ait dit (échec fermé)."""
        s = self._dossier_stock(d)
        if s is None:
            return {"mode": "arret", "part": 0, "gen": None}
        f = s / "ROUTAGE.json"
        sf = self._stat_cle(f)
        if sf is None:
            return {"mode": "arret", "part": 0, "gen": None}
        cache = self._routes.get(d.gid)
        if cache is not None and cache[0] == sf:
            return cache[1]
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            if r.get("mode") not in ("ombre", "service", "arret"):
                raise ValueError("mode")
            res = {"mode": r["mode"], "part": max(0, min(100, int(r.get("part", 0)))), "gen": r.get("gen")}
            if self.exiger_sceau and not hmac.compare_digest(str(r.get("mac", "")), self._mac("routage", d.gid, res["mode"], res["part"], res["gen"])):
                raise ValueError("signature")
        except (OSError, ValueError, TypeError):
            res = {"mode": "arret", "part": 0, "gen": None}
        self._routes[d.gid] = (sf, res)
        return res

    def router(self, module: str, point: str, mode: str, part: int = 0) -> dict:
        """Pose le routage (écriture atomique, signée si le sceau est exigé) : la mise en service par paliers, et le RETOUR INSTANTANÉ (« arret » ou part 0) : un aiguillage, rien à restaurer.
        Une GÉNÉRATION d'ombre (un identifiant) naît à chaque passage en ombre : les statistiques de l'ombre ne mélangent jamais deux pièces."""
        d = self._points.get("%s.%s" % (module, point))
        if d is None:
            raise PointInconnu("%s.%s" % (module, point))
        if mode not in ("ombre", "service", "arret"):
            raise ValueError("mode inconnu : %r (ombre, service, arret)" % (mode,))
        s = self._dossier_stock(d)
        if s is None:
            raise ValueError("aucun stock d'EC : rien à router")
        self._dossier_prive(s)
        part = max(0, min(100, int(part)))
        gen = uuid.uuid4().hex[:12] if mode == "ombre" else (self._routage(d).get("gen") or uuid.uuid4().hex[:12])
        r = {"mode": mode, "part": part, "gen": gen, "depuis": time.strftime("%Y-%m-%d %H:%M:%S")}
        if self._cle() is not None:
            r["mac"] = self._mac("routage", d.gid, mode, part, gen)
        self._ecrire_atomique(s / "ROUTAGE.json", json.dumps(r))
        self._routes.pop(d.gid, None)
        if mode == "ombre":
            with self._vstat:
                d.ombre = _vide_ombre(gen)
            self._flush(d, force=True)
        return {"mode": mode, "part": part, "gen": gen, "depuis": r["depuis"]}

    @staticmethod
    def _dossier_prive(s: Path):
        """Le dossier d'une EC n'est ni lisible ni modifiable par d'autres que le serveur (POSIX)."""
        s.mkdir(parents=True, exist_ok=True)
        if os.name == "posix":
            for p in (s, s.parent, s.parent.parent):
                try:
                    os.chmod(p, 0o700)
                except OSError:
                    pass

    # ── les statistiques : en mémoire, écrites à côté, lues par tous les processus ──
    def _flush(self, d: _Declare, force: bool = False):
        s = self._dossier_stock(d)
        if s is None or not s.exists():
            return
        maintenant = time.monotonic()
        if not force and maintenant - d.dernier_flush < FLUSH_STATS_S:
            return
        d.dernier_flush = maintenant
        with self._vstat:
            o = d.ombre
            doc = {"appels": d.appels, "ec": d.ec_appels, "ombre": None if o is None else {"gen": o["gen"], "appels": o["appels"], "ecarts": o["ecarts"], "erreurs": o["erreurs"],
                                                                                           "ms_ref": list(o["ms_ref"]), "ms_ec": list(o["ms_ec"]), "distincts": list(o["distincts"])}}
        try:
            self._ecrire_atomique(s / ("STATS-%s.json" % self._ident), json.dumps(doc))
            d.flushe = True
        except OSError:
            pass

    def _cumul(self, d: _Declare) -> dict:
        """Ce que tous les processus qui servent ce point ont fait (le serveur et le démon du Sensorium), toutes instances confondues, ombre de la génération en cours seulement."""
        self._flush(d, force=True)
        s = self._dossier_stock(d)
        gen = self._routage(d).get("gen") if s is not None else None
        appels = ec = 0
        o = {"appels": 0, "ecarts": 0, "erreurs": 0, "ms_ref": [], "ms_ec": [], "distincts": set()}
        vu = False
        if s is not None:
            for f in sorted(s.glob("STATS-*.json")):
                try:
                    doc = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                appels += int(doc.get("appels", 0))
                ec += int(doc.get("ec", 0))
                x = doc.get("ombre")
                if x and gen and x.get("gen") == gen:
                    vu = True
                    for k in ("appels", "ecarts", "erreurs"):
                        o[k] += int(x.get(k, 0))
                    o["ms_ref"] += x.get("ms_ref", [])
                    o["ms_ec"] += x.get("ms_ec", [])
                    o["distincts"] |= set(x.get("distincts", []))
        if not d.flushe:                                    # ce processus n'a pas (encore) de fichier : ses compteurs en mémoire comptent
            appels += d.appels
            ec += d.ec_appels
        return {"appels": appels, "ec": ec, "ombre": o if vu else None}

    def _ombre(self, d: _Declare, ec, entree, sortie_ref, ms_ref: float, gen=None):
        fichier, version, runtime, emp = ec
        with self._vstat:
            if d.ombre is None or d.ombre["gen"] != gen:                  # une autre pièce est passée par là (un autre processus a posé une ombre neuve) : on repart de zéro
                d.ombre = _vide_ombre(gen)
            o = d.ombre
        t = time.perf_counter()
        h = hashlib.sha256(json.dumps(entree, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:12]
        try:
            candidate = _copie(self._executer(d, fichier, runtime, emp, ec=True)(_copie(entree)))
            ms_ec = (time.perf_counter() - t) * 1000
            ecarts = valider(d.contrat.get("sortie"), candidate)
            with self._vstat:
                o["appels"] += 1
                o["ms_ref"].append(ms_ref)
                o["ms_ec"].append(ms_ec)
                if h not in o["distincts"] and len(o["distincts"]) < DISTINCTS_MAX:
                    o["distincts"].append(h)
            if ecarts or _canon(candidate) != _canon(sortie_ref):
                with self._vstat:
                    o["ecarts"] += 1
                self._faute(d, "ombre : " + ("sortie hors contrat" if ecarts else "la sortie diffère de celle de la référence"), version)
        except BacIndisponible:
            return                                                # sans le bac exigé, l'ombre ne tourne pas : rien à compter
        except Exception as e:                                    # une EC qui plante en ombre ne touche personne, mais elle est comptée
            with self._vstat:
                o["appels"] += 1
                o["erreurs"] += 1
            self._faute(d, "ombre : %s : %s" % (type(e).__name__, e), version)
        self._flush(d, force=True)

    def _comparer(self, d: _Declare, entree, sortie, source: str):
        """La couche 5 : un échantillon d'appels est confronté à la référence. Une différence est une dérive de SENS que le schéma ne voit pas."""
        try:
            ref = _copie(self._executer(d, d.reference, d.p.runtime)(_copie(entree)))
        except Exception:
            return
        if _canon(ref) != _canon(sortie):
            self._faute(d, "dérive de sens : la sortie diffère de celle de la référence", source)

    # ── le disjoncteur ───────────────────────────────────────────────────
    def _faute(self, d: _Declare, raison: str, version: str):
        with self._verrou:
            t = self._horloge()
            d.fautes.append(t)
            while d.fautes and t - d.fautes[0] > FENETRE_S:
                d.fautes.popleft()
            if len(d.fautes) >= SEUIL_FAUTES:
                self._suspendre(d, "%d fautes en %d s, dernière : %s" % (len(d.fautes), FENETRE_S, raison), version)

    def _suspendre(self, d: _Declare, raison: str, version: str):
        with self._verrou:
            if d.suspendue:
                return
            d.suspendue = {"depuis": time.strftime("%Y-%m-%d %H:%M:%S"), "raison": raison, "version": version}
            s = self._dossier_stock(d)
            if s is not None:
                try:
                    self._dossier_prive(s)
                    (s / "SUSPENDUE.json").write_text(json.dumps(d.suspendue, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
        if self.alerte:
            try:
                self.alerte(d.gid, "EC %s suspendue sur %s : %s. La référence du dépôt sert ; l'EC est conservée." % (version, d.gid, raison))
            except Exception:
                pass

    def reactiver(self, module: str, point: str) -> bool:
        """Lève la suspension d'une EC (la réparation, la décision de l'admin, ou l'arrivée d'une pièce neuve) : le compte des fautes repart de zéro."""
        d = self._points.get("%s.%s" % (module, point))
        if d is None:
            raise PointInconnu("%s.%s" % (module, point))
        with self._verrou:
            d.suspendue = None
            d.fautes.clear()
            s = self._dossier_stock(d)
            if s is not None and (s / "SUSPENDUE.json").exists():
                (s / "SUSPENDUE.json").unlink()
            self._decisions.clear()
            self._routes.clear()
            self._hotes.clear()                              # un hôte garde le fichier chargé : une EC réécrite sous le même nom, dans la même fraction de seconde, ne doit pas servir l'ancienne
            self.fermer()
        return True

    def etat(self, module: str, point: str) -> dict:
        d = self._points.get("%s.%s" % (module, point))
        if d is None:
            raise PointInconnu("%s.%s" % (module, point))
        ec = self._ec_en_service(d)
        s = self._dossier_stock(d)
        suspendue = d.suspendue
        if suspendue is None and s is not None and (s / "SUSPENDUE.json").exists():
            suspendue = json.loads((s / "SUSPENDUE.json").read_text(encoding="utf-8"))
        cumul = self._cumul(d)
        r = self._routage(d) if (s is not None and (s / "ACTIVE").exists()) else None
        return {"point": d.gid, "contrat": d.p.contrat, "runtime": d.p.runtime, "sert": ec[1] if ec else "reference", "ec_refusee": getattr(d, "refus", ""),
                "suspendue": suspendue, "fautes_recentes": len(d.fautes), "appels": cumul["appels"], "ec_appels": cumul["ec"], "isolation": self.isolation, "bac": self._nom_bac(),
                "routage": None if r is None else {"mode": r["mode"], "part": r["part"]}, "ombre": self._resume_ombre(cumul["ombre"])}

    def _nom_bac(self) -> str:
        """Le bac retenu, SANS l'éprouver : l'état d'un écran ne lance jamais un sous-processus. Tant qu'il n'est pas éprouvé (au démarrage, en arrière-plan), « à éprouver »."""
        if self.isolation != "processus" or self.bac_os == "aucun":
            return "aucun"
        if "choisi" not in _BAC:
            return "à éprouver"
        nom = _BAC["choisi"][1]
        return "indisponible" if (self.bac_os == "requis" and nom == "aucun") else nom

    @staticmethod
    def _resume_ombre(o):
        if not o:
            return None
        mr = statistics.median(o["ms_ref"]) if o["ms_ref"] else None
        me = statistics.median(o["ms_ec"]) if o["ms_ec"] else None
        return {"appels": o["appels"], "ecarts": o["ecarts"], "erreurs": o["erreurs"], "distincts": len(o["distincts"]), "ref_ms": mr, "ec_ms": me,
                "gain_pct": round((mr - me) / mr * 100, 1) if mr and me is not None else None}

# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : ce fichier est tout le nexus des points d'évolution : validation du contrat, résolveur de compatibilité, hôtes d'exécution, disjoncteur, suspension.
#      Il ne contient aucune logique métier : celle-ci vit dans les références (points/EC_*) des modules.
# EC : néant. Il charge des EC mais n'en est pas une ; jamais évolutif (docs/CN_NEXUS.md §4 : mécanismes de l'évolution).
# LIEN : noyau/CN_manifeste.py (PointEvolution), noyau/CN_contexte.py (ctx.point), docs/CN_EVOLUTION.md §2 quater à sexies.
