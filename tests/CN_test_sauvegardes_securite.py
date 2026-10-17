"""Bancs des sauvegardes (plans, réversibles) et de la sécurité (journal, audits)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

BEA = "bea@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("sauvegardes", "securite", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("sauvegardes", installe=True, par="test")   # le module a un script d'installation
        self.n.etat_modules.poser("securite", installe=True, par="test")
        for m in ("droits", "comptes", "sauvegardes", "securite"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(BEA, True)
        self.ctx = self.n.executeur.contextes["sauvegardes"]

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex(cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def echec(self, cap, compte=BEA, **args):
        r = self.ex(cap, compte=compte, **args)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r.get("erreur") or r.get("raison") or ""

    # ── sauvegardes ─────────────────────────────────────────────────────────
    def test_un_plan_se_cree_et_se_defait(self):
        res = self.ex("sauvegardes.plan_save", nom="Documents → NAS", portee="doc", source="/srv/documents", destination="nas:backup")
        self.assertEqual(res["statut"], "faite", res)
        pid = res["resultat"]["id"]
        self.assertIn(pid, [p["id"] for p in self.s("sauvegardes.plans")["plans"]])
        self.n.catalogue.get("sauvegardes.plan_save").defaire(self.ctx, res["resultat"])
        self.assertNotIn(pid, [p["id"] for p in self.s("sauvegardes.plans")["plans"]])

    def test_une_portee_inconnue_est_refusee(self):
        self.assertIn("portée", self.echec("sauvegardes.plan_save", nom="x", portee="lune", source="a", destination="b"))

    def test_la_couverture_dit_ce_qui_n_est_pas_couvert(self):
        cov = self.s("sauvegardes.couverture")
        self.assertIn("doc", cov["non_couverts"])

    # ── sécurité ─────────────────────────────────────────────────────────────
    def test_les_gestes_sont_listes(self):
        self.assertGreaterEqual(len(self.s("securite.gestes")["gestes"]), 5)

    def test_un_geste_s_inscrit_au_journal_et_se_defait(self):
        res = self.ex("securite.noter", geste="bannir-ou-debannir-une-adresse", cible="1.2.3.4", detail="test", ok=True)
        self.assertEqual(res["statut"], "faite", res)
        self.assertGreaterEqual(len(self.s("securite.journal")["journal"]), 1)
        self.n.catalogue.get("securite.noter").defaire(self.n.executeur.contextes["securite"], res["resultat"])
        self.assertEqual(self.s("securite.journal")["journal"], [])

    def test_un_audit_se_pose(self):
        res = self.ex("securite.audit_poser", modele="gpt", titre="Audit de test", corps="rien à signaler")
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("securite.audits")["audits"][0]["titre"], "Audit de test")


if __name__ == "__main__":
    unittest.main()
