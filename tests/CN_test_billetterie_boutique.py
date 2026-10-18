# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 4c
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #0d0646
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 4c : la boutique publique (calendrier, page d'un événement, panier, commande, paiement Stripe par webhook signé, virement, suivi par jeton, limites contre l'abus).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=0d0646 ▼▼▼
"""Bancs de la billetterie, lot 4c : la boutique publique (calendrier, page d'un événement, panier, commande, paiement Stripe par webhook signé, virement, suivi par jeton, limites contre l'abus)."""
import http.client
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_ventes import Ventes      # noqa: E402

SECRET = "whsec_essai"


class Boutique(Ventes):
    def setUp(self):
        super().setUp()
        self.t[0] = 1_790_000_000.0                         # septembre 2026 : l'événement (12 décembre) est à venir
        for cle, val in (("stripe_actif", True), ("stripe_cle_secrete", "sk_test_essai"), ("stripe_webhook_secret", SECRET), ("virement_actif", True),
                         ("iban", "FR76 3000 6000 0112 3456 7890 189"), ("domaine", "billets.exemple.fr")):
            self.n.reglages.poser("billetterie." + cle, val, "")
        self.appels = []
        self.mod.CN_boutique.HTTP["stripe"] = self.faux_stripe
        self.addCleanup(self.mod.CN_boutique.HTTP.clear)
        self.eref = self.ok("evenement", id=self.e["id"])["evenement"]["ref"]
        types = self.ok("evenement_fiche", id=self.e["id"])["types"]
        self.tp = [t["ref"] for t in types if t["nom"] == "Plein tarif"][0]
        self.tr = [t["ref"] for t in types if t["nom"] == "Tarif réduit"][0]

    def faux_stripe(self, url, donnees, cle):
        self.appels.append((url, donnees, cle))
        return {"id": "cs_test_%d" % len(self.appels), "url": "https://checkout.stripe.test/pay/%d" % len(self.appels)}

    def pub(self, capacite, **args):
        r = self.n.executeur.executer("billetterie." + capacite, "anonyme", args, compte="")
        return r

    def pub_ok(self, capacite, **args):
        r = self.pub(capacite, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def pub_echec(self, capacite, **args):
        r = self.pub(capacite, **args)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r.get("erreur") or r.get("raison") or ""

    def commander(self, n=1, moyen="stripe", **k):
        d = dict(evenement=self.eref, lignes=[{"type": self.tp, "quantite": n}], nom="Sophie Marchand", mail="sophie@exemple.org", moyen=moyen, ip="203.0.113.7")
        d.update(k)
        return self.pub_ok("public_commander", **d)

    def evenement_stripe(self, cmd, total=None, ident="evt_1", paye="paid", ref=None, type_="checkout.session.completed"):
        return json.dumps({"id": ident, "type": type_, "data": {"object": {"id": "cs_1", "client_reference_id": ref or cmd["commande"], "payment_status": paye,
                                                                         "amount_total": cmd["total"] if total is None else total, "payment_intent": "pi_" + ident}}}, separators=(",", ":")).encode()

    def webhook(self, corps, secret=SECRET, t=None):
        S = self.mod.CN_stripe
        entete = S.signer(corps, secret, int(self.t[0]) if t is None else t)
        return self.pub("public_webhook_stripe", corps_octets=corps, en_tetes={"stripe-signature": entete})


class Vitrine(Boutique):
    def test_le_calendrier_ne_montre_que_les_evenements_publies(self):
        self.evenement(nom="Brouillon", salle_id=self.salle_id)
        self.ok("evenement_save", id=self.e["id"], quota=100)                  # assez de places pour ne pas être « dernières places »
        cal = self.pub_ok("public_calendrier")
        self.assertEqual([x["nom"] for x in cal["evenements"]], ["Soirée d'hiver"])
        x = cal["evenements"][0]
        self.assertEqual((x["ref"], x["etat"], x["a_partir_de"], x["lieu"]), (self.eref, "ouvert", 1000, "Salle des fêtes"))

    def test_la_page_d_un_evenement_donne_le_programme_avec_ses_heures(self):
        fa = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        a1 = self.ok("artiste_save", scene="Les Marées", genre="Folk", formule_id=fa["id"])
        a2 = self.ok("artiste_save", scene="Nova", genre="Soul", formule_id=fa["id"])
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=a1["id"], duree=45)
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=a2["id"], duree=30)
        self.ok("evenement_save", id=self.e["id"], debut="20:00", pause=10)
        p = self.pub_ok("public_evenement", ref=self.eref)
        self.assertEqual([(x["scene"], x["heure"], x["duree"]) for x in p["programme"]], [("Les Marées", "20:00", 45), ("Nova", "20:55", 30)])
        self.assertEqual(p["salle"]["nom"], "Salle des fêtes")
        self.assertEqual([b["nom"] for b in p["billets"]], ["Plein tarif", "Tarif réduit"])

    def test_un_billet_masque_n_apparait_pas_et_un_billet_epuise_le_dit(self):
        self.ok("type_billet_save", id=self.reduit, visible=0)
        self.assertEqual([b["nom"] for b in self.pub_ok("public_evenement", ref=self.eref)["billets"]], ["Plein tarif"])
        self.ok("type_billet_save", id=self.reduit, visible=1)
        self.acheter([{"type_billet_id": self.reduit, "quantite": 4}], encaisser=True, moyen="especes")
        b = {x["nom"]: x for x in self.pub_ok("public_evenement", ref=self.eref)["billets"]}
        self.assertEqual((b["Tarif réduit"]["etat"], b["Plein tarif"]["etat"]), ("épuisé", "ok"))

    def test_le_visiteur_ne_voit_aucun_identifiant_interne_ni_donnee_d_acheteur(self):
        self.vendre(1)
        p = json.dumps(self.pub_ok("public_evenement", ref=self.eref)) + json.dumps(self.pub_ok("public_calendrier"))
        for interdit in ("Sophie", "sophie@", "salle_id", "evenement_id", "revendeur", "mail\": \"sophie"):
            self.assertNotIn(interdit, p)

    def test_un_evenement_non_publie_est_introuvable(self):
        b = self.evenement(nom="Brouillon", salle_id=self.salle_id)
        ref = self.ok("evenement", id=b["id"])["evenement"]["ref"]
        self.assertIn("introuvable", self.pub_echec("public_evenement", ref=ref))

    def test_les_dernieres_places_se_voient(self):
        self.vendre(8)
        self.assertEqual(self.pub_ok("public_calendrier")["evenements"][0]["etat"], "dernières places")
        self.vendre(2)
        self.assertEqual(self.pub_ok("public_calendrier")["evenements"][0]["etat"], "complet")

    def test_la_boutique_fermee_repond_qu_elle_est_fermee(self):
        self.n.reglages.poser("billetterie.boutique_en_ligne", False, "")
        self.assertIn("fermée", self.pub_echec("public_calendrier"))
        self.assertIn("fermée", self.pub_echec("public_evenement", ref=self.eref))

    def test_le_panier_chiffre_sans_rien_ecrire(self):
        self.ok("promo_save", code="hiver10", type="pct", valeur=10)
        d = self.pub_ok("public_panier", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 2}], code_promo="hiver10")
        self.assertEqual((d["sous_total"], d["remise"], d["total"]), (3000, 300, 2700))
        self.assertEqual(self.stock()["retenus"], 0)
        self.assertIn("n'existe pas", self.pub_echec("public_panier", evenement=self.eref, lignes=[{"type": "TYP-999999", "quantite": 1}]))


class Commande(Boutique):
    def test_commander_retient_les_places_et_rend_la_page_de_paiement(self):
        c = self.commander(2)
        self.assertEqual((c["total"], c["paiement"]["type"], c["places"]), (3000, "stripe", 2))
        self.assertTrue(c["paiement"]["url"].startswith("https://checkout.stripe.test/"))
        self.assertEqual(self.stock()["retenus"], 2)
        url, d, cle = self.appels[0]
        self.assertEqual((d["client_reference_id"], d["line_items[0][price_data][unit_amount]"], d["customer_email"], cle), (c["commande"], "3000", "sophie@exemple.org", "sk_test_essai"))

    def test_la_commande_n_a_pas_de_billet_tant_qu_elle_n_est_pas_payee(self):
        c = self.commander(1)
        self.assertEqual(self.ok("billets", evenement_id=self.e["id"])["billets"], [])
        s = self.pub_ok("public_suivre", commande=c["commande"], suivi=c["suivi"])
        self.assertEqual((s["etat"], s["billets"]), ("retenue", []))

    def test_un_moyen_non_propose_ou_inconnu_est_refuse(self):
        self.assertIn("pas proposé", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="X", mail="x@exemple.org", moyen="paypal"))
        self.n.reglages.poser("billetterie.stripe_actif", False, "")
        self.assertIn("pas proposé", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="X", mail="x@exemple.org", moyen="stripe"))

    def test_le_nom_et_le_courriel_sont_obligatoires(self):
        base = dict(evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], moyen="stripe")
        self.assertIn("nom", self.pub_echec("public_commander", nom="", mail="x@exemple.org", **base))
        self.assertIn("courriel", self.pub_echec("public_commander", nom="X", mail="", **base))

    def test_si_stripe_refuse_la_commande_est_annulee_et_les_places_reviennent(self):
        def casse(url, donnees, cle):
            raise RuntimeError("Stripe est injoignable")
        self.mod.CN_boutique.HTTP["stripe"] = casse
        self.assertIn("paiement", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 3}], nom="X", mail="x@exemple.org", moyen="stripe"))
        self.assertEqual(self.stock()["retenus"], 0)

    def test_le_virement_donne_l_iban_et_la_reference_et_retient_trois_jours(self):
        c = self.commander(1, moyen="virement")
        self.assertEqual((c["paiement"]["type"], c["paiement"]["reference"], c["paiement"]["montant"]), ("virement", c["commande"], 1500))
        self.assertIn("FR76", c["paiement"]["iban"])
        self.avance(2 * 24 * 3600)
        self.assertEqual(self.stock()["retenus"], 1)
        self.ok("commande_encaisser", ref=c["commande"], moyen="virement", reference_externe="VIR-77")
        s = self.pub_ok("public_suivre", commande=c["commande"], suivi=c["suivi"])
        self.assertEqual((s["etat"], len(s["billets"])), ("payee", 1))

    def test_une_attribution_a_un_revendeur_passe_par_la_boutique(self):
        fc = self.formule(com=300, palier_n=0, palier_com=0, fixe=0)
        rev = self.ok("revendeur_save", nom="Léa Martin")
        code = self.ok("revendeur", id=rev["id"])["revendeur"]["code"]
        self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=rev["id"], formule_id=fc["id"])
        c = self.commander(2, code_revendeur=code)
        self.assertIn("attribuée", c["attribution"])
        self.assertEqual(self.webhook(self.evenement_stripe(c))["resultat"]["issue"], "paye")
        self.assertEqual(self.ok("portefeuille", porteur="revendeur", porteur_id=rev["id"], au="2099-01-01")["du"], 600)


class Suivi(Boutique):
    def test_le_suivi_exige_le_jeton_et_ne_dit_pas_si_la_reference_existe(self):
        c = self.commander(1)
        a = self.pub_echec("public_suivre", commande=c["commande"], suivi="mauvais")
        b = self.pub_echec("public_suivre", commande=c["commande"].replace("1", "9"), suivi=c["suivi"])
        self.assertEqual(a, b)
        self.assertIn("introuvable", a)

    def test_les_billets_payes_se_lisent_avec_leur_qr_authentique(self):
        c = self.commander(2)
        self.assertEqual(self.webhook(self.evenement_stripe(c))["resultat"]["issue"], "paye")
        s = self.pub_ok("public_suivre", commande=c["commande"], suivi=c["suivi"])
        self.assertEqual((s["etat"], len(s["billets"])), ("payee", 2))
        k = self.mod.CN_billets.cle(self.ctx, self.ctx.stockage)
        lu = self.mod.CN_billets.lire(s["billets"][0]["qr"])
        self.assertTrue(self.mod.CN_billets.authentique(k, lu["numero"], 0, lu["signature"]))


class Webhook(Boutique):
    def test_un_paiement_confirme_livre_les_billets_et_prepare_le_courriel(self):
        c = self.commander(2)
        r = self.webhook(self.evenement_stripe(c))
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["issue"], "paye")
        self.assertEqual((self.stock()["vendus"], self.stock()["retenus"]), (2, 0))
        cmd = self.ok("commande", ref=c["commande"])["commande"]
        self.assertEqual((cmd["etat"], cmd["moyen"], cmd["reference_externe"]), ("payee", "stripe", "pi_evt_1"))
        mails = self.ctx.stockage.lire("SELECT a, objet, corps, etat FROM courriels")
        self.assertEqual((mails[0]["a"], mails[0]["etat"]), ("sophie@exemple.org", "a_envoyer"))
        self.assertIn("A-0001", mails[0]["corps"])
        self.assertIn(c["suivi"], mails[0]["corps"])

    def test_une_signature_fausse_ou_absente_ne_livre_rien(self):
        c = self.commander(1)
        corps = self.evenement_stripe(c)
        for entete in ("t=%d,v1=%s" % (int(self.t[0]), "0" * 64), "", "n'importe quoi"):
            r = self.pub("public_webhook_stripe", corps_octets=corps, en_tetes={"stripe-signature": entete})
            self.assertEqual(r["resultat"]["ok"], False, entete)
        self.assertEqual(self.webhook(corps, secret="whsec_autre")["resultat"]["ok"], False)
        self.assertEqual(self.stock()["vendus"], 0)

    def test_un_horodatage_trop_ancien_est_refuse(self):
        c = self.commander(1)
        r = self.webhook(self.evenement_stripe(c), t=int(self.t[0]) - 400)
        self.assertEqual(r["resultat"]["ok"], False)

    def test_le_corps_modifie_apres_la_signature_est_refuse(self):
        c = self.commander(1)
        corps = self.evenement_stripe(c)
        entete = self.mod.CN_stripe.signer(corps, SECRET, int(self.t[0]))
        r = self.pub("public_webhook_stripe", corps_octets=corps.replace(b'"amount_total":1500', b'"amount_total":1'), en_tetes={"stripe-signature": entete})
        self.assertEqual(r["resultat"]["ok"], False)

    def test_un_montant_different_ne_livre_rien(self):
        c = self.commander(2)
        r = self.webhook(self.evenement_stripe(c, total=100))
        self.assertEqual(r["resultat"]["issue"], "ecart")
        self.assertEqual(self.stock()["vendus"], 0)
        self.assertIn("montant différent", self.ok("commande", ref=c["commande"])["commande"]["note"])

    def test_le_meme_evenement_recu_deux_fois_n_agit_qu_une_fois(self):
        c = self.commander(1)
        corps = self.evenement_stripe(c)
        self.assertEqual(self.webhook(corps)["resultat"]["issue"], "paye")
        self.assertEqual(self.webhook(corps)["resultat"].get("deja"), True)
        self.assertEqual(self.stock()["vendus"], 1)
        self.assertEqual(len(self.ctx.stockage.lire("SELECT id FROM courriels")), 1)

    def test_un_autre_evenement_pour_la_meme_commande_ne_livre_pas_deux_fois(self):
        c = self.commander(1)
        self.webhook(self.evenement_stripe(c, ident="evt_1"))
        r = self.webhook(self.evenement_stripe(c, ident="evt_2"))
        self.assertEqual(r["resultat"]["issue"], "a_rembourser")
        self.assertEqual(self.stock()["vendus"], 1)

    def test_un_paiement_apres_expiration_sans_places_est_a_rembourser(self):
        c = self.commander(3)
        self.avance(11 * 60)
        self.vendre(9)
        r = self.webhook(self.evenement_stripe(c))
        self.assertEqual(r["resultat"]["issue"], "a_rembourser")
        cmd = self.ok("commande", ref=c["commande"])["commande"]
        self.assertIn("à rembourser chez Stripe", cmd["note"])
        self.assertEqual(self.stock()["vendus"], 9)

    def test_un_paiement_apres_expiration_avec_places_encore_libres_est_livre(self):
        c = self.commander(2)
        self.avance(11 * 60)
        self.assertEqual(self.webhook(self.evenement_stripe(c))["resultat"]["issue"], "paye")

    def test_une_commande_inconnue_ou_un_paiement_non_paye_est_ignore(self):
        c = self.commander(1)
        self.assertEqual(self.webhook(self.evenement_stripe(c, ref="CMD-999999", ident="evt_a"))["resultat"]["issue"], "inconnue")
        self.assertEqual(self.webhook(self.evenement_stripe(c, paye="unpaid", ident="evt_b"))["resultat"]["issue"], "attente")
        self.assertEqual(self.webhook(self.evenement_stripe(c, type_="charge.refunded", ident="evt_c"))["resultat"]["issue"], "ignore")
        self.assertEqual(self.stock()["vendus"], 0)

    def test_un_paiement_livre_se_defait_par_le_retour_arriere(self):
        c = self.commander(1)
        res = self.webhook(self.evenement_stripe(c))["resultat"]
        self.defaire("public_webhook_stripe", res)
        self.assertEqual(self.ok("commande", ref=c["commande"])["commande"]["etat"], "remboursee")


class Abus(Boutique):
    def test_une_adresse_ne_retient_pas_plus_de_trois_commandes_en_meme_temps(self):
        for i in range(3):
            self.commander(1, mail="a%d@exemple.org" % i)
        self.assertIn("réservations en cours", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="X", mail="z@exemple.org", moyen="stripe", ip="203.0.113.7"))
        self.commander(1, mail="autre@exemple.org", ip="198.51.100.9")                     # une autre origine n'est pas gênée

    def test_une_adresse_est_limitee_a_dix_commandes_par_heure(self):
        for i in range(10):
            c = self.commander(1, mail="b%d@exemple.org" % i)
            self.ok("commande_annuler", ref=c["commande"])
        self.assertIn("trop de demandes", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="X", mail="y@exemple.org", moyen="stripe", ip="203.0.113.7"))
        self.avance(3601)
        self.commander(1, mail="y@exemple.org")

    def test_un_courriel_est_limite_a_six_commandes_par_heure(self):
        for i in range(6):
            c = self.commander(1, mail="meme@exemple.org", ip="198.51.100.%d" % (i + 1))
            self.ok("commande_annuler", ref=c["commande"])
        self.assertIn("trop de demandes", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="X", mail="meme@exemple.org", moyen="stripe", ip="198.51.100.99"))

    def test_on_ne_vend_jamais_plus_que_le_stock_meme_en_ligne(self):
        self.vendre(9)
        self.assertIn("1 place", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 2}], nom="X", mail="x@exemple.org", moyen="stripe"))


class ParPasserelle(Boutique):
    """Le chemin réel : Stripe poste sur /api/public/…, le corps brut arrive tel quel à la capacité, la signature se vérifie sur ses octets."""

    def setUp(self):
        super().setUp()
        from noyau.CN_passerelle import Passerelle
        self.g = Passerelle(self.n, "127.0.0.1", 0)
        self.g.demarrer()
        self.addCleanup(self.g.arreter)

    def poster(self, corps, entete):
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        c.request("POST", "/api/public/billetterie.public_webhook_stripe", body=corps, headers={"Content-Type": "application/json; charset=utf-8", "Stripe-Signature": entete})
        r = c.getresponse()
        txt = r.read().decode()
        c.close()
        return r.status, txt

    def test_un_webhook_signe_livre_la_commande(self):
        c = self.commander(2)
        corps = self.evenement_stripe(c)
        st, txt = self.poster(corps, self.mod.CN_stripe.signer(corps, SECRET, int(self.t[0])))
        self.assertEqual(st, 200, txt)
        self.assertEqual(self.ok("commande", ref=c["commande"])["commande"]["etat"], "payee")

    def test_un_webhook_mal_signe_recoit_401_et_ne_livre_rien(self):
        c = self.commander(2)
        corps = self.evenement_stripe(c)
        st, txt = self.poster(corps, "t=%d,v1=%s" % (int(self.t[0]), "a" * 64))
        self.assertEqual(st, 401, txt)
        self.assertEqual(self.ok("commande", ref=c["commande"])["commande"]["etat"], "retenue")

    def test_le_corps_reste_octet_pour_octet_meme_avec_des_espaces_et_des_accents(self):
        c = self.commander(1)
        obj = json.loads(self.evenement_stripe(c))
        corps = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")          # une mise en forme que Stripe pourrait très bien avoir
        st, txt = self.poster(corps, self.mod.CN_stripe.signer(corps, SECRET, int(self.t[0])))
        self.assertEqual(st, 200, txt)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Boutique, Vitrine, Commande, Suivi, Webhook, Abus, ParPasserelle
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
