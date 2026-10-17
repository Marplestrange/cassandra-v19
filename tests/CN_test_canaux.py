"""Bancs des canaux : le miroir (éteint par défaut, réversible)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

BEA = "bea@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("canaux", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("canaux", installe=True, par="test")   # le module a un script d'installation
        for m in ("droits", "comptes", "canaux"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["canaux"]

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("canaux." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_le_miroir_est_eteint_par_defaut(self):
        self.assertEqual(self.s("miroir")["miroir"], False)

    def test_le_miroir_s_allume_et_se_defait(self):
        res = self.ex("canaux.miroir_ecrire", actif=True)
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("miroir")["miroir"], True)
        self.n.catalogue.get("canaux.miroir_ecrire").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("miroir")["miroir"], False)

    def test_l_etat_dit_le_client_non_branche(self):
        e = self.s("etat")
        self.assertEqual(e["client"], False)


if __name__ == "__main__":
    unittest.main()
