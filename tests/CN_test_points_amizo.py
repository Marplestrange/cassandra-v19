# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les sept points d'évolution d'Amizo et de l'équipe (ton_agent, planifier_recherche, classe
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #b26c25
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les sept points d'évolution d'Amizo et de l'équipe (ton_agent, planifier_recherche, classer_fiche, score_source, rapport_matin, proposer_promotion, choix_modele) : déclarés sans défaut, rejouant leur corpus à l'identique, assez forts pour j
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b26c25 ▼▼▼
"""Les sept points d'évolution d'Amizo et de l'équipe (ton_agent, planifier_recherche, classer_fiche, score_source, rapport_matin, proposer_promotion, choix_modele) : déclarés sans défaut,
rejouant leur corpus à l'identique, assez forts pour juger une variante, passant l'analyse durcie du noyau (aucun accès `__xxx__`, natives restreintes), et leurs MESURES vérifiées mécaniquement."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_evaluateur as EV  # noqa: E402
from noyau import CN_manifeste as M  # noqa: E402
from noyau import CN_points as P  # noqa: E402
from noyau import CN_rejeu as R  # noqa: E402

DOSSIER = RACINE / "modules" / "agents"
# (point, plancher du score de détection des variantes fausses)
POINTS = [("ton_agent", 0.85), ("planifier_recherche", 0.75), ("classer_fiche", 0.80), ("score_source", 0.85), ("rapport_matin", 0.85), ("proposer_promotion", 1.0), ("choix_modele", 1.0)]
MINIMUM_CAS = 20


class PointsAmizo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.svc = P.ServicePoints(None)
        cls.rejeu = R.Rejeu(cls.tmp / "rejeu.db")
        cls.ev = EV.Evaluateur(cls.svc, cls.rejeu, minimum=10)
        defauts = cls.svc.declarer(M.charger(DOSSIER / "CN_manifeste.toml"), DOSSIER)
        assert defauts == [], defauts
        cls.corpus, cls.sources = {}, {}
        for point, _ in POINTS:
            cls.corpus[point] = json.loads((DOSSIER / "contrats" / ("CN_%s.corpus.json" % point)).read_text(encoding="utf-8"))
            cls.rejeu.importer("agents.%s" % point, cls.corpus[point]["cas"], "dore")
            cls.sources[point] = (DOSSIER / "points" / ("EC_%s.py" % point)).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def appeler(self, point, entree):
        return self.svc.appeler("agents", point, entree)

    def test_les_sept_points_sont_declares_avec_leur_contrat_et_leur_corpus(self):
        for point, _ in POINTS:
            self.assertIn("agents.%s" % point, self.svc.points("agents"))
            self.assertGreaterEqual(len(self.corpus[point]["cas"]), MINIMUM_CAS, point)
            contrat = json.loads((DOSSIER / "contrats" / ("CN_%s.json" % point)).read_text(encoding="utf-8"))
            self.assertTrue(contrat["mesure"] and contrat["invariants"], point)

    def test_la_reference_passe_l_analyse_durcie_du_noyau(self):
        for point, _ in POINTS:
            self.assertEqual(P.analyser_purete(self.sources[point]), [], point)
            self.assertNotIn("__", "".join(l for l in self.sources[point].splitlines() if not l.lstrip().startswith("#") and "__future__" not in l), point)

    def test_la_reference_rejoue_son_corpus_a_l_identique(self):
        for point, _ in POINTS:
            for c in self.corpus[point]["cas"]:
                self.assertEqual(self.appeler(point, c["entree"]), c["sortie"], "%s : %s" % (point, c["cas"]))

    def test_la_reference_est_equivalente_a_elle_meme_pour_l_evaluateur(self):
        for point, _ in POINTS:
            r = self.ev.evaluer("agents", point, self.sources[point])
            self.assertEqual(r["verdict"], "equivalente", "%s : %s" % (point, r))

    def test_le_corpus_est_assez_fort_pour_juger_une_variante(self):
        for point, plancher in POINTS:
            r = self.ev.pieges("agents", point, maximum=120)
            self.assertGreaterEqual(r["mutants"], 8, point)
            self.assertGreaterEqual(r["score"], plancher, "%s : corpus trop faible, survivants : %s" % (point, r["survivants"][:6]))

    # ── les mesures, vérifiées mécaniquement ─────────────────────────────────────────────────────
    def test_mesure_rapport_matin_chaque_phrase_renvoie_a_une_ligne_du_journal(self):
        for c in self.corpus["rapport_matin"]["cas"]:
            e = c["entree"]
            lignes = {x["id"]: x for x in e["evenements"]}
            sortie = self.appeler("rapport_matin", e)["valeur"]
            for agent, phrases in sortie["agents"].items():
                self.assertLessEqual(len(phrases), 3, c["cas"])
                for ph in phrases:
                    ligne = lignes[ph["journal"]]                                     # la ligne existe dans l'entrée…
                    self.assertEqual(ligne["acteur"], agent, c["cas"])                # … elle est de cet agent …
                    self.assertTrue(e["debut"] <= ligne["ts"] < e["fin"], c["cas"])   # … dans la période
                    self.assertTrue(ph["phrase"].strip(), c["cas"])
            for a in e["agents"]:
                self.assertEqual(a["id"] in sortie["agents"], a["id"] not in sortie["silencieux"], c["cas"])

    def test_mesure_ton_agent_longueur_et_propre(self):
        for c in self.corpus["ton_agent"]["cas"]:
            t = self.appeler("ton_agent", c["entree"])["valeur"]
            self.assertLessEqual(len(t), c["entree"]["longueur_max"], c["cas"])
            self.assertNotIn("  ", t, c["cas"])
            self.assertFalse(any(ord(x) < 32 and x != "\n" for x in t), c["cas"])
        self.assertIn("sourcé", self.appeler("ton_agent", {"agent": "amizo", "ton": "", "longueur_max": 2000})["valeur"])
        self.assertEqual(self.appeler("ton_agent", {"agent": "itare", "ton": "", "longueur_max": 2000})["valeur"], "")

    def test_mesure_proposer_promotion_equivaut_a_la_regle_du_noyau(self):
        for c in self.corpus["proposer_promotion"]["cas"]:
            e = c["entree"]
            attendu = e["validations"] >= e["seuil"] and not e["essai"] and not e["refus_recent"]
            self.assertEqual(self.appeler("proposer_promotion", e)["valeur"]["propose"], attendu, c["cas"])

    def test_mesure_choix_modele_ferme_par_le_secours_sans_doublon(self):
        for c in self.corpus["choix_modele"]["cas"]:
            e = c["entree"]
            roles = self.appeler("choix_modele", e)["valeur"]
            self.assertEqual(len(roles), len(set(roles)), c["cas"])
            if e["au_plafond"] and (e["secours"] or e["agent"] != "cassandra"):
                self.assertLessEqual(set(roles), {e["secours"]}, c["cas"])

    def test_mesure_score_source_borne_et_bloque(self):
        for c in self.corpus["score_source"]["cas"]:
            v = self.appeler("score_source", c["entree"])["valeur"]
            self.assertTrue(0.0 <= v["confiance"] <= 1.0 and v["raisons"], c["cas"])
            self.assertEqual(v["niveau"] == "aucune", v["confiance"] == 0.0, c["cas"])

    def test_mesure_classer_fiche_et_planifier_recherche_respectent_leurs_bornes(self):
        for c in self.corpus["classer_fiche"]["cas"]:
            v = self.appeler("classer_fiche", c["entree"])["valeur"]
            self.assertTrue(1 <= len(v["titre"]) <= 200 and len(v["resume"]) <= 300, c["cas"])
            self.assertEqual(v["etagere"] == "interne", c["entree"]["url"].strip().lower().startswith("espace:"), c["cas"])
        for c in self.corpus["planifier_recherche"]["cas"]:
            v = self.appeler("planifier_recherche", c["entree"])["valeur"]
            b = c["entree"]["budget"]
            self.assertLessEqual(len(v["requetes"]), max(1, min(5, int(b.get("requetes", 3)))), c["cas"])
            self.assertEqual(len(v["requetes"]), len({q.lower() for q in v["requetes"]}), c["cas"])
            self.assertTrue(all(len(q) <= 120 for q in v["requetes"]), c["cas"])
            self.assertLessEqual(v["max_sources"], 2 * len(v["requetes"]), c["cas"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : PointsAmizo
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
