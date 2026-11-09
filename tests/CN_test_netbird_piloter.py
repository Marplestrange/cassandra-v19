# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la commande root `piloter` du module netbird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #e91f20
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la commande root `piloter` du module netbird : ce que le courtier lance À ROOT. Ni Docker ni NetBird ici : `executer` est remplacé, chaque commande qui serait lancée est enregistrée, et l'on vérifie surtout ce qui est REFUSÉ (argum
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e91f20 ▼▼▼
"""Bancs de la commande root `piloter` du module netbird : ce que le courtier lance À ROOT. Ni Docker ni NetBird ici : `executer` est remplacé, chaque commande qui serait lancée est
enregistrée, et l'on vérifie surtout ce qui est REFUSÉ (arguments hors table, conteneur d'un autre service, clé en ligne de commande)."""
import importlib.machinery
import importlib.util
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
CLE = "ABCDEF12-3456-7890-ABCD-EF1234567890"


def charger():
    chemin = str(RACINE / "modules" / "netbird" / "commandes" / "CN_piloter")
    l = importlib.machinery.SourceFileLoader("piloter_banc", chemin)
    s = importlib.util.spec_from_loader("piloter_banc", l)
    m = importlib.util.module_from_spec(s)
    l.exec_module(m)
    return m


class Monde(unittest.TestCase):
    def setUp(self):
        self.p = charger()
        self.cmds, self.envs, self.entrees = [], [], []
        self.conteneurs = {}                                   # nom -> (image, état)
        self.sorties = {}                                      # (début de la commande) -> (code, sortie)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p.RUN = str(Path(self.tmp.name) / "run")
        self.p.executer = self.faux
        self.natif = True                                        # le paquet `netbird` est installé sur la machine
        self.p.shutil = types.SimpleNamespace(which=lambda x: ("/usr/bin/" + x) if (x != "netbird" or self.natif) else None)

    def faux(self, commande, input=None, capture_output=True, text=True, timeout=0, env=None):
        self.cmds.append(list(commande))
        self.envs.append(env or {})
        self.entrees.append(input)
        if commande[:2] == ["docker", "inspect"]:
            c = commande[-1]
            if c not in self.conteneurs:
                return types.SimpleNamespace(returncode=1, stdout="", stderr="Error: No such object")
            return types.SimpleNamespace(returncode=0, stdout="%s|%s" % self.conteneurs[c], stderr="")
        for debut, (code, sortie) in self.sorties.items():
            if " ".join(commande).startswith(debut):
                return types.SimpleNamespace(returncode=code, stdout=sortie, stderr="")
        return types.SimpleNamespace(returncode=0, stdout="ok", stderr="")

    def lance(self, *argv, entree=""):
        return self.p.piloter(list(argv), entree)

    def lances(self):
        return [c for c in self.cmds if c[:2] != ["docker", "inspect"]]


class Cli(Monde):
    def test_un_verbe_hors_table_est_refuse(self):
        for v in ("rm", "bash", "", "cli;id"):
            self.assertFalse(self.lance(v)["ok"], v)
        self.assertFalse(self.lances())

    def test_une_sous_commande_valide_est_lancee_sans_shell(self):
        r = self.lance("cli", "natif", "netbird", "--", "status", "--json")
        self.assertTrue(r["ok"])
        self.assertEqual(self.lances(), [["netbird", "status", "--json"]])

    def test_ce_qui_sort_de_la_table_est_refuse(self):
        for args in (["status", "--json; id"], ["status", "--bizarre"], ["up", "--setup-key=" + CLE], ["up", "--management-url=http://x;rm -rf /"], ["up", "--management-url=file:///etc/passwd"],
                     ["up", "--hostname=mauvais nom"], ["down", "extra"], ["service", "install"], ["networks"], ["networks", "select"], ["networks", "frobnicate"], ["networks", "list", "x"],
                     ["networks", "select", "a;b"], ["ssh", "root@x"], ["debug"], [], ["version", "-x"]):
            r = self.lance("cli", "natif", "netbird", "--", *args)
            self.assertFalse(r["ok"], args)
        self.assertFalse(self.lances(), "rien n'est lancé quand l'argument est refusé")

    def test_un_nom_de_conteneur_illisible_est_refuse(self):
        for c in ("a b", "../x", "-rm", "x;id", "", "x" * 80):
            self.assertFalse(self.lance("cli", "docker", c, "--", "status")["ok"], c)
        self.assertFalse(self.lances())

    def test_options_et_reseaux_valides(self):
        self.assertTrue(self.lance("cli", "natif", "netbird", "--", "up", "--no-browser", "--allow-server-ssh", "--management-url=https://netbird.exemple.fr:443", "--hostname=argos")["ok"])
        self.assertTrue(self.lance("cli", "natif", "netbird", "--", "networks", "select", "reseau-1", "10.0.0.0/24")["ok"])
        self.assertTrue(self.lance("cli", "natif", "netbird", "--", "networks", "list")["ok"])


class Docker(Monde):
    def setUp(self):
        super().setUp()
        self.natif = False                                       # Docker seul : le cas où l'on installe le conteneur

    def test_un_seul_client_par_machine_le_natif_interdit_le_conteneur(self):
        self.natif = True
        r = self.lance("docker_installer", "netbird", "latest")
        self.assertFalse(r["ok"])
        self.assertIn("déjà installé", r["erreur"])
        self.assertIn("wt0", r["erreur"])
        self.assertFalse(self.lances(), "aucun `docker run`")

    def test_un_seul_client_par_machine_un_autre_conteneur_netbird_l_interdit_aussi(self):
        self.sorties["docker ps"] = (0, "nb-ancien|netbirdio/netbird:latest\nredis|redis:7\nnetbird|netbirdio/netbird:0.30")
        r = self.lance("docker_installer", "netbird", "latest")
        self.assertFalse(r["ok"])
        self.assertIn("nb-ancien", r["erreur"])
        self.assertFalse([c for c in self.lances() if c[:2] == ["docker", "run"]])

    def test_les_conteneurs_des_autres_services_ne_genent_pas(self):
        self.sorties["docker ps"] = (0, "redis|redis:7\nvaultwarden|vaultwarden/server:latest")
        self.assertTrue(self.lance("docker_installer", "netbird", "latest")["ok"])
    def test_le_conteneur_d_un_autre_service_n_est_jamais_pilote_ni_retire(self):
        self.conteneurs["vaultwarden"] = ("vaultwarden/server:latest", "running")
        self.conteneurs["faux"] = ("evilnetbirdio/netbird:1", "running")
        for c in ("vaultwarden", "faux"):
            for verbe in (("cli", "docker", c, "--", "status"), ("docker_retirer", c), ("sso", "docker", c), ("sso_annuler", "docker", c)):
                r = self.lance(*verbe)
                self.assertFalse(r["ok"], (c, verbe))
                self.assertIn("pas un conteneur NetBird", r["erreur"])
        self.assertFalse(self.lances(), "aucun `docker exec` ni `docker rm` : rien n'a été touché")

    def test_le_client_dans_le_conteneur(self):
        self.conteneurs["netbird"] = ("netbirdio/netbird:latest", "running")
        self.assertTrue(self.lance("cli", "docker", "netbird", "--", "status", "--json")["ok"])
        self.assertEqual(self.lances(), [["docker", "exec", "netbird", "netbird", "status", "--json"]])

    def test_la_cle_passe_par_l_environnement_jamais_par_la_ligne_de_commande(self):
        self.conteneurs["netbird"] = ("netbirdio/netbird:latest", "running")
        self.assertTrue(self.lance("cli", "docker", "netbird", "--", "up", entree=CLE + "\n")["ok"])
        cmd, env = self.lances()[0], self.envs[-1]
        self.assertEqual(cmd, ["docker", "exec", "-e", "NB_SETUP_KEY", "netbird", "netbird", "up"])
        self.assertTrue(all(CLE not in x for x in cmd), "la clé n'est visible ni dans /proc ni dans `docker ps`")
        self.assertEqual(env["NB_SETUP_KEY"], CLE)

    def test_une_cle_mal_formee_est_refusee_avant_tout(self):
        self.conteneurs["netbird"] = ("netbirdio/netbird:latest", "running")
        for cle in ("court", "x" * 300, "avec espace dedans 1234567890", "a;b;c;d;e;f;g;h;i;j;k;l;m"):
            self.assertFalse(self.lance("cli", "docker", "netbird", "--", "up", entree=cle)["ok"], cle[:20])
        self.assertFalse(self.lances())

    def test_installer_cree_le_conteneur_officiel_avec_ce_qu_il_lui_faut(self):
        r = self.lance("docker_installer", "netbird", "0.40.0", "--management-url=https://netbird.exemple.fr:443", "--hostname=argos", entree=CLE)
        self.assertTrue(r["ok"], r)
        cmd = self.commande_run()
        for attendu in (["docker", "run", "-d"], ["--name", "netbird"], ["--hostname", "argos"], ["--restart", "unless-stopped"], ["--network", "host"], ["--device", "/dev/net/tun"],
                        ["-v", "netbird-donnees:/var/lib/netbird"], ["-e", "NB_SETUP_KEY"], ["-e", "NB_MANAGEMENT_URL=https://netbird.exemple.fr:443"]):
            self.assertTrue(any(cmd[i:i + len(attendu)] == attendu for i in range(len(cmd))), attendu)
        for cap in ("--cap-add=NET_ADMIN", "--cap-add=SYS_ADMIN", "--cap-add=SYS_RESOURCE"):
            self.assertIn(cap, cmd)
        self.assertEqual(cmd[-1], "netbirdio/netbird:0.40.0")
        self.assertTrue(all(CLE not in x for x in cmd))
        self.assertEqual(self.envs[-1]["NB_SETUP_KEY"], CLE)

    def test_installer_sans_cle_ne_met_aucune_cle(self):
        self.assertTrue(self.lance("docker_installer", "netbird", "latest")["ok"])
        self.assertNotIn("NB_SETUP_KEY", self.commande_run())

    def test_installer_refuse_ce_qui_est_suspect_ou_deja_la(self):
        self.conteneurs["existe"] = ("netbirdio/netbird:latest", "running")
        for argv, entree in ((("docker_installer", "existe", "latest"), ""), (("docker_installer", "netbird", "latest;id"), ""), (("docker_installer", "netbird", "latest", "--management-url=ftp://x"), ""),
                             (("docker_installer", "netbird", "latest", "--hostname=a b"), ""), (("docker_installer", "netbird", "latest", "--privileged=true"), ""),
                             (("docker_installer", "netbird", "latest", "--device=/dev/sda"), ""), (("docker_installer", "netbird", "latest"), "trop court"), (("docker_installer", "netbird"), "")):
            self.assertFalse(self.lance(*argv, entree=entree)["ok"], argv)
        self.assertFalse(self.lances(), "aucun `docker run`")

    def test_retirer_garde_le_volume_sauf_purge(self):
        self.conteneurs["netbird"] = ("netbirdio/netbird:latest", "running")
        self.assertTrue(self.lance("docker_retirer", "netbird")["ok"])
        self.assertEqual(self.lances(), [["docker", "rm", "-f", "netbird"]])
        self.cmds.clear()
        self.assertTrue(self.lance("docker_retirer", "netbird", "purger")["ok"])
        self.assertEqual(self.lances(), [["docker", "rm", "-f", "netbird"], ["docker", "volume", "rm", "netbird-donnees"]])
        self.assertFalse(self.lance("docker_retirer", "netbird", "tout")["ok"])

    def commande_run(self):
        """La commande `docker run` lancée (les autres, comme `docker ps` ou `docker inspect`, sont des vérifications)."""
        return [c for c in self.lances() if c[:2] == ["docker", "run"]][0]

    def test_etat_dit_ce_qui_existe(self):
        self.natif = True
        self.assertEqual(self.lance("etat", "netbird")["conteneur"], "absent")
        self.conteneurs["netbird"] = ("netbirdio/netbird:latest", "exited")
        self.assertEqual(self.lance("etat", "netbird")["conteneur"], "arrete")
        self.conteneurs["netbird"] = ("netbirdio/netbird:latest", "running")
        r = self.lance("etat", "netbird")
        self.assertEqual((r["conteneur"], r["docker"], r["natif"]), ("en_marche", True, True))
        self.conteneurs["netbird"] = ("redis:7", "running")
        self.assertEqual(self.lance("etat", "netbird")["conteneur"], "autre")

    def test_sans_docker_les_verbes_docker_le_disent(self):
        self.p.shutil = types.SimpleNamespace(which=lambda x: None)
        for argv in (("docker_installer", "netbird", "latest"), ("cli", "docker", "netbird", "--", "status"), ("docker_retirer", "netbird")):
            r = self.lance(*argv)
            self.assertFalse(r["ok"])
            self.assertIn("Docker n'est pas installé", r["erreur"])


class Sso(Monde):
    def faux_popen(self, lien="Please do the SSO login in your browser. Use this URL: https://login.netbird.io/device?user_code=ABCD-EFGH"):
        monde = self

        class P:
            def __init__(self, cmd, stdin=None, stdout=None, stderr=None, start_new_session=False):
                monde.cmds.append(list(cmd))
                if lien:
                    stdout.write(lien + "\n")
                    stdout.flush()
                self.pid, self.returncode = 4242, None

            def poll(self):
                return self.returncode
        return P

    def test_le_lien_d_identification_est_rendu_et_l_attente_continue(self):
        self.conteneurs["netbird"] = ("netbirdio/netbird:latest", "running")
        with mock.patch.object(self.p.subprocess, "Popen", self.faux_popen()):
            r = self.lance("sso", "docker", "netbird", "--hostname=argos")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["lien"], "https://login.netbird.io/device?user_code=ABCD-EFGH")
        self.assertEqual(self.lances(), [["docker", "exec", "netbird", "netbird", "up", "--no-browser", "--hostname=argos"]])

    def test_sans_lien_dans_le_delai_l_erreur_dit_ce_que_le_client_a_dit(self):
        self.p.ATTENTE_LIEN = 1
        with mock.patch.object(self.p.subprocess, "Popen", self.faux_popen(lien="")):
            r = self.lance("sso", "natif", "netbird")
        self.assertFalse(r["ok"])
        self.assertIn("pas donné de lien", r["erreur"])

    def test_annuler_abandonne_l_attente_et_coupe(self):
        self.conteneurs["netbird"] = ("netbirdio/netbird:latest", "running")
        os.makedirs(self.p.RUN)
        Path(self.p.RUN, "sso.pid").write_text("4242")
        tues = []
        with mock.patch.object(os, "getpgid", create=True, return_value=4242), mock.patch.object(os, "killpg", create=True, side_effect=lambda g, s: tues.append(g)):
            r = self.lance("sso_annuler", "docker", "netbird")
        self.assertTrue(r["ok"])
        self.assertEqual(tues, [4242])
        self.assertEqual(self.lances(), [["docker", "exec", "netbird", "netbird", "down"]])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : charger, Monde, Cli, Docker, Sso
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
