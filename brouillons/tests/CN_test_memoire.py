import unittest
import tempfile
import time
from pathlib import Path
import CN_test_noyau as base

def monde_memoire():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    racine = Path(tmp.name)
    mods = racine / "modules"
    for m in ("droits", "comptes", "memoire"):
        if (base.RACINE / "modules" / m).exists():
            shutil.copytree(base.RACINE / "modules" / m, mods / m)
    n = base.moteur.Noyau(racine / "d", mods, {}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    for m in ("comptes", "droits", "memoire"):
        n.activer(m)
    return tmp, n

class TestMemoire(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_memoire()
        self.addCleanup(self.tmp.cleanup)
        for c in ("chef@x.fr", "adm@x.fr", "bea@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": base.MDP}, compte="operateur")
        self.n.executeur.executer("droits.admin", "humain", {"compte": "adm@x.fr"}, compte="operateur")

    def ex(self, capacite, au_nom_de="operateur", **args):
        return self.n.executeur.executer(capacite, "humain", args, compte=au_nom_de)

    def test_ecrire_et_lister(self):
        r = self.ex("memoire.ecrire", au_nom_de="bea@x.fr", categorie="personne", cle="pref", valeur="j'aime le bleu", nature="constat")
        self.assertTrue(r["resultat"]["ok"])
        nid = r["resultat"]["id"]
        
        # bea can see it
        mems = self.ex("memoire.lister", au_nom_de="bea@x.fr")["resultat"]["memoires"]
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0]["cle"], "pref")
        
        # chef cannot see bea's memory
        mems_chef = self.ex("memoire.lister", au_nom_de="chef@x.fr")["resultat"]["memoires"]
        self.assertEqual(len(mems_chef), 0)
        
        # expirer
        self.ex("memoire.expirer", au_nom_de="bea@x.fr", mid=nid)
        self.assertEqual(len(self.ex("memoire.lister", au_nom_de="bea@x.fr")["resultat"]["memoires"]), 0)

    def test_rejet_secret(self):
        # The secret regex rejects standard tokens
        r = self.ex("memoire.ecrire", au_nom_de="bea@x.fr", categorie="config", cle="api", valeur="mot de passe ghp_123456789012345678901234567890123456", nature="constat")
        self.assertFalse(r["resultat"]["ok"])
        self.assertEqual(r["resultat"]["refus"], "secret")

    def test_rejet_creux(self):
        r = self.ex("memoire.ecrire", au_nom_de="bea@x.fr", categorie="lecon", cle="panne", valeur="examiner les journaux avant d'intervenir", nature="constat")
        self.assertFalse(r["resultat"]["ok"])
        self.assertEqual(r["resultat"]["refus"], "creux")
