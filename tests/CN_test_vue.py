"""Bancs de la vue d'ensemble : le verdict est composé, et une source muette n'est jamais comptée « tranquille »."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import json   # noqa: E402
from modules.vue import CN_composer as _facade   # noqa: E402
from noyau import CN_manifeste as _manifeste   # noqa: E402
from noyau.CN_points import ServicePoints   # noqa: E402

DOSSIER = RACINE / "modules" / "vue"
_SVC = ServicePoints(None)                                       # sans stock d'EC : c'est la référence du dépôt qui sert
_DEFAUTS = _SVC.declarer(_manifeste.charger(DOSSIER / "CN_manifeste.toml"), DOSSIER)


def composer(admin, compte, s, quand):
    """Comme le module : par le noyau (ctx.point), donc contrat validé à l'entrée et à la sortie."""
    return _facade.composer(admin, compte, s, quand, appeler=lambda point, entree: _SVC.appeler("vue", point, entree))


def site(d, up=True, ssl=60, code=200):
    return {"domaine": d, "source": "declare", "up": up, "code": code, "ms": 120, "ssl_jours": ssl}


def sources(**kw):
    base = {"sites": {"sites": [site("a.fr")]}, "flotte": {"machines": []}, "metriques": {"disk": 40, "cpu": 10}, "sante": {"score": 95},
            "incidents": {"incidents": []}, "fil": {"fil": []}, "notifs": {"notifications": []}, "autonomie": {"palier": "proposer"}}
    base.update(kw)
    return base


class Vue(unittest.TestCase):
    def test_tout_va_bien_dit_stable(self):
        r = composer(True, "root", sources(), "t")
        self.assertEqual(r["niveau"], "stable")
        self.assertEqual(r["muettes"], [])
        self.assertEqual(r["sites"][0]["domain"], "a.fr")                    # les mots que l'écran lit

    def test_un_site_qui_ne_repond_pas_est_une_panne(self):
        r = composer(True, "root", sources(sites={"sites": [site("a.fr"), site("b.fr", up=False, code=502)]}), "t")
        self.assertEqual(r["niveau"], "panne")
        self.assertIn("b.fr ne répond pas (code 502)", r["titre"])
        self.assertEqual(r["sites"][0]["domain"], "b.fr")                    # le tombé passe en tête

    def test_une_source_muette_n_est_jamais_stable(self):
        r = composer(True, "root", sources(metriques=None), "t")
        self.assertEqual(r["niveau"], "inconnu")
        self.assertIn("collecteur", r["muettes"])
        self.assertIn("se tait", r["titre"])

    def test_une_panne_l_emporte_sur_le_silence(self):
        r = composer(True, "root", sources(metriques=None, sites={"sites": [site("a.fr", up=False)]}), "t")
        self.assertEqual(r["niveau"], "panne")

    def test_le_certificat_a_deux_seuils(self):
        self.assertEqual(composer(True, "r", sources(sites={"sites": [site("a.fr", ssl=5)]}), "t")["niveau"], "panne")
        r = composer(True, "r", sources(sites={"sites": [site("a.fr", ssl=15)]}), "t")
        self.assertEqual(r["niveau"], "regarder")
        self.assertEqual(composer(True, "r", sources(sites={"sites": [site("a.fr", ssl=25)]}), "t")["niveau"], "stable")

    def test_une_machine_attendue_hors_ligne_est_une_panne_pas_une_intermittente(self):
        att = {"nom": "m1", "statut": "attendue", "en_ligne": False, "dernier_contact": "hier"}
        inter = {"nom": "m2", "statut": "intermittente", "en_ligne": False}
        r = composer(True, "r", sources(flotte={"machines": [att, inter]}), "t")
        self.assertEqual(r["niveau"], "panne")
        self.assertEqual(r["flotte"]["hors_ligne"], ["m1"])
        self.assertEqual(composer(True, "r", sources(flotte={"machines": [inter]}), "t")["niveau"], "stable")

    def test_un_disque_presque_plein_se_dit(self):
        self.assertEqual(composer(True, "r", sources(metriques={"disk": 90}), "t")["niveau"], "regarder")
        self.assertEqual(composer(True, "r", sources(metriques={"disk": 97}), "t")["niveau"], "panne")

    def test_un_compte_ne_voit_ni_la_machine_ni_la_flotte(self):
        r = composer(False, "bea", {"sites": {"sites": [site("a.fr")]}, "notifs": {"notifications": [{"niveau": "critique", "titre": "x", "id": 1}]}}, "t")
        self.assertFalse(r["admin"])
        for cle in ("flotte", "machine", "cassandra", "fil"):
            self.assertNotIn(cle, r)
        self.assertEqual(r["cloche"]["total"], 1)
        self.assertEqual([c["cle"] for c in r["compteurs"]], ["sites", "tls", "notifs"])

    def test_un_compte_n_est_pas_dit_muet_pour_ce_qu_il_ne_lit_pas(self):
        r = composer(False, "bea", {"sites": {"sites": [site("a.fr")]}}, "t")
        self.assertEqual(r["muettes"], [])
        self.assertEqual(r["niveau"], "stable")


class PointDEvolution(unittest.TestCase):
    def test_le_point_est_declare_sans_defaut(self):
        self.assertEqual(_DEFAUTS, [])
        self.assertEqual(_SVC.points("vue"), ["vue.verdict.composer"])
        self.assertEqual(_SVC.etat("vue", "verdict.composer")["sert"], "reference")

    def test_la_reference_rejoue_son_corpus_dore_a_l_identique(self):
        """Le corpus a été produit par l'ANCIEN composer, avant sa conversion en point d'évolution : l'égalité prouve que rien n'a changé."""
        corpus = json.loads((DOSSIER / "contrats" / "CN_verdict_composer.corpus.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(corpus["cas"]), 15)
        for c in corpus["cas"]:
            e = c["entree"]
            self.assertEqual(composer(e["admin"], e["compte"], e["sources"], e["quand"]), c["sortie"], c["cas"])

    def test_la_facade_refuse_de_court_circuiter_le_noyau(self):
        with self.assertRaises(TypeError):
            _facade.composer(True, "root", sources(), "t")

    def test_une_ec_defaillante_ne_change_rien_pour_l_utilisateur(self):
        """Le disjoncteur sur un vrai point : une EC qui rend n'importe quoi est remplacée par la référence, dans le même appel."""
        import shutil
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        d = tmp / "vue" / "verdict.composer"
        d.mkdir(parents=True)
        corps = "def composer(entree):" + chr(10) + "    return {'niveau': 'stable'}" + chr(10)
        tete = chr(10).join(["# ZONE       : EC", "# RUNTIME    : python", "# VERSION EC : EC1  #aaaaaa", "# CONTRAT PROUVÉ : @1.0"]) + chr(10)
        (d / "EC_verdict_composer__EC1.py").write_text(tete + corps, encoding="utf-8")
        (d / "ACTIVE").write_text("EC_verdict_composer__EC1.py", encoding="utf-8")
        svc = ServicePoints(tmp)
        svc.declarer(_manifeste.charger(DOSSIER / "CN_manifeste.toml"), DOSSIER)
        sortie = _facade.composer(True, "root", sources(metriques=None), "t", appeler=lambda p, e: svc.appeler("vue", p, e))
        self.assertEqual(sortie["niveau"], "inconnu")                      # la vérité de la référence, pas le « stable » mensonger de l'EC
        self.assertEqual(svc.etat("vue", "verdict.composer")["fautes_recentes"], 1)


if __name__ == "__main__":
    unittest.main()
