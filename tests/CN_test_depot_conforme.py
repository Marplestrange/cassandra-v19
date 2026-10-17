# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le dépôt entier respecte le format universel (docs/CN_FORMAT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #220fc4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le dépôt entier respecte le format universel (docs/CN_FORMAT.md) : nom préfixé, en-tête, borne, explicatif, pureté des EC, empreintes scellées. Ce banc est la porte de l'intégration continue : un fichier ajouté sans en-tête, ou modifié sans
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=220fc4 ▼▼▼
"""Le dépôt entier respecte le format universel (docs/CN_FORMAT.md) : nom préfixé, en-tête, borne, explicatif, pureté des EC, empreintes scellées.
Ce banc est la porte de l'intégration continue : un fichier ajouté sans en-tête, ou modifié sans que son empreinte soit rescellée, fait échouer la suite."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "outils"))
import CN_bornes as B  # noqa: E402


class DepotConforme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = B.audit()

    def test_aucun_fichier_n_est_hors_format(self):
        fautifs = {r["chemin"]: r["erreurs"] for r in self.audit["fichiers"] if r["erreurs"]}
        self.assertEqual(fautifs, {}, "fichiers hors format : lancer `python outils/CN_entete.py --ecrire` puis `python outils/CN_bornes.py --sceller`")

    def test_aucune_empreinte_n_est_perimee(self):
        perimees = [r["chemin"] for r in self.audit["fichiers"] if any("empreinte à recalculer" in i for i in r["infos"])]
        self.assertEqual(perimees, [], "contenu modifié sans rescellement : `python outils/CN_bornes.py --sceller`")

    def test_toute_ec_est_pure_et_porte_son_hote(self):
        ec = [r for r in self.audit["fichiers"] if r.get("zone") == "EC"]
        self.assertTrue(ec, "le pilote vue au moins fournit une référence")
        for r in ec:
            self.assertEqual(r["erreurs"], [], r["chemin"])

    def test_le_depot_n_a_pas_de_fichier_sans_prefixe_hors_liste_fermee(self):
        sans = [c for c in B.fichiers_suivis() if (RACINE / c).is_file() and Path(c).name not in B.NOMS_IMPOSES and not Path(c).name.startswith(B.PREFIXES)
                and not any(p in B.IGNORER_DOSSIERS for p in Path(c).parts)]
        self.assertEqual(sans, [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : DepotConforme
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
