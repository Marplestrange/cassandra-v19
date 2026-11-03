# ══════════════════════════════════════════════════════════════════
# TITRE      : Bancs du cerveau des agents
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #7d589b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du cerveau : un agent peut-il répondre, qu'est-ce qui casse, le détecteur qui le dit, les économies suggérées, les moteurs d'IA de la machine.
# MÉTHODE    : un vrai noyau avec les modules agents, modeles, memoire et notes ; aucun modèle réel (on lie des modèles déclarés, sans les appeler).
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=7d589b ▼▼▼
"""Bancs du cerveau : un agent sans modèle ne répond pas, et le noyau le dit."""
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402

ROOT = "root@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("agents", "notes", "modeles", "memoire"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("modeles", "memoire", "notes", "agents"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ROOT, True)

    def ex(self, cap, compte=ROOT, **a):
        return self.n.executeur.executer(cap, "humain", a, compte=compte)

    def lire(self, cap, **a):
        r = self.ex(cap, **a)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def modele(self, nom="maison", fournisseur="personnalise", base="http://127.0.0.1:9/v1"):
        return self.lire("modeles.instance_ajouter", fournisseur=fournisseur, nom=nom, cle="sk-x", base_url=base)["id"]

    def agent(self, cid):
        return next(a for a in self.lire("agents.cerveau")["agents"] if a["id"] == cid)


class Cerveau(Monde):
    def test_sans_modele_aucun_agent_ne_repond_et_la_raison_est_dite(self):
        r = self.lire("agents.cerveau")
        self.assertEqual((r["repondent"], r["total"]), (0, 3))
        self.assertEqual(sorted(r["sans"]), ["Amizo", "Cassandra", "Itare"])
        self.assertIn("principal", self.agent("cassandra")["raison"])
        self.assertIn("itare_citadelle", self.agent("itare")["raison"])

    def test_lier_un_role_fait_repondre_les_agents_qui_en_dependent(self):
        mid = self.modele()
        self.lire("modeles.role_lier", role="principal", modele_id=mid)
        r = self.lire("agents.cerveau")
        self.assertTrue(self.agent("cassandra")["peut"])
        self.assertTrue(self.agent("amizo")["peut"], "Amizo prend le rôle principal par défaut")
        self.assertFalse(self.agent("itare")["peut"])
        self.assertEqual((r["repondent"], r["total"]), (2, 3))
        self.assertEqual(self.agent("cassandra")["modele"], "maison")

    def test_un_modele_d_agent_qui_nomme_un_role_sans_modele_ne_repond_pas(self):
        mid = self.modele()
        self.lire("modeles.role_lier", role="principal", modele_id=mid)
        self.lire("agents.agent_regler", id="cassandra", champs={"modele": "agent_cassandra"})
        a = self.agent("cassandra")
        self.assertFalse(a["peut"])
        self.assertIn("agent_cassandra", a["raison"])
        self.lire("modeles.role_lier", role="agent_cassandra", modele_id=mid)
        self.assertTrue(self.agent("cassandra")["peut"])

    def test_le_secours_est_nomme_quand_il_est_lie(self):
        a, b = self.modele("un"), self.modele("deux")
        self.lire("modeles.role_lier", role="principal", modele_id=a)
        self.lire("modeles.role_lier", role="secours_cassandra", modele_id=b)
        self.lire("agents.agent_regler", id="cassandra", champs={"secours": "secours_cassandra"})
        self.assertEqual(self.agent("cassandra")["secours"], "deux")

    def test_un_service_sans_modele_n_est_pas_une_panne(self):
        s = self.agent("relecteur")
        self.assertIsNone(s["peut"])
        self.assertEqual(self.lire("agents.cerveau")["total"], 3)

    def test_le_detecteur_signale_cassandra_et_amizo_pas_itare(self):
        self.n.tick()
        ouverts = {e["donnees"]["titre"]: e["donnees"] for e in self.n.bus.recents(portee=TOUT, limite=900) if e["type"] == "constat.ouvert"}
        self.assertEqual(sorted(ouverts), ["Amizo ne peut pas répondre", "Cassandra ne peut pas répondre"])
        self.assertEqual(ouverts["Cassandra ne peut pas répondre"]["niveau"], "critique")
        mid = self.modele()
        self.lire("modeles.role_lier", role="principal", modele_id=mid)
        self.n.tick(time.time() + 400)                       # la fréquence du détecteur est de 300 s
        resolus = [e["donnees"] for e in self.n.bus.recents(portee=TOUT, limite=900) if e["type"] == "constat.resolu"]
        self.assertEqual(len(resolus), 2)


class Economies(Monde):
    def test_sans_depense_aucune_suggestion(self):
        self.assertEqual(self.lire("agents.economies")["suggestions"], [])

    def test_un_agent_en_ligne_aux_echanges_courts_se_voit_proposer_le_local(self):
        en_ligne = self.modele("gpt", "openai", "")
        local = self.modele("qwen2.5:3b", "ollama", "")
        self.lire("modeles.role_lier", role="principal", modele_id=en_ligne)
        ctx = self.n.executeur.contextes["agents"]
        ctx.stockage.ecrire("INSERT INTO agent_couts(jour, agent, compte, appels, entrees, sorties, centimes) VALUES (date('now'), 'cassandra', '', 40, 20000, 4000, 120)")
        # le modèle local n'a pas encore répondu : pas de suggestion qui promette ce qu'on n'a pas vu
        self.assertFalse([s for s in self.lire("agents.economies")["suggestions"] if s["id"].startswith("local-")])
        ctx_m = self.n.executeur.contextes["modeles"]
        ctx_m.stockage.ecrire("UPDATE modeles SET essai_ts=1, essai_ok=1, essai_s=3.2, essai_msg='ok' WHERE id=?", (local,))
        sug = [s for s in self.lire("agents.economies")["suggestions"] if s["id"].startswith("local-")]
        self.assertEqual(len(sug), 1)
        self.assertEqual(sug[0]["action"], {"type": "modele", "agent": "cassandra", "modele_id": local})
        self.assertAlmostEqual(sug[0]["euros"], 1.2)

    def test_une_depense_negligeable_ne_propose_pas_de_plafond(self):
        ctx = self.n.executeur.contextes["agents"]
        ctx.stockage.ecrire("INSERT INTO agent_couts(jour, agent, compte, appels, entrees, sorties, centimes) VALUES (date('now'), 'cassandra', '', 3, 100, 100, 5)")
        self.assertFalse([s for s in self.lire("agents.economies")["suggestions"] if s["id"] == "plafond"])

    def test_une_depense_sans_plafond_global_propose_d_en_poser_un(self):
        ctx = self.n.executeur.contextes["agents"]
        ctx.stockage.ecrire("INSERT INTO agent_couts(jour, agent, compte, appels, entrees, sorties, centimes) VALUES (date('now'), 'cassandra', '', 3, 100, 100, 150)")
        self.assertTrue([s for s in self.lire("agents.economies")["suggestions"] if s["id"] == "plafond"])


class Moteurs(Monde):
    def test_les_moteurs_sont_lus_sans_rien_charger(self):
        r = self.lire("modeles.moteurs")
        self.assertEqual([m["id"] for m in r["moteurs"]], ["sens", "dictee", "lecture", "ocr", "vision"])
        self.assertIn("total", r["machine"])
        self.assertEqual(next(m for m in r["moteurs"] if m["id"] == "vision")["etat"], "absent")
        mid = self.modele()
        self.lire("modeles.role_lier", role="vision", modele_id=mid)
        self.assertEqual(next(m for m in self.lire("modeles.moteurs")["moteurs"] if m["id"] == "vision")["etat"], "pose")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le monde d'essai, la lecture du cerveau, les économies, les moteurs.
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/agents (CN_atelier.py : cerveau, economies), modules/modeles (moteurs)
