# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 2
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #cc9ac6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 2 : le registre en écriture seule, les soldes, la date de disponibilité, les retraits et leur retour arrière.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=cc9ac6 ▼▼▼
"""Bancs de la billetterie, lot 2 : le registre en écriture seule, les soldes, la date de disponibilité, les retraits et leur retour arrière."""
import sqlite3
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_base import Monde      # noqa: E402

import importlib.util as _u                      # noqa: E402


class Registre(Monde):
    def setUp(self):
        super().setUp()
        self.rev = self.ok("revendeur_save", nom="Léa Martin")
        self.db = self.ctx.stockage

    def prov(self, montant, dispo="", **k):
        return self.ok("provision", porteur="revendeur", porteur_id=self.rev["id"], nature=k.pop("nature", "commission"), montant=montant, disponible_le=dispo, **k)

    def solde(self, au="2026-01-20"):
        return self.ok("portefeuille", porteur="revendeur", porteur_id=self.rev["id"], au=au)


class Soldes(Registre):
    def test_le_scenario_de_la_demande_20_billets_a_5_euros_font_100_euros(self):
        for i in range(20):
            self.prov(500, "2026-01-19", note="billet %d" % (i + 1))
        s = self.solde("2026-01-18")
        self.assertEqual((s["disponible"], s["en_attente"], s["du"]), (0, 10000, 10000))
        s = self.solde("2026-01-19")
        self.assertEqual((s["disponible"], s["en_attente"], s["du"]), (10000, 0, 10000))

    def test_une_ligne_sans_date_est_retirable_tout_de_suite(self):
        self.prov(1200)
        self.assertEqual(self.solde("2020-01-01")["disponible"], 1200)

    def test_la_somme_du_registre_est_toujours_disponible_plus_en_attente(self):
        self.prov(500, "2026-01-30")
        self.prov(700)
        self.prov(-200, nature="ajustement")
        s = self.solde("2026-01-20")
        self.assertEqual(s["disponible"] + s["en_attente"], s["du"])
        self.assertEqual(s["du"], 1000)

    def test_un_artiste_a_son_propre_portefeuille(self):
        a = self.ok("artiste_save", scene="Nova")
        self.ok("provision", porteur="artiste", porteur_id=a["id"], nature="forfait", montant=8000, disponible_le="2026-01-19")
        self.assertEqual(self.ok("portefeuille", porteur="artiste", porteur_id=a["id"], au="2026-01-20")["disponible"], 8000)
        self.assertEqual(self.solde()["du"], 0)

    def test_un_porteur_inconnu_est_refuse(self):
        self.assertIn("introuvable", self.echec("provision", porteur="revendeur", porteur_id=999, nature="commission", montant=100))
        self.assertIn("porteur", self.echec("provision", porteur="client", porteur_id=1, nature="commission", montant=100))


class EcritureSeule(Registre):
    def test_le_registre_refuse_toute_retouche_et_tout_effacement(self):
        self.prov(500)
        c = sqlite3.connect(self.db.chemin)
        try:
            with self.assertRaises(sqlite3.DatabaseError) as m:
                c.execute("UPDATE mouvements SET montant = 999999")
            self.assertIn("écriture seule", str(m.exception))
            with self.assertRaises(sqlite3.DatabaseError):
                c.execute("DELETE FROM mouvements")
        finally:
            c.close()
        self.assertEqual(self.solde()["du"], 500)

    def test_defaire_une_provision_ecrit_une_ligne_contraire(self):
        res = self.ok("provision", porteur="revendeur", porteur_id=self.rev["id"], nature="commission", montant=500)
        self.defaire("provision", res)
        lignes = self.ok("mouvements", porteur="revendeur", porteur_id=self.rev["id"])["mouvements"]
        self.assertEqual(sorted(m["montant"] for m in lignes), [-500, 500])
        self.assertEqual(self.solde()["du"], 0)

    def test_defaire_deux_fois_n_ecrit_qu_une_ligne_contraire(self):
        res = self.ok("provision", porteur="revendeur", porteur_id=self.rev["id"], nature="commission", montant=500)
        self.defaire("provision", res)
        self.defaire("provision", res)
        self.assertEqual(self.solde()["du"], 0)

    def test_un_montant_negatif_se_declare_comme_ajustement(self):
        self.assertIn("ajustement", self.echec("provision", porteur="revendeur", porteur_id=self.rev["id"], nature="commission", montant=-100))
        self.assertIn("zéro", self.echec("provision", porteur="revendeur", porteur_id=self.rev["id"], nature="ajustement", montant=0))

    def test_la_meme_cle_n_ecrit_qu_une_ligne(self):
        mod = sys.modules["cassandra_module_billetterie"]          # le nom exact : un préfixe attrape aussi les sous-modules et les modules d'essai
        reg = getattr(mod, "CN_registre")
        with self.db.transaction() as tx:
            a = reg.ecrire(tx, "revendeur", self.rev["id"], "commission", 500, cle="commande:CMD-000001:ligne:1")
            b = reg.ecrire(tx, "revendeur", self.rev["id"], "commission", 500, cle="commande:CMD-000001:ligne:1")
        self.assertEqual(a, b)
        self.assertEqual(self.solde()["du"], 500)


class Retraits(Registre):
    def setUp(self):
        super().setUp()
        self.prov(10000, "2026-01-19")                       # 100 € retirables dès le 19 décembre

    def demander(self, montant, au="2026-01-20"):
        return self.ok("retrait_demander", porteur="revendeur", porteur_id=self.rev["id"], montant=montant, au=au)

    def test_demander_reserve_le_montant_dans_le_portefeuille(self):
        r = self.demander(6000)
        self.assertEqual(r["ref"], "RET-000001")
        s = self.solde()
        self.assertEqual((s["disponible"], s["retraits_en_cours"], s["du"]), (4000, 6000, 4000))

    def test_le_seuil_minimal_du_reglage_s_applique(self):
        self.assertIn("minimal", self.echec("retrait_demander", porteur="revendeur", porteur_id=self.rev["id"], montant=1999, au="2026-01-20"))
        self.demander(2000)

    def test_on_ne_retire_pas_ce_qui_n_est_pas_encore_disponible(self):
        self.assertIn("retirables", self.echec("retrait_demander", porteur="revendeur", porteur_id=self.rev["id"], montant=6000, au="2026-01-18"))

    def test_on_ne_retire_pas_plus_que_ce_qui_reste(self):
        self.demander(9000)
        self.assertIn("retirables", self.echec("retrait_demander", porteur="revendeur", porteur_id=self.rev["id"], montant=2500, au="2026-01-20"))

    def test_le_cycle_demandee_validee_payee(self):
        r = self.demander(6000)
        self.ok("retrait_valider", id=r["id"])
        self.ok("retrait_payer", id=r["id"], reference_virement="VIR-2026-1")
        x = self.ok("retraits", etat="payee")["retraits"][0]
        self.assertEqual((x["etat"], x["reference_virement"]), ("payee", "VIR-2026-1"))
        s = self.solde()
        self.assertEqual((s["retraits_en_cours"], s["verse"], s["du"]), (0, 6000, 4000))

    def test_on_ne_paie_pas_ce_qui_n_est_pas_valide(self):
        r = self.demander(6000)
        self.assertIn("validée", self.echec("retrait_payer", id=r["id"]))

    def test_refuser_rend_le_montant_au_portefeuille_par_une_ligne_contraire(self):
        r = self.demander(6000)
        self.ok("retrait_refuser", id=r["id"], motif="IBAN à vérifier")
        s = self.solde()
        self.assertEqual((s["disponible"], s["retraits_en_cours"], s["du"]), (10000, 0, 10000))
        natures = [m["nature"] for m in self.ok("mouvements", porteur="revendeur", porteur_id=self.rev["id"])["mouvements"]]
        self.assertEqual(sorted(natures), ["commission", "reprise", "retrait"])

    def test_defaire_une_demande_rend_le_montant(self):
        res = self.ex("retrait_demander", porteur="revendeur", porteur_id=self.rev["id"], montant=6000, au="2026-01-20")["resultat"]
        self.defaire("retrait_demander", res)
        self.assertEqual(self.solde()["disponible"], 10000)
        self.assertEqual(self.ok("retraits")["retraits"][0]["etat"], "refusee")

    def test_defaire_un_refus_rouvre_la_demande_si_le_portefeuille_la_couvre(self):
        r = self.demander(6000)
        res = self.ok("retrait_refuser", id=r["id"])
        self.defaire("retrait_refuser", res)
        self.assertEqual(self.ok("retraits")["retraits"][0]["etat"], "demandee")
        s = self.solde()
        self.assertEqual((s["disponible"], s["retraits_en_cours"]), (4000, 6000))

    def test_valider_se_defait(self):
        r = self.demander(6000)
        res = self.ok("retrait_valider", id=r["id"])
        self.defaire("retrait_valider", res)
        self.assertEqual(self.ok("retraits")["retraits"][0]["etat"], "demandee")

    def test_un_revendeur_suspendu_ne_retire_pas(self):
        self.ok("revendeur_save", id=self.rev["id"], actif=0)
        self.assertIn("suspendu", self.echec("retrait_demander", porteur="revendeur", porteur_id=self.rev["id"], montant=6000, au="2026-01-20"))

    def test_sous_le_seuil_par_defaut_de_20_euros_un_retrait_est_refuse(self):
        self.assertIn("minimal", self.echec("retrait_demander", porteur="revendeur", porteur_id=self.rev["id"], montant=1000, au="2026-01-20"))


class DisponibiliteApresEvenement(unittest.TestCase):
    def test_le_delai_se_compte_depuis_le_jour_de_l_evenement(self):
        racine = Path(__file__).resolve().parent.parent / "modules" / "billetterie"
        sp = _u.spec_from_file_location("cassandra_module_billetterie_essai", racine / "CN_module.py", submodule_search_locations=[str(racine)])
        mod = _u.module_from_spec(sp)
        sys.modules["cassandra_module_billetterie_essai"] = mod
        try:
            sp.loader.exec_module(mod)
            reg = mod.CN_registre
            self.assertEqual(reg.disponible_apres("2026-12-12", 7), "2026-12-19")
            self.assertEqual(reg.disponible_apres("2026-12-28", 7), "2027-01-04")
            self.assertEqual(reg.disponible_apres("", 7), "")
        finally:
            sys.modules.pop("cassandra_module_billetterie_essai", None)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Registre, Soldes, EcritureSeule, Retraits, DisponibiliteApresEvenement
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
