# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du coffre
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #c9dff2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du coffre : le magasin de secrets, réversible, contre un faux serveur Vaultwarden.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c9dff2 ▼▼▼
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
CAM, DAN, EVE, FRED = "cam@x.fr", "dan@x.fr", "eve@x.fr", "fred@x.fr"
MDP = "Abcdefgh1!"


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

    # ── les espaces : chacun ne voit que le sien ─────────────────────────────
    def creer(self, *comptes):
        for c in comptes:
            r = self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP}, compte="")
            self.assertEqual(r["statut"], "faite", r)

    def refuse(self, cap, compte=BEA, **args):
        r = self.ex("coffre." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "echec", r)
        return r

    def societe(self, admin=BEA, sid="1"):
        """Une société avec son espace ; `admin` en est le premier administrateur (sans accès aux secrets tant qu'il ne s'en donne pas)."""
        self.creer(BEA, CAM, DAN, EVE, FRED)
        self.s("espace_creer", compte=BEA, societe=sid, nom="Atelier Lumen", admin=admin)
        return "s:" + sid

    def test_un_compte_ne_voit_que_son_coffre(self):
        self.creer(BEA, CAM)
        self.s("set", compte=BEA, name="banque", valeur="1234")
        self.assertEqual(self.s("list", compte=BEA)["noms"], ["banque"])
        self.assertEqual(self.s("list", compte=CAM)["noms"], [])                          # CAM ne voit rien de BEA
        self.assertIsNone(self.s("get", compte=CAM, name="banque")["valeur"])            # pas même par son nom
        self.assertEqual(self.s("get", compte=BEA, name="banque")["valeur"], "1234")

    def test_nul_ne_lit_l_espace_d_un_autre_pas_meme_l_administrateur_de_l_instance(self):
        self.creer(BEA, CAM)                                                              # BEA, la première, est administratrice
        self.assertTrue(self.n.droits.est_admin(BEA))
        self.s("set", compte=CAM, name="perso", valeur="a-moi")
        for cap, args in (("get", {"name": "perso"}), ("list", {}), ("set", {"name": "perso", "valeur": "x"}), ("delete", {"name": "perso"}), ("journal", {})):
            self.refuse(cap, compte=BEA, espace="u:" + CAM, **args)                      # nommer l'espace d'un autre ne l'ouvre pas
        self.assertEqual(self.s("get", compte=CAM, name="perso")["valeur"], "a-moi")

    def test_sans_compte_le_coffre_ne_s_ouvre_pas(self):
        r = self.ex("coffre.list", compte="")
        self.assertNotEqual(r["statut"], "faite")

    def test_deux_comptes_peuvent_avoir_le_meme_nom_de_secret(self):
        self.creer(BEA, CAM)
        self.s("set", compte=BEA, name="cle", valeur="celle-de-bea")
        self.s("set", compte=CAM, name="cle", valeur="celle-de-cam")
        self.assertEqual(self.s("get", compte=BEA, name="cle")["valeur"], "celle-de-bea")
        self.assertEqual(self.s("get", compte=CAM, name="cle")["valeur"], "celle-de-cam")

    def test_un_espace_de_societe_a_ses_roles(self):
        esp = self.societe()
        # l'administrateur du coffre gère les accès, mais ne lit rien tant qu'il ne s'est pas ouvert une collection
        self.refuse("set", compte=BEA, espace=esp, name="k0", valeur="x")
        self.ex_accorder(BEA, esp, CAM, "membre")
        self.ex_accorder(BEA, esp, DAN, "contrib")
        self.ex_accorder(BEA, esp, EVE, "lecture")
        self.s("set", compte=CAM, espace=esp, name="k1", valeur="v1")                    # membre : lit et écrit
        self.assertEqual(self.s("get", compte=CAM, espace=esp, name="k1")["valeur"], "v1")
        self.assertEqual(self.s("get", compte=EVE, espace=esp, name="k1")["valeur"], "v1")   # lecture : lit
        self.refuse("set", compte=EVE, espace=esp, name="k1", valeur="x")                  # …n'écrit pas
        # contributeur : écrit, mais ne relit QUE ses propres secrets
        self.s("set", compte=DAN, espace=esp, name="k2", valeur="v2")
        self.assertEqual(self.s("get", compte=DAN, espace=esp, name="k2")["valeur"], "v2")
        self.assertIsNone(self.s("get", compte=DAN, espace=esp, name="k1")["valeur"])
        self.assertEqual(self.s("list", compte=DAN, espace=esp)["noms"], ["k2"])
        self.refuse("set", compte=DAN, espace=esp, name="k1", valeur="écrasé")             # ni ne touche à ceux des autres
        self.refuse("delete", compte=DAN, espace=esp, name="k1")
        self.assertEqual(self.s("get", compte=CAM, espace=esp, name="k2")["valeur"], "v2")   # le membre voit ce que le contributeur a déposé
        # un étranger n'a rien : ni lecture, ni liste, ni écriture
        for cap, args in (("get", {"name": "k1"}), ("list", {}), ("set", {"name": "k9", "valeur": "x"})):
            self.refuse(cap, compte=FRED, espace=esp, **args)

    def ex_accorder(self, qui, esp, cible, role, **plus):
        r = self.ex("coffre.accorder", compte=qui, **dict({"espace": esp, "utilisateur": cible, "role": role}, **plus))
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_l_administrateur_du_coffre_s_ouvre_lui_meme_une_collection_et_c_est_journalise(self):
        esp = self.societe()
        self.refuse("set", compte=BEA, espace=esp, name="k", valeur="x")
        self.ex_accorder(BEA, esp, BEA, "admin", collections="*")
        self.s("set", compte=BEA, espace=esp, name="k", valeur="x")
        actes = [j["action"] for j in self.s("journal", compte=BEA, espace=esp)["journal"]]
        self.assertTrue(any(a.startswith("accorder:") for a in actes), actes)

    def test_les_collections_limitent_ce_qu_un_membre_voit(self):
        esp = self.societe()
        self.ex_accorder(BEA, esp, BEA, "admin", collections="*")
        self.ex_accorder(BEA, esp, CAM, "membre", collections="compta")
        self.s("set", compte=BEA, espace=esp, name="banque", valeur="b", collection="compta")
        self.s("set", compte=BEA, espace=esp, name="hebergeur", valeur="h", collection="hebergement")
        self.assertEqual(self.s("list", compte=CAM, espace=esp)["noms"], ["banque"])
        self.assertEqual(self.s("get", compte=CAM, espace=esp, name="banque")["valeur"], "b")
        self.assertIsNone(self.s("get", compte=CAM, espace=esp, name="hebergeur")["valeur"])
        self.refuse("set", compte=CAM, espace=esp, name="autre", valeur="x", collection="hebergement")

    def test_un_acces_expire_s_eteint_seul(self):
        esp = self.societe()
        self.ex_accorder(BEA, esp, BEA, "admin", collections="*")
        self.s("set", compte=BEA, espace=esp, name="k", valeur="v")
        self.ex_accorder(BEA, esp, CAM, "membre", expire="2020-01-01")                     # déjà échu
        self.refuse("get", compte=CAM, espace=esp, name="k")
        self.ex_accorder(BEA, esp, CAM, "membre", expire="2999-01-01")
        self.assertEqual(self.s("get", compte=CAM, espace=esp, name="k")["valeur"], "v")
        self.refuse("accorder", compte=BEA, espace=esp, utilisateur=CAM, role="membre", expire="pas-une-date")

    def test_le_dernier_administrateur_du_coffre_reste(self):
        esp = self.societe()
        self.refuse("retirer", compte=BEA, espace=esp, utilisateur=BEA)
        self.refuse("accorder", compte=BEA, espace=esp, utilisateur=BEA, role="membre")  # pas de rétrogradation non plus
        self.ex_accorder(BEA, esp, CAM, "admin")
        r = self.ex("coffre.retirer", compte=BEA, espace=esp, utilisateur=BEA)            # CAM veille : BEA peut partir
        self.assertEqual(r["statut"], "faite", r)

    def test_seul_un_administrateur_du_coffre_gere_les_acces(self):
        esp = self.societe()
        self.ex_accorder(BEA, esp, CAM, "membre")
        self.refuse("accorder", compte=CAM, espace=esp, utilisateur=DAN, role="membre")
        self.refuse("membres", compte=CAM, espace=esp)
        self.refuse("retirer", compte=FRED, espace=esp, utilisateur=CAM)
        self.assertEqual({m["compte"] for m in self.s("membres", compte=BEA, espace=esp)["membres"]}, {BEA, CAM})

    def test_les_espaces_d_un_compte_sont_les_siens_et_ceux_ou_on_l_a_fait_entrer(self):
        esp = self.societe()
        self.ex_accorder(BEA, esp, CAM, "membre")
        vus = {e["id"]: e for e in self.s("espaces", compte=CAM)["espaces"]}
        self.assertEqual(set(vus), {"u:" + CAM, esp})
        self.assertEqual(vus[esp]["role"], "membre")
        self.assertEqual(set(e["id"] for e in self.s("espaces", compte=FRED)["espaces"]), {"u:" + FRED})   # l'étranger n'apprend rien

    def test_un_espace_archive_n_ouvre_plus(self):
        esp = self.societe()
        self.ex_accorder(BEA, esp, BEA, "admin", collections="*")
        self.s("set", compte=BEA, espace=esp, name="k", valeur="v")
        self.s("espace_archiver", compte=BEA, espace=esp)
        self.refuse("get", compte=BEA, espace=esp, name="k")
        self.assertEqual(set(e["id"] for e in self.s("espaces", compte=BEA)["espaces"]), {"u:" + BEA})

    def test_ouvrir_ou_archiver_un_espace_demande_le_droit_d_administrer(self):
        self.creer(BEA, CAM)                                                              # CAM n'est pas administratrice
        self.assertEqual(self.ex("coffre.espace_creer", compte=CAM, societe="9", nom="X")["statut"], "refuse")

    def test_un_coffre_externe_n_est_pas_lu_par_l_instance(self):
        esp = self.societe()
        self.ex_accorder(BEA, esp, BEA, "admin", collections="*")
        self.s("regler", compte=BEA, espace=esp, mode="externe", url="https://coffre.exemple.test")
        r = self.refuse("set", compte=BEA, espace=esp, name="k", valeur="v")
        self.assertIn("hors de l'instance", r["erreur"])
        self.refuse("regler", compte=BEA, espace=esp, mode="externe", url="pas-une-adresse")

    def test_les_acces_se_defont(self):
        esp = self.societe()
        res = self.ex_accorder(BEA, esp, CAM, "membre")
        self.n.catalogue.get("coffre.accorder").defaire(self.ctx, res)
        self.refuse("get", compte=CAM, espace=esp, name="k")
        res = self.ex_accorder(BEA, esp, CAM, "membre")
        r = self.ex("coffre.retirer", compte=BEA, espace=esp, utilisateur=CAM)
        self.n.catalogue.get("coffre.retirer").defaire(self.ctx, r["resultat"])
        self.assertIn(CAM, {m["compte"] for m in self.s("membres", compte=BEA, espace=esp)["membres"]})

    def test_defaire_un_secret_rend_aussi_son_auteur(self):
        esp = self.societe()
        self.ex_accorder(BEA, esp, CAM, "membre")
        self.ex_accorder(BEA, esp, DAN, "contrib")
        self.s("set", compte=DAN, espace=esp, name="k", valeur="un")
        res = self.ex("coffre.delete", compte=DAN, espace=esp, name="k")
        self.assertEqual(self.s("list", compte=DAN, espace=esp)["noms"], [])
        self.n.catalogue.get("coffre.delete").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("get", compte=DAN, espace=esp, name="k")["valeur"], "un")  # l'auteur est revenu : DAN relit son secret
        self.assertIsNone(self.s("get", compte=CAM, espace=esp, name="inconnu")["valeur"])

    def test_le_journal_d_un_membre_ordinaire_ne_montre_que_ses_gestes(self):
        esp = self.societe()
        self.ex_accorder(BEA, esp, BEA, "admin", collections="*")
        self.ex_accorder(BEA, esp, CAM, "membre")
        self.s("set", compte=BEA, espace=esp, name="k1", valeur="a")
        self.s("set", compte=CAM, espace=esp, name="k2", valeur="b")
        vus_cam = {j["username"] for j in self.s("journal", compte=CAM, espace=esp)["journal"]}
        vus_bea = {j["username"] for j in self.s("journal", compte=BEA, espace=esp)["journal"]}
        self.assertEqual(vus_cam, {CAM})
        self.assertEqual(vus_bea, {BEA, CAM})


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : FauxVault, Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
