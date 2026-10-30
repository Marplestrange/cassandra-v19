# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs : un module du registre installé par-dessus le module livré
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #507b6e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs : les VRAIES archives du registre officiel (billetterie, dolibarr), vérifiées par les clés embarquées, s'installent par le cycle de l'application par-dessus les modules livrés, qui sont alors remplacés.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=507b6e ▼▼▼
"""Bancs : les VRAIES archives du registre officiel (billetterie, dolibarr), vérifiées par les clés embarquées, s'installent par le cycle de l'application par-dessus les modules livrés, qui sont alors remplacés.

Le banc cherche le dépôt du registre à côté de celui-ci (`../cassandra-registre`) ou dans `CASSANDRA_REGISTRE` ; sans lui, il est ignoré.
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur                                                       # noqa: E402
from noyau import CN_cycle as C, CN_manifeste as mf                            # noqa: E402

REGISTRE = Path(os.environ.get("CASSANDRA_REGISTRE") or (RACINE.parent / "cassandra-registre"))
ARCHIVES = {"billetterie": REGISTRE / "docs" / "modules" / "billetterie" / "billetterie-0.1.0.cmod",
            "dolibarr": REGISTRE / "docs" / "modules" / "dolibarr" / "dolibarr-0.3.1.cmod"}


@unittest.skipUnless(all(a.is_file() for a in ARCHIVES.values()), "le dépôt du registre (docs/modules) est introuvable")
class SurchargeParLeRegistre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        b = self.base = Path(self.tmp.name)
        for m in ARCHIVES:                                                    # les modules LIVRÉS avec le noyau (confiance « interne »)
            shutil.copytree(RACINE / "modules" / m, b / "modules" / m, ignore=shutil.ignore_patterns("__pycache__"))
        (b / "extensions").mkdir()
        self.cycle = C.Cycle(b / "extensions", b / "d", b / "cles", lambda: [(mf.charger(f), True) for f in sorted((b / "extensions").glob("*/CN_manifeste.toml"))])

    def installer(self, mid):
        octets = ARCHIVES[mid].read_bytes()
        e = self.cycle.examiner(octets)
        self.assertTrue(e["autorise"], e["raisons"])
        self.assertEqual(e["editeur"] if "editeur" in e else "cassandra-principale", "cassandra-principale")
        return self.cycle.installer(e["jeton"], e["empreinte_permissions"], par="banc")

    def test_les_archives_du_registre_s_examinent_signees_par_la_racine_embarquee(self):
        for mid, a in ARCHIVES.items():
            e = self.cycle.examiner(a.read_bytes())
            self.assertTrue(e["autorise"], (mid, e["raisons"]))
            self.assertTrue(e["signe"], mid)

    def test_installees_elles_remplacent_les_modules_livres_et_le_noyau_les_branche(self):
        for mid in ARCHIVES:
            self.installer(mid)
        n = moteur.Noyau(self.base / "d2", self.base / "modules", {}, extensions=self.base / "extensions")
        r = n.brancher()
        self.assertEqual(r["refuses"], [], r["refuses"])
        self.assertEqual(set(r["remplaces"]), set(ARCHIVES))                  # chacun a pris la place de la version livrée
        ligne = {x["id"]: x for x in n.catalogue_modules()}
        for mid in ARCHIVES:
            self.assertTrue(ligne[mid]["extension"], mid)
            self.assertEqual(ligne[mid]["confiance"] if "confiance" in ligne[mid] else "signe", "signe")
        self.assertIn("billetterie", r["ordre"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : SurchargeParLeRegistre
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
