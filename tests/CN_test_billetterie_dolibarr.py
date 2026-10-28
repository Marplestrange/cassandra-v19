# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 10
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #0016c6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 10 : le pont facultatif vers Dolibarr (file de rattrapage, idempotence, factures, règlements, avoirs, versements, pannes, prérequis, vrai transport HTTP).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=0016c6 ▼▼▼
"""Bancs de la billetterie, lot 10 : le pont facultatif vers Dolibarr (file de rattrapage, idempotence, factures, règlements, avoirs, versements, pannes, prérequis, vrai transport HTTP)."""
import json
import re
import sys
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_ventes import Ventes      # noqa: E402


class FauxDolibarr:
    """Un Dolibarr minimal en mémoire : assez pour vérifier ce que la billetterie envoie et comment elle se comporte quand il répond, se tait ou refuse."""

    def __init__(self, pont_erreur):
        self.pe = pont_erreur
        self.appels, self.tiers, self.factures, self.fournisseurs, self.panne, self.refus = [], {}, {}, {}, False, None
        self.compteur = 0

    def id(self):
        self.compteur += 1
        return self.compteur

    def __call__(self, methode, url, entetes, corps, delai):
        if self.panne:
            raise self.pe("Dolibarr est injoignable (ConnectionRefusedError)", injoignable=True)
        u = urllib.parse.urlsplit(url)
        chemin, q = u.path.split("/api/index.php", 1)[1], dict(urllib.parse.parse_qsl(u.query))
        d = json.loads(corps) if corps else None
        self.appels.append((methode, chemin, q, d, entetes))
        if self.refus and chemin.startswith(self.refus):
            return 500, {"error": {"code": 500, "message": "Erreur simulée"}}
        flt = re.match(r"\(t\.(\w+):=:'(.*)'\)", q.get("sqlfilters", ""))

        def cherche(table):
            r = [dict(x, id=i) for i, x in table.items() if flt and str(x.get(flt.group(1))) == flt.group(2)]
            return (200, r) if r else (404, {"error": {"code": 404, "message": "Not Found"}})
        if chemin == "/status":
            return 200, {"success": {"code": 200, "dolibarr_version": "23.0.2"}}
        if chemin == "/setup/company":
            return 200, {"name": "Maison Bohème", "country_code": "FR", "idprof1": "123 456 789", "tva_intra": ""}
        if chemin == "/bankaccounts":
            return 200, [{"id": 1, "ref": "BQ", "label": "Compte courant"}, {"id": 2, "ref": "CAISSE", "label": "Caisse"}]
        if chemin == "/setup/dictionary/payment_types":
            return 200, [{"id": 6, "code": "CB", "label": "Carte bancaire"}, {"id": 4, "code": "LIQ", "label": "Espèces"}, {"id": 2, "code": "VIR", "label": "Virement"}]
        if chemin == "/setup/dictionary/vat":
            return 200, [{"taux": "0", "note": "Non applicable"}]
        if chemin == "/thirdparties" and methode == "GET":
            return cherche(self.tiers)
        if chemin == "/thirdparties" and methode == "POST":
            i = self.id()
            self.tiers[i] = d
            return 200, i
        for base, table in (("/invoices", self.factures), ("/supplierinvoices", self.fournisseurs)):
            if chemin == base and methode == "GET":
                return cherche(table)
            if chemin == base and methode == "POST":
                i = self.id()
                table[i] = dict(d, statut=0, paiements=[], ref="")
                return 200, i
            m = re.match(base + r"/(\d+)(/validate|/payments)?$", chemin)
            if m:
                f = table[int(m.group(1))]
                if m.group(2) == "/validate":
                    f["statut"], f["ref"] = 1, ("AV" if f.get("type") == 2 else ("SI" if base != "/invoices" else "FA")) + "2610-%04d" % int(m.group(1))
                    return 200, dict(f, id=int(m.group(1)))
                if m.group(2) == "/payments" and methode == "POST":
                    f["paiements"].append(d)
                    return 200, self.id()
                if m.group(2) == "/payments":
                    return 200, f["paiements"] or (404, {})[1]
                return 200, dict(f, id=int(m.group(1)))
        return 404, {"error": {"message": "route inconnue " + chemin}}


class Pont(Ventes):
    def setUp(self):
        super().setUp()
        self.mod_dol = self.mod.CN_dolibarr
        self.dol = FauxDolibarr(self.mod_dol.PontErreur)
        self.mod_dol.HTTP["dolibarr"] = self.dol
        self.addCleanup(self.mod_dol.HTTP.clear)

    def relier(self, **k):
        d = dict(dolibarr_actif=True, dolibarr_url="http://dolibarr.test/api/index.php", dolibarr_cle="cle-secrete", dolibarr_banque_carte=1, dolibarr_banque_especes=2, dolibarr_banque_virement=1)
        d.update(k)
        for cle, val in d.items():
            self.n.reglages.poser("billetterie." + cle, val, "")

    def traiter(self, maximum=10):
        return self.mod_dol.traiter(self.ctx, self.ctx.stockage, maximum)

    def file(self, etat=""):
        return [x for x in self.ok("dolibarr_file")["file"] if not etat or x["etat"] == etat]

    def posts(self, chemin):
        return [a for a in self.dol.appels if a[0] == "POST" and a[1] == chemin]


class File(Pont):
    def test_pont_coupe_aucune_ecriture_n_est_empilee(self):
        self.vendre(1)
        self.assertEqual(self.file(), [])

    def test_une_vente_empile_sans_jamais_parler_a_dolibarr(self):
        self.relier()
        self.vendre(2)
        self.assertEqual([(x["objet"], x["etat"]) for x in self.file()], [("facture", "a_faire")])
        self.assertEqual(self.dol.appels, [])

    def test_le_domaine_factures_coupe_l_empilement(self):
        self.relier(dolibarr_factures=False)
        self.vendre(1)
        self.assertEqual(self.file(), [])

    def test_la_meme_ecriture_n_est_empilee_qu_une_fois(self):
        self.relier()
        cid = self.ok("commande", ref=self.vendre(1)["ref"])["commande"]["id"]
        with self.ctx.stockage.transaction() as tx:
            self.assertFalse(self.mod.CN_file_dolibarr.empiler(self.ctx, tx, "facture", cid))
        self.assertEqual(len(self.file()), 1)


class Facture(Pont):
    def test_la_facture_est_creee_validee_et_reglee_sur_le_bon_compte(self):
        self.relier()
        c = self.vendre(2)
        r = self.traiter()
        self.assertEqual((r["faits"], r["echecs"]), (1, 0))
        f = list(self.dol.factures.values())[0]
        self.assertEqual((f["type"], f["ref_ext"], f["statut"], f["ref"]), (0, c["ref"], 1, "FA2610-0002"))
        self.assertEqual([(l["qty"], l["subprice"], l["tva_tx"]) for l in f["lines"]], [(2, 15.0, 0.0)])
        p = f["paiements"][0]
        self.assertEqual((p["paymentid"], p["accountid"], p["closepaidinvoices"]), (4, 2, "yes"))            # espèces : mode LIQ, compte de caisse
        cmd = self.ok("commande", ref=c["ref"])["commande"]
        self.assertEqual(cmd["dolibarr_facture_ref"], "FA2610-0002")
        self.assertEqual(self.file()[0]["etat"], "fait")

    def test_le_client_a_son_tiers_une_seule_fois(self):
        self.relier()
        self.vendre(1)
        self.vendre(1)
        self.traiter()
        self.assertEqual(len(self.posts("/thirdparties")), 1)
        t = list(self.dol.tiers.values())[0]
        self.assertEqual((t["email"], t["client"], t["code_client"]), ("sophie@exemple.org", 1, "auto"))
        self.assertEqual(len(self.dol.factures), 2)

    def test_une_ecriture_rejouee_ne_double_rien(self):
        self.relier()
        c = self.vendre(1)
        self.traiter()
        self.ctx.stockage.ecrire("UPDATE dolibarr_file SET etat = 'a_faire', essais = 0")
        self.ctx.stockage.ecrire("UPDATE commandes SET dolibarr_facture_id = NULL, dolibarr_facture_ref = ''")           # même la mémoire locale perdue : Dolibarr est interrogé par la référence
        self.traiter()
        self.assertEqual((len(self.dol.factures), len(self.posts("/invoices"))), (1, 1))
        self.assertEqual(self.ok("commande", ref=c["ref"])["commande"]["dolibarr_facture_ref"], "FA2610-0002")

    def test_remise_et_frais_sont_des_lignes_le_don_n_en_est_pas_une(self):
        self.relier()
        self.ok("promo_save", code="HIVER10", type="pct", valeur=10)
        c = self.acheter([{"type_billet_id": self.plein, "quantite": 2}], encaisser=True, moyen="especes", code_promo="HIVER10", don=500)
        self.traiter()
        f = list(self.dol.factures.values())[0]
        total = sum(l["qty"] * l["subprice"] for l in f["lines"])
        cmd = self.ok("commande", ref=c["ref"])["commande"]
        self.assertEqual((round(total * 100), cmd["don"]), (cmd["total"] - cmd["don"], 500))
        self.assertTrue([l for l in f["lines"] if l["subprice"] < 0 and "Remise" in l["desc"]])

    def test_une_commande_gratuite_ne_se_facture_pas(self):
        self.relier()
        self.acheter([{"type_billet_id": self.plein, "quantite": 1}], encaisser=True, moyen="offert")
        r = self.traiter()
        self.assertEqual((r["ignores"], len(self.dol.factures)), (1, 0))

    def test_remboursee_avant_facturation_rien_n_est_ecrit(self):
        self.relier()
        c = self.vendre(1)
        self.ok("commande_rembourser", ref=c["ref"], motif="x")
        r = self.traiter()
        self.assertEqual((r["ignores"], len(self.dol.factures)), (2, 0))

    def test_sans_fiche_client_la_vente_va_aux_clients_divers(self):
        self.relier()
        self.acheter([{"type_billet_id": self.plein, "quantite": 1}], encaisser=True, moyen="especes", mail="", nom="")
        self.traiter()
        self.assertEqual(list(self.dol.tiers.values())[0]["ref_ext"], "BILLETTERIE-DIVERS")


class Pannes(Pont):
    def test_dolibarr_injoignable_la_vente_reste_payee_et_l_ecriture_attend(self):
        self.relier()
        c = self.vendre(1)
        self.dol.panne = True
        r = self.traiter()
        self.assertEqual((r["reportes"], "injoignable" in r["raison"]), (1, True))
        x = self.file()[0]
        self.assertEqual((x["etat"], x["essais"]), ("a_faire", 1))
        self.assertEqual(self.ok("commande", ref=c["ref"])["commande"]["etat"], "payee")
        self.assertEqual(self.traiter()["reportes"], 0)                       # pas encore dû
        self.avance(301)
        self.dol.panne = False
        self.assertEqual(self.traiter()["faits"], 1)

    def test_apres_six_echecs_l_ecriture_passe_en_echec_et_se_relance(self):
        self.relier()
        self.vendre(1)
        self.dol.refus = "/invoices"
        for i in range(6):
            self.traiter()
            self.avance(300 * 2 ** i + 1)
        x = self.file()[0]
        self.assertEqual((x["etat"], "HTTP 500" in x["erreur"]), ("echec", True))
        r = self.ok("dolibarr_relancer", id=x["id"])
        self.assertEqual(self.file()[0]["etat"], "a_faire")
        self.assertIn("seule une écriture en échec", self.echec("dolibarr_relancer", id=x["id"]))
        self.assertIn("introuvable", self.echec("dolibarr_relancer", id=x["id"] + 99))
        self.defaire("dolibarr_relancer", r)
        self.assertEqual(self.file()[0]["etat"], "echec")

    def test_sans_compte_bancaire_choisi_on_dit_lequel_choisir(self):
        self.relier(dolibarr_banque_especes=0)
        self.vendre(1)
        self.traiter()
        self.assertIn("compte bancaire", self.file()[0]["erreur"])
        self.assertIn("espèces", self.file()[0]["erreur"])

    def test_la_cle_refusee_est_dite(self):
        self.relier()
        self.vendre(1)
        self.dol.refus = None
        original = self.mod_dol.HTTP["dolibarr"]
        self.mod_dol.HTTP["dolibarr"] = lambda *a: (401, {"error": "Unauthorized"})
        self.traiter()
        self.mod_dol.HTTP["dolibarr"] = original
        self.assertIn("refuse l'accès", self.file()[0]["erreur"])

    def test_une_adresse_piegee_ne_part_jamais_dans_une_recherche(self):
        self.relier()
        self.ctx.stockage.ecrire("INSERT INTO clients(ref, nom, mail) VALUES ('CLI-999999', 'X', ?)", ("x')) OR 1=1 --@exemple.org",))
        c = self.vendre(1)
        self.ctx.stockage.ecrire("UPDATE commandes SET client_id = (SELECT id FROM clients WHERE ref = 'CLI-999999') WHERE ref = ?", (c["ref"],))
        self.traiter()
        self.assertFalse([a for a in self.dol.appels if "OR 1=1" in json.dumps(a[2])])
        self.assertIn("refusée", self.file()[0]["erreur"])


class Avoir(Pont):
    def test_un_remboursement_ecrit_un_avoir_lie_a_la_facture(self):
        self.relier()
        c = self.vendre(2)
        self.traiter()
        self.ok("commande_rembourser", ref=c["ref"], motif="x")
        self.assertEqual([x["objet"] for x in self.file("a_faire")], ["avoir"])
        self.traiter()
        av = [f for f in self.dol.factures.values() if f.get("type") == 2][0]
        fid = [i for i, f in self.dol.factures.items() if f.get("type") == 0][0]
        self.assertEqual((av["fk_facture_source"], av["ref"], av["ref_ext"]), (fid, "AV2610-0004", "AVOIR-" + c["ref"]))
        self.assertEqual([l["subprice"] for l in av["lines"]], [-15.0])
        self.assertEqual(self.ok("commande", ref=c["ref"])["commande"]["dolibarr_avoir_ref"], "AV2610-0004")

    def test_l_avoir_n_est_pas_double_si_rejoue(self):
        self.relier()
        c = self.vendre(1)
        self.traiter()
        self.ok("commande_rembourser", ref=c["ref"], motif="x")
        self.traiter()
        self.ctx.stockage.ecrire("UPDATE dolibarr_file SET etat = 'a_faire' WHERE objet = 'avoir'")
        self.traiter()
        self.assertEqual(len([f for f in self.dol.factures.values() if f.get("type") == 2]), 1)

    def test_le_domaine_avoirs_coupe(self):
        self.relier(dolibarr_avoirs=False)
        c = self.vendre(1)
        self.traiter()
        self.ok("commande_rembourser", ref=c["ref"], motif="x")
        self.assertEqual(self.file("a_faire"), [])


class Versement(Pont):
    def test_un_retrait_verse_ecrit_la_facture_fournisseur_et_son_reglement(self):
        self.relier(dolibarr_commissions=True)
        fc = self.formule(com=300, palier_n=12, palier_com=500, fixe=1000)
        rev = self.ok("revendeur_save", nom="Léa Martin", mail="lea@exemple.org", siret="12345678900012")
        code = self.ok("revendeur", id=rev["id"])["revendeur"]["code"]
        self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=rev["id"], formule_id=fc["id"], quota=8)
        self.vendre(4, revendeur_code=code)
        r = self.ok("retrait_demander", porteur="revendeur", porteur_id=rev["id"], montant=2000, au="2099-01-01")
        self.ok("retrait_valider", id=r["id"])
        self.ok("retrait_payer", id=r["id"], reference_virement="VIR-123")
        self.traiter()
        t = [x for x in self.dol.tiers.values() if x.get("fournisseur") == 1][0]
        self.assertEqual((t["name"], t["code_fournisseur"], t["idprof1"], t["client"]), ("Léa Martin", "auto", "12345678900012", 0))
        fa = list(self.dol.fournisseurs.values())[0]
        self.assertEqual((fa["ref_supplier"], fa["lines"][0]["subprice"], fa["statut"]), (r["ref"], 20.0, 1))
        p = fa["paiements"][0]
        self.assertEqual((p["paymentid"], p["accountid"], p["num_payment"]), (2, 1, "VIR-123"))

    def test_le_domaine_commissions_est_coupe_par_defaut(self):
        self.relier()
        self.assertFalse(self.mod.CN_file_dolibarr.relie(self.ctx) and self.ctx.reglage("dolibarr_commissions"))


class Prerequis(Pont):
    def test_tester_sans_reglage_dit_quoi_regler(self):
        self.assertIn("adresse de l'API", self.echec("dolibarr_tester"))

    def test_tester_liste_ce_qui_manque_et_ce_qui_va(self):
        self.relier(dolibarr_banque_virement=99)
        r = self.ok("dolibarr_tester")
        self.assertEqual((r["version"], r["societe"]["name"]), ("23.0.2", "Maison Bohème"))
        ko = [p for p in r["points"] if not p["ok"]]
        self.assertEqual(len(ko), 1)
        self.assertIn("virement", ko[0]["libelle"])
        self.assertIn("choisissez", ko[0]["detail"])
        self.assertFalse(r["ok"])
        self.relier(dolibarr_banque_virement=1)
        self.assertTrue(self.ok("dolibarr_tester")["ok"])

    def test_l_etat_resume_la_file(self):
        self.relier()
        self.vendre(1)
        e = self.ok("dolibarr_etat")
        self.assertEqual((e["relie"], e["a_faire"], e["domaines"]["factures"]), (True, 1, True))
        self.assertEqual(self.ok("dolibarr_rattraper")["faits"], 1)
        self.assertEqual(self.ok("dolibarr_etat")["faits"], 1)

    def test_pont_coupe_le_rattrapage_le_dit(self):
        self.assertIn("pas relié", self.ok("dolibarr_rattraper")["raison"])


class Transport(unittest.TestCase):
    """Le vrai transport HTTP contre un petit serveur : en-tête de clé, corps JSON, 404 d'une recherche vide, accès refusé."""

    def test_le_vrai_client_parle_correctement(self):
        vus = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def repondre(self, code, corps):
                b = json.dumps(corps).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                vus.append(("GET", self.path, self.headers.get("DOLAPIKEY"), self.headers.get("Host")))
                if "vide" in self.path:
                    return self.repondre(404, {"error": {"message": "Not Found"}})
                if self.headers.get("DOLAPIKEY") != "bonne-cle":
                    return self.repondre(401, {"error": "Unauthorized"})
                self.repondre(200, {"success": {"dolibarr_version": "23"}})

            def do_POST(self):
                corps = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                vus.append(("POST", self.path, corps, self.headers.get("Content-Type")))
                self.repondre(200, 42)
        srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        import importlib.util as u
        import importlib
        racine = RACINE / "modules" / "billetterie"
        sp = u.spec_from_file_location("cassandra_module_billetterie_dol", racine / "CN_module.py", submodule_search_locations=[str(racine)])
        mod = u.module_from_spec(sp)
        sys.modules["cassandra_module_billetterie_dol"] = mod
        self.addCleanup(sys.modules.pop, "cassandra_module_billetterie_dol", None)
        sp.loader.exec_module(mod)
        d = importlib.import_module("cassandra_module_billetterie_dol.CN_dolibarr")

        class Ctx:
            def __init__(s, cle):
                s.v = {"dolibarr_url": "http://127.0.0.1:%d/api/index.php" % srv.server_address[1], "dolibarr_cle": cle, "dolibarr_hote": "dolibarr.interne"}

            def reglage(s, n):
                return s.v.get(n)
        self.assertEqual(d.appel(Ctx("bonne-cle"), "GET", "/status")["success"]["dolibarr_version"], "23")
        self.assertIsNone(d.appel(Ctx("bonne-cle"), "GET", "/thirdparties-vide"))
        self.assertEqual(d.appel(Ctx("bonne-cle"), "POST", "/thirdparties", {"name": "Zoë"}), 42)
        with self.assertRaises(d.PontErreur) as m:
            d.appel(Ctx("mauvaise"), "GET", "/status")
        self.assertIn("refuse l'accès", str(m.exception))
        self.assertEqual(vus[0][2:], ("bonne-cle", "dolibarr.interne"))
        self.assertEqual(vus[2][2:], ({"name": "Zoë"}, "application/json"))
        with self.assertRaises(d.PontErreur) as m:
            ctx_mort = Ctx("x")
            ctx_mort.v["dolibarr_url"] = "http://127.0.0.1:1/api/index.php"
            d.appel(ctx_mort, "GET", "/status")
        self.assertTrue(m.exception.injoignable)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : FauxDolibarr, Pont, File, Facture, Pannes, Avoir, Versement, Prerequis …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
