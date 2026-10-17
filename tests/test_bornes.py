"""Bancs de l'outil de bornes : détection des marqueurs, pureté d'une EC, conformité d'un fichier, scellement des empreintes."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import CN_bornes as B  # noqa: E402

EN_TETE = """# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Essai
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : essai
# ZONE       : {zone}
# VERSION CN : {vcn}
# VERSION EC : {vec}
# RÔLE       : un essai
# MÉTHODE    : sans méthode
# ══════════════════════════════════════════════════════════════════════════════
"""


def fichier_cn(corps="x = 1\n"):
    return (EN_TETE.format(zone="CN", vcn="0.1.0  #000000", vec="néant") +
            "# ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼\n" + corps +
            "# ▲▲▲ FIN BORNE CN ▲▲▲\n\n# ═══ EXPLICATIF CN / EC ═══\n# CN : essai.\n")


def fichier_ec(corps="def f(x):\n    return x + 1\n"):
    return (EN_TETE.format(zone="EC", vcn="néant", vec="EC0 (référence 0.1.0)  #000000") + "# HÔTE CN    : CN_essai.py · essai.f @1.0\n" +
            "# ▼▼▼ BORNE EC point=essai.f contrat=@1.0 version=EC0 empreinte=000000 ▼▼▼\n" + corps +
            "# ▲▲▲ FIN BORNE EC ▲▲▲\n\n# ═══ EXPLICATIF CN / EC ═══\n# EC : essai.\n")


class Marqueurs(unittest.TestCase):
    def test_une_vraie_ligne_de_marqueur_est_reconnue(self):
        self.assertTrue(B.marqueur("# ▼▼▼ BORNE CN version=0.1.0 empreinte=abc123 ▼▼▼").startswith("BORNE CN"))
        self.assertTrue(B.marqueur("# ▲▲▲ FIN BORNE EC ▲▲▲").startswith("FIN BORNE"))
        self.assertTrue(B.marqueur("# ═══ EXPLICATIF CN / EC ═══").startswith("EXPLICATIF"))
        self.assertTrue(B.marqueur("// ▼▼▼ BORNE CN version=1 empreinte=ab ▼▼▼"))
        self.assertTrue(B.marqueur("<!-- ▼▼▼ BORNE CN version=1 empreinte=ab ▼▼▼ -->"))

    def test_une_chaine_qui_cite_un_marqueur_n_en_est_pas_un(self):
        self.assertIsNone(B.marqueur('    if "FIN BORNE" in l:'))
        self.assertIsNone(B.marqueur('RE = re.compile(r"BORNE CN version=(\\S+)")'))
        self.assertIsNone(B.marqueur("# un commentaire ordinaire sur la borne"))


class Purete(unittest.TestCase):
    def test_une_fonction_pure_passe(self):
        self.assertEqual(B.pureté("import math\n\ndef f(x):\n    return math.sqrt(x)\n"), [])

    def test_les_effets_sont_refuses(self):
        self.assertTrue(any("os" in f for f in B.pureté("import os\n\ndef f():\n    return os.getcwd()\n")))
        self.assertTrue(any("ctx" in f for f in B.pureté("def f(ctx):\n    return 1\n")))
        self.assertTrue(any("open" in f for f in B.pureté("def f():\n    return open('x')\n")))
        self.assertTrue(any("time" in f for f in B.pureté("import time\n\ndef f():\n    return time.time()\n")))
        self.assertTrue(any("global" in f for f in B.pureté("X = 1\n\ndef f():\n    global X\n    X = 2\n")))

    def test_une_syntaxe_illisible_est_signalee(self):
        self.assertTrue(B.pureté("def f(:\n"))


class Conformite(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._racine, B.RACINE = B.RACINE, self.tmp
        self.addCleanup(setattr, B, "RACINE", self._racine)
        (self.tmp / "modules" / "essai").mkdir(parents=True)

    def poser(self, nom, texte):
        p = self.tmp / "modules" / "essai" / nom
        p.write_text(texte, encoding="utf-8", newline="\n")
        return "modules/essai/" + nom

    def test_un_fichier_conforme_n_a_pas_d_erreur(self):
        c = self.poser("CN_essai.py", fichier_cn())
        B.sceller(c)
        self.assertEqual(B.analyser(c)["erreurs"], [])

    def test_un_fichier_ec_pur_est_conforme(self):
        c = self.poser("EC_essai.py", fichier_ec())
        B.sceller(c)
        self.assertEqual(B.analyser(c)["erreurs"], [])

    def test_le_prefixe_manquant_est_une_erreur(self):
        c = self.poser("essai.py", fichier_cn())
        self.assertTrue(any("préfixe" in e for e in B.analyser(c)["erreurs"]))

    def test_le_prefixe_doit_egaler_la_zone(self):
        c = self.poser("EC_essai.py", fichier_cn())
        self.assertTrue(any("différent de ZONE" in e for e in B.analyser(c)["erreurs"]))

    def test_un_en_tete_incomplet_est_signale(self):
        c = self.poser("CN_essai.py", fichier_cn().replace("# TITRE      : Essai\n", ""))
        self.assertTrue(any("TITRE" in e for e in B.analyser(c)["erreurs"]))

    def test_du_code_hors_borne_est_une_erreur(self):
        c = self.poser("CN_essai.py", fichier_cn().replace("# ▼▼▼ BORNE CN", "y = 2\n# ▼▼▼ BORNE CN", 1))
        self.assertTrue(any("hors borne" in e for e in B.analyser(c)["erreurs"]))

    def test_l_explicatif_est_obligatoire(self):
        c = self.poser("CN_essai.py", fichier_cn().replace("# ═══ EXPLICATIF CN / EC ═══\n", ""))
        self.assertTrue(any("explicatif" in e for e in B.analyser(c)["erreurs"]))

    def test_une_ec_impure_est_refusee(self):
        c = self.poser("EC_essai.py", fichier_ec("import os\n\ndef f(x):\n    return os.getcwd()\n"))
        self.assertTrue(any("pureté" in e for e in B.analyser(c)["erreurs"]))

    def test_une_ec_sans_hote_est_refusee(self):
        c = self.poser("EC_essai.py", fichier_ec().replace("# HÔTE CN    : CN_essai.py · essai.f @1.0\n", ""))
        self.assertTrue(any("HÔTE" in e for e in B.analyser(c)["erreurs"]))

    def test_la_constante_du_projet_est_gardee(self):
        c = self.poser("CN_essai.py", fichier_cn().replace("marplestrange@cassandra.center", "autre@exemple.test"))
        self.assertTrue(any("MAIL" in e for e in B.analyser(c)["erreurs"]))

    def test_un_nom_impose_de_l_exterieur_est_hors_format(self):
        c = self.poser("__init__.py", "")
        r = B.analyser(c)
        self.assertTrue(r.get("exempt"))
        self.assertEqual(r["erreurs"], [])


class Scellement(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self._racine, B.RACINE = B.RACINE, self.tmp
        self.addCleanup(setattr, B, "RACINE", self._racine)

    def test_sceller_ecrit_l_empreinte_et_se_repete_sans_changer(self):
        (self.tmp / "CN_a.py").write_text(fichier_cn(), encoding="utf-8", newline="\n")
        self.assertTrue(B.sceller("CN_a.py"))
        t1 = (self.tmp / "CN_a.py").read_text(encoding="utf-8")
        self.assertNotIn("empreinte=000000", t1)
        self.assertFalse(B.sceller("CN_a.py"))            # idempotent
        self.assertEqual(t1, (self.tmp / "CN_a.py").read_text(encoding="utf-8"))

    def test_modifier_la_borne_change_l_empreinte(self):
        (self.tmp / "CN_a.py").write_text(fichier_cn(), encoding="utf-8", newline="\n")
        B.sceller("CN_a.py")
        avant = B.analyser("CN_a.py")["infos"]
        t = (self.tmp / "CN_a.py").read_text(encoding="utf-8").replace("x = 1", "x = 2")
        (self.tmp / "CN_a.py").write_text(t, encoding="utf-8", newline="\n")
        self.assertTrue(any("empreinte à recalculer" in i for i in B.analyser("CN_a.py")["infos"]))
        self.assertFalse(any("empreinte à recalculer" in i for i in avant))


if __name__ == "__main__":
    unittest.main()
