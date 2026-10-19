# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module taches, avec le vrai module des projets pour les rôles
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #90a7a6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module taches, avec le vrai module des projets pour les rôles.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=90a7a6 ▼▼▼
"""Bancs du module taches, avec le vrai module des projets pour les rôles."""
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

BEA, LEO, ZOE = "bea@x.fr", "leo@x.fr", "zoe@x.fr"
J = lambda n: (datetime.now() + timedelta(days=n)).strftime("%Y-%m-%d")


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("projets", "taches"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("projets", "taches"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["taches"]
        self.n.executeur.contextes["projets"].executer_lecture = lambda cap, **a: {"comptes": [{"compte": x} for x in (BEA, LEO, ZOE)]}
        self.e = self.n.executeur.executer

    def ex(self, cap, compte=BEA, acteur="humain", **args):
        return self.e("taches." + cap, acteur, args, compte=compte)

    def ok(self, cap, **kw):
        r = self.ex(cap, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def retour(self, cap, res):
        self.n.catalogue.get("taches." + cap).defaire(self.ctx, res)

    def tache(self, texte="Appeler le client", compte=BEA, **kw):
        return self.ok("creer", texte=texte, compte=compte, **kw)["id"]

    def fiche(self, tid, compte=BEA):
        return self.ok("fiche", id=tid, compte=compte)

    def projet(self, nom="Site", compte=BEA):
        return self.e("projets.creer", "humain", {"nom": nom}, compte=compte)["resultat"]["id"]

    def inviter(self, pid, cible, role, par=BEA):
        self.e("projets.inviter", "humain", {"id": pid, "compte": cible, "role": role}, compte=par)
        self.e("projets.repondre_invitation", "humain", {"id": pid, "accepter": True}, compte=cible)

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def journal(self, tid, compte=BEA):
        return [j["texte"] for j in self.fiche(tid, compte)["journal"]]


class Cycle(Monde):
    def test_creer_prouve_journalise_et_se_defait(self):
        r = self.ex("creer", texte="Appeler le client", echeance=J(2), priorite="haute", notes="avant 10 h")
        self.assertEqual(r["statut"], "faite", r)
        f = self.fiche(r["resultat"]["id"])
        self.assertEqual((f["tache"]["statut"], f["tache"]["priorite"], f["tache"]["echeance"], f["provenance"]["kind"]), ("todo", 2, J(2) + " 09:00", "manuel"))
        self.assertEqual(self.journal(r["resultat"]["id"]), ["Ouverte"])
        self.assertEqual(len(self.evts("capacite.prouvee")), 1)
        self.retour("creer", r["resultat"])
        self.assertEqual(self.ok("lister")["taches"], [])

    def test_les_refus_de_creation(self):
        for args in (dict(texte="  "), dict(texte="x", echeance="un jour"), dict(texte="x", priorite="vitale"), dict(texte="x", recurrence="tous les mardis"), dict(texte="x", responsable="inconnu@x.fr")):
            self.assertEqual(self.ex("creer", **args)["statut"], "echec", args)
        for compte in ("", "cassandra", "itare"):
            self.assertEqual(self.ex("creer", compte=compte, texte="x")["statut"], "echec")

    def test_les_formes_d_echeance(self):
        t = self.tache(echeance="+3d")
        self.assertEqual(self.fiche(t)["tache"]["echeance"][:10], J(3))
        t = self.tache(echeance="2026-12-24T18:30")
        self.assertEqual(self.fiche(t)["tache"]["echeance"], "2026-12-24 18:30")

    def test_les_transitions_laissent_leur_trace(self):
        t = self.tache()
        self.ok("modifier", id=t, statut="en cours")
        self.ok("modifier", id=t, statut="fait")
        self.ok("modifier", id=t, statut="todo")
        self.assertEqual(self.journal(t)[:4], ["Rouverte", "Passée « faite »", "Passée « en cours »", "Ouverte"])
        f = self.fiche(t)["tache"]
        self.assertEqual((f["statut"], f["fait_le"]), ("todo", None))

    def test_terminer_met_a_cent_pour_cent_et_date_la_fin(self):
        t = self.tache()
        self.ok("modifier", id=t, statut="fait")
        f = self.fiche(t)["tache"]
        self.assertEqual((f["avancement"], f["fait_le"] is not None), (100, True))
        self.assertEqual(len(self.evts("tache.terminee")), 1)

    def test_avancer_une_tache_a_faire_la_passe_en_cours(self):
        t = self.tache()
        self.ok("modifier", id=t, avancement=40)
        f = self.fiche(t)["tache"]
        self.assertEqual((f["statut"], f["avancement"]), ("en cours", 40))
        self.assertIn("Avancement 40 %", self.journal(t))

    def test_abandonner_exige_une_raison_gardee(self):
        t = self.tache()
        r = self.ex("modifier", id=t, statut="abandonnee")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("pourquoi", r["erreur"])
        self.ok("modifier", id=t, statut="abandonnee", raison="Le client a annulé")
        self.assertIn("Abandonnée : « Le client a annulé »", self.journal(t))
        self.assertEqual(self.fiche(t)["tache"]["raison"], "Le client a annulé")

    def test_repousser_l_echeance_compte_les_reports_avancer_non(self):
        t = self.tache(echeance=J(1))
        self.ok("modifier", id=t, echeance=J(5))
        self.ok("modifier", id=t, echeance=J(9))
        self.ok("modifier", id=t, echeance=J(2))
        f = self.fiche(t)["tache"]
        self.assertEqual(f["reports"], 2)
        self.assertTrue(any(j.startswith("Reportée du ") for j in self.journal(t)))

    def test_le_retour_d_une_modification_remet_la_tache(self):
        t = self.tache(echeance=J(1), priorite="basse")
        r = self.ex("modifier", id=t, texte="Autre texte", statut="en cours", priorite="urgente", echeance=J(9))
        self.retour("modifier", r["resultat"])
        f = self.fiche(t)["tache"]
        self.assertEqual((f["texte"], f["statut"], f["priorite"], f["echeance"][:10], f["reports"]), ("Appeler le client", "todo", 0, J(1), 0))

    def test_une_tache_a_soi_n_est_pas_a_un_autre(self):
        t = self.tache()
        for cap, args in (("fiche", {}), ("modifier", dict(statut="fait")), ("supprimer", {}), ("lier", dict(kind="url", ref="http://x.fr"))):
            self.assertEqual(self.ex(cap, id=t, compte=LEO, **args)["statut"], "echec", cap)
        self.assertEqual(self.ok("lister", compte=LEO)["taches"], [])


class Recurrence(Monde):
    def test_la_suivante_repart_de_l_echeance_precedente_pas_d_aujourd_hui(self):
        t = self.tache("Facturer", echeance=J(-4), recurrence="weekly")
        r = self.ex("modifier", id=t, statut="fait")
        self.assertEqual(r["statut"], "faite", r)
        s = r["resultat"]["suivante"]
        self.assertEqual(s["echeance"][:10], J(3))                              # -4 + 7, et non aujourd'hui + 7
        n = self.fiche(s["id"])["tache"]
        self.assertEqual((n["texte"], n["statut"], n["recurrence"], n["avancement"]), ("Facturer", "todo", "weekly", 0))
        self.assertIn("Occurrence suivante de « Facturer »", self.journal(s["id"]))
        self.assertTrue(any(j.startswith("Terminée — prochaine occurrence le") for j in self.journal(t)))

    def test_le_retour_retire_l_occurrence_creee_par_l_acte(self):
        t = self.tache("Facturer", echeance=J(1), recurrence="monthly")
        r = self.ex("modifier", id=t, statut="fait")
        self.assertEqual(len(self.ok("lister")["taches"]), 1)
        self.retour("modifier", r["resultat"])
        taches = self.ok("lister")["taches"]
        self.assertEqual([x["id"] for x in taches], [t])

    def test_rouvrir_ou_modifier_sans_terminer_ne_cree_rien(self):
        t = self.tache(echeance=J(1), recurrence="weekly")
        self.ok("modifier", id=t, statut="en cours")
        self.ok("modifier", id=t, notes="encore")
        self.assertEqual(len(self.ok("lister")["taches"]), 1)

    def test_sans_echeance_la_suivante_part_d_aujourd_hui(self):
        t = self.tache("Sauvegarde", recurrence="weekly")
        s = self.ok("modifier", id=t, statut="fait")["suivante"]
        self.assertEqual(s["echeance"][:10], J(7))


class SousTachesEtLiens(Monde):
    def test_les_sous_taches_sont_comptees(self):
        p = self.tache("Déménager")
        a, b = self.tache("Cartons", parent_id=p), self.tache("Camion", parent_id=p)
        self.ok("modifier", id=a, statut="fait")
        t = {x["id"]: x for x in self.ok("lister")["taches"]}
        self.assertEqual((t[p]["nb_sous"], t[p]["nb_sous_faites"]), (2, 1))
        self.assertEqual([x["id"] for x in self.ok("lister", racines_seules=True)["taches"]], [p])
        self.assertEqual({s["id"] for s in self.fiche(p)["sous"]}, {a, b})

    def test_une_tache_parente_d_autrui_est_refusee(self):
        autre = self.tache("Chez Léo", compte=LEO)
        self.assertEqual(self.ex("creer", texte="x", parent_id=autre)["statut"], "echec")

    def test_lier_normalise_ne_double_pas_et_se_defait(self):
        t = self.tache()
        r = self.ex("lier", id=t, kind="domain", ref="https://www.Exemple.fr/accueil", label="Le site")
        self.assertEqual((r["statut"], r["resultat"]["ref"]), ("faite", "exemple.fr"))
        self.assertTrue(self.ok("lier", id=t, kind="domain", ref="exemple.fr")["existait"])
        self.assertEqual(len(self.fiche(t)["liens"]), 1)
        self.retour("lier", r["resultat"])
        self.assertEqual(self.fiche(t)["liens"], [])
        for args in (dict(kind="inconnu", ref="x"), dict(kind="url", ref="")):
            self.assertEqual(self.ex("lier", id=t, **args)["statut"], "echec", args)

    def test_une_tache_se_rattache_a_un_rappel_et_a_un_document(self):
        t = self.tache()
        self.ok("lier", id=t, kind="reminder", ref="7", label="Appeler le notaire")
        self.ok("lier", id=t, kind="document", ref="contrats/bail.pdf", label="Le bail")
        self.assertEqual(sorted((l["kind"], l["ref"]) for l in self.fiche(t)["liens"]), [("document", "contrats/bail.pdf"), ("reminder", "7")])

    def test_delier_et_son_retour(self):
        t = self.tache()
        self.ok("lier", id=t, kind="contact", ref="12", label="Zoé")
        r = self.ex("delier", id=t, kind="contact", ref="12")
        self.assertEqual(self.fiche(t)["liens"], [])
        self.retour("delier", r["resultat"])
        self.assertEqual(self.fiche(t)["liens"][0]["label"], "Zoé")
        self.assertEqual(self.ex("delier", id=t, kind="contact", ref="99")["statut"], "echec")

    def test_supprimer_emporte_les_sous_taches_les_liens_et_le_journal_et_le_retour_les_rend(self):
        p = self.tache("Déménager")
        a = self.tache("Cartons", parent_id=p)
        self.ok("lier", id=p, kind="url", ref="http://x.fr")
        self.ok("lier", id=a, kind="note", ref="7")
        self.ok("modifier", id=a, statut="en cours")
        r = self.ex("supprimer", id=p)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM taches")[0]["n"], 0)
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM liens")[0]["n"] + self.ctx.stockage.lire("SELECT COUNT(*) n FROM journal")[0]["n"], 0)
        self.retour("supprimer", r["resultat"])
        self.assertEqual({x["id"] for x in self.ok("lister")["taches"]}, {p, a})
        self.assertEqual(len(self.fiche(p)["liens"]), 1)
        self.assertEqual(len(self.fiche(a)["liens"]), 1)
        self.assertIn("Passée « en cours »", self.journal(a))


class Provenance(Monde):
    def test_une_detection_ne_devient_tache_qu_une_fois(self):
        r = self.ex("creer", texte="Renouveler le certificat de a.fr", source="constat", origine="certificat:a.fr")
        self.assertEqual(r["statut"], "faite", r)
        f = self.fiche(r["resultat"]["id"])
        self.assertEqual((f["provenance"]["kind"], f["provenance"]["ref"]), ("constat", "certificat:a.fr"))
        again = self.ex("creer", texte="Renouveler le certificat de a.fr", source="constat", origine="certificat:a.fr")
        self.assertEqual(again["statut"], "echec")
        self.assertIn("déjà devenue une tâche", again["erreur"])
        self.assertEqual(self.ex("creer", texte="Pareil chez Léo", source="constat", origine="certificat:a.fr", compte=LEO)["statut"], "faite")

    def test_deux_taches_manuelles_identiques_sont_permises(self):
        self.tache("Appeler")
        self.tache("Appeler")
        self.assertEqual(len(self.ok("lister")["taches"]), 2)

    def test_provenances_connues_et_inconnues(self):
        t = self.tache("x", source="auto-ssl", origine="a.fr")
        self.assertIn("certificat", self.fiche(t)["provenance"]["texte"])
        t = self.tache("y", source="robot-x", origine="1")
        self.assertIn("robot-x", self.fiche(t)["provenance"]["texte"])


class Responsable(Monde):
    def test_confier_a_itare_le_dit_au_bus_et_au_journal(self):
        t = self.tache("Chercher des devis", responsable="itare")
        self.assertIn("Ouverte — confiée à Itare", self.journal(t))
        e = self.evts("tache.confiee")
        self.assertEqual((len(e), e[0]["donnees"]["a"]), (1, "itare"))
        t2 = self.tache("Autre")
        self.ok("modifier", id=t2, responsable="itare")
        self.assertIn("Confiée à Itare", self.journal(t2))
        self.assertEqual(len(self.evts("tache.confiee")), 2)
        self.ok("modifier", id=t2, responsable="")
        self.assertIn("Plus de responsable", self.journal(t2))

    def test_hors_projet_seul_soi_meme_ou_itare(self):
        self.assertEqual(self.ex("creer", texte="x", responsable=LEO)["statut"], "echec")
        self.assertEqual(self.ex("creer", texte="x", responsable=BEA)["statut"], "faite")

    def test_dans_un_projet_un_membre_actif_ou_le_proprietaire(self):
        p = self.projet()
        self.assertEqual(self.ex("creer", texte="x", projet_id=p, responsable=LEO)["statut"], "echec")           # étranger
        self.e("projets.inviter", "humain", {"id": p, "compte": LEO, "role": "auteur"}, compte=BEA)
        self.assertEqual(self.ex("creer", texte="x", projet_id=p, responsable=LEO)["statut"], "echec")           # invité, pas encore membre
        self.e("projets.repondre_invitation", "humain", {"id": p, "accepter": True}, compte=LEO)
        self.assertEqual(self.ex("creer", texte="x", projet_id=p, responsable=LEO)["statut"], "faite")
        self.assertEqual(self.ex("creer", texte="y", projet_id=p, responsable=BEA, compte=LEO)["statut"], "faite")      # le propriétaire


class Projets(Monde):
    def test_dans_un_projet_il_faut_pouvoir_y_ecrire(self):
        p = self.projet()
        self.inviter(p, LEO, "lecteur")
        self.inviter(p, ZOE, "auteur")
        self.assertEqual(self.ex("creer", texte="x", projet_id=p, compte=LEO)["statut"], "echec")
        t = self.ok("creer", texte="De Zoé", projet_id=p, compte=ZOE)["id"]
        self.assertEqual(self.ex("creer", texte="x", projet_id=p, compte="chef@x.fr")["statut"], "echec")        # étranger
        self.assertEqual(self.ex("creer", texte="x", projet_id=9999)["statut"], "echec")

    def test_les_membres_voient_les_taches_du_projet_les_etrangers_non(self):
        p = self.projet()
        self.inviter(p, LEO, "lecteur")
        mienne = self.ok("creer", texte="La mienne", projet_id=p)["id"]
        self.assertEqual([x["texte"] for x in self.ok("lister", projet_id=p, compte=LEO)["taches"]], ["La mienne"])
        self.assertEqual(self.fiche(mienne, LEO)["tache"]["texte"], "La mienne")
        self.assertEqual(self.ex("lister", projet_id=p, compte=ZOE)["statut"], "echec")
        self.assertEqual(self.ex("fiche", id=mienne, compte=ZOE)["statut"], "echec")

    def test_un_lecteur_voit_mais_ne_modifie_pas_un_auteur_modifie_celle_d_un_autre(self):
        p = self.projet()
        self.inviter(p, LEO, "lecteur")
        self.inviter(p, ZOE, "auteur")
        t = self.ok("creer", texte="Partagée", projet_id=p)["id"]
        self.assertEqual(self.ex("modifier", id=t, statut="fait", compte=LEO)["statut"], "echec")
        self.assertEqual(self.ex("modifier", id=t, statut="en cours", compte=ZOE)["statut"], "faite")

    def test_un_projet_supprime_ne_supprime_pas_les_taches(self):
        p = self.projet()
        t = self.ok("creer", texte="Reste à la personne", projet_id=p)["id"]
        self.e("projets.supprimer", "humain", {"id": p}, compte=BEA)
        self.assertEqual(self.fiche(t)["tache"]["texte"], "Reste à la personne")
        self.assertEqual([x["id"] for x in self.ok("lister")["taches"]], [t])

    def test_avancement_pondere_par_la_charge_sans_les_abandonnees(self):
        p = self.projet()
        a = self.ok("creer", texte="Petite", projet_id=p, charge=1)["id"]
        b = self.ok("creer", texte="Grosse", projet_id=p, charge=9)["id"]
        c = self.ok("creer", texte="Abandonnée", projet_id=p, charge=50)["id"]
        self.ok("modifier", id=a, statut="fait")
        self.ok("modifier", id=c, statut="abandonnee", raison="plus utile")
        av = self.ok("avancement", projet_id=p)
        self.assertEqual((av["global"], av["fait"], av["total"]), (10, 1, 10))
        self.ok("modifier", id=b, statut="fait")
        self.assertEqual(self.ok("avancement", projet_id=p)["global"], 100)
        self.assertEqual(self.ex("avancement", projet_id=p, compte=ZOE)["statut"], "echec")

    def test_la_liste_porte_le_nom_du_projet(self):
        p = self.projet("Refonte")
        self.ok("creer", texte="x", projet_id=p)
        self.assertEqual(self.ok("lister")["taches"][0]["projet"], "Refonte")

    def test_deplacer_vers_un_projet_ou_l_on_ne_peut_pas_ecrire_est_refuse(self):
        autre = self.projet("Chez Léo", compte=LEO)
        t = self.tache()
        self.assertEqual(self.ex("modifier", id=t, projet_id=autre)["statut"], "echec")


class Retard(Monde):
    def test_une_tache_ouverte_echue_est_un_constat_pour_son_compte(self):
        passee = self.tache("En retard", echeance=J(-3))
        self.tache("Dans l'avenir", echeance=J(3))
        self.tache("Sans date")
        faite = self.tache("Faite", echeance=J(-3))
        self.ok("modifier", id=faite, statut="fait")
        self.ok("modifier", id=passee, echeance=J(-1))
        self.ok("modifier", id=passee, echeance=J(-1))
        self.n.tick()
        o = [e for e in self.evts("constat.ouvert") if "Tâche en retard" in e["donnees"]["titre"]]
        self.assertEqual([e["donnees"]["titre"] for e in o], ["Tâche en retard : En retard"])
        self.assertEqual(o[0]["compte"], BEA)
        self.ok("modifier", id=passee, statut="fait")
        self.n.tick(time.time() + 4000)
        self.assertEqual(len(self.evts("constat.resolu")), 1)


class SansProjets(unittest.TestCase):
    def test_sans_le_module_des_projets_les_taches_personnelles_marchent(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        mods = Path(tmp.name) / "modules"
        shutil.copytree(RACINE / "modules" / "taches", mods / "taches", ignore=shutil.ignore_patterns("__pycache__"))
        n = moteur.Noyau(Path(tmp.name) / "d", mods, {}, gerer_modules=True)
        n.brancher()
        self.assertTrue(n.activer("taches")["ok"])
        r = n.executeur.executer("taches.creer", "humain", {"texte": "Seule"}, compte=BEA)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(n.executeur.executer("taches.creer", "humain", {"texte": "x", "projet_id": 1}, compte=BEA)["statut"], "echec")
        r = n.executeur.executer("taches.lister", "humain", {}, compte=BEA)
        self.assertEqual(len(r.get("resultat", r)["taches"]), 1)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Cycle, Recurrence, SousTachesEtLiens, Provenance, Responsable, Projets, Retard …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
