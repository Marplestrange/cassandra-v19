# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la gestion Dolibarr
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #09c917
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la gestion Dolibarr : règlements, avoirs, relances, devis, dons, cotisations, virements, projets, requête libre, clé par compte
# MÉTHODE    : un Dolibarr de poche avec des clés, des règlements et des soldes ; chaque geste avec sa preuve et son retour arrière
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=09c917 ▼▼▼
"""Bancs de la gestion Dolibarr : règlements, avoirs, relances, devis, dons, cotisations, virements, projets, requête libre, clé par compte."""
import gzip
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
from noyau.CN_bus import TOUT                 # noqa: E402

CLE_MANDAT, CLE_DRISSE, CLE_AMANDINE = "cle-mandat", "cle-drisse", "cle-amandine"


class FauxGestion:
    """Un Dolibarr de poche, assez complet pour la gestion : règlements, soldes, devis, dons, documents, cotisations. Chaque requête note la clé qui l'a faite."""

    def __init__(self):
        self.journal, self.societe = [], "Maison Bohème"
        self.utilisateurs = {CLE_MANDAT: {"login": "cassandra", "admin": "0"}, CLE_DRISSE: {"login": "marple", "admin": "1"}, CLE_AMANDINE: {"login": "amandine", "admin": "0"}}
        self.t = {c: {} for c in ("thirdparties", "invoices", "proposals", "projects", "donations", "members", "agendaevents", "subscriptions", "paiements", "contacts")}
        self.suivant = {c: 1 for c in self.t}
        self.paiements = {}                  # id de facture -> [ids de règlements]
        self.banques = {1: 1000.0, 2: 50.0}
        self.docs = {}                       # id de don -> [noms de fichiers]
        self.pdfs = {}                       # (modulepart, id) -> [chemins de PDF] pour les devis et les factures
        self.taille_pdf = None               # une taille annoncée exprès trop grande
        self.mode_vir = {"id": 6, "code": "VIR"}
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
                longueur = int(self.headers.get("Content-Length") or 0)
                corps = json.loads(self.rfile.read(longueur) or b"null") if longueur else None
                if cle not in faux.utilisateurs:
                    return self._rep(401, {"error": {"code": 401}})
                return faux.route(self, methode, chemin, q, corps, cle)

            do_GET = lambda s: s._traiter("GET")
            do_POST = lambda s: s._traiter("POST")
            do_PUT = lambda s: s._traiter("PUT")
            do_DELETE = lambda s: s._traiter("DELETE")

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    @property
    def url(self):
        return "http://127.0.0.1:%d/api/index.php" % self.port

    def arreter(self):
        self.srv.shutdown()
        self.srv.server_close()

    def nouveau(self, coll, obj):
        i = self.suivant[coll]
        self.suivant[coll] += 1
        obj = dict(obj, id=i)
        self.t[coll][i] = obj
        return i

    def reste(self, i):
        f = self.t["invoices"][i]
        return round(float(f.get("total_ttc", 0)) - sum(self.t["paiements"][p]["amount"] for p in self.paiements.get(i, [])), 2)

    def facture(self, i):
        f = dict(self.t["invoices"][i])
        f["remaintopay"] = self.reste(i)
        return f

    def route(self, h, m, chemin, q, corps, cle):
        R = h._rep
        p = chemin.strip("/").split("/")
        if chemin == "/status":
            return R(200, {"success": {"dolibarr_version": "23.0.2", "access_locked": "0"}})
        if chemin == "/users/info":
            return R(200, dict(self.utilisateurs[cle], id="7", entity="1"))
        if chemin == "/setup/company":
            return R(200, {"name": self.societe})
        if chemin == "/setup/dictionary/payment_types":
            return R(200, [self.mode_vir, {"id": 7, "code": "CHQ"}])
        if chemin == "/setup/modules":
            return R(200, ["api"])
        if chemin == "/users" and m == "GET":
            return R(200, [{"id": 1, "login": "marple", "api_key": "SECRET-A-NE-PAS-MONTRER", "pass_crypted": "xxx", "lastname": "M"}])
        if p[0] == "bankaccounts":
            if p[1:] == ["transfer"] and m == "POST":
                a, b, mt = int(corps["bankaccount_from_id"]), int(corps["bankaccount_to_id"]), float(corps["amount"])
                self.banques[a] -= mt
                self.banques[b] += mt
                return R(200, 1)
            if len(p) == 3 and p[2] == "balance":
                return R(200, self.banques[int(p[1])])
        if p[0] == "invoices" and p[1:] == ["paymentsdistributed"] and m == "POST":
            if corps["accountid"] not in self.banques:
                return R(400, {"error": {"message": "compte inconnu"}})
            pid = None
            for k, v in corps["arrayofamounts"].items():
                pid = self.nouveau("paiements", {"amount": float(v["amount"]), "facture": int(k), "compte": corps["accountid"], "mode": corps["paymentid"]})
                self.paiements.setdefault(int(k), []).append(pid)
            return R(200, pid)
        if p[0] == "invoices":
            if len(p) == 1 and m == "POST":
                i = self.nouveau("invoices", dict(corps, statut="0", fk_soc=corps.get("socid")))
                return R(200, i)
            i = int(p[1]) if len(p) > 1 and p[1].isdigit() else None
            if i not in self.t["invoices"]:
                return R(404, {"error": {"code": 404}})
            if len(p) == 2 and m == "GET":
                return R(200, self.facture(i))
            if len(p) == 2 and m == "DELETE":
                if self.t["invoices"][i]["statut"] != "0":
                    return R(400, {"error": {"code": 400}})
                del self.t["invoices"][i]
                return R(200, {"success": {}})
            if p[2:] == ["validate"]:
                self.t["invoices"][i]["statut"] = "1"
                return R(200, self.facture(i))
            if p[2:] == ["payments"] and m == "GET":
                ps = [self.t["paiements"][x] for x in self.paiements.get(i, [])]
                return R(200, ps) if ps else R(404, {"error": {"code": 404}})
            if p[2:] == ["payments"] and m == "POST":
                if corps["accountid"] not in self.banques:
                    return R(400, {"error": {"message": "compte inconnu"}})
                pid = self.nouveau("paiements", {"amount": float(corps["amount"]) if "amount" in corps else 0.0, "facture": i, "compte": corps["accountid"], "mode": corps["paymentid"]})
                self.paiements.setdefault(i, []).append(pid)
                return R(200, pid)
        if p[0] == "paiements" and m == "DELETE":
            pid = int(p[1])
            if pid not in self.t["paiements"]:
                return R(404, {})
            i = self.t["paiements"][pid]["facture"]
            self.paiements[i].remove(pid)
            del self.t["paiements"][pid]
            return R(200, {"success": {}})
        if p[0] == "proposals":
            if len(p) == 1 and m == "POST":
                if not corps.get("date"):                                                             # comme Dolibarr 24
                    return R(500, {"error": {"code": 500, "message": "Internal Server Error: Error creating order", "0": "Date of proposal is required"}})
                return R(200, self.nouveau("proposals", dict(corps, statut="0")))
            i = int(p[1]) if len(p) > 1 and p[1].isdigit() else None
            if i not in self.t["proposals"]:
                return R(404, {})
            if len(p) == 2:
                return R(200, dict(self.t["proposals"][i]))
            etat = {"validate": "1", "settodraft": "0"}.get(p[2])
            if p[2] == "close":
                etat = str(corps["status"])
            self.t["proposals"][i]["statut"] = etat
            return R(200, dict(self.t["proposals"][i]))
        if p[0] == "donations":
            if len(p) == 1 and m == "POST":
                return R(200, self.nouveau("donations", dict(corps, statut="0", ref="DON-%d" % self.suivant["donations"])))
            i = int(p[1])
            if i not in self.t["donations"]:
                return R(200, {"id": None, "ref": None})                                              # Dolibarr 24 : 200 et un objet vide
            if p[2:] == ["validate"]:
                self.t["donations"][i]["statut"] = "1"
                return R(200, dict(self.t["donations"][i]))
            if m == "GET":
                return R(200, dict(self.t["donations"][i]))
            if m == "DELETE":
                del self.t["donations"][i]
                return R(200, {"success": {}})
        if p[0] == "documents":
            if p[1:] == ["builddoc"] and m == "PUT" and corps["modulepart"] != "donation":
                coll = {"propal": "proposals", "facture": "invoices"}[corps["modulepart"]]
                ref = corps["original_file"].split("/")[0]
                i = next(k for k, v in self.t[coll].items() if v.get("ref") == ref)
                self.pdfs.setdefault((corps["modulepart"], i), []).append(corps["original_file"])
                return R(200, {"filename": corps["original_file"]})
            if p[1:] == ["download"] and m == "GET":
                import base64
                contenu = b"%PDF-1.4 faux"
                return R(200, {"filename": q["original_file"].split("/")[-1], "content-type": "application/pdf", "filesize": self.taille_pdf or len(contenu), "content": base64.b64encode(contenu).decode(), "encoding": "base64"})
            if len(p) == 1 and m == "GET" and q.get("modulepart") != "donation":
                noms = self.pdfs.get((q["modulepart"], int(q["id"])), [])
                return R(200, [{"name": n.split("/")[1]} for n in noms]) if noms else R(404, {})
            if p[1:] == ["builddoc"] and m == "PUT":
                ref = corps["original_file"].split("/")[0]
                i = next(k for k, v in self.t["donations"].items() if v["ref"] == ref)
                self.docs.setdefault(i, []).append(corps["original_file"])
                return R(200, {"filename": corps["original_file"]})
            if len(p) == 1 and m == "GET":
                return R(200, [{"name": n.split("/")[1]} for n in self.docs.get(int(q["id"]), [])]) if self.docs.get(int(q["id"])) else R(404, {})
            if len(p) == 1 and m == "DELETE":
                for k in self.pdfs:
                    if q["original_file"] in self.pdfs[k]:
                        self.pdfs[k].remove(q["original_file"])
                for k in self.docs:
                    if q["original_file"] in self.docs[k]:
                        self.docs[k].remove(q["original_file"])
                return R(200, {"success": {}})
        if p[0] == "members":
            i = int(p[1])
            if i not in self.t["members"]:
                return R(404, {})
            if p[2:] == ["subscriptions"] and m == "POST":
                return R(200, self.nouveau("subscriptions", dict(corps, membre=i)))
            if p[2:] == ["subscriptions"] and m == "GET":
                ls = [v for v in self.t["subscriptions"].values() if v["membre"] == i]
                return R(200, ls) if ls else R(404, {})
            return R(200, dict(self.t["members"][i]))
        if p[0] == "subscriptions" and m == "DELETE":
            del self.t["subscriptions"][int(p[1])]
            return R(200, {"success": {}})
        if p[0] == "projects":
            if len(p) == 1 and m == "POST":
                if not corps.get("ref"):                                                              # comme Dolibarr 24
                    return R(400, {"error": {"code": 400, "message": "Bad Request: ref field missing"}})
                return R(200, self.nouveau("projects", dict(corps, statut="0")))
            i = int(p[1])
            if i not in self.t["projects"]:
                return R(404, {})
            if p[2:] == ["validate"]:
                self.t["projects"][i]["statut"] = "1"
                return R(200, dict(self.t["projects"][i]))
            if m == "DELETE":
                del self.t["projects"][i]
                return R(200, {"success": {}})
            if m == "PUT":
                self.t["projects"][i].update({("statut" if k == "status" else k): str(v) if k in ("status", "statut") else v for k, v in corps.items() if k != "statut"})   # « statut » est ignoré, comme Dolibarr 24
            return R(200, dict(self.t["projects"][i]))
        if p[0] == "contacts":
            if len(p) == 1 and m == "POST":
                if not corps.get("socid") or corps["socid"] not in self.t["thirdparties"]:
                    return R(500, {"error": {"code": 500, "message": "Internal Server Error: Error creating contact", "0": "ErrorFieldRequired socid"}})
                return R(200, self.nouveau("contacts", corps))
            i = int(p[1])
            if i not in self.t["contacts"]:
                return R(404, {})
            if m == "DELETE":
                del self.t["contacts"][i]
                return R(200, {"success": {}})
            if m == "PUT":
                self.t["contacts"][i].update(corps)
            return R(200, dict(self.t["contacts"][i]))
        if p[0] == "agendaevents":
            if len(p) == 1 and m == "POST":
                if "fk_element" in corps or "elementtype" in corps:                                   # comme Dolibarr 24
                    return R(400, {"error": {"code": 400, "message": "Bad Request: Parameter fk_element is not allowed in request"}})
                if not corps.get("userownerid"):                                                      # comme Dolibarr 24
                    return R(400, {"error": {"code": 400, "message": "Bad Request: userownerid field missing"}})
                return R(200, self.nouveau("agendaevents", corps))
            i = int(p[1])
            if i not in self.t["agendaevents"]:
                return R(404, {})
            if m == "DELETE":
                del self.t["agendaevents"][i]
                return R(200, {"success": {}})
            return R(200, dict(self.t["agendaevents"][i]))
        if p[0] == "thirdparties":
            if len(p) == 1 and m == "POST":
                if str(corps.get("client", 0)) not in ("0", "") and not corps.get("code_client"):      # comme Dolibarr 24 : sans code client, l'erreur
                    return R(500, {"error": {"code": 500, "message": "Internal Server Error: Error creating thirdparty", "1": "ErrorCustomerCodeRequired"}})
                return R(200, self.nouveau("thirdparties", corps))
            i = int(p[1]) if len(p) > 1 else 0
            if i not in self.t["thirdparties"]:
                return R(404, {})
            if m == "PUT":
                self.t["thirdparties"][i].update(corps)
            if m == "DELETE":
                del self.t["thirdparties"][i]
                return R(200, {"success": {}})
            return R(200, dict(self.t["thirdparties"][i]))
        return R(404, {"error": {"code": 404}})


class GestionDolibarr(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.faux = FauxGestion()
        self.addCleanup(self.faux.arreter)
        self.conf = base / "config"
        self.conf.mkdir()
        (self.conf / "dolibarr.conf").write_text("url = %s\n" % self.faux.url, encoding="utf-8")
        (self.conf / "dolibarr.key").write_text(CLE_MANDAT, encoding="utf-8")
        ancien = os.environ.get("CASSANDRA_CONFIG")
        os.environ["CASSANDRA_CONFIG"] = str(self.conf)
        self.addCleanup(lambda: os.environ.__setitem__("CASSANDRA_CONFIG", ancien) if ancien else os.environ.pop("CASSANDRA_CONFIG", None))
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "dolibarr", mods / "dolibarr")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("dolibarr")["ok"])
        self.e = self.n.executeur.executer
        self.ctx = self.n.executeur.contextes["dolibarr"]

    def retour(self, cap, res):
        self.n.catalogue.get("dolibarr." + cap).defaire(self.ctx, res)

    def facture(self, total=120.0, statut="1", **plus):
        return self.faux.nouveau("invoices", dict({"total_ttc": total, "statut": statut, "socid": 1, "fk_soc": 1, "ref": "FA2610-0001", "type": "0",
                                                    "lines": [{"desc": "Son", "qty": 2, "subprice": total / 2, "tva_tx": 0}]}, **plus))

    # --- règlements
    def test_encaisser_partiellement_puis_totalement(self):
        i = self.facture()
        r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 20, "banque": 1})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(self.faux.reste(i), 100.0)
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 100, "banque": 1})["statut"], "faite")
        self.assertEqual(self.faux.reste(i), 0.0)

    def test_encaisser_se_defait(self):
        i = self.facture()
        r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": "45,50", "banque": 1})
        self.assertEqual(self.faux.reste(i), 74.5)
        self.retour("encaisser", r["resultat"])
        self.assertEqual(self.faux.reste(i), 120.0)

    def test_encaisser_refuse_ce_qui_depasse_ou_ce_qui_n_est_pas_validee(self):
        i, brouillon = self.facture(), self.facture(statut="0")
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 500, "banque": 1})["statut"], "echec")
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": brouillon, "montant": 5, "banque": 1})["statut"], "echec")
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 0, "banque": 1})["statut"], "echec")
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 5, "banque": 1, "mode": "OR"})["statut"], "echec")
        self.assertEqual(self.faux.paiements, {})

    def test_cassandra_et_itare_racontent_avant_d_encaisser(self):
        i = self.facture()
        for qui in ("cassandra", "itare"):
            self.assertEqual(self.e("dolibarr.encaisser", qui, {"id": i, "montant": 5, "banque": 1})["statut"], "racontee")
        self.assertEqual(self.faux.paiements, {})
        self.n.catalogue.regler_palier("dolibarr.encaisser", "auto")
        self.assertEqual(self.e("dolibarr.encaisser", "itare", {"id": i, "montant": 5, "banque": 1})["statut"], "faite")

    # --- avoirs et relances
    def test_un_avoir_en_brouillon_aux_montants_negatifs_et_il_se_defait(self):
        i = self.facture()
        r = self.e("dolibarr.creer_avoir", "humain", {"id": i})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        a = self.faux.t["invoices"][r["resultat"]["id"]]
        self.assertEqual((a["type"], a["fk_facture_source"], a["statut"], a["lines"][0]["subprice"]), (2, i, "0", -60.0))
        self.retour("creer_avoir", r["resultat"])
        self.assertNotIn(r["resultat"]["id"], self.faux.t["invoices"])

    def test_un_avoir_exige_une_facture_validee(self):
        self.assertEqual(self.e("dolibarr.creer_avoir", "humain", {"id": self.facture(statut="0")})["statut"], "echec")

    def test_une_relance_est_gardee_dans_l_agenda_et_se_retire(self):
        i = self.facture()
        r = self.e("dolibarr.relancer", "humain", {"id": i, "message": "Bonjour, la facture est échue."})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        ev = self.faux.t["agendaevents"][r["resultat"]["evenement"]]
        self.assertEqual((ev["note"], ev["socid"], "fk_element" in ev, "FA2610-0001" in ev["label"]), ("Bonjour, la facture est échue.", 1, False, True))
        self.retour("relancer", r["resultat"])
        self.assertEqual(self.faux.t["agendaevents"], {})
        self.assertEqual(self.e("dolibarr.relancer", "humain", {"id": i, "message": ""})["statut"], "echec")

    # --- devis
    def test_le_devis_se_valide_se_signe_puis_se_facture(self):
        d = self.faux.nouveau("proposals", {"statut": "0", "socid": 3, "ref": "PR2610-0001", "lines": [{"desc": "Spectacle", "qty": 1, "subprice": 500, "tva_tx": 0}]})
        for action, etat in (("valider", "1"), ("signer", "2")):
            r = self.e("dolibarr.devis", "humain", {"id": d, "action": action})
            self.assertEqual(r["statut"], "faite", msg=str(r))
            self.assertEqual(self.faux.t["proposals"][d]["statut"], etat)
        self.assertEqual(self.e("dolibarr.devis", "humain", {"id": d, "action": "signer"})["statut"], "echec")        # déjà signé
        r = self.e("dolibarr.facturer_devis", "humain", {"id": d})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        f = self.faux.t["invoices"][r["resultat"]["id"]]
        self.assertEqual((f["statut"], f["socid"], len(f["lines"])), ("0", 3, 1))
        self.retour("facturer_devis", r["resultat"])
        self.assertEqual(self.faux.t["invoices"], {})

    def test_un_devis_non_signe_ne_se_facture_pas_et_signer_se_defait(self):
        d = self.faux.nouveau("proposals", {"statut": "1", "socid": 3, "lines": [{"desc": "x", "qty": 1, "subprice": 1}]})
        self.assertEqual(self.e("dolibarr.facturer_devis", "humain", {"id": d})["statut"], "echec")
        r = self.e("dolibarr.devis", "humain", {"id": d, "action": "signer"})
        self.retour("devis", r["resultat"])
        self.assertEqual(self.faux.t["proposals"][d]["statut"], "0")

    # --- dons
    def test_un_don_se_saisit_se_valide_et_donne_son_recu(self):
        r = self.e("dolibarr.don_creer", "humain", {"montant": "2000", "date": "2026-10-31", "nom": "Dupont"})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        i = r["resultat"]["id"]
        self.assertEqual(self.faux.t["donations"][i]["amount"], 2000.0)
        self.assertEqual(self.e("dolibarr.don_recu", "humain", {"id": i})["statut"], "echec")           # pas encore validé
        self.assertEqual(self.e("dolibarr.don_valider", "humain", {"id": i})["statut"], "faite")
        rr = self.e("dolibarr.don_recu", "humain", {"id": i})
        self.assertEqual(rr["statut"], "faite", msg=str(rr))
        self.assertEqual(len(self.faux.docs[i]), 1)
        self.retour("don_recu", rr["resultat"])
        self.assertEqual(self.faux.docs[i], [])
        with self.assertRaises(Exception):
            self.retour("don_valider", {"id": i})                    # un don validé ne se repasse pas en promesse : le retour le dit
        with self.assertRaises(Exception):
            self.retour("don_creer", {"id": i, "montant": 2000.0})   # et ne se supprime plus

    def test_une_promesse_de_don_se_supprime(self):
        r = self.e("dolibarr.don_creer", "humain", {"montant": 10})
        self.retour("don_creer", r["resultat"])
        self.assertEqual(self.faux.t["donations"], {})

    # --- cotisations, virements, projets
    def test_une_cotisation_se_defait(self):
        m = self.faux.nouveau("members", {"login": "x"})
        r = self.e("dolibarr.cotisation", "humain", {"membre": m, "montant": 15, "debut": "2026-10-31", "fin": "2027-10-31"})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(len(self.faux.t["subscriptions"]), 1)
        self.retour("cotisation", r["resultat"])
        self.assertEqual(self.faux.t["subscriptions"], {})

    def test_un_virement_deplace_l_argent_et_se_contre_passe(self):
        r = self.e("dolibarr.virement_interne", "humain", {"de": 1, "vers": 2, "montant": 100})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(self.faux.banques, {1: 900.0, 2: 150.0})
        self.retour("virement_interne", r["resultat"])
        self.assertEqual(self.faux.banques, {1: 1000.0, 2: 50.0})
        self.assertEqual(self.e("dolibarr.virement_interne", "humain", {"de": 1, "vers": 1, "montant": 5})["statut"], "echec")

    def test_un_projet_s_ouvre_et_se_clot(self):
        p = self.faux.nouveau("projects", {"statut": "0", "title": "Cabaret"})
        self.assertEqual(self.e("dolibarr.projet", "humain", {"id": p, "action": "clore"})["statut"], "echec")        # il faut l'ouvrir d'abord
        self.assertEqual(self.e("dolibarr.projet", "humain", {"id": p, "action": "valider"})["statut"], "faite")
        r = self.e("dolibarr.projet", "humain", {"id": p, "action": "clore"})
        self.assertEqual((r["statut"], self.faux.t["projects"][p]["statut"]), ("faite", "2"))
        self.retour("projet", r["resultat"])
        self.assertEqual(self.faux.t["projects"][p]["statut"], "1")

    def test_dolibarr_24_exige_un_code_client_et_une_ref_de_projet_le_module_les_pose(self):
        r = self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": {"name": "Client neuf", "client": 1}})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(self.faux.t["thirdparties"][r["resultat"]["id"]]["code_client"], "auto")
        r2 = self.e("dolibarr.creer", "humain", {"objet": "projets", "champs": {"title": "Cabaret"}})
        self.assertEqual(r2["statut"], "faite", msg=str(r2))
        self.assertEqual(self.faux.t["projects"][r2["resultat"]["id"]]["ref"], "auto")

    def test_un_tiers_supprime_se_recree_avec_son_code(self):
        r = self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": {"name": "À supprimer", "client": 1}})
        s = self.e("dolibarr.supprimer", "humain", {"objet": "tiers", "id": r["resultat"]["id"]})
        self.assertEqual(s["statut"], "faite", msg=str(s))
        back = self.e("dolibarr.restaurer", "humain", {"corbeille": s["resultat"]["corbeille"]})
        self.assertEqual(back["statut"], "faite", msg=str(back))

    def test_un_devis_brouillon_a_toujours_sa_date_et_un_don_disparu_est_introuvable(self):
        r = self.e("dolibarr.creer_brouillon", "humain", {"objet": "devis", "socid": 3, "lignes": [{"desc": "x", "qty": 1, "subprice": 1}]})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertTrue(self.faux.t["proposals"][r["resultat"]["id"]]["date"])
        self.assertEqual(self.e("dolibarr.don_valider", "humain", {"id": 999})["statut"], "echec")

    # --- le PDF d'une pièce
    def test_le_pdf_d_une_facture_se_lit_en_base64(self):
        import base64
        i = self.facture()
        self.faux.pdfs[("facture", i)] = ["FA2610-0001/FA2610-0001.pdf"]
        r = self.e("dolibarr.piece_pdf", "humain", {"objet": "factures", "id": i})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual((r["resultat"]["nom"], r["resultat"]["type"], base64.b64decode(r["resultat"]["donnees_b64"])[:5]), ("FA2610-0001.pdf", "application/pdf", b"%PDF-"))

    def test_une_piece_sans_pdf_se_voit_refuser_la_lecture_mais_peut_le_produire_puis_le_retirer(self):
        d = self.faux.nouveau("proposals", {"statut": "1", "socid": 3, "ref": "PR2610-0001", "lines": []})
        self.assertEqual(self.e("dolibarr.piece_pdf", "humain", {"objet": "devis", "id": d})["statut"], "echec")
        r = self.e("dolibarr.produire_pdf", "humain", {"objet": "devis", "id": d})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(self.e("dolibarr.piece_pdf", "humain", {"objet": "devis", "id": d})["statut"], "faite")
        self.assertEqual(self.e("dolibarr.produire_pdf", "humain", {"objet": "devis", "id": d})["statut"], "echec")        # il existe déjà
        self.retour("produire_pdf", r["resultat"])
        self.assertEqual(self.e("dolibarr.piece_pdf", "humain", {"objet": "devis", "id": d})["statut"], "echec")

    def test_un_pdf_trop_gros_ou_un_objet_inconnu_est_refuse(self):
        i = self.facture()
        self.faux.pdfs[("facture", i)] = ["FA2610-0001/FA2610-0001.pdf"]
        self.faux.taille_pdf = 50 * 1024 * 1024
        self.assertEqual(self.e("dolibarr.piece_pdf", "humain", {"objet": "factures", "id": i})["statut"], "echec")
        self.assertEqual(self.e("dolibarr.piece_pdf", "humain", {"objet": "contrats", "id": 1})["statut"], "echec")

    # --- tout le catalogue
    def test_la_lecture_libre_masque_les_secrets(self):
        r = self.e("dolibarr.lire_libre", "humain", {"chemin": "/users"})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        ligne = r["resultat"]["reponse"][0]
        self.assertEqual((ligne["api_key"], ligne["pass_crypted"], ligne["lastname"]), ("***", "***", "M"))
        self.assertNotIn("SECRET-A-NE-PAS-MONTRER", json.dumps(self.e("dolibarr.lire_libre", "humain", {"chemin": "/users"})))

    def test_la_requete_libre_refuse_ce_qui_n_est_pas_un_domaine_de_l_api(self):
        for chemin in ("/etc/passwd", "/thirdparties/../users", "thirdparties", "/inconnu/1", "/thirdparties/12 34", "/x"):
            self.assertEqual(self.e("dolibarr.lire_libre", "humain", {"chemin": chemin})["statut"], "echec", msg=chemin)
        self.assertEqual(self.faux.journal, [])

    def test_l_ecriture_libre_modifie_avec_preuve_et_retour(self):
        t = self.faux.nouveau("thirdparties", {"name": "Avant", "town": "Paris"})
        r = self.e("dolibarr.ecrire_libre", "humain", {"methode": "PUT", "chemin": "/thirdparties/%d" % t, "corps": {"name": "Après"}})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(self.faux.t["thirdparties"][t]["name"], "Après")
        self.retour("ecrire_libre", r["resultat"])
        self.assertEqual(self.faux.t["thirdparties"][t]["name"], "Avant")

    def test_l_ecriture_libre_cree_et_se_defait_mais_ne_supprime_pas(self):
        r = self.e("dolibarr.ecrire_libre", "humain", {"methode": "POST", "chemin": "/thirdparties", "corps": {"name": "Nouveau"}})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.retour("ecrire_libre", r["resultat"])
        self.assertEqual(self.faux.t["thirdparties"], {})
        self.assertEqual(self.e("dolibarr.ecrire_libre", "humain", {"methode": "DELETE", "chemin": "/thirdparties/1"})["statut"], "echec")

    # --- la clé : propre au compte, de mandat, jamais celle d'un autre
    def accorder(self, *comptes):
        for c in comptes:
            for d in ("dolibarr.utiliser", "dolibarr.administrer"):
                self.n.droits.regler("compte", c, d, "accorde")

    def poser_cle(self, compte, valeur):
        self.n.reglages.poser("dolibarr.cle_api", valeur, compte=compte)

    def test_mon_acces_dit_qui_je_suis_sans_montrer_la_cle(self):
        r = self.e("dolibarr.mon_acces", "humain", {})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual((r["resultat"]["cle"], r["resultat"]["utilisateur"], r["resultat"]["societe"]), ("fichier", "cassandra", "Maison Bohème"))
        self.assertNotIn(CLE_MANDAT, json.dumps(r))

    def test_un_compte_ecrit_avec_sa_propre_cle_et_pas_avec_celle_d_un_autre(self):
        self.accorder("drisse", "amandine")
        self.poser_cle("drisse", CLE_DRISSE)
        self.poser_cle("amandine", CLE_AMANDINE)
        i = self.facture()
        for compte, cle in (("drisse", CLE_DRISSE), ("amandine", CLE_AMANDINE)):
            self.faux.journal.clear()
            r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 10, "banque": 1}, compte=compte)
            self.assertEqual(r["statut"], "faite", msg=str(r))
            self.assertEqual({c for _, _, c in self.faux.journal}, {cle})
        self.faux.journal.clear()
        self.e("dolibarr.mon_acces", "humain", {}, compte="drisse")
        self.assertEqual({c for _, _, c in self.faux.journal}, {CLE_DRISSE})

    def test_un_compte_sans_cle_lit_mais_n_ecrit_pas(self):
        self.accorder("camille")
        i = self.facture()
        self.assertEqual(self.e("dolibarr.lire_libre", "humain", {"chemin": "/invoices/%d" % i}, compte="camille")["statut"], "faite")
        self.faux.journal.clear()
        r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 10, "banque": 1}, compte="camille")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("clé Dolibarr de ce compte", json.dumps(r, ensure_ascii=False))
        self.assertFalse([1 for m, _, _ in self.faux.journal if m != "GET"])          # rien n'est parti

    def test_le_mandat_pour_tous_est_un_choix_de_l_administrateur(self):
        self.accorder("camille")
        i = self.facture()
        self.n.reglages.poser("dolibarr.mandat_pour_tous", True)
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 10, "banque": 1}, compte="camille")["statut"], "faite")
        self.assertEqual({c for m, _, c in self.faux.journal if m == "POST"}, {CLE_MANDAT})

    def test_la_cle_de_mandat_reglee_l_emporte_sur_le_fichier(self):
        self.n.reglages.poser("dolibarr.cle_mandat", CLE_DRISSE)
        self.assertEqual(self.e("dolibarr.mon_acces", "humain", {})["resultat"]["utilisateur"], "marple")

    def test_on_n_ecrit_pas_dans_la_mauvaise_societe(self):
        self.n.reglages.poser("dolibarr.societe_attendue", "Maison Bohème")
        i = self.facture()
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 10, "banque": 1})["statut"], "faite")
        self.faux.societe = "IMRI - IT Dépannage"
        import importlib
        mod = sys.modules.get("modules.dolibarr.CN_module") or None
        for m in list(sys.modules.values()):
            if getattr(m, "_SOCIETES", None) is not None and hasattr(m, "_garde_societe"):
                m._SOCIETES.clear()
        self.faux.journal.clear()
        r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 10, "banque": 1})
        self.assertEqual(r["statut"], "echec")
        self.assertIn("IMRI", json.dumps(r, ensure_ascii=False))
        self.assertFalse([1 for m, _, _ in self.faux.journal if m != "GET"])


class LiensDolibarr(unittest.TestCase):
    """Envoyer un projet ou un contact de Cassandra à Dolibarr : par défaut rien ne part, envoyé il est lié, Dolibarr fait foi, détaché les deux copies restent."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.faux = FauxGestion()
        self.addCleanup(self.faux.arreter)
        conf = base / "config"
        conf.mkdir()
        (conf / "dolibarr.conf").write_text("url = %s\n" % self.faux.url, encoding="utf-8")
        (conf / "dolibarr.key").write_text(CLE_MANDAT, encoding="utf-8")
        ancien = os.environ.get("CASSANDRA_CONFIG")
        os.environ["CASSANDRA_CONFIG"] = str(conf)
        self.addCleanup(lambda: os.environ.__setitem__("CASSANDRA_CONFIG", ancien) if ancien else os.environ.pop("CASSANDRA_CONFIG", None))
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "dolibarr", mods / "dolibarr")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("dolibarr")["ok"])
        self.e = self.n.executeur.executer
        for c in ("drisse", "amandine", "camille"):
            self.n.droits.regler("compte", c, "dolibarr.utiliser", "accorde")
        # Les fiches de Cassandra : lues par executer_lecture (projets.voir, contacts.voir). Le module projets de ce dépôt ne s'exécute pas ici (son point date_ok importe
        # _strptime, refusé par le bac à sable de Python 3.14) : on rend donc les fiches à la main, dans la forme exacte que ces deux capacités rendent.
        fiches = {"projets.voir": {"projet": {"id": 1, "nom": "Soirée de lancement", "debut": "2026-12-12", "fin": "2026-12-13", "resume": "Équipe de six"}},
                  "contacts.voir": {"id": 1, "display_name": "Léa Fontaine", "emails": ["lea@exemple.invalid"], "addr": "lea@exemple.invalid", "phone": "0600000001", "mobile": "",
                                    "company": "Cie Les Pierrots", "job_title": ""}}
        self.n.executeur.contextes["dolibarr"].executer_lecture = lambda cap, **a: fiches.get(cap) if int(a.get("id", 0)) in (1, 2) else None
        self.n.reglages.poser("dolibarr.cle_api", CLE_DRISSE, compte="drisse")
        self.n.reglages.poser("dolibarr.cle_api", CLE_AMANDINE, compte="amandine")
        self.projet = self.contact = 1

    def lien(self, cap, args, compte="drisse", qui="humain"):
        return self.e("dolibarr." + cap, qui, args, compte=compte)

    def retour(self, cap, res, compte="drisse"):
        """Le retour arrière d'un envoi : exécuté au nom du compte, comme le ferait le Journal."""
        mod = sys.modules[self.n.executeur.catalogue.get("dolibarr." + cap).faire.__module__]
        mod._CTX = self.n.executeur.contextes["dolibarr"]
        self.n.executeur.contextes["dolibarr"]._compte.valeur = compte
        try:
            self.n.catalogue.get("dolibarr." + cap).defaire(self.n.executeur.contextes["dolibarr"], res)
        finally:
            self.n.executeur.contextes["dolibarr"]._compte.valeur = ""

    def test_rien_ne_part_vers_dolibarr_sans_envoi(self):
        self.assertEqual(self.faux.t["projects"], {})
        self.assertEqual(self.faux.t["contacts"], {})
        self.assertEqual(self.lien("liens", {})["resultat"], [])

    def test_un_projet_envoye_est_cree_chez_dolibarr_et_lie(self):
        r = self.lien("envoyer_projet", {"id": self.projet})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        o = self.faux.t["projects"][r["resultat"]["id_doli"]]
        self.assertEqual((o["title"], o["ref"], o["description"]), ("Soirée de lancement", "auto", "Équipe de six"))
        liens = self.lien("liens", {"type": "projet"})["resultat"]
        self.assertEqual([(x["type"], x["id"], x["id_doli"]) for x in liens], [("projet", self.projet, r["resultat"]["id_doli"])])
        self.assertEqual(self.lien("envoyer_projet", {"id": self.projet})["statut"], "echec")             # déjà lié

    def test_un_envoi_se_defait_en_retirant_l_objet_et_le_lien(self):
        r = self.lien("envoyer_projet", {"id": self.projet})
        self.retour("envoyer_projet", r["resultat"])
        self.assertEqual(self.faux.t["projects"], {})
        self.assertEqual(self.lien("liens", {})["resultat"], [])

    def test_un_contact_est_toujours_rattache_a_un_tiers_choisi_ou_cree(self):
        self.assertEqual(self.lien("envoyer_contact", {"id": self.contact})["statut"], "echec")           # ni tiers ni nouveau tiers : il ne devient pas un tiers tout seul
        self.assertEqual(self.faux.t["contacts"], {})
        r = self.lien("envoyer_contact", {"id": self.contact, "nouveau_tiers": "Cie Les Pierrots"})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        c = self.faux.t["contacts"][r["resultat"]["id_doli"]]
        self.assertEqual((c["firstname"], c["lastname"], c["email"], c["phone_pro"]), ("Léa", "Fontaine", "lea@exemple.invalid", "0600000001"))
        self.assertEqual(self.faux.t["thirdparties"][c["socid"]]["name"], "Cie Les Pierrots")
        self.retour("envoyer_contact", r["resultat"])
        self.assertEqual((self.faux.t["contacts"], self.faux.t["thirdparties"]), ({}, {}))                 # le contact ET le tiers que cet envoi a créé

    def test_un_contact_peut_etre_rattache_a_un_tiers_existant(self):
        tid = self.faux.nouveau("thirdparties", {"name": "MONARCH", "client": 1})
        r = self.lien("envoyer_contact", {"id": self.contact, "tiers": tid})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(self.faux.t["contacts"][r["resultat"]["id_doli"]]["socid"], tid)
        self.retour("envoyer_contact", r["resultat"])
        self.assertEqual(len(self.faux.t["thirdparties"]), 1)                                              # le tiers existant n'est jamais supprimé

    def test_dolibarr_fait_foi_une_fois_lie_et_detacher_garde_les_deux_copies(self):
        r = self.lien("envoyer_projet", {"id": self.projet})
        m = self.lien("modifier_lie", {"type": "projet", "id": self.projet, "champs": {"title": "Soirée du 12"}})
        self.assertEqual(m["statut"], "faite", msg=str(m))
        self.assertEqual(self.faux.t["projects"][r["resultat"]["id_doli"]]["title"], "Soirée du 12")
        self.assertEqual(self.lien("modifier_lie", {"type": "projet", "id": self.projet, "champs": {"rowid": 1}})["statut"], "echec")     # hors liste
        d = self.lien("detacher", {"type": "projet", "id": self.projet})
        self.assertEqual(d["statut"], "faite", msg=str(d))
        self.assertEqual(self.lien("liens", {})["resultat"], [])
        self.assertEqual(len(self.faux.t["projects"]), 1)                                                  # chez Dolibarr : intact
        self.assertEqual(self.n.executeur.contextes["dolibarr"].executer_lecture("projets.voir", id=1)["projet"]["nom"], "Soirée de lancement")      # chez Cassandra : intact
        self.assertEqual(self.lien("modifier_lie", {"type": "projet", "id": self.projet, "champs": {"title": "x"}})["statut"], "echec")   # plus lié

    def test_les_liens_sont_ceux_du_compte_et_un_compte_sans_cle_n_envoie_pas(self):
        self.lien("envoyer_projet", {"id": self.projet})
        self.assertEqual(self.lien("liens", {}, compte="amandine")["resultat"], [])                         # le lien de l'un n'est pas à l'autre
        p = 2
        self.faux.journal.clear()
        self.assertEqual(self.lien("envoyer_projet", {"id": p}, compte="camille")["statut"], "echec")
        self.assertFalse([1 for m, _, _ in self.faux.journal if m != "GET"])

    def test_itare_prepare_seulement_tant_que_le_palier_est_raconter(self):
        self.assertEqual(self.lien("envoyer_projet", {"id": self.projet}, qui="itare")["statut"], "racontee")
        self.assertEqual(self.faux.t["projects"], {})


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus
# EC : néant
# LIEN : tests/CN_test_noyau.py (le Dolibarr de poche d'origine), modules/dolibarr
