# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La répartition du catalogue entre les agents
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #717a0a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La répartition du catalogue entre les agents : Cassandra tient l'infrastructure (jamais le bureau), Itare le bureau (jamais l'infrastructure).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=717a0a ▼▼▼
"""La répartition du catalogue entre les agents : Cassandra tient l'infrastructure (jamais le bureau), Itare le bureau (jamais l'infrastructure).

Les modules communs (mémoire, agents, planification…) restent aux deux ; Amizo garde ses six outils. La répartition est une DONNÉE (`repartition` de CN_equipe.json) : un module de plus se range
dans une famille sans toucher au code."""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

from noyau import CN_manifeste as M                                # noqa: E402
import CN_test_agents_actions as actions                           # noqa: E402
from CN_test_agents import BEA, ROOT, texte                        # noqa: E402

REPARTITION = json.loads((RACINE / "modules" / "agents" / "CN_equipe.json").read_text(encoding="utf-8"))["repartition"]
BUREAU, INFRA = set(REPARTITION["bureau"]), set(REPARTITION["infrastructure"])


def capacites_par_module():
    sortie = {}
    for d in sorted((RACINE / "modules").iterdir()):
        f = d / "CN_manifeste.toml"
        if f.exists():
            sortie[d.name] = M.charger(f).capacites
    return sortie


class Repartition(actions.Actions):
    def test_les_deux_familles_ne_se_chevauchent_pas_et_nomment_des_modules_qui_existent(self):
        self.assertEqual(BUREAU & INFRA, set())
        existants = set(capacites_par_module())
        self.assertEqual((BUREAU | INFRA) - existants, set())
        for m in ("billetterie", "dolibarr", "notes", "contacts", "ged"):
            self.assertIn(m, BUREAU)
        for m in ("fastpanel", "comptes"):
            self.assertIn(m, INFRA)
        self.assertEqual(REPARTITION["sans"], {"cassandra": "bureau", "itare": "infrastructure"})

    def test_le_catalogue_reel_a_des_deux_cotes_de_quoi_etre_partage(self):
        pour = {"cassandra": 0, "itare": 0}
        for module, caps in capacites_par_module().items():
            for c in caps:
                if "itare" in c.qui and module in BUREAU:
                    pour["itare"] += 1
                if "cassandra" in c.qui and module in INFRA:
                    pour["cassandra"] += 1
        self.assertGreater(pour["itare"], 100)
        self.assertGreater(pour["cassandra"], 50)

    def test_itare_garde_le_bureau_et_perd_l_infrastructure(self):
        cles = [t["cle"] for t in self.agent("outils", compte=BEA)["outils"]]
        self.assertIn("notes.creer", cles)
        self.assertEqual([k for k in cles if k.split(".")[0] in INFRA], [])

    def test_cassandra_n_a_plus_le_bureau_dans_son_tour(self):
        r = self.causer("Crée une note", [self.creer("Hors famille"), texte("Fait ?")], agent="cassandra", compte=ROOT)
        self.assertEqual([e for e in self.evts("capacite.faite") if e.get("objet_id") == "notes.creer"], [])
        self.assertEqual([a for a in r["actions"] if a.get("statut") == "faite"], [])
        self.assertNotIn("Hors famille", str(self.ex("notes.lister", compte=ROOT)["resultat"]))

    def test_les_outils_d_un_agent_decident_chaque_droit_une_seule_fois(self):
        """Le premier `agents.equipe` à froid dérive les outils de chaque agent : un droit se décide une fois par dérivation, pas une fois par capacité."""
        d, appels = self.n.droits, []
        vrai = d.raison
        d.raison = lambda compte, droit, *a, **k: (appels.append(droit), vrai(compte, droit, *a, **k))[1]
        self.addCleanup(setattr, d, "raison", vrai)
        outils = self.ctx.outils("itare")
        self.assertGreater(len(outils), len(set(appels)))
        self.assertEqual(len(appels), len(set(appels)))

    def test_les_services_et_amizo_ne_changent_pas(self):
        e = {a["id"]: a for a in self.agent("equipe", compte=ROOT)["equipe"]}
        self.assertLessEqual(e["amizo"]["nb_outils"], 6)
        for s in ("relecteur", "vision", "auditeur"):
            self.assertEqual(e[s]["nb_outils"], 0)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : capacites_par_module, Repartition
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
