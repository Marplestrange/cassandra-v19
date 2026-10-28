# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 7
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #c81999
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 7 : les comptes clients (lien de connexion, session, mon espace, achat avec compte, export, suppression différée, cloisonnement).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c81999 ▼▼▼
"""Bancs de la billetterie, lot 7 : les comptes clients (lien de connexion, session, mon espace, achat avec compte, export, suppression différée, cloisonnement)."""
import re
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_boutique import Boutique      # noqa: E402


class Comptes(Boutique):
    def setUp(self):
        super().setUp()
        self.cl = self.mod.CN_clients

    def lien_pour(self, mail="sophie@exemple.org"):
        self.pub_ok("public_compte_lien", mail=mail, ip="203.0.113.50")
        c = [x for x in self.ok("courriels")["courriels"] if x["a"] == mail and "lien de connexion" in x["objet"]][-1]
        return re.search(r"#/compte\?t=([A-Za-z0-9_\-]+)", c["corps"]).group(1)

    def session(self, mail="sophie@exemple.org"):
        return self.pub_ok("public_compte_ouvrir", jeton=self.lien_pour(mail))["session"]

    def commande_payee(self, mail, session="", n=1, **k):
        c = self.commander(n, mail=mail, nom="Sophie Marchand", session=session, ip="203.0.113.%d" % (60 + len(mail)), **k)
        self.ok("commande_encaisser", ref=c["commande"], moyen="stripe", reference_externe="pi_" + c["commande"])
        return c


class Connexion(Comptes):
    def test_le_lien_est_envoye_par_courriel_et_ne_se_garde_qu_en_empreinte(self):
        jeton = self.lien_pour()
        lignes = self.ctx.stockage.lire("SELECT empreinte FROM liens_connexion")
        self.assertEqual(len(lignes), 1)
        self.assertNotIn(jeton, lignes[0]["empreinte"])
        self.assertEqual(lignes[0]["empreinte"], self.mod.CN_ventes.empreinte(jeton))

    def test_la_reponse_est_la_meme_que_le_compte_existe_ou_non(self):
        self.commande_payee("connu@exemple.org")
        a = self.pub_ok("public_compte_lien", mail="connu@exemple.org", ip="203.0.113.1")
        b = self.pub_ok("public_compte_lien", mail="inconnu@exemple.org", ip="203.0.113.2")
        self.assertEqual(sorted(a.keys()), sorted(b.keys()))
        self.assertTrue(a["ok"] and b["ok"])

    def test_un_lien_ouvre_une_session_une_seule_fois(self):
        jeton = self.lien_pour()
        r = self.pub_ok("public_compte_ouvrir", jeton=jeton)
        self.assertTrue(r["session"])
        self.assertIn("plus valable", self.pub_echec("public_compte_ouvrir", jeton=jeton))

    def test_un_lien_perime_ou_faux_est_refuse(self):
        jeton = self.lien_pour()
        self.avance(16 * 60)
        self.assertIn("plus valable", self.pub_echec("public_compte_ouvrir", jeton=jeton))
        self.assertIn("plus valable", self.pub_echec("public_compte_ouvrir", jeton="n-importe-quoi"))

    def test_la_session_expire_au_bout_de_trente_jours(self):
        s = self.session()
        self.pub_ok("public_compte_moi", session=s)
        self.avance(31 * 24 * 3600)
        self.assertIn("expiré", self.pub_echec("public_compte_moi", session=s))

    def test_se_deconnecter_ferme_la_session(self):
        s = self.session()
        self.pub_ok("public_compte_fermer", session=s)
        self.assertIn("expiré", self.pub_echec("public_compte_moi", session=s))

    def test_trop_de_demandes_de_lien_sont_refusees(self):
        for i in range(4):
            self.pub_ok("public_compte_lien", mail="abus@exemple.org", ip="203.0.113.%d" % (100 + i))
        self.assertIn("trop de demandes", self.pub_echec("public_compte_lien", mail="abus@exemple.org", ip="203.0.113.150"))

    def test_defaire_l_ouverture_supprime_la_session(self):
        r = self.pub_ok("public_compte_ouvrir", jeton=self.lien_pour())
        self.defaire("public_compte_ouvrir", r)
        self.assertIn("expiré", self.pub_echec("public_compte_moi", session=r["session"]))


class MonEspace(Comptes):
    def test_il_retrouve_ses_commandes_et_jamais_celles_d_un_autre(self):
        self.commande_payee("sophie@exemple.org")
        self.commande_payee("autre@exemple.org")
        m = self.pub_ok("public_compte_moi", session=self.session("sophie@exemple.org"))
        self.assertEqual(len(m["commandes"]), 1)
        self.assertEqual(m["mail"], "sophie@exemple.org")

    def test_les_achats_faits_sans_compte_avec_le_meme_courriel_apparaissent_apres_la_creation_du_compte(self):
        c = self.commande_payee("sophie@exemple.org")
        m = self.pub_ok("public_compte_moi", session=self.session())
        self.assertEqual(m["commandes"][0]["commande"], c["commande"])
        self.pub_ok("public_suivre", commande=c["commande"], suivi=m["commandes"][0]["suivi"])

    def test_modifier_son_nom_et_le_defaire(self):
        s = self.session()
        r = self.pub_ok("public_compte_modifier", session=s, nom="Sophie M.", tel="0600000000", consentement=True)
        m = self.pub_ok("public_compte_moi", session=s)
        self.assertEqual((m["nom"], m["consentement"]), ("Sophie M.", True))
        self.defaire("public_compte_modifier", r)
        self.assertEqual(self.pub_ok("public_compte_moi", session=s)["nom"], "")

    def test_l_export_contient_tout(self):
        c = self.commande_payee("sophie@exemple.org", don=500)
        x = self.pub_ok("public_compte_exporter", session=self.session())
        self.assertEqual(x["client"]["mail"], "sophie@exemple.org")
        self.assertEqual([k["ref"] for k in x["commandes"]], [c["commande"]])
        self.assertEqual(len(x["billets"]), 1)
        self.assertTrue(x["courriels"])


class AchatAvecCompte(Comptes):
    def setUp(self):
        super().setUp()
        self.n.reglages.poser("billetterie.frais_sans_compte", 200, "")

    def test_sans_compte_les_frais_s_ajoutent_avec_compte_non(self):
        s = self.session()
        l = [{"type": self.tp, "quantite": 1}]
        self.assertEqual(self.pub_ok("public_panier", evenement=self.eref, lignes=l)["total"], 1700)
        self.assertEqual(self.pub_ok("public_panier", evenement=self.eref, lignes=l, session=s)["total"], 1500)

    def test_le_parametre_sans_compte_n_est_pas_cru(self):
        l = [{"type": self.tp, "quantite": 1}]
        self.assertEqual(self.pub_ok("public_panier", evenement=self.eref, lignes=l, sans_compte=False)["total"], 1700)

    def test_avec_compte_le_courriel_et_le_nom_viennent_du_compte(self):
        s = self.session("sophie@exemple.org")
        self.pub_ok("public_compte_modifier", session=s, nom="Sophie Marchand", tel="", consentement=False)
        c = self.pub_ok("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="Usurpateur", mail="victime@exemple.org", moyen="stripe", session=s, ip="203.0.113.77")
        cmd = self.ok("commande", ref=c["commande"])["commande"]
        self.assertEqual((cmd["mail"], cmd["total"]), ("sophie@exemple.org", 1500))

    def test_un_evenement_qui_exige_un_compte_refuse_sans_session_et_accepte_avec(self):
        self.ok("evenement_save", id=self.e["id"], achat="obligatoire")
        l = [{"type": self.tp, "quantite": 1}]
        self.assertIn("compte", self.pub_echec("public_commander", evenement=self.eref, lignes=l, nom="X", mail="x@exemple.org", moyen="stripe", sans_compte=False, ip="203.0.113.81"))
        s = self.session()
        self.pub_ok("public_commander", evenement=self.eref, lignes=l, nom="Sophie", mail="", moyen="stripe", session=s, ip="203.0.113.82")
        self.assertEqual(self.pub_ok("public_compte_moi", session=s)["nom"], "Sophie")        # la première commande donne son nom au compte

    def test_une_session_perimee_n_achete_pas_en_silence_sans_compte(self):
        s = self.session()
        self.avance(31 * 24 * 3600)
        self.assertIn("expiré", self.pub_echec("public_commander", evenement=self.eref, lignes=[{"type": self.tp, "quantite": 1}], nom="X", mail="x@exemple.org", moyen="stripe", session=s, ip="203.0.113.83"))


class Suppression(Comptes):
    def test_la_suppression_est_differee_et_se_defait(self):
        s = self.session()
        r = self.pub_ok("public_compte_supprimer", session=s)
        self.assertGreater(r["effacement_le"], self.t[0] + 6 * 24 * 3600)
        self.assertEqual(self.pub_ok("public_compte_moi", session=s)["suppression_le"], r["effacement_le"])
        self.pub_ok("public_compte_annuler_suppression", session=s)
        self.assertEqual(self.pub_ok("public_compte_moi", session=s)["suppression_le"], 0)

    def test_avant_le_delai_rien_n_est_efface(self):
        c = self.commande_payee("sophie@exemple.org")
        self.pub_ok("public_compte_supprimer", session=self.session())
        self.avance(3 * 24 * 3600)
        with self.ctx.stockage.transaction() as tx:
            self.assertEqual(self.cl.effacer_echus(tx), 0)
        self.assertEqual(self.ok("commande", ref=c["commande"])["commande"]["nom"], "Sophie Marchand")

    def test_apres_le_delai_les_donnees_personnelles_partent_les_montants_et_les_recus_restent(self):
        c = self.commande_payee("sophie@exemple.org", don=500)
        for cle, val in (("dons_eligible", True), ("dons_base_legale", "art. 200 CGI"), ("titulaire_nom", "Maison Bohème"), ("titulaire_adresse", "3 quai des Arts, Nantes")):
            self.n.reglages.poser("billetterie." + cle, val, "")
        self.pub_ok("public_recu_demander", commande=c["commande"], suivi=c["suivi"], adresse="12 rue des Lilas, 44000 Nantes")
        s = self.session()
        self.pub_ok("public_compte_supprimer", session=s)
        self.avance(8 * 24 * 3600)
        with self.ctx.stockage.transaction() as tx:
            self.assertEqual(self.cl.effacer_echus(tx), 1)
        cmd = self.ok("commande", ref=c["commande"])["commande"]
        self.assertEqual((cmd["nom"], cmd["mail"], cmd["total"], cmd["etat"]), ("", "", 1500 + 500, "payee"))
        self.assertEqual([b["nom"] + b["mail"] for b in self.ok("billets", evenement_id=self.e["id"])["billets"] if b["commande_id"] == cmd["id"]], [""])
        self.assertEqual(self.ok("recus_fiscaux")["recus"][0]["etat"], "emis")
        self.assertIn("expiré", self.pub_echec("public_compte_moi", session=s))
        self.assertEqual([x for x in self.ok("courriels")["courriels"] if x["a"] == "sophie@exemple.org"], [])

    def test_le_meme_courriel_peut_recreer_un_compte_neuf_apres_l_effacement(self):
        self.commande_payee("sophie@exemple.org")
        self.pub_ok("public_compte_supprimer", session=self.session())
        self.avance(8 * 24 * 3600)
        with self.ctx.stockage.transaction() as tx:
            self.cl.effacer_echus(tx)
        m = self.pub_ok("public_compte_moi", session=self.session())
        self.assertEqual(m["commandes"], [])

    def test_le_titulaire_lit_les_clients_exporte_un_dossier_et_programme_un_effacement(self):
        self.commande_payee("sophie@exemple.org")
        cl = self.ok("clients")["clients"]
        self.assertEqual([(x["mail"], x["commandes"]) for x in cl], [("sophie@exemple.org", 1)])
        d = self.ok("client_dossier", id=cl[0]["id"])
        self.assertEqual(len(d["commandes"]), 1)
        r = self.ok("client_effacement", id=cl[0]["id"])
        self.assertGreater(r["effacement_le"], 0)
        self.defaire("client_effacement", r)
        self.assertEqual(self.ok("clients")["clients"][0]["suppression_le"], 0)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Comptes, Connexion, MonEspace, AchatAvecCompte, Suppression
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
