# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'outil de bornes
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #07fc60
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'outil de bornes : détection des marqueurs, pureté d'une EC, conformité d'un fichier, scellement des empreintes.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=07fc60 ▼▼▼
"""Bancs de l'outil de bornes : détection des marqueurs, pureté d'une EC, conformité d'un fichier, scellement des empreintes."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import CN_bornes as B  # noqa: E402

NL = chr(10)

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
    return (EN_TETE.format(zone="EC", vcn="néant", vec="EC0 (référence 0.1.0)  #000000") + "# RUNTIME    : python\n# HÔTE CN    : CN_essai.py · essai.f @1.0\n" +
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

    def test_une_ec_doit_declarer_son_runtime(self):
        c = self.poser("EC_essai.py", fichier_ec().replace("# RUNTIME    : python\n", ""))
        self.assertTrue(any("RUNTIME" in e for e in B.analyser(c)["erreurs"]))

    def test_une_ec_dans_un_autre_langage_est_acceptee_sans_analyse_de_purete(self):
        php = fichier_ec("function f($x) { return $x + 1; }\n").replace("# ", "// ").replace("python", "php")
        c = self.poser("EC_essai.php", php)
        r = B.analyser(c)
        self.assertFalse([e for e in r["erreurs"] if "pureté" in e])
        self.assertTrue(any("runtime php" in i for i in r["infos"]))

    def test_un_binaire_ou_un_sql_porte_son_en_tete_dans_un_compagnon(self):
        c = self.poser("EC_essai.wasm", "bin")
        self.assertTrue(any("compagnon" in e for e in B.analyser(c)["erreurs"]))
        self.poser("EC_essai.wasm.borne", EN_TETE.format(zone="EC", vcn="néant", vec="EC0  #000000"))
        self.assertEqual(B.analyser(c)["erreurs"], [])
        m = self.poser("CN_001_init.sql", "CREATE TABLE t(x);\n")
        self.assertTrue(any("compagnon" in e for e in B.analyser(m)["erreurs"]))

    def test_les_ec_liees_acceptent_n_importe_quelle_extension(self):
        (self.tmp / "modules" / "essai" / "points").mkdir()
        self.poser("points/EC_essai.wasm", "bin")
        cn = fichier_cn().replace("# VERSION EC : néant\n", "# VERSION EC : néant\n# EC LIÉES   : essai.f @1.0 -> points/EC_essai.*\n")
        c = self.poser("CN_essai.py", cn)
        self.assertFalse([e for e in B.analyser(c)["erreurs"] if "EC LIÉES" in e])
        c2 = self.poser("CN_essai2.py", cn.replace("points/EC_essai.*", "points/EC_absent.*"))
        self.assertTrue(any("EC LIÉES" in e for e in B.analyser(c2)["erreurs"]))

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


class Versions(unittest.TestCase):
    """La version dit la même chose partout, et se monte d'un seul geste."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        ancienne, B.RACINE = B.RACINE, self.tmp
        self.addCleanup(setattr, B, "RACINE", ancienne)
        d = self.tmp / "modules" / "essai"
        d.mkdir(parents=True)
        (d / "CN_manifeste.toml").write_text('[module]\nid = "essai"\nversion = "0.1.0"\n', encoding="utf-8")
        corps = fichier_cn().replace("0.1.0  #000000", "0.1.0  #000000")
        (d / "CN_a.py").write_text(corps, encoding="utf-8", newline="\n")
        B.sceller("modules/essai/CN_a.py")

    def test_un_fichier_qui_dit_autre_chose_que_le_manifeste_est_signale(self):
        self.assertEqual(B.analyser("modules/essai/CN_a.py")["erreurs"], [])
        (self.tmp / "modules" / "essai" / "CN_manifeste.toml").write_text('[module]\nid = "essai"\nversion = "0.2.0"\n', encoding="utf-8")
        self.assertTrue(any("le manifeste du module 0.2.0" in e for e in B.analyser("modules/essai/CN_a.py")["erreurs"]))

    def test_un_marqueur_qui_dit_autre_chose_que_l_en_tete_est_signale(self):
        p = self.tmp / "modules" / "essai" / "CN_a.py"
        p.write_text(p.read_text(encoding="utf-8").replace("BORNE CN version=0.1.0", "BORNE CN version=9.9.9"), encoding="utf-8", newline="\n")
        self.assertTrue(any("le marqueur de borne 9.9.9" in e for e in B.analyser("modules/essai/CN_a.py")["erreurs"]))

    def test_monter_met_tout_a_jour_et_rend_le_module_conforme(self):
        modifies = B.monter("essai", "0.2.0")
        self.assertIn("modules/essai/CN_manifeste.toml", modifies)
        self.assertIn("modules/essai/CN_a.py", modifies)
        self.assertEqual(B.version_du_module("essai"), "0.2.0")
        t = (self.tmp / "modules" / "essai" / "CN_a.py").read_text(encoding="utf-8")
        self.assertIn("VERSION CN : 0.2.0", t)
        self.assertIn("BORNE CN version=0.2.0", t)
        self.assertEqual(B.analyser("modules/essai/CN_a.py")["erreurs"], [])
        self.assertEqual([i for i in B.analyser("modules/essai/CN_a.py")["infos"] if "empreinte" in i], [])

    def test_une_version_mal_formee_ou_un_module_inconnu_est_refuse(self):
        with self.assertRaises(ValueError):
            B.monter("essai", "2")
        with self.assertRaises(ValueError):
            B.monter("absent", "1.0.0")


class SansGit(unittest.TestCase):
    def test_sans_git_ce_que_git_ignorerait_n_est_pas_liste(self):
        """Sur une machine où le dépôt arrive par tar (pas de .git), `node_modules` et `__pycache__` ne sont pas des fichiers du projet."""
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        for chemin in ("CN_a.py", "modules/x/CN_b.py", "outils/ui/node_modules/lib/index.js", "modules/x/__pycache__/b.pyc"):
            f = tmp / chemin
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("x", encoding="utf-8")
        ancienne, B.RACINE = B.RACINE, tmp
        self.addCleanup(setattr, B, "RACINE", ancienne)
        self.assertEqual(sorted(B.fichiers_suivis()), ["CN_a.py", "modules/x/CN_b.py"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : fichier_cn, fichier_ec, Marqueurs, Purete, Conformite, Scellement
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
