"""Bancs du pont FastPanel : un faux panneau (API HTTP avec état + base SQLite au schéma réel) et le module branché dans un vrai noyau."""
import json
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

import CN_main as moteur                      # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402
import importlib.util                      # noqa: E402

JETON = "jwt-" + "x" * 40


def charger_module():
    spec = importlib.util.spec_from_file_location("fastpanel_mod", RACINE / "modules" / "fastpanel" / "CN_module.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FauxPanneau:
    """L'API du panneau, avec un état. Connexion par /api/login (les autres chemins répondent 404, comme le vrai), jeton exigé ailleurs."""

    def __init__(self, prefixe="/api"):
        self.prefixe = prefixe                 # "" : une façade qui retire /api avant de transmettre
        self.utilisateur, self.mdp = "cassandra", "mdp-de-test"
        self.refuse = False
        self.expirer_une_fois = False
        self.requetes = []
        self.services = [{"id": 1, "name": "nginx", "state": "active"}, {"id": 2, "name": "mysql", "state": "active"},
                         {"id": 3, "name": "exim", "service": "exim4", "state": "inactive"}]
        self.bases = [{"id": 10, "name": "existante"}]
        self.suite = 11
        self.certs = [{"id": 5, "common_name": "a.exemple.fr", "alternative_name": "www.a.exemple.fr", "issued_at": "2026-08-01T00:00:00Z"}]
        self.stockages, self.plans = [], []
        self.regles = [{"id": 1, "name": "SSH", "port_range": "22", "proto": "TCP", "type": "INPUT", "policy": "ACCEPT", "rules": []}]
        self.politique, self.suite_regle = "ACCEPT", 2
        self.renouvelle = True
        faux = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def _rep(self, code, corps=None):
                d = json.dumps(corps if corps is not None else {}).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(d)))
                self.end_headers()
                self.wfile.write(d)

            def _corps(self):
                n = int(self.headers.get("Content-Length") or 0)
                return json.loads(self.rfile.read(n).decode()) if n else {}

            def _faire(self, methode):
                corps = self._corps()
                chemin = self.path
                faux.requetes.append((methode, chemin, corps, self.headers.get("Authorization", "")))
                if faux.prefixe == "" and chemin.startswith("/api/"):
                    return self._rep(404, {"erreur": "inconnu"})
                if faux.prefixe == "/api" and not chemin.startswith("/api/"):
                    return self._rep(404, {"erreur": "inconnu"})
                p = chemin[len(faux.prefixe):] if faux.prefixe and chemin.startswith(faux.prefixe) else chemin
                if methode == "POST" and p == "/login":
                    if faux.refuse or corps.get("username") != faux.utilisateur or corps.get("password") != faux.mdp:
                        return self._rep(401, {"erreur": "refusé"})
                    return self._rep(200, {"data": {"token": JETON}})
                if methode == "POST" and p in ("/authorization", "/v1/login", "/auth"):
                    return self._rep(404)
                if self.headers.get("Authorization") != "Bearer " + JETON or faux.expirer_une_fois:
                    faux.expirer_une_fois = False
                    return self._rep(401, {"erreur": "jeton"})
                return self.route(methode, p, corps)

            def route(self, m, p, corps):
                if m == "GET" and p == "/services":
                    return self._rep(200, {"data": faux.services})
                if m == "PUT" and p.startswith("/services/"):
                    ident, action = p.split("/")[2], p.split("/")[3]
                    s = next(x for x in faux.services if str(x["id"]) == ident)
                    s["state"] = {"start": "active", "restart": "active", "stop": "inactive"}[action]
                    return self._rep(200, {})
                if m == "GET" and p == "/firewall/ports":
                    return self._rep(200, {"data": faux.regles})
                if m == "GET" and p == "/firewall/policy":
                    return self._rep(200, {"data": {"policy": faux.politique}})
                if m == "PUT" and p == "/firewall/policy":
                    faux.politique = corps["policy"]
                    return self._rep(200, {})
                if m == "PUT" and p == "/firewall/ports":
                    r = dict(corps["port"], id=faux.suite_regle)
                    faux.suite_regle += 1
                    faux.regles.append(r)
                    return self._rep(200, {"data": {"id": r["id"]}})
                if m == "PUT" and p.startswith("/firewall/ports/"):
                    rid = int(p.split("/")[3])
                    faux.regles = [dict(corps["port"], id=rid) if x["id"] == rid else x for x in faux.regles]
                    return self._rep(200, {"data": {"id": rid}})
                if m == "DELETE" and p.startswith("/firewall/ports/"):
                    faux.regles = [x for x in faux.regles if x["id"] != int(p.split("/")[3])]
                    return self._rep(204)
                if m == "GET" and p == "/databases":
                    return self._rep(200, {"data": faux.bases})
                if m == "GET" and p == "/databases/servers":
                    return self._rep(200, {"data": [{"id": 1, "name": "MySQL", "use_as_default": True}]})
                if m == "GET" and p == "/databases/servers/1/users":
                    return self._rep(200, {"data": [{"id": 7, "login": "deja"}]})
                if m == "POST" and p == "/databases":
                    faux.bases.append({"id": faux.suite, "name": corps["name"]})
                    faux.suite += 1
                    return self._rep(200, {})            # asynchrone : pas d'identifiant rendu
                if m == "DELETE" and p.startswith("/databases/"):
                    faux.bases = [b for b in faux.bases if str(b["id"]) != p.split("/")[2]]
                    return self._rep(204)
                if m == "GET" and p == "/certificates":
                    return self._rep(200, {"data": faux.certs})
                if m == "PUT" and p == "/certificates/5/renew/external":
                    if faux.renouvelle:
                        faux.certs[0]["issued_at"] = "2026-10-12T00:00:00Z"
                    return self._rep(200, {})
                if m == "GET" and p == "/backups/accounts":
                    return self._rep(200, {"data": faux.stockages})
                if m == "POST" and p == "/backups/accounts":
                    faux.stockages.append({"id": 3, "name": corps["name"], "type": corps["type"], "path": corps["path"]})
                    return self._rep(200, {"data": {"id": 3}})
                if m == "DELETE" and p == "/backups/accounts/3":
                    faux.stockages = []
                    return self._rep(204)
                if m == "GET" and p == "/v2/backup/plans":
                    return self._rep(200, {"data": faux.plans})
                if m == "POST" and p in ("/v2/backup/plans/full", "/v2/backup/plans"):
                    faux.plans.append({"id": 9, "name": corps["name"], "corps": corps})
                    return self._rep(200, {"data": {"id": 9}})
                if m == "DELETE" and p == "/v2/backup/plans/9":
                    faux.plans = []
                    return self._rep(204)
                return self._rep(404)

            def do_GET(self):
                self._faire("GET")

            def do_POST(self):
                self._faire("POST")

            def do_PUT(self):
                self._faire("PUT")

            def do_DELETE(self):
                self._faire("DELETE")

        self.serveur = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.serveur.daemon_threads = True
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.serveur.server_address[1]

    def arreter(self):
        self.serveur.shutdown()
        self.serveur.server_close()


def construire_base(chemin, maintenant=None):
    """Une base FastPanel 2 miniature, au schéma réel (celui que la V18 a relevé)."""
    maintenant = maintenant or datetime.now()
    d = lambda j, m=0: (maintenant + timedelta(days=j, minutes=m)).strftime("%Y-%m-%d %H:%M:%S")
    c = sqlite3.connect(chemin)
    c.executescript("""
    CREATE TABLE panel_account(id INTEGER PRIMARY KEY, username TEXT, home_dir TEXT, status TEXT, roles TEXT, ssh_access INT, quota_value INT, restore_email TEXT, created_at TEXT);
    CREATE TABLE certificate(id INTEGER PRIMARY KEY, expired_at TEXT, expires INT);
    CREATE TABLE site(id INTEGER PRIMARY KEY, domain TEXT, owner_id INT, status TEXT, certificate_id INT);
    CREATE TABLE website_backends(id INTEGER PRIMARY KEY, frontend_id INT, handler TEXT, handler_version TEXT, main INT, type TEXT);
    CREATE TABLE site_stats(site_id INT, error_count INT, status_code INT, size INT, databases_size INT);
    CREATE TABLE db(id INTEGER PRIMARY KEY, name TEXT, engine TEXT, size INT, owner_id INT, site_id INT, charset TEXT, created_at TEXT, dump_at TEXT);
    CREATE TABLE database_user(id INTEGER PRIMARY KEY, login TEXT);
    CREATE TABLE datbases_users(database_id INT, user_id INT);
    CREATE TABLE ftp_account(id INTEGER PRIMARY KEY, name TEXT, home_dir TEXT, enabled INT, owner_id INT, virtualhost_id INT, created TEXT);
    CREATE TABLE email_domain(id INTEGER PRIMARY KEY, name TEXT);
    CREATE TABLE mailboxes(id INTEGER PRIMARY KEY, address TEXT, quota INT, size INT, enabled INT, domain_id INT);
    CREATE TABLE domain(id INTEGER PRIMARY KEY, name TEXT);
    CREATE TABLE record(id INTEGER PRIMARY KEY, domain_id INT, name TEXT, type TEXT, value TEXT, ttl INT);
    CREATE TABLE backup_account(id INTEGER PRIMARY KEY, name TEXT, type TEXT);
    CREATE TABLE backup_plan_v2(id INTEGER PRIMARY KEY, name TEXT, account_id INT, owner_id INT);
    CREATE TABLE backup_copy_v2(id INTEGER PRIMARY KEY, plan_id INT, action TEXT, total_uploaded INT, total_source INT, start_at TEXT, end_at TEXT, total_file_count INT, partial INT, copied_user TEXT, dbs TEXT);
    """)
    c.executemany("INSERT INTO panel_account VALUES(?,?,?,?,?,?,?,?,?)", [(1, "alice", "/var/www/alice", "active", "user", 1, 5 * 1073741824, "a@x.fr", "2026-01-01 10:00:00"), (2, "bob", "/var/www/bob", "active", "user", 0, 0, "", "2026-02-01 10:00:00")])
    c.executemany("INSERT INTO certificate VALUES(?,?,?)", [(1, d(90), 90), (2, d(10), 90), (3, d(-5), 90), (4, "", 90)])
    c.executemany("INSERT INTO site VALUES(?,?,?,?,?)", [
        (1, "ok.exemple.fr", 1, "1", 1), (2, "proche.exemple.fr", 1, "1", 2), (3, "echu.exemple.fr", 2, "1", 3), (4, "sans.exemple.fr", 2, "1", None),
        (5, "inconnu.exemple.fr", 2, "1", 4), (6, "_", 2, "1", None), (7, "proxy.exemple.fr", 2, "1", None)])
    c.executemany("INSERT INTO website_backends VALUES(?,?,?,?,?,?)", [(1, 1, "php_fpm", "83", 1, "php"), (2, 2, "php_fpm", "74", 1, "php"), (3, 3, "mpm_itk", "81", 1, "php"), (4, 7, "reverse_proxy", "", 1, "reverse_proxy"), (5, 4, "php_fpm", "", 1, "php")])
    c.execute("INSERT INTO site_stats VALUES(1, 2, 200, 10485760, 5242880)")
    c.executemany("INSERT INTO db VALUES(?,?,?,?,?,?,?,?,?)", [(1, "wp_ok", "mysql", 3145728, 1, 1, "utf8mb4", "2026-03-01 00:00:00", "2026-10-01 00:00:00")])
    c.execute("INSERT INTO database_user VALUES(1,'wp_user')")
    c.execute("INSERT INTO datbases_users VALUES(1,1)")
    c.execute("INSERT INTO ftp_account VALUES(1,'ftpalice','/var/www/alice',1,1,1,'2026-03-01')")
    c.execute("INSERT INTO email_domain VALUES(1,'exemple.fr')")
    c.executemany("INSERT INTO mailboxes VALUES(?,?,?,?,?,?)", [(1, "contact@exemple.fr", 1073741824, 52428800, 1, 1), (2, "off@exemple.fr", 0, 0, 0, 1)])
    c.execute("INSERT INTO domain VALUES(1,'exemple.fr')")
    c.execute("INSERT INTO record VALUES(1,1,'@','A','192.0.2.1',300)")
    c.execute("INSERT INTO backup_account VALUES(1,'local','local')")
    c.execute("INSERT INTO backup_plan_v2 VALUES(1,'nuit',1,1)")
    c.executemany("INSERT INTO backup_copy_v2 VALUES(?,?,?,?,?,?,?,?,?,?,?)", [
        (1, 1, "backup", 2097152, 4194304, d(-1), d(-1, 5), 120, 0, "alice", '[{"name":"wp_ok"}]'),
        (2, 1, "backup", 1048576, 1048576, d(-30), d(-30, 5), 10, 0, "bob", "[]"),
        (3, 1, "error", 0, 0, d(-1), "", 0, 0, "bob", "[]")])
    c.commit()
    c.close()


class Base(unittest.TestCase):
    def setUp(self):
        self.mod = charger_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.faux = FauxPanneau()
        self.addCleanup(self.faux.arreter)
        self.db = self.base / "fastpanel2.db"
        construire_base(self.db)

    def noyau(self, **regl):
        mods = self.base / "modules"
        shutil.copytree(RACINE / "modules" / "fastpanel", mods / "fastpanel", dirs_exist_ok=True)
        n = moteur.Noyau(self.base / "d", mods, {}, gerer_modules=True)
        n.brancher()
        self.assertTrue(n.activer("fastpanel")["ok"])
        valeurs = {"url": self.faux.url, "utilisateur": self.faux.utilisateur, "mot_de_passe": self.faux.mdp, "base_panneau": str(self.db)}
        valeurs.update(regl)
        self.n, self.e = n, n.executeur.executer
        self.poser(valeurs)
        return n

    def poser(self, valeurs):
        for k, v in valeurs.items():
            self.n.reglages.poser("fastpanel." + k, v)

    def lire(self, cap, **args):
        return self.e("fastpanel." + cap, "cassandra", args, compte="")

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]


class Connexion(Base):
    def test_la_connexion_ouvre_une_session_et_l_envoie_sur_les_appels(self):
        self.noyau()
        r = self.lire("services")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual({s["nom"] for s in r["resultat"]}, {"nginx", "mysql", "exim"})
        self.assertTrue(any(q[3] == "Bearer " + JETON for q in self.faux.requetes))

    def test_exim_n_est_compte_qu_une_fois_et_garde_son_alias(self):
        self.noyau()
        s = {x["nom"]: x for x in self.lire("services")["resultat"]}
        self.assertIn("exim4", s["exim"]["alias"])
        self.assertFalse(s["exim"]["actif"])

    def test_mauvais_mot_de_passe_est_un_acces_refuse(self):
        self.noyau(mot_de_passe="faux")
        s = self.lire("sante")["resultat"]
        self.assertFalse(s["api"]["ok"])
        self.assertEqual(s["api"]["genre"], "acces_refuse")

    def test_le_mot_de_passe_ne_sort_pas_dans_les_erreurs(self):
        self.noyau(mot_de_passe="faux-secret-xyz")
        s = json.dumps(self.lire("sante"))
        self.assertNotIn("faux-secret-xyz", s)

    def test_sans_identifiants_c_est_non_configure(self):
        self.noyau(utilisateur="", mot_de_passe="")
        self.assertEqual(self.lire("sante")["resultat"]["api"]["genre"], "non_configure")

    def test_une_facade_qui_retire_le_prefixe_api_fonctionne_aussi(self):
        self.faux.prefixe = ""
        self.noyau()
        r = self.lire("services")
        self.assertEqual(r["statut"], "faite", r)

    def test_une_session_expiree_est_rouverte_une_fois(self):
        self.noyau()
        self.lire("services")
        self.faux.expirer_une_fois = True
        self.assertEqual(self.lire("services")["statut"], "faite")

    def test_une_adresse_choisie_est_la_seule_essayee(self):
        self.noyau(url="http://127.0.0.1:9")
        s = self.lire("sante")["resultat"]["api"]
        self.assertEqual(s["genre"], "injoignable")
        self.assertEqual(self.faux.requetes, [])

    def test_un_jeton_fixe_remplace_le_compte(self):
        self.noyau(utilisateur="", mot_de_passe="", jeton=JETON)
        self.assertEqual(self.lire("services")["statut"], "faite")
        self.assertFalse(any(q[1].endswith("/login") for q in self.faux.requetes))

    def test_un_booleen_de_formulaire_s_ecrit_en_minuscules(self):
        self.assertEqual(self.mod._formulaire({"a": True, "b": False, "c": None, "d": 3}), b"a=true&b=false&c=&d=3")

    def test_une_page_html_est_reconnue_comme_telle(self):
        self.assertIn("HTML", self.mod._diag("<!DOCTYPE html><html>"))
        self.assertIn("Cloudflare", self.mod._diag("<title>Just a moment</title> cloudflare"))
        self.assertEqual(self.mod._diag('{"a":1}'), "")


class Lectures(Base):
    def setUp(self):
        super().setUp()
        self.noyau()

    def test_les_comptes_avec_leurs_decomptes(self):
        u = {x["compte"]: x for x in self.lire("utilisateurs")["resultat"]}
        self.assertEqual((u["alice"]["sites"], u["alice"]["bases"], u["alice"]["ssh"], u["alice"]["quota_go"]), (2, 1, True, 5.0))
        self.assertIsNone(u["bob"]["quota_go"])

    def test_les_quatre_etats_de_certificat_et_les_hotes_invalides_ecartes(self):
        s = {x["domaine"]: x["ssl"]["etat"] for x in self.lire("sites")["resultat"]}
        self.assertEqual(s, {"ok.exemple.fr": "actif", "proche.exemple.fr": "proche", "echu.exemple.fr": "echu", "sans.exemple.fr": "aucun",
                             "inconnu.exemple.fr": "inconnu", "proxy.exemple.fr": "aucun"})
        self.assertNotIn("_", s)

    def test_php_normalise_et_statistiques(self):
        s = {x["domaine"]: x for x in self.lire("sites")["resultat"]}
        self.assertEqual((s["ok.exemple.fr"]["php"], s["ok.exemple.fr"]["gestionnaire"]), ("8.3", "php_fpm"))
        self.assertEqual((s["ok.exemple.fr"]["fichiers_mo"], s["ok.exemple.fr"]["erreurs"]), (10.0, 2))

    def test_les_bases_avec_proprietaire_site_et_utilisateurs(self):
        b = self.lire("bases")["resultat"][0]
        self.assertEqual((b["nom"], b["proprietaire"], b["site"], b["utilisateurs"], b["taille_mo"]), ("wp_ok", "alice", "ok.exemple.fr", "wp_user", 3.0))

    def test_ftp_mail_dns(self):
        self.assertEqual(self.lire("ftp")["resultat"][0]["site"], "ok.exemple.fr")
        m = {x["adresse"]: x for x in self.lire("mail")["resultat"]}
        self.assertEqual((m["contact@exemple.fr"]["quota_mo"], m["contact@exemple.fr"]["statut"], m["off@exemple.fr"]["statut"]), (1024.0, "active", "suspendue"))
        self.assertEqual(self.lire("dns")["resultat"][0]["zone"], "exemple.fr")

    def test_les_copies_ont_un_etat_deduit(self):
        c = self.lire("sauvegardes")["resultat"]
        self.assertEqual(sorted(x["etat"] for x in c), ["echec", "reussie", "reussie"])
        reussie = next(x for x in c if x["compte"] == "alice")
        self.assertEqual((reussie["duree_min"], reussie["bases"], reussie["destination"]), (5, ["wp_ok"], "local (local)"))

    def test_une_base_introuvable_leve_une_erreur_et_ne_rend_pas_une_liste_vide(self):
        self.poser({"base_panneau": str(self.base / "absente.db")})
        r = self.lire("sites")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("introuvable", json.dumps(r))

    def test_un_schema_inconnu_est_dit_et_pas_lu_comme_un_zero(self):
        c = sqlite3.connect(self.db)
        c.execute("ALTER TABLE site RENAME TO sites_v3")
        c.commit()
        c.close()
        r = self.lire("sites")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("table « site »", json.dumps(r, ensure_ascii=False))

    def test_la_base_n_est_jamais_modifiee(self):
        avant = self.db.read_bytes()
        self.lire("sites")
        self.lire("sauvegardes")
        self.assertEqual(avant, self.db.read_bytes())

    def test_seul_un_select_se_lit(self):
        with self.assertRaises(self.mod.PontErreur):
            self.mod._requete("DELETE FROM site")

    def test_sante_dit_d_ou_vient_chaque_reponse(self):
        s = self.lire("sante")["resultat"]
        self.assertTrue(s["api"]["ok"] and s["base_panneau"]["ok"])
        self.assertEqual(s["base_panneau"]["chemin"], str(self.db))

    def test_certificats_et_audit_php(self):
        a = self.lire("certificats")["resultat"]
        self.assertEqual((a["echus"], [x["domaine"] for x in a["proches"]], a["inconnus"]), (["echu.exemple.fr"], ["proche.exemple.fr"], ["inconnu.exemple.fr"]))
        p = self.lire("php")["resultat"]
        self.assertEqual({x["domaine"] for x in p["fin_de_support"]}, {"proche.exemple.fr", "echu.exemple.fr"})
        self.assertEqual(p["version_non_lue"][0]["domaine"], "sans.exemple.fr")

    def test_audit_des_sauvegardes_absente_et_perimee(self):
        a = self.lire("audit")["resultat"]["sauvegardes"]
        # alice : copie d'hier ; bob : une copie à -30 j (périmée), l'échec d'hier ne compte pas ; le proxy est écarté
        self.assertEqual(a["sans"], [])
        self.assertEqual({x["domaine"] for x in a["perimees"]}, {"echu.exemple.fr", "sans.exemple.fr", "inconnu.exemple.fr"})
        self.assertNotIn("proxy.exemple.fr", a["sans"] + [x["domaine"] for x in a["perimees"]])

    def test_ssl_sonder_refuse_un_nom_invalide(self):
        self.assertEqual(self.lire("ssl_sonder", domaine="pas un nom")["statut"], "echec")


class Surveillance(Base):
    def setUp(self):
        super().setUp()
        self.noyau()

    def releve(self):
        self.n.lancer("fastpanel.releve")

    def etat_service(self, nom):
        o = self.n.registre.lire("fastpanel_service", nom, portee=TOUT)
        return o["etat"] if o else None

    def test_la_releve_pose_le_panneau_et_ses_services(self):
        self.releve()
        i = self.n.registre.lire("fastpanel", "principal", portee=TOUT)
        self.assertEqual(i["etat"], "ok")
        self.assertEqual(i["donnees"]["services"]["total"], 3)
        self.assertEqual((self.etat_service("nginx"), self.etat_service("exim")), ("actif", "arrete"))

    def test_un_service_arrete_depuis_toujours_ne_dit_rien(self):
        self.releve()
        self.releve()
        self.assertEqual(self.evts("fastpanel.service_tombe"), [])

    def test_un_service_actif_qui_s_arrete_seul_est_signale_une_fois_puis_revient(self):
        self.releve()
        self.faux.services[0]["state"] = "inactive"
        self.releve()
        self.releve()
        self.assertEqual(self.etat_service("nginx"), "tombe")
        self.assertEqual(len(self.evts("fastpanel.service_tombe")), 1)
        self.n.tick()
        self.assertTrue(any("nginx" in json.dumps(e, ensure_ascii=False) for e in self.evts("constat.ouvert")))
        self.faux.services[0]["state"] = "active"
        self.releve()
        self.assertEqual(self.etat_service("nginx"), "actif")
        self.assertEqual(len(self.evts("fastpanel.service_revenu")), 1)
        self.n.tick(time.time() + 100)
        self.assertTrue(any("nginx" in json.dumps(e, ensure_ascii=False) for e in self.evts("constat.resolu")))

    def test_un_service_en_cours_de_demande_n_est_pas_juge(self):
        self.releve()
        self.n.executeur.contextes["fastpanel"].poser("fastpanel_service", "mysql", "mysql", etat="demande", donnees={"id": "2", "demande_t": time.time()})
        self.faux.services[1]["state"] = "inactive"
        self.releve()
        self.assertEqual(self.etat_service("mysql"), "demande")
        self.assertEqual(self.evts("fastpanel.service_tombe"), [])

    def test_une_demande_oubliee_se_resynchronise(self):
        self.releve()
        self.n.executeur.contextes["fastpanel"].poser("fastpanel_service", "mysql", "mysql", etat="demande", donnees={"id": "2", "demande_t": time.time() - 3600})
        self.releve()
        self.assertEqual(self.etat_service("mysql"), "actif")

    def test_le_panneau_injoignable_puis_la_reprise(self):
        self.poser({"url": "http://127.0.0.1:9"})
        self.releve()
        self.assertEqual(self.n.registre.lire("fastpanel", "principal", portee=TOUT)["etat"], "injoignable")
        self.assertEqual(len(self.evts("fastpanel.injoignable")), 1)
        self.releve()
        self.assertEqual(len(self.evts("fastpanel.injoignable")), 1)             # pas de répétition
        self.poser({"url": self.faux.url})
        self.releve()
        self.assertEqual(len(self.evts("fastpanel.reprise")), 1)

    def test_identifiants_refuses_donne_acces_refuse(self):
        self.poser({"mot_de_passe": "faux"})
        self.releve()
        self.assertEqual(self.n.registre.lire("fastpanel", "principal", portee=TOUT)["etat"], "refuse")
        self.assertEqual(len(self.evts("fastpanel.acces_refuse")), 1)

    def test_non_configure(self):
        self.poser({"utilisateur": "", "mot_de_passe": ""})
        self.releve()
        self.assertEqual(self.n.registre.lire("fastpanel", "principal", portee=TOUT)["etat"], "non_configure")

    def test_l_audit_est_calcule_meme_quand_l_api_se_tait(self):
        self.poser({"url": "http://127.0.0.1:9"})
        self.releve()
        a = self.n.registre.lire("fastpanel", "principal", portee=TOUT)["donnees"]["audit"]
        self.assertEqual(a["certificats"]["echus"], ["echu.exemple.fr"])


class Actions(Base):
    def setUp(self):
        super().setUp()
        self.noyau()
        # le module branché par le noyau est une autre instance du fichier : on règle ses constantes dans ses globales
        g = self.n.catalogue.get("fastpanel.sante").faire.__globals__
        g["ATTENTE_SERVICE_S"], g["ATTENTE_SSL_S"], g["PAS_ATTENTE_S"] = 1, 1, 0.1

    def etat(self, nom):
        return next(s["state"] for s in self.faux.services if s["name"] == nom)

    def faire(self, cap, **args):
        return self.e("fastpanel." + cap, "humain", args, compte="")

    def retour(self, cap, res):
        self.n.catalogue.get("fastpanel." + cap).defaire(self.n.executeur.contextes["fastpanel"], res)

    def test_redemarrer_un_service_est_prouve(self):
        r = self.faire("service_relancer", service="mysql", action="restart")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        self.assertEqual(self.etat("mysql"), "active")

    def test_arreter_un_service_est_prouve_et_le_retour_le_relance(self):
        r = self.faire("service_arreter", service="mysql")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.etat("mysql"), "inactive")
        self.assertEqual(self.n.registre.lire("fastpanel_service", "mysql", portee=TOUT)["etat"], "arrete")       # voulu : pas une panne
        self.retour("service_arreter", r["resultat"])
        self.assertEqual(self.etat("mysql"), "active")
        self.assertEqual(self.n.registre.lire("fastpanel_service", "mysql", portee=TOUT)["etat"], "actif")

    def test_un_arret_voulu_ne_declenche_pas_d_alerte_a_la_releve_suivante(self):
        self.faire("service_arreter", service="mysql")
        self.n.lancer("fastpanel.releve")
        self.assertEqual(self.evts("fastpanel.service_tombe"), [])

    def test_un_service_qui_ne_change_pas_d_etat_est_annule(self):
        class Fige(dict):
            def __setitem__(self, k, v):
                if k != "state":
                    super().__setitem__(k, v)
        self.faux.services[1] = Fige(self.faux.services[1])
        r = self.faire("service_arreter", service="mysql")
        self.assertEqual(r["statut"], "annulee", r)

    def test_un_service_inconnu_ou_un_nom_dangereux_est_refuse(self):
        self.assertEqual(self.faire("service_relancer", service="inconnu")["statut"], "echec")
        self.assertEqual(self.faire("service_relancer", service="a; rm -rf /")["statut"], "echec")
        self.assertEqual(self.faire("service_relancer", service="nginx", action="disable")["statut"], "echec")
        self.assertEqual([q for q in self.faux.requetes if q[0] == "PUT"], [])

    def test_cassandra_au_palier_raconter_ne_touche_a_rien(self):
        r = self.e("fastpanel.service_arreter", "cassandra", {"service": "mysql"}, compte="")
        self.assertEqual(r["statut"], "racontee")
        self.assertEqual(self.etat("mysql"), "active")

    def test_un_arret_n_atteint_pas_le_palier_maitre(self):
        self.assertNotIn("maitre", self.n.catalogue.get("fastpanel.service_arreter").capacite.paliers)

    def test_renouveler_un_certificat_est_prouve_par_la_date_d_emission(self):
        r = self.faire("ssl_renouveler", domaine="www.a.exemple.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        self.assertEqual([e["donnees"]["domaine"] for e in self.evts("fastpanel.certificat_renouvele")], ["a.exemple.fr"])

    def test_un_renouvellement_sans_effet_n_est_pas_un_succes(self):
        self.faux.renouvelle = False
        self.assertIn(self.faire("ssl_renouveler", domaine="a.exemple.fr")["statut"], ("annulee", "annulation_impossible"))
        self.assertEqual(self.evts("fastpanel.certificat_renouvele"), [])

    def test_un_domaine_sans_certificat_au_panneau_est_refuse(self):
        self.assertEqual(self.faire("ssl_renouveler", domaine="autre.exemple.fr")["statut"], "echec")

    def test_creer_une_base_rend_le_mot_de_passe_une_fois_et_le_tait_au_journal(self):
        r = self.faire("base_creer", nom="neuve", proprietaire_id=1)
        self.assertEqual(r["statut"], "faite", r)
        res = r["resultat"]
        self.assertEqual((res["nom"], res["utilisateur"]), ("neuve", "neuve"))
        self.assertGreaterEqual(len(res["mot_de_passe"]), 20)
        self.assertIn("neuve", [b["name"] for b in self.faux.bases])
        corps = [q[2] for q in self.faux.requetes if q[0] == "POST" and q[1].endswith("/databases")][0]
        self.assertEqual((corps["charset"], corps["user"]["allow_remote_connection"]), ("utf8mb4", False))
        journal = json.dumps(self.n.bus.recents(portee=TOUT, limite=900), ensure_ascii=False, default=str)
        self.assertNotIn(res["mot_de_passe"], journal)

    def test_le_retour_d_une_creation_supprime_cette_base_et_elle_seule(self):
        r = self.faire("base_creer", nom="neuve", proprietaire_id=1)
        self.retour("base_creer", r["resultat"])
        self.assertEqual([b["name"] for b in self.faux.bases], ["existante"])

    def test_les_bases_invalides_ou_existantes_sont_refusees(self):
        for args in ({"nom": "a b"}, {"nom": "x" * 65}, {"nom": "existante"}, {"nom": "ok", "nouvel_utilisateur": "mauvais nom"}, {"nom": "ok", "nouvel_utilisateur": "deja"}):
            self.assertEqual(self.faire("base_creer", proprietaire_id=1, **args)["statut"], "echec", args)
        self.assertEqual([q for q in self.faux.requetes if q[0] == "POST" and q[1].endswith("/databases")], [])

    def test_declarer_un_stockage_local_puis_le_retirer(self):
        r = self.faire("stockage_local_creer", nom="filet", chemin="/var/backups/panneau")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.faux.stockages[0]["path"], "/var/backups/panneau")
        self.retour("stockage_local_creer", r["resultat"])
        self.assertEqual(self.faux.stockages, [])

    def test_un_chemin_de_stockage_dangereux_est_refuse(self):
        for ch in ("relatif/dossier", "/var/../etc", "/a b", ""):
            self.assertEqual(self.faire("stockage_local_creer", nom="x1", chemin=ch)["statut"], "echec", ch)
        self.assertEqual(self.faux.stockages, [])

    def test_un_plan_demande_un_stockage(self):
        self.assertEqual(self.faire("plan_creer", nom="nuit")["statut"], "echec")

    def test_creer_un_plan_garde_n_copies_et_se_defait(self):
        self.faire("stockage_local_creer", nom="filet", chemin="/var/backups/panneau")
        r = self.faire("plan_creer", nom="nuit", garder=5, heure="3")
        self.assertEqual(r["statut"], "faite", r)
        c = self.faux.plans[0]["corps"]
        self.assertEqual((c["full_copy_limit"], c["partial_copy_limit"], c["hour"], c["account"]), (5, 5, "3", 3))
        self.retour("plan_creer", r["resultat"])
        self.assertEqual(self.faux.plans, [])


if __name__ == "__main__":
    unittest.main()
