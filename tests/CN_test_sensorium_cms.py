# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la détection du CMS par le collecteur
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #5b7327
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la détection du CMS par le collecteur : la table cms_sites existait et rien ne la remplissait. Le collecteur est chargé sur une base temporaire ; les racines des sites sont de vrais dossiers temporaires : aucune commande, aucun rés
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=5b7327 ▼▼▼
"""Bancs de la détection du CMS par le collecteur : la table cms_sites existait et rien ne la remplissait.
Le collecteur est chargé sur une base temporaire ; les racines des sites sont de vrais dossiers temporaires : aucune commande, aucun réseau."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from tests.CN_test_sensorium_v19 import charger_demon  # noqa: E402


class Cms(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.m = charger_demon(self.tmp)
        self.m.init_all_tables()
        self.sites = []

    def site(self, domaine, fichiers=None, racine=None):
        base = Path(racine) if racine else self.tmp / "www" / domaine
        base.mkdir(parents=True, exist_ok=True)
        for rel, texte in (fichiers or {}).items():
            f = base / rel
            if texte is None:
                f.mkdir(parents=True, exist_ok=True)
            else:
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(texte, encoding="utf-8")
        self.sites.append({"domain": domaine, "document_root": str(base), "ssl_enabled": 1, "server_type": "nginx", "php_version": "", "status": "active", "last_check": "x"})
        return base

    def relever(self):
        self.m.save_many("web_sites", self.sites)
        return {c["domain"]: c for c in self.m.collect_cms_sites()}

    def test_un_wordpress_est_reconnu_avec_sa_version(self):
        self.site("blog.exemple.test", {"wp-config.php": "<?php // rien", "wp-includes/version.php": "<?php\n$wp_version = '6.7.1';\n"})
        c = self.relever()["blog.exemple.test"]
        self.assertEqual((c["cms_type"], c["version"]), ("wordpress", "6.7.1"))

    def test_un_site_statique_n_a_pas_de_cms(self):
        self.site("vitrine.exemple.test", {"index.html": "<h1>bonjour</h1>"})
        self.assertEqual(self.relever(), {})

    def test_une_racine_absente_ou_vide_ne_casse_rien(self):
        self.sites.append({"domain": "fantome.exemple.test", "document_root": str(self.tmp / "nulle-part"), "ssl_enabled": 0, "server_type": "nginx", "php_version": "", "status": "active", "last_check": "x"})
        self.sites.append({"domain": "relais.exemple.test", "document_root": "", "ssl_enabled": 0, "server_type": "nginx", "php_version": "", "status": "active", "last_check": "x"})
        self.assertEqual(self.relever(), {})

    def test_deux_sites_sur_la_meme_racine_ont_le_meme_cms(self):
        base = self.site("a.exemple.test", {"occ": "#!/usr/bin/env php", "lib/versioncheck.php": "<?php", "version.php": "<?php\n$OC_VersionString = '30.0.2';\n"})
        self.site("b.exemple.test", racine=base)
        r = self.relever()
        self.assertEqual({d: (c["cms_type"], c["version"]) for d, c in r.items()}, {"a.exemple.test": ("nextcloud", "30.0.2"), "b.exemple.test": ("nextcloud", "30.0.2")})

    def test_rien_ne_se_lit_hors_de_la_racine(self):
        """Un lien symbolique qui sort de la racine (posé par le propriétaire du site, lu par un collecteur qui tourne en root) est ignoré."""
        dehors = self.tmp / "secret"
        dehors.mkdir()
        (dehors / "version.php").write_text("<?php\n$wp_version = '9.9.9';\n", encoding="utf-8")
        base = self.site("piege.exemple.test", {"wp-config.php": "<?php"})
        try:
            os.symlink(str(dehors), str(base / "wp-includes"), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("liens symboliques indisponibles sur ce poste")
        self.assertEqual(self.relever(), {})                                     # wp-includes mène dehors : le marqueur ne compte pas, donc pas de CMS

    def test_la_table_est_remplie_et_lisible_par_le_socket(self):
        self.site("blog.exemple.test", {"wp-config.php": "<?php", "wp-includes/version.php": "<?php\n$wp_version = '6.7.1';\n"})
        self.m.save_many("web_sites", self.sites)
        self.m.save_many("cms_sites", self.m.collect_cms_sites())
        conn = self.m.get_conn()
        try:
            lignes = conn.execute("SELECT domain, cms_type, version FROM cms_sites").fetchall()
        finally:
            conn.close()
        self.assertEqual([tuple(x) for x in lignes], [("blog.exemple.test", "wordpress", "6.7.1")])
        self.assertIn("cms_sites", self.m.SOCKET_ALLOWED_ENTITIES)               # sans cela sensorium.entite("cms_sites") était refusée


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Cms
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
