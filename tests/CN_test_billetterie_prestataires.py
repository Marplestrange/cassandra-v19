# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 8b
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #e02795
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 8b : PayPal et HelloAsso (page hébergée, vérification chez le prestataire au retour, montant exact, ordre de CETTE commande, idempotence).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e02795 ▼▼▼
"""Bancs de la billetterie, lot 8b : PayPal et HelloAsso (page hébergée, vérification chez le prestataire au retour, montant exact, ordre de CETTE commande, idempotence)."""
import base64
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_boutique import Boutique      # noqa: E402


class Prestataires(Boutique):
    def setUp(self):
        super().setUp()
        self.p = self.mod.CN_prestataires
        self.appels = {"paypal": [], "helloasso": []}
        self.pp = {"capture": "ok", "ordres": {}}
        self.ha = {"intentions": {}, "payee": False, "montant": None, "autre": False}
        self.p.HTTP["paypal"] = self.faux_paypal
        self.p.HTTP["helloasso"] = self.faux_helloasso
        self.addCleanup(self.p.HTTP.clear)
        for cle, val in (("paypal_actif", True), ("paypal_client_id", "client-pp"), ("paypal_secret", "secret-pp"), ("helloasso_actif", True), ("helloasso_client_id", "client-ha"),
                         ("helloasso_secret", "secret-ha"), ("helloasso_organisation", "maison-boheme")):
            self.n.reglages.poser("billetterie." + cle, val, "")

    # ── doublures ────────────────────────────────────────────────────────────
    def faux_paypal(self, methode, url, entetes, corps, delai):
        self.appels["paypal"].append((methode, url, entetes, corps))
        if url.endswith("/v1/oauth2/token"):
            return 200, {"access_token": "jeton-pp"}
        if url.endswith("/v2/checkout/orders") and methode == "POST":
            d = json.loads(corps)
            oid = "ORD-%d" % (len(self.pp["ordres"]) + 1)
            self.pp["ordres"][oid] = d
            return 201, {"id": oid, "status": "PAYER_ACTION_REQUIRED", "links": [{"rel": "self", "href": "x"}, {"rel": "payer-action", "href": "https://paypal.test/pay/" + oid}]}
        if url.endswith("/capture"):
            oid = url.split("/")[-2]
            u = self.pp["ordres"][oid]["purchase_units"][0]
            if self.pp["capture"] == "refus":
                return 422, {"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "ORDER_NOT_APPROVED", "description": "L'acheteur n'a pas approuvé"}]}
            valeur = u["amount"]["value"] if self.pp["capture"] != "montant" else "1.00"
            ref = u["reference_id"] if self.pp["capture"] != "autre" else "CMD-999999"
            return 201, {"id": oid, "status": "COMPLETED", "purchase_units": [{"reference_id": ref, "payments": {"captures": [{"id": "CAP-" + oid, "status": "COMPLETED", "amount": {"currency_code": "EUR", "value": valeur}}]}}]}
        return 404, {}

    def faux_helloasso(self, methode, url, entetes, corps, delai):
        self.appels["helloasso"].append((methode, url, entetes, corps))
        if url.endswith("/oauth2/token"):
            return 200, {"access_token": "jeton-ha"}
        if url.endswith("/checkout-intents") and methode == "POST":
            d = json.loads(corps)
            iid = 1000 + len(self.ha["intentions"])
            self.ha["intentions"][str(iid)] = d
            return 200, {"id": iid, "redirectUrl": "https://helloasso.test/pay/%d" % iid}
        if "/checkout-intents/" in url and methode == "GET":
            iid = url.rsplit("/", 1)[1]
            d = self.ha["intentions"][iid]
            rep = {"id": int(iid), "metadata": {"commande": d["metadata"]["commande"] if not self.ha["autre"] else "CMD-999999"}}
            if self.ha["payee"]:
                rep["order"] = {"id": 7000 + int(iid), "amount": {"total": d["totalAmount"] if self.ha["montant"] is None else self.ha["montant"]}}
            return 200, rep
        return 404, {}

    def commande_pp(self, **k):
        return self.commander(1, moyen="paypal", **k)

    def verifier(self, c, fournisseur, ordre=""):
        return self.pub_ok("public_paiement_verifier", commande=c["commande"], suivi=c["suivi"], fournisseur=fournisseur, ordre=ordre)

    def etat(self, c):
        return self.ok("commande", ref=c["commande"])["commande"]["etat"]


class PayPal(Prestataires):
    def test_le_moyen_n_est_propose_que_regle_et_actif(self):
        ids = [m["id"] for m in self.pub_ok("public_evenement", ref=self.eref)["paiements"]]
        self.assertIn("paypal", ids)
        self.n.reglages.poser("billetterie.paypal_secret", "", "")
        self.assertNotIn("paypal", [m["id"] for m in self.pub_ok("public_evenement", ref=self.eref)["paiements"]])

    def test_l_ordre_a_le_montant_exact_la_reference_et_les_adresses_de_retour(self):
        c = self.commande_pp()
        self.assertEqual(c["paiement"], {"type": "paypal", "url": "https://paypal.test/pay/ORD-1"})
        d = self.pp["ordres"]["ORD-1"]
        u = d["purchase_units"][0]
        self.assertEqual((u["amount"], u["reference_id"]), ({"currency_code": "EUR", "value": "15.00"}, c["commande"]))
        ctxp = d["payment_source"]["paypal"]["experience_context"]
        self.assertIn("/boutique.html?c=%s&s=%s&p=paypal" % (c["commande"], c["suivi"]), ctxp["return_url"])
        auth = [a for a in self.appels["paypal"] if a[1].endswith("/v1/oauth2/token")][0][2]["Authorization"]
        self.assertEqual(base64.b64decode(auth.split()[1]).decode(), "client-pp:secret-pp")
        self.assertTrue(self.appels["paypal"][1][1].startswith("https://api-m.paypal.com/"))

    def test_le_bac_a_sable_change_d_adresse(self):
        self.n.reglages.poser("billetterie.paypal_sandbox", True, "")
        self.commande_pp()
        self.assertTrue(self.appels["paypal"][0][1].startswith("https://api-m.sandbox.paypal.com/"))

    def test_au_retour_la_capture_reussie_livre_les_billets_une_seule_fois(self):
        c = self.commande_pp()
        r = self.verifier(c, "paypal", "ORD-1")
        self.assertEqual(r["etat"], "payee")
        self.assertEqual(self.etat(c), "payee")
        self.assertEqual(len(self.ok("billets", evenement_id=self.e["id"])["billets"]), 1)
        self.assertTrue(self.verifier(c, "paypal", "ORD-1")["deja"])
        self.assertEqual(len(self.ok("billets", evenement_id=self.e["id"])["billets"]), 1)

    def test_l_ordre_d_une_autre_commande_est_refuse(self):
        c1, c2 = self.commande_pp(), self.commande_pp(ip="203.0.113.99", mail="b@exemple.org")
        self.assertIn("pas celui", self.pub_echec("public_paiement_verifier", commande=c1["commande"], suivi=c1["suivi"], fournisseur="paypal", ordre="ORD-2"))
        self.assertEqual((self.etat(c1), self.etat(c2)), ("retenue", "retenue"))

    def test_un_montant_different_ne_livre_rien(self):
        c = self.commande_pp()
        self.pp["capture"] = "montant"
        r = self.verifier(c, "paypal", "ORD-1")
        self.assertEqual(r["etat"], "ecart")
        self.assertIn("montant", r["detail"])
        self.assertEqual(self.etat(c), "retenue")

    def test_une_reference_etrangere_ne_livre_rien(self):
        c = self.commande_pp()
        self.pp["capture"] = "autre"
        self.assertEqual(self.verifier(c, "paypal", "ORD-1")["etat"], "ecart")
        self.assertEqual(self.etat(c), "retenue")

    def test_un_paiement_non_approuve_reste_en_attente(self):
        c = self.commande_pp()
        self.pp["capture"] = "refus"
        r = self.verifier(c, "paypal", "ORD-1")
        self.assertEqual(r["etat"], "attente")
        self.assertEqual(self.etat(c), "retenue")

    def test_il_faut_le_bon_jeton_de_suivi_et_le_bon_prestataire(self):
        c = self.commande_pp()
        self.assertIn("introuvable", self.pub_echec("public_paiement_verifier", commande=c["commande"], suivi="faux", fournisseur="paypal", ordre="ORD-1"))
        self.assertIn("pas été payée par ce prestataire", self.pub_echec("public_paiement_verifier", commande=c["commande"], suivi=c["suivi"], fournisseur="helloasso", ordre="x"))
        self.assertIn("inconnu", self.pub_echec("public_paiement_verifier", commande=c["commande"], suivi=c["suivi"], fournisseur="bitcoin"))

    def test_defaire_la_livraison_rembourse(self):
        c = self.commande_pp()
        r = self.verifier(c, "paypal", "ORD-1")
        self.defaire("public_paiement_verifier", r)
        self.assertEqual(self.etat(c), "remboursee")

    def test_paypal_qui_refuse_la_creation_annule_la_commande_et_rend_les_places(self):
        self.p.HTTP["paypal"] = lambda m, u, e, c, d: (401, {"error": "invalid_client", "error_description": "Client Authentication failed"}) if u.endswith("token") else (500, {})
        self.assertIn("n'a pas pu être préparé", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="X", mail="x@exemple.org", moyen="paypal", ip="203.0.113.5"))
        self.assertEqual(self.stock()["retenus"], 0)


class HelloAsso(Prestataires):
    def commande_ha(self, **k):
        return self.commander(2, moyen="helloasso", **k)

    def test_l_intention_porte_le_montant_en_centimes_la_commande_et_l_acheteur(self):
        c = self.commande_ha()
        self.assertEqual(c["paiement"], {"type": "helloasso", "url": "https://helloasso.test/pay/1000"})
        d = self.ha["intentions"]["1000"]
        self.assertEqual((d["totalAmount"], d["initialAmount"], d["metadata"], d["containsDonation"]), (3000, 3000, {"commande": c["commande"]}, False))
        self.assertEqual((d["payer"]["firstName"], d["payer"]["lastName"], d["payer"]["email"]), ("Sophie", "Marchand", "sophie@exemple.org"))
        self.assertIn("/boutique.html?c=%s&s=%s&p=helloasso" % (c["commande"], c["suivi"]), d["returnUrl"])
        self.assertTrue([a for a in self.appels["helloasso"] if "/organizations/maison-boheme/checkout-intents" in a[1]])

    def test_tant_que_l_intention_n_a_pas_de_commande_reglee_rien_n_est_livre(self):
        c = self.commande_ha()
        self.assertEqual(self.verifier(c, "helloasso")["etat"], "attente")
        self.assertEqual(self.etat(c), "retenue")

    def test_payee_au_bon_montant_les_billets_sont_livres(self):
        c = self.commande_ha()
        self.ha["payee"] = True
        self.assertEqual(self.verifier(c, "helloasso")["etat"], "payee")
        self.assertEqual(self.etat(c), "payee")
        self.assertEqual(len(self.ok("billets", evenement_id=self.e["id"])["billets"]), 2)
        self.assertTrue(self.verifier(c, "helloasso")["deja"])

    def test_un_montant_different_ne_livre_rien(self):
        c = self.commande_ha()
        self.ha.update(payee=True, montant=100)
        r = self.verifier(c, "helloasso")
        self.assertEqual(r["etat"], "ecart")
        self.assertEqual(self.etat(c), "retenue")

    def test_l_intention_d_une_autre_commande_ne_livre_rien(self):
        c = self.commande_ha()
        self.ha.update(payee=True, autre=True)
        self.assertEqual(self.verifier(c, "helloasso")["etat"], "ecart")
        self.assertEqual(self.etat(c), "retenue")

    def test_helloasso_ouvre_les_adresses_du_bac_a_sable_quand_on_le_demande(self):
        self.n.reglages.poser("billetterie.helloasso_sandbox", True, "")
        self.commande_ha()
        self.assertTrue(self.appels["helloasso"][0][1].startswith("https://api.helloasso-sandbox.com/"))


class RetourApresExpiration(Prestataires):
    def test_paye_chez_paypal_apres_l_expiration_et_places_reparties_est_signale_a_rembourser(self):
        c = self.commande_pp()
        ref = self.ok("commande", ref=c["commande"])["commande"]
        self.avance(11 * 60)
        with self.ctx.stockage.transaction() as tx:
            self.mod.CN_ventes.expirer(tx)
        self.vendre(10)                                                 # toutes les places sont reparties pendant ce temps
        r = self.verifier(c, "paypal", "ORD-1")
        self.assertEqual(r["etat"], "a_rembourser")
        self.assertEqual(self.etat(c), "expiree")
        self.assertIn("à rembourser", self.ok("commande", ref=c["commande"])["commande"]["note"])
        self.assertIsNotNone(ref)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Prestataires, PayPal, HelloAsso, RetourApresExpiration
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
