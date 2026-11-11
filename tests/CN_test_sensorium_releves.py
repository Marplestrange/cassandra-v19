# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : test_sensorium_releves.py
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #d05ffd
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : test_sensorium_releves.py
# MÉTHODE    : charge CN_releves_machine.py seul et lui donne des sorties de commandes fictives (exemple.test) ; aucune machine, aucun réseau
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d05ffd ▼▼▼
import importlib.util
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("sensorium_releves_machine", RACINE / "modules" / "sensorium" / "CN_releves_machine.py")
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)

INSPECTS = [
    {"Id": "8d8b6094815a" + "0" * 52, "Name": "/recherche", "Image": "sha256:aaa", "RestartCount": 0,
     "State": {"Status": "running", "Running": True, "StartedAt": "2026-11-02T05:25:31.967664066Z"},
     "HostConfig": {"NetworkMode": "default", "RestartPolicy": {"Name": "unless-stopped"}},
     "Config": {"Env": ["SECRET_KEY=ne-doit-jamais-sortir"], "Labels": {}},
     "NetworkSettings": {"Ports": {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8890"}], "9000/tcp": None}, "Networks": {"bridge": {"IPAddress": "172.17.0.3"}}},
     "Mounts": [{"Type": "bind", "Source": "/opt/recherche", "Destination": "/etc/searxng"}, {"Type": "volume", "Name": "5" * 64, "Destination": "/var/cache/searxng"}]},
    {"Id": "f0c94693855c" + "1" * 52, "Name": "/reseau-serveur", "Image": "sha256:bbb", "RestartCount": 2,
     "State": {"Status": "running", "Running": True, "StartedAt": "2026-11-10T02:19:53Z", "Health": {"Status": "healthy"}},
     "HostConfig": {"NetworkMode": "reseau_defaut", "RestartPolicy": {"Name": "always"}},
     "Config": {"Labels": {"com.docker.compose.project": "reseau", "com.docker.compose.project.config_files": "/opt/reseau/docker-compose.yml", "com.docker.compose.service": "serveur"}},
     "NetworkSettings": {"Ports": {"3478/udp": [{"HostIp": "0.0.0.0", "HostPort": "3478"}, {"HostIp": "::", "HostPort": "3478"}], "80/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8081"}]},
                         "Networks": {"reseau_defaut": {"IPAddress": "172.21.0.3"}}}, "Mounts": []},
]

NGINX = """# configuration file /etc/nginx/nginx.conf:
http {
    include /etc/nginx/conf.d/*.conf;
    include /etc/nginx/sites/*/*.conf;
}
# configuration file /etc/nginx/conf.d/panneau.conf:
server {
    server_name panneau.exemple.test;
    listen 203.0.113.52:443 ssl;
    location / {
        proxy_pass https://127.0.0.1:8888;   # le panneau
    }
}
server {
    server_name _;
    listen 203.0.113.52:80 default_server;
    location / { return 444; }
}
# configuration file /etc/nginx/sites/client/reseau.exemple.test.conf:
upstream reseau.exemple.test2 {
        server 127.0.0.1:8080;
}
server {
    server_name reseau.exemple.test ;
    listen 203.0.113.52:443 ssl;
    include /etc/nginx/sites/client/reseau.exemple.test.includes;
    location / {
        proxy_pass http://reseau.exemple.test2;
    }
    location ~* ^.+\\.(jpg|png|css)$ {
        try_files $uri @fallback;
    }
    location @fallback {
        proxy_pass http://reseau.exemple.test2;
    }
}
server {
    server_name reseau.exemple.test ;
    listen 203.0.113.52:80;
    return 301 https://$host$request_uri;
}
# configuration file /etc/nginx/sites/client/reseau.exemple.test.includes:
location ~ ^/(api|oauth2)/ {
    proxy_pass http://127.0.0.1:8081;
}
location ~ ^/signal\\.Echange/ {
    grpc_pass grpc://127.0.0.1:8081;
}
location /variable {
    proxy_pass http://$amont;
}
"""

PS = """cassandra                        41822 21.2 100748    328 /usr/bin/python3 CN_main.py demarrer
root                                 1  1.0  10456 995850 /sbin/init
mysql                             8364  0.8 175964 995752 /usr/sbin/mysqld
root                            372202  0.4 190660 814008 searxng worker-1
clamav                          418918  0.0 1001032 813911 /usr/sbin/clamd --foreground=true
root                             60211 55.0   3000      0 ps -eo user:32,pid,pcpu,rss,etimes,args --no-headers
root                                17  0.0      0 995850 [kworker/1:1-events]
"""
CGROUPS = {41822: "0::/system.slice/cassandra-noyau.service\n", 1: "0::/init.scope\n", 8364: "0::/system.slice/mysql.service\n",
           372202: "0::/system.slice/docker-8d8b6094815a%s.scope\n" % ("0" * 52), 418918: "0::/system.slice/clamav-daemon.service\n", 17: "0::/\n"}


class Conteneurs(unittest.TestCase):
    def test_la_fiche_dit_les_ports_le_reseau_et_ne_garde_aucun_secret(self):
        f = R.conteneurs(INSPECTS, R.images([{"Id": "sha256:aaa", "Size": 265611353, "Created": "2026-11-01T22:57:37.87Z"}]), {"sha256:aaa": "Void Linux"})
        r = f["recherche"]
        self.assertEqual(r["ports"], [["127.0.0.1", 8890, 8080, "tcp", "machine"]])                # un port non publié (9000) n'est pas un port ouvert
        self.assertEqual((r["reseau"], r["ip"], r["politique"], r["sante"], r["redemarrages"]), ("bridge", "172.17.0.3", "unless-stopped", "", 0))
        self.assertEqual(r["volumes"], [["bind", "/opt/recherche", "/etc/searxng"], ["volume", "volume anonyme", "/var/cache/searxng"]])
        self.assertEqual((r["taille_mo"], r["created"], r["distribution"], r["ident"]), (253, "2026-11-01T22:57:37", "Void Linux", "8d8b6094815a"))
        self.assertNotIn("ne-doit-jamais-sortir", repr(f))
        s = f["reseau-serveur"]
        self.assertEqual(s["ports"], [["0.0.0.0", 3478, 3478, "udp", "public"], ["127.0.0.1", 8081, 80, "tcp", "machine"]])   # IPv4 et IPv6 : une seule publication
        self.assertEqual((s["sante"], s["redemarrages"], s["compose"]), ("healthy", 2, "/opt/reseau/docker-compose.yml · service serveur"))

    def test_la_portee_d_une_adresse(self):
        self.assertEqual([R.portee(a) for a in ("127.0.0.1", "::1", "0.0.0.0", "::", "", "100.64.0.11", "192.168.1.4", "203.0.113.52")],
                         ["machine", "machine", "public", "public", "public", "prive", "prive", "public"])

    def test_la_distribution(self):
        self.assertEqual(R.distribution('NAME="Alpine Linux"\nPRETTY_NAME="Alpine Linux v3.24"\n'), "Alpine Linux v3.24")
        self.assertEqual(R.distribution("OCI runtime exec failed: exec: \"cat\": executable file not found"), "")


class MisesAJour(unittest.TestCase):
    def test_la_reference_d_une_image(self):
        self.assertEqual(R.reference_image("searxng/searxng"), {"registre": "registry-1.docker.io", "depot": "searxng/searxng", "etiquette": "latest"})
        self.assertEqual(R.reference_image("nginx:1.27"), {"registre": "registry-1.docker.io", "depot": "library/nginx", "etiquette": "1.27"})
        self.assertEqual(R.reference_image("ghcr.io/exemple/outil:v2"), {"registre": "ghcr.io", "depot": "exemple/outil", "etiquette": "v2"})
        self.assertEqual(R.reference_image("registre.exemple.test:5000/a/b"), {"registre": "registre.exemple.test:5000", "depot": "a/b", "etiquette": "latest"})
        for epinglee in ("exemple/coffre@sha256:" + "c" * 64, "sha256:" + "c" * 64, "c" * 12, "", "Exemple/Majuscules", "a/b:étiquette illisible"):
            self.assertIsNone(R.reference_image(epinglee), epinglee)

    def test_le_defi_d_un_registre_et_le_verdict(self):
        self.assertEqual(R.defi_bearer('Bearer realm="https://auth.exemple.test/token",service="registre.exemple.test",scope="repository:a/b:pull"'),
                         {"realm": "https://auth.exemple.test/token", "service": "registre.exemple.test", "scope": "repository:a/b:pull"})
        self.assertEqual(R.defi_bearer('Basic realm="x"'), {})
        self.assertEqual([R.etat_maj(d, l) for d, l in (("sha256:a", ["sha256:a"]), ("sha256:b", ["sha256:a"]), ("", ["sha256:a"]), ("sha256:b", []))], ["a_jour", "disponible", "", ""])
        im = R.images([{"Id": "sha256:aaa", "Size": 1048576, "RepoDigests": ["exemple/coffre@sha256:un", "miroir.exemple.test/coffre@sha256:deux"]}])
        self.assertEqual(im["sha256:aaa"]["empreintes"], ["sha256:deux", "sha256:un"])

    def test_le_service_d_un_processus_tue_faute_de_memoire(self):
        lignes = ["[Wed Nov 11 03:12:44 2026] oom-kill:constraint=CONSTRAINT_NONE,nodemask=(null),cpuset=/,mems_allowed=0,global_oom,task_memcg=/system.slice/php8.3-fpm.service,task=php-fpm,pid=52110,uid=33",
                  "[Wed Nov 11 03:15:02 2026] oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),cpuset=x,mems_allowed=0,oom_memcg=/docker/abc,task_memcg=/docker/abc,task=node,pid=777,uid=0"]
        self.assertEqual(R.oom_services(lignes), {"52110": "php8.3-fpm", "777": ""})


class Proxys(unittest.TestCase):
    def test_les_renvois_suivent_les_inclusions_et_les_amonts(self):
        lignes = R.proxys_nginx(NGINX)
        self.assertEqual([(l["nom"], l["chemin"], l["vers"], l["genre"], l["tls"]) for l in lignes], [
            ("panneau.exemple.test", "/", "127.0.0.1:8888", "https", 1),
            ("reseau.exemple.test", "~ ^/(api|oauth2)/", "127.0.0.1:8081", "http", 1),              # rangé dans un fichier inclus par le bloc du site
            ("reseau.exemple.test", "~ ^/signal\\.Echange/", "127.0.0.1:8081", "grpc", 1),
            ("reseau.exemple.test", "/", "127.0.0.1:8080", "http", 1),                                # l'amont (upstream) est résolu ; le repli @fallback ne le redit pas
        ])
        self.assertEqual({l["port"] for l in lignes}, {8888, 8081, 8080})

    def test_une_sortie_vide_ou_sans_renvoi_ne_rend_rien(self):
        self.assertEqual(R.proxys_nginx(""), [])
        self.assertEqual(R.proxys_nginx("# configuration file /etc/nginx/nginx.conf:\nhttp { server { server_name site.exemple.test; root /var/www; } }\n"), [])


class Processus(unittest.TestCase):
    def test_les_plus_gourmands_avec_leur_porteur(self):
        l = R.processus(PS, CGROUPS.get, {"8d8b6094815a" + "0" * 52: "recherche"}, limite=3)
        self.assertEqual([p["pid"] for p in l], [41822, 1, 8364, 372202, 418918])                    # les 3 du processeur, puis ceux que la mémoire ajoute
        self.assertFalse([p for p in l if p["command"].startswith("ps -eo")])                       # la sonde ne se compte pas
        par = {p["pid"]: p for p in l}
        self.assertEqual((par[41822]["genre"], par[41822]["a_qui"], par[41822]["mem_mb"], par[41822]["age_s"]), ("service", "cassandra-noyau", 98.4, 328))
        self.assertEqual((par[372202]["genre"], par[372202]["a_qui"]), ("conteneur", "recherche"))
        self.assertEqual((par[1]["genre"], par[418918]["a_qui"]), ("système", "clamav-daemon"))

    def test_l_appartenance(self):
        self.assertEqual(R.appartenance("0::/user.slice/user-0.slice/session-c106.scope\n"), ("session", "0"))
        self.assertEqual(R.appartenance("0::/user.slice/user-1000.slice/user@1000.service/app.slice/x.service\n"), ("session", "1000"))
        self.assertEqual(R.appartenance("12:pids:/docker/%s\n1:name=systemd:/docker/%s\n" % ("a" * 64, "a" * 64)), ("conteneur", "a" * 12))
        self.assertEqual(R.appartenance("0::/\n"), ("noyau", ""))
        self.assertEqual(R.appartenance(""), ("noyau", ""))

    def test_la_memoire(self):
        m = R.memoire({"MemTotal": 8000000, "MemFree": 1000000, "Buffers": 200000, "Cached": 2500000, "SReclaimable": 300000, "MemAvailable": 4500000, "SwapTotal": 2000000, "SwapFree": 1900000})
        self.assertEqual((m["total_mo"], m["cache_mo"], m["libre_mo"], m["disponible_mo"], m["echange_mo"]), (7812, 2930, 977, 4395, 98))
        self.assertEqual(m["applis_mo"], 7812 - 977 - 2930)
        self.assertEqual(R.memoire({}), {})


class Services(unittest.TestCase):
    def test_les_mesures_d_une_unite(self):
        u = {"MainPID": "1629", "MemoryCurrent": "27054080", "CPUUsageNSec": "345941178000", "ActiveEnterTimestamp": "Tue 2026-11-03 18:32:06 UTC", "NRestarts": "1"}
        m = R.mesures_service(u, (345941178000 - 3_000_000_000, 100.0), 130.0)
        self.assertEqual((m["pid"], m["memoire_mo"], m["cpu_pct"], m["depuis"], m["redemarrages"]), (1629, 25.8, 10.0, "2026-11-03T18:32:06", 1))
        self.assertIsNone(R.mesures_service(u, None, 130.0)["cpu_pct"])                              # sans passe d'avant : inconnu, pas zéro
        repos = R.mesures_service({"MainPID": "0", "MemoryCurrent": "[not set]", "CPUUsageNSec": "[not set]", "ActiveEnterTimestamp": ""}, (5, 1.0), 2.0)
        self.assertEqual((repos["pid"], repos["memoire_mo"], repos["cpu_pct"], repos["depuis"]), (0, None, None, ""))


JOURNAL = """2026-11-09T08:12:01+0000 machine sshd[4101]: Accepted publickey for lea from 100.64.0.11 port 51000 ssh2: ED25519 SHA256:AAAAconnue
2026-11-10T03:31:37+0000 machine sshd[70577]: Accepted publickey for lea from 100.64.0.11 port 54356 ssh2: ED25519 SHA256:AAAAconnue
2026-11-10T04:00:00+0000 machine sshd[70999]: Accepted password for depot from 198.51.100.20 port 40000 ssh2
2026-11-10T04:00:02+0000 machine sshd[71000]: Failed password for root from 203.0.113.24 port 40001 ssh2
"""


class Sessions(unittest.TestCase):
    def setUp(self):
        self.acc = R.acceptes(JOURNAL)
        self.cles = R.cles_connues(["256 SHA256:AAAAconnue lea@portable (ED25519)\n2048 SHA256:BBBB vieille cle rsa (RSA)\n"])

    def test_le_journal_et_les_cles(self):
        self.assertEqual(len(self.acc), 3)
        self.assertEqual((self.acc[1]["quand"], self.acc[1]["user"], self.acc[1]["ip"], self.acc[1]["methode"], self.acc[1]["algo"]),
                         ("2026-11-10T03:31:37", "lea", "100.64.0.11", "publickey", "ED25519"))
        self.assertEqual(self.cles, {"SHA256:AAAAconnue": "lea@portable", "SHA256:BBBB": "vieille cle rsa"})

    def test_une_session_dit_son_terminal_son_identification_et_son_adresse(self):
        w = R.sessions_w("lea      pts/0    100.64.0.11      08:12    3:00   0.10s  0.02s htop\n")
        s = R.enrichir_sessions([{"user": "lea", "ip": "100.64.0.11", "login_time": "2026-11-10 03:31"}, {"user": "sshd", "ip": "203.0.113.24", "login_time": ""}],
                                w, self.acc, self.cles, {"203.0.113.24": 14})
        self.assertEqual((s[0]["tty"], s[0]["inactivite"], s[0]["commande"], s[0]["methode"], s[0]["cle"], s[0]["connexions_30j"], s[0]["refus_1h"]),
                         ("pts/0", "3:00", "htop", "clé", "ED25519 « lea@portable »", 2, 0))
        self.assertEqual((s[1]["tty"], s[1]["methode"], s[1]["cle"], s[1]["connexions_30j"], s[1]["refus_1h"]), ("", "", "", 0, 14))
        self.assertEqual(set(s[0]), set(s[1]))                                                       # mêmes colonnes pour toutes les lignes
        self.assertNotIn("SHA256", repr(s))                                                          # jamais l'empreinte

    def test_les_connexions_reussies_se_regroupent(self):
        c = R.connexions(self.acc, self.cles)
        self.assertEqual([(g["user"], g["ip"], g["methode"], g["nombre"], g["derniere"]) for g in c],
                         [("depot", "198.51.100.20", "mot de passe", 1, "2026-11-10T04:00:00"), ("lea", "100.64.0.11", "clé", 2, "2026-11-10T03:31:37")])
        self.assertEqual(c[1]["premiere"], "2026-11-09T08:12:01")


class Fiche(unittest.TestCase):
    def test_le_processeur(self):
        info = "".join("processor\t: %d\nmodel name\t: Processeur Exemple 7\ncpu MHz\t\t: 2445.404\nphysical id\t: 0\ncpu cores\t: 4\n\n" % i for i in range(4))
        self.assertEqual(R.processeur(info), {"modele": "Processeur Exemple 7", "coeurs": 4, "fils": 4, "mhz": 2445})
        self.assertEqual(R.processeur(""), {"modele": "", "coeurs": 0, "fils": 0, "mhz": 0})

    def test_le_pare_feu_les_mises_a_jour_les_disques_les_versions(self):
        self.assertEqual([R.politique_entree(x) for x in ("-P INPUT DROP\n-A INPUT -i lo -j ACCEPT", "-P INPUT ACCEPT", "")], ["refuser", "accepter", ""])
        self.assertEqual(R.maj_auto('APT::Periodic::Update-Package-Lists "1";\nAPT::Periodic::Unattended-Upgrade "1";'), "automatiques, chaque jour")
        self.assertEqual(R.maj_auto('APT::Periodic::Unattended-Upgrade "0";'), "désactivées : les correctifs attendent une main")
        self.assertEqual(R.maj_auto(""), "")
        self.assertEqual(R.disques({"blockdevices": [{"name": "sda", "model": "DISQUE VIRTUEL", "size": "76.3G", "rota": False, "type": "disk"}, {"name": "sr0", "type": "rom"}]}),
                         [["sda", "DISQUE VIRTUEL", "76.3G", "sans plateaux"]])
        self.assertEqual([R.version(x) for x in ("nginx version: nginx/1.30.6", "git version 2.39.5", "Python 3.11.2", "mysql  Ver 8.0.40 for Linux", "ollama version is 0.5.1", "rien")],
                         ["1.30.6", "2.39.5", "3.11.2", "8.0.40", "0.5.1", ""])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Conteneurs, Proxys, Processus, Services, Sessions, Fiche
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/sensorium/CN_releves_machine.py ; le branchement dans le démon est éprouvé dans CN_test_sensorium_demon.py
