# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la billetterie, lot 4a
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #e053b5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la billetterie, lot 4a : le contrôle à l'entrée (signature, portes, entrées multiples, retour arrière, hors ligne, conflits).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e053b5 ▼▼▼
"""Bancs de la billetterie, lot 4a : le contrôle à l'entrée (signature, portes, entrées multiples, retour arrière, hors ligne, conflits)."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
from CN_test_billetterie_ventes import Ventes      # noqa: E402


class Controle(Ventes):
    def setUp(self):
        super().setUp()
        self.k = self.mod.CN_billets.cle(self.ctx, self.ctx.stockage)

    def billet(self, numero):
        return self.ok("billet", numero=numero)

    def passer(self, texte, **k):
        d = dict(evenement_id=self.e["id"], texte=texte, porte="Entrée principale")
        d.update(k)
        return self.ok("controler", **d)

    def un_billet(self, **k):
        c = self.vendre(1, **k)
        return self.billet(c["numeros"][0])


class Authenticite(Controle):
    def test_un_qr_authentique_laisse_entrer_une_fois(self):
        b = self.un_billet()
        r1 = self.passer(b["qr"])
        self.assertEqual((r1["niveau"], r1["titre"], r1["entre"]), ("ok", "Entrée autorisée", True))
        self.assertIn("Sophie Marchand", r1["detail"])
        r2 = self.passer(b["qr"])
        self.assertEqual((r2["niveau"], r2["titre"]), ("ko", "Déjà utilisé"))
        self.assertIn("Entrée principale", r2["detail"])

    def test_le_numero_de_controle_saisi_vaut_le_qr(self):
        b = self.un_billet()
        r = self.passer(b["code_controle"])
        self.assertEqual((r["niveau"], r["detail"].endswith("numéro")), ("ok", False))

    def test_un_qr_falsifie_est_refuse(self):
        b = self.un_billet()
        r = self.passer("CASS1.%s.AAAAAA" % b["billet"]["numero"])
        self.assertEqual((r["niveau"], r["titre"]), ("ko", "Billet invalide"))
        self.assertEqual(self.billet(b["billet"]["numero"])["billet"]["entrees_faites"], 0)

    def test_un_numero_de_controle_faux_est_refuse(self):
        b = self.un_billet()
        r = self.passer(b["billet"]["numero"] + "-AAAAAA")
        self.assertEqual((r["niveau"], r["titre"]), ("ko", "Numéro de contrôle incorrect"))

    def test_un_numero_incomplet_demande_le_numero_entier(self):
        b = self.un_billet()
        r = self.passer(b["billet"]["numero"])
        self.assertEqual((r["niveau"], r["titre"]), ("warn", "Numéro incomplet"))

    def test_la_validation_a_la_main_accepte_le_numero_nu(self):
        b = self.un_billet()
        r = self.passer(b["billet"]["numero"], manuel=True)
        self.assertEqual(r["niveau"], "ok")
        self.assertIn("à la main", r["detail"])

    def test_un_numero_inconnu_est_refuse(self):
        self.assertEqual(self.passer("Z-9999", manuel=True)["niveau"], "ko")
        self.assertEqual(self.passer("")["titre"], "Aucun code lu")

    def test_un_billet_reemis_invalide_l_ancien_qr(self):
        b = self.un_billet()
        self.ok("billet_reemettre", numero=b["billet"]["numero"])
        self.assertEqual(self.passer(b["qr"])["titre"], "Billet invalide")
        self.assertEqual(self.passer(self.billet(b["billet"]["numero"])["qr"])["niveau"], "ok")

    def test_un_billet_rembourse_ne_passe_plus(self):
        c = self.vendre(1)
        b = self.billet(c["numeros"][0])
        self.ok("commande_rembourser", ref=c["ref"])
        self.assertEqual(self.passer(b["qr"])["titre"], "Billet annulé")

    def test_un_billet_d_un_autre_evenement_previent(self):
        b = self.un_billet()
        autre = self.evenement(nom="Autre", salle_id=self.salle_id, quota=5)
        r = self.ok("controler", evenement_id=autre["id"], texte=b["qr"], porte="Entrée principale")
        self.assertEqual((r["niveau"], r["titre"]), ("warn", "Autre événement"))


class Entrees(Controle):
    def test_un_pack_duo_donne_deux_entrees(self):
        self.ok("type_billet_save", id=self.reduit, entrees=2)
        c = self.acheter([{"type_billet_id": self.reduit, "quantite": 1}], encaisser=True, moyen="especes")
        b = self.billet(c["numeros"][0])
        r1 = self.passer(b["qr"])
        self.assertIn("entrée 1 sur 2", r1["detail"])
        self.assertEqual(self.passer(b["qr"])["niveau"], "ok")
        self.assertEqual(self.passer(b["qr"])["niveau"], "ko")

    def test_annuler_une_entree_la_rend_au_billet(self):
        b = self.un_billet()
        res = self.ex("controler", evenement_id=self.e["id"], texte=b["qr"], porte="Entrée principale")["resultat"]
        self.assertEqual(self.passer(b["qr"])["niveau"], "ko")
        self.defaire("controler", res)
        self.assertEqual(self.passer(b["qr"])["niveau"], "ok")
        entrees = [x for x in self.ok("controle_etat", evenement_id=self.e["id"])["derniers"] if x["annule"]]
        self.assertEqual(len(entrees), 1)                        # la ligne du journal reste, marquée annulée

    def test_un_refus_se_defait_sans_rien_changer(self):
        b = self.un_billet()
        self.passer(b["qr"])
        res = self.ex("controler", evenement_id=self.e["id"], texte=b["qr"], porte="Entrée principale")["resultat"]
        self.assertEqual(res["niveau"], "ko")
        self.defaire("controler", res)
        self.assertEqual(self.billet(b["billet"]["numero"])["billet"]["entrees_faites"], 1)

    def test_les_compteurs_de_l_ouvreur(self):
        a, b = self.un_billet(), self.un_billet()
        self.ok("invitation_save", evenement_id=self.e["id"], categorie="Presse", quota=1)
        self.ok("invitation_emettre", evenement_id=self.e["id"], categorie="Presse", nom="Journaliste")
        self.passer(a["qr"])
        self.passer("CASS1.%s.BBBBBB" % b["billet"]["numero"])           # refusé
        etat = self.ok("controle_etat", evenement_id=self.e["id"])
        self.assertEqual((etat["entrees"], etat["attendus"], etat["restants"], etat["refuses"]), (1, 3, 2, 1))

    def test_chercher_un_billet_par_nom(self):
        self.un_billet()
        self.assertEqual(self.ok("controle_chercher", evenement_id=self.e["id"], q="Marchand")["billets"][0]["nom"], "Sophie Marchand")
        self.assertEqual(self.ok("controle_chercher", evenement_id=self.e["id"], q="S")["billets"], [])


class HorsLigne(Controle):
    def test_regle_portes_chaque_categorie_a_sa_porte(self):
        self.ok("type_billet_save", id=self.reduit, porte="Porte latérale")
        plein = self.un_billet()
        c = self.acheter([{"type_billet_id": self.reduit, "quantite": 1}], encaisser=True, moyen="especes")
        reduit = self.billet(c["numeros"][0])
        r = self.passer(plein["qr"], hors_ligne=True, porte="Porte latérale")
        self.assertEqual((r["niveau"], r["titre"]), ("warn", "Mauvaise porte"))
        self.assertEqual(self.passer(plein["qr"], hors_ligne=True, porte="Entrée principale")["niveau"], "ok")
        self.assertEqual(self.passer(reduit["qr"], hors_ligne=True, porte="Porte latérale")["niveau"], "ok")

    def test_regle_portes_n_agit_pas_en_ligne(self):
        b = self.un_billet()
        self.assertEqual(self.passer(b["qr"], hors_ligne=False, porte="Backstage")["niveau"], "ok")

    def test_regle_secours_pas_de_controle_hors_ligne(self):
        self.n.reglages.poser("billetterie.regle_hors_ligne", "secours", "")
        b = self.un_billet()
        r = self.passer(b["qr"], hors_ligne=True)
        self.assertEqual((r["niveau"], r["titre"]), ("warn", "Contrôle hors ligne désactivé"))
        self.assertEqual(self.billet(b["billet"]["numero"])["billet"]["entrees_faites"], 0)

    def test_regle_signaler_laisse_tout_passer(self):
        self.n.reglages.poser("billetterie.regle_hors_ligne", "signaler", "")
        b = self.un_billet()
        self.assertEqual(self.passer(b["qr"], hors_ligne=True, porte="Backstage")["niveau"], "ok")

    def test_les_invitations_ont_leur_porte(self):
        self.ok("invitation_save", evenement_id=self.e["id"], categorie="Presse", quota=1, porte="Backstage")
        res = self.ok("invitation_emettre", evenement_id=self.e["id"], categorie="Presse", nom="Journaliste")
        b = self.billet(res["numero"])
        self.assertEqual(self.passer(b["qr"], hors_ligne=True, porte="Entrée principale")["titre"], "Mauvaise porte")
        self.assertEqual(self.passer(b["qr"], hors_ligne=True, porte="Backstage")["niveau"], "ok")

    def test_le_telechargement_hors_ligne_donne_de_quoi_reconnaitre_chaque_billet(self):
        b = self.un_billet()
        liste = self.ok("controle_liste", evenement_id=self.e["id"])
        self.assertEqual(liste["regle"], "portes")
        x = liste["billets"][0]
        self.assertEqual((x["numero"], x["porte"], x["entrees"]), (b["billet"]["numero"], "Entrée principale", 1))
        self.assertTrue(b["code_controle"].endswith(x["signature"]))


class Conflits(Controle):
    def test_un_billet_vu_a_deux_portes_pendant_la_coupure_devient_un_conflit(self):
        b = self.un_billet()
        n = b["billet"]["numero"]
        res = self.ok("controle_synchroniser", evenement_id=self.e["id"], entrees=[
            {"numero": n, "porte": "Porte latérale", "heure_appareil": "2026-12-12T20:14:00"},
            {"numero": n, "porte": "Entrée principale", "heure_appareil": "2026-12-12T20:12:00"}])
        self.assertEqual((res["appliquees"], res["conflits"]), (1, 1))
        c = self.ok("conflits", etat="a_arbitrer")["conflits"][0]
        self.assertEqual((c["porte1"], c["porte2"], c["heure1"], c["heure2"]), ("Entrée principale", "Porte latérale", "2026-12-12T20:12:00", "2026-12-12T20:14:00"))
        self.assertEqual(self.ok("controle_etat", evenement_id=self.e["id"])["conflits_a_arbitrer"], 1)

    def test_bloquer_le_billet_l_annule_et_se_defait(self):
        b = self.un_billet()
        n = b["billet"]["numero"]
        self.ok("controle_synchroniser", evenement_id=self.e["id"], entrees=[{"numero": n, "porte": "A", "heure_appareil": "1"}, {"numero": n, "porte": "B", "heure_appareil": "2"}])
        cid = self.ok("conflits")["conflits"][0]["id"]
        res = self.ok("conflit_arbitrer", id=cid, decision="bloquer")
        self.assertEqual(self.billet(n)["billet"]["etat"], "annule")
        self.assertIn("déjà arbitré", self.echec("conflit_arbitrer", id=cid, decision="accepter"))
        self.defaire("conflit_arbitrer", res)
        self.assertEqual((self.billet(n)["billet"]["etat"], self.ok("conflits")["conflits"][0]["etat"]), ("valide", "a_arbitrer"))

    def test_accepter_laisse_le_billet_valide(self):
        b = self.un_billet()
        n = b["billet"]["numero"]
        self.ok("controle_synchroniser", evenement_id=self.e["id"], entrees=[{"numero": n, "porte": "A", "heure_appareil": "1"}, {"numero": n, "porte": "B", "heure_appareil": "2"}])
        self.ok("conflit_arbitrer", id=self.ok("conflits")["conflits"][0]["id"], decision="accepter")
        self.assertEqual(self.billet(n)["billet"]["etat"], "valide")

    def test_une_decision_inconnue_est_refusee(self):
        self.assertIn("décision", self.echec("conflit_arbitrer", id=1, decision="peut-être"))

    def test_la_synchronisation_refuse_un_billet_inconnu_et_se_defait(self):
        b = self.un_billet()
        n = b["billet"]["numero"]
        res = self.ok("controle_synchroniser", evenement_id=self.e["id"], entrees=[{"numero": "Z-0000", "porte": "A", "heure_appareil": "1"}, {"numero": n, "porte": "A", "heure_appareil": "2"}])
        self.assertEqual((res["appliquees"], res["refusees"]), (1, 1))
        self.defaire("controle_synchroniser", res)
        self.assertEqual(self.billet(n)["billet"]["entrees_faites"], 0)


class Droits(Controle):
    def test_un_ouvreur_a_le_droit_controler_et_rien_d_autre(self):
        ouvreur = "marc@x.fr"
        self.n.droits.regler_groupe("ouvreurs", "Ouvreurs")
        self.n.droits.regler_membre(ouvreur, "ouvreurs", True)
        self.n.droits.regler("groupe", "ouvreurs", "billetterie.controler", "accorde")
        b = self.un_billet()
        r = self.n.executeur.executer("billetterie.controler", "humain", {"evenement_id": self.e["id"], "texte": b["qr"], "porte": "Entrée principale"}, compte=ouvreur)
        self.assertEqual(r["statut"], "faite", r)
        r = self.n.executeur.executer("billetterie.commande_rembourser", "humain", {"ref": "CMD-000001"}, compte=ouvreur)
        self.assertEqual(r["statut"], "refuse", r)
        r = self.n.executeur.executer("billetterie.conflit_arbitrer", "humain", {"id": 1, "decision": "accepter"}, compte=ouvreur)
        self.assertEqual(r["statut"], "refuse", r)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Controle, Authenticite, Entrees, HorsLigne, Conflits, Droits
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
