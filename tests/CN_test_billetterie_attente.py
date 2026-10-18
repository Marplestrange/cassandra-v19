# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 5b
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #14e880
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 5b : la liste d'attente (inscription, ordre, offres qui retiennent les places, expiration, paiement d'une offre, annulation de l'événement).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=14e880 ▼▼▼
"""Bancs de la billetterie, lot 5b : la liste d'attente (inscription, ordre, offres qui retiennent les places, expiration, paiement d'une offre, annulation de l'événement)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_boutique import Boutique      # noqa: E402


class Attente(Boutique):
    def setUp(self):
        super().setUp()
        self.gros = self.vendre(8)              # 8 places vendues
        self.petit = self.vendre(2)             # puis les 2 dernières : complet

    def inscrire(self, mail, q=1, nom="Camille", **k):
        d = dict(evenement=self.eref, quantite=q, nom=nom, mail=mail, ip="198.51.100.%d" % (abs(hash(mail)) % 200 + 1))
        d.update(k)
        return self.pub_ok("public_attente_inscrire", **d)

    def liberer(self, vente):
        self.ok("commande_rembourser", ref=vente["ref"], motif="désistement")

    def etat(self, a):
        return self.pub_ok("public_attente_suivre", suivi=a["suivi"])

    def test_on_ne_s_inscrit_pas_quand_il_reste_des_places(self):
        self.liberer(self.petit)
        self.assertIn("il reste des places", self.pub_echec("public_attente_inscrire", evenement=self.eref, quantite=1, nom="X", mail="x@exemple.org"))

    def test_le_rang_suit_l_ordre_d_inscription_et_un_courriel_ne_s_inscrit_qu_une_fois(self):
        a, b = self.inscrire("a@exemple.org"), self.inscrire("b@exemple.org")
        self.assertEqual((a["rang"], b["rang"]), (1, 2))
        self.assertIn("déjà sur la liste", self.pub_echec("public_attente_inscrire", evenement=self.eref, quantite=1, nom="A", mail="A@exemple.org"))

    def test_la_liste_fermee_refuse(self):
        self.n.reglages.poser("billetterie.liste_attente", False, "")
        self.assertIn("pas ouverte", self.pub_echec("public_attente_inscrire", evenement=self.eref, quantite=1, nom="X", mail="x@exemple.org"))
        self.assertFalse(self.pub_ok("public_evenement", ref=self.eref)["liste_attente"])

    def test_une_place_liberee_est_offerte_au_premier_et_retenue(self):
        a, b = self.inscrire("a@exemple.org", 2), self.inscrire("b@exemple.org", 1)
        self.liberer(self.petit)
        o = self.ok("attente_proposer", evenement_id=self.e["id"])["offres"]
        self.assertEqual([x["mail"] for x in o], ["a@exemple.org"])
        s = self.etat(a)
        self.assertEqual(s["etat"], "offerte")
        self.assertEqual(self.etat(b)["rang"], 1)
        self.assertEqual(self.stock()["restant"], 0)                           # les places sont retenues pour l'offre : personne ne peut les acheter
        self.assertIn("il ne reste que 0", self.echec("panier_devis", evenement_id=self.e["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}]))
        mails = [x for x in self.ok("courriels")["courriels"] if x["a"] == "a@exemple.org" and "libérées" in x["objet"]]
        self.assertEqual(len(mails), 1)
        self.assertIn(s["offre"]["commande"], mails[0]["corps"])

    def test_celui_qui_ne_tient_pas_dans_les_places_libres_est_saute_pas_oublie(self):
        a, b = self.inscrire("a@exemple.org", 2), self.inscrire("b@exemple.org", 1)
        self.liberer(self.gros)                                                # 8 places : tout le monde est servi
        self.ok("attente_proposer", evenement_id=self.e["id"])
        self.assertEqual((self.etat(a)["etat"], self.etat(b)["etat"]), ("offerte", "offerte"))

    def test_celui_dont_la_demande_ne_tient_pas_est_saute_sans_perdre_son_rang(self):
        a, b = self.inscrire("a@exemple.org", 3), self.inscrire("b@exemple.org", 2)
        self.liberer(self.petit)                                               # 2 places libres : la demande de 3 ne tient pas, celle de 2 oui
        self.ok("attente_proposer", evenement_id=self.e["id"])
        self.assertEqual((self.etat(a)["etat"], self.etat(a)["rang"], self.etat(b)["etat"]), ("attente", 1, "offerte"))

    def test_l_offre_expire_et_la_place_passe_au_suivant(self):
        a, b = self.inscrire("a@exemple.org", 2), self.inscrire("b@exemple.org", 2)
        self.liberer(self.petit)
        self.ok("attente_proposer", evenement_id=self.e["id"])
        self.assertEqual(self.etat(b)["etat"], "attente")
        self.avance(25 * 3600)                                                 # l'offre dure 24 h
        self.ok("attente_proposer", evenement_id=self.e["id"])
        self.assertEqual((self.etat(a)["etat"], self.etat(b)["etat"]), ("expiree", "offerte"))

    def test_payer_l_offre_la_convertit(self):
        a = self.inscrire("a@exemple.org", 2)
        self.liberer(self.petit)
        self.ok("attente_proposer", evenement_id=self.e["id"])
        o = self.etat(a)["offre"]
        p = self.pub_ok("public_payer", commande=o["commande"], suivi=o["suivi"], moyen="stripe")
        self.assertEqual(p["paiement"]["type"], "stripe")
        self.assertEqual(p["total"], 2200)                                    # 2 x 10 € + 2 € de frais d'achat sans compte
        self.ok("commande_encaisser", ref=o["commande"], moyen="stripe", reference_externe="pi_att")
        self.assertEqual(self.etat(a)["etat"], "convertie")
        self.assertEqual(self.stock()["vendus"], 10)

    def test_payer_une_offre_par_virement_prolonge_la_retenue(self):
        a = self.inscrire("a@exemple.org", 2)
        self.liberer(self.petit)
        self.ok("attente_proposer", evenement_id=self.e["id"])
        o = self.etat(a)["offre"]
        p = self.pub_ok("public_payer", commande=o["commande"], suivi=o["suivi"], moyen="virement")
        self.assertEqual((p["paiement"]["type"], p["paiement"]["reference"]), ("virement", o["commande"]))
        self.assertEqual(self.ok("commande", ref=o["commande"])["commande"]["etat"], "en_attente")

    def test_public_payer_exige_le_bon_jeton_et_une_reservation_valable(self):
        a = self.inscrire("a@exemple.org", 2)
        self.liberer(self.petit)
        self.ok("attente_proposer", evenement_id=self.e["id"])
        o = self.etat(a)["offre"]
        self.assertIn("introuvable", self.pub_echec("public_payer", commande=o["commande"], suivi="faux", moyen="stripe"))
        self.assertIn("pas proposé", self.pub_echec("public_payer", commande=o["commande"], suivi=o["suivi"], moyen="paypal"))
        self.avance(25 * 3600)
        self.assertIn("plus valable", self.pub_echec("public_payer", commande=o["commande"], suivi=o["suivi"], moyen="stripe"))

    def test_des_visiteurs_qui_se_trompent_ne_ferment_pas_la_boutique(self):
        for _ in range(4):
            self.pub_echec("public_payer", commande="CMD-000001", suivi="faux", moyen="stripe")
        self.assertEqual(self.n.catalogue.savoir("billetterie.public_payer")["palier"], "auto")

    def test_refuser_l_offre_libere_les_places_pour_le_suivant(self):
        a, b = self.inscrire("a@exemple.org", 2), self.inscrire("b@exemple.org", 2)
        self.liberer(self.petit)
        self.ok("attente_proposer", evenement_id=self.e["id"])
        r = self.pub_ok("public_attente_retirer", suivi=a["suivi"])
        self.assertEqual(r["offres_suivantes"], 1)
        self.assertEqual((self.etat(a)["etat"], self.etat(b)["etat"]), ("retiree", "offerte"))
        self.assertIn("plus active", self.pub_echec("public_attente_retirer", suivi=a["suivi"]))

    def test_defaire_les_offres_rend_les_places_et_les_rangs(self):
        a = self.inscrire("a@exemple.org", 2)
        self.liberer(self.petit)
        res = self.ok("attente_proposer", evenement_id=self.e["id"])
        self.defaire("attente_proposer", res)
        self.assertEqual(self.etat(a)["etat"], "attente")
        self.assertEqual(self.stock()["restant"], 2)
        self.assertEqual([x for x in self.ok("courriels")["courriels"] if "libérées" in x["objet"]], [])

    def test_un_jeton_inconnu_ne_dit_rien(self):
        self.assertIn("introuvable", self.pub_echec("public_attente_suivre", suivi="nimporte"))

    def test_annuler_l_evenement_ferme_la_liste_et_defaire_la_rouvre(self):
        a = self.inscrire("a@exemple.org", 2)
        res = self.ok("evenement_annuler", id=self.e["id"], motif="Salle fermée", confirme=True)
        self.assertEqual(self.etat(a)["etat"], "retiree")
        self.defaire("evenement_annuler", res)
        self.assertEqual(self.etat(a)["etat"], "attente")

    def test_le_titulaire_lit_la_liste_dans_l_ordre(self):
        self.inscrire("a@exemple.org", 2)
        self.inscrire("b@exemple.org", 1, nom="Bastien")
        l = self.ok("attente_liste", evenement_id=self.e["id"])["attente"]
        self.assertEqual([(x["mail"], x["quantite"], x["etat"]) for x in l], [("a@exemple.org", 2, "attente"), ("b@exemple.org", 1, "attente")])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Attente
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
