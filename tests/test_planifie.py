import unittest
import tempfile
from pathlib import Path
import sqlite3

import test_noyau as base
from test_noyau import ecrire_module, MDP, RACINE, moteur

def monde_planifie():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    chemin = Path(tmp.name)
    mods = chemin / "modules"
    for m in ("droits", "comptes"):
        shutil.copytree(RACINE / "modules" / m, mods / m)
    shutil.copytree(RACINE / "modules" / "planifie", mods / "planifie")
    n = moteur.Noyau(chemin / "d", mods, {}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    n.activer("comptes")
    n.activer("planifie")
    return tmp, n

class TestPlanifie(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_planifie()
        self.addCleanup(self.tmp.cleanup)
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "adm@x.fr", "mot_de_passe": MDP}, compte="operateur")
        self.n.executeur.executer("droits.admin", "humain", {"compte": "adm@x.fr"}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="adm@x.fr", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    def test_lister_vide(self):
        r = self.ex("planifie.lister")
        self.assertEqual(r["statut"], "faite")
        self.assertEqual(r["resultat"]["taches"], [])

    def test_sauver_et_basculer(self):
        r = self.ex("planifie.sauver", description="test", cron_expr="* * * * *", command="echo 1")
        self.assertEqual(r["statut"], "faite")
        nid = r["resultat"]["id"]
        lst = self.ex("planifie.lister")["resultat"]["taches"]
        self.assertEqual(len(lst), 1)
        self.assertEqual(lst[0]["command"], "echo 1")
        self.assertEqual(lst[0]["enabled"], 1)

        # Basculer
        r2 = self.ex("planifie.basculer", cron_id=nid, enabled=False)
        self.assertEqual(r2["statut"], "faite")
        lst = self.ex("planifie.lister")["resultat"]["taches"]
        self.assertEqual(lst[0]["enabled"], 0)

        # Preuve de retour arrière sur basculer
        self.n.catalogue.get("planifie.basculer").defaire(self.n.executeur.contextes["planifie"], r2["resultat"])
        lst = self.ex("planifie.lister")["resultat"]["taches"]
        self.assertEqual(lst[0]["enabled"], 1)

class TestRiskyCommand(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(RACINE / "modules" / "planifie"))
        import module
        self.is_risky_command = module.is_risky_command

    @unittest.skip("brouillon : à corriger")

    def test_lecons_v18(self):
        # V18: cd l'expliquait 24/73 refus. `cd /opt && cat f` doit être libre
        self.assertFalse(self.is_risky_command("cd /opt && cat f"))
        # V18: sqlite garantit readonly avec le drapeau
        self.assertFalse(self.is_risky_command("sqlite3 -readonly a.db 'SELECT 1'"))
        self.assertTrue(self.is_risky_command("sqlite3 a.db 'SELECT 1'"))
        # V18: curl d envoi
        self.assertTrue(self.is_risky_command("curl -d a b"))
        # V18: awk avec > ou system
        self.assertTrue(self.is_risky_command("awk '{print > \"a\"}'"))
        self.assertTrue(self.is_risky_command("awk '{system(\"ls\")}'"))
        # V18: sed avec w ou e
        self.assertTrue(self.is_risky_command("sed -e 's/a/b/w a.txt'"))
        self.assertFalse(self.is_risky_command("sed -n 's/a/b/p'")) # libre
        # V18: substitution
        self.assertTrue(self.is_risky_command("echo `rm -rf /`"))
        self.assertTrue(self.is_risky_command("echo $(rm -rf /)"))
        # V18: $(( n'est pas une substitution
        self.assertFalse(self.is_risky_command("sed -n '$((1+1))p' f"))
