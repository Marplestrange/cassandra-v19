"""Bancs du coffre : le magasin de secrets, réversible, contre un faux serveur Vaultwarden."""
import json
import shutil
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

BEA = "bea@x.fr"


class FauxVault(BaseHTTPRequestHandler):
    items = {}
    prochain = 1

    def _json(self, d, code=200):
        b = json.dumps(d).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path == "/status":
            return self._json({"success": True, "data": {"template": {"status": "unlocked", "userEmail": "cassandra@vault.local", "serverUrl": "http://127.0.0.1"}}})
        if self.path.startswith("/list/object/items"):
            if "search=" in self.path:
                import urllib.parse
                q = urllib.parse.unquote(self.path.split("search=", 1)[1])
                data = [v for k, v in self.items.items() if k == q]
            else:
                data = list(self.items.values())
            return self._json({"success": True, "data": {"data": data}})
        return self._json({"success": False, "error": "not found"}, 404)

    def do_POST(self):
        if self.path == "/object/item":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            FauxVault.prochain += 1
            it = {"id": str(FauxVault.prochain), "name": body.get("name"), "notes": body.get("notes")}
            self.items[body.get("name")] = it
            return self._json({"success": True, "data": {"id": it["id"]}})
        return self._json({"success": False, "error": "not found"}, 404)

    def do_PUT(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        self.items[body.get("name")] = {"id": body.get("id"), "name": body.get("name"), "notes": body.get("notes")}
        return self._json({"success": True, "data": {"id": body.get("id")}})

    def do_DELETE(self):
        # /object/item/<id>
        rid = self.path.rsplit("/", 1)[-1]
        for k, v in list(self.items.items()):
            if v.get("id") == rid:
                del self.items[k]
        return self._json({"success": True})

    def log_message(self, *a):
        pass


class Monde(unittest.TestCase):
    def setUp(self):
        FauxVault.items = {}
        FauxVault.prochain = 1
        self.httpd = HTTPServer(("127.0.0.1", 0), FauxVault)
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()
        self.addCleanup(self.httpd.shutdown)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("coffre", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "coffre"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["coffre"]
        self.db = self.ctx.stockage
        self.ctx.reglage = lambda nom, compte=None: self.url if nom == "vault_url" else (8 if nom == "vault_timeout" else "")

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("coffre." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_status_et_disponible(self):
        self.assertTrue(self.s("status")["available"])
        self.assertTrue(self.s("available")["disponible"])

    def test_poser_lire_lister_et_retirer_un_secret(self):
        self.s("set", name="cassandra/cle-api", valeur="une-valeur")
        self.assertEqual(self.s("get", name="cassandra/cle-api")["valeur"], "une-valeur")
        self.assertIn("cassandra/cle-api", self.s("list", prefix="cassandra/")["noms"])
        self.assertEqual(self.s("get", name="absent")["valeur"], None)
        # le retrait est réversible
        res = self.ex("coffre.delete", name="cassandra/cle-api")
        self.assertEqual(self.s("get", name="cassandra/cle-api")["valeur"], None)
        self.n.catalogue.get("coffre.delete").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("get", name="cassandra/cle-api")["valeur"], "une-valeur")

    def test_poser_est_reversible(self):
        self.s("set", name="x", valeur="un")
        res = self.ex("coffre.set", name="x", valeur="deux")
        self.assertEqual(self.s("get", name="x")["valeur"], "deux")
        self.n.catalogue.get("coffre.set").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("get", name="x")["valeur"], "un")

    def test_la_liste_ne_sort_jamais_les_valeurs(self):
        self.s("set", name="a", valeur="secret-a")
        noms = self.s("list")["noms"]
        self.assertIn("a", noms)
        self.assertTrue(all("secret" not in n for n in noms))

    def test_le_journal_inscrit_les_acces(self):
        self.s("set", name="j", valeur="v")
        self.s("get", name="j")
        j = self.s("journal")["journal"]
        self.assertGreaterEqual(len(j), 2)


if __name__ == "__main__":
    unittest.main()
