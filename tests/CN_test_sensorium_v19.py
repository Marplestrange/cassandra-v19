# ══════════════════════════════════════════════════════════════════
# TITRE      : Bancs du Sensorium V19 : le démon voit le noyau V19, le module relève la santé des modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #29ca35
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : prouve que le Sensorium voit la V19 elle-même (unité cassandra-noyau, sonde HTTP, bases, code scellé, courtier root) et que le module relève la santé de chaque module du noyau.
# MÉTHODE    : charge CN_sensorium.py sur une base temporaire, simule systemctl et l'API HTTP (aucun réseau, aucune commande système), fabrique de vraies bases SQLite (saines, abîmées, tronquées) et une version scellée, puis monte un vrai noyau avec ses modules pour la santé de dedans.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=29ca35 ▼▼▼
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
DOSSIER = RACINE / "modules" / "sensorium"
PYTHON = sys.executable


def charger_demon(tmp):
    donnees = tmp / "donnees" / "sensorium"
    donnees.mkdir(parents=True, exist_ok=True)
    (tmp / "donnees" / "ec").mkdir(exist_ok=True)
    os.environ["CASSANDRA_DATA_DIR"] = str(donnees)
    os.environ["SENSORIUM_DB"] = str(donnees / "s.db")
    os.environ["SENSORIUM_SOCKET"] = str(tmp / "k.sock")
    sys.path.insert(0, str(DOSSIER))
    spec = importlib.util.spec_from_file_location("sensorium_demon_v19", DOSSIER / "CN_sensorium.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    import CN_points_sensorium as ps
    ps._SVC = ps._REJEU = None
    ps._ECHEC = ""
    return m


class Demon(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.m = charger_demon(self.tmp)
        self.m._V19_UNITE.update(t=0.0, u=None)
        self.m._V19_VERIF.clear()
        self.m._V19_CODE.update(t=0.0, release=None, res=None)
        self.m._V19_CODE.pop("travail", None)
        self.racine = self.tmp / "var-cassandra"
        self.donnees = self.racine / "donnees"
        (self.donnees / "modules").mkdir(parents=True)
        for nom, val in (("RACINE_V19", str(self.racine)), ("DONNEES_V19", str(self.donnees)), ("CONFIG_V19", str(self.racine / "config")),
                         ("UTILISATEURS_V19", str(self.tmp / "www")), ("LIBEXEC_V19", str(self.tmp / "libexec")), ("URL_NOYAU_FORCEE", "")):
            p = mock.patch.object(self.m, nom, val)
            p.start()
            self.addCleanup(p.stop)

    def systemctl(self, props, charge="loaded"):
        """Un faux run_cmd_ex : systemctl répond pour les unités de `props` ({unité: {propriété: valeur}}), rien pour les autres."""
        def faux(cmd, timeout=10, input_data=None):
            if cmd[:2] == ["systemctl", "show"]:
                u = cmd[2]
                if "--value" in cmd:
                    return (0, (charge if u in props else "not-found"), "")
                p = props.get(u, {})
                voulues = cmd[cmd.index("-p") + 1].split(",")
                return (0, "\n".join("%s=%s" % (k, p[k]) for k in voulues if k in p), "")
            return (None, "", "")
        return mock.patch.object(self.m, "run_cmd_ex", faux)

    def valeurs(self, rows):
        return {r["cle"]: r for r in rows}


class Unite(Demon):
    def test_l_unite_v19_est_preferee_a_celle_de_la_v18(self):
        with self.systemctl({"cassandra-noyau.service": {}, "cassandra.service": {}}):
            self.assertEqual(self.m._unite_noyau(), "cassandra-noyau.service")

    def test_a_defaut_l_unite_v18(self):
        with self.systemctl({"cassandra.service": {}}):
            self.assertEqual(self.m._unite_noyau(), "cassandra.service")

    def test_sans_aucune_unite_rien_n_est_invente(self):
        with self.systemctl({}):
            self.assertIsNone(self.m._unite_noyau())

    def test_l_adresse_du_noyau_se_lit_dans_son_unite(self):
        env = {"cassandra-noyau.service": {"Environment": 'PYTHONUNBUFFERED=1 CASSANDRA_ECOUTE=0.0.0.0:9100 CASSANDRA_DONNEES=/x'}}
        with self.systemctl(env):
            self.assertEqual(self.m._url_noyau("cassandra-noyau.service"), "http://127.0.0.1:9100")
        with self.systemctl({"cassandra-noyau.service": {}}):
            self.assertEqual(self.m._url_noyau("cassandra-noyau.service"), "http://127.0.0.1:9000")
        with mock.patch.object(self.m, "URL_NOYAU_FORCEE", "http://100.64.0.1:9000"):
            self.assertEqual(self.m._url_noyau("x"), "http://100.64.0.1:9000")

    def test_une_machine_sans_cassandra_ne_dit_rien(self):
        shutil.rmtree(self.racine)
        with self.systemctl({}):
            self.assertEqual(self.m.collect_cassandra_v19(), [])


class Noyau(Demon):
    PROPS = {"cassandra-noyau.service": {"ActiveState": "active", "SubState": "running", "Result": "success", "MainPID": "812",
                                         "MemoryCurrent": str(300 << 20), "NRestarts": "0", "ActiveEnterTimestamp": "Sat 2026-10-31 02:00:00 CET"}}

    def sonde(self, sante=(200, 40, b'{"ok": true, "version": "0.1.0"}', ""), page=(200, 20, b"<!doctype html><html></html>", "")):
        def faux(url, timeout=5):
            return sante if url.endswith("/api/sante") else page
        return mock.patch.object(self.m, "_sonde_http", faux)

    def releve(self, props=None, **kw):
        with self.systemctl(props or self.PROPS), self.sonde(**kw), mock.patch.object(self.m, "_cassandra_demarrages", lambda: []):
            return self.valeurs(self.m.collect_noyau_v19())

    def test_un_noyau_sain_se_lit_en_cinq_releves(self):
        r = self.releve()
        for cle in ("noyau.service", "noyau.http", "noyau.version", "noyau.page", "noyau.demarrages"):
            self.assertIn(cle, r)
            self.assertEqual(r[cle]["severite"], "info", (cle, r[cle]))
        self.assertIn("PID 812", r["noyau.service"]["valeur"])
        self.assertIn("300 Mo", r["noyau.service"]["valeur"])
        self.assertIn("0.1.0", r["noyau.version"]["valeur"])

    def test_un_noyau_arrete_alerte_et_n_est_pas_sonde(self):
        arrete = {"cassandra-noyau.service": {"ActiveState": "failed", "SubState": "failed", "Result": "exit-code"}}
        r = self.releve(arrete)
        self.assertEqual(r["noyau.service"]["severite"], "warning")
        self.assertIn("exit-code", r["noyau.service"]["valeur"])
        self.assertNotIn("noyau.http", r)

    def test_un_noyau_actif_qui_ne_repond_pas_alerte(self):
        r = self.releve(sante=(None, 5000, b"", "timed out"))
        self.assertEqual(r["noyau.http"]["severite"], "warning")
        self.assertIn("ne répond pas", r["noyau.http"]["valeur"])

    def test_une_reponse_illisible_ou_en_erreur_alerte(self):
        self.assertEqual(self.releve(sante=(500, 30, b"", ""))["noyau.http"]["severite"], "warning")
        self.assertEqual(self.releve(sante=(200, 30, b"pas du json", ""))["noyau.http"]["severite"], "warning")
        self.assertEqual(self.releve(sante=(200, 30, b'{"ok": false}', ""))["noyau.http"]["severite"], "warning")

    def test_une_reponse_lente_alerte(self):
        self.assertEqual(self.releve(sante=(200, 3500, b'{"ok": true, "version": "x"}', ""))["noyau.http"]["severite"], "warning")

    def test_une_page_de_connexion_absente_alerte(self):
        r = self.releve(page=(502, 20, b"", ""))
        self.assertEqual(r["noyau.page"]["severite"], "warning")

    def test_un_noyau_qui_redemarre_en_boucle_alerte(self):
        boucle = {"cassandra-noyau.service": dict(self.PROPS["cassandra-noyau.service"], NRestarts="5")}
        self.assertEqual(self.releve(boucle)["noyau.service"]["severite"], "warning")
        with self.systemctl(self.PROPS), self.sonde(), mock.patch.object(self.m, "_cassandra_demarrages", lambda: [1, 2, 3]):
            r = self.valeurs(self.m.collect_noyau_v19())
        self.assertEqual(r["noyau.demarrages"]["severite"], "warning")

    def test_la_memoire_non_mesuree_ne_fait_pas_un_chiffre_absurde(self):
        p = {"cassandra-noyau.service": dict(self.PROPS["cassandra-noyau.service"], MemoryCurrent="18446744073709551615")}
        v = self.releve(p)["noyau.service"]["valeur"]
        self.assertNotIn("Mo de RAM", v)

    def test_la_base_du_noyau_qui_ne_s_ecrit_plus_se_voit(self):
        f = self.donnees / "noyau.db"
        sqlite3.connect(f).close()
        vieux = time.time() - 8 * 3600
        os.utime(f, (vieux, vieux))
        r = self.releve()
        self.assertEqual(r["noyau.activite"]["severite"], "warning")
        os.utime(f, None)
        self.assertEqual(self.releve()["noyau.activite"]["severite"], "info")

    def test_les_demarrages_se_lisent_dans_le_journal_de_la_bonne_unite(self):
        vues = []

        def faux(cmd, timeout=10):
            vues.append(cmd)
            return "2026-10-31T08:00:00 hote systemd[1]: Started Cassandra"
        with self.systemctl(self.PROPS), mock.patch.object(self.m, "run_cmd", faux):
            r = self.m._cassandra_demarrages()
        self.assertEqual(len(r), 1)
        self.assertIn("cassandra-noyau", vues[0])
        self.assertNotIn("cassandra-noyau.service", vues[0])

    def test_un_demon_vieux_nom_garde_la_section_v18(self):
        with self.systemctl({"cassandra.service": {}}), mock.patch.object(self.m, "_sante_cassandra_v18", lambda: [self.m._mesure("cassandra.processus", "application", "v18")]), \
                mock.patch.object(self.m, "collect_cassandra_v19", lambda: []), mock.patch.object(self.m, "_journaux_acces", lambda: {}):
            cles = [r["cle"] for r in self.m.collect_sante_applicative()]
        self.assertIn("cassandra.processus", cles)
        self.m._V19_UNITE.update(t=0.0, u=None)
        with self.systemctl(self.PROPS), mock.patch.object(self.m, "_sante_cassandra_v18", lambda: [self.m._mesure("cassandra.processus", "application", "v18")]), \
                mock.patch.object(self.m, "collect_cassandra_v19", lambda: []), mock.patch.object(self.m, "_journaux_acces", lambda: {}):
            cles = [r["cle"] for r in self.m.collect_sante_applicative()]
        self.assertNotIn("cassandra.processus", cles)

    def test_un_releve_qui_plante_n_efface_pas_les_autres(self):
        def casse():
            raise RuntimeError("boum")
        casse.__name__ = "collect_stores_v19"
        with self.systemctl(self.PROPS), mock.patch.object(self.m, "collect_stores_v19", casse), \
                mock.patch.object(self.m, "collect_noyau_v19", lambda: [self.m._mesure("noyau.service", "application", "ok")]), \
                mock.patch.object(self.m, "collect_code_v19", lambda: []), mock.patch.object(self.m, "collect_courtier_v19", lambda: []):
            r = self.valeurs(self.m.collect_cassandra_v19())
        self.assertIn("noyau.service", r)
        self.assertEqual(r["noyau.releve_stores"]["severite"], "warning")
        self.assertIn("boum", r["noyau.releve_stores"]["valeur"])


def base_saine(chemin, lignes=3000):
    c = sqlite3.connect(chemin)
    c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
    c.execute("CREATE INDEX i ON t(v)")
    c.executemany("INSERT INTO t(v) VALUES (?)", (("valeur %d" % i * 3,) for i in range(lignes)))
    c.commit()
    c.close()


class Bases(Demon):
    def releve(self):
        """Un relevé, la vérification d'intégrité qu'il lance en arrière-plan (on l'attend), puis un second relevé qui en lit le résultat."""
        self.m.collect_stores_v19()
        t = self.m._V19_INTEGRITE["travail"]
        if t is not None:
            t.join(60)
        return self.valeurs(self.m.collect_stores_v19())

    def test_une_base_saine_est_verifiee_et_dite_saine(self):
        base_saine(self.donnees / "noyau.db")
        base_saine(self.donnees / "modules" / "agenda.db", 50)
        with self.systemctl({}):
            premier = self.valeurs(self.m.collect_stores_v19())
            self.assertIn("en cours", premier["store.noyau"]["valeur"])           # la première passe ne bloque pas sur la vérification
            r = self.releve()
        self.assertEqual(set(r), {"store.noyau", "store.module.agenda", "store.total"})
        self.assertEqual(r["store.noyau"]["severite"], "info")
        self.assertIn("intégrité ok", r["store.noyau"]["valeur"])
        self.assertIn("2 bases", r["store.total"]["valeur"])

    def test_la_verification_n_est_pas_refaite_a_chaque_passe(self):
        base_saine(self.donnees / "noyau.db")
        with mock.patch.object(self.m, "_quick_check", return_value="ok") as qc:
            self.releve()
            self.releve()
        self.assertEqual(qc.call_count, 1)

    def test_une_base_abimee_au_milieu_est_trouvee(self):
        f = self.donnees / "modules" / "courrier.db"
        base_saine(f, 4000)
        with open(f, "r+b") as fh:                                   # on abîme une page intérieure, l'en-tête reste intact
            fh.seek(4096 * 2)
            fh.write(b"\xff" * 200)
        self.assertNotIn(self.m._quick_check(f), ("ok", ""))
        r = self.releve()
        self.assertEqual(r["store.module.courrier"]["severite"], "warning")
        self.assertIn("INTÉGRITÉ", r["store.module.courrier"]["valeur"])

    def test_un_en_tete_abime_est_trouve_sans_ouvrir_la_base(self):
        f = self.donnees / "modules" / "notes.db"
        base_saine(f)
        with open(f, "r+b") as fh:
            fh.write(b"PAS DU SQLITE!!!!")
        d = self.m._inspecter_base(f)
        self.assertIn("en-tête", d["defaut"])
        r = self.releve()
        self.assertEqual(r["store.module.notes"]["severite"], "warning")

    def test_une_base_lente_ne_bloque_pas_le_releve(self):
        f = self.donnees / "modules" / "grosse.db"
        base_saine(f, 50)
        lancee = []

        def lente(chemin, delai=0):
            lancee.append(chemin)
            time.sleep(1.5)
            return "ok"
        with mock.patch.object(self.m, "_quick_check", lente):
            t0 = time.monotonic()
            r = self.valeurs(self.m.collect_stores_v19())
            self.assertLess(time.monotonic() - t0, 1.0)                                   # le relevé ne l'attend pas
            self.assertIn("store.module.grosse", r)
            self.m._V19_INTEGRITE["travail"].join(20)
        self.assertEqual(len(lancee), 1)

    def test_un_fichier_tronque_est_trouve(self):
        f = self.donnees / "modules" / "ged.db"
        base_saine(f, 4000)
        taille = f.stat().st_size
        with open(f, "r+b") as fh:
            fh.truncate(taille // 2)
        self.assertIn("tronqué", self.m._inspecter_base(f)["defaut"])

    def test_une_base_vide_se_dit(self):
        f = self.donnees / "modules" / "vide.db"
        f.write_bytes(b"")
        self.assertIn("vide", self.m._inspecter_base(f)["defaut"])

    def test_un_journal_wal_demesure_alerte(self):
        f = self.donnees / "modules" / "salon.db"
        base_saine(f, 20)
        with open(str(f) + "-wal", "wb") as w:
            w.truncate(80 << 20)
        r = self.valeurs(self.m.collect_stores_v19())
        self.assertEqual(r["store.module.salon"]["severite"], "warning")
        self.assertIn("WAL", r["store.module.salon"]["valeur"])

    def test_une_base_ouverte_par_un_autre_n_est_pas_une_alerte(self):
        f = self.donnees / "modules" / "occupee.db"
        base_saine(f, 20)
        with mock.patch.object(self.m.sqlite3, "connect", side_effect=sqlite3.OperationalError("database is locked")):
            self.assertEqual(self.m._quick_check(f), "")
        with mock.patch.object(self.m.sqlite3, "connect", side_effect=sqlite3.OperationalError("unable to open database file")):
            self.assertEqual(self.m._quick_check(f), "")
        with mock.patch.object(self.m.sqlite3, "connect", side_effect=sqlite3.DatabaseError("file is not a database")):
            self.assertIn("illisible", self.m._quick_check(f))

    def test_les_bases_des_societes_et_des_utilisateurs_sont_comptees(self):
        (self.racine / "societes" / "1" / "commun" / "ged").mkdir(parents=True)
        base_saine(self.racine / "societes" / "1" / "commun" / "ged" / "a.db", 10)
        (self.tmp / "www" / "fastuser" / "data" / "cassandra" / "notes").mkdir(parents=True)
        base_saine(self.tmp / "www" / "fastuser" / "data" / "cassandra" / "notes" / "b.db", 10)
        abimee = self.tmp / "www" / "fastuser" / "data" / "cassandra" / "notes" / "c.db"
        abimee.write_bytes(b"x" * 300)
        r = self.valeurs(self.m.collect_stores_v19())
        self.assertIn("1 bases de sociétés", r["store.societes"]["valeur"])
        self.assertEqual(r["store.societes"]["severite"], "info")
        self.assertIn("2 bases d'utilisateurs", r["store.utilisateurs"]["valeur"])
        self.assertEqual(r["store.utilisateurs"]["severite"], "warning")

    def test_sans_aucune_base_aucun_releve(self):
        self.assertEqual(self.m.collect_stores_v19(), [])


class CodeScelle(Demon):
    def version(self, avec_outil=True):
        courant = self.racine / "releases" / "v1"
        (courant / "noyau").mkdir(parents=True)
        shutil.copy(RACINE / "noyau" / "CN_chemins.py", courant / "noyau" / "CN_chemins.py")
        if avec_outil:
            (courant / "outils").mkdir()
            shutil.copy(RACINE / "outils" / "CN_bornes.py", courant / "outils" / "CN_bornes.py")
        return courant

    def lien(self, courant):
        """Le lien <racine>/current vers la version en service (un lien symbolique demande un privilège sous Windows : on le simule)."""
        vrai = os.path.realpath
        return mock.patch.object(self.m.os.path, "realpath", lambda p: str(courant) if str(p).endswith("current") else vrai(p))

    def test_un_code_conforme_au_scelle_est_dit_conforme(self):
        courant = self.version()
        self.m._code_scelle_travail(str(courant), "v1")
        res = self.m._V19_CODE["res"]
        self.assertEqual(res["etat"], "ok", res)
        self.assertEqual(res["erreurs"], 0, res)
        self.assertGreaterEqual(res["fichiers"], 2)

    def test_un_fichier_modifie_dans_sa_borne_est_un_ecart(self):
        courant = self.version()
        f = courant / "noyau" / "CN_chemins.py"
        t = f.read_text(encoding="utf-8")
        f.write_text(t.replace('"/var/www"', '"/var/tmp"', 1), encoding="utf-8")
        self.m._code_scelle_travail(str(courant), "v1")
        res = self.m._V19_CODE["res"]
        self.assertGreater(res["erreurs"], 0, res)
        self.assertTrue(any("CN_chemins" in e[0] for e in res["ecarts"]), res)

    def test_sans_les_outils_on_le_dit_sans_alarme(self):
        courant = self.version(avec_outil=False)
        self.m._code_scelle_travail(str(courant), "v1")
        self.assertEqual(self.m._V19_CODE["res"]["etat"], "absent")

    def test_le_releve_rend_le_dernier_resultat_et_alerte_sur_un_ecart(self):
        courant = self.version()
        f = courant / "noyau" / "CN_chemins.py"
        f.write_text(f.read_text(encoding="utf-8").replace('"/var/www"', '"/var/tmp"', 1), encoding="utf-8")
        self.m._code_scelle_travail(str(courant), "v1")
        with self.lien(courant), mock.patch.object(self.m, "_code_scelle_travail"):
            r = self.m.collect_code_v19()
        self.assertEqual(r[0]["cle"], "code.scelle")
        self.assertEqual(r[0]["severite"], "warning")
        self.assertIn("écart", r[0]["valeur"])

    def test_la_premiere_passe_dit_qu_elle_verifie(self):
        courant = self.version()
        with self.lien(courant), mock.patch.object(self.m, "_code_scelle_travail"):
            r = self.m.collect_code_v19()
        self.assertIn("en cours", r[0]["valeur"])
        self.assertEqual(r[0]["severite"], "info")

    def test_sans_version_courante_rien_n_est_dit(self):
        self.assertEqual(self.m.collect_code_v19(), [])


def stat_de(mode, uid=0):
    return os.stat_result((mode, 1, 1, 1, uid, 0, 10, 0, 0, 0))


class Courtier(Demon):
    def manifeste(self, module, commandes):
        d = self.racine / "current" / "modules" / module
        d.mkdir(parents=True, exist_ok=True)
        (d / "CN_manifeste.toml").write_text("[module]\nid = \"%s\"\n" % module + "".join("\n[[racine]]\nid = \"%s\"\nlibelle = \"x\"\n" % c for c in commandes), encoding="utf-8")

    def pose(self, module, commandes):
        d = self.tmp / "libexec" / module
        d.mkdir(parents=True, exist_ok=True)
        for c in commandes:
            (d / c).write_text("#!/bin/sh\n", encoding="utf-8")

    def releve(self, units=None, sur=""):
        props = {"cassandra-courtier.path": {"LoadState": "loaded", "ActiveState": "waiting"},
                 "cassandra-courtier.service": {"LoadState": "loaded", "ActiveState": "inactive", "Result": "success"}}
        props.update(units or {})
        with self.systemctl(props), mock.patch.object(self.m, "_sur_root", lambda c, d: sur):
            return self.valeurs(self.m.collect_courtier_v19())

    def test_les_commandes_declarees_et_posees_sont_conformes(self):
        self.manifeste("urgence", ["etat", "agir"])
        self.pose("urgence", ["etat", "agir"])
        r = self.releve()
        self.assertEqual(r["courtier.commandes"]["severite"], "info", r)
        self.assertIn("2 commande(s) root pour 1 module(s)", r["courtier.commandes"]["valeur"])
        self.assertEqual(r["courtier.etat"]["severite"], "info")

    def test_une_commande_non_declaree_est_une_alerte(self):
        self.manifeste("urgence", ["etat"])
        self.pose("urgence", ["etat", "porte-derobee"])
        r = self.releve()
        self.assertEqual(r["courtier.commandes"]["severite"], "warning")
        self.assertIn("porte-derobee n'est déclarée par aucun manifeste", r["courtier.commandes"]["valeur"])

    def test_une_commande_declaree_mais_absente_est_une_alerte(self):
        self.manifeste("urgence", ["etat", "agir"])
        self.pose("urgence", ["etat"])
        r = self.releve()
        self.assertIn("agir est déclarée mais pas posée", r["courtier.commandes"]["valeur"])

    def test_un_module_sans_declaration_ne_peut_rien_poser(self):
        self.pose("fantome", ["x"])
        r = self.releve()
        self.assertEqual(r["courtier.commandes"]["severite"], "warning")

    def test_une_commande_modifiable_par_d_autres_est_une_alerte(self):
        self.manifeste("urgence", ["etat"])
        self.pose("urgence", ["etat"])
        r = self.releve(sur="modifiable par un autre que root (mode 777)")
        self.assertEqual(r["courtier.commandes"]["severite"], "warning")
        self.assertIn("modifiable", r["courtier.commandes"]["valeur"])

    def test_les_droits_d_un_programme_se_lisent_au_noyau_du_systeme(self):
        tests = {"/p": (stat_de(0o100755, 0), ""), "/q": (stat_de(0o100755, 1000), "n'appartient pas à root"), "/r": (stat_de(0o100775, 0), "modifiable"),
                 "/s": (stat_de(0o100644, 0), "pas un programme exécutable"), "/t": (stat_de(0o120777, 0), "est un lien")}
        def faux(chemin):
            if chemin not in tests:
                raise OSError("absent")
            return tests[chemin][0]
        with mock.patch.object(self.m.os, "lstat", faux):
            for chemin, (_, attendu) in tests.items():
                got = self.m._sur_root(chemin, False)
                self.assertTrue(got == attendu or (attendu and attendu in got), (chemin, got))
            self.assertEqual(self.m._sur_root("/absent", False), "absent")
        with mock.patch.object(self.m.os, "lstat", lambda c: stat_de(0o40755, 0)):
            self.assertEqual(self.m._sur_root("/d", True), "")
        with mock.patch.object(self.m.os, "lstat", lambda c: stat_de(0o40777, 0)):
            self.assertIn("modifiable", self.m._sur_root("/d", True))

    def test_les_declarations_se_lisent_aussi_sans_tomllib(self):
        self.manifeste("urgence", ["etat", "agir"])
        with mock.patch.dict(sys.modules, {"tomllib": None}):
            self.assertEqual(self.m._racines_declarees(), {"urgence": {"etat", "agir"}})
        self.assertEqual(self.m._racines_declarees(), {"urgence": {"etat", "agir"}})

    def test_un_courtier_a_l_arret_est_une_alerte(self):
        self.manifeste("urgence", ["etat"])
        self.pose("urgence", ["etat"])
        r = self.releve({"cassandra-courtier.path": {"LoadState": "loaded", "ActiveState": "failed"}})
        self.assertEqual(r["courtier.etat"]["severite"], "warning")
        r = self.releve({"cassandra-courtier.service": {"LoadState": "loaded", "ActiveState": "failed", "Result": "exit-code"}})
        self.assertEqual(r["courtier.etat"]["severite"], "warning")

    def test_des_demandes_qui_attendent_trop_sont_une_alerte(self):
        self.manifeste("urgence", ["etat"])
        self.pose("urgence", ["etat"])
        spool = self.donnees / "courtier"
        spool.mkdir()
        f = spool / "a.json"
        f.write_text("{}", encoding="utf-8")
        vieux = time.time() - 600
        os.utime(f, (vieux, vieux))
        r = self.releve()
        self.assertEqual(r["courtier.file"]["severite"], "warning")
        self.assertIn("1 demande(s) en attente", r["courtier.file"]["valeur"])

    def test_pas_de_courtier_pas_de_commandes_c_est_normal(self):
        with self.systemctl({}):
            r = self.valeurs(self.m.collect_courtier_v19())
        self.assertEqual(r["courtier.etat"]["severite"], "info")

    def test_des_commandes_root_sans_courtier_sont_une_alerte(self):
        self.pose("urgence", ["etat"])
        with self.systemctl({}), mock.patch.object(self.m, "_sur_root", lambda c, d: ""):
            r = self.valeurs(self.m.collect_courtier_v19())
        self.assertEqual(r["courtier.etat"]["severite"], "warning")


# ---------- le module, dans un vrai noyau ----------
MODULE_CASSE = '''
[module]
id = "casse"
nom = "Module d'essai"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Un module dont le moteur tombera."
famille = "gestion"

[[droits]]
id = "utiliser"
libelle = "Utiliser le module d'essai"
defaut = true

[[moteurs]]
id = "moteur_essai"
libelle = "Un moteur d'essai"
mode = "periodique"
toutes_les_s = 3600
duree_max_s = 5
'''
PY_CASSE = "def brancher(ctx):\n    ctx.moteur('moteur_essai', lambda ctx: None)\n"


class ModuleDansUnNoyau(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import CN_main as moteur
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        mods = base / "modules"
        ig = shutil.ignore_patterns("__pycache__")
        for m in ("droits", "modules", "sensorium"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=ig)
        manifeste = mods / "sensorium" / "CN_manifeste.toml"
        t = manifeste.read_text(encoding="utf-8")
        manifeste.write_text(re.sub(r"\[installation\][^\[]*", "", t), encoding="utf-8")          # pas d'installation de service root dans un banc
        (mods / "casse").mkdir()
        (mods / "casse" / "CN_manifeste.toml").write_text(MODULE_CASSE, encoding="utf-8")
        (mods / "casse" / "CN_module.py").write_text(PY_CASSE, encoding="utf-8")
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        for m in ("droits", "modules", "sensorium", "casse"):
            r = cls.n.activer(m)
            assert r["ok"], (m, r)
        cls.n.droits.regler_admin("root@exemple.test", True)

    @classmethod
    def tearDownClass(cls):
        cls.n.arreter()
        cls.tmp.cleanup()

    _heure = 0

    def tick(self):
        """Une passe des détecteurs, à une heure toujours plus tardive : un détecteur n'est échu qu'après sa fréquence."""
        ModuleDansUnNoyau._heure += 10000
        return self.n.tick(maintenant=time.time() + ModuleDansUnNoyau._heure)

    def lire(self):
        r = self.n.executeur.executer("sensorium.modules", "humain", {}, compte="root@exemple.test")
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_la_sante_des_modules_est_relevee_par_le_moteur(self):
        r = self.n.lancer("sensorium.sante_modules")
        self.assertEqual(r.get("statut"), "fait", r)
        lu = self.lire()
        self.assertFalse(lu["muet"], lu)
        self.assertIn("casse", lu["modules"])
        self.assertIn("sensorium", lu["modules"])
        self.assertEqual(lu["modules"]["casse"]["verdict"], "sain")
        self.assertIn("root@exemple.test", lu["administrateurs"])

    def test_un_module_dont_le_moteur_est_suspendu_est_un_constat_puis_se_retablit(self):
        self.n.lancer("sensorium.sante_modules")
        self.n._moteurs_suspendus.add(("casse", "moteur_essai"))
        try:
            self.n.lancer("sensorium.sante_modules")
            self.assertEqual(self.lire()["modules"]["casse"]["verdict"], "en_echec")
            self.tick()
            constats = self.n.base.lire("SELECT titre, objet_type, objet_id, etat FROM constats WHERE module='sensorium' AND detecteur='modules_en_echec'")
            self.assertTrue(any(c["objet_id"] == "casse" and c["etat"] == "ouvert" for c in constats), constats)
            evs = self.n.base.lire("SELECT type FROM evenements WHERE type='module_noyau.en_echec'")
            self.assertTrue(evs)
        finally:
            self.n._moteurs_suspendus.discard(("casse", "moteur_essai"))
        self.n.lancer("sensorium.sante_modules")
        self.assertEqual(self.lire()["modules"]["casse"]["verdict"], "sain")
        self.tick()
        ouverts = self.n.base.lire("SELECT objet_id FROM constats WHERE module='sensorium' AND detecteur='modules_en_echec' AND etat='ouvert'")
        self.assertFalse([c for c in ouverts if c["objet_id"] == "casse"])
        self.assertTrue(self.n.base.lire("SELECT 1 FROM evenements WHERE type='module_noyau.retabli'"))

    def test_sans_administrateur_c_est_un_constat(self):
        admins = list(self.n.droits.etat()["admins"])                    # l'administrateur d'amorçage (fastuser) compte aussi
        for a in admins:
            self.n.droits.regler_admin(a, False)
        try:
            self.n.lancer("sensorium.sante_modules")
            self.tick()
            constats = self.n.base.lire("SELECT titre FROM constats WHERE module='sensorium' AND detecteur='sans_administrateur' AND etat='ouvert'")
            self.assertTrue(constats)
        finally:
            for a in admins:
                self.n.droits.regler_admin(a, True)
        self.n.lancer("sensorium.sante_modules")
        self.tick()
        self.assertFalse(self.n.base.lire("SELECT 1 FROM constats WHERE module='sensorium' AND detecteur='sans_administrateur' AND etat='ouvert'"))


class ModuleSansNoyau(unittest.TestCase):
    """Le module seul, avec un faux contexte : ce que devient la relève quand le noyau ne répond pas."""
    def setUp(self):
        spec = importlib.util.spec_from_file_location("sensorium_module_v19", DOSSIER / "CN_module.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.reponses, self.emis, self.cles = {}, [], {}

        class Ctx:
            pass
        ctx = Ctx()
        ctx.executer_lecture = self.lecture
        ctx.emettre = lambda t, **kw: self.emis.append((t, kw))
        ctx.moteur = lambda i, f: self.cles.__setitem__("moteur." + i, f)
        ctx.detecteur = lambda i, f: self.cles.__setitem__("detecteur." + i, f)
        ctx.implementer = lambda i, f, *a, **k: self.cles.__setitem__("capacite." + i, f)
        ctx.lire = lambda *a, **k: None
        ctx.poser = lambda *a, **k: True
        self.ctx = ctx
        self.mod.brancher(ctx)

    def lecture(self, cap, **args):
        r = self.reponses[cap]
        if isinstance(r, Exception):
            raise r
        return r

    def test_un_noyau_qui_ne_rend_pas_la_sante_est_un_constat(self):
        self.reponses = {"modules.sante": PermissionError("pas une capacité de lecture")}
        self.cles["moteur.sante_modules"](self.ctx)
        c = self.cles["detecteur.modules_en_echec"](self.ctx)
        self.assertEqual(len(c), 1)
        self.assertIn("ne se lit plus", c[0]["titre"])
        self.assertTrue(self.cles["capacite.modules"](self.ctx)["muet"])

    def test_avant_la_premiere_releve_rien_n_est_dit(self):
        self.assertEqual(self.cles["detecteur.modules_en_echec"](self.ctx), [])
        self.assertEqual(self.cles["detecteur.sans_administrateur"](self.ctx), [])

    def test_une_reponse_inattendue_est_un_constat_pas_une_erreur(self):
        self.reponses = {"modules.sante": None}
        self.cles["moteur.sante_modules"](self.ctx)
        self.assertEqual(len(self.cles["detecteur.modules_en_echec"](self.ctx)), 1)

    def test_chaque_module_en_echec_dit_ce_qui_est_coupe(self):
        self.reponses = {"modules.sante": {"modules": {"a": {"verdict": "sain"}, "b": {"verdict": "en_echec", "en_echec": ["b.m1", "b.d2"]}, "c": {"verdict": "a_surveiller"}}},
                         "droits.etat": {"admins": ["x"]}}
        self.cles["moteur.sante_modules"](self.ctx)
        c = self.cles["detecteur.modules_en_echec"](self.ctx)
        self.assertEqual([x["objet"] for x in c], [("module_noyau", "b")])
        self.assertIn("b.m1", c[0]["detail"])
        self.assertEqual([t for t, _ in self.emis], ["module_noyau.en_echec"])

    def test_l_echec_ne_se_dit_qu_une_fois_et_le_retour_aussi(self):
        mal = {"modules": {"b": {"verdict": "en_echec", "en_echec": ["b.m"]}}}
        bien = {"modules": {"b": {"verdict": "sain"}}}
        self.reponses = {"modules.sante": mal, "droits.etat": {"admins": ["x"]}}
        for _ in range(3):
            self.cles["moteur.sante_modules"](self.ctx)
        self.reponses["modules.sante"] = bien
        for _ in range(2):
            self.cles["moteur.sante_modules"](self.ctx)
        self.assertEqual([t for t, _ in self.emis], ["module_noyau.en_echec", "module_noyau.retabli"])

    def test_sans_administrateur_et_droits_illisibles(self):
        ok = {"modules": {}}
        self.reponses = {"modules.sante": ok, "droits.etat": {"admins": []}}
        self.cles["moteur.sante_modules"](self.ctx)
        self.assertEqual(len(self.cles["detecteur.sans_administrateur"](self.ctx)), 1)
        self.reponses["droits.etat"] = PermissionError("non")
        self.cles["moteur.sante_modules"](self.ctx)
        self.assertEqual(self.cles["detecteur.sans_administrateur"](self.ctx), [])      # ne pas savoir n'est pas « aucun administrateur »


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
