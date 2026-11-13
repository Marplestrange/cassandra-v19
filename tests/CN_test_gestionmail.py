# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module Gestion e-mail
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #03f68f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module Gestion e-mail : un vrai noyau avec les vrais modules FastPanel, Panel Detect et Gestion e-mail ; la machine est fictive (les signatures trouvées sont posées par le banc) et la lecture du panneau est simulée, sauf les routes
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=03f68f ▼▼▼
"""Bancs du module Gestion e-mail : un vrai noyau avec les vrais modules FastPanel, Panel Detect et Gestion e-mail ; la machine est fictive
(les signatures trouvées sont posées par le banc) et la lecture du panneau est simulée, sauf les routes de Panel Detect.
Le module ne nomme aucun panneau : il demande sa route à Panel Detect, et dit « absent », « muet » ou la liste, sans les confondre."""
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
BOITES = [
    {"adresse": "contact@boutique.exemple.test", "domaine": "boutique.exemple.test", "quota_mo": 2048, "utilise_mo": 1884, "statut": "active"},
    {"adresse": "Bonjour@atelier.exemple.test", "domaine": "", "quota_mo": 1024, "utilise_mo": 230, "statut": "active"},
    {"adresse": "ancien@boutique.exemple.test", "domaine": "boutique.exemple.test", "quota_mo": 0, "utilise_mo": 12, "statut": "suspendue"},
]


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("fastpanel", "paneldetect", "gestionmail"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("fastpanel", "paneldetect", "gestionmail"):
            self.n.etat_modules.poser(m, installe=True, actif=False, par="test")
            self.assertTrue(self.n.activer(m)["ok"], m)
        pd = self.n.catalogue.get("paneldetect.etat").faire.__globals__
        self.machine = lambda panneaux: pd.__setitem__("presents", lambda *a, **k: [dict(p) for p in panneaux])
        self.machine([FP])
        self.sim = {"fastpanel.mail": BOITES}
        self.lu = []
        ctx = self.n.executeur.contextes["gestionmail"]
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

    def lister(self):
        r = self.n.executeur.executer("gestionmail.lister", "humain", {}, compte="")
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]


class Lecture(Monde):
    def test_la_liste_est_triee_normalisee_et_dit_la_place_prise(self):
        d = self.lister()
        self.assertEqual(d["etat"], "ok")
        self.assertEqual([b["adresse"] for b in d["boites"]], ["ancien@boutique.exemple.test", "Bonjour@atelier.exemple.test", "contact@boutique.exemple.test"])
        par = {b["adresse"]: b for b in d["boites"]}
        contact = par["contact@boutique.exemple.test"]
        self.assertEqual((contact["pct"], contact["presque_pleine"]), (92.0, True))
        self.assertEqual(par["Bonjour@atelier.exemple.test"]["domaine"], "atelier.exemple.test")      # le domaine se lit dans l'adresse quand le panneau ne le donne pas
        self.assertEqual((d["pleines"], d["suspendues"], d["total_mo"]), (1, 1, 2126.0))

    def test_sans_quota_connu_aucun_pourcentage_n_est_invente(self):
        ancien = next(b for b in self.lister()["boites"] if b["adresse"].startswith("ancien"))
        self.assertEqual((ancien["pct"], ancien["quota_mo"], ancien["presque_pleine"], ancien["suspendue"]), (None, None, False, True))

    def test_les_domaines_sont_comptes(self):
        d = {x["domaine"]: x for x in self.lister()["domaines"]}
        self.assertEqual((d["boutique.exemple.test"]["boites"], d["boutique.exemple.test"]["utilise_mo"], d["atelier.exemple.test"]["boites"]), (2, 1896.0, 1))

    def test_une_liste_vide_est_une_lecture_reussie(self):
        self.sim["fastpanel.mail"] = []
        d = self.lister()
        self.assertEqual((d["etat"], d["boites"]), ("ok", []))

    def test_un_panneau_muet_n_est_pas_aucune_boite(self):
        self.sim["fastpanel.mail"] = None
        d = self.lister()
        self.assertEqual((d["etat"], d["boites"]), ("muet", []))

    def test_un_refus_de_droit_se_lit_comme_un_module_absent(self):
        self.sim["fastpanel.mail"] = PermissionError("refusé")
        self.assertEqual(self.lister()["etat"], "absent")

    def test_sans_panneau_la_page_dit_absent(self):
        self.machine([])
        d = self.lister()
        self.assertEqual((d["etat"], d["boites"]), ("absent", []))
        self.assertNotIn("fastpanel.mail", self.lu)                                                  # sans route, rien n'est lu

    def test_un_panneau_sans_module_ou_deux_panneaux_ne_servent_rien(self):
        self.machine([HESTIA])
        self.assertEqual(self.lister()["etat"], "absent")
        self.machine([FP, HESTIA])
        self.assertEqual(self.lister()["etat"], "absent")                                            # rien n'est choisi à la place de l'administrateur

    def test_un_panneau_qui_revient_est_vu_tout_de_suite(self):
        self.machine([])
        self.assertEqual(self.lister()["etat"], "absent")
        self.machine([FP])
        self.assertEqual(self.lister()["etat"], "ok")


class Independance(Monde):
    def test_le_module_et_son_ecran_ne_nomment_aucun_panneau(self):
        for chemin in ("modules/gestionmail/CN_module.py", "interface/CN_gestionmail-ecran.js"):
            t = (RACINE / chemin).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"fastpanel", t, re.I), chemin)

    def test_la_fonction_demandee_existe_chez_panel_detect(self):
        src = (RACINE / "modules" / "gestionmail" / "CN_module.py").read_text(encoding="utf-8")
        fonctions = set(re.findall(r'fonction="([a-z_]+)"', src))
        connues = {x["fonction"]: x for x in self.n.executeur.executer("paneldetect.etat", "humain", {}, compte="")["resultat"]["routes"]}
        self.assertEqual(fonctions, {"courrier"})
        self.assertEqual((connues["courrier"]["capacite"], connues["courrier"]["nature"]), ("fastpanel.mail", "lecture"))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Lecture, Independance
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
