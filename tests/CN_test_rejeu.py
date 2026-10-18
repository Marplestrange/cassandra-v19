# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du corpus de rejeu et de l'évaluateur
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #92bab2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du corpus de rejeu et de l'évaluateur : la partition réservée, la borne, l'équivalence par paliers, le gain qui tient, et l'évaluateur qui se teste lui-même.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=92bab2 ▼▼▼
"""Bancs du corpus de rejeu et de l'évaluateur : la partition réservée, la borne, l'équivalence par paliers, le gain qui tient, et l'évaluateur qui se teste lui-même."""
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_evaluateur as EV  # noqa: E402
from noyau import CN_points as P  # noqa: E402
from noyau import CN_rejeu as R  # noqa: E402
from noyau import CN_manifeste as M  # noqa: E402

LENTE = ("def doubler(entree):\n    s = sum(entree['x'] for _ in range(2000))\n    return {'y': s * 2 // 2000}\n")
RAPIDE = "def doubler(entree):\n    return {'y': entree['x'] * 2}\n"
CONTRAT = {"entree": {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}},
           "sortie": {"type": "object", "required": ["y"], "properties": {"y": {"type": "integer"}}}}


class Stockage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.r = R.Rejeu(self.tmp / "rejeu.db")

    def test_une_meme_entree_est_comptee_pas_dupliquee(self):
        self.r.enregistrer("m.p", {"a": 1, "b": 2}, {}, 1.5, "reference")
        self.r.enregistrer("m.p", {"b": 2, "a": 1}, {}, 2.5, "EC3")                 # l'ordre des clés ne change pas l'identité
        s = self.r.stats("m.p")
        self.assertEqual((s["distincts"], s["appels"]), (1, 2))
        self.assertEqual(s["duree_moyenne_ms"], 2.0)

    def test_absorber_ajoute_les_deltas_d_un_autre_processus_sans_rien_compter_deux_fois(self):
        autre = R.Rejeu(self.tmp / "autre.db")
        autre.enregistrer("m.p", {"x": 1}, {}, 2.0)
        autre.enregistrer("m.p", {"x": 1}, {}, 4.0)
        autre.enregistrer("m.p", {"x": 2}, {}, 1.0)
        self.assertEqual(self.r.absorber(self.tmp / "autre.db"), 3)
        self.assertEqual(self.r.absorber(self.tmp / "autre.db"), 0)                      # rien de nouveau : rien d'ajouté
        s = self.r.stats("m.p")
        self.assertEqual((s["distincts"], s["appels"]), (2, 3))
        autre.enregistrer("m.p", {"x": 2}, {}, 3.0)
        self.assertEqual(self.r.absorber(self.tmp / "autre.db"), 1)                      # seul le delta
        self.assertEqual(self.r.stats("m.p")["appels"], 4)
        self.assertEqual(self.r.absorber(self.tmp / "absent.db"), 0)                     # un fichier absent n'est pas une erreur

    def test_la_partition_reservee_est_stable_et_proche_d_un_cinquieme(self):
        for i in range(300):
            self.r.enregistrer("m.p", {"x": i})
        s = self.r.stats("m.p")
        self.assertTrue(30 <= s["reserve"] <= 90, s)
        a, b = {c["h"] for c in self.r.corpus("m.p", "visible")}, {c["h"] for c in self.r.corpus("m.p", "reserve")}
        self.assertEqual(a & b, set())                                                # jamais une entrée des deux côtés
        self.assertEqual(len(a | b), 300)
        self.assertEqual(R.est_reserve(R.empreinte({"x": 7})), R.est_reserve(R.empreinte({"x": 7})))      # la même entrée tombe toujours du même côté

    def test_le_corpus_est_borne_et_les_cas_dores_ne_sont_jamais_evinces(self):
        r = R.Rejeu(self.tmp / "b.db", max_par_point=10)
        r.importer("m.p", [{"entree": {"x": -i}} for i in range(1, 6)], "dore")
        for i in range(200):
            r.enregistrer("m.p", {"x": i})
        s = r.stats("m.p")
        self.assertLessEqual(s["distincts"], 10 + R.PURGE_TOUS_LES)
        self.assertEqual(s["dores"], 5)

    def test_importer_est_idempotent(self):
        cas = [{"entree": {"x": 1}}, {"entree": {"x": 2}}]
        self.assertEqual(self.r.importer("m.p", cas), 2)
        self.assertEqual(self.r.importer("m.p", cas), 0)

    def test_inactif_n_enregistre_rien(self):
        r = R.Rejeu(self.tmp / "i.db", actif=False)
        r.enregistrer("m.p", {"x": 1})
        self.assertEqual(r.stats("m.p")["distincts"], 0)


class Banc(unittest.TestCase):
    """Un point synthétique : la référence double (lentement) ; les candidats sont des textes."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        mod = self.tmp / "modules" / "essai"
        (mod / "points").mkdir(parents=True)
        (mod / "contrats").mkdir()
        (mod / "points" / "EC_doubler.py").write_text(LENTE, encoding="utf-8")
        (mod / "contrats" / "CN_doubler.json").write_text(json.dumps(CONTRAT), encoding="utf-8")
        self.svc = P.ServicePoints(None)
        self.svc.declarer(types.SimpleNamespace(id="essai", points_evolution=(M.PointEvolution("doubler", "Double", "1.0", "points/EC_doubler", "doubler"),)), mod)
        self.rejeu = R.Rejeu(self.tmp / "rejeu.db")
        for i in range(60):
            self.rejeu.enregistrer("essai.doubler", {"x": i})
        self.ev = EV.Evaluateur(self.svc, self.rejeu, minimum=20)

    def evaluer(self, texte, **kw):
        return self.ev.evaluer("essai", "doubler", texte, **kw)


class Equivalence(Banc):
    def test_un_candidat_equivalent_est_reconnu_et_va_jusqu_au_bout(self):
        r = self.evaluer(RAPIDE)
        self.assertEqual(r["verdict"], "equivalente", r)
        self.assertEqual((r["palier_atteint"], r["evalues"]), (1.0, 60))

    def test_un_candidat_plus_rapide_donne_un_gain_qui_tient_sur_le_reserve(self):
        r = self.evaluer(RAPIDE)
        self.assertGreater(r["gain_pct"], 50, r["latence_ms"])
        self.assertGreater(r["gain_reserve_pct"], 0)                                   # mesuré à part sur ce que le générateur n'a jamais vu
        self.assertTrue(r["gain_tient"])

    def test_une_divergence_arrete_l_evaluation_et_designe_le_cas(self):
        r = self.evaluer("def doubler(entree):\n    return {'y': entree['x'] * 2 + (1 if entree['x'] == 30 else 0)}\n")
        self.assertEqual(r["verdict"], "divergente")
        self.assertIn(r["divergence"]["partition"], ("visible", "reserve"))
        self.assertLess(r["evalues"], 60)

    def test_une_exception_du_candidat_est_une_erreur(self):
        r = self.evaluer("def doubler(entree):\n    raise RuntimeError('boum')\n")
        self.assertEqual(r["verdict"], "erreur")
        self.assertIn("boum", r["erreur"])

    def test_une_sortie_hors_contrat_est_une_divergence(self):
        r = self.evaluer("def doubler(entree):\n    return {'y': 'texte'}\n")
        self.assertEqual(r["verdict"], "divergente")

    def test_un_candidat_impur_n_est_pas_charge(self):
        r = self.evaluer("import os\n\ndef doubler(entree):\n    return {'y': len(os.listdir('.'))}\n")
        self.assertEqual(r["verdict"], "impure")
        self.assertEqual(r["evalues"], 0)

    def test_un_candidat_illisible_ou_sans_la_fonction_n_est_pas_un_candidat(self):
        self.assertEqual(self.evaluer("def doubler(:\n")["verdict"], "illisible")
        self.assertEqual(self.evaluer("def autre(entree):\n    return {'y': 1}\n")["verdict"], "illisible")

    def test_un_corpus_trop_etroit_n_autorise_aucune_promotion(self):
        petit = R.Rejeu(self.tmp / "petit.db")
        for i in range(3):
            petit.enregistrer("essai.doubler", {"x": i})
        r = EV.Evaluateur(self.svc, petit, minimum=200).evaluer("essai", "doubler", RAPIDE)
        self.assertEqual(r["verdict"], "corpus_trop_etroit")                           # équivalent sur 3 cas ne prouve rien

    def test_les_paliers_arretent_tot_un_mauvais_candidat(self):
        r = self.evaluer("def doubler(entree):\n    return {'y': entree['x'] * 3}\n", paliers=(0.05, 0.25, 1.0))
        self.assertEqual(r["verdict"], "divergente")
        self.assertLessEqual(r["evalues"], 3)                                          # mort dans le premier palier (5 % de 60 = 3 cas)


class Pieges(Banc):
    def test_les_mutations_sont_des_fautes_plausibles_une_a_la_fois(self):
        ms = EV.mutants("def f(x):\n    if x > 1:\n        return x + 2\n    return 0\n", 40)
        textes = {t for t, _, _ in ms}
        self.assertGreaterEqual(len(ms), 4)
        self.assertEqual(len(textes), len(ms))                                         # chacune est différente des autres
        for t, d, ligne in ms:
            compile(t, "<m>", "exec")
            self.assertTrue(d and ligne >= 1)

    def test_le_corpus_attrape_les_variantes_fausses(self):
        r = self.ev.pieges("essai", "doubler")
        self.assertGreaterEqual(r["mutants"], 3)
        self.assertGreaterEqual(r["score"], 0.5, r)

    def test_un_corpus_faible_est_dit_faible(self):
        faible = R.Rejeu(self.tmp / "faible.db")
        faible.enregistrer("essai.doubler", {"x": 0})                                  # un seul cas, x = 0 : presque toute faute y est invisible
        r = EV.Evaluateur(self.svc, faible, minimum=0).pieges("essai", "doubler")
        self.assertLess(r["score"], 0.6, r)
        self.assertTrue(r["survivants"])


class PointReel(unittest.TestCase):
    """Le vrai point `vue.verdict.composer`, avec son corpus doré comme premier rejeu."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        dossier = RACINE / "modules" / "vue"
        cls.svc = P.ServicePoints(None)
        cls.svc.declarer(M.charger(dossier / "CN_manifeste.toml" if (dossier / "CN_manifeste.toml").exists() else dossier / "manifeste.toml"), dossier)
        cls.rejeu = R.Rejeu(cls.tmp / "rejeu.db")
        corpus = json.loads((dossier / "contrats" / "CN_verdict_composer.corpus.json").read_text(encoding="utf-8"))
        cls.rejeu.importer("vue.verdict.composer", corpus["cas"], "dore")
        cls.ev = EV.Evaluateur(cls.svc, cls.rejeu, minimum=10)
        cls.source = (dossier / "points" / "EC_verdict_composer.py").read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def test_le_corpus_dore_est_le_premier_rejeu(self):
        s = self.rejeu.stats("vue.verdict.composer")
        self.assertEqual((s["distincts"], s["dores"]), (49, 49))

    def test_la_reference_est_equivalente_a_elle_meme(self):
        r = self.ev.evaluer("vue", "verdict.composer", self.source)
        self.assertEqual(r["verdict"], "equivalente", r)

    def test_une_faute_dans_le_verdict_est_attrapee(self):
        faux = self.source.replace('SEUIL_TLS_PANNE, SEUIL_TLS_REGARDER = 7, 21', 'SEUIL_TLS_PANNE, SEUIL_TLS_REGARDER = 7, 31')
        self.assertNotEqual(faux, self.source)
        r = self.ev.evaluer("vue", "verdict.composer", faux)
        self.assertEqual(r["verdict"], "divergente")

    def test_le_corpus_dore_est_assez_fort_pour_juger_le_verdict(self):
        """L'évaluateur se juge lui-même : la part de variantes fausses du composer que le corpus attrape. Les 15 premiers cas n'en attrapaient que 70 % (bornes des seuils
        non testées) ; les 34 cas ajoutés pour couvrir les survivants la portent à 92 %. Ce plancher empêche le corpus de s'affaiblir en silence."""
        r = self.ev.pieges("vue", "verdict.composer", maximum=200)
        self.assertGreaterEqual(r["mutants"], 100)
        self.assertGreaterEqual(r["score"], 0.85, "corpus trop faible : survivants = %s" % r["survivants"][:8])


class DansLeNoyau(unittest.TestCase):
    """Un vrai noyau, le vrai module `vue` : un appel de la capacité nourrit le rejeu, et le corpus doré est importé au branchement."""

    @classmethod
    def setUpClass(cls):
        import CN_main as moteur
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        mods = base / "modules"
        for m in ("vue", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        for m in ("droits", "comptes", "vue"):
            cls.n.activer(m)
        cls.n.droits.regler_admin("root@x.fr", True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_le_corpus_dore_est_importe_au_branchement(self):
        self.assertEqual(self.n.rejeu.stats("vue.verdict.composer")["dores"], 49)

    def test_un_appel_de_capacite_nourrit_le_rejeu(self):
        avant = self.n.rejeu.stats("vue.verdict.composer")["appels"]
        r = self.n.executeur.executer("vue.ensemble", "humain", {}, compte="root@x.fr")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["ok"], True)
        self.assertEqual(self.n.rejeu.stats("vue.verdict.composer")["appels"], avant + 1)

    def test_l_evaluateur_du_noyau_juge_un_candidat_sur_ce_corpus(self):
        source = (RACINE / "modules" / "vue" / "points" / "EC_verdict_composer.py").read_text(encoding="utf-8")
        r = self.n.evaluateur.evaluer("vue", "verdict.composer", source, minimum=10)
        self.assertEqual(r["verdict"], "equivalente", r)
        self.assertGreaterEqual(r["corpus"]["distincts"], 49)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Stockage, Banc, Equivalence, Pieges, PointReel
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
