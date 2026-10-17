import unittest
import tempfile
from pathlib import Path
import CN_test_noyau as base

class PontFastPanel(unittest.TestCase):
    def setUp(self):
        # Initialisation du noyau avec un environnement temporaire
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        self.mods = self.base_dir / "modules"
        self.mods.mkdir()
        
        # Le noyau va charger le module "fastpanel" depuis ce dossier.
        # Ici on utilise directement le noyau du framework de tests.
        self.n = base.Noyau(self.base_dir / "d", self.mods, {"fastpanel": {}}, gerer_modules=True, exiger_compte=True)
        # self.n.brancher() etc.

    def tearDown(self):
        self.tmp.cleanup()

    @unittest.skip("brouillon : à corriger")

    def test_cloisonnement(self):
        # V18 : L'admin voit tout ; un compte ordinaire ne voit que ce qui se rattache à ses sites.
        # Un compte sans droit de "voir_tout" doit recevoir une liste filtrée.
        pass

    @unittest.skip("brouillon : à corriger")

    def test_z_zero_absence(self):
        # V18 : ZÉRO PAR ABSENCE ≠ ZÉRO PAR CONFORMITÉ
        # Vérifier qu'une exception de lecture ne renvoie pas un simple tableau vide masquant la panne.
        pass

    @unittest.skip("brouillon : à corriger")

    def test_droits_manquants(self):
        # Test qu'une création/suppression par un utilisateur sans le droit "piloter" lève une PermissionError
        pass

    @unittest.skip("brouillon : à corriger")

    def test_preuve_et_retour_arriere(self):
        # Vérification du cycle: action -> preuve -> defaire
        pass
