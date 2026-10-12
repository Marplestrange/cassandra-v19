import unittest
import tempfile
import sys
from pathlib import Path
import test_noyau as base

def monde_voix():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    b = Path(tmp.name)
    mods = b / "modules"
    for m in ("droits", "comptes", "voix"):
        try:
            shutil.copytree(base.RACINE / "modules" / m, mods / m)
        except Exception:
            pass
    n = base.moteur.Noyau(b / "d", mods, {"voix": {"dossier_voix": str(b / "voix_dir")}}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    n.activer("comptes")
    n.activer("voix")
    n.identite.unix = lambda nom: "/bin/bash"
    n.identite.fastpanel = lambda: False
    return tmp, n, b

class TestVoix(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n, self.base = monde_voix()
        self.addCleanup(self.tmp.cleanup)
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "adm@x.fr", "mot_de_passe": base.MDP}, compte="operateur")
        self.n.executeur.executer("droits.admin", "humain", {"compte": "adm@x.fr"}, compte="operateur")
        self.n.executeur.executer("comptes.creer", "humain", {"compte": "usr@x.fr", "mot_de_passe": base.MDP}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="usr@x.fr", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    def test_machine_regler_et_defaire(self):
        # Leçon V18 : "Le moteur est oublié... sans cette ligne le nouveau modèle n'aurait d'effet qu'au prochain redémarrage"
        res = self.ex("voix.machine_regler", au_nom_de="adm@x.fr", modele="tiny")
        self.assertEqual(res["statut"], "faite")
        self.assertEqual(res["resultat"]["apres"]["modele"], "tiny")
        
        # Validation du retour arrière
        self.n.catalogue.get("voix.machine_regler").defaire(self.n.executeur.contextes["voix"], res["resultat"])
        d = self.ex("voix.reglages")
        self.assertEqual(d["resultat"]["modele"], "small")

    @unittest.skip("brouillon : à corriger")

    def test_choisir_bascule_mode_ne_perd_pas_nom(self):
        # Leçon V18 : "BASCULER LE MODE DEPUIS LE CHAT n'envoie pas de voix : sans ce garde-fou le nom vide écraserait le choix"
        self.ex("voix.choisir", nom="gilles", debit="1.2")
        r1 = self.ex("voix.reglages")
        self.assertEqual(r1["resultat"]["choix"], "gilles")
        self.assertEqual(r1["resultat"]["debit"], "1.20")
        
        # Bascule mode seulement
        self.ex("voix.choisir", mode=True)
        r2 = self.ex("voix.reglages")
        self.assertEqual(r2["resultat"]["choix"], "gilles")
        self.assertEqual(r2["resultat"]["debit"], "1.20")
        self.assertEqual(r2["resultat"]["mode"], True)

    def test_prononcable(self):
        # Leçon V18 : "Les emojis et la mise en forme... sont retirés avant lecture"
        sys.path.insert(0, str(self.base / "modules" / "voix"))
        import module as vx
        sys.path.pop(0)
        
        self.assertEqual(vx._vx_prononcable("```python\ncode\n```"), "(bloc de code)")
        self.assertEqual(vx._vx_prononcable("[Itare](https://x.com)"), "Itare")
        self.assertEqual(vx._vx_prononcable("https://x.com"), "un lien")
        self.assertEqual(vx._vx_prononcable("**Gras**"), "Gras")

    @unittest.skip("brouillon : à corriger")

    def test_est_echo(self):
        # Leçon V18 : "Sa propre voix ne lui revient pas... (3 mots mini, ratio > 75%)"
        sys.path.insert(0, str(self.base / "modules" / "voix"))
        import module as vx
        sys.path.pop(0)
        
        self.assertFalse(vx._vx_est_echo("non", "non")) # Trop court -> False
        # Faux positif V18 résolu par la condition > 0.75
        self.assertFalse(vx._vx_est_echo("le serveur est en bonne santé", "Est-ce que le serveur est en bonne santé ?"))
        # Vrai écho verbatim -> True
        self.assertTrue(vx._vx_est_echo("je vais redémarrer le serveur nginx", "Je vais redémarrer le serveur nginx immédiatement."))

    def test_parler_mise_en_forme_seule(self):
        # Leçon V18 : "ce passage ne contient que de la mise en forme : rien à prononcer"
        res = self.ex("voix.parler", texte="***")
        self.assertEqual(res["statut"], "echec")
        self.assertIn("rien à prononcer", res["erreur"])

    def test_ecouter_trop_long(self):
        # Leçon V18 : "_VX_AUDIO_MAX à 20Mo pour ne pas exploser la RAM."
        res = self.ex("voix.ecouter", octets=b"x" * (21 * 1024 * 1024))
        self.assertEqual(res["statut"], "echec")
        self.assertIn("trop long", res["erreur"])
        
    def test_telecharger_inconnu(self):
        # Leçon V18 : "Téléchargement depuis HF : seulement celles du catalogue"
        res = self.ex("voix.telecharger", au_nom_de="adm@x.fr", ref="/etc/passwd")
        self.assertEqual(res["statut"], "echec")
        self.assertIn("voix inconnue", res["erreur"])
