# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le démarrage de TOUS les modules ensemble, comme au lancement du serveur
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #23603d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le démarrage de TOUS les modules ensemble, comme au lancement du serveur.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=23603d ▼▼▼
"""Le démarrage de TOUS les modules ensemble, comme au lancement du serveur.

Un manifeste peut être valide seul et refusé avec les autres (un type d'objet que deux modules revendiquent, un événement sans propriétaire…) : seuls les bancs qui chargent le catalogue
complet le voient. Celui-ci charge chaque module livré, sans en écarter aucun, et exige zéro refus.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                                           # noqa: E402


class DemarrageComplet(unittest.TestCase):
    def test_tous_les_modules_livres_se_chargent_ensemble_sans_un_refus(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        n = moteur.Noyau(tmp)
        self.addCleanup(n.arreter)
        n.brancher(annoncer=False)
        livres = sorted(d.name for d in (RACINE / "modules").iterdir() if (d / "CN_manifeste.toml").exists())
        refus = n.rapport.get("refus") if isinstance(n.rapport, dict) else getattr(n.rapport, "refus", None)
        self.assertFalse(refus, refus)
        charges = set(n.rapport["ordre"]) if isinstance(n.rapport, dict) and "ordre" in n.rapport else set()
        self.assertEqual(sorted(set(livres) - charges), [], "modules livrés mais non chargés")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : DemarrageComplet
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
