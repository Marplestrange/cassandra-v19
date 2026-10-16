"""Bancs de la vue d'ensemble : le verdict est composé, et une source muette n'est jamais comptée « tranquille »."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from modules.vue.composer import composer   # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
