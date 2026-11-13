# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module Bases de données
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #ed9f4d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module Bases de données : un vrai noyau avec les vrais modules FastPanel, Panel Detect et Bases ; la machine est fictive (les signatures trouvées sont posées par le banc) et les lectures du panneau sont simulées, sauf les routes de
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ed9f4d ▼▼▼
"""Bancs du module Bases de données : un vrai noyau avec les vrais modules FastPanel, Panel Detect et Bases ; la machine est fictive
(les signatures trouvées sont posées par le banc) et les lectures du panneau sont simulées, sauf les routes de Panel Detect.
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
BASES = [
    {"id": 7, "nom": "wp_prod", "moteur": "mysql", "taille_mo": 120.5, "proprietaire": "fastuser", "site": "boutique.exemple.fr", "jeu": "utf8mb4",
     "cree": "2026-03-01 10:00:00", "derniere_copie": "2026-11-09 04:00:00", "utilisateurs": "wp_user, wp_lecture"},
    {"id": 3, "nom": "Archive", "moteur": "mysql", "taille_mo": 2048, "proprietaire": "fastuser", "site": "", "jeu": "", "cree": "", "derniere_copie": "", "utilisateurs": "arch"},
]


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("fastpanel", "paneldetect", "bases"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("fastpanel", "paneldetect", "bases"):
            self.n.etat_modules.poser(m, installe=True, actif=False, par="test")
            self.assertTrue(self.n.activer(m)["ok"], m)
        pd = self.n.catalogue.get("paneldetect.etat").faire.__globals__
        self.machine = lambda panneaux: pd.__setitem__("presents", lambda *a, **k: [dict(p) for p in panneaux])
        self.machine([FP])
        # Le panneau est simulé : les routes de Panel Detect, elles, sont les vraies (paneldetect lit « fastpanel.routes » du vrai module).
        self.sim = {"fastpanel.bases": BASES, "fastpanel.utilisateurs": [{"compte": "fastuser"}, {"compte": "autre"}], "fastpanel.adresse": {"url": "https://argos.exemple.fr:8888"}}
        self.lu = []
        ctx = self.n.executeur.contextes["bases"]
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
        r = self.n.executeur.executer("bases.lister", "humain", {}, compte="")
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]


class Lecture(Monde):
    def test_la_liste_est_triee_normalisee_et_porte_de_quoi_creer(self):
        d = self.lister()
        self.assertEqual(d["etat"], "ok")
        self.assertEqual([b["nom"] for b in d["bases"]], ["Archive", "wp_prod"])                  # sans tenir compte de la casse
        wp = next(b for b in d["bases"] if b["nom"] == "wp_prod")
        self.assertEqual((wp["id"], wp["site"], wp["utilisateurs"], wp["copiee"]), (7, "boutique.exemple.fr", ["wp_user", "wp_lecture"], True))
        self.assertEqual(d["utilisateurs"], ["arch", "wp_lecture", "wp_user"])
        self.assertEqual(d["comptes"], ["autre", "fastuser"])
        self.assertEqual(d["adresse"], "https://argos.exemple.fr:8888")
        self.assertEqual((d["sans_copie"], d["total_mo"]), (1, 2168.5))                            # « Archive » n'a jamais été copiée
        self.assertEqual(d["gestes"], {"creer": True, "supprimer": True})

    def test_une_liste_vide_est_une_lecture_reussie(self):
        self.sim["fastpanel.bases"] = []
        d = self.lister()
        self.assertEqual((d["etat"], d["bases"]), ("ok", []))

    def test_un_panneau_muet_n_est_pas_aucune_base(self):
        self.sim["fastpanel.bases"] = None
        d = self.lister()
        self.assertEqual((d["etat"], d["bases"], d["comptes"]), ("muet", [], []))

    def test_un_refus_de_droit_se_lit_comme_un_module_absent(self):
        self.sim["fastpanel.bases"] = PermissionError("refusé")
        self.assertEqual(self.lister()["etat"], "absent")

    def test_sans_panneau_la_page_dit_absent(self):
        self.machine([])
        d = self.lister()
        self.assertEqual((d["etat"], d["bases"], d["gestes"]), ("absent", [], {"creer": False, "supprimer": False}))
        self.assertNotIn("fastpanel.bases", self.lu)                                                # sans route, rien n'est lu

    def test_un_panneau_sans_module_ou_deux_panneaux_ne_servent_rien(self):
        self.machine([HESTIA])
        self.assertEqual(self.lister()["etat"], "absent")
        self.machine([FP, HESTIA])
        self.assertEqual(self.lister()["etat"], "absent")                                           # rien n'est choisi à la place de l'administrateur

    def test_un_panneau_qui_revient_est_vu_tout_de_suite(self):
        self.machine([])
        self.assertEqual(self.lister()["etat"], "absent")
        self.machine([FP])
        self.assertEqual(self.lister()["etat"], "ok")                                               # le cache des routes suit la signature des panneaux


class Independance(Monde):
    def test_le_module_et_son_ecran_ne_nomment_aucun_panneau(self):
        for chemin in ("modules/bases/CN_module.py", "interface/CN_bases-ecran.js"):
            t = (RACINE / chemin).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"fastpanel", t, re.I), chemin)                             # tout passe par Panel Detect

    def test_les_fonctions_demandees_existent_chez_panel_detect(self):
        src = (RACINE / "modules" / "bases" / "CN_module.py").read_text(encoding="utf-8") + (RACINE / "interface" / "CN_bases-ecran.js").read_text(encoding="utf-8")
        fonctions = set(re.findall(r'(?:route\(c, |lire\(c, |viaRoute\()"([a-z_]+)"', src))
        connues = {x["fonction"] for x in self.n.executeur.executer("paneldetect.etat", "humain", {}, compte="")["resultat"]["routes"]}
        self.assertEqual(fonctions - connues, set(), "fonctions demandées mais inconnues de Panel Detect")
        self.assertTrue({"bases", "comptes", "adresse", "base_creer", "base_supprimer"} <= fonctions)

    def test_la_creation_et_la_suppression_sont_des_gestes_que_panel_detect_nomme(self):
        r = {x["fonction"]: x for x in self.n.executeur.executer("paneldetect.etat", "humain", {}, compte="")["resultat"]["routes"]}
        self.assertEqual((r["base_creer"]["capacite"], r["base_creer"]["nature"]), ("fastpanel.base_creer", "geste"))
        self.assertEqual((r["base_supprimer"]["capacite"], r["base_supprimer"]["nature"]), ("fastpanel.base_supprimer", "geste"))
        self.assertEqual((r["adresse"]["capacite"], r["adresse"]["nature"]), ("fastpanel.adresse", "lecture"))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Lecture, Independance
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
