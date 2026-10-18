# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des points d'évolution du démon Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #62bc65
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : prouve que le démon du Sensorium, seul et sans noyau, appelle ses points d'évolution ; que ses appels nourrissent le rejeu que le noyau absorbe ; et qu'une panne du service ne perd jamais une mesure.
# MÉTHODE    : charge CN_sensorium.py comme module, un dossier de données temporaire, puis appelle les fonctions façades.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=62bc65 ▼▼▼
import importlib.util
import json
import os
import shutil
import sys
import tempfile
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
        return v

    def iterdir(self):
        pref = self.chemin.rstrip("/") + "/"
        vus = []
        for k in sorted(self.dirs) + sorted(self.fs):
            if k.startswith(pref) and "/" not in k[len(pref):] and k not in vus:
                vus.append(k)
        return [FauxFichier(k, self.fs, self.dirs) for k in vus]

    def __str__(self):
        return self.chemin

    def __truediv__(self, x):
        return FauxFichier(self.chemin.rstrip("/") + "/" + x, self.fs, self.dirs)

    @property
    def parent(self):
        return FauxFichier(self.chemin.rsplit("/", 1)[0] or "/", self.fs, self.dirs)


class Collecteurs(unittest.TestCase):
    """Les collecteurs mail et FTP de FastPanel : les LECTURES restent dans le démon, la FORME passe par le point `fp_formes`. Les attendus viennent de l'ANCIEN code, rejoué sur les mêmes scénarios (33 scénarios : mail, FTP, comptes, bases ; aucun écart)."""

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
        fs, dirs = dict(sc.get("fs", {})), set(sc.get("dirs", []))
        m.Path = lambda chemin: FauxFichier(chemin, fs, dirs)
        m.datetime = type("DT", (), {"now": staticmethod(lambda tz=None: type("N", (), {"isoformat": staticmethod(lambda: "2026-10-17T12:00:00.000001")})())})
        m._fp_available = lambda: sc.get("dispo", True)
        m._mogwai = lambda args, timeout=15: sc.get("mogwai", "")
        m._fp_api_get_list = lambda ep: list(sc.get("api", []))
        m._fp_sqlite_ftp = lambda: [dict(x) for x in sc.get("base_ftp", [])]
        m._fp_get_fp2_usernames = lambda: list(sc.get("users", []))
        m._fp_sqlite_users = lambda: [dict(x) for x in sc.get("base_users", [])]
        m._fp_sqlite_databases = lambda: [dict(x) for x in sc.get("base_dbs", [])]

        def run_cmd(cmd, *a, **k):
            if cmd.startswith("du -sb"):
                return sc.get("du", {}).get(cmd.split()[2].strip("'"), "")
            return sc.get("mysql", "")
        m.run_cmd = run_cmd
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
