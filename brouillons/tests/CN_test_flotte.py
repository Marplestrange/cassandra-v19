import unittest
import CN_test_noyau as base

class TestFlotte(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n, self.pannes = base.monde_notifs()
        self.addCleanup(self.tmp.cleanup)
        for c in ("chef@x.fr", "adm@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": base.MDP}, compte="operateur")
        self.n.executeur.executer("droits.admin", "humain", {"compte": "adm@x.fr"}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="adm@x.fr", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    @unittest.skip("brouillon : à corriger")

    def test_parc_lecture(self):
        r = self.ex("flotte.parc")
        self.assertEqual(r["statut"], "faite")

    @unittest.skip("brouillon : à corriger")

    def test_engagement_modifier_et_defaire(self):
        # Modifier l'engagement
        r = self.ex("flotte.engagement", nom="machine1", statut="intermittente")
        self.assertEqual(r["statut"], "faite")
        res = r["resultat"]
        self.assertEqual(res["apres"]["statut"], "intermittente")

        # Vérifier defaire
        self.n.catalogue.get("flotte.engagement").defaire(self.n.executeur.contextes["flotte"], res)
        # Relire
        r2 = self.ex("flotte.engagement", nom="machine1")
        self.assertEqual(r2["resultat"]["avant"]["statut"], "attendue")

    @unittest.skip("brouillon : à corriger")

    def test_sensorium_detecteur_delai(self):
        # V18 : une alerte n'est notifiée que si elle DURE 10 min.
        # En V19, le détecteur renvoie le constat seulement s'il est temps.
        ctx = self.n.executeur.contextes["flotte"]
        ctx.stockage.ecrire("INSERT INTO world_model(wkey, severity, value) VALUES('cpu.load', 'warning', 'elevé')")
        
        # Exécution du détecteur (premier passage, âge < 600)
        constats = ctx.detecteurs["alertes"](ctx)
        self.assertEqual(len(constats), 0, "L'alerte ne doit pas lever de constat immédiatement")
        
        # On recule la date de début de l'alerte pour simuler 10 minutes passées
        ctx.stockage.ecrire("UPDATE sensorium_alertes SET depuis = datetime('now', '-15 minutes')")
        constats = ctx.detecteurs["alertes"](ctx)
        self.assertEqual(len(constats), 1, "L'alerte lève le constat après 10 minutes")
