# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les points d'évolution RÉELS du dépôt (vue
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #470bde
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les points d'évolution RÉELS du dépôt (les points déclarés ci-dessous) : déclarés sans défaut, équivalents à leur corpus doré (produit par l'ancien code), et protégés par un corpus assez fort pour juger une variante. Tout nouveau po
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=470bde ▼▼▼
"""Les points d'évolution RÉELS du dépôt (les points déclarés ci-dessous) : déclarés sans défaut, équivalents à leur corpus doré (produit par l'ancien code),
et protégés par un corpus assez fort pour juger une variante. Tout nouveau point réel s'ajoute à la liste : ce banc est sa porte d'entrée."""
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

# (module, point, nom de la référence, plancher du score de détection des variantes fausses)
POINTS = [("vue", "verdict.composer", "EC_verdict_composer", 0.85),
          ("contacts", "signaux", "EC_signaux", 0.88),
          ("contacts", "vcard_lire", "EC_vcard_lire", 0.9),
          ("contacts", "vcard_ecrire", "EC_vcard_ecrire", 0.92)]


def manifeste_de(dossier: Path):
    f = dossier / "CN_manifeste.toml"
    return M.charger(f if f.exists() else dossier / "manifeste.toml")


class PointsReels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.svc = P.ServicePoints(None)
        cls.rejeu = R.Rejeu(cls.tmp / "rejeu.db")
        cls.ev = EV.Evaluateur(cls.svc, cls.rejeu, minimum=10)
        cls.corpus, cls.sources = {}, {}
        for module, point, ref, _ in POINTS:
            dossier = RACINE / "modules" / module
            defauts = cls.svc.declarer(manifeste_de(dossier), dossier)
            assert defauts == [], defauts
            fichier = dossier / "contrats" / ("CN_%s.corpus.json" % point.replace(".", "_"))
            cls.corpus[(module, point)] = json.loads(fichier.read_text(encoding="utf-8"))
            cls.rejeu.importer("%s.%s" % (module, point), cls.corpus[(module, point)]["cas"], "dore")
            cls.sources[(module, point)] = (dossier / "points" / (ref + ".py")).read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_chaque_point_est_declare_avec_son_contrat_et_son_corpus(self):
        self.assertEqual(sorted(self.svc.points()), sorted("%s.%s" % (m, p) for m, p, _, _ in POINTS))
        for module, point, _, _ in POINTS:
            self.assertGreaterEqual(len(self.corpus[(module, point)]["cas"]), 20, "%s.%s : un corpus doré d'au moins vingt cas" % (module, point))

    def test_la_reference_rejoue_son_corpus_dore_a_l_identique(self):
        """Le corpus a été produit par l'ANCIEN code, avant la conversion : l'égalité prouve que rien n'a changé."""
        for module, point, _, _ in POINTS:
            for c in self.corpus[(module, point)]["cas"]:
                self.assertEqual(self.svc.appeler(module, point, c["entree"]), c["sortie"], "%s.%s : %s" % (module, point, c["cas"]))

    def test_la_reference_est_equivalente_a_elle_meme_pour_l_evaluateur(self):
        for module, point, _, _ in POINTS:
            r = self.ev.evaluer(module, point, self.sources[(module, point)])
            self.assertEqual(r["verdict"], "equivalente", "%s.%s : %s" % (module, point, r))

    def test_le_corpus_est_assez_fort_pour_juger_une_variante(self):
        """L'évaluateur se juge lui-même : la part des variantes fausses de la référence que le corpus attrape. Ce plancher empêche un corpus de s'affaiblir en silence."""
        for module, point, _, plancher in POINTS:
            r = self.ev.pieges(module, point, maximum=200)
            self.assertGreaterEqual(r["mutants"], 30, "%s.%s" % (module, point))
            self.assertGreaterEqual(r["score"], plancher, "%s.%s : corpus trop faible, survivants : %s" % (module, point, r["survivants"][:6]))

    def test_aucune_fiche_privee_ne_voyage_dans_le_corpus_de_contacts(self):
        """Le corpus des contacts est synthétique : jamais une vraie adresse. Un banc qui le vérifie empêche d'y coller un carnet réel."""
        texte = json.dumps(self.corpus[("contacts", "signaux")], ensure_ascii=False)
        for reel in ("gmail.com", "orange.fr", "free.fr", "hotmail", "yahoo", "outlook"):
            self.assertNotIn(reel, texte)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : manifeste_de, PointsReels
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
