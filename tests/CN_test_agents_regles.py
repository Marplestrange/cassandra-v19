# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les règles communes aux agents, la tuile « retenus / refusés », les tâches récurrentes, « 
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #15bc49
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les règles communes aux agents, la tuile « retenus / refusés », les tâches récurrentes, « Pourquoi ? » en phrases et le vocabulaire côté données.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=15bc49 ▼▼▼
"""Les règles communes aux agents, la tuile « retenus / refusés », les tâches récurrentes, « Pourquoi ? » en phrases et le vocabulaire côté données.

Une règle posée AGIT dans le tour de l'agent : on le prouve par un tour, pas par la relecture de la règle.
"""
import sys
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

import CN_test_agents_actions as actions                           # noqa: E402
from CN_test_agents import BEA, LEO, ROOT, appel, texte           # noqa: E402


class Regles(actions.Actions):
    def test_les_regles_par_defaut_et_le_vocabulaire(self):
        r = self.agent("regles", compte=BEA)
        self.assertEqual((r["plafond_global_cts"], r["palier_defaut"], r["dehors_par_amizo"], r["ordre_journal"]), (None, "auto", True, "recent"))
        self.assertEqual(r["vocabulaire"]["niveaux"]["reine"], "Pleine autonomie")
        self.assertEqual(r["vocabulaire"]["palier_agent"], "Palier")

    def test_seul_l_administrateur_les_regle(self):
        self.refuse("regles_regler", compte=BEA, palier_defaut="raconter")
        self.assertEqual(self.agent("regles", compte=ROOT)["palier_defaut"], "auto")
        for faux in ({"palier_defaut": "retire"}, {"ordre_journal": "hier"}, {"dehors_par_amizo": "oui"}, {"plafond_euros": -1}, {"plafond_euros": 5, "action": "x"}):
            self.assertEqual(self.refuse("regles_regler", compte=ROOT, **faux)["statut"], "echec", faux)

    def test_le_plafond_global_se_pose_se_leve_et_se_defait(self):
        r = self.regler("regles_regler", compte=ROOT, plafond_euros=3.5, action="arret")
        self.assertEqual((r["plafond_global_cts"], r["plafond_action"]), (350, "arret"))
        self.assertEqual(self.agent("regles", compte=BEA)["plafond_global_cts"], 350)
        self.regler("regles_regler", compte=ROOT, sans_plafond=True)
        self.assertIsNone(self.agent("regles", compte=ROOT)["plafond_global_cts"])

    def test_le_palier_par_defaut_raconter_agit_dans_le_tour(self):
        self.regler("regles_regler", compte=ROOT, palier_defaut="raconter")
        r = self.causer("Crée une note", [self.creer("Racontée par la règle"), texte("Proposée.")], agent="itare")
        self.assertEqual(r["actions"][0]["statut"], "racontee")
        self.assertEqual(self.notes(), [])                                                           # rien n'a été fait
        self.regler("regles_regler", compte=ROOT, palier_defaut="auto")
        r = self.causer("Crée une note", [self.creer("Faite"), texte("Fait.")], agent="itare")
        self.assertEqual(r["actions"][0]["statut"], "faite")

    def test_une_regle_se_defait(self):
        r = self.ex("agents.regles_regler", compte=ROOT, plafond_euros=2, ordre_journal="ancien")
        self.assertEqual(r["statut"], "faite")
        self.assertEqual(self.agent("regles", compte=ROOT)["ordre_journal"], "ancien")
        fait = next(e for e in self.evts("capacite.faite") if e.get("objet_id") == "agents.regles_regler")
        self.assertEqual(self.n.executeur.defaire_acte(fait["id"], ROOT)["statut"], "defaite")
        r = self.agent("regles", compte=ROOT)
        self.assertEqual((r["ordre_journal"], r["plafond_global_cts"]), ("recent", None))


class Tuile(actions.Actions):
    def test_retenus_et_refuses(self):
        self.assertEqual(self.agent("retenus_refuses", compte=BEA)["retenus"], 0)
        for i in range(2):
            self.db.ecrire("INSERT INTO relectures(agent, compte, conversation_id, tour, verdict, motifs, ts) VALUES (?,?,?,?,?,?,?)", ("itare", BEA, 0, i, "retenue", '["secret"]', time.time()))
        self.db.ecrire("INSERT INTO relectures(agent, compte, conversation_id, tour, verdict, motifs, ts) VALUES (?,?,?,?,?,?,?)", ("itare", LEO, 0, 0, "retenue", '["secret"]', time.time()))
        self.racontee()
        self.decider(self.props()[0]["id"], "refuser")
        r = self.agent("retenus_refuses", compte=BEA)
        self.assertEqual((r["par_le_relecteur"], r["par_l_utilisateur"], r["retenus"]), (2, 1, 2))     # celles de Léo n'y sont pas
        self.assertEqual(self.agent("retenus_refuses", compte=ROOT)["par_le_relecteur"], 3)             # l'administrateur voit l'instance
        self.assertEqual(self.agent("retenus_refuses", compte=BEA, jours=9999)["jours"], 90)


class Taches(actions.Actions):
    def test_confier_lister_retirer(self):
        r = self.regler("tache_confier", compte=BEA, agent="itare", consigne="Prépare mon point du matin", frequence="quotidien", heure="07:30")
        liste = self.agent("taches", compte=BEA)
        self.assertEqual([(t["id"], t["agent"], t["frequence"], t["heure"]) for t in liste["taches"]], [(r["tache"], "itare", "quotidien", "07:30")])
        self.assertGreater(liste["taches"][0]["prochaine"], time.time())
        self.assertFalse(liste["declenchement_automatique"])
        self.assertEqual(self.agent("taches", compte=LEO)["taches"], [])                                 # la tâche d'un compte n'est qu'à lui
        self.assertEqual(self.refuse("tache_retirer", compte=LEO, id=r["tache"])["statut"], "echec")
        self.regler("tache_retirer", compte=BEA, id=r["tache"])
        self.assertEqual(self.agent("taches", compte=BEA)["taches"], [])

    def test_validations_et_cloisonnement_des_agents(self):
        for faux in ({"agent": "vision"}, {"agent": "inconnu"}, {"agent": "cassandra"}, {"consigne": "x"}, {"frequence": "minute"}, {"heure": "25:00"}, {"jour": "someday"}):
            a = dict({"agent": "itare", "consigne": "Fais le point", "frequence": "hebdomadaire", "heure": "08:00", "jour": "lundi"}, **faux)
            self.assertEqual(self.refuse("tache_confier", compte=BEA, **a)["statut"], "echec", faux)
        self.regler("tache_confier", compte=ROOT, agent="cassandra", consigne="Vérifie les sauvegardes", frequence="horaire")

    def test_lancer_joue_un_tour_de_l_agent_sous_le_compte_de_la_tache(self):
        t = self.regler("tache_confier", compte=BEA, agent="itare", consigne="Dis bonjour", frequence="quotidien")["tache"]
        self.faux.reponses += [texte("Bonjour !")]
        r = self.regler("tache_lancer", compte=BEA, id=t)
        self.assertGreater(r["conversation_id"], 0)
        self.assertIn("Bonjour !", [m["contenu"] for m in self.msgs(r["conversation_id"])])
        self.assertIsNotNone(self.agent("taches", compte=BEA)["taches"][0]["derniere"])
        self.assertEqual(self.refuse("tache_lancer", compte=LEO, id=t)["statut"], "echec")

    def test_la_prochaine_echeance(self):
        a = sys.modules[self.n.catalogue.get("agents.taches").faire.__module__]
        mardi_10h = time.mktime((2026, 11, 3, 10, 0, 0, 0, 0, -1))
        self.assertEqual(time.strftime("%Y-%m-%d %H:%M", time.localtime(a.prochaine("quotidien", "08:00", 0, mardi_10h))), "2026-11-04 08:00")
        self.assertEqual(time.strftime("%Y-%m-%d %H:%M", time.localtime(a.prochaine("quotidien", "12:00", 0, mardi_10h))), "2026-11-03 12:00")
        self.assertEqual(time.strftime("%Y-%m-%d %H:%M", time.localtime(a.prochaine("hebdomadaire", "08:00", 0, mardi_10h))), "2026-11-09 08:00")
        self.assertEqual(time.strftime("%Y-%m-%d %H:%M", time.localtime(a.prochaine("horaire", "", 0, mardi_10h))), "2026-11-03 11:00")


class PourquoiEnPhrases(actions.Actions):
    def test_rien_d_brut_pour_l_ecran(self):
        self.ex("memoire.ecrire", compte=BEA, categorie="config", cle="nginx-port", valeur="nginx écoute sur le port 8080", nature="constat", provenance="dit")
        self.n.reglages.poser("memoire.seuil_rappel_pct", 5, "")
        r = self.causer("Quel est le port de nginx ? Crée une note.", [self.creer("Port"), texte("Le port est 8080 [M:1].")], agent="itare")
        acte = next(a["evenement"] for a in r["actions"] if a.get("cle") == "notes.creer")
        p = self.agent("pourquoi", compte=BEA, acte=acte)
        self.assertIn("nginx-port", p["memoire"][0]["libelle"])
        self.assertNotRegex(" ".join(p["phrases"]), r"M:\d+")
        self.assertEqual(p["issue_texte"], "L'acte a été fait.")

    def test_une_issue_absente_se_dit(self):
        self.racontee()
        ev = self.db.lire("SELECT evenement FROM agent_actes ORDER BY evenement DESC LIMIT 1")[0]["evenement"]
        p = self.agent("pourquoi", compte=BEA, acte=ev)
        self.assertNotIn("inconnue", p["issue_texte"])
        self.assertTrue(p["issue_texte"])

    def test_un_souvenir_disparu_ne_montre_pas_son_identifiant(self):
        self.db.ecrire("INSERT OR REPLACE INTO agent_actes(evenement, compte, agent, capacite, conversation_id, tour, declencheur, memoires, palier, niveau, confirmer, proposition_id, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (987001, BEA, "itare", "notes.creer", 0, 0, "tour", "[4242]", "auto", "entretien", 0, 0, time.time()))
        p = self.agent("pourquoi", compte=BEA, acte=987001)
        self.assertEqual(p["issue_texte"], "sans issue enregistrée")
        self.assertNotIn("4242", " ".join(p["phrases"]))


class MauvaisJour(actions.Actions):
    def maintenant(self):
        return self.agent("regles", compte=ROOT)["mauvais_jour"]

    def test_seul_l_administrateur_le_pose_et_la_duree_est_bornee(self):
        self.refuse("mauvais_jour", compte=BEA, duree_h=2)
        self.assertFalse(self.maintenant()["actif"])
        for faux in (-1, 721, "x", True):
            self.assertEqual(self.refuse("mauvais_jour", compte=ROOT, duree_h=faux)["statut"], "echec", faux)

    def test_tous_les_agents_racontent_sans_toucher_aux_reglages_et_la_levee_dit_ce_qui_a_change(self):
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="auto")
        avant = [dict(r) for r in self.db.lire("SELECT * FROM agent_paliers ORDER BY agent, compte, outil")]
        etat = self.regler("mauvais_jour", compte=ROOT, duree_h=0)
        self.assertTrue(etat["actif"])
        self.assertEqual(etat["jusqua"], 0)
        r = self.causer("Crée une note", [self.creer("Pas aujourd'hui"), texte("Je te la propose.")], agent="itare")
        self.assertEqual(r["actions"][0]["statut"], "racontee")
        self.assertEqual(self.notes(), [])
        self.assertEqual([dict(x) for x in self.db.lire("SELECT * FROM agent_paliers ORDER BY agent, compte, outil")], avant)         # les réglages d'origine n'ont pas bougé
        self.assertTrue(self.agent("regles", compte=BEA)["mauvais_jour"]["actif"])
        self.assertEqual(self.agent("regles", compte=BEA)["mauvais_jour"]["raconte"], [{"agent": "itare", "capacite": "notes.creer", "fois": 1}])
        bilan = self.regler("mauvais_jour_lever", compte=ROOT)
        self.assertFalse(bilan["actif"])
        self.assertEqual(bilan["raconte"], [{"agent": "itare", "capacite": "notes.creer", "fois": 1}])
        r = self.causer("Crée une note", [self.creer("Maintenant oui"), texte("Fait.")], agent="itare")
        self.assertEqual(r["actions"][0]["statut"], "faite")
        self.assertIn("agents.mauvais_jour", [e.get("objet_id") for e in self.evts("capacite.faite")])           # le journal garde les deux gestes
        self.assertIn("agents.mauvais_jour_lever", [e.get("objet_id") for e in self.evts("capacite.faite")])
        self.refuse("mauvais_jour_lever", compte=ROOT)                                                          # ce n'est plus un mauvais jour

    def test_le_retour_est_automatique_a_l_echeance(self):
        self.regler("mauvais_jour", compte=ROOT, duree_h=2)
        m = self.maintenant()
        self.assertTrue(m["actif"])
        self.assertAlmostEqual(m["jusqua"] - m["depuis"], 2 * 3600, delta=5)
        import json
        brut = json.loads(self.db.lire("SELECT valeur FROM agents_regles WHERE cle='mauvais_jour'")[0]["valeur"])
        brut["jusqua"] = time.time() - 1
        self.db.ecrire("UPDATE agents_regles SET valeur=? WHERE cle='mauvais_jour'", (json.dumps(brut),))
        self.assertFalse(self.maintenant()["actif"])
        r = self.causer("Crée une note", [self.creer("Après l'échéance"), texte("Fait.")], agent="itare")
        self.assertEqual(r["actions"][0]["statut"], "faite")

    def test_la_pose_se_defait(self):
        self.ex("agents.mauvais_jour", compte=ROOT, duree_h=1)
        fait = next(e for e in self.evts("capacite.faite") if e.get("objet_id") == "agents.mauvais_jour")
        self.assertEqual(self.n.executeur.defaire_acte(fait["id"], ROOT)["statut"], "defaite")
        self.assertFalse(self.maintenant()["actif"])


class TachesAutomatiques(actions.Actions):
    def moteur(self):
        f = [f for m, mo, f in self.n.moteurs if m == "agents" and mo.id == "taches"][0]
        return lambda: f(self.n.executeur.contextes["agents"])

    def vieillir(self, tache, jours=2):
        self.db.ecrire("UPDATE taches_agents SET cree=? WHERE id=?", (time.time() - jours * 86400, tache))

    def test_une_tache_echue_se_joue_seule_sous_le_compte_et_ne_se_rejoue_pas(self):
        t = self.regler("tache_confier", compte=BEA, agent="itare", consigne="Dis bonjour", frequence="quotidien", heure="08:00")["tache"]
        passe = self.moteur()
        passe()
        self.assertIsNone(self.agent("taches", compte=BEA)["taches"][0]["derniere"])               # pas échue : rien
        self.vieillir(t)
        self.faux.reponses += [texte("Bonjour !")]
        passe()
        fiche = self.agent("taches", compte=BEA)
        self.assertTrue(fiche["declenchement_automatique"])
        self.assertIsNotNone(fiche["taches"][0]["derniere"])
        cid = fiche["taches"][0]["conversation_id"]
        self.assertIn("Bonjour !", [m["contenu"] for m in self.msgs(cid)])
        self.assertEqual(self.ex("agents.conversation", compte=LEO, id=cid)["statut"], "echec")     # la conversation est celle du compte de la tâche
        lancees = [e for e in self.evts("tache.lancee") if e["compte"] == BEA]
        self.assertEqual((len(lancees), lancees[0]["donnees"]["automatique"]), (1, True))
        passe()
        self.assertEqual(len([e for e in self.evts("tache.lancee")]), 1)                    # sa prochaine échéance est demain

    def test_la_tache_obeit_aux_paliers_de_l_agent(self):
        t = self.regler("tache_confier", compte=BEA, agent="itare", consigne="Crée une note", frequence="quotidien")["tache"]
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="raconter")
        self.vieillir(t)
        self.faux.reponses += [self.creer("Automatique"), texte("Proposée.")]
        self.moteur()()
        self.assertEqual(self.notes(), [])                                                         # racontée, pas faite : le palier de l'agent s'applique
        self.assertEqual(self.props()[0]["capacite"], "notes.creer")

    def test_un_mauvais_jour_retient_aussi_les_taches(self):
        t = self.regler("tache_confier", compte=BEA, agent="itare", consigne="Crée une note", frequence="quotidien")["tache"]
        self.vieillir(t)
        self.regler("mauvais_jour", compte=ROOT)
        self.faux.reponses += [self.creer("Pas aujourd'hui"), texte("Proposée.")]
        self.moteur()()
        self.assertEqual(self.notes(), [])

    def test_une_tache_qui_echoue_ne_ferme_pas_la_passe_des_autres(self):
        a = self.regler("tache_confier", compte=BEA, agent="itare", consigne="Première", frequence="quotidien")["tache"]
        b = self.regler("tache_confier", compte=BEA, agent="itare", consigne="Seconde", frequence="quotidien")["tache"]
        self.vieillir(a)
        self.vieillir(b)
        self.faux.reponses += [(500, {"error": "panne"}), (500, {"error": "panne"}), (500, {"error": "panne"}), texte("Seconde faite.")]
        self.moteur()()
        self.assertTrue(all(t["derniere"] for t in self.agent("taches", compte=BEA)["taches"]))     # les deux ont été tentées


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Regles, Tuile, Taches, PourquoiEnPhrases
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
