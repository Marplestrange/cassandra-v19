# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le principe de l'Évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #b1f927
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le principe de l'Évolution : il ne reste dans les fichiers CN que du code NON ÉLIGIBLE à l'évolution.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b1f927 ▼▼▼
"""Le principe de l'Évolution : il ne reste dans les fichiers CN que du code NON ÉLIGIBLE à l'évolution.

Une fonction éligible (pure, sans état partagé, de plus de huit lignes, dans un module qui n'est pas décisionnel) est soit déjà un point d'évolution, soit
consignée avec sa RAISON dans outils/CN_auto_extraire.exceptions.json (« entrées introuvables », « entrée non sérialisable »…). Ce banc échoue quand du code
éligible arrive au nexus sans l'une ni l'autre : on l'extrait (python outils/CN_auto_extraire.py extraire), ou on dit pourquoi on le garde.
L'analyse est statique : elle ne synthétise aucune entrée et ne touche aucun fichier."""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils"))
import CN_auto_extraire as A  # noqa: E402


class Eligibilite(unittest.TestCase):
    def test_aucune_fonction_eligible_ne_reste_au_nexus_sans_raison_ecrite(self):
        exceptions = A.charger_exceptions()
        sans_raison = []
        for module in A.modules():
            if module in A.DECISIONNELS:
                continue
            br = A.branchement(module)
            if br is None:
                continue
            for f in A.fichiers(module):
                cands, _ = A.examiner(module, f)
                for c in cands:
                    if Path(c["fichier"]).name not in br:
                        continue
                    if "%s:%s:%s" % (module, Path(c["fichier"]).name, c["fn"]) not in exceptions:
                        sans_raison.append("%s : %s (%s)" % (module, c["fn"], Path(c["fichier"]).name))
        self.assertEqual(sans_raison, [], "du code éligible à l'évolution reste au nexus sans raison écrite : python outils/CN_auto_extraire.py extraire --exceptions")

    def test_une_exception_designe_une_fonction_qui_existe_encore(self):
        """Une raison écrite pour une fonction extraite depuis (ou disparue) est une ligne morte : elle fait croire qu'il y a une dette."""
        import ast
        mortes = []
        for cle in A.charger_exceptions():
            module, fichier, fn = cle.split(":")
            chemin = RACINE / "modules" / module / fichier
            if not chemin.exists():
                mortes.append(cle)
                continue
            arbre = ast.parse(A.lire(chemin))
            n = next((x for x in arbre.body if isinstance(x, ast.FunctionDef) and x.name == fn), None)
            if n is None or "_appeler_point(" in (ast.get_source_segment(A.lire(chemin), n) or ""):
                mortes.append(cle)
        self.assertEqual(mortes, [])

    def test_les_modules_decisionnels_sont_nommes(self):
        self.assertTrue({"droits", "urgence", "webauthn", "coffre"} <= set(A.DECISIONNELS))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Eligibilite
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
