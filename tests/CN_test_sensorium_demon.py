# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du démon Sensorium : socket, boucle, échecs de commandes, jeton FastPanel, certificats, journaux d'attaques, box
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #4c9e27
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : prouve les garanties du démon du Sensorium que l'audit de novembre 2026 a corrigées : un échec de commande n'est pas « rien à signaler », un socket muet est lâché ou fait arrêter le collecteur, un jeton FastPanel expiré est renouvelé, un certificat expiré se compte, un journal d'accès se lit par blocs, une redirection rouverte alerte.
# MÉTHODE    : charge CN_sensorium.py comme module sur une base et un socket temporaires, simule les commandes et l'API HTTP (aucun réseau, aucune commande système), puis appelle les fonctions du démon.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=4c9e27 ▼▼▼
import gzip
import importlib.util
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
DOSSIER = RACINE / "modules" / "sensorium"
PYTHON = sys.executable


def charger_demon(donnees, base, sock):
    os.environ["CASSANDRA_DATA_DIR"] = str(donnees)
    os.environ["SENSORIUM_DB"] = str(base)
    os.environ["SENSORIUM_SOCKET"] = str(sock)
    sys.path.insert(0, str(DOSSIER))
    spec = importlib.util.spec_from_file_location("sensorium_demon_garanties", DOSSIER / "CN_sensorium.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Reponse:
    """Une réponse HTTP minimale (urlopen) : `read()` et le gestionnaire de contexte."""
    def __init__(self, corps):
        self._octets = json.dumps(corps).encode()

    def read(self, *a):
        return self._octets

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.donnees = self.tmp / "donnees" / "sensorium"
        self.donnees.mkdir(parents=True)
        (self.tmp / "donnees" / "ec").mkdir()
        self.sock = self.tmp / "k.sock"
        self.m = charger_demon(self.donnees, self.donnees / "s.db", self.sock)
        import CN_points_sensorium as ps
        ps._SVC = ps._REJEU = None
        ps._ECHEC = ""
        self.m.init_all_tables()

    def echange(self, texte):
        """Ce que le serveur répond à une requête, sur une paire de sockets (sans fichier socket)."""
        srv = self.m.SharedMemorySocket()
        a, b = socket.socketpair()
        t = threading.Thread(target=srv.handle_client, args=(b,))
        t.start()
        a.sendall(texte.encode())
        a.settimeout(5)
        data = b""
        while True:
            morceau = a.recv(65536)
            if not morceau:
                break
            data += morceau
        t.join()
        a.close()
        return data


class CommandesEtJson(Base):
    def test_un_echec_n_est_pas_un_resultat_vide(self):
        rc, _out, _err = self.m.run_cmd_ex([PYTHON, "-c", "import sys; sys.exit(3)"])
        self.assertEqual(rc, 3)
        with self.assertRaises(RuntimeError):
            self.m.run_cmd_strict([PYTHON, "-c", "import sys; sys.stderr.write('boum'); sys.exit(2)"])
        self.assertEqual(self.m.run_cmd_strict([PYTHON, "-c", "pass"]), "")           # vide ET réussi : une vraie absence

    def test_une_commande_introuvable_ou_trop_lente_n_a_pas_de_code(self):
        rc, _o, err = self.m.run_cmd_ex(["commande-qui-n-existe-pas-xyz"])
        self.assertIsNone(rc)
        self.assertTrue(err)
        self.assertEqual(self.m.run_cmd(["commande-qui-n-existe-pas-xyz"]), "")
        rc, _o, err = self.m.run_cmd_ex([PYTHON, "-c", "import time; time.sleep(5)"], timeout=1)
        self.assertIsNone(rc)
        self.assertIn("délai", err)

    def test_les_erreurs_ne_se_melent_pas_au_json(self):
        code = "import sys, json; sys.stderr.write('avertissement'); print(json.dumps({'a': 1}))"
        self.assertEqual(self.m.run_json([PYTHON, "-c", code], {}), {"a": 1})
        self.assertEqual(self.m.run_json([PYTHON, "-c", "print('pas du json')"], {"d": 1}), {"d": 1})
        self.assertEqual(self.m.run_json(["commande-qui-n-existe-pas-xyz"], []), [])

    def test_les_unites_en_echec_levent_quand_systemctl_echoue(self):
        with mock.patch.object(self.m, "_qui", return_value="/bin/systemctl"), \
                mock.patch.object(self.m, "run_cmd_ex", return_value=(1, "", "Failed to connect to bus")):
            with self.assertRaises(RuntimeError):
                self.m.collect_failed_units()
        with mock.patch.object(self.m, "_qui", return_value="/bin/systemctl"), \
                mock.patch.object(self.m, "run_cmd_ex", return_value=(0, "", "")):
            self.assertEqual(self.m.collect_failed_units(), [])               # aucune unité en échec : une vraie réponse

    def test_fail2ban_arrete_n_est_pas_aucune_adresse_bannie(self):
        with mock.patch.object(self.m, "_qui", return_value="/usr/bin/fail2ban-client"), \
                mock.patch.object(self.m, "run_cmd_ex", return_value=(255, "", "Failed to access socket path")):
            with self.assertRaises(RuntimeError):
                self.m.collect_fail2ban_banned()
        with mock.patch.object(self.m, "_qui", return_value=""):
            self.assertEqual(self.m.collect_fail2ban_banned(), [])            # pas de fail2ban : personne n'est banni


class Lots(Base):
    def test_le_lot_omet_les_echecs_et_n_attend_pas_la_tache_lente(self):
        def lent():
            time.sleep(4)
            return [2]

        def boum():
            raise RuntimeError("x")
        t0 = time.time()
        r = self.m.KnowledgeCollector._run_parallel([("a", lambda: [1]), ("b", boum), ("c", lent)], max_workers=3, delai=1)
        self.assertEqual(r, {"a": [1]})                       # ni la panne ni la tâche lente ne sont rendues : leur table garde son état
        self.assertLess(time.time() - t0, 3.5)                # le lot n'a pas attendu la tâche de 4 s
        conn = self.m.get_conn()
        etat = {x["famille"]: x for x in conn.execute("SELECT * FROM sensor_health")}
        conn.close()
        self.assertIsNotNone(etat["a"]["dernier_ok"])
        self.assertEqual(etat["b"]["erreur"], "x")
        self.assertIn("délai", etat["c"]["erreur"])

    def test_une_seule_construction_du_monde_a_la_fois(self):
        actifs, maxi, appels, verrou = [0], [0], [0], threading.Lock()

        def faux():
            with verrou:
                actifs[0] += 1
                maxi[0] = max(maxi[0], actifs[0])
                appels[0] += 1
            time.sleep(0.3)
            with verrou:
                actifs[0] -= 1
        self.m._construire_world_model = faux
        fils = [threading.Thread(target=self.m.build_world_model) for _ in range(6)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(maxi[0], 1)                          # jamais deux à la fois
        self.assertIn(appels[0], (2, 3))                      # les demandes reçues en cours de route en valent UNE de plus, pas six


class Socket(Base):
    def test_ping_et_requetes_inconnues(self):
        self.assertEqual(self.echange("PING"), b"PONG")
        self.assertEqual(self.echange("N_IMPORTE_QUOI"), b"ERROR")

    def test_un_client_muet_est_lache(self):
        srv = self.m.SharedMemorySocket()
        a, b = socket.socketpair()
        t = threading.Thread(target=srv.handle_client, args=(b,))
        t0 = time.time()
        t.start()
        t.join(timeout=9)                                     # le client n'envoie rien
        a.close()
        self.assertFalse(t.is_alive(), "le fil du client muet n'a pas été libéré")
        self.assertLess(time.time() - t0, 8)

    def test_les_jokers_d_un_like_ne_sont_pas_des_jokers(self):
        conn = self.m.get_conn()
        for cle, val in (("co_a", "x"), ("coXa", "x"), ("zz", "100%"), ("yy", "1000")):
            conn.execute("INSERT INTO world_model (wkey, category, value, severity, source, observed_at, updated_at) "
                         "VALUES (?,?,?,?,?,?,?)", (cle, "c", val, "info", "observed", "t", "t"))
        conn.commit()
        conn.close()
        cles = lambda d: sorted(x["wkey"] for x in json.loads(d))
        self.assertEqual(cles(self.echange("GET_WORLD:co_")), ["co_a"])           # « _ » n'est plus « un caractère quelconque »
        self.assertEqual(cles(self.echange("QUERY_WORLD:100%")), ["zz"])          # « % » non plus

    def test_le_collecteur_s_arrete_quand_le_fil_du_socket_meurt(self):
        """Sans sockets Unix (Windows) : le serveur de socket est simulé, il écoute puis s'éteint ; la boucle doit le voir."""
        m = self.m

        class SocketQuiMeurt:
            def __init__(self):
                self.running, self.pret, self.erreur = True, threading.Event(), "bind refusé"

            def start(self):
                self.pret.set()
                self.running = False

            def stop(self):
                pass
        for nom in dir(m):
            if nom.startswith("collect_") and nom != "collect_metrics":
                setattr(m, nom, lambda *a, **k: [])
        m.SharedMemorySocket = SocketQuiMeurt
        m._SOCKET_MORT_APRES = 2
        c = m.KnowledgeCollector()
        erreurs = []

        def cible():
            try:
                c.run()
            except BaseException as e:
                erreurs.append(e)
        t = threading.Thread(target=cible, daemon=True)
        t.start()
        t.join(timeout=40)
        c.running = False
        self.assertFalse(t.is_alive(), "le collecteur a continué avec un socket mort")
        self.assertTrue(erreurs and isinstance(erreurs[0], RuntimeError), erreurs)
        self.assertIn("socket", str(erreurs[0]))
        self.assertIn("bind refusé", str(erreurs[0]))

    @unittest.skipUnless(hasattr(socket, "AF_UNIX"), "pas de sockets Unix sur cette plateforme")
    def test_le_collecteur_s_arrete_quand_son_socket_disparait(self):
        m = self.m
        for nom in dir(m):                                    # aucune commande système : tous les relevés rendent du vide
            if nom.startswith("collect_") and nom != "collect_metrics":
                setattr(m, nom, lambda *a, **k: [])
        m._SOCKET_MORT_APRES = 2
        c = m.KnowledgeCollector()
        erreurs = []

        def cible():
            try:
                c.run()
            except BaseException as e:
                erreurs.append(e)
        t = threading.Thread(target=cible, daemon=True)
        t.start()
        for _ in range(100):                                  # le socket écoute-t-il ?
            if self.sock.exists():
                break
            time.sleep(0.2)
        self.assertTrue(self.sock.exists(), "le socket n'est jamais apparu")
        c2 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        c2.settimeout(5)
        c2.connect(str(self.sock))
        c2.sendall(b"PING")
        self.assertEqual(c2.recv(16), b"PONG")
        c2.close()
        os.unlink(self.sock)                                  # le fichier socket disparaît : le collecteur ne doit pas collecter dans le vide
        t.join(timeout=40)
        c.running = False
        self.assertFalse(t.is_alive(), "le collecteur a continué avec un socket mort")
        self.assertTrue(erreurs and isinstance(erreurs[0], RuntimeError), erreurs)
        self.assertIn("socket", str(erreurs[0]))


class JetonFastPanel(Base):
    def _faux_urlopen(self, appels):
        def faux(req, timeout=0):
            url, jeton = req.full_url, req.get_header("Authorization")
            appels.append((url, jeton))
            if url.endswith("/login"):
                return Reponse({"token": "neuf"})
            if jeton == "Bearer vieux":
                raise urllib.error.HTTPError(url, 401, "expired", {}, None)
            return Reponse({"data": [1]})
        return faux

    def test_un_jeton_expire_est_renouvele_une_fois(self):
        m, appels = self.m, []
        m._fp_panel_creds = {"username": "u", "password": "p"}
        m._fp_jwt_token = "vieux"
        with mock.patch.object(urllib.request, "urlopen", self._faux_urlopen(appels)):
            self.assertEqual(m._fp_api_get("/api/x"), {"data": [1]})
        self.assertEqual(m._fp_jwt_token, "neuf")
        self.assertEqual(len(appels), 3)                      # l'appel refusé, la connexion, l'appel refait

    def test_un_mot_de_passe_change_fait_relire_les_fichiers(self):
        m = self.m
        m._fp_panel_creds = {"username": "u", "password": "ancien"}
        m._fp_jwt_token = ""

        def refuse(req, timeout=0):
            raise urllib.error.HTTPError(req.full_url, 401, "bad", {}, None)
        with mock.patch.object(urllib.request, "urlopen", refuse):
            self.assertEqual(m._fp_api_login(), "")
        self.assertEqual(m._fp_panel_creds, {})               # les identifiants en mémoire sont jetés


class Certificats(Base):
    def test_un_certificat_expire_se_compte_et_se_dit(self):
        conn = self.m.get_conn()
        for dom, jours in (("a.test", -3), ("b.test", 0), ("c.test", 10), ("d.test", 90)):
            conn.execute("INSERT INTO ssl_certificates (domain, issuer, days_left) VALUES (?,?,?)", (dom, "Let's Encrypt", jours))
        conn.commit()
        conn.close()
        srv = self.m.SharedMemorySocket()
        srv.update_cache()
        self.assertEqual(srv.cache["ssl_expiring"], 3)        # l'expiré (-3) et celui d'aujourd'hui comptent
        prev = {x["cle"]: x["valeur"] for x in self.m.calculer_projections()}
        self.assertIn("EXPIRÉ depuis 3 j", prev["certificat.a.test"])
        self.assertIn("aujourd'hui", prev["certificat.b.test"])
        self.assertIn("expire dans 10 j", prev["certificat.c.test"])
        self.assertNotIn("certificat.d.test", prev)

    def test_un_joker_et_les_autres_noms_donnent_les_jours_du_site(self):
        conn = self.m.get_conn()
        conn.execute("INSERT INTO ssl_certificates (domain, issuer, days_left, sans) VALUES (?,?,?,?)",
                     ("exemple.fr", "Let's Encrypt", 5, "exemple.fr,*.exemple.fr,autre.fr"))
        for d in ("www.exemple.fr", "autre.fr"):
            conn.execute("INSERT INTO web_sites (domain, ssl_enabled, status) VALUES (?,?,?)", (d, 1, "active"))
        conn.commit()
        conn.close()
        self.m._construire_world_model()
        conn = self.m.get_conn()
        monde = {x["wkey"]: x["value"] for x in conn.execute("SELECT wkey, value FROM world_model")}
        conn.close()
        self.assertIn("5 j", monde["web.www.exemple.fr"])     # couvert par le joker *.exemple.fr
        self.assertIn("5 j", monde["web.autre.fr"])           # couvert par un autre nom du même certificat


class JournauxDAttaques(Base):
    def test_reseaux_de_la_maison(self):
        for ip in ("192.168.1.5", "10.0.0.1", "100.64.3.2", "127.0.0.1", "::1", "fd00::1", "pas une adresse"):
            self.assertTrue(self.m._secu_maison(ip), ip)
        for ip in ("8.8.8.8", "93.184.216.34", "2606:4700::1111"):
            self.assertFalse(self.m._secu_maison(ip), ip)

    def test_lecture_par_blocs_et_ligne_en_cours(self):
        p = self.tmp / "acces.log"
        p.write_bytes(b"aaa\nbbb\nccc")                      # la dernière ligne n'est pas finie
        self.m._SECU_BLOC = 8
        self.assertEqual(list(self.m._secu_blocs(str(p), 0)), [(["aaa", "bbb"], 8)])
        with open(p, "ab") as f:
            f.write(b"\nddd\n")
        self.assertEqual(list(self.m._secu_blocs(str(p), 8)), [(["ccc", "ddd"], 16)])           # la ligne finie est lue, depuis l'octet 8
        p.write_bytes(b"x" * 20 + b"\n")                      # une ligne plus longue qu'un bloc : franchie, sans boucle infinie
        total = [pos for _l, pos in self.m._secu_blocs(str(p), 0)]
        self.assertEqual(total[-1], 21)

    def test_gzip_en_flux(self):
        p = self.tmp / "acces.log.2.gz"
        with gzip.open(p, "wt") as f:
            f.write("un\ndeux\n")
        self.assertEqual([l.strip() for l in self.m._secu_lignes_gz(str(p))], ["un", "deux"])

    def test_les_totaux_avancent_sans_double_compte(self):
        log = self.tmp / "site.access.log"
        ligne = '203.0.113.9 - - [31/Oct/2026:10:00:00 +0100] "GET /.env HTTP/1.1" 404 10 "-" "curl/8"\n'
        maison = '192.168.0.4 - - [31/Oct/2026:10:00:05 +0100] "GET /.env HTTP/1.1" 404 10 "-" "curl/8"\n'
        log.write_text(ligne + maison, encoding="utf-8")
        self.m._journaux_acces = lambda: {"site.test": str(log)}

        def total():
            conn = self.m.get_conn()
            r = conn.execute("SELECT COALESCE(SUM(requetes),0), COALESCE(SUM(sondes),0) FROM secu_jour").fetchone()
            conn.close()
            return tuple(r)
        self.m.collect_securite_historique()
        self.assertEqual(total(), (1, 1))                     # la ligne du réseau de la maison n'est pas comptée
        self.m.collect_securite_historique()
        self.assertEqual(total(), (1, 1))                     # relu : rien n'est recompté
        with open(log, "a", encoding="utf-8") as f:
            f.write(ligne)
        self.m.collect_securite_historique()
        self.assertEqual(total(), (2, 2))                     # seule la ligne nouvelle s'ajoute


class Box(Base):
    """La box est simulée par un faux urlopen ; la redirection 22 apparaît, disparaît, puis revient."""
    def lancer(self, redirections):
        """Un relevé de la box ; `redirections` : liste, ou None quand la box ne répond pas à cette question."""
        def faux(req, timeout=0):
            chemin = req.full_url.split("/api/v1", 1)[1]
            if chemin == "/login/":
                return Reponse({"success": True, "result": {"challenge": "c"}})
            if chemin == "/login/session/":
                return Reponse({"success": True, "result": {"session_token": "S"}})
            if chemin == "/fw/redir/":
                return Reponse({"success": redirections is not None, "result": redirections})
            if chemin in ("/vpn/", "/upnpigd/redir/", "/lan/browser/pub/", "/wifi/bss/"):
                return Reponse({"success": True, "result": []})
            return Reponse({"success": True, "result": {}})
        jeton = self.tmp / "freebox.token"
        jeton.write_text(json.dumps({"box": "http://box.test", "base": "/api/v1", "app_id": "a", "app_token": "t"}), encoding="utf-8")
        self.m._BOX_JETON = str(jeton)
        with mock.patch.object(urllib.request, "urlopen", faux):
            return {x["cle"]: x["valeur"] for x in self.m.collect_box()}

    def test_une_redirection_rouverte_alerte_de_nouveau(self):
        r22 = [{"enabled": True, "ip_proto": "tcp", "wan_port_start": 22, "wan_port_end": 22,
                "lan_ip": "192.168.0.2", "lan_port": 22, "comment": "ssh"}]
        mesures = self.lancer(r22)
        self.assertNotIn("NOUVELLE", mesures["box.redirection.tcp_22"])       # la première prise de connaissance n'alerte pas
        self.assertNotIn("NOUVELLE", self.lancer(r22)["box.redirection.tcp_22"])
        self.assertIn("non lues", self.lancer(None)["box.redirections"])      # la box muette n'est pas « aucune redirection »
        self.assertIn("aucune", self.lancer([])["box.redirections"])          # la liste est vide : la redirection est oubliée
        self.assertIn("NOUVELLE", self.lancer(r22)["box.redirection.tcp_22"])  # sa réouverture alerte


class RelecturesDeFond(Base):
    """Défauts trouvés à la seconde lecture du module."""
    def test_inactive_n_est_pas_active(self):
        sorties = {"named -v": "BIND 9.18.1", "systemctl is-active bind9": "inactive", "systemctl is-active pdns": "active"}
        with mock.patch.object(self.m.Path, "exists", return_value=True), \
                mock.patch.object(self.m, "run_cmd", side_effect=lambda cmd, *a, **k: sorties[cmd]):
            serveurs, _ = self.m.collect_dns_servers()
        etat = {x["server_type"]: x["running"] for x in serveurs}
        self.assertEqual(etat, {"bind": 0, "powerdns": 1})        # « inactive » contenait « active »

    def test_wg_absent_ou_refuse_n_est_pas_un_tunnel(self):
        with mock.patch.object(self.m, "_qui", return_value=""), mock.patch.object(self.m, "run_json", return_value={}):
            self.assertEqual(self.m.collect_vpn_connections(), [])
        with mock.patch.object(self.m, "_qui", side_effect=lambda n: "/usr/bin/wg" if n == "wg" else ""), \
                mock.patch.object(self.m, "run_json", return_value={}):
            refus = (1, "", "Unable to access interface: Operation not permitted")
            with mock.patch.object(self.m, "run_cmd_ex", return_value=refus):
                self.assertEqual(self.m.collect_vpn_connections(), [])
            actif = (0, "interface: wg0\n  public key: x", "")
            with mock.patch.object(self.m, "run_cmd_ex", return_value=actif):
                self.assertEqual([v["type"] for v in self.m.collect_vpn_connections()], ["wireguard"])

    def test_chaque_cle_ssh_a_options_a_sa_propre_empreinte(self):
        import pathlib
        home = self.tmp / "home"
        (home / ".ssh").mkdir(parents=True)
        lignes = [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIsimple moi@pc",
            'command="/usr/bin/rsync --server",no-pty ssh-rsa AAAAB3NzaC1yc2EAAAAbackup1 sauvegarde1',
            'from="10.0.0.1",no-port-forwarding ssh-rsa AAAAB3NzaC1yc2EAAAAbackup2 sauvegarde2',
            "sk-ssh-ed25519@openssh.com AAAAGnNrLXNzaC1lZDI1NTE5QG9wZW5zc2guY29t cle-usb",
            "pas une cle",
        ]
        (home / ".ssh" / "authorized_keys").write_text("\n".join(lignes) + "\n", encoding="utf-8")
        vrai = pathlib.Path.read_text

        def faux(self_, *a, **k):
            if str(self_).replace("\\", "/") == "/etc/passwd":
                return "root:x:0:0:root:home:/bin/sh\n"          # un dossier RELATIF : pas de « : » de lecteur Windows dans la ligne
            return vrai(self_, *a, **k)
        ancien = os.getcwd()
        os.chdir(self.tmp)
        try:
            with mock.patch.object(pathlib.Path, "read_text", faux):
                cles = self.m.collect_ssh_authorized_keys()
        finally:
            os.chdir(ancien)
        self.assertEqual(len(cles), 4)
        self.assertEqual(len({c["key_hash"] for c in cles}), 4)      # avant : les deux clés à options n'en faisaient qu'une
        self.assertEqual(sorted(c["key_type"] for c in cles), ["sk-ssh-ed25519@openssh.com", "ssh-ed25519", "ssh-rsa", "ssh-rsa"])
        self.assertEqual(sorted(c["comment"] for c in cles), ["cle-usb", "moi@pc", "sauvegarde1", "sauvegarde2"])

    def test_le_journal_des_changements_est_purge(self):
        from datetime import datetime, timedelta
        vieux = (datetime.now() - timedelta(days=200)).isoformat()
        recent = (datetime.now() - timedelta(days=2)).isoformat()
        conn = self.m.get_conn()
        for ts in (vieux, recent):
            conn.execute("INSERT INTO changelog (ts, entity_type, entity_name, change_type, severity) VALUES (?,?,?,?,?)",
                         (ts, "t", ts, "added", "info"))
            conn.execute("INSERT INTO correlations (ts, entite, alerte, causes) VALUES (?,?,?,?)", (ts, ts, "a", "[]"))
        conn.commit()
        conn.close()
        self.m.run_retention_vacuum()
        conn = self.m.get_conn()
        self.assertEqual([r[0] for r in conn.execute("SELECT entity_name FROM changelog")], [recent])
        self.assertEqual([r[0] for r in conn.execute("SELECT entite FROM correlations")], [recent])
        conn.close()

    def test_les_secrets_d_une_configuration_ne_sont_pas_gardes(self):
        texte = "[client]\npassword = hunter2\nuser=x\nsecret_key: abc123\nport=3306\n"
        masque = self.m._derive_masque(texte)
        self.assertNotIn("hunter2", masque)
        self.assertNotIn("abc123", masque)
        self.assertIn("user=x", masque)
        self.assertIn("port=3306", masque)
        self.assertEqual(masque, self.m._derive_masque(texte))                                       # stable : pas de fausse dérive
        self.assertNotEqual(masque, self.m._derive_masque(texte.replace("hunter2", "hunter3")))       # un changement reste visible
        p = self.tmp / "my.cnf"
        p.write_text(texte, encoding="utf-8")
        self.assertNotIn("hunter2", self.m._derive_etat(str(p)))

    def test_un_nom_de_site_n_est_jamais_un_chemin(self):
        with mock.patch.object(self.m, "run_cmd") as run, mock.patch.object(self.m.Path, "exists", return_value=False):
            certs = self.m._fp_certs(["../../etc/passwd", "a/b", ".cache", "ok.exemple.fr"])
        self.assertEqual(certs, {"../../etc/passwd": None, "a/b": None, ".cache": None, "ok.exemple.fr": None})
        run.assert_not_called()


class CapacitesDuModule(Base):
    """Les lectures du module (CN_module.py) quand le collecteur ne répond pas."""
    def _brancher(self):
        spec = importlib.util.spec_from_file_location("sensorium_module_garanties", DOSSIER / "CN_module.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.SOCKET = str(self.tmp / "absent.sock")
        implementees = {}
        ctx = mock.MagicMock()
        ctx.implementer.side_effect = lambda nom, fn: implementees.__setitem__(nom, fn)
        mod.brancher(ctx)
        return mod, implementees, ctx

    def test_une_source_muette_ne_pose_ni_zero_ni_erreur(self):
        mod, impl, ctx = self._brancher()
        r = impl["metriques"](ctx)                           # pas de collecteur : socket absent, ou pas de socket Unix du tout
        self.assertIs(r.get("muet"), True)
        self.assertTrue(r.get("erreur"))
        self.assertNotIn("cpu", r)                           # aucune mesure inventée

    def test_une_source_vivante_rend_ses_mesures(self):
        mod, impl, ctx = self._brancher()
        with mock.patch.object(mod, "json_de", return_value={"cpu": 12.3, "top_processes": []}):
            self.assertEqual(impl["metriques"](ctx), {"cpu": 12.3, "top_processes": []})


class PointsEtChemins(Base):
    def test_un_nom_de_point_n_est_jamais_un_chemin(self):
        import CN_points_sensorium as ps
        with self.assertRaises(ValueError):
            ps._reference_directe("../../noyau/CN_points", {})

    def test_la_banniere_ne_se_lit_que_sur_la_boucle_locale(self):
        self.m._BANNIERE_HOTE = "192.0.2.1"
        self.assertTrue(self.m._banniere(25, False).startswith("!hôte refusé"))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : les bancs des garanties du démon du Sensorium.
# EC : néant.
# LIEN : modules/sensorium/CN_sensorium.py, modules/sensorium/CN_points_sensorium.py, tests/CN_test_sensorium_points.py.
