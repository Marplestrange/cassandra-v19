# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les points d'évolution RÉELS du dépôt (vue
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #4aa857
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les points d'évolution RÉELS du dépôt (les points déclarés ci-dessous) : déclarés sans défaut, équivalents à leur corpus doré (produit par l'ancien code), et protégés par un corpus assez fort pour juger une variante. Tout nouveau po
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=4aa857 ▼▼▼
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
          ("contacts", "vcard_ecrire", "EC_vcard_ecrire", 0.92),
          ("contacts", "csv_apparier", "EC_csv_apparier", 1.0),
          ("contacts", "csv_fiches", "EC_csv_fiches", 0.95),
          ("memoire", "json_extraire", "EC_json_extraire", 0.90),
          ("notes", "lire_entete", "EC_lire_entete", 0.90),
          ("notes", "md_vers_html", "EC_md_vers_html", 0.90),
          ("dns", "analyser", "EC_analyser", 0.90),
          ("agenda", "ical_lire", "EC_ical_lire", 0.95),
          ("memoire", "perception_monde", "EC_perception_monde", 0.80),
          ("planifie", "decrire", "EC_decrire", 0.95),
          ("planifie", "collisions", "EC_collisions", 0.60),
          ("flotte", "lire_sortie", "EC_lire_sortie", 0.95),
          ("flotte", "lire_metriques", "EC_lire_metriques", 1.00),
          ("ged", "media_kind", "EC_media_kind", 0.90),
          ("courrier", "roles_uniques", "EC_roles_uniques", 1.00),
          ("agents", "resume_resultat", "EC_resume_resultat", 0.95),
          ("courrier", "utf7_decoder", "EC_utf7_decoder", 0.75),
          ("courrier", "decoder_entete", "EC_decoder_entete", 1.00),
          ("courrier", "adresse_parts", "EC_adresse_parts", 0.85),
          ("courrier", "role_du_dossier", "EC_role_du_dossier", 1.00),
          ("courrier", "motif_technique", "EC_motif_technique", 1.00),
          ("courrier", "html_en_texte", "EC_html_en_texte", 0.90),
          ("mesures", "moteur", "EC_moteur", 0.85),
          ("contacts", "initiales", "EC_initiales", 0.90),
          ("contacts", "meilleure", "EC_meilleure", 0.80),
          ("contacts", "csv_decoder", "EC_csv_decoder", 1.00),
          ("dns", "dom_enregistre", "EC_dom_enregistre", 1.00),
          ("notes", "liens_de", "EC_liens_de", 1.00),
          ("jour", "tuiles", "EC_tuiles", 1.00),
          ("agents", "choisir_outils", "EC_choisir_outils", 0.95),
          ("memoire", "routage", "EC_routage", 1.00),
          ("memoire", "termes", "EC_termes", 0.90),
          ("memoire", "jetons", "EC_jetons", 1.00),
          ("memoire", "question_de", "EC_question_de", 0.95)]
# (cas dorés, variantes fausses) minimaux ; une très petite fonction ne peut pas engendrer trente mutants : son plancher de score est alors de 1,0
SEUILS = {("memoire", "question_de"): (18, 23), ("memoire", "jetons"): (18, 7), ("memoire", "termes"): (20, 8), ("memoire", "routage"): (20, 3), ("agents", "choisir_outils"): (20, 21), ("jour", "tuiles"): (20, 28), ("notes", "liens_de"): (20, 3), ("dns", "dom_enregistre"): (18, 13), ("contacts", "csv_decoder"): (11, 3), ("contacts", "meilleure"): (17, 11), ("courrier", "html_en_texte"): (20, 16), ("courrier", "motif_technique"): (15, 5), ("courrier", "role_du_dossier"): (20, 6), ("courrier", "adresse_parts"): (13, 3), ("courrier", "decoder_entete"): (13, 3), ("courrier", "utf7_decoder"): (18, 7), ("agents", "resume_resultat"): (20, 26), ("courrier", "roles_uniques"): (16, 9), ("ged", "media_kind"): (20, 15), ("flotte", "lire_metriques"): (20, 11), ("memoire", "json_extraire"): (20, 12), ("contacts", "csv_fiches"): (20, 15), ("notes", "md_vers_html"): (20, 24), ("notes", "lire_entete"): (20, 22), ("contacts", "csv_apparier"): (15, 3)}


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
            self.assertGreaterEqual(len(self.corpus[(module, point)]["cas"]), SEUILS.get((module, point), (20, 30))[0], "%s.%s : un corpus doré d'au moins vingt cas" % (module, point))

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
            self.assertGreaterEqual(r["mutants"], SEUILS.get((module, point), (20, 30))[1], "%s.%s" % (module, point))
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
