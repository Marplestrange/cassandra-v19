import unittest
import tempfile
from pathlib import Path
import CN_test_noyau as base

def monde_sauvegardes():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    chemin = Path(tmp.name)
    mods = chemin / "modules"
    for m in ("droits", "comptes", "sauvegardes"):
        src = base.RACINE / "modules" / m
        if src.exists():
            shutil.copytree(src, mods / m)
    n = base.moteur.Noyau(chemin / "d", mods, {}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    for m in ("comptes", "sauvegardes"):
        n.activer(m)
    return tmp, n

class SauvegardesTest(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_sauvegardes()
        self.addCleanup(self.tmp.cleanup)
        for c in ("adm@x.fr", "bea@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": base.MDP}, compte="operateur")
        self.n.executeur.executer("droits.admin", "humain", {"compte": "adm@x.fr"}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="operateur", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    def test_enregistrer_et_lister(self):
        r = self.ex("sauvegardes.enregistrer", au_nom_de="adm@x.fr", nom="Mon Plan", source="/tmp", destination="b2:bucket")
        self.assertEqual(r["statut"], "faite")
        
        # bea a le droit de lire
        r2 = self.ex("sauvegardes.lister", au_nom_de="bea@x.fr")
        self.assertEqual(r2["statut"], "faite")
        self.assertEqual(len(r2["resultat"]["plans"]), 1)
        self.assertEqual(r2["resultat"]["plans"][0]["nom"], "Mon Plan")
        
    def test_refus_droits(self):
        r = self.ex("sauvegardes.enregistrer", au_nom_de="bea@x.fr", nom="Mon Plan", source="/tmp", destination="b2:bucket")
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("droit", r["raison"])
        
    def test_supprimer_plan_fp(self):
        # V18 leçon : un plan FastPanel se supprime dans le panneau
        r = self.ex("sauvegardes.supprimer", au_nom_de="adm@x.fr", id="fp:123")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("se supprime dans le panneau", r["erreur"])
        
    def test_lancer_et_defaire(self):
        r = self.ex("sauvegardes.enregistrer", au_nom_de="adm@x.fr", nom="Plan test", source="/tmp", destination="b2:bucket", date_dossier=0)
        pid = r["resultat"]["id"]
        
        l = self.ex("sauvegardes.lancer", au_nom_de="adm@x.fr", id=pid, blanc=True)
        self.assertEqual(l["statut"], "faite")
        self.assertTrue(l["resultat"]["blanc"])
        
        u = self.n.catalogue.get("sauvegardes.lancer").defaire(self.n.executeur.contextes["sauvegardes"], l["resultat"])
        self.assertIsNone(u)

    def test_couverture(self):
        r = self.ex("sauvegardes.couverture", au_nom_de="adm@x.fr")
        self.assertEqual(r["statut"], "faite")
        # Les zones systémiques (mémoire et coffre) remonteront comme non protégées (trous)
        self.assertTrue(len(r["resultat"]["trous"]) >= 2)
