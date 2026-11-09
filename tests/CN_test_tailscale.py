# ══════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #dce85f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module tailscale : le client est simulé (un faux `tailscale` qui répond comme le vrai), le reste tourne dans un vrai noyau.
# MÉTHODE    : on remplace `_lancer` du module ; on vérifie les états, le lien d'identification, la clé qui ne traîne nulle part, et les refus dits en clair.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=dce85f ▼▼▼
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
        self.g["_TTL"] = 0                                          # pas de cache : les bancs changent l'état du faux client entre deux lectures
        self.pong = ""
        self.g["utilisateur"] = lambda: "cassandra"          # le compte qui pilote : fixé, le banc ne dépend pas de celui qui le lance
        self.apres_cle = CONNECTE
        self.g["_PROC"] = str(base / "pas-de-proc")            # le banc ne regarde pas les vrais processus de la machine
        self.bruit_avant = self.bruit_apres = ""
        self.g["time"] = types.SimpleNamespace(time=time.time, sleep=lambda s: None)

    def faux_client(self, args, delai=10):
        self.appels.append(list(args))
        if args[:2] == ["status", "--json"]:
            if self.etat is None:
                return None, "absent"
            return 0, self.bruit_avant + json.dumps(self.etat) + self.bruit_apres
        if args[:2] == ["debug", "prefs"]:
            return 0, json.dumps(self.prefs)
        cle = args[0]
        if cle in self.reponses:
            return self.reponses[cle]
        if args == ["up"] and getattr(self, "identification_requise", False):
            return None, "pas de réponse de tailscaled"         # le `up` seul attend une identification qui ne vient pas
        if args == ["up"] and self.etat.get("BackendState") == "Stopped":
            self.etat = CONNECTE                              # `up` seul : la machine enregistrée reprend sa configuration
            return 0, ""
        if cle == "up" and any(x == "--timeout=15m" or x.startswith("--timeout") for x in args) and self.etat.get("BackendState") == "Stopped" and not [x for x in args if x.startswith("--reset")]:
            return 1, "changing settings via 'tailscale up' requires mentioning all non-default flags"       # ce que le vrai client dit (constaté sur argos)
        if cle == "up":
            f = [x for x in args if x.startswith("--auth-key=file:")]
            if f:
                self.cle_lue = open(f[0].split("file:", 1)[1]).read()
                self.mode = oct(__import__("os").stat(f[0].split("file:", 1)[1]).st_mode & 0o777)
                self.etat = self.apres_cle
            return 0, ""
        if cle == "down":
            self.etat = statut("Stopped")
        if cle == "logout":
            self.etat = statut("NeedsLogin")
        if cle == "set" and args[1].startswith("--ssh="):
            self.prefs["RunSSH"] = args[1].endswith("true")
        if cle == "set" and "=" in args[1]:
            nom, val = args[1].split("=", 1)
            booleens = {"--accept-routes": "RouteAll", "--accept-dns": "CorpDNS", "--shields-up": "ShieldsUp"}
            if nom in booleens:
                self.prefs[booleens[nom]] = val == "true"
            elif nom == "--hostname":
                self.prefs["Hostname"] = val
            elif nom == "--exit-node":
                self.prefs["ExitNodeIP"] = val
            elif nom == "--advertise-routes":
                self.prefs["AdvertiseRoutes"] = [x for x in val.split(",") if x] or None
            elif nom == "--advertise-exit-node":
                routes = [x for x in (self.prefs.get("AdvertiseRoutes") or []) if x not in ("0.0.0.0/0", "::/0")]
                self.prefs["AdvertiseRoutes"] = (routes + ["0.0.0.0/0", "::/0"] if val == "true" else routes) or None
        if cle == "ping":
            return 0, self.pong
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
        self.etat = statut("NeedsLogin")                  # première connexion : rien à garder, `--reset --operator` est voulu
        ctx = self.n.executeur.contextes["tailscale"]
        ctx.reglage = lambda nom, defaut="": CLE if nom == "cle_auth" else defaut
        r = self.lire("connecter", nom="argos", ssh=True, avec_cle=True)
        self.assertEqual(r["etat"], "connecte")
        up = [a for a in self.appels if a[0] == "up"][0]
        self.assertTrue(all(CLE not in x for x in up))
        self.assertIn("--ssh", up)
        self.assertTrue([x for x in up if x.startswith("--operator=")], "--reset sans --operator ferait perdre à Cassandra le droit de piloter Tailscale")
        self.assertIn("--hostname=argos", up)
        self.assertIn("--reset", up)
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


class Corrections(Monde):
    """Les défauts relevés à l'audit : chacun a son banc."""

    def cle(self):
        ctx = self.n.executeur.contextes["tailscale"]
        ctx.reglage = lambda nom, defaut="": CLE if nom == "cle_auth" else defaut

    def test_reconnecter_une_machine_coupee_ne_remet_rien_a_zero(self):
        self.etat = statut("Stopped")
        r = self.lire("connecter", nom="argos", ssh=True)
        self.assertEqual(r["etat"], "connecte")
        self.assertEqual([a for a in self.appels if a[0] == "up"], [["up"]],
                         "aucun drapeau : ni --reset (efface routes, nœud de sortie, DNS), ni --timeout (le client refuse tout `up` avec drapeau quand un réglage n'est pas celui par défaut)")
        self.assertIn(["set", "--hostname=argos"], self.appels)
        self.assertIn(["set", "--ssh=true"], self.appels)

    def test_une_machine_coupee_dont_l_identite_est_a_refaire_repart_comme_une_premiere_connexion(self):
        self.cle()
        self.etat = statut("Stopped")
        self.identification_requise = True
        r = self.lire("connecter", avec_cle=True)
        self.assertEqual(r["etat"], "connecte")
        ups = [a for a in self.appels if a[0] == "up"]
        self.assertEqual(ups[0], ["up"])
        self.assertIn("--reset", ups[1])
        self.assertTrue([x for x in ups[1] if x.startswith("--operator=")])

    def test_une_machine_a_approuver_n_est_pas_defaite(self):
        self.cle()
        self.etat = statut("NeedsLogin")
        self.apres_cle = statut("NeedsMachineAuth")
        r = self.lire("connecter", avec_cle=True)
        self.assertEqual(r["etat"], "a_approuver")
        self.assertFalse([a for a in self.appels if a[0] == "down"], "défaire couperait une connexion valable, qui n'attend que l'administrateur")

    def test_annuler_ne_coupe_pas_une_connexion_qui_marche(self):
        self.etat = CONNECTE
        r = self.lire("annuler")
        self.assertEqual(r["etat"], "connecte")
        self.assertFalse([a for a in self.appels if a[0] == "down"])

    def test_annuler_coupe_une_identification_abandonnee(self):
        self.etat = statut("NeedsLogin", AuthURL="https://login.tailscale.com/a/abc123")
        self.lire("annuler")
        self.assertTrue([a for a in self.appels if a[0] == "down"])

    def test_un_avertissement_du_client_ne_fait_pas_croire_que_tailscaled_est_arrete(self):
        self.etat = CONNECTE
        self.bruit_avant = 'Warning: client version "1.80.0" != tailscaled server version "1.104.4"' + chr(10)
        self.bruit_apres = chr(10) + 'Warning: autre chose'
        r = self.lire("etat")
        self.assertEqual((r["etat"], r["nom"]), ("connecte", "argos"))

    def test_deja_connecte_applique_quand_meme_le_nom_et_ssh_demandes(self):
        self.etat = CONNECTE
        r = self.lire("connecter", nom="neuf", ssh=True)
        self.assertEqual(r["etat"], "connecte")
        self.assertIn(["set", "--hostname=neuf"], self.appels)
        self.assertIn(["set", "--ssh=true"], self.appels)
        self.assertFalse([a for a in self.appels if a[0] == "up"])

    def test_l_etat_dit_si_cassandra_peut_piloter(self):
        self.etat = CONNECTE
        self.prefs = {"RunSSH": False}
        r = self.lire("etat")
        self.assertIs(r["pilotable"], False)
        self.prefs = {"RunSSH": False, "OperatorUser": "cassandra"}
        self.assertIs(self.lire("etat")["pilotable"], True)

    def test_le_refus_d_acces_nomme_le_compte_reel(self):
        self.g["utilisateur"] = lambda: "service"
        self.reponses["down"] = (1, "Access denied: checkprefs access denied")
        with self.assertRaises(Exception) as q:
            self.lire("deconnecter")
        self.assertIn("--operator=service", str(q.exception))

    def test_trois_machines_localhost_ne_portent_pas_le_meme_nom(self):
        pairs = {str(i): {"HostName": "localhost", "DNSName": ("localhost.tail1.ts.net." if i == 0 else "localhost-%d.tail1.ts.net." % i), "TailscaleIPs": ["100.64.0.%d" % (10 + i)],
                          "OS": "android", "Online": True, "LastSeen": "2026-11-09T10:00:00Z"} for i in range(3)}
        self.etat = dict(CONNECTE, Peer=pairs)
        noms = sorted(p["nom"] for p in self.lire("etat")["pairs"])
        self.assertEqual(len(set(noms)), 3, noms)

    def test_un_up_d_avant_un_redemarrage_est_vu_et_abandonne(self):
        from unittest import mock
        proc = Path(self.tmp.name) / "proc"
        for pid, cmd in (("4242", ["/usr/bin/tailscale", "up", "--reset", "--operator=cassandra", "--timeout=15m"]), ("77", ["/usr/bin/tailscale", "status"]), ("x", ["rien"])):
            (proc / pid).mkdir(parents=True)
            (proc / pid / "cmdline").write_bytes(b"\0".join(c.encode() for c in cmd) + b"\0")
        self.g["_PROC"] = str(proc)
        self.etat = statut("NeedsLogin", AuthURL="https://login.tailscale.com/a/abc123")
        self.assertTrue(self.lire("etat")["en_attente"], "un `up` encore en attente doit se voir, sinon un second s'ajoute au premier")
        self.assertEqual(self.g["orphelins"](), [4242])
        with mock.patch.object(__import__("os"), "kill") as tuer:
            self.lire("annuler")
        tuer.assert_called_once()
        self.assertEqual(tuer.call_args[0][0], 4242)


class Ajouts(Monde):
    """Réglages, ping, expiration des clés, cache et flux d'événements."""

    def set_appels(self):
        return [a for a in self.appels if a[0] == "set"]

    def test_l_etat_donne_les_reglages_lus_dans_les_preferences(self):
        self.etat = CONNECTE
        self.prefs = {"RouteAll": True, "CorpDNS": True, "ShieldsUp": False, "Hostname": "argos", "AdvertiseRoutes": ["10.0.0.0/24", "0.0.0.0/0", "::/0"], "ExitNodeIP": ""}
        r = self.lire("etat")["reglages"]
        self.assertEqual((r["accept_routes"], r["accept_dns"], r["shields_up"], r["hostname"]), (True, True, False, "argos"))
        self.assertEqual((r["advertise_routes"], r["advertise_exit_node"]), (["10.0.0.0/24"], True))

    def test_regler_change_un_reglage_par_set_et_le_prouve(self):
        self.etat = CONNECTE
        r = self.lire("regler", cle="accept_routes", valeur=True)
        self.assertTrue(r["reglages"]["accept_routes"])
        self.assertIn(["set", "--accept-routes=true"], self.appels)
        self.assertFalse([a for a in self.appels if a[0] == "up"], "jamais up --reset pour un réglage")

    def test_regler_se_defait_par_la_valeur_d_avant(self):
        self.etat = CONNECTE
        self.prefs = {"ShieldsUp": False}
        res = self.lire("regler", cle="shields_up", valeur="oui")
        self.assertTrue(self.prefs["ShieldsUp"])
        self.n.catalogue.get("tailscale.regler").defaire(self.n.executeur.contextes["tailscale"], res)
        self.assertFalse(self.prefs["ShieldsUp"])

    def test_regler_refuse_ce_qui_n_a_pas_de_sens(self):
        self.etat = CONNECTE
        for cle, valeur in (("inconnu", True), ("accept_routes", "peut-etre"), ("hostname", "mauvais nom;"), ("advertise_routes", "pas-une-route"),
                            ("advertise_routes", "0.0.0.0/0"), ("exit_node", "100.64.0.2"), ("exit_node", "pas-une-ip")):
            with self.assertRaises(Exception, msg=(cle, valeur)):
                self.lire("regler", cle=cle, valeur=valeur)
        self.assertFalse(self.set_appels(), "rien n'est envoyé au client quand la valeur est refusée")

    def test_le_nom_se_remet_a_celui_du_systeme_en_le_videant(self):
        self.etat = CONNECTE
        self.prefs = {"Hostname": "autre"}
        self.lire("regler", cle="hostname", valeur="")
        self.assertIn(["set", "--hostname="], self.appels)
        self.assertEqual(self.prefs["Hostname"], "")

    def test_les_routes_annoncees_gardent_la_sortie_internet_deja_annoncee(self):
        self.etat = CONNECTE
        self.prefs = {"AdvertiseRoutes": ["0.0.0.0/0", "::/0"]}
        r = self.lire("regler", cle="advertise_routes", valeur="192.168.1.0/24, 10.0.0.5/24")
        arg = [a for a in self.set_appels() if a[1].startswith("--advertise-routes=")][0][1]
        self.assertIn("192.168.1.0/24", arg)
        self.assertIn("10.0.0.0/24", arg)                      # mise en forme : l'adresse d'hôte devient le réseau
        self.assertIn("0.0.0.0/0", arg)
        self.assertTrue(r["reglages"]["advertise_exit_node"])

    def test_le_noeud_de_sortie_doit_etre_une_machine_qui_en_offre_une(self):
        pairs = dict(CONNECTE["Peer"])
        pairs["c"] = {"HostName": "sortie", "DNSName": "sortie.tail1.ts.net.", "TailscaleIPs": ["100.64.0.9"], "OS": "linux", "Online": True, "ExitNodeOption": True, "LastSeen": "2026-11-09T10:00:00Z"}
        self.etat = dict(CONNECTE, Peer=pairs)
        r = self.lire("regler", cle="exit_node", valeur="100.64.0.9")
        self.assertEqual(r["reglages"]["exit_node"], "100.64.0.9")

    def test_ping_dit_le_chemin_et_le_temps(self):
        self.etat = CONNECTE
        self.pong = "pong from orion (100.64.0.2) via DERP(hel) in 120ms" + chr(10) + "pong from orion (100.64.0.2) via 82.1.2.3:41641 in 20ms" + chr(10) + "pong from orion (100.64.0.2) via 82.1.2.3:41641 in 40ms"
        r = self.lire("ping", machine="orion")
        self.assertEqual((r["ok"], r["chemin"], r["reponses"], r["ms"]), (True, "direct", 3, 60.0))
        self.assertIn(["ping", "-c", "3", "--timeout", "2s", "100.64.0.2"], self.appels)

    def test_ping_sans_reponse_et_ping_d_une_machine_inconnue(self):
        self.etat = CONNECTE
        self.pong = "no reply"
        r = self.lire("ping", machine="orion")
        self.assertEqual((r["ok"], r["reponses"]), (False, 0))
        n = len(self.appels)
        with self.assertRaises(Exception):
            self.lire("ping", machine="; rm -rf /")
        self.assertEqual([a for a in self.appels[n:] if a[0] == "ping"], [], "la cible vient du réseau, jamais d'un argument libre")

    def test_les_cles_qui_expirent_sont_annoncees(self):
        import datetime as dt
        bientot = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=5, hours=2)).isoformat()
        passee = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=2)).isoformat()
        loin = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=90)).isoformat()
        pairs = {"a": dict(CONNECTE["Peer"]["a"], KeyExpiry=passee), "b": dict(CONNECTE["Peer"]["b"], KeyExpiry=loin)}
        self.etat = dict(CONNECTE, Self=dict(CONNECTE["Self"], KeyExpiry=bientot), Peer=pairs)
        r = self.lire("etat")
        self.assertEqual(r["expiration"]["jours"], 5)
        self.assertEqual([(x["nom"], x["jours"] < 0) for x in r["expirent"]], [("orion", True)])
        self.etat = CONNECTE
        self.assertIsNone(self.lire("etat")["expiration"])

    def test_etat_reutilise_la_derniere_lecture_puis_les_gestes_relisent(self):
        self.g["_TTL"] = 60
        self.etat = CONNECTE
        self.lire("etat")
        n = len([a for a in self.appels if a[:2] == ["status", "--json"]])
        self.lire("etat")
        self.assertEqual(len([a for a in self.appels if a[:2] == ["status", "--json"]]), n, "deuxième lecture : servie par le cache")
        self.lire("ssh_regler", actif=True)
        self.assertTrue(self.lire("etat")["ssh"], "un geste qui écrit relit à neuf : le cache ne montre jamais l'avant")

    def test_le_veilleur_reveille_l_attente_des_qu_un_evenement_arrive(self):
        import sys as _s
        import time as _t
        V = self.g["Veilleur"]
        v = V(commande=[_s.executable, "-c", "import time; time.sleep(0.3); print('evenement', flush=True); time.sleep(5)"])
        try:
            debut = _t.time()
            self.assertTrue(v.attendre(4))
            self.assertLess(_t.time() - debut, 2.5, "réveillé par l'événement, pas par la fin du délai")
        finally:
            v.fermer()

    def test_sans_flux_le_veilleur_dort_comme_avant(self):
        dormi = []
        self.g["time"] = types.SimpleNamespace(time=time.time, sleep=lambda x: dormi.append(x))
        v = self.g["Veilleur"](commande=["commande-qui-n-existe-pas-xyz"])
        self.assertIsNone(v.proc)
        self.assertFalse(v.attendre(0.7))
        self.assertEqual(dormi, [0.7])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le faux client, les états, les gestes.
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/tailscale (le module essayé)
