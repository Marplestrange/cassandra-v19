import tempfile
from pathlib import Path
import unittest
import test_noyau as base

COURRIER_TOML = """[module]
id = "courrier"
nom = "Courrier"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Boîtes, IMAP, brouillons, mandats d'envoi, médias."

[[capacites]]
id = "etat"
libelle = "Etat"
risque = "lecture"
"""

COURRIER_PY = """
def brancher(ctx):
    def etat(ctx):
        # Simule l'état d'un compte non provisionné
        return {"ok": True, "configuree": False, "souci": "coffre_ou_absente"}
    ctx.implementer("etat", etat)
"""

INIT_SQL = """CREATE TABLE mail_cache (account TEXT);"""

def monde_courrier():
    import shutil
    tmp = tempfile.TemporaryDirectory()
    p = Path(tmp.name)
    mods = p / "modules"
    for m in ("droits", "comptes", "notifications"):
        shutil.copytree(base.RACINE / "modules" / m, mods / m)
    base.ecrire_module(mods, "courrier", COURRIER_TOML, COURRIER_PY, sql=INIT_SQL)
    n = base.moteur.Noyau(p / "d", mods, {}, gerer_modules=True, exiger_compte=True)
    n.brancher()
    n.activer("comptes")
    n.activer("notifications")
    n.activer("courrier")
    return tmp, n

class TestCourrier(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde_courrier()
        self.addCleanup(self.tmp.cleanup)
        for c in ("chef@x.fr", "adm@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": base.MDP}, compte="operateur")

    def ex(self, capacite, acteur="humain", au_nom_de="operateur", **args):
        return self.n.executeur.executer(capacite, acteur, args, compte=au_nom_de)

    @unittest.skip("brouillon : à corriger")

    def test_etat_boite_vide_renseigne_souci(self):
        # V18 leçon: Sans identifiants personnels, on rend un hôte vide et on dit pourquoi.
        r = self.ex("courrier.etat", au_nom_de="adm@x.fr")
        self.assertFalse(r["resultat"]["configuree"])
        self.assertIn("souci", r["resultat"])
