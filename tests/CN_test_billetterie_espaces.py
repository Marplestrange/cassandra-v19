# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 5d
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #1309db
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 5d : « Mon espace » du revendeur et de l'artiste (cloisonnement par compte, portefeuille, retrait, un compte pour une seule fiche).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1309db ▼▼▼
"""Bancs de la billetterie, lot 5d : « Mon espace » du revendeur et de l'artiste (cloisonnement par compte, portefeuille, retrait, un compte pour une seule fiche)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_base import BEA      # noqa: E402
from CN_test_billetterie_ventes import Ventes      # noqa: E402

LEA, PAUL, ARTISTE = "lea@x.fr", "paul@x.fr", "nova@x.fr"


class Espaces(Ventes):
    def setUp(self):
        super().setUp()
        n = self.n.droits
        n.regler_groupe("revendeurs", "Revendeurs")
        n.regler("groupe", "revendeurs", "billetterie.revendeur", "accorde")
        n.regler_groupe("artistes", "Artistes")
        n.regler("groupe", "artistes", "billetterie.artiste", "accorde")
        for c in (LEA, PAUL):
            n.regler_membre(c, "revendeurs", True)
        n.regler_membre(ARTISTE, "artistes", True)
        self.fc = self.formule(com=300, palier_n=3, palier_com=500, fixe=1000)
        self.lea = self.lier("revendeur_save", nom="Léa Martin", compte=LEA)
        self.paul = self.lier("revendeur_save", nom="Paul Durand", compte=PAUL)
        self.code_lea = self.ok("revendeur", id=self.lea["id"])["revendeur"]["code"]
        self.code_paul = self.ok("revendeur", id=self.paul["id"])["revendeur"]["code"]
        for r in (self.lea, self.paul):
            self.ok("affectation_save", evenement_id=self.e["id"], revendeur_id=r["id"], formule_id=self.fc["id"], quota=8)

    def lier(self, capacite, **a):
        """Enregistre une fiche AVEC un champ « compte » (le mot « compte » est aussi celui de l'acteur dans les aides : on passe par l'exécuteur)."""
        r = self.n.executeur.executer("billetterie." + capacite, "humain", a, compte=BEA)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def lier_echec(self, capacite, **a):
        r = self.n.executeur.executer("billetterie." + capacite, "humain", a, compte=BEA)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r.get("erreur") or r.get("raison") or ""

    def moi(self, capacite, compte, **a):
        return self.n.executeur.executer("billetterie." + capacite, "humain", a, compte=compte)

    def moi_ok(self, capacite, compte, **a):
        r = self.moi(capacite, compte, **a)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]


class Revendeur(Espaces):
    def test_il_voit_son_code_ses_evenements_et_ses_chiffres(self):
        self.vendre(2, revendeur_code=self.code_lea)
        m = self.moi_ok("mon_revendeur", LEA)
        self.assertEqual((m["nom"], m["code"]), ("Léa Martin", self.code_lea))
        a = m["affectations"][0]
        self.assertEqual((a["vendus"], a["quota"], a["restant"], a["formule"]), (2, 8, 6, "Formule C"))
        self.assertGreater(a["commission"], 0)
        self.assertEqual(m["portefeuille"]["du"], a["commission"])
        self.assertEqual(len(m["ventes"]), 1)

    def test_il_ne_voit_jamais_les_ventes_d_un_autre(self):
        self.vendre(2, revendeur_code=self.code_lea)
        self.vendre(1, revendeur_code=self.code_paul)
        paul = self.moi_ok("mes_ventes", PAUL)["ventes"]
        self.assertEqual([(v["billets"]) for v in paul], [1])
        self.assertNotIn("mail", str(paul))
        self.assertEqual(self.moi_ok("mon_revendeur", PAUL)["portefeuille"]["du"], paul[0]["commission"])        # 3 € + 10 € de fixe, le tout sur la ligne de la commande

    def test_un_compte_sans_fiche_est_refuse_en_clair(self):
        self.n.droits.regler_membre("inconnu@x.fr", "revendeurs", True)
        r = self.moi("mon_revendeur", "inconnu@x.fr")
        self.assertIn("aucune fiche de revendeur", r.get("erreur", ""))

    def test_le_droit_revendeur_n_ouvre_pas_la_gestion(self):
        for cap, args in (("commande_rembourser", {"ref": "CMD-000001"}), ("revendeurs", {}), ("portefeuille", {"porteur": "revendeur", "porteur_id": self.paul["id"]}), ("retrait_valider", {"id": 1})):
            self.assertEqual(self.moi(cap, LEA, **args)["statut"], "refuse", cap)

    def test_un_acteur_sans_le_droit_ne_voit_pas_l_espace(self):
        self.assertEqual(self.moi("mon_revendeur", "intrus@x.fr")["statut"], "refuse")

    def test_il_demande_un_retrait_sur_son_propre_portefeuille(self):
        self.ok("evenement_save", id=self.e["id"], date_iso="2026-01-01")                # événement passé : la commission est retirable
        self.vendre(4, revendeur_code=self.code_lea)                                      # 3 x 3 € + 5 € + 10 € de fixe = 24 €
        du = self.moi_ok("mon_revendeur", LEA)["portefeuille"]["disponible"]
        self.assertEqual(du, 2400)
        r = self.moi_ok("mon_retrait_revendeur", LEA, montant=2000)
        m = self.moi_ok("mon_revendeur", LEA)["portefeuille"]
        self.assertEqual((m["disponible"], m["retraits"][0]["montant"], m["retraits"][0]["etat"]), (du - 2000, 2000, "demandee"))
        self.assertEqual(self.moi_ok("mon_revendeur", PAUL)["portefeuille"]["retraits"], [])
        self.defaire("mon_retrait_revendeur", r)
        self.assertEqual(self.moi_ok("mon_revendeur", LEA)["portefeuille"]["disponible"], du)

    def test_un_retrait_sous_le_seuil_ou_au_dela_du_disponible_est_refuse(self):
        self.ok("evenement_save", id=self.e["id"], date_iso="2026-01-01")
        self.vendre(2, revendeur_code=self.code_lea)
        self.assertIn("minimal", self.moi("mon_retrait_revendeur", LEA, montant=100).get("erreur", ""))
        self.assertIn("retirables", self.moi("mon_retrait_revendeur", LEA, montant=10 ** 7).get("erreur", ""))

    def test_il_ne_choisit_ni_la_fiche_ni_la_date(self):
        r = self.moi("mon_retrait_revendeur", LEA, montant=2500, porteur_id=self.paul["id"], au="2099-01-01")
        self.assertEqual(r["statut"], "echec", r)                              # la capacité n'a ni « porteur_id » ni « au » : on ne choisit ni la fiche ni la date
        self.assertEqual(self.moi_ok("mon_revendeur", PAUL)["portefeuille"]["retraits"], [])


class Artiste(Espaces):
    def setUp(self):
        super().setUp()
        fa = self.ok("formule_save", nom="Artiste A", role="artiste", forfait=8000, com=500)
        self.art = self.lier("artiste_save", scene="Nova", genre="Soul", formule_id=fa["id"], compte=ARTISTE)
        autre = self.ok("artiste_save", scene="Les Marées", genre="Folk", formule_id=fa["id"])
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=autre["id"], duree=45)
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=self.art["id"], duree=30)
        self.ok("evenement_save", id=self.e["id"], debut="20:00", pause=10)

    def test_il_voit_son_passage_avec_son_heure_et_sa_formule(self):
        m = self.moi_ok("mon_artiste", ARTISTE)
        p = m["programme"][0]
        self.assertEqual((m["scene"], p["ordre"], p["sur"], p["heure"], p["duree"]), ("Nova", 2, 2, "20:55", 30))
        self.assertEqual((m["formule"]["nom"], m["formule"]["forfait"], m["vend"]), ("Artiste A", 8000, False))

    def test_il_ne_voit_pas_les_ventes_ni_les_chiffres_des_revendeurs(self):
        self.vendre(2, revendeur_code=self.code_lea)
        m = self.moi_ok("mon_artiste", ARTISTE)
        self.assertNotIn("Léa", str(m))
        self.assertNotIn("vente", m)

    def test_l_artiste_n_entre_pas_dans_l_espace_revendeur(self):
        self.assertEqual(self.moi("mon_revendeur", ARTISTE)["statut"], "refuse")

    def test_l_artiste_qui_vend_voit_ses_ventes_et_son_lien(self):
        fa = self.ok("formule_save", nom="Artiste V", role="artiste", forfait=0, com=500)
        v = self.lier("artiste_save", scene="Solo", genre="Rock", formule_id=fa["id"], vend=1, compte="solo@x.fr")
        self.n.droits.regler_membre("solo@x.fr", "artistes", True)
        rv = self.ok("revendeurs")["revendeurs"]
        code = [x for x in rv if x["nom"] == "Solo"][0]["code"]
        self.ok("passage_save", evenement_id=self.e["id"], artiste_id=v["id"], duree=20)        # un artiste vendeur vend par son passage
        self.vendre(1, revendeur_code=code)
        m = self.moi_ok("mon_artiste", "solo@x.fr")
        self.assertTrue(m["vend"])
        self.assertEqual((m["vente"]["code"], len(m["vente"]["ventes"])), (code, 1))
        self.assertIsNotNone(v)


class UnCompteUneFiche(Espaces):
    def test_un_compte_ne_se_lie_qu_a_une_fiche_de_revendeur(self):
        self.assertIn("déjà lié", self.lier_echec("revendeur_save", nom="Imposteur", compte=LEA))
        self.lier("revendeur_save", id=self.paul["id"], compte="")
        self.lier("revendeur_save", nom="Imposteur", compte=PAUL)

    def test_un_compte_ne_se_lie_qu_a_une_fiche_d_artiste(self):
        self.lier("artiste_save", scene="A", compte="a@x.fr")
        self.assertIn("déjà lié", self.lier_echec("artiste_save", scene="B", compte="a@x.fr"))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Espaces, Revendeur, Artiste, UnCompteUneFiche
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
