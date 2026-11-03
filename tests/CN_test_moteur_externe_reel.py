# ══════════════════════════════════════════════
# TITRE      : Banc du moteur externe réel (OpenEvolve, de bout en bout)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #e815e1
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Installe le vrai OpenEvolve (paquets épinglés par empreinte, venv), le fait chercher dans la cage avec un modèle de banc, et vérifie ce que le relais a compté.
# MÉTHODE    : sauté sans réseau : il lui faut un accès à PyPI et ~1 minute. `CN_TEST_RESEAU=1 python -m unittest tests.CN_test_moteur_externe_reel` ; sous Linux avec bubblewrap, c'est le bac qui enveloppe le moteur.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e815e1 ▼▼▼
"""Banc de bout en bout d'un moteur externe réel. Il n'est joué que sur demande (CN_TEST_RESEAU=1) : il télécharge une trentaine de paquets."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_installateur as I  # noqa: E402
from noyau import CN_moteurs as MO  # noqa: E402


@unittest.skipUnless(os.environ.get("CN_TEST_RESEAU") == "1", "CN_TEST_RESEAU=1 pour jouer ce banc (accès à PyPI)")
class OpenEvolveReel(unittest.TestCase):
    def test_installe_epingle_et_cherche_dans_la_cage(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "cle").write_bytes(b"cle-de-banc-" * 3)
            r = subprocess.run([sys.executable, str(RACINE / "outils" / "CN_moteurs_epingler.py"), "--id", "openevolve", "--nom", "OpenEvolve", "--paquet", "openevolve==0.4.1",
                                "--adaptateur", "CN_adaptateur_openevolve", "--catalogue", str(base / "moteurs-catalogue.json"), "--cle", str(base / "cle")], capture_output=True, text=True, timeout=900)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            reg = MO.Registre(base / "moteurs.json")
            res = I.Installateur(base / "moteurs", base / "moteurs-catalogue.json", (base / "cle").read_bytes(), registre=reg, delai_s=900).installer("openevolve")
            self.assertTrue(res["ok"], res)
            m = [x for x in reg.liste() if x["id"] == "openevolve"][0]
            relais = []
            moteur = MO.MoteurProcessus("adaptateur:" + m["adaptateur"], appeler_modele=lambda p, role: "idée\n```python\ndef f(x):\n    return min(x)\n```", python=m["python"], delai_s=420,
                                        max_appels=8, nom="openevolve", on_relais=relais.append)
            ctx = {"point": "a.b", "source_reference": "def f(x):\n    return sorted(x)[0]\n", "fonction": "f", "contrat": {}, "tombes": [], "budget": 2, "seuils": {},
                   "entrees": [list(range(3000, 0, -1)), list(range(4000, 100, -3)), [5, 3, 9] * 900]}
            sortie = moteur.proposer(ctx)
            self.assertTrue(sortie)
            self.assertIn("min(x)", sortie[0]["texte"])
            self.assertGreaterEqual(moteur.stats["appels_modele"], 1)                   # le moteur n'a parlé à un modèle que par le relais
            self.assertEqual(len(relais), moteur.stats["appels_modele"] + moteur.stats["refus"])


CTX = {"point": "a.b", "source_reference": "def f(x):\n    return sorted(x)[0]\n", "fonction": "f", "contrat": {}, "tombes": [], "budget": 2, "seuils": {},
       "entrees": [list(range(3000, 0, -1)), list(range(4000, 100, -3)), [5, 3, 9] * 900]}
DIFF = "idée\n<<<<<<< SEARCH\n    return sorted(x)[0]\n=======\n    return min(x)\n>>>>>>> REPLACE\n"
CODE = "idée\n```python\ndef f(x):\n    return min(x)\n```"


def _moteur_reel(testcase, ident, paquet, adaptateur, interpreteur=""):
    """Épingle, installe et lance un moteur externe réel dans la cage ; rend (sortie, moteur)."""
    tmp = tempfile.TemporaryDirectory()
    testcase.addCleanup(tmp.cleanup)
    base = Path(tmp.name)
    (base / "cle").write_bytes(b"cle-de-banc-" * 3)
    cmd = [sys.executable, str(RACINE / "outils" / "CN_moteurs_epingler.py"), "--id", ident, "--nom", ident, "--paquet", paquet, "--adaptateur", adaptateur,
           "--catalogue", str(base / "moteurs-catalogue.json"), "--cle", str(base / "cle")] + (["--interpreteur", interpreteur] if interpreteur else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1500)
    testcase.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    reg = MO.Registre(base / "moteurs.json")
    res = I.Installateur(base / "moteurs", base / "moteurs-catalogue.json", (base / "cle").read_bytes(), registre=reg, delai_s=1500).installer(ident)
    testcase.assertTrue(res["ok"], res)
    m = [x for x in reg.liste() if x["id"] == ident][0]
    moteur = MO.MoteurProcessus("adaptateur:" + m["adaptateur"], appeler_modele=lambda p, role: DIFF if "SEARCH" in p else CODE, python=m["python"], delai_s=600, max_appels=40, nom=ident)
    return moteur.proposer(dict(CTX)), moteur


@unittest.skipUnless(os.environ.get("CN_TEST_RESEAU") == "1", "CN_TEST_RESEAU=1 pour jouer ce banc (accès à PyPI)")
class GepaEtShinkaReels(unittest.TestCase):
    def test_gepa(self):
        sortie, moteur = _moteur_reel(self, "gepa", "gepa==0.1.4", "CN_adaptateur_gepa")
        self.assertTrue(sortie)
        self.assertIn("min(x)", sortie[0]["texte"])
        self.assertGreaterEqual(moteur.stats["appels_modele"], 1)

    def test_shinka(self):
        sortie, moteur = _moteur_reel(self, "shinka", "shinka-evolve==0.0.7", "CN_adaptateur_shinka")
        self.assertTrue(sortie)
        self.assertIn("min(x)", sortie[0]["texte"])
        self.assertGreaterEqual(moteur.stats["appels_modele"], 1)


@unittest.skipUnless(os.environ.get("CN_TEST_RESEAU") == "1" and os.environ.get("CN_TEST_PYTHON313"), "CN_TEST_RESEAU=1 et CN_TEST_PYTHON313=<chemin d'un Python >= 3.13.5> pour jouer ce banc (GitHub)")
class CodeEvolveReel(unittest.TestCase):
    COMMIT = "9897ef16b79e95c4d6517ecb04461e27b2296e34"

    def test_le_vrai_codeevolve_dans_son_python_313(self):
        sortie, moteur = _moteur_reel(self, "codeevolve", "codeevolve @ https://codeload.github.com/inter-co/science-codeevolve/tar.gz/" + self.COMMIT, "CN_adaptateur_codeevolve",
                                      os.environ["CN_TEST_PYTHON313"])
        self.assertTrue(sortie)
        self.assertIn("min(x)", sortie[0]["texte"])
        self.assertGreaterEqual(moteur.stats["appels_modele"], 1)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (des bancs).
# CN : tout ce fichier est du nexus : le banc du moteur externe réel.
# LIEN : outils/CN_moteurs_epingler.py, noyau/CN_installateur.py, orfan/adaptateurs/CN_adaptateur_openevolve.py, orfan/CN_moteur_hote.py.
