# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de Sécurité › Accès
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #6e93f8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de Sécurité › Accès : les comptes du panneau et les comptes FTP, lus par la route de Panel Detect ; un vrai noyau, un panneau simulé. Le module ne nomme aucun panneau ; « absent », « muet » et la liste ne se confondent pas ; une clé S
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=6e93f8 ▼▼▼
"""Bancs de Sécurité › Accès : les comptes du panneau et les comptes FTP, lus par la route de Panel Detect ; un vrai noyau, un panneau simulé.
Le module ne nomme aucun panneau ; « absent », « muet » et la liste ne se confondent pas ; une clé SSH n'est jamais renvoyée, seulement son nom."""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402

FP = {"id": "fastpanel", "nom": "FastPanel", "preuves": ["dossier /usr/local/fastpanel2"]}
HESTIA = {"id": "hestia", "nom": "HestiaCP", "preuves": ["dossier /usr/local/hestia"]}
COMPTES = [{"compte": "fastuser", "dossier": "/var/www/fastuser/data", "statut": "active", "roles": "admin", "ssh": True, "quota_go": None,
            "courriel": "", "cree": "2026-03-01 10:00:00", "sites": 2, "bases": 0},
           {"compte": "client1", "dossier": "", "statut": "active", "roles": "user", "ssh": False, "quota_go": 5.0, "courriel": "", "cree": "", "sites": 1, "bases": 1}]
FTP = [{"compte": "client1_ftp", "dossier": "/var/www/client1/data", "statut": "active", "proprietaire": "client1", "site": "boutique.exemple.fr", "cree": ""},
       {"compte": "vieux_ftp", "dossier": "/var/www/x", "statut": "suspendu", "proprietaire": "client1", "site": "", "cree": ""}]


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("fastpanel", "paneldetect", "securite"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("fastpanel", "paneldetect", "securite"):
            self.n.etat_modules.poser(m, installe=True, actif=False, par="test")
            self.assertTrue(self.n.activer(m)["ok"], m)
        pd = self.n.catalogue.get("paneldetect.etat").faire.__globals__
        self.machine = lambda panneaux: pd.__setitem__("presents", lambda *a, **k: [dict(p) for p in panneaux])
        self.machine([FP])
        self.sim = {"fastpanel.utilisateurs": COMPTES, "fastpanel.ftp": FTP,
                    "fastpanel.utilisateur_cles": {"compte": "fastuser", "cles": [{"name": "portable", "type": "ssh-ed25519", "key": "ssh-ed25519 AAAASECRET"}]}}
        self.lu = []
        ctx = self.n.executeur.contextes["securite"]
        vrai = ctx.executer_lecture

        def lecture(cap, **a):
            self.lu.append(cap)
            if cap in self.sim:
                v = self.sim[cap]
                if isinstance(v, Exception):
                    raise v
                return v
            return vrai(cap, **a)
        ctx.executer_lecture = lecture

    def lire(self, cap="securite.acces_panneau", **args):
        r = self.n.executeur.executer(cap, "humain", args, compte="")
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]


class Acces(Monde):
    def test_les_comptes_et_le_ftp_sont_lus_par_la_route(self):
        d = self.lire()
        self.assertEqual((d["comptes"]["etat"], [c["compte"] for c in d["comptes"]["liste"]]), ("ok", ["fastuser", "client1"]))
        self.assertEqual((d["ftp"]["etat"], len(d["ftp"]["liste"])), ("ok", 2))
        self.assertEqual((d["ssh_ouverts"], d["ftp_suspendus"]), (1, 1))

    def test_un_panneau_muet_n_est_pas_aucun_compte(self):
        self.sim["fastpanel.utilisateurs"] = None
        self.sim["fastpanel.ftp"] = []
        d = self.lire()
        self.assertEqual((d["comptes"]["etat"], d["comptes"]["liste"]), ("muet", []))
        self.assertEqual((d["ftp"]["etat"], d["ftp"]["liste"]), ("ok", []))                        # une liste vide est une lecture réussie

    def test_sans_panneau_ou_avec_deux_les_blocs_disent_absent(self):
        for panneaux in ([], [HESTIA], [FP, HESTIA]):
            self.machine(panneaux)
            d = self.lire()
            self.assertEqual((d["comptes"]["etat"], d["ftp"]["etat"]), ("absent", "absent"), panneaux)
        self.assertNotIn("fastpanel.utilisateurs", self.lu)

    def test_un_refus_de_droit_se_lit_comme_absent(self):
        self.sim["fastpanel.ftp"] = PermissionError("refusé")
        d = self.lire()
        self.assertEqual((d["comptes"]["etat"], d["ftp"]["etat"]), ("ok", "absent"))

    def test_les_cles_se_nomment_sans_se_montrer(self):
        d = self.lire("securite.acces_cles", compte="fastuser")
        self.assertEqual((d["etat"], d["cles"]), ("ok", [{"nom": "portable", "type": "ssh-ed25519"}]))
        self.assertNotIn("AAAASECRET", repr(d))

    def test_les_fonctions_demandees_existent_chez_panel_detect(self):
        src = (RACINE / "modules" / "securite" / "CN_module.py").read_text(encoding="utf-8")
        demandees = set(re.findall(r'lire_etat\(ctx, "([a-z_]+)"', src)) | set(re.findall(r'"([a-z_]+)"', re.search(r'for fonction in \(([^)]*)\)', src).group(1)))
        connues = {x["fonction"] for x in self.n.executeur.executer("paneldetect.etat", "humain", {}, compte="")["resultat"]["routes"]}
        self.assertEqual(demandees - connues, set())
        self.assertTrue({"comptes", "ftp", "comptes_cles"} <= demandees)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Acces
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
