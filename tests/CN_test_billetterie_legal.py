# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #b40dd1
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie : les textes légaux de la boutique (publication, version, acceptation obligatoire des conditions de vente, preuve sur la commande, squelette).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b40dd1 ▼▼▼
"""Bancs de la billetterie : les textes légaux de la boutique (publication, version, acceptation obligatoire des conditions de vente, preuve sur la commande, squelette)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_boutique import Boutique      # noqa: E402


class Legal(Boutique):
    def commande(self, **k):
        d = dict(evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="Sophie", mail="sophie@exemple.org", moyen="stripe", ip="203.0.113.7")
        d.update(k)
        return self.pub(("public_commander"), **d)

    def test_sans_conditions_publiees_rien_n_est_exige(self):
        self.assertEqual(self.commande()["statut"], "faite")
        self.assertFalse(any(self.pub_ok("public_evenement", ref=self.eref)["legal"].values()))

    def test_une_page_publiee_se_lit_sans_compte(self):
        self.ok("legal_page_save", cle="mentions", texte="Éditeur : Maison Bohème")
        r = self.pub_ok("public_legal", cle="mentions")
        self.assertEqual((r["titre"], r["texte"], r["version"]), ("Mentions légales", "Éditeur : Maison Bohème", 1))
        self.assertTrue(self.pub_ok("public_evenement", ref=self.eref)["legal"]["mentions"])

    def test_une_page_vide_ou_inconnue_n_est_pas_publiee(self):
        self.assertIn("pas publiée", self.pub_echec("public_legal", cle="cgv"))
        self.assertIn("introuvable", self.pub_echec("public_legal", cle="n-importe-quoi"))

    def test_la_version_monte_a_chaque_changement_et_un_texte_identique_est_refuse(self):
        self.ok("legal_page_save", cle="cgv", texte="v1")
        self.ok("legal_page_save", cle="cgv", texte="v2")
        self.assertEqual(self.pub_ok("public_legal", cle="cgv")["version"], 2)
        self.assertIn("pas changé", self.echec("legal_page_save", cle="cgv", texte="v2"))

    def test_les_conditions_publiees_deviennent_obligatoires_a_la_commande(self):
        self.ok("legal_page_save", cle="cgv", texte="Conditions")
        r = self.commande()
        self.assertEqual(r["statut"], "echec")
        self.assertIn("conditions générales", r["erreur"])
        self.assertEqual(self.stock()["retenus"], 0)                                   # le refus ne retient aucune place
        self.assertEqual(self.commande(cgv=True)["statut"], "faite")

    def test_la_commande_garde_la_version_acceptee(self):
        self.ok("legal_page_save", cle="cgv", texte="v1")
        self.ok("legal_page_save", cle="cgv", texte="v2")
        c = self.commande(cgv=True)["resultat"]
        self.assertEqual(self.ctx.stockage.lire("SELECT cgv_version FROM commandes WHERE ref = ?", (c["commande"],))[0]["cgv_version"], 2)

    def test_defaire_remet_le_texte_et_la_version_d_avant(self):
        self.ok("legal_page_save", cle="cgv", texte="v1")
        r = self.ok("legal_page_save", cle="cgv", texte="v2")
        self.defaire("legal_page_save", r)
        x = self.pub_ok("public_legal", cle="cgv")
        self.assertEqual((x["texte"], x["version"]), ("v1", 1))
        premier = self.ok("legal_page_save", cle="confidentialite", texte="x")
        self.defaire("legal_page_save", premier)
        self.assertIn("pas publiée", self.pub_echec("public_legal", cle="confidentialite"))

    def test_le_squelette_reprend_les_donnees_du_titulaire_et_dit_qu_il_faut_le_relire(self):
        self.n.reglages.poser("billetterie.titulaire_nom", "Maison Bohème", "")
        self.n.reglages.poser("billetterie.titulaire_mail", "contact@exemple.fr", "")
        for cle in ("cgv", "mentions", "confidentialite"):
            t = self.ok("legal_modele", cle=cle)["texte"]
            self.assertIn("SQUELETTE À COMPLÉTER", t)
            self.assertIn("Maison Bohème", t)
            self.assertIn("contact@exemple.fr", t)

    def test_la_liste_dit_ce_qui_est_publie(self):
        self.ok("legal_page_save", cle="cgv", texte="x")
        l = {p["cle"]: p["publiee"] for p in self.ok("legal_pages")["pages"]}
        self.assertEqual(l, {"cgv": True, "mentions": False, "confidentialite": False})

    def test_un_texte_vide_depublie_les_conditions(self):
        self.ok("legal_page_save", cle="cgv", texte="x")
        self.ok("legal_page_save", cle="cgv", texte="")
        self.assertEqual(self.commande()["statut"], "faite")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Legal
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
