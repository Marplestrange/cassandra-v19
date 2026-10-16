"""Bancs de la gestion des modules : lister, activer, désactiver — avec les dépendances, les essentiels, la preuve et le retour."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import main as moteur                      # noqa: E402

ADMIN, SIMPLE = "root@x.fr", "bea@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("modules", "droits", "comptes", "taches", "notes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "modules"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ADMIN, True)
        self.ctx = self.n.executeur.contextes["modules"]

    def ex(self, cap, compte=ADMIN, **args):
        return self.n.executeur.executer("modules." + cap, "humain", args, compte=compte)

    def s(self, cap, **args):
        r = self.ex(cap, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def etat(self, mid):
        return next(m for m in self.s("lister")["modules"] if m["id"] == mid)["etat"]

    def test_le_catalogue_dit_l_etat_de_chacun(self):
        c = {m["id"]: m for m in self.s("lister")["modules"]}
        self.assertEqual(c["modules"]["etat"], "actif")
        self.assertEqual(c["taches"]["etat"], "inactif")
        self.assertIn("peut_activer", c["taches"])

    def test_le_catalogue_dit_si_l_instance_gere_ses_modules(self):
        self.assertTrue(self.s("lister")["gere"])

    def test_la_fiche_dit_ce_que_le_module_sait_faire(self):
        self.s("activer", module="taches")
        self.n.recharger()                                  # l'état s'écrit seul ; le noyau en marche branche au tour suivant
        f = self.s("fiche", module="taches")
        self.assertEqual(f["module"]["id"], "taches")
        caps = {c["id"]: c for c in f["capacites"]}
        self.assertIn("lister", caps)
        self.assertFalse(caps["lister"]["ecrit"])
        ecr = [c for c in f["capacites"] if c["ecrit"]]
        self.assertTrue(ecr and all("parametres" in c and "retour" in c for c in ecr))

    def test_une_fiche_de_module_inconnu_est_refusee(self):
        self.assertEqual(self.ex("fiche", module="nexiste-pas")["statut"], "echec")

    def test_activer_puis_defaire(self):
        res = self.ex("activer", module="taches")
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.etat("taches"), "actif")
        self.n.catalogue.get("modules.activer").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.etat("taches"), "inactif")

    def test_desactiver_puis_defaire(self):
        self.s("activer", module="taches")
        res = self.ex("desactiver", module="taches")
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.etat("taches"), "inactif")
        self.n.catalogue.get("modules.desactiver").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.etat("taches"), "actif")

    def test_un_essentiel_ne_se_desactive_pas(self):
        r = self.ex("desactiver", module="droits")
        self.assertEqual(r["statut"], "echec", r)
        self.assertEqual(self.etat("droits"), "actif")

    def test_un_module_inconnu_est_refuse(self):
        self.assertEqual(self.ex("activer", module="nexiste-pas")["statut"], "echec")

    def test_sans_le_droit_rien_ne_bouge(self):
        for cap in ("lister", "activer"):
            r = self.ex(cap, compte=SIMPLE, module="taches")
            self.assertEqual(r["statut"], "refuse", (cap, r))
        self.assertEqual(self.etat("taches"), "inactif")


if __name__ == "__main__":
    unittest.main()
