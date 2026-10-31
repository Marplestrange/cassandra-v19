# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la connexion sentinelle de la base
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #b45926
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la connexion sentinelle de la base : une seule par fichier, seulement quand le serveur l'a demandé, jamais un verrou tenu, et libérable avant d'effacer un dossier.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b45926 ▼▼▼
"""Bancs de la connexion sentinelle de la base : une seule par fichier, seulement quand le serveur l'a demandé, jamais un verrou tenu, et libérable avant d'effacer un dossier."""
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_base as cb  # noqa: E402

SCHEMA = "CREATE TABLE IF NOT EXISTS ev(id INTEGER PRIMARY KEY, x TEXT);"


class Sentinelle(unittest.TestCase):
    def setUp(self):
        cb.garder_ouvert(False)
        self.dossier = tempfile.mkdtemp()
        self.chemin = str(Path(self.dossier) / "t.db")

    def tearDown(self):
        cb.garder_ouvert(False)
        shutil.rmtree(self.dossier)           # sous Windows, échoue si une sentinelle tient encore le fichier

    def test_par_defaut_rien_ne_reste_ouvert(self):
        b = cb.Base(self.chemin, schema=SCHEMA)
        b.ecrire("INSERT INTO ev(x) VALUES('a')")
        self.assertEqual(b.lire("SELECT count(*) AS n FROM ev")[0]["n"], 1)
        self.assertEqual(cb._sentinelles, {})

    def test_une_seule_sentinelle_par_fichier_meme_avec_des_fils(self):
        cb.garder_ouvert()
        b = cb.Base(self.chemin, schema=SCHEMA)

        def travail():
            for _ in range(10):
                b.ecrire("INSERT INTO ev(x) VALUES('a')")
                b.lire("SELECT count(*) FROM ev")
        fils = [threading.Thread(target=travail) for _ in range(8)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()
        self.assertEqual(len(cb._sentinelles), 1)
        self.assertEqual(b.lire("SELECT count(*) AS n FROM ev")[0]["n"], 80)     # aucune écriture perdue

    def test_la_sentinelle_ne_tient_aucun_verrou(self):
        cb.garder_ouvert()
        b = cb.Base(self.chemin, schema=SCHEMA)
        b.lire("SELECT 1")
        with b.transaction() as c:            # BEGIN IMMEDIATE réussit : la sentinelle n'est dans aucune transaction
            c.execute("INSERT INTO ev(x) VALUES('b')")
        self.assertEqual(b.lire("SELECT x FROM ev")[0]["x"], "b")

    def test_liberer_ferme_la_sentinelle(self):
        cb.garder_ouvert()
        b = cb.Base(self.chemin, schema=SCHEMA)
        b.lire("SELECT 1")
        self.assertEqual(len(cb._sentinelles), 1)
        cb.liberer(self.chemin)
        self.assertEqual(cb._sentinelles, {})

    def test_desactiver_ferme_tout(self):
        cb.garder_ouvert()
        cb.Base(self.chemin, schema=SCHEMA).lire("SELECT 1")
        cb.garder_ouvert(False)
        self.assertEqual(cb._sentinelles, {})

    def test_la_base_en_memoire_n_a_pas_de_sentinelle(self):
        cb.garder_ouvert()
        b = cb.Base(":memory:", schema=SCHEMA)
        self.assertEqual(cb._sentinelles, {})
        del b


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Sentinelle
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
