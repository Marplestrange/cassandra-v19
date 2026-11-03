# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Mon compte, la suite
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #de4d58
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Mon compte, la suite : qui voit ma fiche, les identités liées (FastPanel, système), les appareils (se souvenir, approuver) et « À faire sur mon compte ».
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=de4d58 ▼▼▼
"""Mon compte, la suite : qui voit ma fiche, les identités liées (FastPanel, système), les appareils (se souvenir, approuver) et « À faire sur mon compte »."""
import sys
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from tests.CN_test_fiche import MDP, Monde                  # noqa: E402


class QuiVoitMaFiche(Monde):
    def preparer(self):
        self.creer("root@x.fr")
        self.creer("a@x.fr")
        self.creer("b@x.fr", display_name="Bea Martin")
        self.ex("droits.regler", sujet="a@x.fr", droit="comptes.gerer")                     # lire la fiche d'un autre passe par « gerer »
        self.ex("droits.regler", sujet="root@x.fr", droit="comptes.gerer")
        self.ex("comptes.modifier_moi", au_nom_de="b@x.fr", personal_email="bea@maison.fr", birth="1990-01-02", job="Comptable", office_phone="0102")

    def voir(self, par="a@x.fr"):
        return self.ex("comptes.lire", au_nom_de=par, compte="b@x.fr")["resultat"]["fiche"]

    def test_par_defaut_le_professionnel_se_voit_et_le_prive_jamais(self):
        self.preparer()
        f = self.voir()
        self.assertEqual((f["job"], f["office_phone"]), ("Comptable", "0102"))
        self.assertEqual((f["personal_email"], f["birth"]), ("", ""))
        v = self.ex("comptes.fiche_visibilite", au_nom_de="b@x.fr")["resultat"]
        self.assertEqual(v["groupes"]["perso"], {"collegues": False, "admins": False})
        self.assertTrue(v["journaliser"])

    def test_fermer_un_groupe_le_cache_aux_collegues(self):
        self.preparer()
        r = self.ex("comptes.fiche_visibilite_regler", au_nom_de="b@x.fr", groupe="pro", public="collegues", ouvert=False)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual((self.voir()["job"], self.voir()["office_phone"]), ("Comptable", ""))          # l'identité reste ouverte, le professionnel est fermé
        self.assertEqual(self.voir("root@x.fr")["office_phone"], "0102")                                # les administrateurs ont leur propre colonne

    def test_le_prive_demande_l_ouverture_ET_le_droit(self):
        self.preparer()
        self.ex("comptes.fiche_visibilite_regler", au_nom_de="b@x.fr", groupe="perso", public="collegues", ouvert=True)
        self.assertEqual(self.voir()["personal_email"], "")                                             # ouvert, mais sans le droit
        self.ex("droits.regler", sujet="a@x.fr", droit="comptes.fiche_voir_perso")
        self.assertEqual(self.voir()["personal_email"], "bea@maison.fr")                                # ouvert ET droit
        self.ex("comptes.fiche_visibilite_regler", au_nom_de="b@x.fr", groupe="perso", public="collegues", ouvert=False)
        self.assertEqual(self.voir()["personal_email"], "")                                             # le droit seul ne suffit pas

    def test_un_groupe_ou_un_public_inconnu_est_refuse_et_la_regle_se_defait(self):
        self.preparer()
        self.assertEqual(self.ex("comptes.fiche_visibilite_regler", au_nom_de="b@x.fr", groupe="x", public="admins")["statut"], "echec")
        r = self.ex("comptes.fiche_visibilite_regler", au_nom_de="b@x.fr", groupe="identite", public="admins", ouvert=False)
        self.n.catalogue.get("comptes.fiche_visibilite_regler").defaire(self.n.executeur.contextes["comptes"], r["resultat"])
        self.assertTrue(self.ex("comptes.fiche_visibilite", au_nom_de="b@x.fr")["resultat"]["groupes"]["identite"]["admins"])

    def test_la_journalisation_se_coupe(self):
        self.preparer()
        self.voir()
        vues = lambda: sum(1 for e in self.ex("comptes.mon_journal", au_nom_de="b@x.fr")["resultat"]["evenements"] if e["type"] == "compte.fiche_vue")      # noqa: E731
        self.assertEqual(vues(), 1)
        self.ex("comptes.fiche_visibilite_regler", au_nom_de="b@x.fr", journaliser=False)
        self.voir()
        self.assertEqual(vues(), 1)


class IdentitesLiees(Monde):
    def test_un_administrateur_lie_le_pseudo_fastpanel_et_le_bash_d_un_admin(self):
        self.creer("root@x.fr")
        self.creer("adm@x.fr")
        self.creer("u@x.fr")
        r = self.ex("comptes.identite_lier", compte="u@x.fr", fp_account="marie")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("comptes.identites", au_nom_de="u@x.fr")["resultat"]["fp_account"], "marie")
        self.assertEqual(self.ex("comptes.identite_lier", compte="u@x.fr", fp_account="a b")["statut"], "echec")          # un pseudo propre
        r = self.ex("comptes.identite_lier", compte="u@x.fr", unix_user="marie")
        self.assertEqual(r["statut"], "echec")                                                                           # le bash est réservé aux administrateurs
        self.assertIn("réservé aux administrateurs", r["erreur"])
        vrai = self.n.identite.droits.est_admin
        self.n.identite.droits.est_admin = lambda c: c == "adm@x.fr" or vrai(c)                                         # un administrateur : son bash se lie
        self.assertEqual(self.ex("comptes.identite_lier", compte="adm@x.fr", unix_user="marie")["statut"], "faite")
        self.assertEqual(self.ex("comptes.identites", au_nom_de="adm@x.fr")["resultat"]["unix_user"], "marie")
        self.n.identite.droits.est_admin = lambda c: c in ("adm@x.fr", "u@x.fr") or vrai(c)
        self.assertEqual(self.ex("comptes.identite_lier", compte="u@x.fr", unix_user="marie")["statut"], "echec")        # déjà adossé à un autre

    def test_un_compte_ordinaire_ne_lie_rien_et_le_superadmin_garde_son_bash(self):
        self.creer("root@x.fr")
        self.creer("u@x.fr")
        self.creer("v@x.fr")
        self.assertEqual(self.ex("comptes.identite_lier", au_nom_de="u@x.fr", compte="v@x.fr", fp_account="x")["statut"], "refuse")
        r = self.ex("comptes.identite_lier", compte="root@x.fr", unix_user="autre")
        self.assertEqual(r["statut"], "echec", r)
        self.assertIn("superadministrateur", r["erreur"])
        i = self.ex("comptes.identites", au_nom_de="u@x.fr")["resultat"]
        self.assertFalse(i["peut_modifier"])

    def test_le_lien_se_defait(self):
        self.creer("root@x.fr")
        self.creer("u@x.fr")
        r = self.ex("comptes.identite_lier", compte="u@x.fr", fp_account="marie")
        self.n.catalogue.get("comptes.identite_lier").defaire(self.n.executeur.contextes["comptes"], r["resultat"])
        self.assertEqual(self.ex("comptes.identites", au_nom_de="u@x.fr")["resultat"]["fp_account"], "")


class Appareils(Monde):
    def test_se_souvenir_d_un_appareil_et_l_oublier_apres_trente_jours(self):
        self.creer("root@x.fr")
        self.creer("u@x.fr")
        idt = self.n.identite
        self.assertEqual(idt.appareil_vu("u@x.fr", "203.0.113.5", "Firefox"), "premier")
        self.assertEqual(idt.appareil_vu("u@x.fr", "203.0.113.5", "Firefox"), "connu")
        app = idt.appareils("u@x.fr")[0]
        self.assertTrue(idt.appareil_confiance("u@x.fr", app["id"], True)["ok"])
        self.assertTrue(idt.appareils("u@x.fr")[0]["confiance_jusqua"] > time.time() + 29 * 86400)
        idt.base.ecrire("UPDATE appareils SET derniere=?", (time.time() - 40 * 86400,))
        self.assertEqual(idt.appareil_vu("u@x.fr", "203.0.113.5", "Firefox"), "connu")               # de confiance : jamais « nouveau »
        idt.appareil_confiance("u@x.fr", app["id"], False)
        idt.base.ecrire("UPDATE appareils SET derniere=?", (time.time() - 40 * 86400,))
        self.assertEqual(idt.appareil_vu("u@x.fr", "203.0.113.5", "Firefox"), "nouveau")             # oublié

    def test_un_administrateur_sur_un_appareil_neuf_attend_l_approbation(self):
        self.creer("root@x.fr")
        self.creer("adm@x.fr")
        self.ex("droits.regler", sujet="adm@x.fr", droit="comptes.gerer")
        idt = self.n.identite
        idt.securite["admin_nouvel_appareil"] = "bloquer"
        idt.droits.est_admin = lambda c: c == "adm@x.fr"
        ouvrir = lambda ip, agent: self.ex("comptes.ouvrir_session", au_nom_de="adm@x.fr", compte="adm@x.fr", mot_de_passe=MDP, ip=ip, agent=agent)["resultat"]      # noqa: E731
        self.assertTrue(ouvrir("203.0.113.5", "Firefox")["ok"])                                   # le premier appareil : rien à comparer
        r = ouvrir("198.51.100.7", "Chrome")
        self.assertFalse(r["ok"], r)
        self.assertTrue(r.get("appareil_attente"))
        self.assertEqual(len(idt.sessions("adm@x.fr")), 1)                                        # la session du refus est fermée
        attente = [a for a in idt.appareils("adm@x.fr") if a["statut"] == "attente"]
        self.assertEqual(len(attente), 1)
        self.assertIn("appareils", [a["id"] for a in self.ex("comptes.mes_attentes", au_nom_de="adm@x.fr")["resultat"]["attentes"]])
        self.assertEqual(self.ex("comptes.appareil_decider", au_nom_de="adm@x.fr", appareil=attente[0]["id"], approuver=True)["statut"], "faite")
        self.assertTrue(ouvrir("198.51.100.7", "Chrome")["ok"])                                   # approuvé : il entre

    def test_le_superadministrateur_n_est_jamais_bloque(self):
        self.creer("root@x.fr")
        idt = self.n.identite
        idt.securite["admin_nouvel_appareil"] = "bloquer"
        ouvrir = lambda ip: self.ex("comptes.ouvrir_session", au_nom_de="root@x.fr", compte="root@x.fr", mot_de_passe=MDP, ip=ip, agent="Firefox")["resultat"]      # noqa: E731
        self.assertTrue(ouvrir("203.0.113.5")["ok"])
        self.assertTrue(ouvrir("198.51.100.7")["ok"])


class ADeFaire(Monde):
    def test_les_modules_declarent_leurs_attentes_et_le_noyau_les_rassemble(self):
        self.creer("root@x.fr")
        self.creer("u@x.fr")
        r = self.ex("comptes.mes_attentes", au_nom_de="u@x.fr")["resultat"]["attentes"]
        self.assertEqual([a["id"] for a in r], ["fiche"])
        self.assertEqual((r[0]["vers"], r[0]["module"]), ("mc_profil", "comptes"))
        self.ex("comptes.modifier_moi", au_nom_de="u@x.fr", lastname="Dupont")
        self.assertEqual(self.ex("comptes.mes_attentes", au_nom_de="u@x.fr")["resultat"]["attentes"], [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : QuiVoitMaFiche, IdentitesLiees, Appareils, ADeFaire
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
