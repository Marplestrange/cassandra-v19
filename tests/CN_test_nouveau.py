# ═══════════════════════════════════════════════════════════════════════════
# TITRE      : L'assistant de création d'un module
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #a6adae
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'assistant de création d'un module : le squelette est valide, se charge, s'active, répond, et se met en paquet.
# MÉTHODE    : crée un module neuf, le greffe dans un vrai noyau et appelle sa capacité
# ═══════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a6adae ▼▼▼
"""Un module créé par l'assistant doit marcher sans qu'on y touche : manifeste valide (importance et phrase « sans » déclarées), activable, capacité qui répond, paquet constructible."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur  # noqa: E402
from noyau import CN_manifeste as mf, CN_nouveau as N, CN_paquets as paquets  # noqa: E402

ADMIN = "chef@x.fr"


class Nouveau(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def test_le_squelette_est_valide_et_declare_son_importance(self):
        d = N.creer(self.base, "mon_module", "Mon module", "gestion", "important")
        m = mf.charger(d / "CN_manifeste.toml")
        self.assertEqual((m.id, m.nom, m.famille, m.importance, m.confiance), ("mon_module", "Mon module", "gestion", "important", "local"))
        self.assertTrue(m.sans)
        for f in ("CN_manifeste.toml", "CN_module.py", "CN_LISEZ-MOI.md"):
            self.assertTrue((d / f).is_file(), f)

    def test_un_identifiant_mal_ecrit_un_niveau_inconnu_ou_un_dossier_existant_sont_refuses(self):
        for mauvais in ("", "X", "Mal Ecrit", "9abc", "a" * 50):
            with self.assertRaises(ValueError):
                N.creer(self.base, mauvais)
        with self.assertRaises(ValueError):
            N.creer(self.base, "bon_module", importance="capital")
        N.creer(self.base, "bon_module")
        with self.assertRaisesRegex(ValueError, "existe déjà"):
            N.creer(self.base, "bon_module")
        self.assertFalse((self.base / "capital").exists())

    def test_un_nom_avec_des_guillemets_ne_casse_pas_le_manifeste(self):
        d = N.creer(self.base, "citation", 'Le "Grand" module')
        self.assertEqual(mf.charger(d / "CN_manifeste.toml").nom, "Le 'Grand' module")

    def test_le_module_se_greffe_s_active_et_repond(self):
        ext = self.base / "ext"
        N.creer(ext, "bonjour", "Bonjour")
        mods = self.base / "modules"
        for m in ("droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        n = moteur.Noyau(self.base / "d", mods, {}, gerer_modules=True, extensions=ext)
        n.brancher()
        for m in ("droits", "comptes", "bonjour"):
            self.assertTrue(n.activer(m)["ok"], m)
        n.droits.regler_admin(ADMIN, True)
        r = n.executeur.executer("bonjour.etat", "humain", {}, compte=ADMIN)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"], {"message": "Bonjour depuis Bonjour", "version": "0.1.0"})

    @unittest.skipUnless(shutil.which("openssl"), "openssl absent")
    def test_le_module_se_met_en_paquet_et_se_relit(self):
        d = N.creer(self.base, "paquetable")
        priv = self.base / "e.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(priv)], check=True, capture_output=True)
        a = paquets.construire(d, priv, self.base / "p.cmod")
        self.assertEqual(paquets.verifier(a)["id"], "paquetable")

    def test_la_ligne_de_commande_cree_le_dossier(self):
        r = subprocess.run([sys.executable, str(RACINE / "CN_main.py"), "module", "nouveau", "cli_module", "--nom", "Module CLI", "--dest", str(self.base)], capture_output=True, text=True, cwd=str(RACINE))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.base / "cli_module" / "CN_manifeste.toml").is_file())
        r = subprocess.run([sys.executable, str(RACINE / "CN_main.py"), "module", "nouveau", "Mal Ecrit", "--dest", str(self.base)], capture_output=True, text=True, cwd=str(RACINE))
        self.assertEqual(r.returncode, 1)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le banc de l'assistant de création.
# EC : néant.
# LIEN : noyau/CN_nouveau.py, CN_main.py (module nouveau).
