# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les points d'évolution RÉELS du dépôt (vue
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #10cd96
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les points d'évolution RÉELS du dépôt (les points déclarés ci-dessous) : déclarés sans défaut, équivalents à leur corpus doré (produit par l'ancien code), et protégés par un corpus assez fort pour juger une variante. Tout nouveau po
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=10cd96 ▼▼▼
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
POINTS = [("billetterie", "commission", "EC_commission", 0.85),
          ("vue", "verdict.composer", "EC_verdict_composer", 0.85),
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
          ("memoire", "question_de", "EC_question_de", 0.95),
          ("fastpanel", "audit", "EC_audit", 0.90),
          ("fastpanel", "lecture", "EC_lecture", 0.90),
          ("courrier", "entetes", "EC_entetes", 0.90),
          ("notes", "graphe", "EC_graphe", 1.00),
          ("dns", "derives", "EC_derives", 1.00),
          ("modeles", "appels_de", "EC_appels_de", 0.90),
          ("modeles", "messages_ollama", "EC_messages_ollama", 1.00),
          ("projets", "glissement", "EC_glissement", 1.00),
          ("planifie", "apercu", "EC_apercu", 0.80),
          ("planifie", "derive", "EC_derive", 0.85),
          ("planifie", "boucle", "EC_boucle", 0.65),
          ("sauvegardes", "age_mot", "EC_age_mot", 1.00),
          ("sauvegardes", "etat", "EC_etat", 1.00),
          ("flotte", "duree", "EC_duree", 1.00),
          ("journal", "niveau", "EC_niveau", 1.00),
          ("sensorium", "sante", "EC_sante", 0.85),
          ("sensorium", "pente", "EC_pente", 0.90),
          ("sensorium", "mogwai_table", "EC_mogwai_table", 0.90),
          ("sensorium", "duree_txt", "EC_duree_txt", 1.00),
          ("sensorium", "cron_derniere", "EC_cron_derniere", 0.60),
          ("sensorium", "fp_formes", "EC_fp_formes", 0.80),
          ("sensorium", "sys_formes", "EC_sys_formes", 0.85),
          ("dns", "normaliser", "EC_normaliser", 1.00),
          ("agents", "prompt_systeme", "EC_prompt_systeme", 0.80),
          ("contacts", "norm_nom", "EC_norm_nom", 0.85),
          ("journal", "signature", "EC_signature", 0.65),
          ("memoire", "cle_de", "EC_cle_de", 0.80),
          ("planifie", "segments", "EC_segments", 1.00),
          ("salon", "destinataires_de", "EC_destinataires_de", 0.70),
          ("agenda", "regle_de", "EC_regle_de", 0.80),
          ("agents", "coherents", "EC_coherents", 0.85),
          ("contacts", "remplissage", "EC_remplissage", 0.85),
          ("courrier", "date_iso", "EC_date_iso", 1.00),
          ("dolibarr", "egaux", "EC_egaux", 0.30),
          ("notes", "dossier_ok", "EC_dossier_ok", 0.75),
          ("planifie", "occurrences", "EC_occurrences", 0.45),
          ("planifie", "suivante", "EC_suivante", 0.65),
          ("planifie", "destructeur", "EC_destructeur", 1.00),
          ("securite", "portee", "EC_portee", 0.75),
          ("securite", "adresses_machine", "EC_adresses_machine", 0.80),
          ("securite", "sans_options_cible", "EC_sans_options_cible", 0.75),
          ("securite", "docker_publies", "EC_docker_publies", 0.55),
          ("securite", "de_confiance", "EC_de_confiance", 0.80),
          ("courrier", "style_sur", "EC_style_sur", 1.00),
          ("agenda", "plier", "EC_plier", 0.75),
          ("jour", "propre", "EC_propre", 0.65),
          ("planifie", "precedente", "EC_precedente", 0.45),
          ("projets", "date_ok", "EC_date_ok", 0.70),
          ("securite", "fail2ban", "EC_fail2ban", 0.80),
          ("securite", "outils_analyse", "EC_outils_analyse", 0.80)]
# (cas dorés, variantes fausses) minimaux ; une très petite fonction ne peut pas engendrer trente mutants : son plancher de score est alors de 1,0
SEUILS = {("securite", "outils_analyse"): (12, 30), ("securite", "fail2ban"): (12, 11), ("projets", "date_ok"): (11, 5), ("planifie", "precedente"): (12, 30), ("jour", "propre"): (12, 24), ("agenda", "plier"): (20, 7), ("courrier", "style_sur"): (12, 7), ("securite", "de_confiance"): (12, 8), ("securite", "docker_publies"): (12, 22), ("securite", "sans_options_cible"): (20, 6), ("securite", "adresses_machine"): (12, 29), ("securite", "portee"): (12, 15), ("planifie", "destructeur"): (12, 3), ("planifie", "suivante"): (12, 30), ("planifie", "occurrences"): (12, 30), ("notes", "dossier_ok"): (12, 21), ("dolibarr", "egaux"): (12, 10), ("courrier", "date_iso"): (12, 4), ("contacts", "remplissage"): (17, 5), ("agents", "coherents"): (8, 18), ("agenda", "regle_de"): (10, 8), ("salon", "destinataires_de"): (14, 12), ("planifie", "segments"): (20, 3), ("memoire", "cle_de"): (20, 4), ("journal", "signature"): (20, 3), ("contacts", "norm_nom"): (20, 5), ("agents", "prompt_systeme"): (20, 9), ("dns", "normaliser"): (20, 3), ("billetterie", "commission"): (25, 25), ("sensorium", "cron_derniere"): (13, 9), ("sensorium", "duree_txt"): (14, 4), ("sensorium", "mogwai_table"): (19, 10), ("sensorium", "pente"): (11, 25), ("journal", "niveau"): (20, 6), ("flotte", "duree"): (13, 22), ("sauvegardes", "etat"): (11, 6), ("sauvegardes", "age_mot"): (12, 14), ("planifie", "boucle"): (10, 11), ("planifie", "derive"): (13, 14), ("projets", "glissement"): (12, 8), ("modeles", "messages_ollama"): (15, 5), ("modeles", "appels_de"): (17, 8), ("dns", "derives"): (18, 11), ("notes", "graphe"): (20, 12), ("fastpanel", "audit"): (20, 27), ("memoire", "question_de"): (18, 23), ("memoire", "jetons"): (18, 7), ("memoire", "termes"): (20, 8), ("memoire", "routage"): (20, 3), ("agents", "choisir_outils"): (20, 21), ("jour", "tuiles"): (20, 28), ("notes", "liens_de"): (20, 3), ("dns", "dom_enregistre"): (18, 13), ("contacts", "csv_decoder"): (11, 3), ("contacts", "meilleure"): (17, 11), ("courrier", "html_en_texte"): (20, 16), ("courrier", "motif_technique"): (15, 5), ("courrier", "role_du_dossier"): (20, 6), ("courrier", "adresse_parts"): (13, 3), ("courrier", "decoder_entete"): (13, 3), ("courrier", "utf7_decoder"): (18, 7), ("agents", "resume_resultat"): (20, 26), ("courrier", "roles_uniques"): (16, 9), ("ged", "media_kind"): (20, 15), ("flotte", "lire_metriques"): (20, 11), ("memoire", "json_extraire"): (20, 12), ("contacts", "csv_fiches"): (20, 15), ("notes", "md_vers_html"): (20, 24), ("notes", "lire_entete"): (20, 22), ("contacts", "csv_apparier"): (15, 3)}


def egal_approx(a, b, tol=1e-9):
    """Égalité à l'arrondi flottant près : `sum()` de Python 3.12 somme les flottants avec compensation, pas celui de 3.11 : le dernier chiffre d'un calcul flottant dépend de la version de l'interpréteur."""
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(egal_approx(a[k], b[k], tol) for k in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(egal_approx(x, y, tol) for x, y in zip(a, b))
    return a == b


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
                self.assertTrue(egal_approx(self.svc.appeler(module, point, c["entree"]), c["sortie"]), "%s.%s : %s" % (module, point, c["cas"]))

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
