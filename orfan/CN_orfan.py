# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Orfan v1 : le moteur de recherche d'optimisations de Cassandra
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : orfan
# ZONE       : CN
# VERSION CN : 0.1.0  #800d2a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : propose des variantes d'une fonction pure : d'abord des optimisations déterministes gratuites, puis un modèle de langage guidé par le profil de l'appel.
# MÉTHODE    : il ne connaît pas le noyau : il reçoit un contexte (source, entrées, contrat, tombes) et rend du texte ; il profile par comptage des lignes exécutées.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=800d2a ▼▼▼
"""Orfan v1 (docs/CN_EVOLUTION.md, « Orfan est un projet à part entière » : v1 = ce que savait faire le moteur V18, amélioré).

Contrat d'adaptateur, le seul lien avec Cassandra :   moteur.proposer(contexte) -> liste de textes (ou de {"texte", "hypothese"})

  contexte = {point, source_reference, fonction, contrat, entrees (la partition VISIBLE seulement), tombes (variantes déjà échouées), budget, seuils}

Ce qui améliore le moteur de la V18 :
  - le PROFIL : on compte les lignes réellement exécutées sur de vraies entrées ; le modèle reçoit « la ligne 12 fait 61 % du travail », pas tout le fichier ;
  - des optimisations DÉTERMINISTES d'abord (zéro jeton) : on ne dépense un modèle que sur ce qu'elles n'ont pas résolu ;
  - les TOMBES sont redonnées au modèle (ne pas reproposer ce qui a échoué) ;
  - STRATÈGE puis EXÉCUTANT : un modèle fort propose la stratégie, un modèle économe l'écrit (si deux appelants sont fournis).
Orfan ne juge JAMAIS : il propose. L'évaluation, l'écriture et la mise en service sont du noyau (noyau/CN_evolution.py).
"""
from __future__ import annotations

import ast
import collections
import copy
import json
import re
import sys
import time


# ── le profil : où va le travail ? ───────────────────────────────────────────
def profil(source: str, fonction: str, entrees: list, maximum: int = 20, top: int = 5) -> list:
    """Les lignes les plus exécutées par `fonction` sur de vraies entrées (comptage de lignes : déterministe, sans horloge)."""
    ns: dict = {}
    exec(compile(source, "<orfan>", "exec"), ns)
    f = ns[fonction]
    compte: collections.Counter = collections.Counter()

    def trace(frame, event, arg):
        if frame.f_code.co_filename != "<orfan>":
            return None

        def local(fr, ev, a):
            if ev == "line":
                compte[fr.f_lineno] += 1
            return local
        return local if event == "call" else None

    ancien = sys.gettrace()
    sys.settrace(trace)
    try:
        for e in entrees[:maximum]:
            try:
                f(json.loads(json.dumps(e)))
            except Exception:
                continue
    finally:
        sys.settrace(ancien)
    total = sum(compte.values())
    lignes = source.splitlines()
    return [{"ligne": n, "part_pct": round(100 * c / total, 1), "fois": c, "texte": lignes[n - 1].strip()} for n, c in compte.most_common(top)] if total else []


# ── les optimisations déterministes : zéro jeton ─────────────────────────────
class _Regle(ast.NodeTransformer):
    nom = ""
    hypothese = ""

    def __init__(self):
        self.changements = 0


class _CompDansAgregat(_Regle):
    """any([...]), all([...]), sum([...]), min([...]), max([...]), sorted n'est pas concerné : une liste intermédiaire pour rien, et any/all ne s'arrêtent plus au premier."""
    nom = "liste intermédiaire inutile"
    hypothese = "une compréhension de liste passée à any/all/sum/min/max devient une expression génératrice : pas de liste intermédiaire, et any/all s'arrêtent au premier résultat."

    def visit_Call(self, n):
        self.generic_visit(n)
        if isinstance(n.func, ast.Name) and n.func.id in ("any", "all", "sum", "min", "max") and len(n.args) == 1 and isinstance(n.args[0], ast.ListComp):
            lc = n.args[0]
            n.args[0] = ast.copy_location(ast.GeneratorExp(elt=lc.elt, generators=lc.generators), lc)
            self.changements += 1
        return n


class _TriPourExtremum(_Regle):
    nom = "tri pour un extremum"
    hypothese = "sorted(x)[0] devient min(x) et sorted(x)[-1] max(x) : un parcours au lieu d'un tri complet."

    def visit_Subscript(self, n):
        self.generic_visit(n)
        v = n.value
        if (isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == "sorted" and len(v.args) == 1 and not v.keywords
                and isinstance(n.slice, ast.Constant) and n.slice.value in (0, -1)):
            self.changements += 1
            return ast.copy_location(ast.Call(func=ast.Name(id="min" if n.slice.value == 0 else "max", ctx=ast.Load()), args=v.args, keywords=[]), n)
        return n


class _LongueurZero(_Regle):
    nom = "test de vide par la longueur"
    hypothese = "len(x) == 0 devient not x ; len(x) > 0 devient bool(x) : pas d'appel de fonction."

    def visit_Compare(self, n):
        self.generic_visit(n)
        if (len(n.ops) == 1 and isinstance(n.left, ast.Call) and isinstance(n.left.func, ast.Name) and n.left.func.id == "len" and len(n.left.args) == 1
                and isinstance(n.comparators[0], ast.Constant) and n.comparators[0].value == 0):
            if isinstance(n.ops[0], ast.Eq):
                self.changements += 1
                return ast.copy_location(ast.UnaryOp(op=ast.Not(), operand=n.left.args[0]), n)
            if isinstance(n.ops[0], ast.Gt):
                self.changements += 1
                return ast.copy_location(ast.Call(func=ast.Name(id="bool", ctx=ast.Load()), args=[n.left.args[0]], keywords=[]), n)
        return n


class _ListeDeGenerateur(_Regle):
    nom = "list(générateur)"
    hypothese = "list(e for ...) devient une compréhension de liste : plus rapide, même résultat."

    def visit_Call(self, n):
        self.generic_visit(n)
        if isinstance(n.func, ast.Name) and n.func.id == "list" and len(n.args) == 1 and isinstance(n.args[0], ast.GeneratorExp) and not n.keywords:
            g = n.args[0]
            self.changements += 1
            return ast.copy_location(ast.ListComp(elt=g.elt, generators=g.generators), n)
        return n


class _ConstructeursVides(_Regle):
    nom = "constructeurs vides"
    hypothese = "dict() devient {} et list() devient [] : un littéral au lieu d'un appel."

    def visit_Call(self, n):
        self.generic_visit(n)
        if isinstance(n.func, ast.Name) and not n.args and not n.keywords and n.func.id in ("dict", "list"):
            self.changements += 1
            return ast.copy_location(ast.Dict(keys=[], values=[]) if n.func.id == "dict" else ast.List(elts=[], ctx=ast.Load()), n)
        return n


REGLES = (_CompDansAgregat, _TriPourExtremum, _LongueurZero, _ListeDeGenerateur, _ConstructeursVides)


def optimisations(source: str) -> list:
    """Une variante par règle qui s'applique, avec son hypothèse. Une règle à la fois : on sait laquelle a gagné, ou laquelle a cassé."""
    arbre = ast.parse(source)
    sortie = []
    for R in REGLES:
        r = R()
        neuf = r.visit(copy.deepcopy(arbre))
        if r.changements:
            ast.fix_missing_locations(neuf)
            sortie.append({"texte": ast.unparse(neuf), "hypothese": "%s : %s" % (R.nom, R.hypothese), "origine": "regle"})
    return sortie


class MoteurDeterministe:
    """Zéro jeton : les optimisations connues. Souvent sans effet mesurable ; c'est l'évaluateur du noyau qui le dit."""
    nom = "orfan-deterministe"

    def proposer(self, contexte: dict) -> list:
        return optimisations(contexte["source_reference"])


# ── le modèle : guidé par le profil ──────────────────────────────────────────
SEPARATEUR_CACHE = "<!--orfan:variable-->"     # entre la partie qui ne change pas d'un appel à l'autre (cachable) et celle qui change ; le module Évolution le retire toujours


def construire_prompt(contexte: dict, chauds: list, strategie: str = "") -> str:
    """Ce qu'on dit au modèle : la fonction, où va le temps, ce qu'il ne peut pas changer, ce qui a déjà échoué. Court : tout jeton relu se repaie.
    L'ordre sert le cache du fournisseur : ce qui est stable d'abord (fonction, profil, contrat, règles), ce qui change (tombes, stratégie) après le séparateur."""
    lignes = ["Tu optimises une fonction Python PURE pour qu'elle s'exécute plus vite, SANS changer son résultat.", "",
              "Fonction à améliorer (nom : %s) :" % contexte["fonction"], "```python", contexte["source_reference"].rstrip(), "```", ""]
    if chauds:
        lignes += ["Profil mesuré sur des entrées réelles (lignes les plus exécutées) :"] + ["- ligne %d (%s %% du travail) : %s" % (c["ligne"], c["part_pct"], c["texte"]) for c in chauds] + [""]
    sortie = (contexte.get("contrat") or {}).get("sortie")
    if sortie:
        lignes += ["Contrat de sortie (JSON Schema, à respecter exactement) : " + json.dumps(sortie, ensure_ascii=False), ""]
    lignes += ["Règles strictes :", "- même nom de fonction, même signature, mêmes valeurs rendues pour toute entrée ;",
               "- bibliothèque standard pure seulement (math, re, json, itertools, functools, collections…) : ni fichier, ni réseau, ni heure, ni hasard, ni état global ;",
               "- rends UNIQUEMENT le code complet de la fonction (et de ses fonctions d'aide) dans un bloc ```python, précédé d'une phrase qui dit ton hypothèse."]
    debut_variable = len(lignes)
    if contexte.get("tombes"):
        lignes += ["", "%d variante(s) ont DÉJÀ échoué sur ce point : ne propose pas une transformation triviale déjà tentée." % len(contexte["tombes"])]
    if strategie:
        lignes += ["", "Stratégie à implémenter (décidée avant toi) :", strategie.strip()]
    if len(lignes) > debut_variable:
        lignes.insert(debut_variable, SEPARATEUR_CACHE)
    return "\n".join(lignes)


def extraire_blocs(reponse: str) -> list:
    """Les blocs ```python d'une réponse, chacun avec la phrase qui le précède (l'hypothèse). Une réponse sans bloc n'est pas une proposition."""
    sortie, reste = [], str(reponse or "")
    for m in re.finditer(r"```(?:python)?\s*\n(.*?)```", reste, re.S):
        avant = reste[:m.start()].strip().split("\n")[-1][:300] if reste[:m.start()].strip() else ""
        sortie.append({"texte": m.group(1).strip() + "\n", "hypothese": avant, "origine": "modele"})
    return sortie


class MoteurModele:
    """Un modèle de langage, branché par une fonction `appeler_modele(prompt) -> texte` que Cassandra fournit (depuis son registre de modèles).
    Avec `appeler_strategie` en plus : un modèle FORT décide de la stratégie, un modèle ÉCONOME l'écrit."""
    nom = "orfan-modele"

    def __init__(self, appeler_modele, appeler_strategie=None, profiler: bool = True):
        self.appeler_modele, self.appeler_strategie, self.profiler = appeler_modele, appeler_strategie, profiler
        self.dernier_prompt = ""

    def proposer(self, contexte: dict) -> list:
        chauds = []
        if self.profiler:
            try:
                chauds = profil(contexte["source_reference"], contexte["fonction"], contexte.get("entrees") or [])
            except Exception:
                chauds = []                                      # un profil qui échoue ne bloque pas : le modèle travaille sans
        strategie = ""
        if self.appeler_strategie:
            strategie = str(self.appeler_strategie(construire_prompt(contexte, chauds) + "\n\nNe rends PAS de code : décris en quelques lignes la stratégie la plus prometteuse.") or "")
        self.dernier_prompt = construire_prompt(contexte, chauds, strategie)
        sortie = []
        for _ in range(max(1, min(int(contexte.get("budget", 1)), 3))):
            sortie += extraire_blocs(self.appeler_modele(self.dernier_prompt))
        return sortie


class MoteurComposite:
    """Plusieurs moteurs dans l'ordre : les gratuits d'abord. Les doublons (même arbre syntaxique) sont écartés avant d'être évalués."""
    nom = "orfan"

    def __init__(self, *moteurs):
        self.moteurs = moteurs

    def proposer(self, contexte: dict) -> list:
        vus, sortie = set(), []
        for m in self.moteurs:
            for c in m.proposer(contexte):
                texte = c if isinstance(c, str) else c.get("texte", "")
                try:
                    h = ast.dump(ast.parse(texte))
                except SyntaxError:
                    h = texte
                if h not in vus:
                    vus.add(h)
                    sortie.append(c)
        return sortie


# ── la mesure locale : réservée aux moteurs qui tournent DANS LA CAGE ────────
def charger_local(texte: str, fonction: str):
    """Charge un candidat dans le processus courant. À N'APPELER QUE DANS le processus d'un moteur (CN_moteur_hote : sans clé, sans réseau, sans fichier, mémoire plafonnée,
    tué au délai) : le texte vient d'un modèle que personne n'a relu. Le serveur, lui, ne l'exécute jamais (le juge du noyau le fait dans un travailleur)."""
    ns: dict = {}
    exec(compile(texte, "<orfan-candidat>", "exec"), ns)
    return ns[fonction]


def _canon(valeur) -> str:
    return json.dumps(valeur, ensure_ascii=False, separators=(",", ":"))


def comparer_local(source: str, texte: str, fonction: str, entrees: list, passes: int = 2, maximum: int = 24):
    """(équivalent, rapport) sur les entrées VISIBLES : le candidat répond-il comme la référence (même texte JSON), et combien de fois plus vite (référence / candidat, passes à froid) ?
    Un pré-filtre du moteur pour ne pas rendre au juge ce qui est faux ; le juge du noyau décide, ensuite, sur tout le corpus. Un candidat qui lève est faux."""
    sujet = list(entrees)[:maximum]
    if not sujet:
        return False, 0.0
    try:
        ref, cand = charger_local(source, fonction), charger_local(texte, fonction)
        for e in sujet:
            if _canon(ref(copy.deepcopy(e))) != _canon(cand(copy.deepcopy(e))):
                return False, 0.0
    except Exception:
        return False, 0.0

    def mesure(f):
        meilleur = None
        for _ in range(max(1, passes)):
            t = 0
            for e in sujet:
                x = copy.deepcopy(e)
                d0 = time.perf_counter_ns()
                f(x)
                t += time.perf_counter_ns() - d0
            meilleur = t if meilleur is None else min(meilleur, t)
        return meilleur

    try:
        tr, tc = mesure(ref), mesure(cand)
    except Exception:
        return False, 0.0
    return True, (tr / tc) if tc else 0.0


def point_chaud(source: str, fonction: str, entrees: list, seuil_pct: float = 40.0, fois_min: int = 50):
    """La ligne la plus exécutée si elle porte au moins `seuil_pct` % du travail ET a tourné au moins `fois_min` fois, sinon None : un point chaud justifie de dépenser un modèle ;
    un profil étalé, ou une fonction d'une ligne qui ne tourne presque pas, n'en est pas un (sa seule ligne porterait « 100 % » de presque rien)."""
    try:
        p = profil(source, fonction, entrees)
    except Exception:
        return None
    return p[0] if p and p[0]["part_pct"] >= seuil_pct and p[0].get("fois", 0) >= fois_min else None
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du code du projet Orfan : profil, optimisations déterministes, moteur à modèle, composition. Il ne connaît pas le noyau.
# EC : néant. Orfan v1 n'évolue pas lui-même (le méta-niveau est de la R&D, docs/CN_EVOLUTION.md).
# LIEN : noyau/CN_evolution.py (qui appelle `proposer` et juge), docs/CN_EVOLUTION.md (le contrat d'adaptateur et la R&D d'Orfan).
