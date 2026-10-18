# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 3
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #1f6c61
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 3 : le stock et les places retenues, le prix, les codes promo, les commandes, les billets signés, la commission d'un revendeur (la somme des lignes vaut toujours ce que rapporte la formule), les remboursements, 
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1f6c61 ▼▼▼
"""Bancs de la billetterie, lot 3 : le stock et les places retenues, le prix, les codes promo, les commandes, les billets signés, la commission d'un revendeur (la somme des lignes
vaut toujours ce que rapporte la formule), les remboursements, les invitations, les formules figées."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_base import Monde, BEA      # noqa: E402


class Ventes(Monde):
    """Un événement en vente : 10 places debout, 15 €, billets « Plein tarif » (illimité) et « Tarif réduit » (4 places, 10 €)."""

    def setUp(self):
        super().setUp()
        self.mod = sys.modules["cassandra_module_billetterie"]
        self.t = [1_800_000_000.0]
        self.mod.CN_ventes.horloge = lambda: self.t[0]
        self.addCleanup(setattr, self.mod.CN_ventes, "horloge", __import__("time").time)
        self.e = self.evenement(quota=10)
        self.salle_id = self.ok("evenement", id=self.e["id"])["evenement"]["salle_id"]
        self.ok("evenement_publier", id=self.e["id"])
        types = self.ok("evenement_fiche", id=self.e["id"])["types"]
        self.plein = [t for t in types if t["nom"] == "Plein tarif"][0]["id"]
        self.reduit = [t for t in types if t["nom"] == "Tarif réduit"][0]["id"]
        self.ok("type_billet_save", id=self.reduit, quota=4, prix=1000)

    def acheter(self, lignes=None, **k):
        d = dict(evenement_id=self.e["id"], lignes=lignes or [{"type_billet_id": self.plein, "quantite": 1}], nom="Sophie Marchand", mail="sophie@exemple.org")
        d.update(k)
        return self.ok("commande_creer", **d)

    def vendre(self, n=1, **k):
        return self.acheter([{"type_billet_id": self.plein, "quantite": n}], encaisser=True, moyen="especes", **k)

    def stock(self):
        return self.ok("stock", evenement_id=self.e["id"])

    def avance(self, secondes):
        self.t[0] += secondes


class Prix(Ventes):
    def test_le_prix_vient_de_la_base_pas_de_la_demande(self):
        d = self.ok("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 2, "prix": 1}, {"type_billet_id": self.reduit, "quantite": 1}])
        self.assertEqual((d["sous_total"], d["total"], d["places"]), (3000 + 1000, 4000, 3))

    def test_un_billet_d_un_autre_evenement_est_refuse(self):
        autre = self.evenement(nom="Autre", salle_id=self.salle_id, quota=5)
        self.ok("evenement_publier", id=autre["id"])
        tid = self.ok("evenement_fiche", id=autre["id"])["types"][0]["id"]
        self.assertIn("n'existe pas", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": tid, "quantite": 1}]))

    def test_un_panier_vide_ou_un_evenement_en_brouillon_ne_se_vend_pas(self):
        self.assertIn("vide", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[]))
        b = self.evenement(nom="Brouillon", salle_id=self.salle_id)
        self.assertIn("pas en vente", self.echec("panier_devis", evenement_id=b["id"], lignes=[{"type_billet_id": 1, "quantite": 1}]))

    def test_code_promo_en_pourcentage_et_en_euros(self):
        self.ok("promo_save", code="hiver10", type="pct", valeur=10)
        self.ok("promo_save", code="amis5", type="eur", valeur=500)
        d = self.ok("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 2}], code_promo="HIVER10")
        self.assertEqual((d["remise"], d["total"], d["promo"]), (300, 2700, "HIVER10"))
        d = self.ok("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 2}], code_promo="amis5")
        self.assertEqual((d["remise"], d["total"]), (1000, 2000))

    def test_la_remise_en_euros_ne_depasse_jamais_le_prix(self):
        self.ok("promo_save", code="enorme", type="eur", valeur=99900)
        d = self.ok("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], code_promo="ENORME")
        self.assertEqual((d["remise"], d["total"]), (1500, 0))

    def test_un_code_promo_refuse_dit_pourquoi(self):
        self.assertIn("inconnu", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], code_promo="NOPE"))
        p = self.ok("promo_save", code="ancien", type="pct", valeur=10, fin="2020-01-01")
        self.assertIn("expiré", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], code_promo="ANCIEN"))
        self.ok("promo_save", id=p["id"], fin="")
        self.ok("promo_save", id=p["id"], actif=0)
        self.assertIn("plus actif", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], code_promo="ANCIEN"))

    def test_un_code_promo_est_limite_en_utilisations_et_ne_se_reutilise_pas_apres_suppression(self):
        p = self.ok("promo_save", code="deux", type="pct", valeur=50, max_usages=2)
        self.vendre(1, code_promo="DEUX")
        self.vendre(1, code_promo="DEUX")
        self.assertIn("utilisations", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], code_promo="DEUX"))
        q = self.ok("promo_save", code="jetable", type="pct", valeur=5)
        self.ok("promo_delete", id=q["id"])
        self.assertIn("jamais réutilisé", self.echec("promo_save", code="JETABLE", type="pct", valeur=5))
        self.assertTrue(p["id"])

    def test_une_promo_servie_ne_se_supprime_pas(self):
        p = self.ok("promo_save", code="servie", type="pct", valeur=10)
        self.vendre(1, code_promo="SERVIE")
        self.assertIn("désactivez", self.echec("promo_delete", id=p["id"]))

    def test_le_don_n_existe_que_pour_une_association(self):
        d = self.ok("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], don=500)
        self.assertEqual(d["total"], 2000)
        self.n.reglages.poser("billetterie.titulaire_statut", "autre", "")
        self.assertIn("association", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], don=500))

    def test_les_frais_sans_compte_et_le_compte_obligatoire(self):
        L = [{"type_billet_id": self.plein, "quantite": 1}]
        self.n.reglages.poser("billetterie.compte_client", "libre", "")
        self.assertEqual(self.ok("panier_devis", evenement_id=self.e["id"], lignes=L, canal="caisse", sans_compte=True)["frais"], 0)     # la caisse n'a pas de frais
        d = self.ok("panier_devis", evenement_id=self.e["id"], lignes=L, canal="boutique", sans_compte=True)
        self.assertEqual((d["frais"], d["total"]), (200, 1700))                                    # le réglage général : 2 €
        self.ok("evenement_save", id=self.e["id"], frais_sans_compte=300)
        self.assertEqual(self.ok("panier_devis", evenement_id=self.e["id"], lignes=L, canal="boutique", sans_compte=True)["total"], 1800)   # la fiche de l'événement l'emporte
        self.assertEqual(self.ok("panier_devis", evenement_id=self.e["id"], lignes=L, canal="boutique", sans_compte=False)["frais"], 0)      # avec un compte : aucun frais
        self.n.reglages.poser("billetterie.compte_client", "obligatoire", "")
        self.assertIn("compte", self.echec("panier_devis", evenement_id=self.e["id"], lignes=L, canal="boutique", sans_compte=True))
        self.ok("evenement_save", id=self.e["id"], achat="libre")                                 # la fiche de l'événement l'emporte sur le réglage
        self.assertEqual(self.ok("panier_devis", evenement_id=self.e["id"], lignes=L, canal="boutique", sans_compte=True)["total"], 1800)


class Stock(Ventes):
    def test_une_commande_en_cours_retient_ses_places_puis_les_rend(self):
        self.acheter([{"type_billet_id": self.plein, "quantite": 3}])
        s = self.stock()
        self.assertEqual((s["vendus"], s["retenus"], s["restant"]), (0, 3, 7))
        self.avance(11 * 60)                                       # 10 minutes de réservation par défaut
        self.assertEqual(self.stock()["restant"], 10)

    def test_on_ne_vend_pas_plus_que_ce_qui_reste(self):
        self.vendre(8)
        self.assertIn("2 place", self.echec("commande_creer", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 3}]))
        self.vendre(2)
        self.assertEqual(self.stock()["restant"], 0)

    def test_le_quota_d_un_type_de_billet_est_respecte(self):
        L = lambda q: [{"type_billet_id": self.reduit, "quantite": q}]
        self.acheter(L(4), encaisser=True, moyen="especes")
        self.assertIn("Tarif réduit", self.echec("commande_creer", evenement_id=self.e["id"], lignes=L(1)))
        s = [t for t in self.stock()["types"] if t["nom"] == "Tarif réduit"][0]
        self.assertEqual((s["vendus"], s["restant"]), (4, 0))

    def test_les_invitations_ne_comptent_pas_dans_le_stock_de_vente(self):
        self.ok("invitation_save", evenement_id=self.e["id"], categorie="Presse", quota=2)
        self.ok("invitation_emettre", evenement_id=self.e["id"], categorie="Presse", nom="Journaliste")
        self.assertEqual((self.stock()["vendus"], self.stock()["restant"]), (0, 10))

    def test_le_moteur_expirer_libere_les_commandes_echues(self):
        c = self.acheter([{"type_billet_id": self.plein, "quantite": 2}])
        self.avance(11 * 60)
        with self.ctx.stockage.transaction() as tx:
            self.assertEqual(self.mod.CN_ventes.expirer(tx), 1)
        self.assertEqual(self.ok("commande", ref=c["ref"])["commande"]["etat"], "expiree")

    def test_payer_apres_l_expiration_ne_marche_que_si_les_places_sont_encore_la(self):
        c = self.acheter([{"type_billet_id": self.plein, "quantite": 3}])
        self.avance(11 * 60)
        self.vendre(9)                                             # les places repartent
        self.assertIn("reparties", self.echec("commande_encaisser", ref=c["ref"], moyen="especes"))


class Commandes(Ventes):
    def test_encaisser_cree_les_billets_numerotes_par_evenement(self):
        c = self.vendre(3)
        self.assertEqual((c["etat"], c["total"], len(c["numeros"])), ("payee", 4500, 3))
        self.assertEqual(c["numeros"], ["A-0001", "A-0002", "A-0003"])
        self.assertEqual(self.stock()["vendus"], 3)
        fiche = self.ok("commande", ref=c["ref"])
        self.assertEqual([b["nom"] for b in fiche["billets"]], ["Sophie Marchand"] * 3)

    def test_la_meme_reference_de_paiement_ne_livre_pas_deux_fois(self):
        c = self.acheter()
        r1 = self.ok("commande_encaisser", ref=c["ref"], moyen="stripe", reference_externe="pi_123")
        r2 = self.ok("commande_encaisser", ref=c["ref"], moyen="stripe", reference_externe="pi_123")
        self.assertEqual((len(r1["numeros"]), r2["deja"], r2["numeros"]), (1, True, r1["numeros"]))
        autre = self.acheter()
        self.assertIn("déjà rattaché", self.echec("commande_encaisser", ref=autre["ref"], moyen="stripe", reference_externe="pi_123"))
        self.assertEqual(self.stock()["vendus"], 1)

    def test_une_commande_payee_ne_se_paie_pas_deux_fois(self):
        c = self.vendre(1)
        self.assertIn("plus à payer", self.echec("commande_encaisser", ref=c["ref"], moyen="especes"))

    def test_un_virement_retient_trois_jours_puis_se_valide(self):
        c = self.acheter(moyen="virement")
        self.assertEqual(self.ok("commande", ref=c["ref"])["commande"]["etat"], "en_attente")
        self.avance(2 * 24 * 3600)
        self.assertEqual(self.stock()["retenus"], 1)
        self.ok("commande_encaisser", ref=c["ref"], moyen="virement", reference_externe="VIR-1")
        self.assertEqual(self.stock()["vendus"], 1)

    def test_encaisser_se_defait(self):
        c = self.acheter()
        res = self.ex("commande_encaisser", ref=c["ref"], moyen="especes")["resultat"]
        self.defaire("commande_encaisser", res)
        self.assertEqual(self.stock()["vendus"], 0)
        self.assertEqual(self.ok("commande", ref=c["ref"])["commande"]["etat"], "retenue")

    def test_annuler_une_commande_en_cours_rend_les_places_et_se_defait(self):
        c = self.acheter([{"type_billet_id": self.plein, "quantite": 4}])
        res = self.ok("commande_annuler", ref=c["ref"])
        self.assertEqual(self.stock()["restant"], 10)
        self.defaire("commande_annuler", res)
        self.assertEqual(self.stock()["retenus"], 4)

    def test_on_n_annule_pas_une_commande_payee_on_la_rembourse(self):
        c = self.vendre(1)
        self.assertIn("rembourse", self.echec("commande_annuler", ref=c["ref"]))

    def test_creer_encaisser_puis_annuler_la_creation_ne_laisse_rien(self):
        res = self.ex("commande_creer", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 2}], encaisser=True, moyen="especes")["resultat"]
        self.defaire("commande_creer", res)
        self.assertEqual((self.stock()["vendus"], self.stock()["restant"]), (0, 10))

    def test_un_moyen_immediat_seulement_pour_encaisser_sur_le_champ(self):
        self.assertIn("moyen immédiat", self.echec("commande_creer", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], encaisser=True, moyen="stripe"))

    def test_un_mail_invalide_est_refuse(self):
        self.assertIn("courriel", self.echec("commande_creer", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], mail="pas-un-mail"))


class Billets(Ventes):
    def lire(self, numero):
        return self.ok("billet", numero=numero)

    def test_chaque_billet_a_son_qr_et_son_numero_de_controle(self):
        c = self.vendre(2)
        a, b = [self.lire(n) for n in c["numeros"]]
        self.assertRegex(a["code_controle"], r"^A-0001-[A-HJ-NP-Z2-9]{6}$")
        self.assertTrue(a["qr"].startswith("CASS1.A-0001."))
        self.assertNotEqual(a["code_controle"], b["code_controle"])

    def test_la_signature_dit_si_un_billet_est_authentique(self):
        c = self.vendre(1)
        b = self.lire(c["numeros"][0])
        k = self.mod.CN_billets.cle(self.ctx, self.ctx.stockage)
        lu = self.mod.CN_billets.lire(b["qr"])
        self.assertEqual((lu["source"], lu["numero"]), ("qr", "A-0001"))
        self.assertTrue(self.mod.CN_billets.authentique(k, lu["numero"], 0, lu["signature"]))
        faux = self.mod.CN_billets.lire("CASS1.A-0001.AAAAAA")
        self.assertFalse(self.mod.CN_billets.authentique(k, faux["numero"], 0, faux["signature"]))
        num = self.mod.CN_billets.lire(b["code_controle"])
        self.assertEqual(num["source"], "num")
        self.assertTrue(self.mod.CN_billets.authentique(k, num["numero"], 0, num["signature"]))

    def test_reemettre_change_la_signature_et_l_ancienne_ne_passe_plus(self):
        c = self.vendre(1)
        avant = self.lire(c["numeros"][0])
        res = self.ok("billet_reemettre", numero=c["numeros"][0])
        apres = self.lire(c["numeros"][0])
        self.assertNotEqual(avant["code_controle"], apres["code_controle"])
        k = self.mod.CN_billets.cle(self.ctx, self.ctx.stockage)
        ancien = self.mod.CN_billets.lire(avant["qr"])
        self.assertFalse(self.mod.CN_billets.authentique(k, ancien["numero"], 1, ancien["signature"]))
        self.defaire("billet_reemettre", res)
        self.assertEqual(self.lire(c["numeros"][0])["code_controle"], avant["code_controle"])

    def test_transferer_change_le_porteur_et_se_defait(self):
        c = self.vendre(1)
        res = self.ok("billet_transferer", numero=c["numeros"][0], nom="Marc Lenoir", mail="marc@exemple.org")
        self.assertEqual(self.lire(c["numeros"][0])["billet"]["nom"], "Marc Lenoir")
        self.defaire("billet_transferer", res)
        self.assertEqual(self.lire(c["numeros"][0])["billet"]["nom"], "Sophie Marchand")

    def test_la_cle_est_creee_une_fois_et_n_est_jamais_en_clair(self):
        k1 = self.mod.CN_billets.cle(self.ctx, self.ctx.stockage)
        k2 = self.mod.CN_billets.cle(self.ctx, self.ctx.stockage)
        self.assertEqual((k1, len(k1)), (k2, 32))
        stocke = self.ctx.stockage.lire("SELECT valeur FROM cles")[0]["valeur"]
        self.assertNotIn(k1.hex(), stocke)

    def test_les_invitations_ont_un_quota_et_se_defont(self):
        self.ok("invitation_save", evenement_id=self.e["id"], categorie="Presse", quota=1)
        res = self.ok("invitation_emettre", evenement_id=self.e["id"], categorie="Presse", nom="Journaliste")
        self.assertIn("quota", self.echec("invitation_emettre", evenement_id=self.e["id"], categorie="Presse", nom="Autre"))
        self.assertIn("n'existe pas", self.echec("invitation_emettre", evenement_id=self.e["id"], categorie="VIP", nom="X"))
        self.defaire("invitation_emettre", res)
        self.ok("invitation_emettre", evenement_id=self.e["id"], categorie="Presse", nom="Autre")


class Commissions(Ventes):
    """Le coeur : la somme des lignes du registre vaut TOUJOURS ce que rapporte la formule pour les billets réellement vendus."""

    def setUp(self):
        super().setUp()
        self.fc = self.formule(com=300, palier_n=3, palier_com=500, fixe=1000)         # 3 €, 5 € au-delà de 3 places, 10 € de fixe
        self.rev = self.ok("revendeur_save", nom="Léa Martin")
        self.code = self.ok("revendeur", id=self.rev["id"])["revendeur"]["code"]
        self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=self.rev["id"], formule_id=self.fc["id"], quota=8)

    def du(self):
        return self.ok("portefeuille", porteur="revendeur", porteur_id=self.rev["id"], au="2099-01-01")["du"]

    def attendu(self, n):
        return self.ok("commission", formule_id=self.fc["id"], places=n)["total"]

    def test_le_scenario_de_la_demande_des_billets_a_15_euros_5_euros_de_commission(self):
        f = self.formule(nom="Simple", com=500, palier_n=0, palier_com=0, fixe=0)
        rev = self.ok("revendeur_save", nom="Karim Benali")
        code = self.ok("revendeur", id=rev["id"])["revendeur"]["code"]
        e = self.evenement(nom="Concert", salle_id=self.salle_id, quota=30, prix=1500)
        self.ok("evenement_publier", id=e["id"])
        tid = self.ok("evenement_fiche", id=e["id"])["types"][0]["id"]
        self.ok("affectation_save", evenement_id=e["id"], revendeur_id=rev["id"], formule_id=f["id"], quota=20)
        for _ in range(20):
            self.ok("commande_creer", evenement_id=e["id"], lignes=[{"type_billet_id": tid, "quantite": 1}], revendeur_code=code, encaisser=True, moyen="especes")
        self.assertEqual(self.ok("portefeuille", porteur="revendeur", porteur_id=rev["id"], au="2099-01-01")["du"], 10000)        # 20 billets x 5 € = 100 €

    def test_la_commission_suit_la_formule_vente_apres_vente(self):
        for n in range(1, 7):
            self.vendre(1, revendeur_code=self.code)
            self.assertEqual(self.du(), self.attendu(n), "après %d billet(s)" % n)

    def test_une_vente_de_plusieurs_billets_vaut_la_somme_des_ventes_unitaires(self):
        self.vendre(5, revendeur_code=self.code)
        self.assertEqual(self.du(), self.attendu(5))

    def test_un_remboursement_retire_la_commission_dans_n_importe_quel_ordre(self):
        a = self.vendre(2, revendeur_code=self.code)
        b = self.vendre(2, revendeur_code=self.code)
        c = self.vendre(1, revendeur_code=self.code)
        self.assertEqual(self.du(), self.attendu(5))
        self.ok("commande_rembourser", ref=a["ref"])
        self.assertEqual(self.du(), self.attendu(3))
        self.ok("commande_rembourser", ref=c["ref"])
        self.assertEqual(self.du(), self.attendu(2))
        self.ok("commande_rembourser", ref=b["ref"])
        self.assertEqual(self.du(), 0)                                  # plus aucune vente : plus rien, fixe compris

    def test_le_fixe_n_est_du_qu_a_la_premiere_vente_et_repart_avec_la_derniere(self):
        a = self.vendre(1, revendeur_code=self.code)
        self.assertEqual(self.du(), 300 + 1000)
        self.ok("commande_rembourser", ref=a["ref"])
        self.assertEqual(self.du(), 0)

    def test_le_remboursement_rend_les_places_annule_les_billets_et_se_defait(self):
        c = self.vendre(3, revendeur_code=self.code)
        res = self.ok("commande_rembourser", ref=c["ref"], motif="annulation client")
        self.assertEqual((self.stock()["vendus"], res["chez_le_prestataire"]), (0, False))
        self.assertEqual({b["etat"] for b in self.ok("commande", ref=c["ref"])["billets"]}, {"annule"})
        self.defaire("commande_rembourser", res)
        self.assertEqual(self.du(), self.attendu(3))
        self.assertEqual(self.stock()["vendus"], 3)
        self.ok("commande_rembourser", ref=c["ref"])                       # et se rembourse de nouveau, sans collision de lignes
        self.assertEqual(self.du(), 0)

    def test_un_paiement_par_prestataire_dit_qu_il_reste_a_rembourser_chez_lui(self):
        c = self.acheter(revendeur_code=self.code)
        self.ok("commande_encaisser", ref=c["ref"], moyen="stripe", reference_externe="pi_9")
        self.assertTrue(self.ok("commande_rembourser", ref=c["ref"])["chez_le_prestataire"])

    def test_la_commission_n_est_retirable_qu_apres_l_evenement_plus_le_delai(self):
        self.ok("evenement_save", id=self.e["id"], date_iso="2099-06-10")
        self.vendre(1, revendeur_code=self.code)
        s = self.ok("portefeuille", porteur="revendeur", porteur_id=self.rev["id"], au="2099-06-16")
        self.assertEqual((s["disponible"], s["en_attente"]), (0, 1300))
        s = self.ok("portefeuille", porteur="revendeur", porteur_id=self.rev["id"], au="2099-06-17")
        self.assertEqual((s["disponible"], s["en_attente"]), (1300, 0))                  # 7 jours après le 10

    def test_un_code_inconnu_ou_un_revendeur_non_affecte_donne_une_vente_directe(self):
        c = self.vendre(1, revendeur_code="ZZZ-0000")
        self.assertIn("vente directe", self.ok("commande", ref=c["ref"])["commande"]["attribution"])
        autre = self.ok("revendeur_save", nom="Sans Affectation")
        code = self.ok("revendeur", id=autre["id"])["revendeur"]["code"]
        d = self.vendre(1, revendeur_code=code)
        self.assertIn("pas affecté", self.ok("commande", ref=d["ref"])["commande"]["attribution"])
        self.assertEqual(self.du(), 0)

    def test_le_quota_du_revendeur_limite_l_attribution_pas_la_vente(self):
        self.vendre(8, revendeur_code=self.code)
        c = self.vendre(1, revendeur_code=self.code)
        self.assertIn("quota", self.ok("commande", ref=c["ref"])["commande"]["attribution"])
        self.assertEqual(self.du(), self.attendu(8))

    def test_un_artiste_vendeur_touche_ses_commissions_dans_son_propre_portefeuille(self):
        fa = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        art = self.ok("artiste_save", scene="Les Marées", formule_id=fa["id"], vend=1)
        rev = self.ok("artiste", id=art["id"])["artiste"]["revendeur_id"]
        code = self.ok("revendeur", id=rev)["revendeur"]["code"]
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=art["id"])
        self.vendre(4, revendeur_code=code)
        s = self.ok("portefeuille", porteur="artiste", porteur_id=art["id"], au="2099-01-01")
        self.assertEqual(s["du"], 4 * 500)                                # la commission seule : le forfait se provisionne à part

    def test_un_artiste_qui_ne_joue_pas_ne_vend_pas_pour_cet_evenement(self):
        fa = self.ok("formule_save", nom="A", role="artiste", forfait=8000, com=500)
        art = self.ok("artiste_save", scene="Absent", formule_id=fa["id"], vend=1)
        rev = self.ok("artiste", id=art["id"])["artiste"]["revendeur_id"]
        code = self.ok("revendeur", id=rev)["revendeur"]["code"]
        c = self.vendre(1, revendeur_code=code)
        self.assertIn("ne joue pas", self.ok("commande", ref=c["ref"])["commande"]["attribution"])

    def test_la_formule_modifiee_ne_change_pas_les_conditions_d_un_evenement_qui_a_des_ventes(self):
        self.vendre(1, revendeur_code=self.code)
        self.assertEqual(self.du(), 300 + 1000)
        self.ok("formule_save", id=self.fc["id"], com=900, fixe=5000)       # la formule change APRÈS une vente
        self.vendre(1, revendeur_code=self.code)                            # l'événement garde ses conditions d'origine
        self.assertEqual(self.du(), 2 * 300 + 1000)
        autre = self.evenement(nom="Neuf", salle_id=self.salle_id, quota=10)
        self.ok("evenement_publier", id=autre["id"])
        self.ok("affectation_save", evenement_id=autre["id"], revendeur_id=self.rev["id"], formule_id=self.fc["id"])
        tid = self.ok("evenement_fiche", id=autre["id"])["types"][0]["id"]
        avant = self.du()
        self.ok("commande_creer", evenement_id=autre["id"], lignes=[{"type_billet_id": tid, "quantite": 1}], revendeur_code=self.code, encaisser=True, moyen="especes")
        self.assertEqual(self.du() - avant, 900 + 5000)                     # un événement sans vente prend les conditions nouvelles


class Suppressions(Ventes):
    def test_ce_qui_a_des_ventes_ne_se_supprime_pas(self):
        self.vendre(1)
        self.assertIn("commande", self.echec("evenement_delete", id=self.e["id"]))
        self.assertIn("vendu", self.echec("type_billet_delete", id=self.plein))

    def test_un_revendeur_qui_a_une_ligne_au_registre_ne_se_supprime_pas(self):
        rev = self.ok("revendeur_save", nom="Léa Martin")
        self.ok("provision", porteur="revendeur", porteur_id=rev["id"], nature="commission", montant=100)
        self.assertIn("registre", self.echec("revendeur_delete", id=rev["id"]))

    def test_un_revendeur_qui_a_vendu_ne_se_supprime_pas_meme_sans_affectation(self):
        fc = self.formule()
        rev = self.ok("revendeur_save", nom="Karim Benali")
        code = self.ok("revendeur", id=rev["id"])["revendeur"]["code"]
        aff = self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=rev["id"], formule_id=fc["id"])
        self.vendre(1, revendeur_code=code)
        err = self.echec("revendeur_delete", id=rev["id"])
        self.assertTrue("commande" in err or "registre" in err or "affectation" in err, err)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Ventes, Prix, Stock, Commandes, Billets, Commissions, Suppressions
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
