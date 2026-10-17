# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'évaluateur : un candidat contre la référence, sur le corpus de rejeu
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #fdac92
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : dit si une variante d'un point d'évolution est équivalente à la référence, plus rapide, et si son gain tient hors de ce que le générateur a vu.
# MÉTHODE    : code déterministe (jamais un modèle) ; évaluation par paliers avec arrêt à la première divergence ; partition réservée ; contrôle de sa propre solidité par des variantes fausses.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=fdac92 ▼▼▼
"""L'évaluateur (docs/CN_EVOLUTION.md §2, docs/CN_NEXUS.md §4 : un juge ne s'évolue pas).

  - DÉTERMINISTE : aucune note donnée par un modèle ; une comparaison de données et des mesures de durée ;
  - la RÉFÉRENCE du dépôt est la spécification : la sortie attendue est recalculée par elle, jamais lue d'un enregistrement ;
  - PAR PALIERS (5 %, 25 %, 100 %) avec arrêt à la première divergence : un mauvais candidat meurt tôt, à coût minimal ;
  - la PARTITION RÉSERVÉE vient en dernier : le gain de latence est mesuré à part sur les cas que le générateur n'a jamais vus, et « tient » seulement s'il y subsiste ;
  - un candidat IMPUR (analyse de l'arbre syntaxique) n'est même pas chargé ;
  - il se TESTE lui-même : `pieges()` glisse des variantes volontairement fausses (mutations de la référence) ; si le corpus ne les attrape pas, le corpus est trop faible
    et l'évaluateur le DIT : une absence de preuve n'est pas une preuve.
"""
from __future__ import annotations

import ast
import copy
import math
import statistics
import sys
import time
import types

from . import CN_points as P


class Impur(ValueError):
    def __init__(self, fautes):
        super().__init__("; ".join(fautes[:3]))
        self.fautes = list(fautes)


def charger_texte(texte: str, fonction: str):
    """Compile un candidat Python depuis son TEXTE (jamais le disque, jamais le bytecode) après l'analyse de pureté."""
    ast.parse(texte)                                         # une syntaxe illisible lève SyntaxError : c'est « illisible », pas « impur »
    fautes = P.analyser_purete(texte)
    if fautes:
        raise Impur(fautes)
    mod = types.ModuleType("candidat")
    exec(compile(texte, "<candidat>", "exec"), mod.__dict__)
    return getattr(mod, fonction)


class Delai(Exception):
    """Un candidat qui ne rend pas la main : interrompu, jamais attendu."""


def appel_borne(f, entree, secondes: float = 2.0):
    """Appelle f(entree) avec un délai. Une boucle sans fin (une mutation de condition d'arrêt, un modèle étourdi) arrêterait l'évaluation pour toujours : le traçage lève Delai
    dès que le code du CANDIDAT (« <candidat> ») dépasse son temps. Une boucle dans une fonction native (une expression régulière catastrophique) ne peut pas être interrompue ainsi."""
    limite = time.perf_counter() + secondes

    def local(frame, event, arg):
        if time.perf_counter() > limite:
            raise Delai("délai de %.1f s dépassé" % secondes)
        return local

    def globale(frame, event, arg):
        return local if frame.f_code.co_filename == "<candidat>" else None
    ancien = sys.gettrace()
    sys.settrace(globale)
    try:
        return f(entree)
    finally:
        sys.settrace(ancien)


def _mediane(valeurs):
    return statistics.median(valeurs) if valeurs else None


def _gain(ref, cand):
    if not ref or cand is None:
        return None
    return round((ref - cand) / ref * 100, 1)


class Evaluateur:
    def __init__(self, points, rejeu, minimum: int = 200):
        """`minimum` : en dessous de ce nombre d'entrées distinctes, le corpus est dit TROP ÉTROIT : on ne promeut pas sur un jeu trop mince."""
        self.points, self.rejeu, self.minimum = points, rejeu, int(minimum)

    def evaluer(self, module: str, point: str, candidat: str, paliers=(0.05, 0.25, 1.0), repetitions: int = 3, minimum: int | None = None) -> dict:
        """`repetitions` : le nombre de PASSES à froid du chronométrage (voir _chronometrer)."""
        ref = self.points.reference(module, point)
        gid = ref["gid"]
        res = {"point": gid, "verdict": "", "corpus": {}, "palier_atteint": 0.0, "evalues": 0, "divergence": None, "erreur": "", "latence_ms": {}, "gain_pct": None,
               "gain_visible_pct": None, "gain_reserve_pct": None, "gain_tient": None, "refs_en_echec": 0, "bruit_pct": None}
        try:
            cand = charger_texte(candidat, ref["fonction"])
        except Impur as e:
            res.update(verdict="impure", erreur=str(e), fautes=e.fautes)
            return res
        except Exception as e:                                       # un candidat illisible ou sans la fonction n'est pas un candidat
            res.update(verdict="illisible", erreur="%s : %s" % (type(e).__name__, e))
            return res
        visibles, reserves = self.rejeu.corpus(gid, "visible"), self.rejeu.corpus(gid, "reserve")
        corpus = visibles + reserves                                  # ce que le générateur voit d'abord ; le réservé en dernier
        n = len(corpus)
        res["corpus"] = {"distincts": n, "visibles": len(visibles), "reserves": len(reserves)}
        t_ref = {"visible": [], "reserve": []}
        t_cand = {"visible": [], "reserve": []}
        t_ref2 = []                                          # la référence chronométrée une seconde fois : l'écart avec elle-même est le BRUIT de la machine
        cas_ok = []                                          # les cas où le candidat a répondu comme la référence : ce sont eux qu'on chronomètre
        sortie_contrat = ref["contrat"].get("sortie")
        delai_s = float(ref["contrat"].get("delai_ms") or 2000) / 1000.0
        fait = 0
        arret = False
        for frac in paliers:
            cible = n if frac >= 1 else max(1, math.ceil(frac * n))
            for cas in corpus[fait:cible]:
                part = "reserve" if cas["reserve"] else "visible"
                try:
                    attendue = P._copie(ref["appelable"](P._copie(cas["entree"])))
                except Exception:
                    res["refs_en_echec"] += 1                          # la spécification elle-même échoue sur ce cas : on ne le compte ni pour ni contre
                    fait += 1
                    continue
                try:
                    obtenue = P._copie(appel_borne(cand, P._copie(cas["entree"]), delai_s))
                except Exception as e:
                    res.update(verdict="erreur", erreur="%s : %s" % (type(e).__name__, e), divergence={"h": cas["h"], "partition": part})
                    arret = True
                    break
                ecarts = P.valider(sortie_contrat, obtenue)
                if ecarts or obtenue != attendue:
                    res.update(verdict="divergente", divergence={"h": cas["h"], "partition": part, "contrat": ecarts[:2]})
                    arret = True
                    break
                cas_ok.append(cas)
                res["evalues"] += 1
                fait += 1
            res["palier_atteint"] = round(fait / n, 3) if n else 0.0
            if arret:
                break
        if cas_ok and not arret:                              # le temps ne se mesure que d'un candidat équivalent : un faux plus rapide n'est pas un gain
            t_ref, t_cand, t_ref2 = self._chronometrer(ref, candidat, cas_ok, repetitions)
        rv, cv, rr, cr = _mediane(t_ref["visible"]), _mediane(t_cand["visible"]), _mediane(t_ref["reserve"]), _mediane(t_cand["reserve"])
        res["latence_ms"] = {"reference_visible": rv, "candidat_visible": cv, "reference_reserve": rr, "candidat_reserve": cr}
        res["gain_visible_pct"], res["gain_reserve_pct"] = _gain(rv, cv), _gain(rr, cr)
        toutes_ref, tous_cand = t_ref["visible"] + t_ref["reserve"], t_cand["visible"] + t_cand["reserve"]
        res["gain_pct"] = _gain(_mediane(toutes_ref), _mediane(tous_cand))
        bruit = _gain(_mediane(toutes_ref), _mediane(t_ref2))
        res["bruit_pct"] = abs(bruit) if bruit is not None else None      # un gain qui ne dépasse pas ce que la référence « gagne » sur elle-même n'est pas un gain
        if res["gain_visible_pct"] is not None and res["gain_reserve_pct"] is not None:
            # le gain « tient » s'il subsiste, aux trois quarts au moins, sur ce que le générateur n'a jamais vu
            res["gain_tient"] = True if res["gain_visible_pct"] <= 0 else res["gain_reserve_pct"] >= 0.75 * res["gain_visible_pct"]
        if not res["verdict"]:
            res["verdict"] = "corpus_trop_etroit" if n < (self.minimum if minimum is None else int(minimum)) else "equivalente"
        return res

    @staticmethod
    def _chronometrer(ref: dict, candidat: str, cas_ok: list, passes: int):
        """Mesure le temps en PASSES À FROID : à chaque passe, la référence (deux fois, pour le bruit) et le candidat sont rechargés à neuf, puis chaque entrée est jouée UNE fois.
        Pourquoi pas « trois essais de la même entrée, le meilleur gagne » : une variante qui mémorise ses résultats (lru_cache) serait chaude dès le deuxième essai, et son gain
        serait gonflé. Ici une entrée n'est jamais rejouée dans une même instance ; seul demeure l'effet d'un cache d'une entrée à la suivante, qui est celui du trafic réel.
        Le temps retenu pour chaque entrée est le plus bas des passes (le moins perturbé par le reste de la machine). L'ordre des trois appels tourne d'une passe à l'autre."""
        source_ref = ref["fichier"].read_text(encoding="utf-8")
        passes = max(1, int(passes))
        meilleur: dict = {}
        for p in range(passes):
            if ref["runtime"] == "python":
                ref_a, ref_b = charger_texte(source_ref, ref["fonction"]), charger_texte(source_ref, ref["fonction"])
            else:
                ref_a = ref_b = ref["appelable"]
            cand = charger_texte(candidat, ref["fonction"])
            appelants = [("ref", ref_a), ("cand", cand), ("ref2", ref_b)]
            for i, cas in enumerate(cas_ok):
                k = (p + i) % 3
                for nom, f in appelants[k:] + appelants[:k]:
                    e = P._copie(cas["entree"])
                    t0 = time.perf_counter_ns()
                    f(e)
                    d = (time.perf_counter_ns() - t0) / 1e6
                    cle = (cas["h"], nom)
                    if cle not in meilleur or d < meilleur[cle]:
                        meilleur[cle] = d
        t_ref = {"visible": [], "reserve": []}
        t_cand = {"visible": [], "reserve": []}
        t_ref2 = []
        for cas in cas_ok:
            part = "reserve" if cas["reserve"] else "visible"
            t_ref[part].append(meilleur[(cas["h"], "ref")])
            t_cand[part].append(meilleur[(cas["h"], "cand")])
            t_ref2.append(meilleur[(cas["h"], "ref2")])
        return t_ref, t_cand, t_ref2

    # ── l'évaluateur évalué ──────────────────────────────────────────────
    def pieges(self, module: str, point: str, maximum: int = 40, minimum: int | None = None) -> dict:
        """Glisse des variantes volontairement FAUSSES de la référence et regarde si le corpus les attrape. `score` = part détectée.
        Un survivant n'est pas forcément un défaut du corpus (une mutation peut être équivalente), mais un score bas dit que le corpus est trop faible pour promouvoir quoi que ce soit."""
        ref = self.points.reference(module, point)
        source = ref["fichier"].read_text(encoding="utf-8")
        detectes, survivants, valides = 0, [], 0
        for texte, description, ligne in mutants(source, maximum):
            r = self.evaluer(module, point, texte, paliers=(1.0,), repetitions=1, minimum=0)
            if r["verdict"] in ("impure", "illisible"):
                continue                                                # un mutant qui ne se charge pas n'éprouve rien
            valides += 1
            if r["verdict"] in ("divergente", "erreur"):
                detectes += 1
            else:
                survivants.append({"ligne": ligne, "mutation": description})
        return {"point": ref["gid"], "mutants": valides, "detectes": detectes, "survivants": survivants, "score": round(detectes / valides, 3) if valides else None}


# ── les mutations : des fautes plausibles, une à la fois ─────────────────────
class _Muteur(ast.NodeTransformer):
    ECHANGES_CMP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.In: ast.NotIn, ast.NotIn: ast.In,
                    ast.Is: ast.IsNot, ast.IsNot: ast.Is}
    ECHANGES_BIN = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Add, ast.Div: ast.Mult, ast.FloorDiv: ast.Mult, ast.Mod: ast.Mult}

    def __init__(self, cible: int):
        self.cible, self.i, self.description, self.ligne = cible, -1, "", 0

    def _est_la_cible(self, noeud, description: str) -> bool:
        self.i += 1
        if self.i == self.cible:
            self.description, self.ligne = description, getattr(noeud, "lineno", 0)
            return True
        return False

    def visit_Compare(self, n):
        self.generic_visit(n)
        op = type(n.ops[0])
        if op in self.ECHANGES_CMP and self._est_la_cible(n, "comparaison %s -> %s" % (op.__name__, self.ECHANGES_CMP[op].__name__)):
            n.ops[0] = self.ECHANGES_CMP[op]()
        return n

    def visit_BinOp(self, n):
        self.generic_visit(n)
        op = type(n.op)
        if op in self.ECHANGES_BIN and self._est_la_cible(n, "opération %s -> %s" % (op.__name__, self.ECHANGES_BIN[op].__name__)):
            n.op = self.ECHANGES_BIN[op]()
        return n

    def visit_BoolOp(self, n):
        self.generic_visit(n)
        if self._est_la_cible(n, "booléen %s -> %s" % (type(n.op).__name__, "Or" if isinstance(n.op, ast.And) else "And")):
            n.op = ast.Or() if isinstance(n.op, ast.And) else ast.And()
        return n

    def visit_UnaryOp(self, n):
        self.generic_visit(n)
        if isinstance(n.op, ast.Not) and self._est_la_cible(n, "négation retirée"):
            return n.operand
        return n

    def visit_If(self, n):
        self.generic_visit(n)
        if self._est_la_cible(n, "condition inversée"):
            n.test = ast.UnaryOp(op=ast.Not(), operand=n.test)
        return n

    def visit_Constant(self, n):
        if isinstance(n.value, bool):
            if self._est_la_cible(n, "constante booléenne inversée"):
                return ast.copy_location(ast.Constant(value=not n.value), n)
        elif isinstance(n.value, int):
            if self._est_la_cible(n, "constante %d -> %d" % (n.value, n.value + 1)):
                return ast.copy_location(ast.Constant(value=n.value + 1), n)
        return n


def mutants(source: str, maximum: int = 40) -> list:
    """(texte, description, ligne) de variantes de `source`, une mutation chacune, réparties régulièrement (déterministe)."""
    arbre = ast.parse(source)
    comptage = _Muteur(-1)
    comptage.visit(copy.deepcopy(arbre))
    total = comptage.i + 1
    if total <= 0:
        return []
    cibles = list(range(total)) if total <= maximum else sorted({int(k * total / maximum) for k in range(maximum)})
    sortie = []
    for c in cibles:
        m = _Muteur(c)
        neuf = m.visit(copy.deepcopy(arbre))
        ast.fix_missing_locations(neuf)
        try:
            sortie.append((ast.unparse(neuf), m.description, m.ligne))
        except Exception:
            continue
    return sortie
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Evaluateur (evaluer, pieges), charger_texte, mutants. C'est un JUGE : il ne s'évolue pas et ne dépend d'aucun modèle.
# EC : néant. Les candidats qu'il juge sont des EC ; lui n'en est pas une.
# LIEN : noyau/CN_rejeu.py (le corpus), noyau/CN_points.py (la référence et la pureté), docs/CN_EVOLUTION.md §2 et §5.
