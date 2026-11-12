# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module Panel Detect
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #81809c
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module Panel Detect : la machine est fictive (les signatures trouvées sont posées par le banc), le reste — manifestes, routes, relais des lectures, constats — tourne dans un vrai noyau avec le vrai module FastPanel.
# MÉTHODE    : un vrai noyau avec les vrais modules FastPanel et Panel Detect ; la machine est fictive (les signatures trouvées sont posées par le banc), les lectures du panneau simulées sauf « fastpanel.routes ».
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=81809c ▼▼▼
"""Bancs du module Panel Detect : la machine est fictive (les signatures trouvées sont posées par le banc), le reste — manifestes, routes, relais des lectures, constats — tourne dans un vrai noyau avec le vrai module FastPanel."""
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


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("fastpanel", "paneldetect"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("fastpanel", "paneldetect"):
            self.n.etat_modules.poser(m, installe=True, actif=False, par="test")
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["paneldetect"]
        self.g = self.n.catalogue.get("paneldetect.etat").faire.__globals__
        self.machine([FP])
        self.lu = []
        vrai = self.ctx.executer_lecture

        def lecture(cap, **a):                       # le vrai « fastpanel.routes » ; les autres lectures du panneau sont simulées (pas de panneau dans le banc)
            self.lu.append((cap, a))
            return vrai(cap, **a) if cap == "fastpanel.routes" else {"lu": cap, "args": a}
        self.ctx.executer_lecture = lecture

    def machine(self, panneaux):
        self.g["presents"] = lambda *a, **k: [dict(p) for p in panneaux]

    def ex(self, cap, **args):
        r = self.n.executeur.executer("paneldetect." + cap, "humain", args, compte="")
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def constats(self, nom):
        f = next(x[2] for x in self.n.detecteurs if x[0] == "paneldetect" and x[1].id == nom)
        return f(self.ctx)


class Detection(Monde):
    def test_fastpanel_seul_est_pilote_par_son_module(self):
        e = self.ex("etat")
        self.assertEqual((e["situation"], e["pilote"], e["nom"]), ("pilote", "fastpanel", "FastPanel"))
        self.assertEqual(e["panneaux"][0]["module"]["id"], "fastpanel")

    def test_aucun_panneau(self):
        self.machine([])
        e = self.ex("etat")
        self.assertEqual((e["situation"], e["pilote"], e["nom"]), ("aucun", "", ""))
        self.assertTrue(all(not r["capacite"] for r in e["routes"]))          # sans panneau, aucune route : chaque module fait avec ce qu'il sait seul

    def test_deux_panneaux_ne_choisit_rien(self):
        self.machine([FP, HESTIA])
        e = self.ex("etat")
        self.assertEqual((e["situation"], e["pilote"]), ("deux", ""))
        self.assertTrue(all(not r["capacite"] for r in e["routes"]))
        c = self.constats("deux_panneaux")
        self.assertEqual(len(c), 1)
        self.assertIn("FastPanel et HestiaCP", c[0]["titre"])

    def test_panneau_sans_module(self):
        self.machine([HESTIA])
        e = self.ex("etat")
        self.assertEqual((e["situation"], e["nom"]), ("sans_module", "HestiaCP"))
        self.assertIsNone(e["panneaux"][0]["module"])
        self.assertEqual(len(self.constats("panneau_sans_module")), 1)
        self.machine([FP])
        self.assertEqual(self.constats("panneau_sans_module"), [])
        self.assertEqual(self.constats("deux_panneaux"), [])

    def test_les_signatures_lisent_une_vraie_arborescence(self):
        racine = Path(self.tmp.name) / "machine"
        (racine / "usr" / "local" / "fastpanel2").mkdir(parents=True)
        import importlib.util
        spec = importlib.util.spec_from_file_location("paneldetect_banc", RACINE / "modules" / "paneldetect" / "CN_module.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        presents = mod.presents
        trouves = presents(str(racine), qui=lambda c: None)
        self.assertEqual([p["id"] for p in trouves], ["fastpanel"])
        self.assertEqual(trouves[0]["preuves"], ["dossier /usr/local/fastpanel2"])
        self.assertEqual(presents(str(racine), qui=lambda c: "/usr/bin/virtualmin" if c == "virtualmin" else None)[1]["id"], "virtualmin")


class Routes(Monde):
    def test_les_routes_de_fastpanel_sont_verifiees_contre_son_manifeste(self):
        e = self.ex("etat")
        r = {x["fonction"]: x for x in e["routes"]}
        self.assertEqual((r["sites"]["capacite"], r["sites"]["nature"]), ("fastpanel.sites", "lecture"))
        self.assertEqual((r["courrier"]["capacite"], r["courrier"]["nature"]), ("fastpanel.mail", "lecture"))
        self.assertEqual((r["base_creer"]["capacite"], r["base_creer"]["nature"]), ("fastpanel.base_creer", "geste"))
        self.assertEqual(r["ssl_renouveler"]["nature"], "geste")
        manifeste = (RACINE / "modules" / "fastpanel" / "CN_manifeste.toml").read_text(encoding="utf-8")
        for x in e["routes"]:
            if x["capacite"]:
                self.assertRegex(manifeste, r'\[\[capacites\]\]\s*\nid = "%s"' % x["capacite"].split(".")[1], x["fonction"])

    def test_une_route_qui_n_existe_pas_dans_le_manifeste_est_ecartee(self):
        g = self.n.catalogue.get("fastpanel.routes").faire.__globals__
        self.ctx.executer_lecture = lambda cap, **a: {"routes": {"sites": "fastpanel.inventee", "bases": "autre.bases", "inconnue": "fastpanel.sites", "php": "fastpanel.php"}} if cap == "fastpanel.routes" else None
        e = self.ex("etat")
        r = {x["fonction"]: x["capacite"] for x in e["routes"]}
        self.assertEqual((r["sites"], r["bases"], r["php"]), ("", "", "fastpanel.php"))
        self.assertNotIn("inconnue", r)
        self.assertTrue(g)

    def test_lire_relaie_une_lecture_telle_quelle(self):
        self.assertEqual(self.ex("lire", fonction="sites"), {"lu": "fastpanel.sites", "args": {}})
        self.assertEqual(self.ex("lire", fonction="comptes_cles", compte="fastuser"), {"lu": "fastpanel.utilisateur_cles", "args": {"compte": "fastuser"}})

    def test_lire_refuse_un_geste_et_une_fonction_inconnue(self):
        for f in ("base_creer", "crons"):
            r = self.n.executeur.executer("paneldetect.lire", "humain", {"fonction": f}, compte="")
            self.assertNotEqual(r["statut"], "faite", f)

    def test_lire_sans_panneau_rend_rien(self):
        self.machine([])
        self.assertIsNone(self.ex("lire", fonction="sites"))

    def test_route_donne_la_capacite_a_appeler_soi_meme(self):
        self.assertEqual(self.ex("route", fonction="sites"), {"capacite": "fastpanel.sites", "nature": "lecture"})
        self.assertEqual(self.ex("route", fonction="base_creer"), {"capacite": "fastpanel.base_creer", "nature": "geste"})      # un geste se nomme : il ne se relaie jamais
        for f in ("copies_du_plan", "parefeu_regle_poser", "parefeu_regle_retirer", "parefeu_politique", "parefeu_trancher"):
            self.assertTrue(self.ex("route", fonction=f)["capacite"], f)

    def test_route_sans_droit_et_sans_panneau_rend_vide(self):
        r = self.n.executeur.executer("paneldetect.route", "humain", {"fonction": "sites"}, compte="")
        self.assertEqual(r["statut"], "faite")
        self.machine([])
        self.assertEqual(self.ex("route", fonction="sites"), {"capacite": "", "nature": ""})        # rien n'est servi : l'appelant fait comme si le module était absent

    def test_route_refuse_une_fonction_inconnue(self):
        r = self.n.executeur.executer("paneldetect.route", "humain", {"fonction": "crons"}, compte="")
        self.assertNotEqual(r["statut"], "faite")


class Ecran(unittest.TestCase):
    """L'écran de Panel Detect : servi, assemblé, et il n'appelle que des capacités déclarées."""
    @staticmethod
    def lire(*chemin):
        return RACINE.joinpath(*chemin).read_text(encoding="utf-8")

    def test_l_ecran_est_servi_et_l_assembleur_le_sait(self):
        self.assertIn('<script src="/paneldetect-ecran.js"></script>', self.lire("interface", "CN_index.html"))
        self.assertIn('<script src="/paneldetect-ecran.js"></script>', self.lire("outils", "ui", "CN_assembler.py"))

    def test_l_ecran_ne_lit_que_des_capacites_declarees(self):
        appelees = set(re.findall(r'agir\("([a-z_]+\.[a-z_]+)"', self.lire("interface", "CN_paneldetect-ecran.js")))
        self.assertIn("paneldetect.etat", appelees)
        for cap in sorted(appelees):
            module, nom = cap.split(".")
            self.assertRegex(self.lire("modules", module, "CN_manifeste.toml"), r'\[\[capacites\]\]\s*\nid = "%s"' % nom, cap)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Detection, Routes, Ecran
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/paneldetect ; modules/fastpanel (routes) ; interface/CN_paneldetect-ecran.js
