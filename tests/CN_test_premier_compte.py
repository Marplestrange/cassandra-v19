# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'assistant du premier compte
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #6e2ebf
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'assistant du premier compte : jeton d'installation, une seule fois, superadministrateur.
# MÉTHODE    : une vraie passerelle sur un noyau neuf, des requêtes HTTP.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=6e2ebf ▼▼▼
"""Bancs de l'assistant du premier compte : GET/POST /api/premier."""
import http.client
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                                   # noqa: E402
from noyau.CN_passerelle import Passerelle                 # noqa: E402

MDP = "Abcdefgh1!"


class PremierCompte(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("comptes")["ok"])
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.n.identite.fastpanel = lambda: False
        self.g = Passerelle(self.n, "127.0.0.1", 0)
        self.g.demarrer()
        self.addCleanup(self.g.arreter)
        self.fichier = base / "d" / "premier-compte.jeton"

    def req(self, methode, corps=None):
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        c.request(methode, "/api/premier", body=json.dumps(corps).encode() if corps is not None else None, headers={"Content-Type": "application/json"})
        r = c.getresponse()
        txt = r.read().decode()
        c.close()
        return r.status, json.loads(txt)

    def test_une_installation_neuve_est_libre_et_pose_son_jeton(self):
        st, d = self.req("GET")
        self.assertEqual((st, d["libre"]), (200, True))
        self.assertEqual(len(self.fichier.read_text().strip()), 16)

    def test_sans_le_bon_jeton_aucun_compte(self):
        self.req("GET")
        st, d = self.req("POST", {"jeton": "faux", "compte": "moi@x.fr", "mot_de_passe": MDP})
        self.assertEqual(st, 403)
        self.assertFalse(self.n.identite.existe("moi@x.fr"))

    def test_le_bon_jeton_cree_le_superadmin_une_seule_fois(self):
        self.req("GET")
        jeton = self.fichier.read_text().strip()
        st, d = self.req("POST", {"jeton": jeton, "compte": "moi@x.fr", "mot_de_passe": MDP})
        self.assertEqual((st, d.get("ok")), (200, True))
        self.assertTrue(self.n.identite.lire("moi@x.fr")["superadmin"])
        self.assertFalse(self.fichier.exists())
        st, d = self.req("POST", {"jeton": jeton, "compte": "autre@x.fr", "mot_de_passe": MDP})
        self.assertEqual(st, 403)
        self.assertFalse(self.n.identite.existe("autre@x.fr"))
        self.assertFalse(self.req("GET")[1]["libre"])

    def test_un_mot_de_passe_faible_est_refuse_et_le_jeton_reste(self):
        self.req("GET")
        jeton = self.fichier.read_text().strip()
        st, d = self.req("POST", {"jeton": jeton, "compte": "moi@x.fr", "mot_de_passe": "a"})
        self.assertEqual(st, 400)
        self.assertTrue(self.fichier.exists())

    def test_cinq_jetons_faux_ferment_la_porte_un_moment(self):
        self.req("GET")
        for _ in range(5):
            self.req("POST", {"jeton": "faux", "compte": "moi@x.fr", "mot_de_passe": MDP})
        jeton = self.fichier.read_text().strip()
        st, _ = self.req("POST", {"jeton": jeton, "compte": "moi@x.fr", "mot_de_passe": MDP})
        self.assertEqual(st, 429)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
