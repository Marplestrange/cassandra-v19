"""Bancs du canvas : les départs, les gestes, le plan (écrit/relu, réversible, ce qu'on jette est dit)."""
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
        for m in ("canvas", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "canvas"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["canvas"]

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("canvas." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_les_departs_et_les_gestes_sont_listes(self):
        self.assertGreaterEqual(len(self.s("departs")["departs"]), 4)
        self.assertEqual(len(self.s("gestes")["gestes"]), 5)

    def test_un_plan_se_ecrit_se_relit_et_se_defait(self):
        plan = {"nodes": [{"id": "a", "type": "text", "text": "Idée", "x": 10, "y": 20}],
                "edges": []}
        res = self.ex("canvas.plan_ecrire", ref="note-1", plan=plan)
        self.assertEqual(res["statut"], "faite", res)
        lu = self.s("plan_lire", ref="note-1")
        self.assertEqual(lu["plan"]["nodes"][0]["text"], "Idée")
        self.n.catalogue.get("canvas.plan_ecrire").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("plan_lire", ref="note-1")["neuf"], True)

    def test_une_carte_hors_specification_est_dite(self):
        plan = {"nodes": [{"id": "a", "type": "truc-bizarre"}], "edges": []}
        res = self.s("plan_ecrire", ref="n2", plan=plan)
        self.assertTrue(any("hors spécification" in s for s in res["soucis"]))

    def test_une_fleche_vers_une_carte_disparue_est_dite(self):
        plan = {"nodes": [{"id": "a", "type": "text"}],
                "edges": [{"fromNode": "a", "toNode": "fantome"}]}
        res = self.s("plan_ecrire", ref="n3", plan=plan)
        self.assertEqual(res["liens"], 0)
        self.assertTrue(any("disparue" in s for s in res["soucis"]))


if __name__ == "__main__":
    unittest.main()
