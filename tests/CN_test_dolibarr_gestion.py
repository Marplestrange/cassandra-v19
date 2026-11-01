# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la gestion Dolibarr
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #b70e5c
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la gestion Dolibarr : règlements, avoirs, relances, devis, dons, cotisations, virements, projets, requête libre, clé par compte
# MÉTHODE    : un Dolibarr de poche avec des clés, des règlements et des soldes ; chaque geste avec sa preuve et son retour arrière
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b70e5c ▼▼▼
"""Bancs de la gestion Dolibarr : règlements, avoirs, relances, devis, dons, cotisations, virements, projets, requête libre, clé par compte."""
import base64
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
        self.t = {c: {} for c in ("thirdparties", "invoices", "proposals", "projects", "donations", "members", "agendaevents", "subscriptions", "paiements", "contacts", "supplierinvoices", "products", "orders", "supplierorders", "expensereports")}
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
        if chemin == "/setup/dictionary/expensereport_types":
            return R(200, [{"id": "29", "code": "EX_KME", "label": "Frais kilométriques", "active": "1"}, {"id": "30", "code": "EX_OLD", "label": "Ancien", "active": "0"}])
        if p[0] in ("supplierorders", "expensereports") or (p[0] == "supplierinvoices" and (len(p) == 1 and m == "POST" or p[2:3] in (["validate"], ["settodraft"]) or m == "DELETE")):
            coll = p[0]
            if len(p) == 1 and m == "POST":
                base = {"supplierinvoices": "SI", "supplierorders": "PO", "expensereports": "(PROV"}[coll]
                return R(200, self.nouveau(coll, dict(corps, statut="0", status=0, ref=base + "%d" % self.suivant[coll], **({"total_ttc": sum(float(l["total_ttc"]) for l in corps["lines"])} if coll == "expensereports" else {}))))
            i = int(p[1]) if len(p) > 1 and p[1].isdigit() else None
            if i not in self.t[coll]:
                return R(404, {})
            if len(p) == 2:
                if m == "DELETE":
                    del self.t[coll][i]
                    return R(200, {"success": {}})
                return R(200, dict(self.t[coll][i]))
            etat = {"validate": "1" if coll != "expensereports" else "2", "approve": "2" if coll != "expensereports" else "5", "makeorder": "3", "settodraft": "0"}[p[2]]
            if coll == "expensereports" and not isinstance(corps.get("notrigger"), int):
                return R(400, {"error": {"code": 400, "message": "Bad Request: Invalid value specified for `notrigger`. Expecting integer value"}})
            self.t[coll][i].update(statut=etat, status=int(etat))
            return R(200, dict(self.t[coll][i]))
        if p == ["orders"] and m == "POST":
            return R(200, self.nouveau("orders", dict(corps, statut="0", ref="(PROV%d)" % self.suivant["orders"])))
        if p[0] == "orders" and len(p) >= 2 and p[1].isdigit():
            i = int(p[1])
            if i not in self.t["orders"]:
                return R(404, {})
            if len(p) == 2:
                if m == "DELETE":
                    del self.t["orders"][i]
                    return R(200, {"success": {}})
                return R(200, dict(self.t["orders"][i]))
            self.t["orders"][i]["statut"] = {"validate": "1", "settodraft": "0", "close": "3", "reopen": "1"}[p[2]]
            return R(200, dict(self.t["orders"][i]))
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
            if corps["paymentid"] == 7 and not corps.get("chqemetteur"):                              # comme Dolibarr 24
                return R(400, {"error": {"code": 400, "message": "Bad Request: Emetteur is mandatory when payment code is CHQ"}})
            pid = None
            for k, v in corps["arrayofamounts"].items():
                if "amount" in v and "multicurrency_amount" in v:                                       # comme Dolibarr 24
                    return R(400, {"error": {"code": 400, "message": "Bad Request: Payment in both currency %s ( amount: %s, multicurrency_amount: %s)" % (k, v["amount"], v["multicurrency_amount"])}})
                pid = self.nouveau("paiements", {"amount": float(v["amount"]), "facture": int(k), "compte": corps["accountid"], "mode": corps["paymentid"]})
                self.paiements.setdefault(int(k), []).append(pid)
                if corps.get("closepaidinvoices") == "yes" and self.reste(int(k)) <= 0.005:                 # comme Dolibarr : la facture soldée est close
                    self.t["invoices"][int(k)].update(paye="1", statut="2")
            return R(200, pid)
        if p == ["invoices"] and m == "GET":
            ls = [self.facture(i) for i in sorted(self.t["invoices"]) if self.t["invoices"][i].get("statut") == "1" and self.reste(i) > 0.005] if q.get("status") == "unpaid" else [self.facture(i) for i in sorted(self.t["invoices"])]
            return R(200, ls) if ls else R(404, {})
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
            if p[2:] == ["settounpaid"]:
                self.t["invoices"][i].update(paye="0", statut="1")
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
            if self.t["invoices"][i].get("paye") == "1":                                                   # comme Dolibarr 24
                return R(500, {"error": {"code": 500, "message": "Internal Server Error: Error when deleting Paiement : ErrorDeletePaymentLinkedToAClosedInvoiceNotPossible"}})
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
            pj = self.__dict__.setdefault("pj", {})                                                     # les documents joints : {(modulepart, ref): {nom: contenu b64}}
            if p[1:] == ["upload"] and m == "POST":
                if "/" in corps["filename"] or ".." in corps["filename"]:
                    return R(400, {"error": {"message": "bad filename"}})
                pj.setdefault((corps["modulepart"], corps["ref"]), {})[corps["filename"]] = corps["filecontent"]
                return R(200, "%s/%s" % (corps["ref"], corps["filename"]))
            if p[1:] == ["download"] and m == "GET" and any(q["original_file"] == "%s/%s" % (k[1], n) for k, v in pj.items() for n in v):
                ref, nom = q["original_file"].split("/", 1)
                c = next(v[nom] for k, v in pj.items() if k[1] == ref and nom in v)
                return R(200, {"filename": nom, "content-type": "application/octet-stream", "filesize": len(base64.b64decode(c)), "content": c, "encoding": "base64"})
            if len(p) == 1 and m == "GET" and any(k[0] == q["modulepart"] for k in pj):
                ref = next((str(v.get("ref") or v.get("name")) for coll in self.t.values() if isinstance(coll, dict) for i, v in coll.items() if str(i) == str(q["id"]) and isinstance(v, dict) and (v.get("ref") or v.get("name"))), None)
                fichiers = pj.get((q["modulepart"], ref), {})
                if fichiers:
                    return R(200, [{"name": n, "relativename": "%s/%s" % (ref, n), "size": len(base64.b64decode(c)), "date": 1} for n, c in fichiers.items()])
            if len(p) == 1 and m == "DELETE" and any(q["original_file"] == "%s/%s" % (k[1], n) for k, v in pj.items() for n in v):
                ref, nom = q["original_file"].split("/", 1)
                for k, v in pj.items():
                    if k[1] == ref:
                        v.pop(nom, None)
                return R(200, {"success": {}})
            if p[1:] == ["builddoc"] and m == "PUT" and corps["modulepart"] != "donation":
                coll = {"propal": "proposals", "facture": "invoices"}[corps["modulepart"]]
                ref = corps["original_file"].split("/")[0]
                i = next(k for k, v in self.t[coll].items() if v.get("ref") == ref)
                self.pdfs.setdefault((corps["modulepart"], i), []).append(corps["original_file"])
                return R(200, {"filename": corps["original_file"]})
            if p[1:] == ["download"] and m == "GET":
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
        if p == ["explorer", "swagger.json"]:
            return R(200, {"paths": {"/invoices": {"get": {}, "post": {}}, "/invoices/{id}": {"get": {}, "put": {}, "delete": {}}, "/thirdparties": {"get": {}, "post": {}}}})
        if p[0] == "supplierinvoices":
            i = int(p[1]) if len(p) > 1 and p[1].isdigit() else None
            if i not in self.t["supplierinvoices"]:
                return R(404, {})
            if p[2:] == ["payments"] and m == "POST":
                if not corps.get("payment_mode_id"):                                                  # comme Dolibarr 24
                    return R(400, {"error": {"code": 400, "message": "Bad Request: `payment_mode_id` is required."}})
                self.t["supplierinvoices"][i]["paye"] = "1"
                self.t["supplierinvoices"][i]["statut"] = "2"
                return R(200, 1)
            if p[2:] == ["settounpaid"]:
                self.t["supplierinvoices"][i].update(paye="0", statut="1")
                return R(200, dict(self.t["supplierinvoices"][i]))
            return R(200, dict(self.t["supplierinvoices"][i]))
        if p[0] == "products":
            if len(p) == 1 and m == "POST":
                if not corps.get("ref") or not corps.get("label"):                                    # comme Dolibarr : la réf. et le libellé
                    return R(400, {"error": {"code": 400, "message": "Bad Request: ref field missing"}})
                return R(200, self.nouveau("products", corps))
            i = int(p[1])
            if i not in self.t["products"]:
                return R(404, {})
            if m == "PUT":
                self.t["products"][i].update(corps)
            return R(200, dict(self.t["products"][i]))
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
            if p[2:3] == ["bankaccounts"]:
                ribs = self.__dict__.setdefault("ribs", {}).setdefault(i, {})
                if m == "POST":
                    n = max([0] + list(ribs)) + 1
                    ribs[n] = dict(corps, id=str(n))
                    return R(200, n)
                if m == "DELETE":
                    ribs.pop(int(p[3]), None)
                    return R(200, {"success": {}})
                return R(200, list(ribs.values()))
            if m == "PUT":
                self.t["thirdparties"][i].update(corps)
            if m == "DELETE":
                del self.t["thirdparties"][i]
                return R(200, {"success": {}})
            return R(200, dict(self.t["thirdparties"][i]))
        return R(404, {"error": {"code": 404}})


DROITS_DOLIBARR = tuple("dolibarr." + d for d in ("consulter", "facturer", "valider", "tiers", "dons", "tresorerie", "libre", "administrer"))


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
        for m in ("dolibarr", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "dolibarr"):
            self.assertTrue(self.n.activer(m)["ok"], m)
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

    def test_le_reglement_qui_solde_la_facture_se_defait_en_la_rouvrant(self):
        i = self.facture()
        r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 120, "banque": 1})
        self.assertEqual((r["statut"], self.faux.t["invoices"][i]["paye"]), ("faite", "1"))
        self.retour("encaisser", r["resultat"])                                    # sans rouvrir d'abord, Dolibarr 24 refuse (facture close)
        self.assertEqual((self.faux.reste(i), self.faux.t["invoices"][i]["paye"]), (120.0, "0"))

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
        self.assertEqual(self.faux.t["proposals"][d]["statut"], "1")          # signé → on revient à « ouvert », pas seulement à « brouillon »

    # --- dons
    def test_un_don_se_saisit_et_se_valide_mais_son_recu_ne_passe_pas_par_l_api(self):
        r = self.e("dolibarr.don_creer", "humain", {"montant": "2000", "date": "2026-10-31", "nom": "Dupont"})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        i = r["resultat"]["id"]
        self.assertEqual(self.faux.t["donations"][i]["amount"], 2000.0)
        self.assertEqual(self.e("dolibarr.don_valider", "humain", {"id": i})["statut"], "faite")
        self.assertEqual(self.e("dolibarr.don_recu", "humain", {"id": i})["statut"], "refuse")           # la capacité n'existe plus : Dolibarr 24 ne produit pas ce PDF par l'API
        self.assertEqual(self.e("dolibarr.piece_pdf", "humain", {"objet": "dons", "id": i})["statut"], "echec")
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

    # --- les fiches de Dolibarr : mêmes champs, mêmes règles
    def test_la_fiche_tiers_porte_les_champs_de_dolibarr_et_ses_regles(self):
        complet = {"name": "ASSOCIATION ESSAI", "name_alias": "Essai", "client": "3", "fournisseur": "0", "status": "1", "address": "1 rue X", "zip": "75010", "town": "PARIS", "country_id": "1",
                   "phone": "0102030405", "phone_mobile": "0601020304", "fax": "", "url": "https://exemple.fr", "email": "essai@exemple.fr", "no_email": "0", "skype": "", "twitter": "@essai",
                   "idprof1": "899 553 093", "idprof2": "899 553 093 00019", "idprof3": "90.01Z", "idprof6": "W751260323", "tva_assuj": "0", "tva_intra": "", "typent_id": "8", "effectif_id": "1",
                   "forme_juridique_code": "9220", "capital": "0", "default_lang": "fr_FR", "multicurrency_code": "EUR", "note_public": "n", "note_private": "p"}
        r = self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": complet})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        recu = self.faux.t["thirdparties"][r["resultat"]["id"]]
        self.assertEqual((recu["idprof1"], recu["forme_juridique_code"], recu["client"], recu["code_client"]), ("899 553 093", "9220", "3", "auto"))          # tel quel, et le code que Dolibarr numérote
        for refuse, dit in (({"client": 1}, "name"), ({"name": "X", "email": "pasunmail"}, "email"), ({"name": "X", "url": "exemple.fr"}, "url"), ({"name": "X", "client": "5"}, "client"),
                            ({"name": "X", "idprof1": "123"}, "SIREN"), ({"name": "X", "idprof2": "123"}, "SIRET"), ({"name": "X", "inconnu": "1"}, "refusé")):
            self.assertIn(dit, json.dumps(self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": refuse}), ensure_ascii=False), refuse)
        # hors de France, les identifiants ne sont pas contrôlés comme un SIREN
        self.assertEqual(self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": {"name": "Belge", "country_id": "2", "idprof1": "0123.456.789"}})["statut"], "faite")

    def test_les_charges_que_l_ecran_envoie_sont_acceptees_et_se_relisent(self):
        """Les charges relevées dans l'écran (tous champs remplis, valeurs en texte comme un formulaire les donne) : le module les accepte et Dolibarr les garde."""
        tiers = self.faux.nouveau("thirdparties", {"name": "T", "client": 1})
        for objet, champs, cle in (
                ("produits", {"ref": "ESS-1", "label": "Essai", "type": "1", "status": "1", "status_buy": "0", "barcode": "123", "url": "https://exemple.fr", "description": "d", "price_base_type": "HT", "price": "0",
                              "tva_tx": "0", "accountancy_code_sell": "706", "accountancy_code_buy": "607", "note_private": "n"}, "products"),
                ("projets", {"title": "Essai", "socid": str(tiers), "public": "0", "status": "1", "date_start": "2026-11-02", "date_end": "2026-11-03", "budget_amount": "10", "usage_opportunity": "0", "opp_percent": "10",
                             "opp_amount": "10", "description": "d", "note_public": "n", "note_private": "n"}, "projects"),
                ("contacts", {"civility_code": "MME", "lastname": "Fontaine", "firstname": "Léa", "socid": str(tiers), "poste": "Régie", "statut": "1", "priv": "0", "address": "1 rue X", "zip": "44000", "town": "Nantes",
                              "country_id": "1", "phone_pro": "0102030405", "phone_mobile": "0601020304", "email": "a@b.fr", "no_email": "0", "birthday": "1990-01-01", "default_lang": "fr_FR", "note_public": "n"}, "contacts")):
            r = self.e("dolibarr.creer", "humain", {"objet": objet, "champs": champs})
            self.assertEqual(r["statut"], "faite", msg="%s : %s" % (objet, r))
            self.assertEqual(self.faux.t[cle][r["resultat"]["id"]]["label" if objet == "produits" else ("title" if objet == "projets" else "lastname")], champs.get("label") or champs.get("title") or champs["lastname"])
        # un refus de Dolibarr arrive jusqu'à l'écran AVEC son message (ici : un contact sans tiers)
        r = self.e("dolibarr.creer", "humain", {"objet": "contacts", "champs": {"lastname": "Sans tiers"}})
        self.assertEqual(r["statut"], "echec")
        self.assertIn("ErrorFieldRequired socid", r["erreur"]) if "ErrorFieldRequired" in r["erreur"] else self.assertIn("Error creating contact", r["erreur"])
        # un règlement avec tous les champs de la fiche : numéro, commentaire, date
        i = self.facture()
        r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": "120.0", "banque": 1, "mode": "CHQ", "date": "2026-11-02", "numero": "CHQ-1234", "note": "Merci", "emetteur": "Jean Dupont", "banque_cheque": "Banque Postale"})
        self.assertEqual(r["statut"], "faite", msg=str(r))

    def test_ce_que_l_epreuve_d_une_vraie_instance_a_appris(self):
        """Trouvé sur une copie de Dolibarr 24 : un chèque exige son émetteur ; les réseaux sociaux vont dans « socialnetworks » ; la preuve relit comme Dolibarr garde (dates en secondes, codes comptables tronqués)."""
        i = self.facture()
        r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 10, "banque": 1, "mode": "CHQ"})
        self.assertEqual(r["statut"], "echec")
        self.assertIn("émetteur", r["erreur"])
        self.assertFalse([1 for m, _, _ in self.faux.journal if m == "POST" and "paymentsdistributed" in str(_)])                    # refusé avant d'écrire
        r = self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 10, "banque": 1, "mode": "CHQ", "numero": "CHQ-1", "emetteur": "Jean Dupont", "banque_cheque": "Banque Postale"})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        t = self.e("dolibarr.creer", "humain", {"objet": "tiers", "champs": {"name": "Réseaux", "client": "1", "skype": "s", "twitter": "@x", "town": "Nantes"}})
        self.assertEqual(t["statut"], "faite", msg=str(t))
        o = self.faux.t["thirdparties"][t["resultat"]["id"]]
        self.assertEqual((o["socialnetworks"], "skype" in o, "twitter" in o), ({"skype": "s", "twitter": "@x"}, False, False))
        m = self.e("dolibarr.modifier", "humain", {"objet": "tiers", "id": t["resultat"]["id"], "champs": {"linkedin": "in/x"}})
        self.assertEqual(self.faux.t["thirdparties"][t["resultat"]["id"]]["socialnetworks"], {"skype": "s", "twitter": "@x", "linkedin": "in/x"})      # ce qu'on ne touche pas est gardé
        prod = self.e("dolibarr.creer", "humain", {"objet": "produits", "champs": {"ref": "R", "label": "L", "accountancy_code_sell": "706000"}})
        self.faux.t["products"][prod["resultat"]["id"]]["accountancy_code_sell"] = "706"                                            # Dolibarr tronque les zéros de fin
        self.assertTrue(self.n.catalogue.get("dolibarr.creer").prouver(self.ctx, prod["resultat"]))
        con = self.e("dolibarr.creer", "humain", {"objet": "contacts", "champs": {"lastname": "N", "socid": 1, "birthday": "1990-01-02"}}) if self.faux.t["thirdparties"] else None
        if con and con["statut"] == "faite":
            self.faux.t["contacts"][con["resultat"]["id"]]["birthday"] = 631238400                                                   # Dolibarr garde la date en secondes
            self.assertTrue(self.n.catalogue.get("dolibarr.creer").prouver(self.ctx, con["resultat"]))

    # --- la lecture de la BASE de Dolibarr : superadministrateurs seulement, en lecture seule, requêtes nommées
    def _base(self, grants="GRANT SELECT ON `dolibarr`.* TO `cassandra_ro`@`localhost`"):
        """Un faux client « mysql » : il vérifie la session en lecture seule et le mot de passe hors de la ligne de commande, et répond selon la requête."""
        vus = []

        class R:
            def __init__(s, sortie, code=0, err=b""):
                s.stdout, s.returncode, s.stderr = sortie.encode(), code, err

        def faux(cmd, **kw):
            sql = cmd[-1]
            vus.append((cmd, kw, sql))
            if "SET SESSION TRANSACTION READ ONLY" not in sql or "motdepasse-sql" in " ".join(cmd) or kw["env"].get("MYSQL_PWD") != "motdepasse-sql":
                return R("", 1, "ERROR : session ou mot de passe mal passes".encode())
            if "FROM llx_don d" in sql:
                return R("id\tadresse\tcode_postal\tville\tpays\tcourriel\ttelephone\n7\t3 rue du Don\\nBat. B\t75010\tParis\tNULL\tdonateur@exemple.fr\t\n")
            if "VERSION()" in sql:
                return R("version\n8.0.46\n")
            if "information_schema" in sql:
                return R("t\nllx_don\nllx_extrafields\nllx_blockedlog\nllx_facture\n")
            if "SHOW GRANTS" in sql:
                return R("Grants for cassandra_ro@localhost\n" + grants + "\n")
            if "FROM llx_blockedlog" in sql:
                return R("enregistrements\tdernier\tderniere_date\n184\t100079\t2026-10-31 05:20:37\n")
            return R("", 1, b"requete inconnue")
        g = self.n.catalogue.get("dolibarr.base_requete").faire.__globals__
        ancien = g["EXEC_SQL"]["run"]
        g["EXEC_SQL"]["run"] = faux
        self.addCleanup(g["EXEC_SQL"].__setitem__, "run", ancien)
        for cle, val in (("base_hote", "127.0.0.1"), ("base_nom", "dolibarr"), ("base_utilisateur", "cassandra_ro"), ("base_motdepasse", "motdepasse-sql")):
            self.n.reglages.poser("dolibarr." + cle, val, "")
        return vus

    def _comptes(self):
        self.n.identite.creer("chef@x.fr", "Abcdefgh1!", superadmin=True)
        self.n.identite.creer("admin@x.fr", "Abcdefgh1!")
        self.n.droits.regler_admin("admin@x.fr", True)

    def test_la_base_se_lit_en_lecture_seule_et_pour_les_superadministrateurs_seulement(self):
        vus = self._base()
        self._comptes()
        r = self.e("dolibarr.base_requete", "humain", {"nom": "don_adresses", "parametres": {"ids": [7]}}, compte="chef@x.fr")
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(r["resultat"]["lignes"], [{"id": "7", "adresse": "3 rue du Don\nBat. B", "code_postal": "75010", "ville": "Paris", "pays": None, "courriel": "donateur@exemple.fr", "telephone": ""}])
        cmd, kw, sql = vus[-1]
        self.assertIn("SET SESSION TRANSACTION READ ONLY", sql)
        self.assertEqual(kw["env"]["MYSQL_PWD"], "motdepasse-sql")
        self.assertNotIn("motdepasse-sql", " ".join(cmd))                                         # jamais dans la ligne de commande
        self.assertIn("d.rowid IN (7)", sql)
        # un simple administrateur, un compte sans nom, un moteur : refusés, et rien n'est lancé
        avant = len(vus)
        for compte in ("admin@x.fr", ""):
            r = self.e("dolibarr.base_requete", "humain", {"nom": "journal_etat"}, compte=compte)
            self.assertEqual(r["statut"], "echec", compte)
            self.assertIn("superadministrateurs", r["erreur"])
        self.assertEqual(len(vus), avant)

    def test_la_base_n_accepte_que_des_requetes_nommees_aux_parametres_controles(self):
        vus = self._base()
        self._comptes()
        for args in ({"nom": "DROP TABLE llx_don"}, {"nom": "don_adresses", "parametres": {"ids": ["1; DROP TABLE llx_don"]}}, {"nom": "don_adresses", "parametres": {"ids": []}},
                     {"nom": "don_adresses", "parametres": {"ids": [1], "tri": "x"}}, {"nom": "ca_par_mois", "parametres": {"du": "2026-01-01' OR 1=1 --"}}, {"nom": "don_adresses"}):
            r = self.e("dolibarr.base_requete", "humain", args, compte="chef@x.fr")
            self.assertEqual(r["statut"], "echec", args)
        self.assertEqual(vus, [])                                                                    # aucune n'a atteint le serveur
        r = self.e("dolibarr.base_requete", "humain", {"nom": "journal_etat"}, compte="chef@x.fr")
        self.assertEqual((r["statut"], r["resultat"]["lignes"][0]["enregistrements"]), ("faite", "184"))

    def test_l_etat_de_la_base_dit_si_l_utilisateur_sql_n_a_que_le_droit_de_lire(self):
        self._base()
        self._comptes()
        r = self.e("dolibarr.base_etat", "humain", {}, compte="chef@x.fr")["resultat"]
        self.assertEqual((r["actif"], r["version"], r["lecture_seule"], r["tables_manquantes"], r["droits_en_trop"]), (True, "8.0.46", True, [], []))
        self._base(grants="GRANT SELECT, INSERT, DELETE ON `dolibarr`.* TO `cassandra_ro`@`localhost`")
        r = self.e("dolibarr.base_etat", "humain", {}, compte="chef@x.fr")["resultat"]
        self.assertEqual((r["lecture_seule"], r["droits_en_trop"]), (False, ["DELETE", "INSERT"]))

    def test_sans_reglage_la_base_est_coupee_et_le_dit(self):
        self._comptes()
        r = self.e("dolibarr.base_etat", "humain", {}, compte="chef@x.fr")
        self.assertEqual((r["statut"], r["resultat"]["actif"]), ("faite", False))
        self.assertIn("pas réglée", r["resultat"]["raison"])
        self.assertEqual(self.e("dolibarr.base_requete", "humain", {"nom": "journal_etat"}, compte="chef@x.fr")["statut"], "echec")

    # --- les droits par métier : ce que l'administrateur accorde dans Paramètres › Droits
    def test_chaque_droit_de_dolibarr_ferme_ses_gestes(self):
        self.n.identite.creer("chef@x.fr", "Abcdefgh1!", superadmin=True)
        self.n.identite.creer("paul@x.fr", "Abcdefgh1!")
        i = self.facture()
        pour = lambda cap, args: self.e("dolibarr." + cap, "humain", args, compte="paul@x.fr")
        # sans rien d'accordé, « consulter » (par défaut) suffit à lire, rien d'autre
        self.assertEqual(pour("lister", {"objet": "tiers"})["statut"], "faite")
        gestes = {"facturer": ("creer_brouillon", {"objet": "factures", "socid": 1, "lignes": [{"desc": "x", "qty": 1, "subprice": 1}]}),
                  "valider": ("valider_facture", {"id": i}), "tiers": ("creer", {"objet": "tiers", "champs": {"name": "T", "client": 1}}),
                  "dons": ("don_creer", {"montant": "5", "nom": "N"}), "tresorerie": ("virement_interne", {"de": 1, "vers": 2, "montant": "1"}),
                  "libre": ("ecrire_libre", {"methode": "PUT", "chemin": "/thirdparties/1", "corps": {"town": "X"}})}
        for droit, (cap, args) in gestes.items():
            r = pour(cap, args)
            self.assertEqual(r["statut"], "refuse", "%s sans le droit %s : %s" % (cap, droit, r))
            self.assertIn("dolibarr." + droit, r["raison"])
            self.n.droits.regler("compte", "paul@x.fr", "dolibarr." + droit, "accorde")
            self.assertNotEqual(pour(cap, args)["statut"], "refuse", "%s avec le droit %s" % (cap, droit))       # accordé : le geste s'exécute (il peut échouer pour une autre raison)
        # la lecture de la base reste aux superadministrateurs, même avec « administrer »
        self.n.droits.regler("compte", "paul@x.fr", "dolibarr.administrer", "accorde")
        self._base()
        self.assertEqual(self.e("dolibarr.base_etat", "humain", {}, compte="paul@x.fr")["statut"], "echec")

    def test_tout_ce_que_l_ecran_lit_est_permis_a_la_lecture_de_l_ecran(self):
        """Une page ajoutée à l'écran dont le domaine manque à la liste ferait un 403 muet pour tout compte qui ne peut que consulter (vu avec « Commandes »)."""
        import re as _re
        src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "interface", "CN_dolibarr-ecran.js"), encoding="utf-8").read()
        domaines = set(_re.findall(r'lire\("/([a-z]+)', src)) | set(_re.findall(r'agir\("dolibarr\.lire_ecran", \{ chemin: "/([a-z]+)', src))
        self.assertGreater(len(domaines), 10)
        import importlib.util
        spec = importlib.util.spec_from_file_location("dolibarr_mod_domaines", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "modules", "dolibarr", "CN_module.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(sorted(domaines - set(mod.DOMAINES_ECRAN)), [], "l'écran lit ces domaines, que lire_ecran refuse")

    def test_consulter_suffit_a_l_ecran_mais_pas_a_la_requete_libre(self):
        self.n.identite.creer("chef@x.fr", "Abcdefgh1!", superadmin=True)
        self.n.identite.creer("paul@x.fr", "Abcdefgh1!")
        i = self.facture()
        pour = lambda cap, args: self.e("dolibarr." + cap, "humain", args, compte="paul@x.fr")
        self.assertEqual(pour("lire_ecran", {"chemin": "/invoices/%d" % i})["statut"], "faite")        # l'écran lit ses fiches
        self.assertEqual(pour("lire_ecran", {"chemin": "/setup/dictionary/countries"})["statut"], "faite")
        self.assertNotEqual(pour("lire_ecran", {"chemin": "/users"})["statut"], "faite")                # pas les utilisateurs de Dolibarr
        self.assertNotEqual(pour("lire_ecran", {"chemin": "/setup/modules"})["statut"], "faite")        # ni sa configuration
        r = pour("lire_libre", {"chemin": "/users"})
        self.assertEqual(r["statut"], "refuse")                                                          # la requête libre reste un droit à part
        self.assertIn("dolibarr.libre", r["raison"])

    def test_mes_droits_a_moi_ne_rend_que_ceux_du_compte_qui_demande(self):
        self.n.identite.creer("chef@x.fr", "Abcdefgh1!", superadmin=True)
        self.n.identite.creer("paul@x.fr", "Abcdefgh1!")
        self.n.droits.regler("compte", "paul@x.fr", "dolibarr.facturer", "accorde")
        r = self.e("droits.mes_droits_a_moi", "humain", {}, compte="paul@x.fr")
        if r["statut"] != "faite":
            self.skipTest("le module des droits n'est pas dans ce banc : %s" % r)
        d = r["resultat"]
        self.assertEqual((d["compte"], d["admin"]), ("paul@x.fr", False))
        self.assertIn("dolibarr.facturer", d["droits"])
        self.assertIn("dolibarr.consulter", d["droits"])
        self.assertNotIn("dolibarr.valider", d["droits"])

    def test_le_don_porte_les_champs_de_sa_fiche_dolibarr(self):
        r = self.e("dolibarr.don_creer", "humain", {"montant": "20", "date": "2026-11-01", "nom": "Martin", "prenom": "Léa", "societe": "",
                                                    "champs": {"address": "1 rue X", "zip": "44000", "town": "Nantes", "country_id": "1", "email": "lea@exemple.fr", "public": "0", "note_private": "n"}})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        d = self.faux.t["donations"][r["resultat"]["id"]]
        self.assertEqual((d["lastname"], d["firstname"], d["town"], d["email"], d["public"]), ("Martin", "Léa", "Nantes", "lea@exemple.fr", "0"))
        self.assertEqual(self.e("dolibarr.don_creer", "humain", {"montant": "5", "champs": {"inconnu": "x"}})["statut"], "echec")           # un champ hors fiche est refusé

    def test_on_joint_un_document_a_une_facture_on_le_relit_et_on_le_retire(self):
        i = self.facture()
        contenu = base64.b64encode(b"%PDF-1.4 note du benevole").decode()
        r = self.e("dolibarr.document_ajouter", "humain", {"objet": "factures", "id": i, "nom": "justificatif.pdf", "donnees_b64": contenu})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        liste = self.e("dolibarr.documents", "humain", {"objet": "factures", "id": i})["resultat"]
        self.assertEqual([d["nom"] for d in liste["documents"]], ["justificatif.pdf"])
        lu = self.e("dolibarr.document_lire", "humain", {"objet": "factures", "id": i, "nom": "justificatif.pdf"})
        self.assertEqual(lu["statut"], "faite", msg=str(lu))
        self.assertEqual(base64.b64decode(lu["resultat"]["donnees_b64"]), b"%PDF-1.4 note du benevole")
        # le même nom deux fois : refusé, jamais écrasé
        self.assertEqual(self.e("dolibarr.document_ajouter", "humain", {"objet": "factures", "id": i, "nom": "justificatif.pdf", "donnees_b64": contenu})["statut"], "echec")
        # un retour arrière retire exactement ce fichier
        self.retour("document_ajouter", r["resultat"])
        self.assertEqual(self.e("dolibarr.documents", "humain", {"objet": "factures", "id": i})["resultat"]["documents"], [])

    def test_un_document_joint_refuse_ce_qui_ressemble_a_une_page_ou_un_script(self):
        i = self.facture()
        ok = base64.b64encode(b"x").decode()
        for nom in ("shell.php", "page.html", "../../x.pdf", "a/b.pdf", ".htaccess", "sans_extension", "script.js", "image.svg"):
            r = self.e("dolibarr.document_ajouter", "humain", {"objet": "factures", "id": i, "nom": nom, "donnees_b64": ok})
            self.assertEqual(r["statut"], "echec", nom)
        self.assertEqual(self.e("dolibarr.document_ajouter", "humain", {"objet": "factures", "id": i, "nom": "a.pdf", "donnees_b64": "pas du base64 !"})["statut"], "echec")
        self.assertEqual(self.e("dolibarr.document_ajouter", "humain", {"objet": "factures", "id": i, "nom": "a.pdf", "donnees_b64": base64.b64encode(b"0" * (5 * 2 ** 20 + 1)).decode()})["statut"], "echec")
        self.assertEqual(self.e("dolibarr.document_ajouter", "humain", {"objet": "inconnu", "id": i, "nom": "a.pdf", "donnees_b64": ok})["statut"], "echec")

    def test_joindre_un_document_demande_le_droit_de_facturer(self):
        self.n.identite.creer("chef@x.fr", "Abcdefgh1!", superadmin=True)
        self.n.identite.creer("paul@x.fr", "Abcdefgh1!")
        i = self.facture()
        pour = lambda cap, args: self.e("dolibarr." + cap, "humain", args, compte="paul@x.fr")
        self.assertEqual(pour("documents", {"objet": "factures", "id": i})["statut"], "faite")            # consulter : lire la liste
        r = pour("document_ajouter", {"objet": "factures", "id": i, "nom": "a.pdf", "donnees_b64": base64.b64encode(b"x").decode()})
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("dolibarr.facturer", r["raison"])

    def test_devis_commande_facture_se_suivent_et_se_defont(self):
        t = self.faux.nouveau("thirdparties", {"name": "Cie Les Pierrots", "client": 1})
        lignes = [{"desc": "Animation", "qty": 1, "subprice": 450, "tva_tx": 0}]
        brouillon = self.faux.nouveau("proposals", {"socid": t, "lines": lignes, "statut": "1", "ref": "PR1"})
        self.assertEqual(self.e("dolibarr.commande_creer", "humain", {"devis": brouillon})["statut"], "echec")                       # un devis non signé ne devient pas commande
        signe = self.faux.nouveau("proposals", {"socid": t, "lines": lignes, "statut": "2", "ref": "PR2"})
        c = self.e("dolibarr.commande_creer", "humain", {"devis": signe})
        self.assertEqual(c["statut"], "faite", msg=str(c))
        cid = c["resultat"]["id"]
        self.assertEqual(self.e("dolibarr.facturer_commande", "humain", {"id": cid})["statut"], "echec")                              # une commande en brouillon ne se facture pas
        self.assertEqual(self.e("dolibarr.commande", "humain", {"id": cid, "action": "livrer"})["statut"], "echec")                   # on valide avant de livrer
        v = self.e("dolibarr.commande", "humain", {"id": cid, "action": "valider"})
        self.assertEqual(v["statut"], "faite", msg=str(v))
        self.assertEqual(self.faux.t["orders"][cid]["statut"], "1")
        f = self.e("dolibarr.facturer_commande", "humain", {"id": cid})
        self.assertEqual(f["statut"], "faite", msg=str(f))
        facture = self.faux.t["invoices"][f["resultat"]["id"]]
        self.assertEqual((facture["statut"], facture["lines"], facture["socid"]), ("0", lignes, t))
        l = self.e("dolibarr.commande", "humain", {"id": cid, "action": "livrer"})
        self.assertEqual(l["statut"], "faite", msg=str(l))
        # chaque geste se défait, dans l'ordre inverse
        self.retour("commande", l["resultat"])
        self.assertEqual(self.faux.t["orders"][cid]["statut"], "1")
        self.retour("facturer_commande", f["resultat"])
        self.assertNotIn(f["resultat"]["id"], self.faux.t["invoices"])
        self.retour("commande", v["resultat"])
        self.assertEqual(self.faux.t["orders"][cid]["statut"], "0")
        self.retour("commande_creer", c["resultat"])
        self.assertNotIn(cid, self.faux.t["orders"])

    def test_une_facture_fournisseur_se_prepare_se_valide_et_se_defait(self):
        t = self.faux.nouveau("thirdparties", {"name": "Imprimerie", "fournisseur": 1})
        ligne = [{"desc": "Affiches", "qty": 1, "subprice": 80, "tva_tx": 20}]
        sans_ref = self.e("dolibarr.creer_brouillon", "humain", {"objet": "fournisseurs", "socid": t, "lignes": ligne})
        self.assertEqual(sans_ref["statut"], "echec")                                                  # Dolibarr exige la réf. du fournisseur
        r = self.e("dolibarr.creer_brouillon", "humain", {"objet": "fournisseurs", "socid": t, "lignes": ligne, "champs": {"ref_supplier": "F-2026-14", "date_echeance": "2026-12-15"}})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        fid = r["resultat"]["id"]
        v = self.e("dolibarr.facture_fournisseur_valider", "humain", {"id": fid})
        self.assertEqual(v["statut"], "faite", msg=str(v))
        self.assertEqual(self.faux.t["supplierinvoices"][fid]["statut"], "1")
        self.assertEqual(self.e("dolibarr.facture_fournisseur_valider", "humain", {"id": fid})["statut"], "echec")        # déjà validée
        self.retour("facture_fournisseur_valider", v["resultat"])
        self.assertEqual(self.faux.t["supplierinvoices"][fid]["statut"], "0")
        self.retour("creer_brouillon", r["resultat"])
        self.assertNotIn(fid, self.faux.t["supplierinvoices"])

    def test_une_commande_fournisseur_avance_pas_a_pas_et_ne_se_defait_pas_par_l_api(self):
        t = self.faux.nouveau("thirdparties", {"name": "Imprimerie", "fournisseur": 1})
        r = self.e("dolibarr.creer_brouillon", "humain", {"objet": "commandes_fournisseurs", "socid": t, "lignes": [{"desc": "Scène", "qty": 1, "subprice": 300, "tva_tx": 0}]})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        oid = r["resultat"]["id"]
        self.assertEqual(self.e("dolibarr.commande_fournisseur", "humain", {"id": oid, "action": "commander"})["statut"], "echec")      # on valide et on approuve d'abord
        for action, etat in (("valider", "1"), ("approuver", "2"), ("commander", "3")):
            x = self.e("dolibarr.commande_fournisseur", "humain", {"id": oid, "action": action})
            self.assertEqual(x["statut"], "faite", msg=str(x))
            self.assertEqual(self.faux.t["supplierorders"][oid]["statut"], etat)
        with self.assertRaises(Exception):
            self.retour("commande_fournisseur", x["resultat"])                                                                         # aucun retour par l'API

    def test_une_note_de_frais_se_saisit_avec_ses_totaux_se_valide_et_se_defait(self):
        o = self.e("dolibarr.frais_options", "humain", {})
        self.assertEqual(o["statut"], "faite", msg=str(o))
        self.assertEqual([x["id"] for x in o["resultat"]["types"]], [29])                                                              # le type inactif n'est pas proposé
        self.assertEqual(set(o["resultat"]["utilisateurs"][0]), {"id", "login", "nom"})
        self.assertNotIn("SECRET-A-NE-PAS-MONTRER", json.dumps(o))                                                                     # jamais de clé ni de mot de passe
        args = {"auteur": 7, "debut": "2026-10-01", "fin": "2026-10-31", "type": 29, "note": "Bénévole",
                "lignes": [{"desc": "Trajet aller-retour", "qty": 2, "subprice": 12.5, "tva_tx": 20, "date": "2026-10-12"}, {"desc": "Péage", "qty": 1, "subprice": 8, "tva_tx": 0}]}
        r = self.e("dolibarr.frais_creer", "humain", args)
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(r["resultat"]["total"], 38.0)                                                                                  # 25 + 5 de TVA + 8
        fid = r["resultat"]["id"]
        for mauvais in (dict(args, fin="2026-09-30"), dict(args, lignes=[]), dict(args, lignes=[{"desc": "x", "qty": 0, "subprice": 5}]), dict(args, auteur="x")):
            self.assertEqual(self.e("dolibarr.frais_creer", "humain", mauvais)["statut"], "echec")
        self.assertEqual(self.e("dolibarr.frais_etat", "humain", {"id": fid, "action": "approuver"})["statut"], "echec")               # on valide d'abord
        v = self.e("dolibarr.frais_etat", "humain", {"id": fid, "action": "valider"})
        a = self.e("dolibarr.frais_etat", "humain", {"id": fid, "action": "approuver"})
        self.assertEqual((v["statut"], a["statut"]), ("faite", "faite"), msg=str((v, a)))
        self.assertEqual(self.faux.t["expensereports"][fid]["status"], 5)
        self.retour("frais_etat", a["resultat"])
        self.assertEqual(self.faux.t["expensereports"][fid]["status"], 2)                                                              # revient à « validée »
        self.retour("frais_etat", v["resultat"])
        self.assertEqual(self.faux.t["expensereports"][fid]["status"], 0)
        self.retour("frais_creer", r["resultat"])
        self.assertNotIn(fid, self.faux.t["expensereports"])

    def test_un_rib_se_verifie_se_range_et_se_retire(self):
        t = self.faux.nouveau("thirdparties", {"name": "Cie Les Pierrots", "fournisseur": 1})
        iban = "FR76 3000 6000 0112 3456 7890 189"                 # l'IBAN d'exemple de la Banque de France : la clé de contrôle est bonne
        r = self.e("dolibarr.rib_creer", "humain", {"tiers": t, "label": "Compte principal", "iban": iban, "bic": "agrifrpp", "banque": "Crédit Agricole"})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        liste = self.e("dolibarr.rib_lister", "humain", {"tiers": 1})["resultat"]["ribs"]
        self.assertEqual([(x["iban"], x["bic"]) for x in liste], [("FR7630006000011234567890189", "AGRIFRPP")])
        self.assertEqual(self.e("dolibarr.rib_creer", "humain", {"tiers": t, "label": "Autre", "iban": iban})["statut"], "echec")          # jamais deux fois le même IBAN
        for mauvais in ("FR7630006000011234567890188", "FR76", "1234", "FR76 ABCD !!!!"):
            self.assertEqual(self.e("dolibarr.rib_creer", "humain", {"tiers": t, "label": "X", "iban": mauvais})["statut"], "echec", mauvais)
        self.assertEqual(self.e("dolibarr.rib_creer", "humain", {"tiers": t, "label": "X", "iban": "DE89370400440532013000", "bic": "faux"})["statut"], "echec")
        self.assertEqual(self.e("dolibarr.rib_creer", "humain", {"tiers": 999, "label": "X", "iban": "DE89370400440532013000"})["statut"], "echec")
        self.retour("rib_creer", r["resultat"])
        self.assertEqual(self.e("dolibarr.rib_lister", "humain", {"tiers": 1})["resultat"]["ribs"], [])

    def test_un_rib_ne_se_change_que_par_un_humain_avec_le_droit_de_tresorerie(self):
        self.n.identite.creer("chef@x.fr", "Abcdefgh1!", superadmin=True)
        self.n.identite.creer("paul@x.fr", "Abcdefgh1!")
        t = self.faux.nouveau("thirdparties", {"name": "Cie Les Pierrots", "fournisseur": 1})
        args = {"tiers": t, "label": "X", "iban": "DE89370400440532013000"}
        r = self.e("dolibarr.rib_creer", "humain", args, compte="paul@x.fr")
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("dolibarr.tresorerie", r["raison"])
        self.assertEqual(self.e("dolibarr.rib_lister", "humain", {"tiers": 1}, compte="paul@x.fr")["statut"], "refuse")                      # même la lecture : un IBAN est sensible
        self.assertNotEqual(self.e("dolibarr.rib_creer", "itare", args, compte="chef@x.fr")["statut"], "faite")                             # un agent ne change jamais un RIB

    def test_un_don_avec_recu_fiscal_exige_l_identite_complete_du_donateur(self):
        complet = {"address": "1 rue X", "zip": "44000", "town": "Nantes", "email": "lea@exemple.fr"}
        r = self.e("dolibarr.don_creer", "humain", {"montant": "20", "nom": "Martin", "recu": True, "champs": {"zip": "44000"}})
        self.assertEqual(r["statut"], "echec")
        for mot in ("l'adresse", "la ville", "le courriel"):
            self.assertIn(mot, json.dumps(r, ensure_ascii=False))
        self.assertNotIn("code postal", json.dumps(r, ensure_ascii=False))                                                    # ce qui est donné ne se réclame pas
        self.assertEqual(self.e("dolibarr.don_creer", "humain", {"montant": "20", "recu": True, "champs": complet})["statut"], "echec")        # ni nom ni société
        self.assertEqual(self.e("dolibarr.don_creer", "humain", {"montant": "20", "societe": "Cie Les Pierrots", "recu": True, "champs": complet})["statut"], "faite")
        self.assertEqual(self.e("dolibarr.don_creer", "humain", {"montant": "5"})["statut"], "faite")                                         # un don anonyme reste possible

    def test_le_statut_donne_la_racine_de_dolibarr_pour_ouvrir_une_fiche(self):
        r = self.e("dolibarr.statut", "humain", {})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertNotIn("/api", r["resultat"]["site"])
        self.assertTrue(r["resultat"]["site"].startswith("http"))

    def test_les_autres_fiches_ont_leurs_champs_et_leurs_obligations(self):
        for objet, ok, ko in (("contacts", {"lastname": "Fontaine", "civility_code": "MME", "poste": "Régie", "email": "a@b.fr"}, {"firstname": "Léa"}),
                              ("produits", {"label": "Billet", "type": "1", "price_base_type": "HT", "price": "15", "tva_tx": "0", "barcode": "123"}, {"ref": "X"}),
                              ("projets", {"title": "Soirée", "usage_opportunity": "0", "budget_amount": "100"}, {"description": "x"})):
            self.assertNotIn("obligatoire", json.dumps(self.e("dolibarr.creer", "humain", {"objet": objet, "champs": ok}), ensure_ascii=False), objet)
            self.assertIn("obligatoire", json.dumps(self.e("dolibarr.creer", "humain", {"objet": objet, "champs": ko}), ensure_ascii=False), objet)

    def test_le_refus_de_dolibarr_est_dit_avec_son_message(self):
        import io, urllib.error
        import importlib.util as iu
        sp = iu.spec_from_file_location("dolibarr_mod_msg", RACINE / "modules" / "dolibarr" / "CN_module.py")
        mod = iu.module_from_spec(sp)
        sp.loader.exec_module(mod)
        e = urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO('{"error":{"code":500,"message":"ErrorBadEMail essai"}}'.encode()))
        self.assertEqual(mod._dit_dolibarr(e), " : ErrorBadEMail essai")
        self.assertEqual(mod._dit_dolibarr(urllib.error.HTTPError("u", 500, "x", {}, io.BytesIO(b"pas du json"))), "")

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

    def test_l_en_tete_d_une_facture_ou_d_un_devis_porte_les_champs_de_la_fiche_dolibarr(self):
        r = self.e("dolibarr.creer_brouillon", "humain", {"objet": "factures", "socid": 3, "lignes": [{"desc": "x", "qty": 2, "subprice": 5, "tva_tx": 20, "remise_percent": 10}],
                                                          "champs": {"ref_client": "CMD-42", "date": "2026-11-02", "date_lim_reglement": "2026-12-02", "cond_reglement_id": "4", "mode_reglement_id": 2, "fk_account": "1", "note_public": "Merci"}})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        f = self.faux.t["invoices"][r["resultat"]["id"]]
        self.assertEqual((f["ref_client"], f["cond_reglement_id"], f["mode_reglement_id"], f["fk_account"], f["note_public"]), ("CMD-42", 4, 2, 1, "Merci"))
        self.assertEqual((f["date_lim_reglement"] - f["date"]) // 86400, 30)                      # des dates en jours, comme la fiche
        d = self.e("dolibarr.creer_brouillon", "humain", {"objet": "devis", "socid": 3, "lignes": [{"desc": "x", "qty": 1, "subprice": 1}], "champs": {"duree_validite": "15"}})
        self.assertEqual(self.faux.t["proposals"][d["resultat"]["id"]]["duree_validite"], 15)
        for mauvais in ({"inconnu": "1"}, {"fk_account": "abc"}, {"date_lim_reglement": "demain"}):                  # un champ hors fiche, un nombre faux, une date fausse
            self.assertEqual(self.e("dolibarr.creer_brouillon", "humain", {"objet": "factures", "socid": 3, "lignes": [{"desc": "x", "qty": 1, "subprice": 1}], "champs": mauvais})["statut"], "echec", mauvais)

    def test_les_impayees_comptent_ce_qui_reste_du_et_pas_le_total_des_factures(self):
        i = self.facture(total=120.0)
        self.facture(total=50.0)
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 40, "banque": 1})["statut"], "faite")
        r = self.e("dolibarr.impayees", "humain", {})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual((r["resultat"]["n"], r["resultat"]["total_ttc"]), (2, 130.0))        # 80 + 50, pas 120 + 50

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
            for d in DROITS_DOLIBARR:
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

    # --- le catalogue, le paiement d'une facture reçue, les réglages propres au compte
    def test_le_catalogue_de_l_api_compte_les_operations_par_domaine(self):
        r = self.e("dolibarr.catalogue_api", "humain", {})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(r["resultat"]["operations"], 7)
        self.assertEqual(r["resultat"]["domaines"][0], {"domaine": "invoices", "lire": 2, "creer": 1, "modifier": 1, "supprimer": 1})

    def test_payer_une_facture_recue_se_prouve_et_se_defait(self):
        i = self.faux.nouveau("supplierinvoices", {"statut": "1", "paye": "0", "total_ttc": 80, "ref": "SI2610-0001"})
        r = self.e("dolibarr.payer_fournisseur", "humain", {"id": i, "banque": 1})
        self.assertEqual(r["statut"], "faite", msg=str(r))
        self.assertEqual(self.faux.t["supplierinvoices"][i]["paye"], "1")
        self.retour("payer_fournisseur", r["resultat"])
        self.assertEqual(self.faux.t["supplierinvoices"][i]["paye"], "0")
        self.assertEqual(self.e("dolibarr.payer_fournisseur", "humain", {"id": 999, "banque": 1})["statut"], "echec")

    def test_le_compte_peut_interdire_l_ecriture_a_son_itare_et_lui_fixer_un_seuil(self):
        self.accorder("drisse")
        self.poser_cle("drisse", CLE_DRISSE)
        self.n.catalogue.regler_palier("dolibarr.encaisser", "auto")
        i = self.facture(total=900.0)
        self.assertEqual(self.e("dolibarr.encaisser", "itare", {"id": i, "montant": 100, "banque": 1}, compte="drisse")["statut"], "faite")      # libre par défaut
        self.n.reglages.poser("dolibarr.itare_seuil", 150, compte="drisse")
        r = self.e("dolibarr.encaisser", "itare", {"id": i, "montant": 200, "banque": 1}, compte="drisse")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("seuil", json.dumps(r, ensure_ascii=False))
        self.assertEqual(self.e("dolibarr.encaisser", "itare", {"id": i, "montant": 100, "banque": 1}, compte="drisse")["statut"], "faite")      # sous le seuil
        self.assertEqual(self.e("dolibarr.encaisser", "humain", {"id": i, "montant": 200, "banque": 1}, compte="drisse")["statut"], "faite")      # un humain n'a pas de seuil
        self.n.reglages.poser("dolibarr.itare_ecrire", "desactive", compte="drisse")
        self.n.catalogue.regler_palier("dolibarr.relancer", "auto")          # au palier « raconter », il ne ferait que proposer : la garde ne joue que pour ce qui s'exécute seul
        self.faux.journal.clear()
        self.assertEqual(self.e("dolibarr.relancer", "itare", {"id": i, "message": "x"}, compte="drisse")["statut"], "echec")
        self.assertFalse([1 for m, _, _ in self.faux.journal if m != "GET"])
        self.assertEqual(self.e("dolibarr.lire_libre", "itare", {"chemin": "/invoices/%d" % i}, compte="drisse")["statut"], "faite")           # il lit toujours


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
            [self.n.droits.regler("compte", c, d, "accorde") for d in DROITS_DOLIBARR]
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
