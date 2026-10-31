# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Garde-fou
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #16ca4d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Garde-fou : la valeur d'un secret de module ne sort jamais d'une capacité qu'un agent peut appeler.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=16ca4d ▼▼▼
"""Garde-fou : la valeur d'un secret de module ne sort jamais d'une capacité qu'un agent peut appeler.

Un agent (cassandra, itare, agent) est un modèle : ce que rend un outil entre dans son contexte, chez un fournisseur en ligne, et dans la conversation stockée.
Deux contrôles :
  1. STATIQUE : pour chaque capacité ouverte aux agents, on suit dans son code la valeur de `ctx.reglage(<secret du module>)`, de `ctx.dechiffrer(...)` et de
     toute fonction du module qui en rend une ; si elle atteint un `return` ou un événement (donc le journal), le banc échoue. `bool(...)`, `len(...)` et les
     comparaisons ne portent plus la valeur : « un jeton est posé » est permis, le jeton lui-même ne l'est pas.
  2. DYNAMIQUE : on pose des valeurs-témoins dans tous les secrets, on appelle chaque capacité de lecture ouverte aux agents des modules qui ont des secrets,
     et aucune réponse ne doit contenir un témoin.
Le banc s'essaie lui-même sur un module qui fuit, pour prouver qu'il échoue quand il le doit.
"""
import ast
import json
import shutil
import socket
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur                      # noqa: E402

AGENTS = {"cassandra", "itare", "agent"}
QUI_PAR_DEFAUT = {"cassandra", "itare", "humain", "agent"}
# Ces appels ne rendent plus la valeur : une taille, un booléen, un résultat de comparaison.
NEUTRALISE = {"bool", "len", "isinstance", "callable"}
# Ces appels transforment la valeur sans l'effacer.
TRANSPARENT = {"str", "bytes", "repr", "format", "bytearray", "list", "tuple", "dict", "sorted", "reversed", "min", "max", "sum"}
METHODES_TRANSPARENTES = {"strip", "lstrip", "rstrip", "lower", "upper", "encode", "decode", "format", "join", "replace", "split", "removeprefix", "removesuffix", "get"}


def secrets_declares(manifeste):
    return {r["id"] for r in manifeste.get("reglages", []) if r.get("type") == "secret"}


class Suivi(ast.NodeVisitor):
    """Suit, dans UNE fonction, les noms qui portent un secret, et note les `return` et les événements qui en portent un."""

    def __init__(self, secrets, sources):
        self.secrets, self.sources = secrets, sources          # sources : noms de fonctions du module qui rendent un secret
        self.portes = set()
        self.fuites = []

    def porte(self, n):
        if n is None:
            return False
        if isinstance(n, ast.Name):
            return n.id in self.portes
        if isinstance(n, ast.Compare):
            return False
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            return False
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "ctx":
                if f.attr == "dechiffrer":
                    return True
                if f.attr == "reglage":
                    a0 = n.args[0] if n.args else None
                    return isinstance(a0, ast.Constant) and a0.value in self.secrets
            if isinstance(f, ast.Name):
                if f.id in NEUTRALISE:
                    return False
                if f.id in self.sources:
                    return True
                if f.id in TRANSPARENT:
                    return any(self.porte(a) for a in n.args)
                return False
            if isinstance(f, ast.Attribute) and f.attr in METHODES_TRANSPARENTES:
                return self.porte(f.value) or any(self.porte(a) for a in n.args)
            return False
        return any(self.porte(c) for c in ast.iter_child_nodes(n) if isinstance(c, ast.expr))

    def visit_Assign(self, n):
        if self.porte(n.value):
            for t in n.targets:
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        self.portes.add(x.id)
        self.generic_visit(n)

    def visit_AnnAssign(self, n):
        if n.value is not None and self.porte(n.value) and isinstance(n.target, ast.Name):
            self.portes.add(n.target.id)
        self.generic_visit(n)

    def visit_NamedExpr(self, n):
        if self.porte(n.value):
            self.portes.add(n.target.id)
        self.generic_visit(n)

    def visit_Return(self, n):
        if self.porte(n.value):
            self.fuites.append(("return", n.lineno))
        self.generic_visit(n)

    def visit_Call(self, n):
        f = n.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "ctx" and f.attr == "emettre":
            if any(self.porte(a) for a in n.args) or any(self.porte(k.value) for k in n.keywords):
                self.fuites.append(("evenement", n.lineno))
        self.generic_visit(n)


def fonctions(arbre):
    return {n.name: n for n in ast.walk(arbre) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def analyser(source: str, manifeste: dict):
    """{capacité: [fuites]} pour les capacités ouvertes aux agents d'un module."""
    secrets = secrets_declares(manifeste)
    arbre = ast.parse(source)
    fns = fonctions(arbre)
    # Les fonctions du module qui rendent un secret, de proche en proche.
    sources = set()
    for _ in range(len(fns) + 1):
        neuf = set(sources)
        for nom, fn in fns.items():
            s = Suivi(secrets, sources)
            for instr in fn.body:
                s.visit(instr)
            if any(k == "return" for k, _ in s.fuites):
                neuf.add(nom)
        if neuf == sources:
            break
        sources = neuf
    ouvertes = {c["id"] for c in manifeste.get("capacites", []) if AGENTS & set(c.get("qui", QUI_PAR_DEFAUT))}
    liens = {}
    for n in ast.walk(arbre):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "implementer" and len(n.args) >= 2 \
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[1], ast.Name):
            liens[n.args[0].value] = n.args[1].id
    fuites = {}
    for cap, nom in liens.items():
        if cap not in ouvertes or nom not in fns:
            continue
        s = Suivi(secrets, sources)
        for instr in fns[nom].body:
            s.visit(instr)
        if s.fuites:
            fuites[cap] = s.fuites
    return fuites


def modules_a_secrets():
    for toml in sorted((RACINE / "modules").glob("*/CN_manifeste.toml")):
        man = tomllib.loads(toml.read_text(encoding="utf-8"))
        code = toml.parent / "CN_module.py"
        if secrets_declares(man) and code.exists():
            yield toml.parent.name, man, code


FUYANT = '''
def brancher(ctx):
    def jeton_de(compte):
        return str(ctx.reglage("jeton", compte) or "").strip()

    def etat(ctx):
        return {"pose": bool(ctx.reglage("jeton"))}

    def direct(ctx):
        return {"jeton": ctx.reglage("jeton")}

    def par_aide(ctx):
        return {"x": jeton_de("a")}

    def par_variable(ctx):
        t = ctx.reglage("jeton")
        corps = {"a": [t.strip()]}
        return corps

    def par_evenement(ctx):
        ctx.emettre("x.y", donnees={"t": ctx.reglage("jeton")})
        return {}

    def dechiffre(ctx):
        return ctx.dechiffrer("c", "e")

    ctx.implementer("etat", etat)
    ctx.implementer("direct", direct)
    ctx.implementer("par_aide", par_aide)
    ctx.implementer("par_variable", par_variable)
    ctx.implementer("par_evenement", par_evenement)
    ctx.implementer("dechiffre", dechiffre)
'''
MANIFESTE_FUYANT = {"reglages": [{"id": "jeton", "type": "secret"}],
                    "capacites": [{"id": c} for c in ("etat", "direct", "par_aide", "par_variable", "par_evenement", "dechiffre")]}


class Analyseur(unittest.TestCase):
    def test_le_banc_voit_une_fuite_directe_par_aide_par_variable_par_evenement_et_par_dechiffrement(self):
        f = analyser(FUYANT, MANIFESTE_FUYANT)
        self.assertEqual(set(f), {"direct", "par_aide", "par_variable", "par_evenement", "dechiffre"})
        self.assertNotIn("etat", f, "« un jeton est posé » (un booléen) n'est pas une fuite")

    def test_une_capacite_fermee_aux_agents_n_est_pas_jugee(self):
        man = dict(MANIFESTE_FUYANT, capacites=[{"id": c["id"], "qui": ["humain", "compte"]} for c in MANIFESTE_FUYANT["capacites"]])
        self.assertEqual(analyser(FUYANT, man), {})


class AucuneCapaciteNeRendUnSecret(unittest.TestCase):
    def test_statique(self):
        vus, fuites = 0, {}
        for nom, man, code in modules_a_secrets():
            vus += 1
            for cap, f in analyser(code.read_text(encoding="utf-8"), man).items():
                fuites["%s.%s" % (nom, cap)] = f
        self.assertGreaterEqual(vus, 6, "les modules à secrets ont bien été trouvés")
        self.assertEqual(fuites, {}, "une capacité ouverte aux agents rend ou journalise la valeur d'un secret : %s" % fuites)


class Dynamique(unittest.TestCase):
    TEMOIN = "temoin-inventé-pour-le-banc-"

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        base = Path(cls.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules", mods, ignore=shutil.ignore_patterns("__pycache__"))
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        cls.modules = [nom for nom, _, _ in modules_a_secrets()]
        for nom in cls.modules + ["reglages"]:          # seuls ces modules-là : en activer 45 d'un coup en défait certains
            cls.n.activer(nom)
        cls.n.droits.regler_admin("chef@x.fr", True)
        cls.temoins = {}
        for cle, (mod, d) in sorted(cls.n.reglages.connus.items()):
            if d.type != "secret":
                continue
            for compte in ("", "chef@x.fr") if d.portee == "compte" else ("",):
                t = cls.TEMOIN + cle.replace(".", "-") + ("-" + compte if compte else "")
                cls.n.reglages.poser(cle, t, compte, "banc")
                cls.temoins[t] = cle

    def test_aucune_reponse_d_un_outil_d_agent_ne_porte_un_temoin(self):
        self.assertGreaterEqual(len({c.split(".")[0] for c in self.temoins.values()}), 6, "les secrets des modules à secrets ont bien été posés")
        sorties, fuites = 0, []

        def pas_de_reseau(*a, **k):
            raise OSError("réseau coupé pour le banc")

        with mock.patch.object(socket, "create_connection", pas_de_reseau), mock.patch.object(socket.socket, "connect", pas_de_reseau):
            for acteur in sorted(AGENTS):
                for o in self.n._outils("chef@x.fr", acteur):
                    cle = o["cle"]
                    if cle.split(".")[0] not in {c.split(".")[0] for c in self.temoins.values()} or o["risque"] != "lecture":
                        continue
                    e = self.n.catalogue.get(cle)
                    if e.capacite.ecrit or e.capacite.sortant or e.capacite.externe:
                        continue
                    r = self.n.executeur.executer(cle, acteur, {}, compte="chef@x.fr")
                    sorties += 1
                    texte = json.dumps(r, default=str, ensure_ascii=False)
                    fuites += ["%s (%s)" % (cle, acteur) for t in self.temoins if t in texte]
        self.assertGreater(sorties, 0, "aucune capacité de lecture d'agent n'a été essayée : le banc ne prouve rien")
        self.assertEqual(fuites, [])

    def test_aucun_outil_d_agent_ne_lit_le_journal_ni_l_age_des_secrets(self):
        for acteur in sorted(AGENTS):
            noms = {o["cle"] for o in self.n._outils("chef@x.fr", acteur)}
            self.assertFalse(noms & {"reglages.secrets_lectures", "reglages.secrets_ages", "reglages.pieges", "reglages.regler_secret"}, acteur)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : secrets_declares, Suivi, fonctions, analyser, modules_a_secrets, Analyseur, AucuneCapaciteNeRendUnSecret, Dynamique
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
