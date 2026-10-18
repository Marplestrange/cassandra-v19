# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 4b
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #8b3c0b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 4b : la caisse (session, espèces et carte, rendu de monnaie, clôture et écart, réserve de numéros pour vendre sans réseau).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8b3c0b ▼▼▼
"""Bancs de la billetterie, lot 4b : la caisse (session, espèces et carte, rendu de monnaie, clôture et écart, réserve de numéros pour vendre sans réseau)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_ventes import Ventes      # noqa: E402


class Caisse(Ventes):
    def setUp(self):
        super().setUp()
        self.n.reglages.poser("billetterie.reserve_caisse", 10, "")
        self.caisse = self.ok("caisse_ouvrir", evenement_id=self.e["id"], caissier="Camille", fond=10000)

    def vente(self, n=1, **k):
        d = dict(caisse_id=self.caisse["id"], lignes=[{"type_billet_id": self.plein, "quantite": n}], moyen="especes", recu=1500 * n)
        d.update(k)
        return self.ok("caisse_vendre", **d)

    def etat(self):
        return self.ok("caisse_etat", caisse_id=self.caisse["id"])


class Session(Caisse):
    def test_une_caisse_s_ouvre_avec_son_fond(self):
        self.assertEqual(self.caisse["ref"], "CAI-000001")
        c = self.etat()["caisse"]
        self.assertEqual((c["etat"], c["fond"], c["appareil"]), ("ouverte", 10000, "K1"))

    def test_deux_caisses_ne_s_ouvrent_pas_sur_le_meme_appareil(self):
        self.assertIn("déjà ouverte", self.echec("caisse_ouvrir", evenement_id=self.e["id"], caissier="Autre", appareil="K1"))
        self.ok("caisse_ouvrir", evenement_id=self.e["id"], caissier="Autre", appareil="K2")

    def test_on_n_ouvre_pas_la_caisse_d_un_evenement_qui_n_est_pas_en_vente(self):
        b = self.evenement(nom="Brouillon", salle_id=self.salle_id)
        self.assertIn("pas en vente", self.echec("caisse_ouvrir", evenement_id=b["id"], caissier="X"))

    def test_ouvrir_se_defait_tant_qu_elle_n_a_rien_vendu(self):
        res = self.ex("caisse_ouvrir", evenement_id=self.e["id"], caissier="Autre", appareil="K2")["resultat"]
        self.defaire("caisse_ouvrir", res)
        self.assertEqual([c["appareil"] for c in self.ok("caisses", etat="ouverte")["caisses"]], ["K1"])
        self.vente(1)
        with self.assertRaises(ValueError):
            self.defaire("caisse_ouvrir", self.caisse)


class Ventes_(Caisse):
    def test_une_vente_en_especes_rend_la_monnaie(self):
        v = self.vente(2, recu=5000)
        self.assertEqual((v["total"], v["recu"], v["rendu"], len(v["numeros"])), (3000, 5000, 2000, 2))
        self.assertEqual(self.stock()["vendus"], 2)

    def test_le_montant_recu_ne_peut_pas_etre_inferieur_au_total(self):
        self.assertIn("inférieur", self.echec("caisse_vendre", caisse_id=self.caisse["id"], lignes=[{"type_billet_id": self.plein, "quantite": 2}], moyen="especes", recu=2000))
        self.assertEqual(self.stock()["vendus"], 0)

    def test_la_carte_n_a_ni_recu_ni_rendu(self):
        v = self.vente(1, moyen="carte_terminal", recu=0)
        self.assertEqual((v["recu"], v["rendu"]), (0, 0))
        self.assertEqual(self.vente(1, moyen="carte_declaree", recu=0)["moyen"], "carte_declaree")

    def test_un_moyen_inconnu_est_refuse(self):
        self.assertIn("moyen", self.echec("caisse_vendre", caisse_id=self.caisse["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], moyen="cheque"))

    def test_une_vente_en_caisse_ne_rapporte_aucune_commission(self):
        fc = self.formule()
        rev = self.ok("revendeur_save", nom="Léa Martin")
        self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=rev["id"], formule_id=fc["id"])
        self.vente(3)
        self.assertEqual(self.ok("portefeuille", porteur="revendeur", porteur_id=rev["id"], au="2099-01-01")["du"], 0)

    def test_le_code_promo_s_applique_en_caisse(self):
        self.ok("promo_save", code="amis", type="pct", valeur=50)
        v = self.vente(2, code_promo="AMIS", recu=1500)
        self.assertEqual(v["total"], 1500)

    def test_les_totaux_de_la_session(self):
        self.vente(2, recu=3000)
        self.vente(1, moyen="carte_terminal", recu=0)
        self.vente(1, moyen="carte_declaree", recu=0)
        t = self.etat()["totaux"]
        self.assertEqual((t["total"], t["billets"], t["attendu_especes"], t["a_rapprocher"]), (6000, 4, 10000 + 3000, 1500))
        self.assertEqual(t["par_moyen"]["carte_terminal"], 1500)

    def test_annuler_une_vente_la_rembourse_et_retire_les_numeros(self):
        res = self.ex("caisse_vendre", caisse_id=self.caisse["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], moyen="especes", recu=1500)["resultat"]
        self.defaire("caisse_vendre", res)
        self.assertEqual(self.stock()["vendus"], 0)

    def test_un_remboursement_en_especes_sort_du_tiroir_attendu(self):
        v = self.vente(1, recu=1500)
        self.ok("commande_rembourser", ref=v["ref"])
        t = self.etat()["totaux"]
        self.assertEqual((t["remboursees"], t["especes_rendues_par_remboursement"]), (1, 1500))
        z = self.ok("caisse_cloturer", caisse_id=self.caisse["id"], compte_especes=10000)
        self.assertEqual((z["attendu"], z["ecart"]), (10000, 0))


class Cloture(Caisse):
    def test_la_cloture_compte_l_ecart_et_se_numerote(self):
        self.vente(2, recu=3000)
        z = self.ok("caisse_cloturer", caisse_id=self.caisse["id"], compte_especes=13050)
        self.assertEqual((z["z"], z["attendu"], z["ecart"]), ("Z-000001", 13000, 50))
        self.assertEqual(self.etat()["caisse"]["etat"], "fermee")

    def test_les_numeros_de_cloture_se_suivent_sans_trou(self):
        self.ok("caisse_cloturer", caisse_id=self.caisse["id"], compte_especes=10000)
        b = self.ok("caisse_ouvrir", evenement_id=self.e["id"], caissier="Autre", appareil="K2")
        self.assertEqual(self.ok("caisse_cloturer", caisse_id=b["id"], compte_especes=0)["z"], "Z-000002")

    def test_on_ne_vend_plus_sur_une_caisse_cloturee_ni_ne_la_cloture_deux_fois(self):
        self.ok("caisse_cloturer", caisse_id=self.caisse["id"], compte_especes=10000)
        self.assertIn("clôturée", self.echec("caisse_vendre", caisse_id=self.caisse["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], moyen="especes", recu=1500))
        self.assertIn("clôturée", self.echec("caisse_cloturer", caisse_id=self.caisse["id"], compte_especes=10000))

    def test_rouvrir_une_caisse_ne_rend_pas_le_numero_de_cloture(self):
        res = self.ex("caisse_cloturer", caisse_id=self.caisse["id"], compte_especes=10000)["resultat"]
        self.defaire("caisse_cloturer", res)
        self.assertEqual(self.etat()["caisse"]["etat"], "ouverte")
        self.assertEqual(self.ok("caisse_cloturer", caisse_id=self.caisse["id"], compte_especes=10000)["z"], "Z-000002")


class Reserve(Caisse):
    def numeros(self):
        return self.ok("caisse_reserver", caisse_id=self.caisse["id"])["numeros"]

    def test_la_reserve_donne_dix_numeros_signes(self):
        n = self.numeros()
        self.assertEqual((len(n), n[0]["numero"], n[9]["numero"]), (10, "A-0001", "A-0010"))
        k = self.mod.CN_billets.cle(self.ctx, self.ctx.stockage)
        lu = self.mod.CN_billets.lire(n[0]["qr"])
        self.assertTrue(self.mod.CN_billets.authentique(k, lu["numero"], 0, lu["signature"]))
        self.assertEqual(self.etat()["reserve_libre"], 10)

    def test_les_numeros_reserves_ne_sont_jamais_donnes_a_une_autre_vente(self):
        self.numeros()
        v = self.vente(1)                                           # une vente EN LIGNE prend la suite
        self.assertEqual(v["numeros"], ["A-0011"])

    def test_vendre_sans_reseau_avec_les_numeros_reserves(self):
        n = self.numeros()
        v = self.ok("caisse_vendre", caisse_id=self.caisse["id"], lignes=[{"type_billet_id": self.plein, "quantite": 2}], moyen="especes", recu=3000,
                    numeros=[n[0]["numero"], n[1]["numero"]], hors_ligne=True)
        self.assertEqual(v["numeros"], ["A-0001", "A-0002"])
        b = self.ok("billet", numero="A-0001")
        self.assertEqual(b["code_controle"], n[0]["code_controle"])            # le QR imprimé hors ligne est celui que le serveur reconnaît
        self.assertEqual(self.etat()["reserve_libre"], 8)

    def test_un_numero_hors_reserve_ou_deja_vendu_est_refuse(self):
        n = self.numeros()
        L = [{"type_billet_id": self.plein, "quantite": 1}]
        self.assertIn("réserve", self.echec("caisse_vendre", caisse_id=self.caisse["id"], lignes=L, moyen="especes", recu=1500, numeros=["A-0099"], hors_ligne=True))
        self.ok("caisse_vendre", caisse_id=self.caisse["id"], lignes=L, moyen="especes", recu=1500, numeros=[n[0]["numero"]], hors_ligne=True)
        self.assertIn("réserve", self.echec("caisse_vendre", caisse_id=self.caisse["id"], lignes=L, moyen="especes", recu=1500, numeros=[n[0]["numero"]], hors_ligne=True))
        self.assertIn("numéro(s)", self.echec("caisse_vendre", caisse_id=self.caisse["id"], lignes=L, moyen="especes", recu=1500, numeros=[n[1]["numero"], n[2]["numero"]], hors_ligne=True))

    def test_la_reserve_d_une_autre_caisse_ne_sert_pas(self):
        autre = self.ok("caisse_ouvrir", evenement_id=self.e["id"], caissier="Autre", appareil="K2")
        n = self.ok("caisse_reserver", caisse_id=autre["id"])["numeros"]
        self.assertIn("réserve", self.echec("caisse_vendre", caisse_id=self.caisse["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], moyen="especes", recu=1500,
                                            numeros=[n[0]["numero"]], hors_ligne=True))

    def test_la_cloture_retire_les_numeros_non_utilises_pour_toujours(self):
        n = self.numeros()
        self.ok("caisse_vendre", caisse_id=self.caisse["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], moyen="especes", recu=1500, numeros=[n[0]["numero"]], hors_ligne=True)
        z = self.ok("caisse_cloturer", caisse_id=self.caisse["id"], compte_especes=11500)
        self.assertEqual(z["numeros_retires"], 9)
        b = self.ok("caisse_ouvrir", evenement_id=self.e["id"], caissier="Autre", appareil="K2")
        v = self.ok("caisse_vendre", caisse_id=b["id"], lignes=[{"type_billet_id": self.plein, "quantite": 1}], moyen="especes", recu=1500)
        self.assertEqual(v["numeros"], ["A-0011"])                                # A-0002 à A-0010 ne reviennent jamais

    def test_une_vente_hors_ligne_est_acceptee_meme_si_les_places_sont_reparties(self):
        n = self.numeros()
        self.vendre(10)                                                # la boutique vend les 10 places pendant la coupure
        L = [{"type_billet_id": self.plein, "quantite": 1}]
        self.assertIn("ne reste", self.echec("caisse_vendre", caisse_id=self.caisse["id"], lignes=L, moyen="especes", recu=1500, numeros=[n[0]["numero"]]))
        v = self.ok("caisse_vendre", caisse_id=self.caisse["id"], lignes=L, moyen="especes", recu=1500, numeros=[n[0]["numero"]], hors_ligne=True)
        self.assertEqual(v["numeros"], [n[0]["numero"]])                      # l'argent est pris : la vente est acceptée
        self.assertIn("sur-vente", self.ok("commande", ref=v["ref"])["commande"]["note"])
        self.assertEqual(self.etat()["totaux"]["hors_ligne"], 1)

    def test_reserver_se_defait_et_retire_les_numeros(self):
        res = self.ex("caisse_reserver", caisse_id=self.caisse["id"])["resultat"]
        self.defaire("caisse_reserver", res)
        self.assertEqual(self.etat()["reserve_libre"], 0)
        self.assertEqual(self.vente(1)["numeros"], ["A-0011"])


class Droits(Caisse):
    def test_un_caissier_vend_mais_ne_rembourse_ni_n_arbitre(self):
        caissier = "paul@x.fr"
        self.n.droits.regler_groupe("caisse", "Caisse")
        self.n.droits.regler_membre(caissier, "caisse", True)
        self.n.droits.regler("groupe", "caisse", "billetterie.vendre", "accorde")
        r = self.n.executeur.executer("billetterie.caisse_vendre", "humain", {"caisse_id": self.caisse["id"], "lignes": [{"type_billet_id": self.plein, "quantite": 1}], "moyen": "especes", "recu": 1500}, compte=caissier)
        self.assertEqual(r["statut"], "faite", r)
        for cap, args in (("commande_rembourser", {"ref": r["resultat"]["ref"]}), ("evenement_publier", {"id": 1}), ("controle_etat", {"evenement_id": self.e["id"]})):
            self.assertEqual(self.n.executeur.executer("billetterie." + cap, "humain", args, compte=caissier)["statut"], "refuse", cap)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Caisse, Session, Ventes_, Cloture, Reserve, Droits
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
