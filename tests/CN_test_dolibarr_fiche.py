# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la fiche utilisateur échangée avec Dolibarr
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #d23bb4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la fiche utilisateur échangée avec Dolibarr : liste blanche, conversions, lien confirmé, comparaison, envoi et retour arrière, champs interdits refusés.
# MÉTHODE    : un Dolibarr de poche (utilisateurs, pays, départements) ; chaque compte agit avec sa propre clé ; aucune requête n'est faite hors de la machine.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d23bb4 ▼▼▼
"""Bancs de la fiche utilisateur échangée avec Dolibarr."""
import gzip
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur                      # noqa: E402

MDP = "Abcdefgh1!"
CLE_MANDAT, CLE_A = "cle-mandat", "cle-marie"


def _module_dolibarr():
    spec = importlib.util.spec_from_file_location("mod_dolibarr_fiche", RACINE / "modules" / "dolibarr" / "CN_module.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FauxUsers:
    """Un Dolibarr de poche pour les utilisateurs : ce que l'API rend (y compris ce qu'elle ne devrait pas donner), ce qu'elle accepte."""

    def __init__(self):
        self.journal = []
        self.users = {
            7: {"id": "7", "login": "marie", "lastname": "Dupont", "firstname": "Marie", "email": "marie@x.fr", "job": "Cheffe", "civility_code": "MME", "gender": "woman",
                "birth": 631152000, "employee": "1", "dateemployment": 1262304000, "dateemploymentend": None, "personal_email": "", "office_phone": "0102030405",
                "user_mobile": "", "personal_mobile": "", "office_fax": "", "address": "1 rue X", "zip": "75001", "town": "Paris", "country_code": "FR", "country_id": "1",
                "state_code": "75", "state_id": "75", "lang": "fr_FR", "color": "aabbcc", "signature": "", "socialnetworks": [], "note_public": "",
                "pass_crypted": "HASH", "api_key": "SECRET", "national_registration_number": "1 80 01 75 001 001 11", "accountancy_code": "421", "weeklyhours": "35",
                "note_private": "à ne jamais copier", "salary": "3000", "thm": "20", "rights": {"x": 1}, "statut": "1", "admin": "0", "entity": "1"},
            8: {"id": "8", "login": "autre", "lastname": "Autre", "firstname": "Un", "email": "autre@x.fr", "statut": "1"},
        }
        self.pays = {"FR": 1, "BE": 2}
        self.deps = {"75": 75, "69": 69}
        self.cles = {CLE_MANDAT: "cassandra", CLE_A: "marie"}
        faux = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _rep(self, code, corps):
                brut = gzip.compress(json.dumps(corps).encode())
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(brut)))
                self.end_headers()
                self.wfile.write(brut)

            def _traiter(self, methode):
                u = urlparse(self.path)
                chemin = u.path[len("/api/index.php"):]
                q = {k: v[0] for k, v in parse_qs(u.query).items()}
                cle = self.headers.get("DOLAPIKEY", "")
                faux.journal.append((methode, chemin, cle))
                n = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(n) or b"null") if n else None
                if cle not in faux.cles:
                    return self._rep(401, {"error": {"code": 401}})
                if methode == "GET" and chemin == "/users":
                    filtre = q.get("sqlfilters", "")
                    adresse = filtre.split(":=:'")[1].split("'")[0] if ":=:'" in filtre else ""
                    return self._rep(200, [u for u in faux.users.values() if u.get("email", "").lower() == adresse.lower()])
                if chemin.startswith("/users/") and chemin[7:].isdigit():
                    i = int(chemin[7:])
                    if i not in faux.users:
                        return self._rep(404, {"error": {"code": 404}})
                    if methode == "GET":
                        return self._rep(200, faux.users[i])
                    if methode == "PUT":
                        for k in ("pass", "pass_crypted", "api_key", "openid"):
                            if k in (corps or {}):
                                return self._rep(405, {"error": {"code": 405}})
                        faux.users[i].update({k: (str(v) if k in ("employee",) else v) for k, v in (corps or {}).items()})
                        if "country_id" in (corps or {}):
                            faux.users[i]["country_code"] = next(c for c, v in faux.pays.items() if v == corps["country_id"])
                        return self._rep(200, faux.users[i])
                if methode == "GET" and chemin == "/setup/dictionary/countries":
                    code = q["sqlfilters"].split("'")[1]
                    return self._rep(200, [{"id": faux.pays[code], "code": code}] if code in faux.pays else [])
                if methode == "GET" and chemin == "/setup/dictionary/states":
                    code = q["sqlfilters"].split("'")[1]
                    return self._rep(200, [{"id": faux.deps[code], "code_departement": code}] if code in faux.deps else [])
                return self._rep(404, {"error": {"code": 404}})

            do_GET = lambda s: s._traiter("GET")
            do_PUT = lambda s: s._traiter("PUT")
            do_POST = lambda s: s._traiter("POST")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    @property
    def url(self):
        return "http://127.0.0.1:%d/api/index.php" % self.port

    def arreter(self):
        self.srv.shutdown()
        self.srv.server_close()


class Conversions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _module_dolibarr()

    def test_la_liste_blanche_arrete_ce_que_l_api_rend_en_trop(self):
        f = self.m.fiche_depuis_doli(FauxUsers().users[7])
        for interdit in ("pass_crypted", "api_key", "national_registration_number", "accountancy_code", "weeklyhours", "note_private", "salary", "thm", "rights", "statut", "admin", "login"):
            self.assertNotIn(interdit, f)
        self.assertEqual(set(f), set(self.m.FICHE_BLANCHE))

    def test_les_horodatages_deviennent_des_jours_et_reviennent(self):
        f = self.m.fiche_depuis_doli(FauxUsers().users[7])
        self.assertEqual((f["birth"], f["dateemployment"], f["dateemploymentend"]), ("1990-01-01", "2010-01-01", ""))
        corps = self.m.corps_vers_doli({"birth": "1990-01-01", "dateemploymentend": ""})
        self.assertEqual(self.m._iso_depuis_ts(corps["birth"]), "1990-01-01")        # l'aller-retour ne glisse pas d'un jour
        self.assertEqual(corps["dateemploymentend"], "")

    def test_les_reseaux_sociaux_et_l_employe(self):
        u = dict(FauxUsers().users[7], socialnetworks={"mastodon": "@m", "vide": ""}, employee="0", color="#0a726b")
        f = self.m.fiche_depuis_doli(u)
        self.assertEqual(json.loads(f["socialnetworks"]), {"mastodon": "@m"})
        self.assertEqual((f["employee"], f["color"]), ("0", "0a726b"))
        self.assertEqual(self.m.fiche_depuis_doli(dict(u, socialnetworks=[]))["socialnetworks"], "")
        self.assertEqual(self.m.corps_vers_doli({"socialnetworks": '{"a": "b"}', "employee": "1"}), {"socialnetworks": {"a": "b"}, "employee": 1})

    def test_un_champ_interdit_ou_inconnu_est_refuse(self):
        for k in ("pass", "api_key", "salary", "note_private", "national_registration_number", "ref_employee", "admin", "login"):
            with self.assertRaises(ValueError, msg=k):
                self.m.corps_vers_doli({k: "x"})
        with self.assertRaises(ValueError):
            self.m.corps_vers_doli({"nimporte": "x"})


class Fiche(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.faux = FauxUsers()
        self.addCleanup(self.faux.arreter)
        conf = base / "config"
        conf.mkdir()
        (conf / "dolibarr.conf").write_text("url = %s\n" % self.faux.url, encoding="utf-8")
        (conf / "dolibarr.key").write_text(CLE_MANDAT, encoding="utf-8")
        ancien = os.environ.get("CASSANDRA_CONFIG")
        os.environ["CASSANDRA_CONFIG"] = str(conf)
        self.addCleanup(lambda: os.environ.__setitem__("CASSANDRA_CONFIG", ancien) if ancien else os.environ.pop("CASSANDRA_CONFIG", None))
        mods = base / "modules"
        for m in ("dolibarr", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        for m in ("droits", "comptes", "dolibarr"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.idt = self.n.identite
        self.idt.unix = lambda nom: "/bin/bash"
        self.idt.fastpanel = lambda: False
        self.e = self.n.executeur.executer
        for c, dn in (("root@x.fr", "Root"), ("marie@x.fr", "Marie Dupont")):
            r = self.e("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP, "display_name": dn}, compte="operateur")
            self.assertEqual(r["statut"], "faite", r)
        self.n.reglages.poser("dolibarr.cle_api", CLE_A, compte="marie@x.fr")

    def ex(self, cap, **args):
        return self.e("dolibarr." + cap, "humain", args, compte="marie@x.fr")

    def lier(self):
        r = self.ex("fiche_lier", id_doli=7)
        self.assertEqual(r["statut"], "faite", r)

    def test_sans_lien_rien_ne_se_lit_et_rien_ne_s_ecrit(self):
        self.assertEqual(self.ex("fiche_lire")["resultat"], {"lie": False, "configure": True})
        self.assertEqual(self.ex("fiche_comparer")["resultat"], {"lie": False})
        self.assertEqual(self.ex("fiche_ecrire", champs={"job": "X"})["statut"], "echec")

    def test_chercher_propose_et_ne_lie_pas(self):
        r = self.ex("fiche_chercher")["resultat"]
        self.assertEqual([c["id"] for c in r["candidats"]], [7])
        self.assertIsNone(r["lie"])
        self.assertEqual(self.ex("fiche_lire")["resultat"], {"lie": False, "configure": True})

    def test_lier_exige_mon_adresse_et_se_defait(self):
        self.assertEqual(self.ex("fiche_lier", id_doli=8)["statut"], "echec")             # l'utilisateur 8 n'a pas mon adresse
        self.assertEqual(self.ex("fiche_lier", id_doli=999)["statut"], "echec")
        self.assertEqual(self.ex("fiche_lier", id_doli="abc")["statut"], "echec")
        self.lier()
        self.assertEqual(self.ex("fiche_lier", id_doli=7)["statut"], "echec")             # déjà liée
        self.assertTrue(self.ex("fiche_lire")["resultat"]["lie"])
        r = self.ex("fiche_delier")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("fiche_lire")["resultat"], {"lie": False, "configure": True})
        self.assertEqual(self.ex("fiche_delier")["statut"], "echec")

    def test_le_lien_est_propre_au_compte(self):
        self.lier()
        r = self.e("dolibarr.fiche_lire", "humain", {}, compte="root@x.fr")
        self.assertEqual(r["resultat"], {"lie": False, "configure": True})

    def test_lire_rend_la_liste_blanche_seulement(self):
        self.lier()
        r = self.ex("fiche_lire")["resultat"]
        self.assertEqual((r["champs"]["lastname"], r["champs"]["birth"], r["champs"]["country_code"]), ("Dupont", "1990-01-01", "FR"))
        self.assertNotIn("pass_crypted", r["champs"])
        self.assertNotIn("national_registration_number", json.dumps(r))
        self.assertNotIn("SECRET", json.dumps(r))

    def test_comparer_dit_ce_qui_differe(self):
        self.lier()
        self.e("comptes.modifier_moi", "humain", {"lastname": "Dupont", "firstname": "Marie", "job": "Directrice", "town": "Paris"}, compte="marie@x.fr")
        r = self.ex("fiche_comparer")["resultat"]
        self.assertTrue(r["lie"])
        self.assertIn("job", r["differents"])
        self.assertNotIn("town", r["differents"])
        ligne = next(x for x in r["champs"] if x["champ"] == "job")
        self.assertEqual((ligne["cassandra"], ligne["dolibarr"], ligne["identique"]), ("Directrice", "Cheffe", False))
        self.assertFalse(r["change_depuis_le_lien"])
        self.faux.users[7]["town"] = "Lyon"                                              # quelqu'un change la fiche dans Dolibarr
        self.assertTrue(self.ex("fiche_comparer")["resultat"]["change_depuis_le_lien"])

    def test_ecrire_envoie_avec_ma_cle_prouve_et_se_defait(self):
        self.lier()
        r = self.ex("fiche_ecrire", champs={"job": "Directrice", "birth": "1991-02-03", "country_code": "BE", "socialnetworks": {"mastodon": "@m"}})
        self.assertEqual(r["statut"], "faite", r)
        u = self.faux.users[7]
        self.assertEqual((u["job"], u["country_id"], u["country_code"], u["socialnetworks"]), ("Directrice", 2, "BE", {"mastodon": "@m"}))
        self.assertEqual(self.faux.journal[-1][2] if self.faux.journal[-1][0] == "GET" else None, CLE_A)      # sous le nom de la personne, pas sous le mandat
        puts = [j for j in self.faux.journal if j[0] == "PUT"]
        self.assertEqual({j[2] for j in puts}, {CLE_A})
        self.n.catalogue.get("dolibarr.fiche_ecrire").defaire(self.n.executeur.contextes["dolibarr"], r["resultat"])
        self.assertEqual(self.faux.users[7]["job"], "Cheffe")

    def test_ecrire_refuse_le_trop_long_l_interdit_et_le_pays_inconnu(self):
        self.lier()
        for champs in ({"lastname": "x" * 51}, {"pass": "x"}, {"salary": "9"}, {"national_registration_number": "1"}, {"country_code": "ZZ"}, {"state_code": "99"}, {"inconnu": "1"}):
            avant = dict(self.faux.users[7])
            self.assertEqual(self.ex("fiche_ecrire", champs=champs)["statut"], "echec", champs)
            self.assertEqual(self.faux.users[7], avant, champs)                          # rien n'est parti


# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : FauxUsers, Conversions, Fiche
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/dolibarr/CN_module.py (la fiche), noyau/CN_fiche.py
