"""Le catalogue des modules (docs/CN_MODULES.md) est généré depuis les manifestes : il doit dire la même chose qu'eux."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
sys.path.insert(0, str(RACINE))
import CN_catalogue_modules as cat  # noqa: E402


class Catalogue(unittest.TestCase):
    def test_le_catalogue_est_a_jour(self):
        t = cat.CIBLE.read_text(encoding="utf-8").replace("\r\n", "\n")
        zone = cat.lire_zone(t)
        self.assertEqual(zone if zone is not None else t, cat.corps(),
                         "docs/CN_MODULES.md n'est plus celui des manifestes : `python outils/CN_catalogue_modules.py`, puis `python outils/CN_entete.py --ecrire` et `python outils/CN_bornes.py --sceller`")

    def test_chaque_module_y_figure_une_fois(self):
        t = cat.CIBLE.read_text(encoding="utf-8")
        for m in cat.modules():
            self.assertEqual(t.count("| `%s` — " % m.id), 1, m.id)

    def test_aucune_famille_n_est_oubliee_dans_l_ordre_de_lecture(self):
        for m in cat.modules():
            self.assertIn(m.famille or "autres", cat.ORDRE, "la famille « %s » du module %s n'a pas sa place dans l'ordre du catalogue" % (m.famille, m.id))


if __name__ == "__main__":
    unittest.main()
