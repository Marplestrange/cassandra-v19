# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les points d'évolution : résolution, garde de contrat, disjoncteur
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #5b2cd3
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : appelle un point d'évolution (données en entrée, données en sortie), sert l'EC en service si elle est saine, sinon la référence du dépôt.
# MÉTHODE    : valide l'entrée et la sortie par le contrat, copie les données à chaque frontière, compte les fautes d'une EC et la suspend au troisième écart en dix minutes.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=5b2cd3 ▼▼▼
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
import hashlib
import json
import re
import threading
import types
import time
from collections import deque
from pathlib import Path

SEUIL_FAUTES = 3                   # fautes d'une EC avant suspension
FENETRE_S = 600                    # ... dans cette fenêtre (dix minutes)

STDLIB_PURE = {"__future__", "math", "re", "json", "itertools", "functools", "collections", "dataclasses", "typing", "enum", "fractions", "decimal", "string",
               "textwrap", "unicodedata", "operator", "copy", "heapq", "bisect", "statistics", "hashlib", "base64", "struct", "ec_api", "abc", "numbers"}
NOMS_INTERDITS = {"ctx", "self", "cls", "open", "print", "input", "exec", "eval", "__import__", "compile", "globals", "locals"}


class PointInconnu(KeyError):
    """Ce point n'est déclaré par aucun module actif."""


class ContratViole(ValueError):
    """L'ENTRÉE ne respecte pas le contrat : c'est l'appelant qui se trompe, pas l'EC."""


class PointDefaillant(RuntimeError):
    """La RÉFÉRENCE du dépôt échoue ou viole son propre contrat : un défaut du dépôt, jamais masqué."""


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
        for k, sous in (schema.get("properties") or {}).items():
            if k in valeur:
                fautes += valider(sous, valeur[k], "%s.%s" % (chemin, k))
    if isinstance(valeur, list) and schema.get("items"):
        for i, x in enumerate(valeur[:50]):
            fautes += valider(schema["items"], x, "%s[%d]" % (chemin, i))
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
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] not in STDLIB_PURE:
                    fautes.add("import interdit : " + a.name)
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] not in STDLIB_PURE:
                fautes.add("import interdit : %s" % n.module)
        elif isinstance(n, ast.Name) and n.id in NOMS_INTERDITS:
            fautes.add("nom interdit : " + n.id)
        elif isinstance(n, ast.arg) and n.arg in NOMS_INTERDITS:
            fautes.add("paramètre interdit : " + n.arg)
        elif isinstance(n, (ast.Global, ast.Nonlocal, ast.Await, ast.Yield)):
            fautes.add("global / nonlocal / await / yield")
    return sorted(fautes)


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
                exec(compile(texte, str(chemin), "exec"), mod.__dict__)
                self._cache[cle] = getattr(mod, fonction)
            return self._cache[cle]


HOTES = {"python": HotePython}


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
        self.refus = ""


class ServicePoints:
    def __init__(self, stock=None, enregistreur=None, alerte=None, horloge=time.monotonic, echantillon: int = 0):
        """`stock` : le dossier des EC (jamais dans modules/). `enregistreur(gid, entree, sortie, duree_ms, source)` : la matière du rejeu.
        `alerte(gid, texte)` : appelé à la suspension d'une EC. `echantillon` : un appel sur N compare l'EC à la référence (0 : jamais)."""
        self.stock = Path(stock) if stock else None
        self.enregistreur, self.alerte, self._horloge, self.echantillon = enregistreur, alerte, horloge, int(echantillon)
        self._points: dict = {}
        self._erreurs: dict = {}
        self._hotes: dict = {}
        self._verrou = threading.RLock()
        self._verifiees: dict = {}

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
                contrat = json.loads(fichier_contrat.read_text(encoding="utf-8")) if fichier_contrat.exists() else {}
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

    def _ec_en_service(self, d: _Declare):
        """Rend (fichier, hote, version) de l'EC à servir, ou None. Toute raison de ne pas la servir est gardée dans d.refus (visible par etat())."""
        d.refus = ""
        s = self._dossier_stock(d)
        if s is None or not (s / "ACTIVE").exists():
            return None
        if d.suspendue or (s / "SUSPENDUE.json").exists():
            d.refus = "suspendue"
            return None
        nom = (s / "ACTIVE").read_text(encoding="utf-8").strip()
        if not nom or Path(nom).name != nom:
            d.refus = "ACTIVE désigne un chemin qui sort du dossier de l'EC"
            return None
        f = s / nom
        if not f.is_file():
            d.refus = "le fichier d'EC désigné est introuvable"
            return None
        octets = f.read_bytes()
        emp = hashlib.sha256(octets).hexdigest()
        cle = (str(f), emp, d.p.contrat)                 # la vérification est liée au CONTENU, pas à une date : une EC réécrite est revérifiée
        if cle not in self._verifiees:
            self._verifiees[cle] = self._verifier_ec(d, f, octets)
        ok, raison, version, runtime = self._verifiees[cle]
        if not ok:
            d.refus = raison
            if raison.startswith("impure"):
                self._suspendre(d, raison, version)
            return None
        return f, version, runtime, emp

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
    def _executer(self, d: _Declare, fichier: Path, runtime: str, empreinte: str = ""):
        """L'appelable d'un fichier. Avec `empreinte` (celle du contenu VÉRIFIÉ), l'hôte refuse un fichier qui a changé entre la vérification et le chargement."""
        hote = self._hotes.get(runtime) or self._hotes.setdefault(runtime, HOTES[runtime]())
        if empreinte and hasattr(hote, "appelable_verifie"):
            return hote.appelable_verifie(fichier, d.p.fonction, empreinte)
        return hote.appelable(fichier, d.p.fonction)

    def appeler(self, module: str, point: str, entree):
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
        if ec:
            fichier, version, runtime, emp = ec
            try:
                brute = self._executer(d, fichier, runtime, emp)(_copie(entree))
                candidate = _copie(brute)
                ecarts = valider(d.contrat.get("sortie"), candidate)
                if ecarts:
                    raise ContratViole("sortie hors contrat : " + " ; ".join(ecarts[:3]))
                ms = (time.perf_counter() - t0) * 1000
                delai = d.contrat.get("delai_ms") or d.p.delai_ms
                if ms > delai:
                    self._faute(d, "délai dépassé : %d ms pour un plafond de %d ms" % (ms, delai), version)
                sortie, source = candidate, version
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
        d.appels += 1
        if source != "reference" and self.echantillon and d.appels % self.echantillon == 0:
            self._comparer(d, entree, sortie, source)
        ms = (time.perf_counter() - t0) * 1000
        if self.enregistreur:
            try:
                self.enregistreur(gid, entree, sortie, ms, source)
            except Exception:
                pass
        return sortie

    def _comparer(self, d: _Declare, entree, sortie, source: str):
        """La couche 5 : un échantillon d'appels est confronté à la référence. Une différence est une dérive de SENS que le schéma ne voit pas."""
        try:
            ref = _copie(self._executer(d, d.reference, d.p.runtime)(_copie(entree)))
        except Exception:
            return
        if ref != sortie:
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
                    s.mkdir(parents=True, exist_ok=True)
                    (s / "SUSPENDUE.json").write_text(json.dumps(d.suspendue, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
        if self.alerte:
            try:
                self.alerte(d.gid, "EC %s suspendue sur %s : %s. La référence du dépôt sert ; l'EC est conservée." % (version, d.gid, raison))
            except Exception:
                pass

    def reactiver(self, module: str, point: str) -> bool:
        """Lève la suspension d'une EC (la réparation, ou la décision de l'admin) : le compte des fautes repart de zéro."""
        d = self._points.get("%s.%s" % (module, point))
        if d is None:
            raise PointInconnu("%s.%s" % (module, point))
        with self._verrou:
            d.suspendue = None
            d.fautes.clear()
            s = self._dossier_stock(d)
            if s is not None and (s / "SUSPENDUE.json").exists():
                (s / "SUSPENDUE.json").unlink()
            self._verifiees.clear()
            self._hotes.clear()                              # un hôte garde le fichier chargé : une EC réécrite sous le même nom, dans la même fraction de seconde, ne doit pas servir l'ancienne
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
        return {"point": d.gid, "contrat": d.p.contrat, "runtime": d.p.runtime, "sert": ec[1] if ec else "reference", "ec_refusee": getattr(d, "refus", ""),
                "suspendue": suspendue, "fautes_recentes": len(d.fautes), "appels": d.appels}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : ce fichier est tout le nexus des points d'évolution : validation du contrat, résolveur de compatibilité, hôtes d'exécution, disjoncteur, suspension.
#      Il ne contient aucune logique métier : celle-ci vit dans les références (points/EC_*) des modules.
# EC : néant. Il charge des EC mais n'en est pas une ; jamais évolutif (docs/CN_NEXUS.md §4 : mécanismes de l'évolution).
# LIEN : noyau/CN_manifeste.py (PointEvolution), noyau/CN_contexte.py (ctx.point), docs/CN_EVOLUTION.md §2 quater à sexies.
