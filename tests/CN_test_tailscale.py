# ══════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #deb334
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module tailscale : le client est simulé (un faux `tailscale` qui répond comme le vrai), le reste tourne dans un vrai noyau.
# MÉTHODE    : on remplace `_lancer` du module ; on vérifie les états, le lien d'identification, la clé qui ne traîne nulle part, et les refus dits en clair.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=deb334 ▼▼▼
"""Bancs du module tailscale : le client est simulé, le reste tourne dans un vrai noyau."""
import json
import shutil
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402

class Echec(Exception):
    pass


CLE = "tskey-auth-kAbCdEfGh12345-ZyXwVuTsRqPoNmLkJiHg"


def statut(backend, **plus):
    d = {"Version": "1.80.0", "BackendState": backend, "AuthURL": "", "TailscaleIPs": [], "Health": [], "Self": {}, "Peer": {}, "CurrentTailnet": {}}
    d.update(plus)
    return d


CONNECTE = statut("Running", TailscaleIPs=["100.64.0.7", "fd7a::7"], Self={"HostName": "argos", "DNSName": "argos.tail1.ts.net."},
                  CurrentTailnet={"Name": "drisse@example.org", "MagicDNSSuffix": "tail1.ts.net"},
                  Peer={"a": {"HostName": "orion", "DNSName": "orion.tail1.ts.net.", "TailscaleIPs": ["100.64.0.2"], "OS": "linux", "Online": True, "LastSeen": "2026-11-02T10:00:00Z"},
                        "b": {"HostName": "hermes", "DNSName": "hermes.tail1.ts.net.", "TailscaleIPs": ["100.64.0.3"], "OS": "windows", "Online": False, "LastSeen": "2026-10-30T08:00:00Z"}})


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "tailscale", mods / "tailscale")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("tailscale", installe=True, actif=False, par="test")
        self.assertTrue(self.n.activer("tailscale")["ok"])
        self.e = self.n.executeur.executer
        self.g = self.n.catalogue.get("tailscale.etat").faire.__globals__
        self.appels = []
        self.etat = statut("Stopped")
        self.reponses = {}
        self.prefs = {"RunSSH": False}
        self.g["_lancer"] = self.faux_client
        self.g["time"] = types.SimpleNamespace(time=time.time, sleep=lambda s: None)

    def faux_client(self, args, delai=10):
        self.appels.append(list(args))
        if args[:2] == ["status", "--json"]:
            if self.etat is None:
                return None, "absent"
            return 0, json.dumps(self.etat)
        if args[:2] == ["debug", "prefs"]:
            return 0, json.dumps(self.prefs)
        cle = args[0]
        if cle in self.reponses:
            return self.reponses[cle]
        if cle == "up":
            f = [x for x in args if x.startswith("--auth-key=file:")]
            if f:
                self.cle_lue = open(f[0].split("file:", 1)[1]).read()
                self.mode = oct(__import__("os").stat(f[0].split("file:", 1)[1]).st_mode & 0o777)
                self.etat = CONNECTE
            return 0, ""
        if cle == "down":
            self.etat = statut("Stopped")
        if cle == "logout":
            self.etat = statut("NeedsLogin")
        if cle == "set" and args[1].startswith("--ssh="):
            self.prefs["RunSSH"] = args[1].endswith("true")
        return 0, ""

    def lire(self, cap, **a):
        r = self.e("tailscale." + cap, "humain", a, compte="")
        if r.get("statut") != "faite":
            raise Echec(r.get("erreur") or r.get("raison") or str(r))
        return r["resultat"]


class Etats(Monde):
    def test_client_absent_se_dit(self):
        self.etat = None
        r = self.lire("etat")
        self.assertEqual(r["etat"], "absent")

    def test_deconnecte_connecte_et_identification_sont_trois_etats(self):
        self.assertEqual(self.lire("etat")["etat"], "deconnecte")
        self.etat = statut("NeedsLogin", AuthURL="https://login.tailscale.com/a/abc123")
        r = self.lire("etat")
        self.assertEqual((r["etat"], r["lien"]), ("a_identifier", "https://login.tailscale.com/a/abc123"))
        self.etat = CONNECTE
        r = self.lire("etat")
        self.assertEqual((r["etat"], r["nom"], r["ip4"], r["ip6"], r["reseau"]), ("connecte", "argos", "100.64.0.7", "fd7a::7", "drisse@example.org"))

    def test_les_machines_du_reseau_en_ligne_d_abord(self):
        self.etat = CONNECTE
        r = self.lire("etat")
        self.assertEqual([p["nom"] for p in r["pairs"]], ["orion", "hermes"])
        self.assertEqual(r["en_ligne"], 1)

    def test_ssh_se_lit_dans_les_preferences(self):
        self.etat = CONNECTE
        self.assertFalse(self.lire("etat")["ssh"])
        self.prefs["RunSSH"] = True
        self.assertTrue(self.lire("etat")["ssh"])


class Gestes(Monde):
    def test_connecter_avec_cle_ne_met_la_cle_ni_en_ligne_de_commande_ni_sur_disque(self):
        ctx = self.n.executeur.contextes["tailscale"]
        ctx.reglage = lambda nom, defaut="": CLE if nom == "cle_auth" else defaut
        r = self.lire("connecter", nom="argos", ssh=True, avec_cle=True)
        self.assertEqual(r["etat"], "connecte")
        up = [a for a in self.appels if a[0] == "up"][0]
        self.assertTrue(all(CLE not in x for x in up))
        self.assertIn("--ssh", up)
        self.assertTrue([x for x in up if x.startswith("--operator=")], "--reset sans --operator ferait perdre à Cassandra le droit de piloter Tailscale")
        self.assertIn("--hostname=argos", up)
        self.assertEqual(self.cle_lue, CLE)
        if sys.platform != "win32":                       # Windows ne connaît pas les droits POSIX
            self.assertEqual(self.mode, "0o600")
        f = [x for x in up if x.startswith("--auth-key=file:")][0].split("file:", 1)[1]
        self.assertFalse(Path(f).exists(), "le fichier de la clé doit disparaître")

    def test_une_cle_mal_formee_est_refusee_avant_tout_appel(self):
        ctx = self.n.executeur.contextes["tailscale"]
        ctx.reglage = lambda nom, defaut="": "n'importe quoi" if nom == "cle_auth" else defaut
        with self.assertRaises(Exception) as q:
            self.lire("connecter", avec_cle=True)
        self.assertIn("tskey-", str(q.exception))
        self.assertFalse([a for a in self.appels if a[0] == "up"])

    def test_la_cle_ne_fuit_pas_dans_une_erreur(self):
        ctx = self.n.executeur.contextes["tailscale"]
        ctx.reglage = lambda nom, defaut="": CLE if nom == "cle_auth" else defaut
        self.reponses["up"] = (1, "invalid key: %s is expired" % CLE)
        with self.assertRaises(Exception) as q:
            self.lire("connecter", avec_cle=True)
        self.assertNotIn(CLE, str(q.exception))
        self.assertIn("tskey-", str(q.exception))

    def test_un_refus_d_acces_dit_la_commande_qui_le_regle(self):
        self.reponses["down"] = (1, "Access denied: checkprefs access denied\nUse 'sudo tailscale ...' to perform this operation")
        with self.assertRaises(Exception) as q:
            self.lire("deconnecter")
        self.assertIn("--operator=cassandra", str(q.exception))

    def test_un_nom_de_machine_invalide_est_refuse(self):
        with self.assertRaises(Exception):
            self.lire("connecter", nom="mauvais nom; rm -rf /")
        self.assertFalse([a for a in self.appels if a[0] == "up"])

    def test_deja_connecte_ne_relance_rien(self):
        self.etat = CONNECTE
        self.assertEqual(self.lire("connecter")["etat"], "connecte")
        self.assertFalse([a for a in self.appels if a[0] == "up"])

    def test_deconnecter_quitter_et_ssh(self):
        self.etat = CONNECTE
        self.assertEqual(self.lire("deconnecter")["etat"], "deconnecte")
        self.etat = CONNECTE
        self.assertEqual(self.lire("quitter")["etat"], "a_identifier")
        self.etat = CONNECTE
        self.assertTrue(self.lire("ssh_regler", actif=True)["ssh"])
        self.assertFalse(self.lire("ssh_regler", actif=False)["ssh"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le faux client, les états, les gestes.
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/tailscale (le module essayé)
