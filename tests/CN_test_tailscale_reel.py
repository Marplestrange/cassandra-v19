# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Banc du module tailscale contre un VRAI tailscaled (mode utilisateur, socket et état dans 
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #cd93c7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Banc du module tailscale contre un VRAI tailscaled (mode utilisateur, socket et état dans un dossier temporaire : le tailscaled de la machine n'est pas touché).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=cd93c7 ▼▼▼
"""Banc du module tailscale contre un VRAI tailscaled (mode utilisateur, socket et état dans un dossier temporaire : le tailscaled de la machine n'est pas touché).

Les bancs simulés (CN_test_tailscale.py) ne voient pas ce que le vrai client refuse ou renvoie : trois défauts n'ont été trouvés qu'en essayant pour de vrai (un `up` avec
drapeau refusé sur une machine coupée, le droit d'opérateur effacé par `logout`, un message de santé non traduit). Ce banc les garde en vue.

    CASSANDRA_TS_REEL=1 python -m unittest tests.CN_test_tailscale_reel            gestes sans identification : état, réglages, lien, annulation, `up` orphelin
    CASSANDRA_TS_REEL=1 TS_AUTHKEY=tskey-auth-... python -m unittest ...           en plus : connexion par clé, coupure, reconnexion, retrait (la clé doit être éphémère)

Sans CASSANDRA_TS_REEL=1, ou sans `tailscaled` et `tailscale` dans le PATH, tout est sauté.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402

ACTIF = os.environ.get("CASSANDRA_TS_REEL") == "1" and shutil.which("tailscaled") and shutil.which("tailscale")
CLE = os.environ.get("TS_AUTHKEY", "")


class Echec(Exception):
    pass


@unittest.skipUnless(ACTIF, "banc réel : CASSANDRA_TS_REEL=1 et tailscaled/tailscale installés")
class Reel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        cls.socket = str(base / "ts.sock")
        cls.demon = subprocess.Popen(["tailscaled", "--tun=userspace-networking", "--socket=" + cls.socket, "--statedir=" + str(base / "etat")],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            if os.path.exists(cls.socket):
                break
            time.sleep(0.5)
        else:
            cls.demon.kill()
            raise unittest.SkipTest("tailscaled n'a pas démarré (droits ? /dev/net/tun n'est pas nécessaire en mode utilisateur)")
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "tailscale", mods / "tailscale", ignore=shutil.ignore_patterns("__pycache__"))
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        cls.n.etat_modules.poser("tailscale", installe=True, actif=False, par="test")
        assert cls.n.activer("tailscale")["ok"]
        cls.e = cls.n.executeur.executer
        cls.g = cls.n.catalogue.get("tailscale.etat").faire.__globals__
        cls.g["_SOCKET"] = cls.socket
        cls.g["_TTL"] = 0
        try:
            import pwd
            moi = pwd.getpwuid(os.getuid()).pw_name
        except ImportError:
            moi = "cassandra"
        # le démon de ce banc appartient à celui qui le lance : il en est l'opérateur de fait
        subprocess.run(["tailscale", "--socket=" + cls.socket, "set", "--operator=" + moi], capture_output=True, timeout=20)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.demon.terminate()
            cls.demon.wait(10)
        except Exception:                      # noqa: BLE001
            cls.demon.kill()
        cls.tmp.cleanup()

    def lire(self, cap, **a):
        r = self.e("tailscale." + cap, "humain", a, compte="")
        if r.get("statut") != "faite":
            raise Echec(r.get("erreur") or r.get("raison") or str(r))
        return r["resultat"]

    def prefs(self):
        out = subprocess.run(["tailscale", "--socket=" + self.socket, "debug", "prefs"], capture_output=True, text=True, timeout=20).stdout
        return json.loads(out)

    def attendre_etat(self, voulus, delai=30):
        fin = time.time() + delai
        r = {}
        while time.time() < fin:
            r = self.lire("etat")
            if r.get("etat") in voulus:
                return r
            time.sleep(1)
        self.fail("état attendu %s, vu %s" % (voulus, r.get("etat")))

    def test_01_un_demon_neuf_demande_une_identification(self):
        r = self.attendre_etat({"a_identifier", "deconnecte"})
        self.assertIn(r["etat"], ("a_identifier", "deconnecte"))
        self.assertIsNotNone(r["reglages"], "les réglages se lisent dans les vraies préférences")
        self.assertIn(r["pilotable"], (True, False))

    def test_02_les_reglages_se_lisent_et_s_ecrivent_dans_les_vraies_preferences(self):
        self.attendre_etat({"a_identifier", "deconnecte", "connecte"})
        res = self.lire("regler", cle="accept_routes", valeur=True)
        self.assertTrue(res["reglages"]["accept_routes"])
        self.assertTrue(self.prefs()["RouteAll"], "le champ RouteAll des préférences est bien « accept_routes »")
        self.lire("regler", cle="shields_up", valeur=True)
        self.assertTrue(self.prefs()["ShieldsUp"])
        self.lire("regler", cle="advertise_routes", valeur="192.168.77.0/24")
        self.assertEqual(self.lire("etat")["reglages"]["advertise_routes"], ["192.168.77.0/24"])
        self.lire("regler", cle="advertise_exit_node", valeur=True)
        r = self.lire("etat")["reglages"]
        self.assertTrue(r["advertise_exit_node"])
        self.assertEqual(r["advertise_routes"], ["192.168.77.0/24"], "annoncer la sortie Internet ne perd pas les routes")
        self.lire("regler", cle="advertise_routes", valeur="")
        r = self.lire("etat")["reglages"]
        self.assertEqual((r["advertise_routes"], r["advertise_exit_node"]), ([], True), "vider les routes garde la sortie Internet annoncée")
        for cle, valeur in (("accept_routes", False), ("shields_up", False), ("advertise_exit_node", False)):
            self.lire("regler", cle=cle, valeur=valeur)
        r = self.lire("etat")["reglages"]
        self.assertEqual((r["accept_routes"], r["shields_up"], r["advertise_exit_node"], r["advertise_routes"]), (False, False, False, []))

    def test_03_un_refus_du_client_se_dit_en_clair(self):
        self.attendre_etat({"a_identifier", "deconnecte", "connecte"})
        with self.assertRaises(Echec) as q:
            self.lire("regler", cle="exit_node", valeur="100.64.0.250")
        self.assertIn("sortie", str(q.exception).lower())

    def test_04_connexion_sans_cle_lien_puis_annulation_et_orphelin(self):
        r = self.attendre_etat({"a_identifier", "deconnecte"})
        try:
            r = self.lire("connecter")
        except Echec as e:
            self.skipTest("le serveur de coordination Tailscale n'est pas joignable d'ici : %s" % e)
        self.assertTrue(r.get("lien", "").startswith("https://login.tailscale.com/"), r)
        self.assertTrue(self.lire("etat")["en_attente"])
        # un redémarrage de Cassandra : le `up` en attente n'est plus suivi, il doit se retrouver (même socket) puis s'abandonner
        self.g["_EN_ATTENTE"]["proc"] = None
        self.assertTrue(self.lire("etat")["en_attente"], "le `up` orphelin se retrouve par /proc")
        self.lire("annuler")
        time.sleep(2)
        self.assertFalse(self.lire("etat")["en_attente"])
        self.assertEqual(self.g["orphelins"](), [])

    @unittest.skipUnless(CLE, "TS_AUTHKEY (clé éphémère) non fournie : cycle complet sauté")
    def test_05_cycle_complet_avec_une_cle(self):
        ctx = self.n.executeur.contextes["tailscale"]
        ctx.reglage = lambda nom, defaut="": CLE if nom == "cle_auth" else defaut
        self.assertEqual(self.lire("connecter", avec_cle=True)["etat"], "connecte")
        self.lire("regler", cle="accept_routes", valeur=True)
        self.assertEqual(self.lire("deconnecter")["etat"], "deconnecte")
        # le défaut trouvé sur argos : sans AUCUN drapeau, la reconnexion garde les réglages ; avec --timeout le client la refusait
        self.assertEqual(self.lire("connecter")["etat"], "connecte")
        self.assertTrue(self.prefs()["RouteAll"], "la reconnexion ne remet rien à zéro")
        self.assertEqual(self.lire("quitter")["etat"], "a_identifier")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Echec, Reel
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
