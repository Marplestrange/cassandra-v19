# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #71a703
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie : la rentabilité d'un événement (coûts, recettes, seuil de rentabilité, date de décision, conseil).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=71a703 ▼▼▼
"""Bancs de la billetterie : la rentabilité d'un événement (coûts, recettes, seuil de rentabilité, date de décision, conseil)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_ventes import Ventes      # noqa: E402


class Rentabilite(Ventes):
    """La salle coûte 100 €, les places 15 € : sans artiste, 7 places équilibrent la soirée (7 x 15 = 105 ≥ 100)."""

    def setUp(self):
        super().setUp()
        self.ok("salle_save", id=self.salle_id, location=10000, acompte=3000)

    def rent(self):
        return self.ok("evenement_rentabilite", evenement_id=self.e["id"])

    def artiste(self, scene, forfait, role="cachet"):
        f = self.ok("formule_save", nom="F " + scene, role=role, forfait=forfait, com=500 if role == "artiste" else 0)
        a = self.ok("artiste_save", scene=scene, formule_id=f["id"])
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=a["id"], duree=30)
        return a

    def test_sans_cout_le_seuil_n_est_pas_calculable_et_le_dit(self):
        self.ok("salle_save", id=self.salle_id, location=0, acompte=0)
        r = self.rent()
        self.assertEqual((r["couts_fixes"], r["seuil_places"]), (0, 0))
        self.assertIn("pas calculable", r["conseil"])

    def test_le_seuil_vient_de_la_salle_et_des_artistes(self):
        self.artiste("Nova", 8000)                                               # 100 € + 80 € = 180 € ; 180 / 15 = 12 places
        r = self.rent()
        self.assertEqual((r["couts_salle"], r["couts_artistes"], r["couts_fixes"], r["seuil_places"], r["seuil_sans_commission"]), (10000, 8000, 18000, 12, 12))
        self.assertEqual(r["artistes"], [{"scene": "Nova", "montant": 8000}])

    def test_un_artiste_qui_joue_deux_fois_n_est_paye_qu_une_fois(self):
        a = self.artiste("Nova", 8000)
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=a["id"], duree=20)
        self.assertEqual(self.rent()["couts_artistes"], 8000)

    def test_les_recettes_et_le_resultat_se_lisent_sur_les_ventes_payees(self):
        self.artiste("Nova", 8000)
        self.vendre(8)
        self.acheter([{"type_billet_id": self.plein, "quantite": 2}])             # une réservation non payée ne compte pas
        r = self.rent()
        self.assertEqual((r["vendus"], r["recettes"], r["resultat"], r["places_manquantes"]), (8, 12000, 12000 - 18000, 4))

    def test_les_dons_ne_sont_pas_des_recettes_de_billets(self):
        self.vendre(2, don=500)
        self.assertEqual(self.rent()["recettes"], 3000)

    def test_la_commission_observee_par_place_releve_le_seuil(self):
        fc = self.formule(com=300, palier_n=12, palier_com=500, fixe=0)
        rev = self.ok("revendeur_save", nom="Léa")
        code = self.ok("revendeur", id=rev["id"])["revendeur"]["code"]
        self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=rev["id"], formule_id=fc["id"], quota=8)
        self.vendre(4, revendeur_code=code)                                        # 4 places, 12 € de commission : 3 € par place
        r = self.rent()
        self.assertEqual((r["commissions"], r["commission_par_place"], r["seuil_sans_commission"], r["seuil_places"]), (1200, 300, 7, 9))          # 100 € / (15 - 3) = 8,33 -> 9

    def test_la_date_de_decision_et_le_conseil(self):
        self.t[0] = 1_790_000_000.0                                                # fin septembre 2026 : bien avant la date de décision
        self.artiste("Nova", 8000)
        r = self.rent()
        self.assertEqual(r["date_decision"], "2026-12-05")                          # J-7 par défaut
        self.assertFalse(r["decision_due"])
        self.assertIn("Décision le 2026-12-05", r["conseil"])
        self.avance(80 * 24 * 3600)                                                # début décembre : la date de décision (5 décembre) est passée
        r = self.rent()
        self.assertTrue(r["decision_due"] and r["sous_le_seuil"])
        self.assertIn("annuler ou reporter", r["conseil"])
        self.assertIn("3000", r["conseil"])                                         # l'acompte de la salle : le plus que l'annulation coûte
        self.assertEqual(r["acompte_salle"], 3000)

    def test_au_dessus_du_seuil_a_la_date_de_decision_on_maintient(self):
        self.vendre(8)
        r = self.rent()                                                            # l'horloge d'essai est en janvier 2027 : la date de décision est passée
        self.assertTrue(r["decision_due"] and not r["sous_le_seuil"])
        self.assertIn("on maintient", r["conseil"])

    def test_elle_n_annule_rien_toute_seule(self):
        self.rent()
        self.assertEqual(self.ok("evenement", id=self.e["id"])["evenement"]["statut"], "en vente")

    def test_la_date_de_decision_suit_le_reglage(self):
        self.n.reglages.poser("billetterie.decision_jours", 14, "")
        self.assertEqual(self.rent()["date_decision"], "2026-11-28")

    def test_un_evenement_annule_est_clos(self):
        self.ok("evenement_annuler", id=self.e["id"], motif="x", confirme=True)
        self.assertIn("clos", self.rent()["conseil"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Rentabilite
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
