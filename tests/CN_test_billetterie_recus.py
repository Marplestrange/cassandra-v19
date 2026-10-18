# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 5c
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #42df5e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 5c : les reçus fiscaux de don (conditions d'émission, numéro continu, contenu figé, annulation avec le remboursement, accès par jeton, export).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=42df5e ▼▼▼
"""Bancs de la billetterie, lot 5c : les reçus fiscaux de don (conditions d'émission, numéro continu, contenu figé, annulation avec le remboursement, accès par jeton, export)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_boutique import Boutique      # noqa: E402

ADRESSE = "12 rue des Lilas, 44000 Nantes"


class Recus(Boutique):
    def setUp(self):
        super().setUp()
        for cle, val in (("dons_eligible", True), ("dons_base_legale", "Organisme d'intérêt général, articles 200 et 238 bis du CGI"), ("titulaire_nom", "Maison Bohème"),
                         ("titulaire_adresse", "3 quai des Arts, 44000 Nantes"), ("titulaire_siret", "123 456 789 00012")):
            self.n.reglages.poser("billetterie." + cle, val, "")

    def avec_don(self, don=500, **k):
        return self.vendre(1, don=don, **k)

    def recu(self, cmd, **k):
        d = dict(commande=cmd["ref"], adresse=ADRESSE)
        d.update(k)
        return self.ok("recu_fiscal_emettre", **d)

    def test_un_reglage_manquant_dit_ce_qui_manque(self):
        c = self.avec_don()
        self.n.reglages.poser("billetterie.dons_eligible", False, "")
        self.assertIn("éligible", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse=ADRESSE))
        self.n.reglages.poser("billetterie.dons_eligible", True, "")
        self.n.reglages.poser("billetterie.dons_base_legale", "", "")
        self.assertIn("base légale", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse=ADRESSE))
        self.n.reglages.poser("billetterie.dons_base_legale", "art. 200 CGI", "")
        self.n.reglages.poser("billetterie.titulaire_adresse", "", "")
        self.assertIn("l'adresse de l'organisme", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse=ADRESSE))

    def test_avec_dolibarr_relie_la_billetterie_ne_fabrique_pas_de_recu(self):
        c = self.avec_don()
        self.n.reglages.poser("billetterie.recu_fiscal_autonome", False, "")
        self.assertIn("Dolibarr", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse=ADRESSE))

    def test_seule_une_association_emet(self):
        c = self.avec_don()
        self.n.reglages.poser("billetterie.titulaire_statut", "autre", "")
        self.assertIn("association", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse=ADRESSE))

    def test_un_billet_sans_don_ne_donne_jamais_de_recu(self):
        c = self.vendre(2)
        self.assertIn("ne contient pas de don", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse=ADRESSE))

    def test_une_commande_non_payee_ne_donne_pas_de_recu(self):
        c = self.acheter(don=500)
        self.assertIn("payée", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse=ADRESSE))

    def test_l_adresse_du_donateur_est_obligatoire(self):
        c = self.avec_don()
        self.assertIn("adresse", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse=""))
        self.assertIn("incomplète", self.echec("recu_fiscal_emettre", commande=c["ref"], adresse="Nantes"))

    def test_le_recu_couvre_le_don_pas_le_billet_et_copie_ce_qui_etait_vrai(self):
        c = self.avec_don(500)
        x = self.recu(c)
        self.assertEqual(x["numero"], "RF-000001")
        r = self.ok("recu_fiscal", numero="RF-000001")
        self.assertEqual((r["montant"], r["mode"], r["etat"], r["nom"]), (500, "espèces", "emis", "Sophie Marchand"))
        k = r["contenu"]
        self.assertEqual((k["organisme"]["nom"], k["donateur"]["adresse"], k["montant_centimes"], k["nature"]), ("Maison Bohème", ADRESSE, 500, "numéraire"))
        self.assertIn("238 bis", k["organisme"]["base_legale"])
        self.n.reglages.poser("billetterie.titulaire_adresse", "Ailleurs", "")
        self.assertEqual(self.ok("recu_fiscal", numero="RF-000001")["contenu"]["organisme"]["adresse"], "3 quai des Arts, 44000 Nantes")

    def test_un_deuxieme_appel_rend_le_meme_recu(self):
        c = self.avec_don()
        a, b = self.recu(c), self.recu(c)
        self.assertEqual((a["numero"], b["numero"], b["deja"]), ("RF-000001", "RF-000001", True))
        self.defaire("recu_fiscal_emettre", b)                               # défaire un appel qui n'a rien émis ne touche pas le reçu
        self.assertEqual(self.ok("recu_fiscal", numero="RF-000001")["etat"], "emis")

    def test_la_numerotation_est_continue_et_ne_reutilise_rien(self):
        a, b = self.avec_don(), self.avec_don(300)
        self.recu(a), self.recu(b)
        self.ok("recu_fiscal_annuler", numero="RF-000001", motif="erreur de saisie")
        c = self.avec_don(700)
        self.assertEqual(self.recu(c)["numero"], "RF-000003")
        l = self.ok("recus_fiscaux")
        self.assertEqual([(x["numero"], x["etat"]) for x in l["recus"]], [("RF-000001", "annule"), ("RF-000002", "emis"), ("RF-000003", "emis")])
        self.assertEqual(l["total_emis"], 1000)

    def test_defaire_l_emission_annule_le_recu_et_en_garde_le_numero(self):
        c = self.avec_don()
        x = self.recu(c)
        self.defaire("recu_fiscal_emettre", x)
        self.assertEqual(self.ok("recu_fiscal", numero="RF-000001")["etat"], "annule")
        self.assertEqual(self.recu(c)["numero"], "RF-000002")

    def test_le_remboursement_annule_le_recu_et_le_defaire_le_rouvre(self):
        c = self.avec_don()
        self.recu(c)
        r = self.ok("commande_rembourser", ref=c["ref"], motif="demande du client")
        x = self.ok("recu_fiscal", numero="RF-000001")
        self.assertEqual((x["etat"], x["motif"]), ("annule", "don remboursé"))
        self.defaire("commande_rembourser", r)
        self.assertEqual(self.ok("recu_fiscal", numero="RF-000001")["etat"], "emis")

    def test_un_recu_emis_ne_se_modifie_ni_ne_s_efface(self):
        c = self.avec_don()
        self.recu(c)
        base = self.ctx.stockage
        with self.assertRaises(Exception) as m:
            base.ecrire("UPDATE recus_fiscaux SET montant = 99999 WHERE numero = 'RF-000001'")
        self.assertIn("ne change pas", str(m.exception))
        with self.assertRaises(Exception) as m:
            base.ecrire("DELETE FROM recus_fiscaux WHERE numero = 'RF-000001'")
        self.assertIn("ne s'efface pas", str(m.exception))

    def test_le_donateur_demande_son_recu_avec_le_jeton_de_sa_commande(self):
        self.n.reglages.poser("billetterie.stripe_actif", True, "")
        c = self.commander(1, don=500)
        self.ok("commande_encaisser", ref=c["commande"], moyen="stripe", reference_externe="pi_don")
        self.assertIn("introuvable", self.pub_echec("public_recu_demander", commande=c["commande"], suivi="faux", adresse=ADRESSE))
        self.assertIn("aucun reçu", self.pub_echec("public_recu", commande=c["commande"], suivi=c["suivi"]))
        x = self.pub_ok("public_recu_demander", commande=c["commande"], suivi=c["suivi"], adresse=ADRESSE)
        r = self.pub_ok("public_recu", commande=c["commande"], suivi=c["suivi"])
        self.assertEqual((r["numero"], r["montant"], r["mode"]), (x["numero"], 500, "carte bancaire"))

    def test_le_jeton_d_une_autre_commande_ne_donne_pas_son_recu(self):
        c1 = self.commander(1, don=500)
        c2 = self.commander(1, don=300, mail="autre@exemple.org", ip="203.0.113.8")
        self.ok("commande_encaisser", ref=c1["commande"], moyen="stripe", reference_externe="pi_a")
        self.ok("commande_encaisser", ref=c2["commande"], moyen="stripe", reference_externe="pi_b")
        self.pub_ok("public_recu_demander", commande=c1["commande"], suivi=c1["suivi"], adresse=ADRESSE)
        self.assertIn("introuvable", self.pub_echec("public_recu", commande=c1["commande"], suivi=c2["suivi"]))

    def test_l_export_de_l_annee_est_un_csv_complet(self):
        a, b = self.avec_don(500), self.avec_don(300)
        self.recu(a), self.recu(b, nom="Association des Amis")
        self.ok("recu_fiscal_annuler", numero="RF-000002", motif="doublon")
        csv = self.ok("recus_export", annee="2026")["csv"].strip().split("\n")
        self.assertEqual(csv[0], "numero;date_don;donateur;adresse;montant_eur;mode;etat;motif_annulation;commande")
        self.assertEqual(len(csv), 3)
        self.assertIn("RF-000002;", csv[2])
        self.assertIn(";3.00;espèces;annule;doublon;", csv[2])
        self.assertEqual(len(self.ok("recus_export", annee="2020")["csv"].strip().split("\n")), 1)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Recus
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
