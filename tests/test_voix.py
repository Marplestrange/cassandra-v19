"""Bancs de la voix : le catalogue, le choix par compte (réversible)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import main as moteur                      # noqa: E402

BEA = "bea@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("voix", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "voix"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(BEA, True)
        self.ctx = self.n.executeur.contextes["voix"]

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("voix." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_le_catalogue_et_la_dispo(self):
        self.assertGreaterEqual(len(self.s("catalogue")["catalogue"]), 4)
        d = self.s("dispo")
        self.assertIn("ecoute", d)

    def test_choisir_une_voix_et_revenir(self):
        res = self.ex("voix.choisir", voix_nom="fr_FR-tom-medium", voix_locuteur="", voix_auto=False)
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("reglages")["reglages"]["voix_nom"], "fr_FR-tom-medium")
        self.n.catalogue.get("voix.choisir").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("reglages")["reglages"]["voix_nom"], "")

    def test_une_voix_inconnue_est_refusee(self):
        r = self.ex("voix.choisir", voix_nom="fr_FR-nimporte-quoi")
        self.assertIn(r["statut"], ("echec", "refuse"), r)


if __name__ == "__main__":
    unittest.main()
