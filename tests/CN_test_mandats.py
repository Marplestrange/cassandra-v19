# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des mandats d'envoi
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #4509f1
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des mandats d'envoi : l'écriture bornée, la règle « l'adresse ne vient pas de la demande », la lecture à voix haute.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=4509f1 ▼▼▼
"""Bancs des mandats d'envoi : l'écriture bornée, la règle « l'adresse ne vient pas de la demande », la lecture à voix haute."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

BEA = "bea@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("mandats", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "mandats"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["mandats"]

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex("mandats." + cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def echec(self, cap, compte=BEA, **args):
        r = self.ex("mandats." + cap, compte=compte, **args)
        self.assertIn(r["statut"], ("echec", "refuse"), r)
        return r.get("erreur") or r.get("raison") or ""

    def test_un_mandat_se_cree_et_se_defait(self):
        res = self.ex("mandats.save", nom="Relance client", declencheurs=["chat"], dst_source="document",
                      objet="Votre facture", corps="Bonjour {{prenom}},", variables=[{"nom": "prenom", "type": "texte"}])
        self.assertEqual(res["statut"], "faite", res)
        mid = res["resultat"]["id"]
        self.assertIn(mid, [m["id"] for m in self.s("mandats")["mandats"]])
        self.n.catalogue.get("mandats.save").defaire(self.ctx, res["resultat"])
        self.assertNotIn(mid, [m["id"] for m in self.s("mandats")["mandats"]])

    def test_une_adresse_libre_impose_l_accord(self):
        self.assertIn("accord", self.echec("save", nom="x", declencheurs=["chat"], dst_source="libre", controle="auto"))

    def test_une_variable_non_declaree_est_refusee(self):
        self.assertIn("non déclarées", self.echec("save", nom="x", declencheurs=["chat"], dst_source="document",
                                                  corps="Bonjour {{prenom}}", variables=[]))

    def test_un_mandat_se_lit_a_voix_haute(self):
        res = self.ex("mandats.save", nom="Relance", declencheurs=["chat"], dst_source="liste", dst_valeur="a@x.fr",
                      objet="Facture", variables=[])
        self.assertEqual(res["statut"], "faite", res)
        plan = self.s("plan", mid=res["resultat"]["id"])
        self.assertEqual(plan["qui"], "une liste fermée (a@x.fr)")
        self.assertEqual(plan["controle"], "après mon accord")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
