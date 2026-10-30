# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le catalogue des modules (docs/CN_MODULES
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #ed3cfe
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le catalogue des modules (docs/CN_MODULES.md) est généré depuis les manifestes : il doit dire la même chose qu'eux.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ed3cfe ▼▼▼
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
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Catalogue
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
