"""Bancs du bureau du jour : les signaux que les modules déclarent, assemblés pour le compte qui regarde."""
import shutil
import sys
import tempfile
import textwrap
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur                      # noqa: E402

BEA, ROOT = "bea@x.fr", "root@x.fr"

FAUX_TOML = """
[module]
id = "faux"
nom = "Faux"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Module d'essai : des signaux qui répondent, qui cassent, qui sont réservés, qui sont lents."
famille = "reseau"

[[capacites]]
id = "ok"
libelle = "Un signal qui répond"
risque = "lecture"

[[capacites]]
id = "casse"
libelle = "Un signal qui plante"
risque = "lecture"

[[capacites]]
id = "machine"
libelle = "Un signal de la machine"
risque = "lecture"

[[capacites]]
id = "lent"
libelle = "Un signal lent"
risque = "lecture"

[[signaux]]
id = "ok"
libelle = "Source qui répond"
capacite = "ok"

[[signaux]]
id = "casse"
libelle = "Source cassée"
capacite = "casse"

[[signaux]]
id = "machine"
libelle = "Source de la machine"
capacite = "machine"
admin = true

[[signaux]]
id = "lent"
libelle = "Source lente"
capacite = "lent"
cadence_s = 3600
"""

FAUX_PY = """
import textwrap

def brancher(ctx):
    appels = {"lent": 0}
    def item(bande, titre):
        return {"bande": bande, "quoi": "tache", "titre": titre, "detail": "", "poids": 10}
    def ok(c):
        return {"items": [item("jour", "Un fait du jour"), {"bande": "inconnue", "titre": "refusé : bande inconnue"}, "pas un item"], "meta": {"x": 1}}
    def casse(c):
        raise ValueError("source HS")
    def machine(c):
        return {"items": [item("brule", "Disque plein")]}
    def lent(c):
        appels["lent"] += 1
        return {"items": [item("regarder", "Lent n°%d" % appels["lent"])]}
    ctx.implementer("ok", ok)
    ctx.implementer("casse", casse)
    ctx.implementer("machine", machine)
    ctx.implementer("lent", lent)
"""


def quand(jours, heure="09:00"):
    return (datetime.now() + timedelta(days=jours)).strftime("%Y-%m-%d") + " " + heure


class Jour(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        ig = shutil.ignore_patterns("__pycache__")
        for m in ("droits", "comptes", "jour", "taches", "agenda"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=ig)
        (mods / "faux").mkdir()
        (mods / "faux" / "CN_manifeste.toml").write_text(FAUX_TOML, encoding="utf-8")
        (mods / "faux" / "CN_module.py").write_text(textwrap.dedent(FAUX_PY), encoding="utf-8")
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "jour", "taches", "agenda", "faux"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ROOT, True)

    def ex(self, cap, compte=BEA, **args):
        return self.n.executeur.executer(cap, "humain", args, compte=compte)

    def jour(self, compte=BEA):
        r = self.ex("jour.aujourdhui", compte=compte)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def titres(self, j, bande):
        return [x["titre"] for b in j["bandes"] if b["cle"] == bande for x in b["items"]]

    def test_les_taches_se_rangent_par_bande_et_les_futures_ne_comptent_pas(self):
        for texte, jours in (("Rendre le devis", -2), ("Appeler le notaire", 0), ("Plus tard", 3)):
            self.assertEqual(self.ex("taches.creer", texte=texte, echeance=quand(jours))["statut"], "faite")
        j = self.jour()
        self.assertIn("Rendre le devis", self.titres(j, "brule"))
        self.assertIn("Appeler le notaire", self.titres(j, "jour"))
        self.assertFalse(any("Plus tard" in t for t in self.titres(j, "brule") + self.titres(j, "jour") + self.titres(j, "regarder")))
        self.assertEqual(j["tuiles"]["en_retard"], 1)
        self.assertEqual(j["tuiles"]["a_faire"], 2)                      # la tâche du jour et le fait du module d'essai
        self.assertIn("1 tâche", j["tuiles"]["en_retard_s"])

    def test_un_rappel_et_un_rendez_vous_du_jour(self):
        self.ex("agenda.rappel_enregistrer", texte="Rappeler Sandrine", echeance=quand(0, "14:30"))
        self.ex("agenda.rappel_enregistrer", texte="Rappel oublié", echeance=quand(-1))
        self.ex("agenda.evenement_enregistrer", titre="Réunion", debut=quand(0, "10:00"), fin=quand(0, "11:00"))
        j = self.jour()
        self.assertIn("Rappel oublié", self.titres(j, "brule"))
        jour = {x["titre"]: x for b in j["bandes"] if b["cle"] == "jour" for x in b["items"]}
        self.assertEqual(jour["Rappeler Sandrine"]["geste"], ["Reporter", "reporter"])
        self.assertEqual(jour["Réunion"]["detail"], "10:00")

    def test_une_source_en_panne_se_voit_et_ne_vide_pas_les_autres(self):
        j = self.jour()
        self.assertEqual(j["pannes"], ["casse"])
        self.assertIn("Source cassée : lecture en panne", self.titres(j, "regarder"))
        self.assertIn("Un fait du jour", self.titres(j, "jour"))

    def test_un_item_mal_forme_est_ecarte(self):
        j = self.jour()
        tout = [x["titre"] for b in j["bandes"] for x in b["items"]]
        self.assertFalse(any("refusé" in t for t in tout))
        self.assertNotIn("pas un item", tout)

    def test_la_machine_est_reservee_a_l_administrateur(self):
        self.assertNotIn("Disque plein", self.titres(self.jour(BEA), "brule"))
        self.assertIn("Disque plein", self.titres(self.jour(ROOT), "brule"))
        self.assertFalse(self.jour(BEA)["admin"])
        self.assertTrue(self.jour(ROOT)["admin"])

    def test_une_source_lente_n_est_relue_qu_apres_sa_cadence(self):
        a = self.titres(self.jour(), "regarder")
        b = self.titres(self.jour(), "regarder")
        self.assertIn("Lent n°1", a)
        self.assertIn("Lent n°1", b)                                      # gardé : la source n'a pas été relue
        self.assertNotIn("Lent n°2", b)

    def test_un_compte_ne_voit_que_ses_taches(self):
        self.ex("taches.creer", texte="Secret de Bea", echeance=quand(-1))
        self.assertNotIn("Secret de Bea", self.titres(self.jour(ROOT), "brule"))
        self.assertIn("Secret de Bea", self.titres(self.jour(BEA), "brule"))


if __name__ == "__main__":
    unittest.main()
