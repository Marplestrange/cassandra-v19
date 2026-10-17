import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

try:
    import CN_test_noyau as base
except ImportError:
    base = None

class SitesTest(unittest.TestCase):
    def setUp(self):
        if not base:
            self.skipTest("CN_test_noyau.py manquant")
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.mods = self.base / "modules"
        
        import shutil
        for m in ("droits", "comptes", "sites"):
            src = base.RACINE / "modules" / m
            if src.exists():
                shutil.copytree(src, self.mods / m)
                
        self.n = base.moteur.Noyau(self.base / "d", self.mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        self.n.activer("comptes")
        self.n.activer("sites")
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.addCleanup(self.tmp.cleanup)

        for c in ("chef@x.fr", "user@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": base.MDP}, compte="operateur")
        self.n.executeur.executer("droits.admin", "humain", {"compte": "chef@x.fr"}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="operateur", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    def test_declarer_et_retirer(self):
        r = self.ex("sites.declarer", au_nom_de="user@x.fr", domain="mon-site.fr")
        self.assertEqual(r["statut"], "faite")
        
        # Preuve
        ctx = self.n.executeur.contextes["sites"]
        mod = self.n.catalogue.get("sites.declarer")
        self.assertTrue(mod.prouver(ctx, r["resultat"]))
        
        # Retrait
        r2 = self.ex("sites.retirer", au_nom_de="user@x.fr", domain="mon-site.fr")
        self.assertEqual(r2["statut"], "faite")
        
    def test_refus_domaine_invalide(self):
        r = self.ex("sites.declarer", au_nom_de="user@x.fr", domain="not a domain")
        self.assertEqual(r["statut"], "echec")
        
    @unittest.skip("brouillon : à corriger")
        
    def test_attribuer_admin(self):
        # Admin attribue à user
        r = self.ex("sites.attribuer", au_nom_de="chef@x.fr", domain="admin-site.fr", compte="user@x.fr")
        self.assertEqual(r["statut"], "faite")
        
        # User ne peut pas attribuer
        r2 = self.ex("sites.attribuer", au_nom_de="user@x.fr", domain="autre-site.fr", compte="chef@x.fr")
        self.assertEqual(r2["statut"], "echec")

    @unittest.skip("brouillon : à corriger")

    def test_lecon_site_up_redirections(self):
        # V18 : "N'exiger que 200 était faux : un site qui force HTTPS répond 301. Une redirection est une réponse, pas une panne."
        class MockResponse:
            def getcode(self): return 301
            def __enter__(self): return self
            def __exit__(self, *args): pass

        with patch("urllib.request.urlopen", return_value=MockResponse()):
            self.ex("sites.declarer", au_nom_de="user@x.fr", domain="redir.fr")
            ctx = self.n.executeur.contextes["sites"]
            # Appel manuel du moteur pour la sonde
            ctx._moteurs["sonde"](ctx)
            
            # Le site doit être up=1 dans la DB
            res = ctx.stockage.lire("SELECT up FROM site_state_seen WHERE domain='redir.fr'")
            self.assertEqual(res[0]["up"], 1, "Une redirection 3xx DOIT être considérée comme 'en ligne'")

    @unittest.skip("brouillon : à corriger")

    def test_lecon_site_probe_lenteur(self):
        # V18 : "Le code seul ne suffit pas : un site qui répond 200 en 8 secondes est en panne"
        # On vérifie que si le timeout est atteint (timeout de `urlopen`), l'erreur est capturée et "up" mis à 0.
        import urllib.error
        with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
            self.ex("sites.declarer", au_nom_de="user@x.fr", domain="lent.fr")
            ctx = self.n.executeur.contextes["sites"]
            ctx._moteurs["sonde"](ctx)
            
            res = ctx.stockage.lire("SELECT up FROM site_state_seen WHERE domain='lent.fr'")
            self.assertEqual(res[0]["up"], 0, "Un site en timeout doit être 'hors ligne'")

    def test_lecon_databases(self):
        # V18 : "Le rattachement vient de db.site_id, pas de ressemblance de noms. Deviner marcherait 9 fois sur 10 et la 10e divulguerait autrui."
        r = self.ex("sites.databases", au_nom_de="user@x.fr", domain="exemple.com")
        # Le stub retourne [] tant que FastPanel n'est pas branché correctement via le courtier, interdisant le guess global.
        self.assertEqual(r["resultat"]["bases"], [])
