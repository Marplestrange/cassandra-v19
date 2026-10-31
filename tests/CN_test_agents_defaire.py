# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Défaire un acte d'agent (`agents
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #2c6130
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Défaire un acte d'agent (`agents.defaire`) et l'Auditeur (service agentique en lecture seule).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2c6130 ▼▼▼
"""Défaire un acte d'agent (`agents.defaire`) et l'Auditeur (service agentique en lecture seule).

  - DÉFAIRE : le retour arrière d'un acte déjà fait, une seule fois, raconté au journal ; le cloisonnement est celui de « Pourquoi ? » ; un acte qui n'a rien fait ne se défait pas ;
    la capacité se déclare au palier « raconter », sous un droit, pour l'utilisateur seulement (jamais pour un agent).
  - AUDITEUR : déclaré comme le Relecteur et Vision (service, sans outil), lecture seule, plafonné ; ses trois regards se calculent à part et se bornent.
"""
import sys
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

import CN_test_agents_actions as actions                           # noqa: E402
from CN_test_agents import BEA, LEO, ROOT, texte                  # noqa: E402


class Defaire(actions.Actions):
    def acte_de(self, titre="Une note", compte=BEA):
        r = self.causer("Crée une note", [self.creer(titre), texte("Fait.")], agent="itare" if compte == BEA else "cassandra", compte=compte)
        return next(a["evenement"] for a in r["actions"] if a.get("cle") == "notes.creer")

    def titres(self, compte=BEA):
        r = self.ex("notes.lister", compte=compte)
        self.assertEqual(r["statut"], "faite", r)
        return str(r["resultat"])

    def test_la_capacite_est_declaree_au_palier_raconter_sous_un_droit_pour_l_utilisateur_seulement(self):
        e = self.n.catalogue.get("agents.defaire")
        self.assertTrue(e.capacite.ecrit)
        self.assertEqual((e.capacite.droit, tuple(e.capacite.qui)), ("agents.utiliser", ("humain", "compte")))
        self.assertEqual(self.n.catalogue.savoir("agents.defaire")["palier"], "raconter")
        self.assertNotIn("agents.defaire", {o["cle"] for acteur in ("itare", "cassandra", "amizo") for o in self.ctx.outils(acteur)})

    def test_un_acte_se_defait_une_fois_et_se_raconte(self):
        acte = self.acte_de("A défaire")
        self.assertIn("A défaire", self.titres())
        r = self.regler("defaire", compte=BEA, acte=acte, raison="je n'en voulais pas")
        self.assertEqual((r["acte"], r["agent"], r["capacite"], r["defait"]), (acte, "itare", "notes.creer", True))
        self.assertNotIn("A défaire", self.titres())                                                 # le retour arrière de la capacité a joué
        defaites = [e for e in self.evts("capacite.defaite") if e["compte"] == BEA]
        self.assertEqual(len(defaites), 1)
        self.assertEqual(defaites[0]["acteur"], "humain")
        p = self.agent("pourquoi", compte=BEA, acte=acte)
        self.assertEqual(p["retour"], "defaite")                                                      # « Pourquoi ? » le dit
        self.assertIn("capacite.defaite", [j["type"] for j in p["journal"]])
        deux = self.refuse("defaire", compte=BEA, acte=acte)                                          # une seule fois
        self.assertIn("déjà défait", deux["erreur"])
        self.assertEqual(len(self.evts("capacite.defaite")), 1)

    def test_l_acte_d_un_autre_compte_ne_se_defait_pas(self):
        acte = self.acte_de("Privée")
        for compte in (LEO, ROOT):
            self.assertEqual(self.refuse("defaire", compte=compte, acte=acte)["statut"], "echec", compte)
        self.assertIn("Privée", self.titres())
        self.assertEqual(self.evts("capacite.defaite"), [])
        for faux in (0, 987654, "x"):
            self.refuse("defaire", compte=BEA, acte=faux)

    def test_l_administrateur_defait_l_acte_de_cassandra(self):
        acte = self.acte_de("Machine", compte=ROOT)
        self.assertEqual(self.refuse("defaire", compte=BEA, acte=acte)["statut"], "echec")
        self.assertTrue(self.regler("defaire", compte=ROOT, acte=acte)["defait"])
        self.assertNotIn("Machine", self.titres(ROOT))

    def test_un_acte_qui_n_a_rien_fait_ne_se_defait_pas(self):
        self.regler("palier_regler", compte=BEA, agent="itare", outil="notes.creer", palier="raconter")
        self.causer("Crée une note", [self.creer("Racontée"), texte("Proposée.")], agent="itare")
        ev = self.db.lire("SELECT evenement FROM agent_actes ORDER BY evenement DESC LIMIT 1")[0]["evenement"]
        r = self.refuse("defaire", compte=BEA, acte=ev)
        self.assertIn("rien à défaire", r["erreur"])

    def test_un_agent_ne_se_defait_pas_lui_meme(self):
        acte = self.acte_de("Intouchable")
        r = self.n.executeur.executer("agents.defaire", "itare", {"acte": acte}, compte=BEA)
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("Intouchable", self.titres())

    def test_un_acte_deja_annule_par_le_noyau_n_est_pas_rejoue(self):
        acte = self.acte_de("Une fois")
        fait = next(e for e in self.evts("capacite.faite") if e.get("cause") == acte)
        self.n.bus.emettre("capacite.annulee", source="notes", acteur="noyau", objet=("capacite", "notes.creer"), cause=fait["id"], donnees={}, compte=BEA)
        self.assertIn("déjà défait", self.refuse("defaire", compte=BEA, acte=acte)["erreur"])


class Auditeur(actions.Actions):
    def test_declare_comme_le_relecteur_et_vision(self):
        defs = {a["id"]: a for a in self.eq.DONNEES["agents"]}
        for sid in ("relecteur", "vision", "auditeur"):
            self.assertEqual((defs[sid]["genre"], defs[sid]["acteur_outils"], defs[sid]["niveau_defaut"], defs[sid]["portee"]), ("service", "", "observer", "instance"), sid)
            self.assertIn(sid, self.eq.DONNEES["services"])
        s = self.eq.DONNEES["services"]["auditeur"]
        self.assertTrue(s["lecture_seule"])
        self.assertEqual(s["controles"], ["cout_derive", "palier_large", "injection_repetee"])
        self.assertEqual(sorted(s["plafonds"]), ["fil", "jetons", "jours_max", "lignes_max", "signaux_max", "tours"])
        self.assertIn("auditeur", {a["id"] for a in self.agent("equipe", compte=ROOT)["equipe"]})

    def test_il_n_a_aucun_outil_et_n_ecrit_rien(self):
        self.assertEqual(self.ctx.outils("auditeur"), [])
        e = self.n.catalogue.get("agents.auditer")
        self.assertFalse(e.capacite.ecrit)
        self.assertEqual(e.capacite.droit, "agents.administrer")

    def test_administrateur_seulement(self):
        r = self.agent("auditer", compte=ROOT)
        self.assertEqual((r["lecture_seule"], r["signaux"]), (True, []))
        self.assertEqual(r["regards"], ["cout_derive", "palier_large", "injection_repetee"])
        for compte in (BEA, LEO):
            self.assertNotEqual(self.ex("agents.auditer", compte=compte)["statut"], "faite", compte)

    def test_ses_trois_regards(self):
        a = sys.modules[self.n.catalogue.get("agents.auditer").faire.__module__]
        couts = [{"jour": "2026-10-28", "agent": "itare", "centimes": 4}, {"jour": "2026-10-29", "agent": "itare", "centimes": 6}, {"jour": "2026-10-30", "agent": "itare", "centimes": 30},
                 {"jour": "2026-10-29", "agent": "cassandra", "centimes": 1}, {"jour": "2026-10-30", "agent": "cassandra", "centimes": 3}]
        defaites = [{"id": 11, "capacite": "notes.creer", "agent": "itare"}, {"id": 12, "capacite": "notes.creer", "agent": "itare"}, {"id": 13, "capacite": "notes.supprimer", "agent": "itare"}]
        relectures = [{"id": i, "agent": "amizo", "compte": ROOT, "motifs": ["ordre_cache"]} for i in (1, 2, 3)] + [{"id": 4, "agent": "itare", "compte": BEA, "motifs": ["secret"]}]
        s = a.analyser(couts, defaites, {("itare", "notes.creer"), ("itare", "notes.supprimer")}, relectures)
        self.assertEqual([x["type"] for x in s], ["cout_derive", "palier_large", "injection_repetee"])
        self.assertEqual((s[0]["agent"], s[1]["capacite"], s[1]["journal"], s[2]["ref"]), ("itare", "notes.creer", 12, "relectures:3"))
        self.assertTrue(all(x["phrase"] for x in s))
        self.assertNotIn("cassandra", [x.get("agent") for x in s])                    # trois centimes de plus ne sont pas une dérive
        self.assertEqual(a.analyser(couts, defaites, set(), relectures[:2]), [s[0]])  # sans palier « auto » ni trois retenues : rien de plus
        self.assertEqual(len(a.analyser(couts, defaites, {("itare", "notes.creer")}, relectures, {"signaux_max": 1})), 1)         # le plafond de signaux borne la sortie

    def test_il_lit_le_journal_et_les_retenues_du_relecteur(self):
        for i in range(3):
            self.db.ecrire("INSERT INTO relectures(agent, compte, conversation_id, tour, verdict, motifs, ts) VALUES (?,?,?,?,?,?,?)", ("amizo", ROOT, 0, i, "retenue", '["ordre_cache"]', time.time()))
        r = self.agent("auditer", compte=ROOT, jours=7)
        self.assertEqual([x["type"] for x in r["signaux"]], ["injection_repetee"])
        self.assertEqual(self.agent("auditer", compte=ROOT, jours=9999)["jours"], 30)             # le plafond de jours


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Defaire, Auditeur
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
