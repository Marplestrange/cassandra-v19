"""Le moteur évolutif : une génération par défaut, plusieurs tirages du modèle par parent, un modèle muet n'arrête pas la recherche."""
import importlib.util
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))


def _charger(nom, chemin):
    sp = importlib.util.spec_from_file_location(nom, RACINE / chemin)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


O = _charger("orfan_essais", "orfan/CN_orfan.py")
EV = _charger("evolutif_essais", "orfan/CN_evolutif.py")

SOURCE = "def f(entree):\n    return {'y': sorted(entree['xs'])[0]}\n"
RAPIDE = "```python\ndef f(entree):\n    return {'y': min(entree['xs'])}\n```"
CONTEXTE = {"source_reference": SOURCE, "fonction": "f", "point": "essai", "budget": 3, "entrees": [{"xs": list(range(3000, 0, -1))} for _ in range(6)]}


class Essais(unittest.TestCase):
    def test_defauts(self):
        m = EV.MoteurEvolutif(O)
        self.assertEqual((m.generations, m.essais), (1, 2))

    def test_deux_tirages_par_parent(self):
        appels = []
        m = EV.MoteurEvolutif(O, lambda p, r="x": appels.append(p) or RAPIDE, generations=1, parents=1, essais=2)
        m.proposer(dict(CONTEXTE))
        self.assertGreaterEqual(len(appels), 2)
        self.assertEqual(len(appels) % 2, 0)

    def test_un_modele_muet_arrete_les_tirages_sans_casser_la_recherche(self):
        def muet(p, r="x"):
            raise RuntimeError("plafond")
        m = EV.MoteurEvolutif(O, muet, essais=3)
        m.proposer(dict(CONTEXTE))
        self.assertEqual(len([j for j in m.journal if "indisponible" in j]), 1)

    def test_les_doublons_entre_tirages_sont_ecartes(self):
        m = EV.MoteurEvolutif(O, lambda p, r="x": RAPIDE, generations=1, parents=1, essais=3)
        textes = [c["texte"] for c in m.proposer(dict(CONTEXTE))]
        self.assertEqual(len(textes), len(set(textes)))


if __name__ == "__main__":
    unittest.main()
