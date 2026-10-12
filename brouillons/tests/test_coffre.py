import unittest
import tempfile
from pathlib import Path
import test_noyau as base

COFFRE_TOML = """
[module]
id = "coffre"
nom = "Coffre et Sécurité"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Bancs d'essai"

[[droits]]
id = "gerer"
libelle = "Gérer"
defaut = false

[[capacites]]
id = "creer_secret"
risque = "eleve"
droit = "gerer"
preuve = "..."
retour = "..."

[[capacites]]
id = "ms_ajouter"
risque = "moyen"
droit = "gerer"
preuve = "..."
retour = "..."
"""

class TestCoffre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.mods = self.base / "modules"
        self.mods.mkdir()
        
        # On importe les modules de base + le nôtre
        import shutil
        for m in ("droits", "comptes"):
            shutil.copytree(base.RACINE / "modules" / m, self.mods / m)
            
        with open(base.RACINE / "modules" / "coffre" / "module.py") as f:
            py_code = f.read()
            
        base.ecrire_module(self.mods, "coffre", COFFRE_TOML, py_code)
        
        self.n = base.moteur.Noyau(self.base / "d", self.mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        self.n.activer("comptes")
        self.n.activer("coffre")
        
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "admin@x.fr", "mot_de_passe": base.MDP}, compte="operateur")
        self.n.executeur.executer("droits.accorder", "humain", {"compte": "admin@x.fr", "droit": "coffre.gerer"}, compte="operateur")

    def tearDown(self):
        self.tmp.cleanup()

    def ex(self, capacite, au_nom_de="admin@x.fr", **args):
        return self.n.executeur.executer(capacite, "humain", args, compte=au_nom_de)

    @unittest.skip("brouillon : à corriger")

    def test_creer_secret_sans_droit(self):
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "user@x.fr", "mot_de_passe": base.MDP}, compte="operateur")
        r = self.ex("coffre.creer_secret", au_nom_de="user@x.fr", nom="mon_secret")
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("coffre.gerer", r["raison"])

    @unittest.skip("brouillon : à corriger")

    def test_creer_secret_audit_journal(self):
        r = self.ex("coffre.creer_secret", nom="api_key_prod")
        self.assertEqual(r["statut"], "faite")
        
        # Vérifier l'audit en base (la table vault_audit a bien enregistré l'action)
        with self.n.contextes["coffre"].stockage.transaction() as c:
            lignes = c.execute("SELECT * FROM vault_audit WHERE secret_name='api_key_prod'").fetchall()
            self.assertEqual(len(lignes), 1)
            self.assertEqual(lignes[0]["action"], "create")
            self.assertEqual(lignes[0]["username"], "admin@x.fr")

    @unittest.skip("brouillon : à corriger")

    def test_ms_ajouter_preuve_defaire(self):
        r = self.ex("coffre.ms_ajouter", nom="srv-bd", url="https://srv", token="xyz")
        self.assertEqual(r["statut"], "faite")
        
        # Preuve (relire l'enregistrement via la capacité de preuve)
        ctx = self.n.contextes["coffre"]
        self.assertTrue(self.n.catalogue.get("coffre.ms_ajouter").prouver(ctx, r["resultat"]))
        
        # Retour arrière (defaire)
        self.n.catalogue.get("coffre.ms_ajouter").defaire(ctx, r["resultat"])
        
        with ctx.stockage.transaction() as c:
            lignes = c.execute("SELECT * FROM multiserver_tokens WHERE nom='srv-bd'").fetchall()
            self.assertEqual(len(lignes), 0)
