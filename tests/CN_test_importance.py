# ═══════════════════════════════════════════════════════════════════════════
# TITRE      : L'importance déclarée par chaque module
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #740ea8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'importance déclarée par chaque module : vital, important ou optionnel, et ce qui s'arrête sans lui.
# MÉTHODE    : lit les manifestes des modules livrés et éprouve le validateur sur des manifestes d'essai
# ═══════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=740ea8 ▼▼▼
"""Chaque module déclare ce que la maison perd sans lui (`importance`) et en une phrase ce qui s'arrête (`sans`). Un module essentiel est vital.
La page des modules s'en sert pour dire, avant tout changement, ce qu'il va casser : une déclaration manquante la laisserait muette."""
import copy
import sys
import tomllib
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_manifeste as M  # noqa: E402


def manifestes():
    for f in sorted((RACINE / "modules").glob("*/CN_manifeste.toml")):
        yield f, tomllib.loads(f.read_text(encoding="utf-8"))


class ImportanceDeclaree(unittest.TestCase):
    def test_chaque_module_livre_declare_son_importance_et_sa_phrase(self):
        manque = []
        for f, d in manifestes():
            m = d["module"]
            if m.get("importance") not in M.IMPORTANCES or not str(m.get("sans", "")).strip():
                manque.append(m["id"])
        self.assertEqual(manque, [], "modules sans importance ou sans phrase « sans » : %s" % manque)

    def test_un_module_essentiel_est_vital(self):
        for f, d in manifestes():
            m = d["module"]
            if m.get("essentiel"):
                self.assertEqual(m.get("importance"), "vital", m["id"])

    def test_au_moins_un_module_de_chaque_niveau(self):
        niveaux = {d["module"].get("importance") for f, d in manifestes()}
        self.assertEqual(niveaux, set(M.IMPORTANCES))

    def test_le_validateur_refuse_un_niveau_inconnu_une_phrase_trop_longue_et_un_essentiel_non_vital(self):
        f, d = next(iter(manifestes()))
        ok = M.valider(copy.deepcopy(d))
        self.assertEqual([e for e in ok if "importance" in e or "sans" in e], [])
        for ch, val in (("importance", "capital"), ("sans", "x" * 301)):
            mauvais = copy.deepcopy(d); mauvais["module"][ch] = val
            self.assertTrue(any(ch in e for e in M.valider(mauvais)), ch)
        mauvais = copy.deepcopy(d); mauvais["module"]["essentiel"] = True; mauvais["module"]["importance"] = "optionnel"
        self.assertTrue(any("essentiel" in e and "vital" in e for e in M.valider(mauvais)))

    def test_le_manifeste_charge_porte_les_deux_champs(self):
        for f, d in manifestes():
            if d["module"]["id"] == "agents":
                m = M.charger(f)
                self.assertEqual((m.importance, bool(m.sans)), ("vital", True))
                return
        self.fail("module agents introuvable")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le banc de la déclaration d'importance.
# EC : néant.
# LIEN : noyau/CN_manifeste.py (le schéma), modules/*/CN_manifeste.toml (les déclarations).
