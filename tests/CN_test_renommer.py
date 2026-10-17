# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'outil de renommage
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #ec4208
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'outil de renommage : une règle unique, des références réécrites sans toucher à la prose, les noms installés qui ne changent pas.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ec4208 ▼▼▼
"""Bancs de l'outil de renommage : une règle unique, des références réécrites sans toucher à la prose, les noms installés qui ne changent pas."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import CN_renommer as R  # noqa: E402


class Depot(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def poser(self, chemin, texte=""):
        p = self.tmp / chemin
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte, encoding="utf-8", newline="\n")

    def monter(self):
        self.poser("main.py", "from noyau import base, bus\nfrom noyau.contexte import Contexte\nimport noyau.base\n\nprint('à la main')\n")
        self.poser("noyau/base.py", "X = 1\n")
        self.poser("noyau/bus.py", "from . import base\nfrom .base import X\n")
        self.poser("noyau/contexte.py", "Contexte = 1\n")
        self.poser("noyau/__init__.py", "")
        self.poser("README.md", "# projet\n")
        self.poser("LICENSE", "AGPL")
        self.poser("modules/vue/module.py", "from . import composer\n")
        self.poser("modules/vue/composer.py", "def composer():\n    pass\n")
        self.poser("modules/vue/manifeste.toml", '[module]\nid = "vue"\n')
        self.poser("modules/urgence/installer.sh", 'for c in confiner crise; do\n  install -m 0755 "$D/commandes/$c" "/usr/libexec/cassandra/urgence/$c"\ndone\n')
        self.poser("modules/urgence/commandes/confiner", "#!/bin/sh\n")
        self.poser("modules/urgence/module.py", 'ctx.racine("confiner", [])\n')
        self.poser("tests/test_x.py", "from noyau.base import X\nimport main\n")
        self.poser("install.sh", "#!/bin/sh\n")
        self.poser("deploy.sh", "python3 -m unittest discover -s tests\nbash install.sh --module vue\nPYTHONPATH=. python main.py etat\n")
        self.poser("exploitation/cassandra-noyau.service", "NotifyAccess=main\nExecStart=/usr/bin/python3 main.py demarrer\n")
        self.poser("interface/index.html", "<script src=\"/app.js\"></script>")
        self.poser("interface/app.js", "1")
        self.poser("docs/NOTES.md", "voir modules/vue/module.py et install.sh\n")
        carte = R.plan(self.tmp)
        rew = R.Reecriture(self.tmp, carte)
        return carte, rew, rew.tout()


class Plan(Depot):
    def test_une_seule_regle_et_les_noms_imposes_restent(self):
        carte, _, _ = self.monter()
        self.assertEqual(carte["modules/vue/module.py"], "modules/vue/CN_module.py")
        self.assertEqual(carte["main.py"], "CN_main.py")
        self.assertEqual(carte["install.sh"], "CN_install.sh")
        for impose in ("README.md", "LICENSE", "noyau/__init__.py"):
            self.assertNotIn(impose, carte)

    def test_les_dossiers_ne_sont_pas_renommes(self):
        carte, _, _ = self.monter()
        self.assertTrue(all(n.startswith(c.rsplit("/", 1)[0] + "/") or "/" not in c for c, n in carte.items()))

    def test_idempotent_un_fichier_deja_prefixe_est_saute(self):
        self.poser("CN_a.py", "x = 1\n")
        self.assertEqual(R.plan(self.tmp), {})


class Imports(Depot):
    def test_les_imports_gardent_leur_nom_local(self):
        _, _, c = self.monter()
        self.assertIn("from noyau import CN_base as base, CN_bus as bus", c["main.py"])
        self.assertIn("from noyau.CN_contexte import Contexte", c["main.py"])
        self.assertIn("from . import CN_base as base", c["noyau/bus.py"])
        self.assertIn("from .CN_base import X", c["noyau/bus.py"])
        self.assertIn("from . import CN_composer as composer", c["modules/vue/module.py"])
        self.assertIn("import CN_main as main", c["tests/test_x.py"])
        self.assertIn("from noyau.CN_base import X", c["tests/test_x.py"])

    def test_un_import_sans_alias_d_un_module_pointe_est_prefixe(self):
        _, _, c = self.monter()
        self.assertIn("import noyau.CN_base", c["main.py"])


class Chaines(Depot):
    def test_la_prose_n_est_jamais_touchee(self):
        _, _, c = self.monter()
        self.assertIn("print('à la main')", c["main.py"])                      # « main » est un mot, pas un module
        self.assertIn("NotifyAccess=main", c["exploitation/cassandra-noyau.service"])

    def test_les_noms_avec_extension_sont_reecrits_partout(self):
        _, _, c = self.monter()
        self.assertIn("bash CN_install.sh --module vue", c["deploy.sh"])
        self.assertIn("python CN_main.py etat", c["deploy.sh"])
        self.assertIn("ExecStart=/usr/bin/python3 CN_main.py demarrer", c["exploitation/cassandra-noyau.service"])
        self.assertIn("modules/vue/CN_module.py", c["docs/NOTES.md"])

    def test_le_nom_installe_d_un_programme_racine_ne_change_pas(self):
        _, _, c = self.monter()
        self.assertIn('"$D/commandes/CN_$c" "/usr/libexec/cassandra/urgence/$c"', c["modules/urgence/installer.sh"])      # la source prend le préfixe, la destination non
        self.assertNotIn("modules/urgence/module.py", c)                         # ctx.racine("confiner", ...) : le nom du programme installé ne bouge pas

    def test_les_fichiers_servis_ne_sont_pas_reecrits(self):
        _, _, c = self.monter()
        self.assertNotIn("interface/index.html", c)                              # l'URL /app.js reste : le serveur retire le préfixe

    def test_une_adresse_web_n_est_pas_un_fichier_du_depot(self):
        self.poser("install.sh", "#!/bin/sh\n")
        self.poser("modules/ollama/installer.sh", "curl -fsSL https://ollama.com/install.sh | sh\nbash install.sh\n")
        carte = R.plan(self.tmp)
        c = R.Reecriture(self.tmp, carte).tout()
        self.assertIn("https://ollama.com/install.sh | sh", c["modules/ollama/installer.sh"])      # l'adresse extérieure ne bouge pas
        self.assertIn("bash CN_install.sh", c["modules/ollama/installer.sh"])                    # le fichier du dépôt, si

    def test_une_migration_garde_son_nom_dans_les_chaines(self):
        self.poser("modules/vue/migrations/001_init.sql", "CREATE TABLE t(a);\n")
        self.poser("tests/test_m.py", "assert appliquees == ['001_init.sql']\n")
        carte = R.plan(self.tmp)
        c = R.Reecriture(self.tmp, carte).tout()
        self.assertEqual(carte["modules/vue/migrations/001_init.sql"], "modules/vue/migrations/CN_001_init.sql")      # le fichier est renommé
        self.assertNotIn("tests/test_m.py", c)                                                                          # son identité, dans les chaînes, non

    def test_le_motif_de_decouverte_des_tests(self):
        _, _, c = self.monter()
        self.assertIn('unittest discover -s tests -p "CN_test*.py"', c["deploy.sh"])


class Application(Depot):
    def test_appliquer_renomme_et_laisse_un_depot_sans_residu(self):
        self.monter()
        code = R.principal(["x", "--racine", str(self.tmp), "--appliquer"])
        self.assertEqual(code, 0)
        self.assertTrue((self.tmp / "modules" / "vue" / "CN_module.py").exists())
        self.assertFalse((self.tmp / "modules" / "vue" / "module.py").exists())
        self.assertTrue((self.tmp / "README.md").exists())
        self.assertEqual(R.residus(self.tmp), [])
        import ast
        for f in self.tmp.rglob("*.py"):
            ast.parse(f.read_text(encoding="utf-8"))                              # tout reste du Python valide
        self.assertEqual(R.plan(self.tmp), {})                                    # un second passage ne trouve plus rien à faire


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Depot, Plan, Imports, Chaines, Application
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
