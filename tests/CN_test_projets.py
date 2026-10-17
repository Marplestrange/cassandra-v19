# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module projets
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #1b7a47
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module projets : un vrai noyau, des comptes simulés, des rôles, un plan qui glisse.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1b7a47 ▼▼▼
"""Bancs du module projets : un vrai noyau, des comptes simulés, des rôles, un plan qui glisse."""
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402

CHEF, BEA, LEO, ZOE = "chef@x.fr", "bea@x.fr", "leo@x.fr", "zoe@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        shutil.copytree(RACINE / "modules" / "projets", mods / "projets")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("projets")["ok"])
        self.n.droits.regler_admin(CHEF, True)
        self.ctx = self.n.executeur.contextes["projets"]
        self.ctx.executer_lecture = lambda cap, **a: {"comptes": [{"compte": x} for x in (CHEF, BEA, LEO, ZOE)]}
        self.e = self.n.executeur.executer

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.e("projets." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def retour(self, cap, res):
        self.n.catalogue.get("projets." + cap).defaire(self.ctx, res)

    def projet(self, nom="Refonte du site", compte=BEA, **kw):
        return self.ok("creer", nom=nom, compte=compte, **kw)["id"]

    def voir(self, pid, compte=BEA):
        return self.ok("voir", id=pid, compte=compte)

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def inv(self, pid, cible, role, par=BEA):
        """Inviter : « compte » est ici l'invité, et c'est `par` qui agit."""
        return self.e("projets.inviter", "humain", {"id": pid, "compte": cible, "role": role}, compte=par)

    def ret(self, pid, cible, par=BEA):
        return self.e("projets.retirer_membre", "humain", {"id": pid, "compte": cible}, compte=par)

    def equipe(self, pid, cible, role, par=BEA):
        r = self.inv(pid, cible, role, par)
        self.assertEqual(r["statut"], "faite", r)
        self.ok("repondre_invitation", id=pid, accepter=True, compte=cible)


class Fiche(Monde):
    def test_creer_depuis_un_modele_pose_ses_phases_et_ouvre_le_journal(self):
        r = self.ex("creer", nom="Mon livre", modele="livre", objectif="Écrire 12 chapitres")
        self.assertEqual(r["statut"], "faite", r)
        v = self.voir(r["resultat"]["id"])
        self.assertEqual([(p["nom"], p["etat"]) for p in v["phases"]], [("Écriture", "En cours"), ("Relecture", "À venir"), ("Édition", "À venir")])
        self.assertEqual(v["projet"]["mon_role"], "proprietaire")
        self.assertIn("modèle Livre", v["projet"]["journal"][0]["texte"])
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)

    def test_le_retour_d_une_creation_efface_le_projet_et_ses_phases(self):
        r = self.ex("creer", nom="X", modele="client")
        self.retour("creer", r["resultat"])
        self.assertEqual(self.ok("lister")["projets"], [])
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM phases")[0]["n"], 0)

    def test_les_refus_de_creation(self):
        for args in (dict(nom="  "), dict(nom="X", modele="inconnu"), dict(nom="X", statut="loufoque"), dict(nom="X", priorite="Urgente"), dict(nom="X", debut="demain"), dict(nom="X", fin="2026-02-30")):
            self.assertEqual(self.ex("creer", **args)["statut"], "echec", args)
        for compte in ("", "cassandra"):
            self.assertEqual(self.ex("creer", compte=compte, nom="X")["statut"], "echec")

    def test_modifier_est_un_patch_et_le_domaine_se_normalise(self):
        pid = self.projet(resume="Un résumé", objectif="Un objectif")
        r = self.ex("modifier", id=pid, priorite="Haute", domaine="https://www.Exemple.fr/accueil")
        self.assertEqual(r["statut"], "faite", r)
        p = self.voir(pid)["projet"]
        self.assertEqual((p["priorite"], p["domaine"], p["resume"], p["objectif"]), ("Haute", "exemple.fr", "Un résumé", "Un objectif"))
        self.retour("modifier", r["resultat"])
        p = self.voir(pid)["projet"]
        self.assertEqual((p["priorite"], p["domaine"]), ("Normale", ""))
        self.assertEqual(self.ex("modifier", id=pid, champ_inconnu="x")["statut"], "echec")

    def test_le_journal_s_enrichit_de_lignes_datees_et_se_defait(self):
        pid = self.projet()
        r = self.ex("noter", id=pid, texte="Première réunion")
        self.assertEqual(r["statut"], "faite", r)
        j = self.voir(pid)["projet"]["journal"]
        self.assertEqual(j[-1]["texte"], "Première réunion")
        self.assertRegex(j[-1]["quand"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
        self.retour("noter", r["resultat"])
        self.assertEqual(len(self.voir(pid)["projet"]["journal"]), 1)
        self.assertEqual(self.ex("noter", id=pid, texte="  ")["statut"], "echec")

    def test_archiver_bloque_l_ecriture_mais_pas_la_fiche(self):
        pid = self.projet()
        r = self.ex("archiver", id=pid)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ok("lister")["projets"], [])
        self.assertEqual(len(self.ok("lister", archives=True)["projets"]), 1)
        refus = self.ex("noter", id=pid, texte="x")
        self.assertEqual(refus["statut"], "echec")
        self.assertIn("archivé", refus["erreur"])
        self.assertEqual(self.ex("phase_enregistrer", id=pid, nom="Nouvelle")["statut"], "echec")
        self.assertEqual(self.ex("modifier", id=pid, resume="encore modifiable")["statut"], "faite")
        self.retour("archiver", r["resultat"])
        self.assertEqual(len(self.ok("lister")["projets"]), 1)
        self.assertEqual(self.ex("archiver", id=pid, archive=False)["statut"], "faite")

    def test_trouver_par_nom_exact_puis_partiel(self):
        a = self.projet("Refonte")
        self.projet("Refonte du site vitrine")
        self.assertEqual(self.ok("trouver", nom="refonte")["projet"]["id"], a)
        self.assertEqual(self.ok("trouver", nom="vitrine")["projet"]["nom"], "Refonte du site vitrine")
        self.assertIsNone(self.ok("trouver", nom="inexistant")["projet"])


class Corbeille(Monde):
    def test_supprimer_ne_detruit_rien_et_restaure_sous_le_meme_numero(self):
        pid = self.projet(modele="client")
        self.ok("jalon_enregistrer", id=pid, nom="Recette", date="2026-12-01")
        self.ok("decision_enregistrer", id=pid, question="Quel hébergeur ?")
        r = self.ex("supprimer", id=pid)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ok("lister")["projets"], [])
        self.assertEqual(self.ok("corbeille")["projets"][0]["id"], pid)
        self.assertEqual(self.ex("voir", id=pid)["statut"], "faite")                     # le propriétaire peut encore le voir (corbeille)
        self.assertTrue(self.voir(pid)["projet"]["corbeille"])
        self.ok("restaurer", id=pid)
        v = self.voir(pid)
        self.assertEqual((len(v["phases"]), len(v["jalons"]), len(v["decisions"])), (5, 1, 1))
        self.assertFalse(v["projet"]["corbeille"])

    def test_le_retour_de_supprimer_et_de_restaurer(self):
        pid = self.projet()
        r = self.ex("supprimer", id=pid)
        self.retour("supprimer", r["resultat"])
        self.assertEqual(len(self.ok("lister")["projets"]), 1)
        self.ok("supprimer", id=pid)
        r = self.ex("restaurer", id=pid)
        self.retour("restaurer", r["resultat"])
        self.assertEqual(self.ok("lister")["projets"], [])

    def test_seul_le_proprietaire_supprime_restaure_et_purge(self):
        pid = self.projet()
        self.equipe(pid, LEO, "coproprietaire")
        self.assertEqual(self.ex("supprimer", id=pid, compte=LEO)["statut"], "echec")
        self.ok("supprimer", id=pid)
        self.assertEqual(self.ex("restaurer", id=pid, compte=LEO)["statut"], "echec")
        self.assertEqual(self.ex("purger", id=pid, compte=LEO)["statut"], "echec")
        self.assertEqual(self.ex("corbeille", compte=LEO)["resultat"]["projets"], [])

    def test_purger_efface_et_se_defait_en_recreant_tout(self):
        pid = self.projet(modele="infra")
        self.ok("jalon_enregistrer", id=pid, nom="Bascule", date="2026-11-01")
        self.equipe(pid, LEO, "auteur")
        self.ok("supprimer", id=pid)
        r = self.ex("purger", id=pid)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM projets")[0]["n"], 0)
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM phases")[0]["n"], 0)
        self.retour("purger", r["resultat"])
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM phases WHERE projet_id=?", (pid,))[0]["n"], 5)
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM jalons WHERE projet_id=?", (pid,))[0]["n"], 1)
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM membres WHERE projet_id=?", (pid,))[0]["n"], 1)

    def test_on_ne_purge_pas_ce_qui_n_est_pas_a_la_corbeille(self):
        pid = self.projet()
        self.assertEqual(self.ex("purger", id=pid)["statut"], "echec")
        self.assertEqual(self.ex("restaurer", id=pid)["statut"], "echec")


class Plan(Monde):
    def test_phases_jalons_decisions(self):
        pid = self.projet(modele="vide")
        p = self.ok("phase_enregistrer", id=pid, nom="Cadrage", ordre=5, debut="2026-10-01", fin="2026-10-15", etat="En cours", charge=3)
        self.assertEqual(self.ok("phase_enregistrer", id=pid, ligne=p["ligne"], etat="Terminée")["ligne"], p["ligne"])
        j = self.ok("jalon_enregistrer", id=pid, nom="Livraison", date="2026-12-24")
        d = self.ok("decision_enregistrer", id=pid, question="Quel CMS ?")
        v = self.voir(pid)
        self.assertEqual([x["nom"] for x in v["phases"]], ["À définir", "Cadrage"])
        self.assertEqual(v["phases"][1]["etat"], "Terminée")
        self.assertEqual((v["jalons"][0]["nom"], v["decisions"][0]["etat"], v["decisions"][0]["auteur"]), ("Livraison", "ouverte", BEA))
        self.ok("decision_enregistrer", id=pid, ligne=d["ligne"], etat="tranchee", reponse="WordPress", raison="Connu de l'équipe")
        dec = self.voir(pid)["decisions"][0]
        self.assertEqual((dec["etat"], dec["reponse"], dec["ferme"]), ("tranchee", "WordPress", time.strftime("%Y-%m-%d")))

    def test_les_valeurs_invalides_sont_refusees(self):
        pid = self.projet()
        for cap, args in (("phase_enregistrer", dict(nom="X", etat="Bizarre")), ("phase_enregistrer", dict(nom="X", debut="31/12/2026")), ("phase_enregistrer", dict(nom="X", charge="beaucoup")),
                          ("phase_enregistrer", dict(nom="")), ("jalon_enregistrer", dict(nom="X", etat="rate")), ("jalon_enregistrer", dict(nom="X", date="bientôt")),
                          ("decision_enregistrer", dict(question="")), ("decision_enregistrer", dict(question="X", etat="peut-être"))):
            self.assertEqual(self.ex(cap, id=pid, **args)["statut"], "echec", (cap, args))

    def test_les_retours_remettent_l_ancien_ou_retirent_le_nouveau(self):
        pid = self.projet()
        r = self.ex("jalon_enregistrer", id=pid, nom="Jalon", date="2026-11-11")
        self.retour("jalon_enregistrer", r["resultat"])
        self.assertEqual(self.voir(pid)["jalons"], [])
        j = self.ok("jalon_enregistrer", id=pid, nom="Jalon", date="2026-11-11")
        r = self.ex("jalon_enregistrer", id=pid, ligne=j["ligne"], date="2027-01-01", nom="Renommé")
        self.retour("jalon_enregistrer", r["resultat"])
        x = self.voir(pid)["jalons"][0]
        self.assertEqual((x["nom"], x["date"]), ("Jalon", "2026-11-11"))

    def test_supprimer_une_ligne_et_son_retour(self):
        pid = self.projet(modele="client")
        ph = self.voir(pid)["phases"][2]
        r = self.ex("phase_supprimer", id=pid, ligne=ph["id"])
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(len(self.voir(pid)["phases"]), 4)
        self.retour("phase_supprimer", r["resultat"])
        self.assertEqual([p["nom"] for p in self.voir(pid)["phases"]], ["Cadrage", "Conception", "Réalisation", "Recette", "Livraison"])
        self.assertEqual(self.ex("phase_supprimer", id=pid, ligne=9999)["statut"], "echec")

    def test_une_ligne_d_un_autre_projet_ne_se_touche_pas(self):
        a, b = self.projet("A"), self.projet("B")
        j = self.ok("jalon_enregistrer", id=a, nom="Jalon A")
        self.assertEqual(self.ex("jalon_supprimer", id=b, ligne=j["ligne"])["statut"], "echec")
        self.assertEqual(self.ex("jalon_enregistrer", id=b, ligne=j["ligne"], nom="Volé")["statut"], "echec")
        self.assertEqual(self.voir(a)["jalons"][0]["nom"], "Jalon A")

    def test_l_avancement_est_pondere_par_la_charge(self):
        pid = self.projet(modele="vide")
        ph0 = self.voir(pid)["phases"][0]
        self.ok("phase_enregistrer", id=pid, ligne=ph0["id"], nom="Petite", charge=1, etat="Terminée")
        self.ok("phase_enregistrer", id=pid, nom="Grosse", charge=9, etat="En cours")
        a = self.voir(pid)["avancement"]
        self.assertEqual((a["global"], a["fait"], a["total"]), (10, 1, 10))
        self.ok("phase_enregistrer", id=pid, ligne=self.voir(pid)["phases"][1]["id"], etat="Terminée")
        self.assertEqual(self.voir(pid)["avancement"]["global"], 100)

    def test_sans_charge_chaque_phase_pese_un(self):
        pid = self.projet(modele="client")
        self.ok("phase_enregistrer", id=pid, ligne=self.voir(pid)["phases"][0]["id"], etat="Terminée")
        self.assertEqual(self.voir(pid)["avancement"]["global"], 20)

    def test_le_plan_de_reference_rend_le_glissement_visible_et_l_ancien_part_au_journal(self):
        pid = self.projet(modele="vide")
        ph = self.voir(pid)["phases"][0]["id"]
        self.ok("phase_enregistrer", id=pid, ligne=ph, nom="Cadrage", debut="2026-10-01", fin="2026-10-15")
        j = self.ok("jalon_enregistrer", id=pid, nom="Livraison", date="2026-12-01")["ligne"]
        r = self.ex("refiger", id=pid)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.voir(pid)["glissement"]["lignes"], [])
        self.assertEqual(self.voir(pid)["projet"]["ref_date"], time.strftime("%Y-%m-%d"))
        self.ok("phase_enregistrer", id=pid, ligne=ph, fin="2026-10-29")
        self.ok("jalon_enregistrer", id=pid, ligne=j, date="2026-12-15")
        g = self.voir(pid)["glissement"]
        self.assertEqual(sorted((l["genre"], l["jours"]) for l in g["lignes"]), [("jalon", 14), ("phase", 14)])
        self.assertEqual(g["max_jours"], 14)
        self.ok("refiger", id=pid)
        g = self.voir(pid)["glissement"]
        self.assertEqual([(l["genre"], l["jours"]) for l in g["lignes"]], [("jalon", 14)])          # les phases se refigent ; un jalon garde sa date d'origine (« ne peut pas bouger »)
        journal = [x["texte"] for x in self.voir(pid)["projet"]["journal"]]
        self.assertTrue(any("référence précédente : Cadrage 2026-10-01→2026-10-15" in t for t in journal), journal)

    def test_le_retour_du_refigeage_remet_l_ancienne_reference(self):
        pid = self.projet(modele="vide")
        ph = self.voir(pid)["phases"][0]["id"]
        self.ok("phase_enregistrer", id=pid, ligne=ph, debut="2026-10-01", fin="2026-10-15")
        self.ok("refiger", id=pid)
        self.ok("phase_enregistrer", id=pid, ligne=ph, fin="2026-11-01")
        r = self.ex("refiger", id=pid)
        self.retour("refiger", r["resultat"])
        p = self.voir(pid)["phases"][0]
        self.assertEqual((p["ref_fin"], p["fin"]), ("2026-10-15", "2026-11-01"))

    def test_jalon_depasse_est_un_constat_pour_le_proprietaire_seulement(self):
        pid = self.projet("Site")
        hier = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        demain = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
        j1 = self.ok("jalon_enregistrer", id=pid, nom="Passé", date=hier)["ligne"]
        self.ok("jalon_enregistrer", id=pid, nom="Futur", date=demain)
        self.ok("jalon_enregistrer", id=pid, nom="Tenu", date=hier, etat="tenu")
        self.assertTrue(self.voir(pid)["jalons"][0]["depasse"])
        self.n.tick()
        ouverts = [e for e in self.evts("constat.ouvert") if "Jalon dépassé" in e["donnees"]["titre"]]
        self.assertEqual([e["donnees"]["titre"] for e in ouverts], ["Jalon dépassé : Passé (Site)"])
        self.assertEqual(ouverts[0]["compte"], BEA)
        self.ok("jalon_enregistrer", id=pid, ligne=j1, etat="tenu")
        self.n.tick(time.time() + 4000)
        self.assertEqual(len(self.evts("constat.resolu")), 1)


class Equipe(Monde):
    def setUp(self):
        super().setUp()
        self.pid = self.projet("Partagé", modele="client")

    def test_chaque_role_ouvre_ses_gestes(self):
        pid = self.pid
        self.equipe(pid, LEO, "lecteur")
        self.equipe(pid, ZOE, "auteur")
        self.equipe(pid, CHEF, "coproprietaire")
        # lecteur : voit, n'écrit pas
        self.assertEqual(self.ex("voir", id=pid, compte=LEO)["statut"], "faite")
        for cap, args in (("noter", dict(texte="x")), ("phase_enregistrer", dict(nom="x")), ("modifier", dict(resume="x")), ("supprimer", {})):
            self.assertEqual(self.ex(cap, id=pid, compte=LEO, **args)["statut"], "echec", ("lecteur", cap))
        self.assertEqual(self.inv(pid, BEA, "lecteur", par=LEO)["statut"], "echec")
        # auteur : écrit, pas la fiche ni l'équipe
        self.assertEqual(self.ex("noter", id=pid, compte=ZOE, texte="de Zoé")["statut"], "faite")
        self.assertEqual(self.ex("phase_enregistrer", id=pid, compte=ZOE, nom="Ajoutée")["statut"], "faite")
        for cap, args in (("modifier", dict(resume="x")), ("archiver", {}), ("refiger", {}), ("supprimer", {})):
            self.assertEqual(self.ex(cap, id=pid, compte=ZOE, **args)["statut"], "echec", ("auteur", cap))
        self.assertEqual(self.inv(pid, LEO, "auteur", par=ZOE)["statut"], "echec")
        # co-propriétaire : fiche et équipe, pas la suppression
        self.assertEqual(self.ex("modifier", id=pid, compte=CHEF, resume="ok")["statut"], "faite")
        self.assertEqual(self.ex("refiger", id=pid, compte=CHEF)["statut"], "faite")
        self.assertEqual(self.inv(pid, LEO, "auteur", par=CHEF)["statut"], "faite")
        self.assertEqual(self.ex("supprimer", id=pid, compte=CHEF)["statut"], "echec")

    def test_les_etrangers_ne_voient_rien_pas_meme_l_administrateur(self):
        for compte in (LEO, CHEF):
            for cap, args in (("voir", {}), ("equipe", {}), ("noter", dict(texte="x")), ("modifier", dict(resume="x")), ("supprimer", {})):
                r = self.ex(cap, id=self.pid, compte=compte, **args)
                self.assertEqual(r["statut"], "echec", (compte, cap))
                self.assertIn("introuvable", r["erreur"])
        self.assertEqual(self.ex("lister", compte=CHEF)["resultat"]["projets"], [])

    def test_une_invitation_n_ouvre_rien_avant_d_etre_acceptee(self):
        self.assertEqual(self.inv(self.pid, LEO, "auteur")["statut"], "faite")
        self.assertEqual(self.ex("voir", id=self.pid, compte=LEO)["statut"], "echec")
        inv = self.ok("invitations", compte=LEO)["invitations"]
        self.assertEqual((inv[0]["id"], inv[0]["projet"], inv[0]["role"], inv[0]["invite_par"]), (self.pid, "Partagé", "auteur", BEA))
        e = self.evts("projet.invitation")
        self.assertEqual((len(e), e[0]["compte"]), (1, LEO))
        self.ok("repondre_invitation", id=self.pid, accepter=True, compte=LEO)
        self.assertEqual(self.voir(self.pid, LEO)["projet"]["mon_role"], "auteur")
        self.assertEqual([p["id"] for p in self.ok("lister", compte=LEO)["projets"]], [self.pid])
        self.assertEqual(self.evts("projet.reponse")[0]["compte"], BEA)

    def test_decliner_retire_l_invitation_et_le_retour_la_remet(self):
        self.inv(self.pid, LEO, "lecteur")
        r = self.ex("repondre_invitation", id=self.pid, accepter=False, compte=LEO)
        self.assertEqual(self.ok("invitations", compte=LEO)["invitations"], [])
        self.retour("repondre_invitation", r["resultat"])
        self.assertEqual(len(self.ok("invitations", compte=LEO)["invitations"]), 1)

    def test_changer_un_role_et_defaire(self):
        self.equipe(self.pid, LEO, "lecteur")
        r = self.inv(self.pid, LEO, "co-proprietaire")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.voir(self.pid, LEO)["projet"]["mon_role"], "coproprietaire")
        self.retour("inviter", r["resultat"])
        self.assertEqual(self.voir(self.pid, LEO)["projet"]["mon_role"], "lecteur")

    def test_les_refus_d_invitation(self):
        for cible, role in (("inconnu@x.fr", "auteur"), (BEA, "auteur"), (LEO, "roi"), ("", "lecteur")):
            self.assertEqual(self.inv(self.pid, cible, role)["statut"], "echec", (cible, role))

    def test_retirer_un_membre_et_son_retour(self):
        self.equipe(self.pid, LEO, "auteur")
        r = self.ret(self.pid, LEO)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ex("voir", id=self.pid, compte=LEO)["statut"], "echec")
        self.retour("retirer_membre", r["resultat"])
        self.assertEqual(self.voir(self.pid, LEO)["projet"]["mon_role"], "auteur")
        self.assertEqual(self.ret(self.pid, ZOE)["statut"], "echec")                      # pas membre

    def test_un_lecteur_peut_se_retirer_mais_pas_retirer_un_autre(self):
        self.equipe(self.pid, LEO, "lecteur")
        self.equipe(self.pid, ZOE, "lecteur")
        self.assertEqual(self.ret(self.pid, ZOE, par=LEO)["statut"], "echec")
        self.assertEqual(self.ret(self.pid, LEO, par=LEO)["statut"], "faite")

    def test_le_projet_supprime_disparait_de_la_vue_des_membres(self):
        self.equipe(self.pid, LEO, "auteur")
        self.ok("supprimer", id=self.pid)
        self.assertEqual(self.ex("voir", id=self.pid, compte=LEO)["statut"], "echec")
        self.assertEqual(self.ok("lister", compte=LEO)["projets"], [])


class Contexte(Monde):
    def poser(self, taches, evenements=()):
        def lecture(cap, **a):
            if cap == "taches.lister":
                return {"taches": taches}
            if cap == "agenda.evenements":
                return {"evenements": list(evenements)}
            return {"comptes": []}
        self.ctx.executer_lecture = lecture

    def test_la_fiche_se_compose_et_la_sante_rend_ses_signaux(self):
        pid = self.projet("Livre 1", modele="livre", perimetre_in="- le manuscrit\n- les notes", reussite="publié")
        hier = time.strftime("%Y-%m-%d 09:00", time.localtime(time.time() - 86400 * 3))
        self.poser([{"id": 1, "texte": "Relire", "statut": "todo", "echeance": hier, "projet_id": pid},
                    {"id": 2, "texte": "Attendre l'éditeur", "statut": "en attente", "echeance": "", "projet_id": pid},
                    {"id": 3, "texte": "Fini", "statut": "fait", "echeance": hier, "projet_id": pid}],
                   [{"id": 9, "titre": "Salon du livre", "projet_id": pid}, {"id": 10, "titre": "Autre", "projet_id": 999}])
        x = self.ok("contexte", id=pid)
        self.assertEqual(x["modele"]["cle"], "livre")
        self.assertEqual(x["perimetre_in"], ["le manuscrit", "les notes"])
        self.assertEqual([e["titre"] for e in x["evenements"]], ["Salon du livre"])           # seuls ceux du projet
        sig = {s["nom"]: s for s in x["sante"]["signaux"]}
        self.assertEqual(sig["Tâches en retard"]["niveau"], "dgr")
        self.assertEqual(sig["Attente de tiers"]["niveau"], "warn")
        self.assertEqual(sig["Étapes tenues"]["niveau"], "muet")                              # aucune étape posée : rendu muet, pas « ok »
        self.assertEqual(x["sante"]["muets"], 2)                                              # les étapes, et le plan de référence jamais figé
        self.assertEqual(x["sante"]["score"], 100 - 7 - 5 + 5)
        self.assertEqual(x["comptes"], dict(x["comptes"], taches_ouvertes=2, taches_total=3, attente=1, retard=1))

    def test_le_portefeuille_porte_la_sante_de_chaque_projet(self):
        a = self.projet("Un")
        self.projet("Deux", compte=LEO)
        self.poser([])
        l = self.ok("portefeuille")["projets"]
        self.assertEqual([x["id"] for x in l], [a])                                           # le sien seulement
        self.assertIn(l[0]["verdict"], ("En bonne santé", "À surveiller", "Fragile"))
        self.assertEqual(l[0]["role"], "proprietaire")

    def test_une_source_qui_casse_ne_vide_pas_la_fiche(self):
        pid = self.projet("Robuste")
        def lecture(cap, **a):
            raise RuntimeError("module absent")
        self.ctx.executer_lecture = lecture
        x = self.ok("contexte", id=pid)
        self.assertEqual((x["taches"], x["evenements"]), ([], []))
        self.assertEqual(x["projet"]["nom"], "Robuste")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Fiche, Corbeille, Plan, Equipe, Contexte
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
