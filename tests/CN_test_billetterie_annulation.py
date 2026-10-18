# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 5a
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #b99b2f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 5a : annuler et reporter un événement (remboursements en masse, commissions reprises, courriels, disponibilité des commissions).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b99b2f ▼▼▼
"""Bancs de la billetterie, lot 5a : annuler et reporter un événement (remboursements en masse, commissions reprises, courriels, disponibilité des commissions)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_ventes import Ventes      # noqa: E402


class Annulation(Ventes):
    def setUp(self):
        super().setUp()
        self.fc = self.formule(com=300, palier_n=3, palier_com=500, fixe=1000)
        self.rev = self.ok("revendeur_save", nom="Relais Nord", mail="nord@exemple.org")
        self.code = self.ok("revendeur", id=self.rev["id"])["revendeur"]["code"]
        self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=self.rev["id"], formule_id=self.fc["id"], quota=8)

    def revendeur_vend(self, n=2):
        return self.vendre(n, revendeur_code=self.code)

    def solde(self, au):
        return self.ok("portefeuille", porteur="revendeur", porteur_id=self.rev["id"], au=au)

    def dossier(self):
        """Trois ventes : espèces, Stripe, une réservation non payée, plus une invitation."""
        a = self.vendre(2)
        b = self.acheter([{"type_billet_id": self.plein, "quantite": 1}], mail="paul@exemple.org")
        self.ok("commande_encaisser", ref=b["ref"], moyen="stripe", reference_externe="pi_test_1")
        c = self.acheter([{"type_billet_id": self.plein, "quantite": 1}], mail="encours@exemple.org")
        return a, b, c

    def test_l_impact_annonce_les_chiffres_sans_rien_ecrire(self):
        self.dossier()
        i = self.ok("evenement_impact", id=self.e["id"])
        self.assertEqual((i["commandes_payees"], i["a_rembourser"], i["commandes_en_cours"]), (2, 4500, 1))
        self.assertEqual(i["par_moyen"]["stripe"], {"commandes": 1, "montant": 1500})
        self.assertEqual(self.ok("evenement", id=self.e["id"])["evenement"]["statut"], "en vente")

    def test_annuler_exige_confirmation_et_motif(self):
        self.assertIn("confirmez", self.echec("evenement_annuler", id=self.e["id"], motif="Salle fermée"))
        self.assertIn("motif", self.echec("evenement_annuler", id=self.e["id"], confirme=True))

    def test_annuler_rembourse_tout_et_rend_les_places(self):
        self.dossier()
        r = self.ok("evenement_annuler", id=self.e["id"], motif="Salle fermée", confirme=True)
        self.assertEqual(len(r["remboursees"]), 2)
        self.assertEqual(len(r["abandonnees"]), 1)
        self.assertEqual(sorted(x["moyen"] for x in r["reste_a_faire"]), ["especes", "stripe"])
        self.assertTrue([x for x in r["reste_a_faire"] if x["moyen"] == "stripe"][0]["chez_le_prestataire"])
        e = self.ok("evenement", id=self.e["id"])["evenement"]
        self.assertEqual((e["statut"], e["publie"], e["motif_annulation"]), ("annulé", 0, "Salle fermée"))
        self.assertIn("pas en vente", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}]))

    def test_les_acheteurs_sont_prevenus_pas_ceux_dont_la_commande_n_etait_pas_payee(self):
        self.dossier()
        self.ok("evenement_annuler", id=self.e["id"], motif="Salle fermée", confirme=True)
        cs = self.ok("courriels")["courriels"]
        objets = [(x["a"], x["objet"]) for x in cs if "Annulation" in x["objet"]]
        self.assertIn(("paul@exemple.org", "Annulation · " + self.ok("evenement", id=self.e["id"])["evenement"]["nom"]), objets)
        self.assertNotIn("encours@exemple.org", [a for a, _ in objets])
        self.assertIn("nord@exemple.org", [a for a, _ in objets])        # le revendeur affecté est prévenu aussi
        self.assertEqual(len(objets), 3)

    def test_un_evenement_annule_ne_s_annule_pas_deux_fois(self):
        self.ok("evenement_annuler", id=self.e["id"], motif="x", confirme=True)
        self.assertIn("ne peut plus", self.echec("evenement_annuler", id=self.e["id"], motif="y", confirme=True))

    def test_la_commission_du_revendeur_est_reprise(self):
        self.revendeur_vend()
        self.assertGreater(self.solde("2099-01-01")["du"], 0)
        self.ok("evenement_annuler", id=self.e["id"], motif="x", confirme=True)
        self.assertEqual(self.solde("2099-01-01")["du"], 0)

    def test_defaire_l_annulation_rejoue_les_commandes(self):
        a, b, c = self.dossier()
        self.revendeur_vend()
        du = self.solde("2099-01-01")["du"]
        res = self.ok("evenement_annuler", id=self.e["id"], motif="x", confirme=True)
        self.defaire("evenement_annuler", res)
        self.assertEqual(self.ok("evenement", id=self.e["id"])["evenement"]["statut"], "en vente")
        self.assertEqual(self.stock()["vendus"], 5)
        self.assertEqual(self.ok("commande", ref=a["ref"])["commande"]["etat"], "payee")
        self.assertEqual(self.ok("commande", ref=c["ref"])["commande"]["etat"], "retenue")
        self.assertEqual(self.solde("2099-01-01")["du"], du)

    def test_reporter_change_la_date_garde_les_billets_et_previent(self):
        a = self.vendre(1)
        r = self.ok("evenement_reporter", id=self.e["id"], nouvelle_date="2027-03-20", motif="Artiste malade", confirme=True)
        e = self.ok("evenement", id=self.e["id"])["evenement"]
        self.assertEqual((e["date_iso"], e["statut"], e["motif_report"]), ("2027-03-20", "en vente", "Artiste malade"))
        self.assertEqual(self.ok("commande", ref=a["ref"])["commande"]["etat"], "payee")
        self.assertEqual(len(r["courriels"]), 2)       # l'acheteur et le revendeur affecté
        self.assertEqual(r["billets_a_rembourser_sur_demande"], 1)

    def test_reporter_refuse_une_date_passee_ou_absente_ou_identique(self):
        d = self.ok("evenement", id=self.e["id"])["evenement"]["date_iso"]
        self.assertIn("nouvelle date", self.echec("evenement_reporter", id=self.e["id"], motif="x", confirme=True))
        self.assertIn("passée", self.echec("evenement_reporter", id=self.e["id"], nouvelle_date="2020-01-01", motif="x", confirme=True))
        self.assertIn("déjà la date", self.echec("evenement_reporter", id=self.e["id"], nouvelle_date=d, motif="x", confirme=True))

    def test_un_report_repousse_la_disponibilite_des_commissions_deja_ecrites(self):
        self.revendeur_vend()
        self.assertGreater(self.solde("2027-01-01")["disponible"], 0)        # la date d'origine (12-12) + 7 jours est passée au 1er janvier
        res = self.ok("evenement_reporter", id=self.e["id"], nouvelle_date="2027-03-20", motif="x", confirme=True)
        s = self.solde("2027-01-01")
        self.assertEqual(s["disponible"], 0)
        self.assertGreater(s["en_attente"], 0)
        self.assertGreater(self.solde("2027-04-01")["disponible"], 0)
        self.defaire("evenement_reporter", res)
        self.assertGreater(self.solde("2027-01-01")["disponible"], 0)
        self.assertEqual(self.ok("evenement", id=self.e["id"])["evenement"]["date_iso"], "2026-12-12")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Annulation
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
