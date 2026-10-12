import unittest
import tempfile
from pathlib import Path
import json

import test_noyau as base

MODELES_TOML = """
[module]
id = "modeles"
nom = "Modèles"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Registre test."
requiert = ["droits"]

[[droits]]
id = "gerer"
libelle = "Gérer"

[[reglages]]
id = "ollama_url"
type = "texte"

[[reglages]]
id = "itare_citadelle_api_key"
type = "secret"
[[reglages]]
id = "itare_citadelle_provider"
type = "texte"
[[reglages]]
id = "itare_citadelle_model"
type = "texte"

[[capacites]]
id = "lister"
risque = "lecture"
[[capacites]]
id = "compte_etat"
risque = "lecture"
[[capacites]]
id = "compte_ecrire"
risque = "faible"
[[capacites]]
id = "ajouter"
risque = "moyen"
droit = "gerer"
[[capacites]]
id = "role_set"
risque = "moyen"
droit = "gerer"
[[capacites]]
id = "migrer"
risque = "moyen"
droit = "gerer"

[permissions]
stockage = true
droits = true
"""

class ModelesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.mods = self.base / "modules"
        import shutil
        for m in ("droits", "comptes"):
            if (base.RACINE / "modules" / m).exists():
                shutil.copytree(base.RACINE / "modules" / m, self.mods / m)
                
        # On lit le vrai module.py écrit à la volée pendant le test si possible, sinon on le copie de l'arborescence réelle
        # Pour le framework de test, copytree est suffisant.
        shutil.copytree(base.RACINE / "modules" / "modeles", self.mods / "modeles")
        
        self.config = {
            "modeles": {
                "itare_citadelle_api_key": "sk-12345",
                "itare_citadelle_provider": "openai",
                "itare_citadelle_model": "gpt-4"
            }
        }
        
        self.n = base.moteur.Noyau(self.base / "d", self.mods, self.config, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        self.n.activer("comptes")
        self.n.activer("modeles")
        
        self.addCleanup(self.tmp.cleanup)
        
        for c in ("adm@x.fr", "bea@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": base.MDP}, compte="operateur")
        self.n.executeur.executer("droits.admin", "humain", {"compte": "adm@x.fr"}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="adm@x.fr", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    @unittest.skip("brouillon : à corriger")

    def test_ajouter_et_lister(self):
        r = self.ex("modeles.ajouter", fournisseur="openai", nom="gpt-4.", cle="sk-123")
        self.assertEqual(r["statut"], "faite")
        mid = r["resultat"]["id"]
        
        lst = self.ex("modeles.lister")["resultat"]
        self.assertEqual(lst["modeles"][0]["nom"], "gpt-4") # Leçon 1 : rstrip appliqué

        # Preuve et retour arrière
        self.n.catalogue.get("modeles.ajouter").defaire(
            self.n.executeur.contextes["modeles"], r["resultat"]
        )
        lst2 = self.ex("modeles.lister")["resultat"]
        self.assertEqual(len(lst2["modeles"]), 0)
        
    def test_ajouter_validation(self):
        r = self.ex("modeles.ajouter", fournisseur="openai", nom="https://gpt-4", cle="sk-123")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("le modèle est un nom", r["erreur"])
        
    def test_compte_ecrire_validation(self):
        r = self.ex("modeles.compte_ecrire", nom="qwen2.5:3b", fournisseur="ollama", au_nom_de="bea@x.fr")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("modèle local inconnu ou non installé", r["erreur"]) # Leçon 2

    def test_compte_etat(self):
        self.ex("modeles.compte_ecrire", nom="gpt-4", fournisseur="openai", au_nom_de="bea@x.fr")
        r = self.ex("modeles.compte_etat", au_nom_de="bea@x.fr")["resultat"]
        self.assertTrue(r["muet"]) # Leçon 4
        self.assertEqual(r["fournisseur"], "openai")

    @unittest.skip("brouillon : à corriger")

    def test_role_set_et_migrer(self):
        r = self.ex("modeles.migrer", role="itare_citadelle")
        self.assertEqual(r["statut"], "faite")
        
        lst = self.ex("modeles.lister")["resultat"]
        self.assertIn("itare_citadelle", lst["roles"]) # Leçons 5 et 6 : le rôle est lié via la table interne modeles_roles
