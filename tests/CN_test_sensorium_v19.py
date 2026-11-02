# ══════════════════════════════════════════════════════════════════
# TITRE      : Bancs du Sensorium V19 : le démon voit le noyau V19, le module relève la santé des modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #9be855
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : prouve que le Sensorium voit la V19 elle-même (unité cassandra-noyau, sonde HTTP, bases, code scellé, courtier root) et que le module relève la santé de chaque module du noyau.
# MÉTHODE    : charge CN_sensorium.py sur une base temporaire, simule systemctl et l'API HTTP (aucun réseau, aucune commande système), fabrique de vraies bases SQLite (saines, abîmées, tronquées) et une version scellée, puis monte un vrai noyau avec ses modules pour la santé de dedans.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9be855 ▼▼▼
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

    # ---- l'écran : etat, acceptations, fenêtres, constats du monde
    def monde(self, rows=None, changes=None):
        """Un collecteur simulé : GET_WORLD rend `rows`, GET_CHANGES `changes`, GET_CORRELATIONS refuse (un démon d'avant)."""
        rows = MONDE if rows is None else rows

        def faux(requete, delai=5.0):
            if requete.startswith("GET_WORLD"):
                return json.loads(json.dumps(rows))
            if requete.startswith("GET_CHANGES"):
                return changes or []
            raise RuntimeError("le collecteur a refusé la requête")
        g = self.n.catalogue.get("sensorium.etat").faire.__globals__
        p = mock.patch.dict(g, {"json_de": faux})
        p.start()
        self.addCleanup(p.stop)

    def ex(self, cap, **args):
        return self.n.executeur.executer(cap, "humain", args, compte="root@exemple.test")

    def etat(self):
        self.n.lancer("sensorium.monde")
        r = self.ex("sensorium.etat")
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def tick_monde(self, fois=2):
        for _ in range(fois):
            self.n.lancer("sensorium.monde")
        return self.tick()

    def constats(self):
        return {c["objet_id"]: c for c in self.n.base.lire("SELECT objet_id, titre, etat FROM constats WHERE module='sensorium' AND detecteur='alertes_du_monde' AND etat='ouvert'")}

    def nettoyer(self):
        for w in ("ssl.exemple.org", "disk./var.usage"):
            self.ex("sensorium.retirer_acceptation", wkey=w)
        for f in self.ex("sensorium.fenetres")["resultat"]["vivantes"]:
            self.ex("sensorium.fenetre_annuler", id=f["id"])

    def test_l_etat_donne_a_chaque_mesure_son_nom_sa_famille_et_son_objet(self):
        self.monde()
        e = self.etat()
        self.assertFalse(e["muet"])
        ssl = next(r for r in e["rows"] if r["wkey"] == "ssl.exemple.org")
        self.assertEqual((ssl["libelle"], ssl["famille"], ssl["objet"]), ("Certificat exemple.org", "ssl", {"genre": "Sites", "nom": "exemple.org"}))
        self.assertEqual(e["hote"], "hote")
        disque = next(r for r in e["rows"] if r["wkey"] == "disk./var.usage")
        self.assertEqual(disque["objet"], {"genre": "Machines", "nom": "hote"})
        self.assertEqual(e["correlations"], [])                          # un démon d'avant la lecture des corrélations : aucune erreur

    def test_un_collecteur_muet_donne_un_etat_muet_pas_une_erreur(self):
        def casse(requete, delai=5.0):
            raise OSError("pas de socket")
        g = self.n.catalogue.get("sensorium.etat").faire.__globals__
        with mock.patch.dict(g, {"json_de": casse}):
            self.n.lancer("sensorium.monde")
            r = self.ex("sensorium.etat")
        self.assertEqual(r["statut"], "faite", r)
        self.assertTrue(r["resultat"]["muet"])
        self.assertIn("pas de socket", r["resultat"]["erreur"])

    def test_une_alerte_acceptee_se_tait_puis_revient_quand_le_chiffre_monte(self):
        self.monde()
        try:
            r = self.ex("sensorium.accepter", wkey="disk./var.usage", raison="volume d'archive", jours=30)
            self.assertEqual(r["statut"], "faite", r)
            e = self.etat()
            d = next(x for x in e["rows"] if x["wkey"] == "disk./var.usage")
            self.assertEqual(d["severity"], "info")
            self.assertEqual(d["acquit"]["raison"], "volume d'archive")
            plus = [dict(x, value="90 %") if x["wkey"] == "disk./var.usage" else x for x in MONDE]
            self.monde(plus)
            d = next(x for x in self.etat()["rows"] if x["wkey"] == "disk./var.usage")
            self.assertEqual(d["severity"], "warning")                    # pire qu'au moment où on l'a acceptée
            self.assertNotIn("acquit", d)
        finally:
            self.nettoyer()

    def test_accepter_une_mesure_inconnue_est_refuse(self):
        self.monde()
        r = self.ex("sensorium.accepter", wkey="n.existe.pas", raison="x")
        self.assertNotEqual(r["statut"], "faite", r)

    def test_retirer_une_acceptation_la_fait_revenir(self):
        self.monde()
        try:
            self.ex("sensorium.accepter", wkey="ssl.exemple.org", raison="x", jours=0)
            self.assertEqual(next(x for x in self.etat()["rows"] if x["wkey"] == "ssl.exemple.org")["severity"], "info")
            self.assertEqual(self.ex("sensorium.retirer_acceptation", wkey="ssl.exemple.org")["statut"], "faite")
            self.assertEqual(next(x for x in self.etat()["rows"] if x["wkey"] == "ssl.exemple.org")["severity"], "warning")
        finally:
            self.nettoyer()

    def test_une_acceptation_perimee_s_efface(self):
        self.monde()
        try:
            self.ex("sensorium.accepter", wkey="ssl.exemple.org", raison="x", jours=30)
            self.n.executeur.contextes["sensorium"].stockage.ecrire("UPDATE sensorium_acceptations SET jusqua='2020-01-01 00:00:00'")
            self.assertEqual(next(x for x in self.etat()["rows"] if x["wkey"] == "ssl.exemple.org")["severity"], "warning")
        finally:
            self.nettoyer()

    def test_les_mesures_en_alerte_ouvrent_des_constats_apres_deux_releves(self):
        self.monde([r for r in MONDE if r["severity"] != "warning"])
        self.n.lancer("sensorium.monde")
        self.tick()                                          # ce que les bancs d'avant ont laissé d'ouvert se referme, et le compte des relevés en alerte repart de zéro
        self.monde()
        try:
            self.tick_monde(1)
            self.assertEqual(self.constats(), {}, "un seul relevé en alerte : pas encore un constat")
            self.tick_monde(1)
            c = self.constats()
            self.assertIn("ssl.exemple.org", c)
            self.assertIn("Certificat exemple.org : expire dans 12 jours", c["ssl.exemple.org"]["titre"])
            self.assertIn("disk./var.usage", c)
            self.assertNotIn("health.score", c, "un total de santé n'est pas une panne")
            self.assertNotIn("service.nginx", c)
        finally:
            self.nettoyer()

    def test_accepter_ferme_le_constat_et_une_maintenance_le_fait_taire(self):
        self.monde()
        try:
            self.tick_monde(2)
            self.assertIn("ssl.exemple.org", self.constats())
            self.ex("sensorium.accepter", wkey="ssl.exemple.org", raison="renouvellement en cours", jours=7)
            self.tick_monde(1)
            self.assertNotIn("ssl.exemple.org", self.constats())
            self.ex("sensorium.retirer_acceptation", wkey="ssl.exemple.org")
            self.tick_monde(1)
            self.assertIn("ssl.exemple.org", self.constats())
            r = self.ex("sensorium.fenetre_poser", portee="famille:ssl", debut=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - 3600)),
                        fin=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 3600)), motif="mise à jour du noyau")
            self.assertEqual(r["statut"], "faite", r)
            self.tick_monde(1)
            self.assertNotIn("ssl.exemple.org", self.constats())
            self.assertIn("disk./var.usage", self.constats(), "la fenêtre ne couvre que sa portée")
            ligne = next(x for x in self.etat()["rows"] if x["wkey"] == "ssl.exemple.org")
            self.assertEqual(ligne["maintenance"]["motif"], "mise à jour du noyau")
            self.assertEqual(ligne["severity"], "warning", "les relevés continuent : la mesure reste en alerte, c'est le constat qui se tait")
            self.ex("sensorium.fenetre_annuler", id=r["resultat"]["id"])
            self.tick_monde(1)
            self.assertIn("ssl.exemple.org", self.constats())
        finally:
            self.nettoyer()

    def test_une_fenetre_mal_formee_est_refusee(self):
        maintenant = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        demain = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 86400))
        for args in ({"portee": "tout le monde", "debut": maintenant, "fin": demain}, {"portee": "*", "debut": demain, "fin": maintenant},
                     {"portee": "*", "debut": "hier", "fin": demain},
                     {"portee": "*", "debut": maintenant, "fin": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 40 * 86400))}):
            r = self.ex("sensorium.fenetre_poser", **args)
            self.assertNotEqual(r["statut"], "faite", args)

    def test_les_fenetres_se_lisent_en_cours_a_venir_et_finies(self):
        t = time.time()
        f = lambda dt: time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(t + dt))
        try:
            a = self.ex("sensorium.fenetre_poser", portee="*", debut=f(-60), fin=f(3600), motif="en cours")["resultat"]["id"]
            b = self.ex("sensorium.fenetre_poser", portee="*", debut=f(7200), fin=f(10800), motif="à venir")["resultat"]["id"]
            l = self.ex("sensorium.fenetres")["resultat"]
            self.assertEqual([x["motif"] for x in l["vivantes"] if x["id"] in (a, b)], ["en cours", "à venir"])
            self.ex("sensorium.fenetre_annuler", id=a)
            l = self.ex("sensorium.fenetres")["resultat"]
            self.assertIn(a, [x["id"] for x in l["finies"]])
            self.assertNotIn(a, [x["id"] for x in l["vivantes"]])
        finally:
            self.nettoyer()

    def test_le_demon_se_lit_et_un_ancien_demon_se_reconnait(self):
        g = self.n.catalogue.get("sensorium.demon").faire.__globals__
        etat = {"version": "6.1-opt", "pid": 812, "duree_s": 500000, "passes": {"rapide": {"duree": 0.8}, "complete": {"duree": 52.0}}}
        with mock.patch.dict(g, {"json_de": lambda r, d=5.0: dict(etat)}):
            r = self.ex("sensorium.demon")["resultat"]
        self.assertFalse(r["muet"])
        self.assertEqual((r["pid"], r["passes"]["complete"]["duree"]), (812, 52.0))

        def ancien(requete, delai=5.0):
            raise RuntimeError("le collecteur a refusé la requête")
        with mock.patch.dict(g, {"json_de": ancien}):
            r = self.ex("sensorium.demon")["resultat"]
        self.assertTrue(r["ancien"] and not r["muet"])

        def muet(requete, delai=5.0):
            raise OSError("pas de socket")
        with mock.patch.dict(g, {"json_de": muet}):
            r = self.ex("sensorium.demon")["resultat"]
        self.assertTrue(r["muet"])
        self.assertIn("pas de socket", r["erreur"])

    def test_un_redemarrage_passe_par_le_courtier_et_se_raconte(self):
        ctx = self.n.executeur.contextes["sensorium"]
        appels = []

        def courtier(commande, args=(), stdin=None, delai=30):
            appels.append((commande, list(args), delai))
            return {"ok": True, "code": 0, "sortie": json.dumps({"ok": True, "silence_s": 6.2, "attendu_s": 38.0, "avant": {"pid": 10}, "apres": {"pid": 77, "version": "6.1-opt"}}), "erreur": ""}
        g = self.n.catalogue.get("sensorium.redemarrer").faire.__globals__
        with mock.patch.object(ctx, "racine", courtier), mock.patch.dict(g, {"json_de": lambda r, d=5.0: {"pid": 77}}):
            r = self.ex("sensorium.redemarrer", quand="apres_passe", motif="déploiement de la 0.1.12")
            self.assertEqual(r["statut"], "faite", r)
            self.assertEqual(appels, [("redemarrer", ["apres_passe"], 240)])
            self.assertEqual(r["resultat"]["silence_s"], 6.2)
            h = self.ex("sensorium.demon")["resultat"]["redemarrages"]
        self.assertEqual((h[0]["motif"], h[0]["resultat"], h[0]["qui"]), ("déploiement de la 0.1.12", "revenu", "root@exemple.test"))

    def test_un_redemarrage_qui_echoue_se_raconte_aussi(self):
        ctx = self.n.executeur.contextes["sensorium"]
        courtier = lambda commande, args=(), stdin=None, delai=30: {"ok": False, "code": 1, "sortie": json.dumps({"ok": False, "erreur": "le démon n'est pas revenu", "silence_s": 90.1}), "erreur": ""}
        g = self.n.catalogue.get("sensorium.redemarrer").faire.__globals__
        with mock.patch.object(ctx, "racine", courtier), mock.patch.dict(g, {"json_de": lambda r, d=5.0: {"pid": 0}}):
            r = self.ex("sensorium.redemarrer", quand="maintenant", motif="essai")
            self.assertNotEqual(r["statut"], "faite", r)
            h = self.ex("sensorium.demon")["resultat"]["redemarrages"]
        self.assertTrue(h[0]["resultat"].startswith("échec : le démon n'est pas revenu"), h[0])
        self.assertEqual(h[0]["silence_s"], 90.1)

    def test_un_mode_de_redemarrage_inconnu_est_refuse_avant_le_courtier(self):
        ctx = self.n.executeur.contextes["sensorium"]
        appels = []
        with mock.patch.object(ctx, "racine", lambda *a, **k: appels.append(a)):
            r = self.ex("sensorium.redemarrer", quand="sans attendre")
        self.assertNotEqual(r["statut"], "faite", r)
        self.assertEqual(appels, [])

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


MONDE = [
    {"wkey": "system.hostname", "value": "hote", "severity": "info", "observed_at": "2026-11-02T08:00:00Z", "detail": ""},
    {"wkey": "ssl.exemple.org", "value": "expire dans 12 jours", "severity": "warning", "observed_at": "2026-11-02T08:00:00Z",
     "detail": json.dumps({"causes_probables": ["le port 80 est fermé"]})},
    {"wkey": "disk./var.usage", "value": "82 %", "severity": "warning", "observed_at": "2026-11-02T08:00:00Z", "detail": ""},
    {"wkey": "service.nginx", "value": "active (running)", "severity": "info", "observed_at": "2026-11-02T08:00:00Z", "detail": ""},
    {"wkey": "health.score", "value": "92 · un certificat", "severity": "warning", "observed_at": "2026-11-02T08:00:00Z", "detail": ""},
]


class Lecture(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(DOSSIER))
        import CN_lecture
        self.lec = CN_lecture

    def test_une_mesure_se_dit_en_francais(self):
        l = self.lec.libelle
        self.assertEqual(l("ssl.exemple.org"), "Certificat exemple.org")
        self.assertEqual(l("service.nginx"), "Service nginx")
        self.assertEqual(l("machine.nas.mises_a_jour"), "Nas — mises à jour")
        self.assertEqual(l("outil_secu.trivy"), "Trivy — failles des images Docker")
        self.assertEqual(l("store.module.agenda"), "Base du module agenda")
        self.assertEqual(l("noyau.service"), "Noyau service")

    def test_chaque_mesure_a_sa_famille_et_son_domaine(self):
        f = self.lec.famille_de
        self.assertEqual(f("ssl.exemple.org"), "ssl")
        self.assertEqual(f("noyau.http"), "noyau")
        self.assertEqual(f("store.noyau"), "store")
        self.assertEqual(f("inconnu.x"), "autre")
        self.assertEqual(self.lec.domaine_de("ssl"), "certificats")
        self.assertEqual(self.lec.domaine_de("noyau"), "cassandra")
        tous = {fid for fid, _, _ in self.lec.FAMILLES}
        rangees = {fid for _, _, fs in self.lec.DOMAINES for fid in fs}
        self.assertEqual(tous, rangees, "chaque famille est dans un domaine, et un seul")

    def test_l_objet_dont_une_mesure_parle(self):
        o = self.lec.objet_de
        self.assertEqual(o("ssl.exemple.org"), ("Sites", "exemple.org"))
        self.assertEqual(o("ssl.*.exemple.org"), ("Sites", "exemple.org"))
        self.assertEqual(o("web.exemple.org"), ("Sites", "exemple.org"))
        self.assertEqual(o("service.nginx.service"), ("Services", "nginx"))
        self.assertEqual(o("docker.sondes"), ("Conteneurs", "sondes"))
        self.assertEqual(o("machine.nas.disque.D:"), ("Machines", "nas"))
        self.assertEqual(o("cle_ssh.deploy.4f2a"), ("Comptes et clés SSH", "deploy"))
        self.assertEqual(o("disk./var.usage", "hote"), ("Machines", "hote"))
        self.assertIsNone(o("disk./var.usage"))
        self.assertEqual(o("store.noyau")[0], "Cassandra")

    def test_une_alerte_acceptee_revient_quand_le_chiffre_monte(self):
        r = {"wkey": "disk./var.usage", "value": "82 %", "severity": "warning"}
        acq = {"disk./var.usage": {"valeur": "82 %", "raison": "archive", "jusqua": "", "par": "x"}}
        self.assertEqual(self.lec.appliquer_acquits([r], acq)[0]["severity"], "info")
        self.assertEqual(self.lec.appliquer_acquits([r], acq)[0]["acquit"]["raison"], "archive")
        self.assertEqual(self.lec.appliquer_acquits([dict(r, value="85 %")], acq)[0]["severity"], "warning")
        self.assertEqual(self.lec.appliquer_acquits([dict(r, value="70 %")], acq)[0]["severity"], "info")
        texte = {"service.x": {"valeur": "inactive"}}
        self.assertEqual(self.lec.appliquer_acquits([{"wkey": "service.x", "value": "inactive", "severity": "warning"}], texte)[0]["severity"], "info")
        self.assertEqual(self.lec.appliquer_acquits([{"wkey": "service.x", "value": "failed", "severity": "warning"}], texte)[0]["severity"], "warning")
        self.assertEqual(self.lec.appliquer_acquits([dict(r, severity="info")], acq)[0].get("acquit"), None)

    def test_une_fenetre_couvre_sa_portee_et_seulement_elle(self):
        f = [{"id": 1, "portee": "famille:ssl", "debut": "2026-11-02 01:00:00", "fin": "2026-11-02 03:00:00"},
             {"id": 2, "portee": "machine:nas", "debut": "2026-11-02 01:00:00", "fin": "2026-11-02 03:00:00"}]
        d = self.lec.dans_fenetre
        self.assertEqual(d("ssl.exemple.org", f, "2026-11-02 02:00:00")["id"], 1)
        self.assertIsNone(d("ssl.exemple.org", f, "2026-11-02 04:00:00"))              # finie
        self.assertIsNone(d("ssl.exemple.org", f, "2026-11-02 00:59:59"))              # pas commencée
        self.assertIsNone(d("service.nginx", f, "2026-11-02 02:00:00"))
        self.assertEqual(d("machine.nas.disque", f, "2026-11-02 02:00:00")["id"], 2)
        self.assertIsNone(d("machine.autre.disque", f, "2026-11-02 02:00:00"))
        tout = [{"id": 3, "portee": "*", "debut": "2026-11-02 01:00:00", "fin": "2026-11-02 03:00:00"}]
        self.assertEqual(d("service.nginx", tout, "2026-11-02 02:00:00")["id"], 3)
        dom = [{"id": 4, "portee": "domaine:certificats", "debut": "2026-11-02 01:00:00", "fin": "2026-11-02 03:00:00"}]
        self.assertEqual(d("ssl.exemple.org", dom, "2026-11-02 02:00:00")["id"], 4)
        self.assertIsNone(d("service.nginx", dom, "2026-11-02 02:00:00"))

    def test_une_reponse_du_collecteur_se_lit_sous_ses_formes(self):
        self.assertEqual(len(self.lec.lignes_du_monde(MONDE)), 5)
        self.assertEqual(len(self.lec.lignes_du_monde({"rows": MONDE})), 5)
        self.assertEqual(self.lec.lignes_du_monde("ERROR"), [])
        self.assertEqual(self.lec.lignes_du_monde([{"sans": "cle"}]), [])


class EtatDuDemon(Demon):
    def test_le_demon_dit_ce_qu_il_est(self):
        e = self.m.etat_du_demon()
        for cle in ("version", "pid", "demarre", "duree_s", "rss_mo", "base_octets", "passes", "retention_jours"):
            self.assertIn(cle, e)
        self.assertEqual(e["pid"], os.getpid())
        self.assertEqual(set(e["passes"]), {"rapide", "complete"})
        self.assertIsNone(e["passes"]["rapide"]["il_y_a_s"])               # aucune passe encore
        json.dumps(e)                                                      # et tout se sérialise : c'est la réponse d'une socket

    def test_une_passe_terminee_se_mesure(self):
        self.m._PASSES["complete"]["en_cours"] = True
        t0 = time.monotonic() - 3.0
        self.m._noter_passe("complete", t0)
        p = self.m.etat_du_demon()["passes"]["complete"]
        self.assertGreaterEqual(p["duree"], 3.0)
        self.assertEqual(p["n"], 1)
        self.assertFalse(p["en_cours"])
        self.assertLessEqual(p["il_y_a_s"], 1)

    def test_les_deux_nouvelles_commandes_repondent_sur_la_socket(self):
        """GET_DAEMON et GET_CORRELATIONS, par le vrai serveur de socket, sur un faux client (pas de socket Unix sous Windows)."""
        class Client:
            def __init__(self, requete):
                self.requete, self.envoye = requete.encode(), b""

            def settimeout(self, t):
                pass

            def recv(self, n):
                r, self.requete = self.requete, b""
                return r

            def sendall(self, d):
                self.envoye += d

            def close(self):
                pass
        srv = self.m.SharedMemorySocket()
        c = Client("GET_DAEMON")
        srv.handle_client(c)
        self.assertEqual(json.loads(c.envoye)["pid"], os.getpid())
        c = Client("GET_CORRELATIONS")
        srv.handle_client(c)
        self.assertIsInstance(json.loads(c.envoye), list)
        c = Client("GET_N_IMPORTE_QUOI")
        srv.handle_client(c)
        self.assertEqual(c.envoye, b"ERROR")                                # un démon d'avant une lecture répond ainsi : le module le reconnaît


def charger_commande():
    from importlib.machinery import SourceFileLoader
    chemin = str(DOSSIER / "commandes" / "CN_redemarrer")
    return SourceFileLoader("sensorium_redemarrer", chemin).load_module()


class CommandeRedemarrer(unittest.TestCase):
    def setUp(self):
        self.c = charger_commande()
        self.t = [0.0]
        self.sorties = []
        self.c.time = mock.Mock(monotonic=self._horloge, sleep=lambda s: self.t.__setitem__(0, self.t[0] + s))
        self.etats = []                                                      # ce que le démon répond, à la suite
        self.c.etat = lambda: self.etats.pop(0) if len(self.etats) > 1 else (self.etats[0] if self.etats else None)
        self.commandes = []

    def _horloge(self):
        self.t[0] += 0.3
        return self.t[0]

    def lance(self, mode, rc=0, sortie=""):
        self.c.sys = mock.Mock(argv=["redemarrer"] + ([mode] if mode else []), exit=lambda n: (_ for _ in ()).throw(SystemExit(n)))
        self.c.subprocess = mock.Mock(run=lambda args, **kw: (self.commandes.append(args), mock.Mock(returncode=rc, stdout=sortie, stderr=sortie))[1])
        lignes = []
        with mock.patch("builtins.print", lambda *a, **k: lignes.append(a[0])):
            try:
                self.c.main()
            except SystemExit as e:
                code = e.code
            else:
                code = None
        return code, json.loads(lignes[-1])

    def test_un_mode_hors_de_la_table_est_refuse_sans_rien_lancer(self):
        for mode in (None, "tout", "maintenant; rm -rf /", "../x"):
            code, d = self.lance(mode)
            self.assertEqual(code, 1)
            self.assertFalse(d["ok"])
        self.assertEqual(self.commandes, [])

    def test_un_redemarrage_reussi_dit_le_silence_et_les_deux_processus(self):
        self.etats = [{"pid": 10, "passes": {"rapide": {"en_cours": False}}}, {"pid": 10, "passes": {}}, {"pid": 77, "version": "6.1-opt", "passes": {}}]
        code, d = self.lance("maintenant")
        self.assertEqual(code, 0, d)
        self.assertTrue(d["ok"])
        self.assertEqual((d["avant"]["pid"], d["apres"]["pid"]), (10, 77))
        self.assertEqual(self.commandes, [["systemctl", "restart", "sensorium.service"]])

    def test_apres_la_passe_il_attend_qu_elle_finisse(self):
        en_cours = {"pid": 10, "passes": {"complete": {"en_cours": True}}}
        fini = {"pid": 10, "passes": {"complete": {"en_cours": False}}}
        self.etats = [en_cours, en_cours, en_cours, fini, {"pid": 99, "version": "x", "passes": {}}]
        code, d = self.lance("apres_passe")
        self.assertEqual(code, 0, d)
        self.assertGreaterEqual(d["attendu_s"], 2.0)
        self.assertEqual(len(self.commandes), 1)

    def test_un_demon_qui_ne_revient_pas_est_un_echec_qui_dit_le_silence(self):
        self.etats = [{"pid": 10, "passes": {}}, {"pid": 10, "passes": {}}, None]
        code, d = self.lance("maintenant")
        self.assertEqual(code, 1)
        self.assertFalse(d["ok"])
        self.assertIn("pas revenu", d["erreur"])
        self.assertGreater(d["silence_s"], 60)

    def test_un_systemctl_qui_echoue_est_un_echec(self):
        self.etats = [{"pid": 10, "passes": {}}]
        code, d = self.lance("maintenant", rc=1, sortie="Failed to restart")
        self.assertEqual(code, 1)
        self.assertIn("a échoué", d["erreur"])

    def test_un_demon_d_avant_qui_ne_dit_pas_son_etat_revient_quand_meme(self):
        self.etats = [None, None, {"pid": 5, "version": "x", "passes": {}}]
        code, d = self.lance("maintenant")
        self.assertEqual(code, 0, d)


class Branchement(unittest.TestCase):
    """L'écran du Sensorium est bien branché : son script est servi, le menu lui donne ses sous-entrées, le shell remplace l'onglet V18."""
    def lire(self, *chemin):
        return (RACINE.joinpath(*chemin)).read_text(encoding="utf-8")

    def test_le_script_est_charge_par_la_page_et_par_l_assembleur(self):
        self.assertIn('<script src="/sensorium-ecran.js"></script>', self.lire("interface", "CN_index.html"))
        self.assertIn('<script src="/sensorium-ecran.js"></script>', self.lire("outils", "ui", "CN_assembler.py"))
        self.assertTrue((RACINE / "interface" / "CN_sensorium-ecran.js").is_file())

    def test_le_shell_remplace_l_onglet_v18_sans_le_supprimer(self):
        shell = self.lire("interface", "CN_shell.js")
        self.assertIn('remplacerV18("sensorium", "sensorium")', shell)
        self.assertIn("CASS.sceneSurMesure.sensorium", self.lire("interface", "CN_sensorium-ecran.js"))
        self.assertIn("function snRendre", self.lire("interface", "CN_app.js"), "le code V18 reste en place : rien n'est retiré sans validation")

    def test_le_menu_donne_au_sensorium_toutes_ses_vues(self):
        sys.path.insert(0, str(RACINE / "modules" / "affichage" / "points"))
        import importlib
        spec = importlib.util.spec_from_file_location("ec_disposition_sensorium", RACINE / "modules" / "affichage" / "points" / "EC_disposition.py")
        ec = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ec)
        entree = next(e for e in ec.ENTREES if e["id"] == "sensorium") if hasattr(ec, "ENTREES") else None
        if entree is None:
            texte = self.lire("modules", "affichage", "points", "EC_disposition.py")
            for v in ("maintenant", "changements", "capteurs", "carte", "demon", "maintenance", "comparer", "alertes"):
                self.assertIn('("%s", ' % v, texte[texte.index('"id": "sensorium"'):texte.index('"id": "historique"')])
        else:
            self.assertEqual([v[0] for v in entree["vues"]], ["maintenant", "changements", "capteurs", "carte", "demon", "maintenance", "comparer", "alertes"])

    def test_les_vues_du_menu_sont_celles_que_l_ecran_connait(self):
        ecran = self.lire("interface", "CN_sensorium-ecran.js")
        for v in ("maintenant", "changements", "capteurs", "carte", "demon", "maintenance", "comparer", "alertes"):
            self.assertIn('["%s", ' % v, ecran)

    def test_le_script_a_une_syntaxe_valide(self):
        if not shutil.which("node"):
            self.skipTest("node n'est pas installé")
        r = subprocess.run(["node", "--check", str(RACINE / "interface" / "CN_sensorium-ecran.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


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
