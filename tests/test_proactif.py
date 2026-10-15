"""Bancs de la proactivité : autonomie, savoir-faire mesuré (promotion à dix réussites, rétrogradation),
l'ombre (jamais exécutée), les incidents et le fil."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import main as moteur                      # noqa: E402

BEA = "bea@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("proactif", "droits", "comptes", "reglages"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "reglages", "proactif"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(BEA, True)
        self.ctx = self.n.executeur.contextes["proactif"]
        self.db = self.ctx.stockage

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("proactif." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def echec(self, cap, compte=BEA, **args):
        r = self.ex("proactif." + cap, compte=compte, **args)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r.get("erreur") or r.get("raison") or ""

    def test_l_autonomie_a_un_palier_et_se_regle(self):
        a = self.s("autonomie")
        self.assertIn(a["palier"], ("observer", "proposer", "maitrise", "raconter"))
        res = self.ex("proactif.autonomie_set", palier="maitrise", pause=False)
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("autonomie")["palier"], "maitrise")
        # le retour arrière remet le palier d'avant
        self.n.catalogue.get("proactif.autonomie_set").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("autonomie")["palier"], a["palier"])

    def test_un_savoir_faire_se_confie_a_dix_reussites(self):
        # un playbook sans dix réussites ne se confie pas
        self.db.ecrire("INSERT INTO proactive_playbooks (signature, action_kind, action, successes) VALUES ('g1','x','y',4)")
        self.assertIn("réussites", self.echec("savoir_etat", signature="g1", etat="auto"))
        # à dix réussites, il se confie ; puis se retire
        self.db.ecrire("UPDATE proactive_playbooks SET successes=10 WHERE signature='g1'")
        res = self.ex("proactif.savoir_etat", signature="g1", etat="auto")
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("savoirs")["savoirs"][0]["etat"], "auto")
        self.n.catalogue.get("proactif.savoir_etat").defaire(self.ctx, res["resultat"])
        self.assertEqual(self.s("savoirs")["savoirs"][0]["etat"], "proposition")

    def test_une_proposition_s_accepte_et_se_defait(self):
        self.db.ecrire("INSERT INTO pf_savoir_props (signature, action_kind, action, vu) VALUES ('g2','x','y',3)")
        res = self.ex("proactif.savoir_accepter", signature="g2")
        self.assertEqual(res["statut"], "faite", res)
        self.assertTrue(any(x["signature"] == "g2" for x in self.s("savoirs")["savoirs"]))
        self.n.catalogue.get("proactif.savoir_accepter").defaire(self.ctx, res["resultat"])
        self.assertFalse(any(x["signature"] == "g2" for x in self.s("savoirs")["savoirs"]))

    def test_l_ombre_se_juge(self):
        self.db.ecrire("INSERT INTO pf_ombre (fkey, signature, action_kind, action, titre, motif) VALUES ('f1','g3','x','y','t','m')")
        o = self.s("ombre")["ombre"]
        self.assertEqual(len(o), 1)
        res = self.ex("proactif.ombre_avis", oid=o[0]["id"], avis="juste")
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("ombre")["justes"], 1)

    def test_le_fil_fond_l_ombre_et_les_savoirs(self):
        self.db.ecrire("INSERT INTO pf_ombre (fkey, signature, action_kind, action, titre, motif) VALUES ('f1','g4','x','y','alerte disque','palier observer')")
        fil = self.s("fil")["fil"]
        self.assertTrue(any(x["source"] == "OMBRE" for x in fil))

    # ── l'automatisme (autonomie par domaine et par geste) ─────────────────
    def test_le_catalogue_liste_les_gestes(self):
        cat = self.s("catalogue")
        self.assertGreater(len(cat["familles"]), 10)
        auto = next(f for f in cat["familles"] if f["id"] == "automatismes")
        self.assertTrue(any(g["id"] == "creer-ou-modifier-une-tache-planifiee" for g in auto["gestes"]))

    def test_regler_un_geste_et_revenir(self):
        res = self.ex("proactif.regler", cle="machine/relancer-un-service", reglages={"lv": "raconter"})
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("reglages")["reglages"]["g:machine/relancer-un-service"]["lv"], "raconter")
        self.n.catalogue.get("proactif.regler").defaire(self.ctx, res["resultat"])
        self.assertNotIn("g:machine/relancer-un-service", self.s("reglages")["reglages"])

    def test_un_geste_en_garde_dure_ne_depasse_pas_proposer(self):
        # « supprimer-un-secret » est en garde dure : il ne peut pas dépasser « proposer »
        r = self.ex("proactif.regler", cle="coffre/supprimer-un-secret", reglages={"lv": "raconter"})
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        self.assertIn("proposer", r.get("erreur") or "")

    def test_le_disjoncteur_se_debloque(self):
        self.db.ecrire("INSERT INTO autonomie_disj (cle, etat, raison) VALUES ('g:machine/relancer-un-service','declenche','3 échecs')")
        self.assertEqual(len(self.s("disjoncteurs")["disjoncteurs"]), 1)
        res = self.ex("proactif.debloquer", cle="machine/relancer-un-service")
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("disjoncteurs")["disjoncteurs"], [])

    def test_la_gouvernance_a_des_intouchables(self):
        g = self.s("gouvernance")
        self.assertIn("ragnar", g["intouchables"])


if __name__ == "__main__":
    unittest.main()
