# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des points d'évolution du démon Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #6ed8d5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : prouve que le démon du Sensorium, seul et sans noyau, appelle ses points d'évolution ; que ses appels nourrissent le rejeu que le noyau absorbe ; et qu'une panne du service ne perd jamais une mesure.
# MÉTHODE    : charge CN_sensorium.py comme module, un dossier de données temporaire, puis appelle les fonctions façades.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=6ed8d5 ▼▼▼
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
DOSSIER = RACINE / "modules" / "sensorium"


def charger_demon(donnees):
    os.environ["CASSANDRA_DATA_DIR"] = str(donnees)
    sys.path.insert(0, str(DOSSIER))
    spec = importlib.util.spec_from_file_location("sensorium_demon_test", DOSSIER / "CN_sensorium.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class DemonEtPoints(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.donnees = self.tmp / "donnees" / "sensorium"
        self.donnees.mkdir(parents=True)
        (self.tmp / "donnees" / "ec").mkdir()
        self.m = charger_demon(self.donnees)
        import CN_points_sensorium as ps
        self.ps = ps
        ps._SVC = ps._REJEU = None
        ps._ECHEC = ""

    def test_le_score_de_sante_d_une_machine_saine_est_cent(self):
        r = self.m.compute_health_score({"cpu_pct": 10, "ram_pct": 20, "disk_pct": 30}, [], [], [], [], None, None, 0, 0)
        self.assertEqual((r["score"], r["status"]), (100, "excellent"))
        self.assertEqual(r["breakdown"], {})

    def test_le_score_de_sante_retire_des_points_par_probleme(self):
        r = self.m.compute_health_score({"cpu_pct": 99}, [{"domain": "a", "days_left": 3}], [], [], [], None, None, 1, 2)
        self.assertEqual(r["breakdown"], {"cpu": -20, "ssl": -5, "oom": -5, "failed_units": -10})
        self.assertEqual(r["score"], 60)
        self.assertEqual(r["alerts_count"], 4)

    def test_la_pente_et_la_table_de_mogwai_passent_par_leurs_points(self):
        a, r2 = self.m._pente([[i, 2 * i + 1] for i in range(8)])
        self.assertAlmostEqual(a, 2.0)
        self.assertAlmostEqual(r2, 1.0)
        self.assertEqual(list(self.m._pente([[0, 1]])), [None, 0.0])             # moins de six points : aucune pente
        lignes = self.m._mogwai_parse_table("NOM\tOWNER\tALIAS\nsite1\tbob\t\n")
        self.assertEqual(lignes, [{"nom": "site1", "owner": "bob", "alias": ""}])
        self.assertEqual(self.m._duree_txt(97200), "1 j 3 h")

    def test_le_cron_retrouve_sa_derniere_execution(self):
        runs = {("root", "/a.sh"): "2026-10-17T03:00:00", ("root", "/b.sh --x"): "2026-10-17T04:00:00"}
        self.assertEqual(self.m._cron_run_lookup(runs, "root", "/a.sh"), "2026-10-17T03:00:00")
        self.assertEqual(self.m._cron_run_lookup(runs, "root", "/b.sh"), "2026-10-17T04:00:00")
        self.assertEqual(self.m._cron_run_lookup(runs, "bob", "/a.sh"), "")

    def test_les_appels_du_demon_nourrissent_son_rejeu_et_le_noyau_les_absorbe(self):
        from noyau import CN_rejeu as R
        for v in (10, 20, 30):
            self.m.compute_health_score({"cpu_pct": v}, [], [], [], [], None, None, 0, 0)
        self.m.compute_health_score({"cpu_pct": 10}, [], [], [], [], None, None, 0, 0)
        fichier = self.donnees / "rejeu_sensorium.db"
        self.assertTrue(fichier.exists())
        noyau = R.Rejeu(self.tmp / "donnees" / "rejeu.db")
        self.assertEqual(noyau.absorber(fichier), 4)
        self.assertEqual(noyau.absorber(fichier), 0)
        s = noyau.stats("sensorium.sante")
        self.assertEqual((s["distincts"], s["appels"]), (3, 4))

    def test_une_panne_du_service_des_points_ne_perd_aucune_mesure(self):
        ps = self.ps

        def casse(_donnees):
            raise RuntimeError("le noyau n'est pas importable")
        ps._charger = casse
        r = self.m.compute_health_score({"cpu_pct": 99}, [], [], [], [], None, None, 0, 0)
        self.assertEqual(r["breakdown"], {"cpu": -20})
        self.assertIn("RuntimeError", ps._ECHEC)

    def test_une_ecriture_refusee_dans_le_stock_ne_perd_pas_non_plus_la_mesure(self):
        ps = self.ps
        self.m.compute_health_score({"cpu_pct": 1}, [], [], [], [], None, None, 0, 0)          # le service est monté
        vrai = ps._SVC.appeler

        def refuse(*a, **k):
            raise PermissionError("système de fichiers en lecture seule")
        ps._SVC.appeler = refuse
        try:
            r = self.m.compute_health_score({"cpu_pct": 99}, [], [], [], [], None, None, 0, 0)
        finally:
            ps._SVC.appeler = vrai
        self.assertEqual(r["breakdown"], {"cpu": -20})


STATS = {}


class FauxDT(__import__("datetime").datetime):
    """L'horloge figée : « maintenant » est le 17 octobre 2026 à midi, pour que les jours avant expiration d'un certificat soient les mêmes à chaque rejeu."""
    @classmethod
    def now(cls, tz=None):
        return __import__("datetime").datetime(2026, 10, 17, 12, 0, 0, 1)

    @classmethod
    def fromtimestamp(cls, t):
        return type("N", (), {"isoformat": staticmethod(lambda: "T%s" % t)})()


class FauxFichier:
    """Un système de fichiers de poche : ce que le collecteur lirait sur une machine, sans toucher la vraie."""
    def __init__(self, chemin, fs, dirs):
        self.chemin, self.fs, self.dirs = str(chemin), fs, dirs
        self.name = self.chemin.rstrip("/").split("/")[-1]

    def exists(self):
        return self.chemin in self.fs or self.chemin in self.dirs

    def is_dir(self):
        return self.chemin in self.dirs and self.chemin not in self.fs

    def read_text(self, **kw):
        v = self.fs[self.chemin]
        if isinstance(v, dict) and "__erreur__" in v:
            raise OSError(v["__erreur__"])
        if isinstance(v, list):                       # des relevés successifs d'un même fichier
            return v.pop(0) if len(v) > 1 else v[0]
        return v

    def iterdir(self):
        pref = self.chemin.rstrip("/") + "/"
        vus = []
        for k in sorted(self.dirs) + sorted(self.fs):
            if k.startswith(pref) and "/" not in k[len(pref):] and k not in vus:
                vus.append(k)
        return [FauxFichier(k, self.fs, self.dirs) for k in vus]

    def is_file(self):
        return self.chemin in self.fs

    @property
    def suffix(self):
        n = self.name
        i = n.rfind(".")
        return n[i:] if 0 < i < len(n) - 1 else ""

    def __lt__(self, autre):
        return self.chemin < autre.chemin

    def glob(self, motif):
        import fnmatch
        pref = self.chemin.rstrip("/") + "/"
        return [FauxFichier(k, self.fs, self.dirs) for k in sorted(self.fs) if k.startswith(pref) and fnmatch.fnmatch(k[len(pref):], motif)]

    def __str__(self):
        return self.chemin

    def rglob(self, motif):
        pref = self.chemin.rstrip("/") + "/"
        fin = motif.lstrip("*")
        return [FauxFichier(k, self.fs, self.dirs) for k in sorted(self.fs) if k.startswith(pref) and k.endswith(fin)]

    def stat(self):
        taille, mtime = STATS[self.chemin]
        return type("St", (), {"st_size": taille, "st_mtime": mtime})()

    @property
    def parts(self):
        return tuple(["/"] + [x for x in self.chemin.split("/") if x])

    def __truediv__(self, x):
        return FauxFichier(self.chemin.rstrip("/") + "/" + x, self.fs, self.dirs)

    @property
    def parent(self):
        return FauxFichier(self.chemin.rsplit("/", 1)[0] or "/", self.fs, self.dirs)


class Conn:
    """Une base en mémoire que le collecteur peut « fermer » sans la perdre : le banc relit ce qu'il y a écrit."""
    def __init__(self, c):
        self.c = c

    def execute(self, *a):
        return self.c.execute(*a)

    def commit(self):
        self.c.commit()

    def close(self):
        pass


class FauxOuvert:
    def __init__(self, contenu):
        self.contenu, self.pos = contenu, 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def seek(self, p):
        self.pos = p

    def read(self, n):
        return self.contenu[self.pos:self.pos + n]


class Collecteurs(unittest.TestCase):
    """Les collecteurs mail et FTP de FastPanel : les LECTURES restent dans le démon, la FORME passe par le point `fp_formes`. Les attendus viennent de l'ANCIEN code, rejoué sur les mêmes scénarios (167 scénarios : mail, FTP, comptes, bases, sauvegardes, crons, sites, sessions, ports, certificats, SMART, matériel, sites web, tâches planifiées, services, disques, PHP-FPM, paquets, instantané du serveur, processus, réseau, erreurs des journaux, exposition des ports, courriel des domaines, contrôles ; aucun écart)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.donnees = self.tmp / "donnees" / "sensorium"
        self.donnees.mkdir(parents=True)
        (self.tmp / "donnees" / "ec").mkdir()
        self.m = charger_demon(self.donnees)
        import CN_points_sensorium as ps
        ps._SVC = ps._REJEU = None
        ps._ECHEC = ""

    def jouer(self, fonction, sc):
        m = self.m
        fs, dirs = {k: (list(v) if isinstance(v, list) else v) for k, v in sc.get("fs", {}).items()}, set(sc.get("dirs", []))
        m.Path = lambda chemin: FauxFichier(chemin, fs, dirs)
        m.datetime = FauxDT
        m._fp_available = lambda: sc.get("dispo", True)
        m._mogwai = lambda args, timeout=15: (sc.get("mogwai_json", "") if "--json" in args else sc.get("mogwai", ""))
        m._cron_last_runs = lambda: {tuple(k.split("|", 1)): v for k, v in sc.get("runs", {}).items()}
        STATS.clear()
        STATS.update({k: tuple(v) for k, v in sc.get("stats", {}).items()})
        m._fp_api_get_list = lambda ep: list(sc.get("api", []))
        m._fp_sqlite_ftp = lambda: [dict(x) for x in sc.get("base_ftp", [])]
        m._fp_get_fp2_usernames = lambda: list(sc.get("users", []))
        m._fp_sqlite_users = lambda: [dict(x) for x in sc.get("base_users", [])]
        m._fp_sqlite_databases = lambda: [dict(x) for x in sc.get("base_dbs", [])]

        m.os = type("OS", (), {"uname": staticmethod(lambda: type("U", (), {"machine": "x86_64"})()), "environ": os.environ, "path": os.path, "getpid": staticmethod(os.getpid)})()
        m.time = type("T", (), {"sleep": staticmethod(lambda s: None), "time": staticmethod(time.time)})()
        m._qui = lambda nom: nom in sc.get("qui", [])
        m._sonde_http = lambda d, ip="": sc.get("http", {}).get(d, "200")

        def run_cmd(cmd, *a, **k):
            c = " ".join(cmd) if isinstance(cmd, list) else cmd
            if c.startswith("openssl x509 -in"):
                chemin = c.split("-in ", 1)[1].split(" -noout", 1)[0].strip("'")
                o = sc.get("openssl", {})
                return o.get(chemin, o.get(chemin.split("/")[-2], ""))
            for cle, val in sc.get("cmds", {}).items():
                if c.startswith(cle):
                    return val
            if c.startswith("du -sb"):
                return sc.get("du", {}).get(c.split()[2].strip("'"), "")
            return sc.get("mysql", "")
        m.run_cmd = run_cmd
        m._read_meminfo = lambda: dict(sc.get("mi", {}))
        if fonction in ("collect_controles", "collect_exposition", "collect_courriel_domaines"):
            import io
            import sqlite3
            m.time = type("T", (), {"sleep": staticmethod(lambda s: None), "time": staticmethod(lambda: 10 ** 9)})()
            m._qui = lambda nom: nom in sc.get("qui", [])

            def cmd(c, *a, **k):
                c = " ".join(c) if isinstance(c, list) else c
                if c.startswith("dig "):
                    return sc.get("dig", {}).get(c.split()[-1], "")
                if c.startswith("curl"):
                    return sc.get("curl", "")
                for cle, val in sc.get("cmds", {}).items():
                    if c.startswith(cle):
                        return val
                return ""
            m.run_cmd = cmd
            m._ip_publique = lambda: sc.get("ip_pub", "")
            m._DOMAINES_CACHE = {"t": 0, "d": None}
            db = sqlite3.connect(":memory:")
            db.execute("CREATE TABLE web_sites (domain, ssl_enabled, listen_ip)")
            db.execute("CREATE TABLE open_ports (port, protocol)")
            for d, ssl, ip in sc.get("sites", []):
                db.execute("INSERT INTO web_sites VALUES (?,?,?)", (d, ssl, ip))
            for port, proto in sc.get("ports", []):
                db.execute("INSERT INTO open_ports VALUES (?,?)", (port, proto))
            m.get_conn = lambda: Conn(db)
            m._tls_verifie = lambda dom, ip: tuple(sc.get("tls", {}).get(dom, [True, "valide"]))
            m._dns_public = lambda dom: list(sc.get("dns", {}).get(dom, []))
            m._banniere = lambda port, tls: sc.get("bannieres", {}).get(str(port), "")
            m.CASSANDRA_CONFIG = "/etc/cassandra/config.json"

            def ouvrir(chemin, mode="r", encoding=None):
                if chemin not in sc.get("fs", {}):
                    raise OSError("absent")
                return io.StringIO(sc["fs"][chemin])
            m.open = ouvrir

            class Ctx:
                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            def joindre(adresse, timeout=2):
                if sc.get("joignables", {}).get(str(adresse[1])):
                    return Ctx()
                raise OSError("refusé")
            m.socket = type("S", (), {"create_connection": staticmethod(joindre)})()
            return json.loads(json.dumps(getattr(m, fonction)()))
        if fonction == "collect_log_errors":
            import fnmatch
            import glob
            import sqlite3
            db = sqlite3.connect(":memory:")
            db.row_factory = sqlite3.Row
            db.execute("CREATE TABLE log_errors_curseur (source TEXT PRIMARY KEY, inode INTEGER, position INTEGER, curseur TEXT, maj TEXT)")
            for src, ino, pos in sc.get("curseur", []):
                db.execute("INSERT INTO log_errors_curseur VALUES (?,?,?,?,?)", (src, ino, pos, None, "x"))
            m.get_conn = lambda: Conn(db)
            m.LOG_ERREURS_JOURNALD = False          # le journal système n'est pas une mesure rejouée : seule sa forme l'est
            contenus = {k: v.encode("utf-8") for k, v in sc.get("fs", {}).items()}

            def stat(chemin):
                if chemin not in sc.get("stat", {}):
                    raise OSError("absent")
                taille, ino = sc["stat"][chemin]
                return type("St", (), {"st_size": taille, "st_ino": ino})()
            m.os = type("OS", (), dict({k: getattr(os, k) for k in dir(os)}, stat=staticmethod(stat)))()
            m.open = lambda chemin, mode="r": FauxOuvert(contenus[chemin])
            vrai_glob = glob.glob
            glob.glob = lambda motif: [k for k in sorted(contenus) if fnmatch.fnmatch(k, motif)]
            try:
                n = getattr(m, fonction)()
            finally:
                glob.glob = vrai_glob
            return json.loads(json.dumps({"n": n, "curseur": [list(r) for r in db.execute("SELECT source, inode, position FROM log_errors_curseur ORDER BY source").fetchall()],
                                          "log_errors": [list(r)[1:] for r in db.execute("SELECT * FROM log_errors ORDER BY id").fetchall()]}))
        if fonction == "collect_paquets_mouvements":
            import sqlite3
            db = sqlite3.connect(":memory:")
            db.execute("CREATE TABLE changelog (ts, entity_type, entity_name, change_type, old_value, new_value, severity)")
            db.execute("CREATE TABLE paquets_curseur (source TEXT PRIMARY KEY, inode, position)")
            for src, ino, pos in sc.get("curseur", []):
                db.execute("INSERT INTO paquets_curseur VALUES (?,?,?)", (src, ino, pos))
            m.get_conn = lambda: Conn(db)
            contenus = {k: v.encode("utf-8") for k, v in sc.get("journaux", {}).items()}

            def stat(chemin):
                if chemin not in sc.get("stat", {}):
                    raise OSError("absent")
                taille, ino = sc["stat"][chemin]
                return type("St", (), {"st_size": taille, "st_ino": ino})()
            m.os = type("OS", (), dict({k: getattr(os, k) for k in dir(os)}, stat=staticmethod(stat)))()
            m.open = lambda chemin, mode="r": FauxOuvert(contenus[chemin])
            n = getattr(m, fonction)()
            return json.loads(json.dumps({"n": n, "changelog": db.execute("SELECT * FROM changelog").fetchall(), "curseur": db.execute("SELECT * FROM paquets_curseur ORDER BY source").fetchall()}))
        return json.loads(json.dumps(getattr(m, fonction)()))

    def test_les_collecteurs_rendent_ce_que_rendait_l_ancien_code(self):
        scenarios = json.loads((Path(__file__).resolve().parent / "CN_donnees_collecteurs.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(scenarios), 20)
        for x in scenarios:
            self.assertEqual(self.jouer(x["fonction"], x["scenario"]), x["attendu"], "%s : %s" % (x["fonction"], json.dumps(x["scenario"], ensure_ascii=False)[:160]))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : les bancs du démon du Sensorium et de ses points.
# EC : néant.
# LIEN : modules/sensorium/CN_points_sensorium.py, noyau/CN_rejeu.py (absorber), modules/sensorium/CN_sensorium.py.
