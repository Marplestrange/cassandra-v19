# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'équipe d'agents
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #768fd6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'équipe d'agents : droits, capacités de lecture et de réglage, coût par jour, plafonds, cloisonnement, et l'absence d'outil de secret chez Itare et les agents invités.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=768fd6 ▼▼▼
"""Bancs de l'équipe d'agents : droits, capacités de lecture et de réglage, coût par jour, plafonds, cloisonnement, et l'absence d'outil de secret chez Itare et les agents invités."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

import CN_main as moteur                                          # noqa: E402
import CN_test_agents as base                                     # noqa: E402
from CN_test_agents import BEA, LEO, ROOT, FauxModele, appel, texte    # noqa: E402

CLE_SECOURS = "sk-LE-SECOURS"
CAPS_ECRITURE = ("agent_regler", "palier_regler", "niveau_regler", "plafond_regler")
CAPS_LECTURE = ("equipe", "agent", "couts", "paliers")


class Equipe(base.Monde):
    def setUp(self):
        super().setUp()
        self.jour = [1_800_000_000.0]
        mod = sys.modules[self.n.catalogue.get("agents.equipe").faire.__module__].eq          # CN_equipe, tel que le noyau l'a chargé
        self.eq = mod
        self._avant = mod.maintenant
        mod.maintenant = lambda: self.jour[0]
        self.addCleanup(setattr, mod, "maintenant", self._avant)
        # un modèle de secours, lié à son propre rôle, pour reconnaître à la clé lequel a parlé
        mid = self.ex("modeles.instance_ajouter", compte=ROOT, fournisseur="personnalise", nom="secours", cle=CLE_SECOURS, base_url=self.faux.url)["resultat"]["id"]
        self.ex("modeles.role_lier", compte=ROOT, role="secours", modele_id=mid)
        cit = self.ex("modeles.instance_ajouter", compte=ROOT, fournisseur="personnalise", nom="citadelle", cle="sk-citadelle", base_url=self.faux.url)["resultat"]["id"]
        self.ex("modeles.role_lier", compte=ROOT, role="itare_citadelle", modele_id=cit)             # Itare parle par ce rôle quand le compte n'a pas choisi son modèle

    def refuse(self, cap, compte=BEA, **args):
        r = self.ex("agents." + cap, compte=compte, **args)
        self.assertNotEqual(r["statut"], "faite", (cap, args, r))
        return r

    def regler(self, cap, compte=ROOT, **args):
        r = self.ex("agents." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def tarifs_chers(self, agent="cassandra", compte=ROOT):
        """Un tour du faux modèle (5 jetons en entrée, 3 en sortie) coûte 0,8 centime."""
        self.regler("agent_regler", compte=compte, id=agent, champs={"limites": {"tarif_entree_cts": 100000, "tarif_sortie_cts": 100000}})

    def cles(self):
        return [r["auth"] for r in self.faux.requetes]


class Droits(Equipe):
    def test_chaque_capacite_nomme_un_droit_du_module(self):
        m = self.n.executeur.contextes["agents"].manifeste
        ids = {d.id for d in m.droits}
        self.assertTrue({"utiliser", "valider", "regler_agent", "administrer"} <= ids)
        for c in m.capacites:
            self.assertIn(c.droit.replace("agents.", ""), ids, c.id)
        for cap in CAPS_LECTURE + CAPS_ECRITURE:
            self.assertTrue(m.capacite(cap).droit, cap)

    def test_les_reglages_ne_sont_jamais_a_la_portee_d_un_agent(self):
        m = self.n.executeur.contextes["agents"].manifeste
        for cap in CAPS_ECRITURE:
            self.assertEqual(set(m.capacite(cap).qui), {"humain", "compte"}, cap)
            for acteur in ("itare", "cassandra", "agent"):
                self.assertEqual(self.n.executeur.executer("agents." + cap, acteur, {"agent": "itare", "id": "itare"}, compte=BEA)["statut"], "refuse")
        outils = {t["cle"] for t in self.ctx.outils("itare")} | {t["cle"] for t in self.ctx.outils("cassandra")}
        self.assertEqual({c for c in outils if c.startswith("agents.")}, {"agents.passer_la_main"})          # le seul outil du module : passer la main à Amizo

    def test_plafond_regler_demande_administrer(self):
        r = self.ex("agents.plafond_regler", compte=BEA, portee="global", euros=5)
        self.assertEqual(r["statut"], "refuse")
        self.assertEqual(r.get("droit"), "agents.administrer")


class Lectures(Equipe):
    def test_equipe_de_l_administrateur_et_d_un_compte_ordinaire(self):
        ids = lambda r: [a["id"] for a in r["equipe"]]            # noqa: E731
        admin = self.agent("equipe", compte=ROOT)
        self.assertEqual(ids(admin), ["cassandra", "itare", "amizo", "relecteur", "vision"])
        self.assertTrue(admin["administrateur"])
        self.assertEqual({a["genre"] for a in admin["equipe"]}, {"agent", "service"})
        cassandra = admin["equipe"][0]
        self.assertEqual((cassandra["nom"], cassandra["niveau"], cassandra["modele"]), ("Cassandra", "reine", "principal"))
        self.assertTrue(cassandra["nb_outils"] > 0)
        self.assertEqual(set(cassandra["outils"]), {"lecture", "auto", "raconter", "maitre", "retire"})
        self.assertEqual(cassandra["cout_jour"]["euros"], 0)
        simple = self.agent("equipe", compte=BEA)
        self.assertEqual(ids(simple), ["itare"])
        self.assertFalse(simple["administrateur"])

    def test_agent_et_paliers(self):
        f = self.agent("agent", compte=BEA, id="itare")
        self.assertEqual((f["agent"]["id"], f["agent"]["nom"], f["agent"]["niveau"]), ("itare", "Itare", "entretien"))
        cles = {o["cle"] for o in f["outils"]}
        self.assertIn("notes.creer", cles)
        p = {x["cle"]: x for x in self.agent("paliers", compte=BEA, id="itare")["paliers"]}
        self.assertEqual((p["notes.creer"]["palier"], p["notes.creer"]["confirmer"], p["notes.creer"]["pose"]), ("auto", False, False))
        self.assertEqual(p["notes.lister"]["palier"], "lecture")
        self.assertNotIn("plafond", f)                              # les plafonds sont l'affaire de l'administrateur
        self.assertIn("plafond", self.agent("agent", compte=ROOT, id="cassandra"))

    def test_un_agent_inconnu_et_les_agents_sans_outils(self):
        self.refuse("agent", compte=ROOT, id="fantome")
        self.assertEqual([p["cle"] for p in self.agent("paliers", compte=ROOT, id="amizo")["paliers"]], ["agents.transmettre"])          # dans ce banc, sans web ni bibliothèque : le seul outil du module

    def test_couts_par_jour_et_par_agent(self):
        self.tarifs_chers()
        self.causer("Un", [texte("a")], compte=ROOT)
        self.causer("Deux", [texte("b")], compte=ROOT)
        c = self.agent("couts", compte=ROOT, id="cassandra", jours=3)
        self.assertEqual(len(c["jours"]), 1)
        self.assertEqual((c["jours"][0]["agent"], c["jours"][0]["appels"], c["jours"][0]["entrees"], c["jours"][0]["sorties"]), ("cassandra", 2, 10, 6))
        self.assertAlmostEqual(c["total_euros"], 0.016, places=4)
        self.jour[0] += 86400
        self.causer("Trois", [texte("c")], compte=ROOT)
        c = self.agent("couts", compte=ROOT, id="cassandra", jours=3)
        self.assertEqual([j["appels"] for j in c["jours"]], [1, 2])          # le plus récent d'abord
        self.assertAlmostEqual(c["aujourdhui_euros"], 0.008, places=4)
        self.assertEqual(self.agent("couts", compte=ROOT, jours=1)["jours"][0]["appels"], 1)

    def test_les_tarifs_par_defaut_comptent_aussi(self):
        self.causer("Un", [texte("a")], compte=ROOT)
        self.assertGreater(self.agent("couts", compte=ROOT)["total_euros"], 0)


class Reglages(Equipe):
    def test_agent_regler_prouve_et_se_defait(self):
        r = self.regler("agent_regler", compte=BEA, id="itare", champs={"nom_affiche": "Rita", "ton": "Sois brève.", "modele": "principal", "secours": "secours", "limites": {"max_tours": 3}})
        self.assertIsNone(r["avant"])
        f = self.agent("agent", compte=BEA, id="itare")["agent"]
        self.assertEqual((f["nom"], f["nom_origine"], f["ton"], f["modele"], f["secours"], f["limites"]), ("Rita", "Itare", "Sois brève.", "principal", "secours", {"max_tours": 3}))
        self.assertEqual(self.agent("equipe", compte=BEA)["equipe"][0]["nom"], "Rita")
        cap = self.n.catalogue.get("agents.agent_regler")
        self.assertTrue(cap.prouver(self.ctx, r))
        r2 = self.regler("agent_regler", compte=BEA, id="itare", champs={"ton": ""})          # vide : on retombe sur l'héritage
        self.assertEqual(self.agent("agent", compte=BEA, id="itare")["agent"]["ton"], "")
        cap.defaire(self.ctx, r2)
        self.assertEqual(self.agent("agent", compte=BEA, id="itare")["agent"]["ton"], "Sois brève.")
        cap.defaire(self.ctx, r)
        self.assertEqual(self.agent("agent", compte=BEA, id="itare")["agent"]["nom"], "Itare")

    def test_validations(self):
        for champs in ({}, {"inconnu": 1}, {"nom_affiche": ""}, {"nom_affiche": "x" * 41}, {"modele": "a b;rm"}, {"limites": {"max_tours": 0}}, {"limites": {"max_tours": 41}},
                       {"limites": {"max_tours": True}}, {"limites": {"inconnue": 1}}, {"limites": [1]}, {"ton": "x" * 2001}):
            self.refuse("agent_regler", id="itare", champs=champs)
        self.refuse("niveau_regler", agent="itare", niveau="dieu")
        self.refuse("palier_regler", agent="itare", outil="notes.creer", palier="maitre")
        self.refuse("palier_regler", agent="itare", outil="notes.creer")
        self.refuse("palier_regler", agent="itare", outil="notes.inexistante", palier="raconter")
        self.refuse("palier_regler", agent="itare", outil="notes.lister", palier="raconter")        # une lecture n'a pas de palier raconter
        self.refuse("palier_regler", agent="itare", outil="notes.creer", palier="retire", confirmer=True)
        for euros in (0, -1, True):
            self.refuse("plafond_regler", compte=ROOT, portee="global", euros=euros)
        self.refuse("plafond_regler", compte=ROOT, portee="global", euros=1, action="exploser")
        self.refuse("plafond_regler", compte=ROOT, portee="fantome", euros=1)

    def test_palier_regler_pose_retire_et_se_defait(self):
        cap = self.n.catalogue.get("agents.palier_regler")
        r = self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="raconter")
        p = {x["cle"]: x for x in self.agent("paliers", compte=BEA, id="itare")["paliers"]}["notes.creer"]
        self.assertEqual((p["palier"], p["pose"], p["defaut"]), ("raconter", True, "auto"))
        self.assertTrue(cap.prouver(self.ctx, r))
        r2 = self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", confirmer=True)    # le palier posé reste, la confirmation s'ajoute
        p = {x["cle"]: x for x in self.agent("paliers", compte=BEA, id="itare")["paliers"]}["notes.creer"]
        self.assertEqual((p["palier"], p["confirmer"]), ("raconter", True))
        cap.defaire(self.ctx, r2)
        cap.defaire(self.ctx, r)
        p = {x["cle"]: x for x in self.agent("paliers", compte=BEA, id="itare")["paliers"]}["notes.creer"]
        self.assertEqual((p["palier"], p["pose"], p["confirmer"]), ("auto", False, False))
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="retire")
        self.assertEqual(self.agent("equipe", compte=BEA)["equipe"][0]["outils"]["retire"], 1)
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="defaut")
        self.assertEqual(self.agent("equipe", compte=BEA)["equipe"][0]["outils"]["retire"], 0)

    def test_niveau_regler_se_defait(self):
        r = self.regler("niveau_regler", compte=BEA, agent="itare", niveau="observer")
        self.assertEqual(self.agent("agent", compte=BEA, id="itare")["agent"]["niveau"], "observer")
        self.n.catalogue.get("agents.niveau_regler").defaire(self.ctx, r)
        self.assertEqual(self.agent("agent", compte=BEA, id="itare")["agent"]["niveau"], "entretien")

    def test_plafond_regler_pose_leve_et_se_defait(self):
        cap = self.n.catalogue.get("agents.plafond_regler")
        r = self.regler("plafond_regler", portee="global", euros=2.5, action="arret")
        self.assertEqual((r["apres"]["centimes"], r["apres"]["action"]), (250, "arret"))
        self.assertEqual(self.agent("couts", compte=ROOT)["plafonds"]["global"], {"euros": 2.5, "action": "arret", "accord_jour": ""})
        self.assertTrue(cap.prouver(self.ctx, r))
        r2 = self.regler("plafond_regler", portee="itare", euros=1)
        cap.defaire(self.ctx, r2)
        self.assertNotIn("itare", self.agent("couts", compte=ROOT)["plafonds"])
        self.regler("plafond_regler", portee="global")                                 # sans montant : le plafond est levé
        self.assertEqual(self.agent("couts", compte=ROOT)["plafonds"], {})
        cap.defaire(self.ctx, r)                                                       # le retour remet celui d'avant (aucun)
        self.assertEqual(self.agent("couts", compte=ROOT)["plafonds"], {})


class Cloisonnement(Equipe):
    def test_un_compte_ordinaire_n_agit_que_sur_son_itare(self):
        for cap, args in (("agent", dict(id="cassandra")), ("paliers", dict(id="amizo")), ("couts", dict(id="cassandra")),
                          ("agent_regler", dict(id="cassandra", champs={"ton": "x"})), ("agent_regler", dict(id="relecteur", champs={"ton": "x"})),
                          ("niveau_regler", dict(agent="cassandra", niveau="observer")), ("palier_regler", dict(agent="cassandra", outil="notes.creer", palier="retire"))):
            self.refuse(cap, **args)
        self.assertEqual(self.agent("equipe", compte=BEA)["equipe"][0]["id"], "itare")

    def test_l_administrateur_regle_cassandra_amizo_et_les_services(self):
        self.regler("agent_regler", id="cassandra", champs={"nom_affiche": "Cass", "secours": "secours"})
        self.regler("agent_regler", id="amizo", champs={"ton": "Cite tes sources."})
        self.regler("agent_regler", id="relecteur", champs={"modele": "principal"})
        self.regler("niveau_regler", agent="vision", niveau="entretien")
        self.assertEqual(self.agent("agent", compte=ROOT, id="cassandra")["agent"]["nom"], "Cass")
        self.assertEqual([a["nom"] for a in self.agent("equipe", compte=ROOT)["equipe"]][:1], ["Cass"])

    def test_l_itare_d_un_autre_compte_n_est_jamais_a_portee(self):
        self.regler("agent_regler", compte=BEA, id="itare", champs={"ton": "Ton secret de Bea.", "nom_affiche": "Rita"})
        self.regler("agent_regler", compte=ROOT, id="itare", champs={"nom_affiche": "Max"})                  # l'administrateur règle SON Itare, pas celui de Bea
        self.assertEqual(self.agent("agent", compte=ROOT, id="itare")["agent"]["ton"], "")
        self.assertEqual(self.agent("agent", compte=ROOT, id="itare")["agent"]["nom"], "Max")
        self.assertEqual(self.agent("agent", compte=BEA, id="itare")["agent"]["nom"], "Rita")
        self.assertEqual(self.agent("agent", compte=LEO, id="itare")["agent"]["nom"], "Itare")
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="retire")
        self.assertEqual(self.agent("equipe", compte=ROOT)["equipe"][1]["outils"]["retire"], 0)
        self.assertEqual(self.agent("equipe", compte=LEO)["equipe"][0]["outils"]["retire"], 0)

    def test_les_couts_d_un_compte_ne_montrent_que_son_itare(self):
        self.causer("Bonjour", [texte("a")], agent="itare", compte=BEA)
        self.causer("Bonjour", [texte("b")], agent="itare", compte=LEO)
        self.causer("Bonjour", [texte("c")], compte=ROOT)
        bea = self.agent("couts", compte=BEA)
        self.assertEqual([(j["agent"], j["appels"]) for j in bea["jours"]], [("itare", 1)])
        self.assertNotIn("plafonds", bea)
        total = self.agent("couts", compte=ROOT)
        self.assertEqual(sorted((j["agent"], j["appels"]) for j in total["jours"]), [("cassandra", 1), ("itare", 2)])          # la somme seule : jamais le contenu d'un compte
        self.assertEqual(self.agent("equipe", compte=BEA)["equipe"][0]["cout_jour"]["appels"], 1)


class Paliers(Equipe):
    def creer(self, titre="Une note"):
        return appel("notes__creer", {"titre": titre, "corps": "x"})

    def test_raconter_pose_pour_cet_agent_ne_fait_rien(self):
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="raconter")
        r = self.causer("Crée une note", [self.creer(), texte("Je l'ai racontée.")], agent="itare")
        self.assertEqual(self.notes(), [])
        self.assertEqual(r["actions"][0]["statut"], "racontee")
        outil = [m for m in self.msgs(r["conversation_id"]) if m["role"] == "tool"][0]
        self.assertIn("racont", outil["contenu"].lower())

    def test_confirmer_retient_l_action_et_la_range_en_attente(self):
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", confirmer=True)
        r = self.causer("Crée une note", [self.creer(), texte("J'attends ton accord.")], agent="itare")
        self.assertEqual(self.notes(), [])
        self.assertEqual(r["actions"][0]["statut"], "a_confirmer")
        att = self.db.lire("SELECT * FROM agent_attentes")
        self.assertEqual([(a["agent"], a["compte"], a["genre"], a["outil"], a["etat"]) for a in att], [("itare", BEA, "confirmer", "notes.creer", "attente")])
        self.causer("Encore", [self.creer("Une autre"), texte("Toujours en attente.")], agent="itare")
        self.assertEqual(len(self.db.lire("SELECT * FROM agent_attentes")), 2)          # une autre demande, une autre attente

    def test_retire_enleve_l_outil_a_l_agent(self):
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="retire")
        r = self.causer("Crée une note", [self.creer(), texte("Je ne peux pas.")], agent="itare")
        self.assertEqual(self.notes(), [])
        noms = {t["function"]["name"] for t in self.faux.requetes[0]["corps"]["tools"]}
        self.assertNotIn("notes__creer", noms)
        self.assertIn("inconnu", [m for m in self.msgs(r["conversation_id"]) if m["role"] == "tool"][0]["contenu"].lower())

    def test_le_palier_pose_pour_un_agent_ne_touche_pas_les_autres(self):
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="raconter")
        self.causer("Crée une note", [self.creer(), texte("Fait.")], agent="itare", compte=LEO)
        self.assertEqual([n["titre"] for n in self.notes(LEO)], ["Une note"])

    def test_observer_raconte_toute_ecriture_mais_laisse_les_lectures(self):
        self.regler("niveau_regler", compte=BEA, agent="itare", niveau="observer")
        r = self.causer("Crée une note", [self.creer(), appel("notes__lister", {}), texte("Rien fait.")], agent="itare")
        self.assertEqual(self.notes(), [])
        self.assertEqual(r["actions"][0]["statut"], "racontee")

    def test_le_ton_et_les_limites_de_l_agent_entrent_dans_le_tour(self):
        self.regler("agent_regler", compte=BEA, id="itare", champs={"ton": "Réponds en vers.", "limites": {"max_tours": 1}})
        r = self.causer("Crée deux notes", [self.creer("A"), self.creer("B"), texte("fin")], agent="itare")
        self.assertIn("Réponds en vers.", self.faux.requetes[0]["corps"]["messages"][0]["content"])
        self.assertEqual(len(self.faux.requetes), 1)                                      # max_tours = 1 : une seule étape, puis l'arrêt
        self.assertTrue([m for m in self.msgs(r["conversation_id"]) if m["role"] == "panne"])

    def test_modele_principal_et_secours_de_l_agent(self):
        self.regler("agent_regler", id="cassandra", champs={"modele": "secours"})
        self.causer("Bonjour", [texte("ok")], compte=ROOT)
        self.assertEqual(self.cles(), ["Bearer " + CLE_SECOURS])
        self.faux.requetes.clear()
        self.regler("agent_regler", id="cassandra", champs={"modele": "principal", "secours": "secours"})
        self.causer("Bonjour", [(500, {"error": "panne"}), texte("repris")], compte=ROOT)
        self.assertEqual(self.cles(), ["Bearer " + base.CLE_ROLE, "Bearer " + CLE_SECOURS])


class Plafonds(Equipe):
    def test_verdict_pur_le_plus_bas_donne_l_action(self):
        v = self.eq.verdict_plafond
        pl = {"global": {"centimes": 300, "action": "arret", "accord_jour": ""}, "itare": {"centimes": 100, "action": "secours", "accord_jour": ""}}
        self.assertIsNone(v(pl, {"global": 50, "itare": 50}, "itare", "j"))
        self.assertEqual(v(pl, {"global": 50, "itare": 100}, "itare", "j")["action"], "secours")
        self.assertEqual(v(pl, {"global": 300, "itare": 50}, "itare", "j")["portee"], "global")
        self.assertEqual(v(pl, {"global": 300, "itare": 100}, "itare", "j")["portee"], "itare")            # les deux atteints : le plus bas
        self.assertEqual(v(pl, {"global": 300}, "cassandra", "j")["portee"], "global")
        pl["global"] = {"centimes": 300, "action": "accord", "accord_jour": "j"}
        self.assertIsNone(v(pl, {"global": 400}, "cassandra", "j"))                                         # accord donné aujourd'hui
        self.assertIsNotNone(v(pl, {"global": 400}, "cassandra", "demain"))

    def test_au_plafond_secours_l_agent_passe_sur_son_modele_de_secours(self):
        self.tarifs_chers()
        self.regler("agent_regler", id="cassandra", champs={"secours": "secours"})
        self.regler("plafond_regler", portee="cassandra", euros=0.01, action="secours")        # 1 centime : atteint au deuxième tour
        self.causer("Un", [texte("a")], compte=ROOT)
        self.causer("Deux", [texte("b")], compte=ROOT)
        self.causer("Trois", [texte("c")], compte=ROOT)
        self.assertEqual(self.cles(), ["Bearer " + base.CLE_ROLE, "Bearer " + base.CLE_ROLE, "Bearer " + CLE_SECOURS])
        self.jour[0] += 86400                                                                   # le lendemain, le compteur repart
        self.causer("Quatre", [texte("d")], compte=ROOT)
        self.assertEqual(self.cles()[-1], "Bearer " + base.CLE_ROLE)

    def test_au_plafond_arret_itare_s_arrete_mais_pas_cassandra(self):
        self.tarifs_chers("cassandra")
        self.tarifs_chers("itare")
        self.regler("plafond_regler", portee="global", euros=0.01, action="arret")
        self.causer("Un", [texte("a")], compte=ROOT)
        self.causer("Deux", [texte("b")], compte=ROOT)
        n = len(self.faux.requetes)
        r = self.causer("Trois", [texte("c")], agent="itare", compte=BEA)
        self.assertEqual((len(self.faux.requetes), r["texte"], r["actions"][0]["action"]), (n, "", "arret"))
        self.faux.reponses.clear()
        self.assertIn("arrêté", [m for m in self.msgs(r["conversation_id"], BEA) if m["role"] == "panne"][0]["contenu"])
        r = self.causer("Quatre", [texte("d")], compte=ROOT)
        self.assertEqual(r["texte"], "d")                                                        # Cassandra n'est jamais coupée (ici : pas de secours, elle garde son modèle)
        self.assertEqual(len(self.faux.requetes), n + 1)

    def test_le_plafond_global_est_partage_et_le_plus_bas_gagne(self):
        self.tarifs_chers("cassandra")
        self.regler("plafond_regler", portee="global", euros=0.02, action="arret")
        self.regler("plafond_regler", portee="cassandra", euros=1, action="arret")
        self.causer("Un", [texte("a")], compte=ROOT)
        self.causer("Deux", [texte("b")], compte=ROOT)
        # global = 2 centimes, non atteint (1,6) ; l'agent a 100 centimes : rien ne retient
        self.assertEqual(self.agent("equipe", compte=ROOT)["equipe"][0]["plafond_atteint"], False)
        self.causer("Trois", [texte("c")], compte=ROOT)
        self.assertEqual(self.agent("equipe", compte=ROOT)["equipe"][0]["plafond_atteint"], True)
        self.assertEqual(self.agent("equipe", compte=BEA)["equipe"][0]["plafond_atteint"], True)        # le plafond global retient aussi Itare

    def test_au_plafond_accord_l_agent_attend_puis_l_accord_du_jour_le_libere(self):
        self.tarifs_chers()
        self.regler("plafond_regler", portee="cassandra", euros=0.01, action="accord")
        self.causer("Un", [texte("a")], compte=ROOT)
        self.causer("Deux", [texte("b")], compte=ROOT)
        n = len(self.faux.requetes)
        r = self.causer("Trois", [texte("c")], compte=ROOT)
        self.assertEqual((len(self.faux.requetes), r["texte"], r["actions"][0]["action"]), (n, "", "accord"))
        self.faux.reponses.clear()
        self.assertEqual([(a["genre"], a["agent"]) for a in self.db.lire("SELECT * FROM agent_attentes")], [("plafond", "cassandra")])
        self.refuse("plafond_regler", compte=BEA, portee="cassandra", accorder=True)
        acc = self.regler("plafond_regler", portee="cassandra", accorder=True)
        r = self.causer("Quatre", [texte("d")], compte=ROOT)
        self.assertEqual(r["texte"], "d")
        self.n.catalogue.get("agents.plafond_regler").defaire(self.ctx, acc)                        # l'accord se retire
        self.assertEqual(self.causer("Cinq", [texte("e")], compte=ROOT)["texte"], "")

    def test_accorder_sans_plafond_est_refuse(self):
        self.refuse("plafond_regler", compte=ROOT, portee="global", accorder=True)


class Secrets(Equipe):
    """Cassandra seule tient le coffre : ni Itare ni un agent invité n'ont un seul outil de secret."""

    def setUp(self):
        super().setUp()
        if not (RACINE / "modules" / "coffre").is_dir():
            self.skipTest("pas de module coffre")
        for m in ("droits", "comptes", "societes", "coffre"):
            if not (Path(self.tmp.name) / "modules" / m).is_dir():
                shutil.copytree(RACINE / "modules" / m, Path(self.tmp.name) / "modules" / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n.brancher()
        r = self.n.activer("coffre")
        self.assertTrue(r["ok"], r)

    def test_aucun_outil_de_secret_pour_itare_ni_pour_un_agent_invite(self):
        cassandra = {t["nom"] for t in self.ctx.outils("cassandra")}
        self.assertTrue([n for n in cassandra if n.startswith("coffre__")], "le banc doit contenir le coffre, sinon ce test ne prouve rien")
        for acteur in ("itare", "agent"):
            self.assertEqual([t["nom"] for t in self.ctx.outils(acteur) if t["nom"].startswith("coffre__")], [], acteur)

    def test_le_tour_d_itare_ne_presente_aucun_outil_de_secret(self):
        self.causer("Bonjour", [texte("Bonjour")], agent="itare")
        noms = {t["function"]["name"] for t in self.faux.requetes[0]["corps"]["tools"]}
        self.assertFalse([n for n in noms if n.startswith("coffre__")])
        self.assertIn("outil_cherche", noms)                       # les outils de bureau sont présentés (ou joignables par outil_cherche) : seul le secret manque


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Equipe, Droits, Lectures, Reglages, Cloisonnement, Paliers, Plafonds, Secrets
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
