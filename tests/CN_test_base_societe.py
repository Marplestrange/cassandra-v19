"""Bancs de la base par société : un module « stockage_par_societe » garde ses données société par société, sans que son code change ; ses moteurs tournent pour chacune."""
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur                      # noqa: E402

BEA, DAN = "bea@x.fr", "dan@x.fr"
MDP = "Abcdefgh1!"
FORM = "lumen-formation"

MANIFESTE = textwrap.dedent('''
    [module]
    id = "carnet"
    nom = "Carnet d'essai"
    version = "0.1.0"
    noyau_min = "0.1.0"
    description = "Un module dont les données sont propres à chaque société."
    importance = "optionnel"
    sans = "rien"

    [permissions]
    stockage = true
    stockage_par_societe = true

    [[droits]]
    id = "utiliser"
    libelle = "Utiliser"
    defaut = true

    [[moteurs]]
    id = "compter"
    libelle = "Écrit une ligne de bilan dans la base de la société courante"
    mode = "periodique"
    toutes_les_s = 3600
    duree_max_s = 20

    [[capacites]]
    id = "noter"
    libelle = "Note un texte"
    risque = "lecture"
    droit = "utiliser"

    [[capacites]]
    id = "lire"
    libelle = "Lit les notes"
    risque = "lecture"
    droit = "utiliser"
''')
CODE = textwrap.dedent('''
    def brancher(ctx):
        db = ctx.stockage                                  # pris une fois, comme le fait un vrai module

        def noter(c, texte=""):
            db.ecrire("INSERT INTO notes(texte) VALUES(?)", (texte,))
            return {"ok": True}

        def lire(c):
            return {"notes": [r["texte"] for r in db.lire("SELECT texte FROM notes ORDER BY id")]}

        def compter(ctx_):
            db.ecrire("INSERT INTO notes(texte) VALUES(?)", ("bilan",))

        ctx.implementer("noter", noter)
        ctx.implementer("lire", lire)
        ctx.moteur("compter", compter)
''')
MIGRATION = "CREATE TABLE notes(id INTEGER PRIMARY KEY AUTOINCREMENT, texte TEXT NOT NULL);\n"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("droits", "comptes", "societes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        (mods / "carnet" / "migrations").mkdir(parents=True)
        (mods / "carnet" / "CN_manifeste.toml").write_text(MANIFESTE, encoding="utf-8")
        (mods / "carnet" / "CN_module.py").write_text(CODE, encoding="utf-8")
        (mods / "carnet" / "migrations" / "CN_001_init.sql").write_text(MIGRATION, encoding="utf-8")
        self.base = base
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "societes", "carnet"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.executeur.contextes["societes"].reglage = lambda nom, compte=None: True if nom == "multi" else None
        for c in (BEA, DAN):
            r = self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP}, compte="")
            self.assertEqual(r["statut"], "faite", r)
        r = self.ex("societes.creer", BEA, nom="Lumen Formation", identifiant=FORM)
        self.assertEqual(r["statut"], "faite", r)

    def ex(self, cap, compte=BEA, dans="", **args):
        return self.n.executeur.executer(cap, "humain", args, compte=compte, societe=dans)

    def ok(self, cap, compte=BEA, dans="", **args):
        r = self.ex(cap, compte, dans, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_chaque_societe_a_ses_donnees_sans_que_le_module_change(self):
        self.ok("societes.module_regler", societe=FORM, module="carnet", ouvert=True)
        self.ok("carnet.noter", texte="principale")
        self.ok("carnet.noter", dans=FORM, texte="formation")
        self.assertEqual(self.ok("carnet.lire")["notes"], ["principale"])
        self.assertEqual(self.ok("carnet.lire", dans=FORM)["notes"], ["formation"])
        mods = self.base / "d" / "modules"
        self.assertTrue((mods / "carnet.db").is_file())                                   # la principale garde le fichier d'avant
        self.assertTrue((mods / ("carnet@%s.db" % FORM)).is_file())

    def test_un_acte_hors_societe_va_a_la_principale(self):
        self.ok("carnet.noter", texte="a")
        self.assertEqual(self.ok("carnet.lire", dans="1")["notes"], ["a"])

    def test_les_moteurs_tournent_pour_chaque_societe_ou_le_module_est_ouvert(self):
        self.ok("societes.module_regler", societe=FORM, module="carnet", ouvert=True)
        self.ok("carnet.noter", dans=FORM, texte="formation")
        r = self.n.lancer("carnet.compter")
        self.assertEqual(r.get("statut"), "fait", r)
        self.assertEqual(self.ok("carnet.lire")["notes"], ["bilan"])
        self.assertEqual(self.ok("carnet.lire", dans=FORM)["notes"], ["formation", "bilan"])

    def test_une_societe_ou_le_module_est_ferme_n_a_ni_donnees_ni_moteur(self):
        r = self.n.lancer("carnet.compter")
        self.assertEqual(r.get("statut"), "fait", r)
        self.assertFalse((self.base / "d" / "modules" / ("carnet@%s.db" % FORM)).exists())
        self.ok("carnet.lire")


if __name__ == "__main__":
    unittest.main()
