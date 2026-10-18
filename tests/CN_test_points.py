# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des points d'évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #363513
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des points d'évolution : le contrat, le résolveur de compatibilité, le disjoncteur, la pureté, l'ouverture à d'autres formats.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=363513 ▼▼▼
"""Bancs des points d'évolution : le contrat, le résolveur de compatibilité, le disjoncteur, la pureté, l'ouverture à d'autres formats."""
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_points as P  # noqa: E402
from noyau.CN_manifeste import PointEvolution  # noqa: E402

REFERENCE = "def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'reference'}\n"
CONTRAT = {"entree": {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}},
           "sortie": {"type": "object", "required": ["y"], "properties": {"y": {"type": "integer"}}}}


def ec(corps, contrat="1.0", runtime="python", version="EC21", zone="EC"):
    return ("# ZONE       : %s\n# RUNTIME    : %s\n# VERSION EC : %s  #a1b2c3\n# CONTRAT PROUVÉ : @%s\n%s" % (zone, runtime, version, contrat, corps))


class Banc(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.mod = self.tmp / "modules" / "essai"
        (self.mod / "points").mkdir(parents=True)
        (self.mod / "contrats").mkdir()
        (self.mod / "points" / "EC_doubler.py").write_text(REFERENCE, encoding="utf-8")
        (self.mod / "contrats" / "CN_doubler.json").write_text(json.dumps(CONTRAT), encoding="utf-8")
        self.stock = self.tmp / "ec"
        self.alertes = []
        self.t = [1000.0]
        self.svc = P.ServicePoints(self.stock, alerte=lambda g, t: self.alertes.append((g, t)), horloge=lambda: self.t[0])
        self.m = types.SimpleNamespace(id="essai", points_evolution=(PointEvolution("doubler", "Double", "1.3", "points/EC_doubler", "doubler"),))
        self.defauts = self.svc.declarer(self.m, self.mod)

    def poser_ec(self, texte, nom="EC_doubler__EC21.py"):
        d = self.stock / "essai" / "doubler"
        d.mkdir(parents=True, exist_ok=True)
        (d / nom).write_text(texte, encoding="utf-8")
        (d / "ACTIVE").write_text(nom, encoding="utf-8")

    def appeler(self, x=2):
        return self.svc.appeler("essai", "doubler", {"x": x})


class Reference(Banc):
    def test_sans_ec_la_reference_sert(self):
        self.assertEqual(self.defauts, [])
        self.assertEqual(self.appeler(3), {"y": 6, "par": "reference"})
        self.assertEqual(self.svc.etat("essai", "doubler")["sert"], "reference")

    def test_une_entree_hors_contrat_est_refusee_sans_toucher_a_l_ec(self):
        with self.assertRaises(P.ContratViole):
            self.svc.appeler("essai", "doubler", {"x": "trois"})
        with self.assertRaises(P.ContratViole):
            self.svc.appeler("essai", "doubler", {})

    def test_une_entree_qui_n_est_pas_du_json_est_refusee(self):
        with self.assertRaises(P.ContratViole):
            self.svc.appeler("essai", "doubler", {"x": object()})

    def test_les_donnees_sont_copiees_a_chaque_frontiere(self):
        e = {"x": 5}
        s = self.svc.appeler("essai", "doubler", e)
        s["y"] = 999
        self.assertEqual(e, {"x": 5})
        self.assertEqual(self.appeler(5)["y"], 10)

    def test_un_point_inconnu_ou_sans_reference_ne_se_tait_pas(self):
        with self.assertRaises(P.PointInconnu):
            self.svc.appeler("essai", "absent", {})
        (self.mod / "points" / "EC_doubler.py").unlink()
        autre = P.ServicePoints(self.stock)
        self.assertTrue(autre.declarer(self.m, self.mod))
        with self.assertRaises(P.PointDefaillant):
            autre.appeler("essai", "doubler", {"x": 1})

    def test_une_reference_qui_viole_son_contrat_est_un_defaut_du_depot(self):
        (self.mod / "points" / "EC_doubler.py").write_text("def doubler(entree):\n    return {'z': 1}\n", encoding="utf-8")
        autre = P.ServicePoints(self.stock)
        autre.declarer(self.m, self.mod)
        with self.assertRaises(P.PointDefaillant):
            autre.appeler("essai", "doubler", {"x": 1})


class EcServie(Banc):
    def test_une_ec_saine_est_servie(self):
        self.poser_ec(ec("def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'EC'}\n"))
        self.assertEqual(self.appeler(4), {"y": 8, "par": "EC"})
        self.assertEqual(self.svc.etat("essai", "doubler")["sert"], "EC21")

    def test_contrat_compatible_additif_et_incompatible(self):
        self.assertTrue(P.compatible("1.3", "1.3"))
        self.assertTrue(P.compatible("1.2", "1.3"))          # prouvée sur un contrat plus ancien de la même majeure : sert
        self.assertFalse(P.compatible("1.4", "1.3"))          # prouvée sur un contrat plus récent : ne sert pas
        self.assertFalse(P.compatible("2.0", "1.3"))          # autre majeure : ne sert pas
        self.assertFalse(P.compatible("?", "1.3"))
        self.poser_ec(ec("def doubler(entree):\n    return {'y': 0, 'par': 'EC'}\n", contrat="2.0"))
        self.assertEqual(self.appeler(2)["par"], "reference")
        self.assertIn("incompatible", self.svc.etat("essai", "doubler")["ec_refusee"])

    def test_une_ec_impure_n_est_jamais_chargee_et_est_suspendue(self):
        self.poser_ec(ec("import os\n\ndef doubler(entree):\n    return {'y': 1, 'par': os.getcwd()}\n"))
        self.assertEqual(self.appeler(2)["par"], "reference")
        e = self.svc.etat("essai", "doubler")
        self.assertIn("impure", e["suspendue"]["raison"])
        self.assertTrue(self.alertes)

    def test_un_fichier_qui_n_est_pas_de_zone_ec_est_refuse(self):
        self.poser_ec(ec("def doubler(entree):\n    return {'y': 0}\n", zone="CN"))
        self.assertEqual(self.appeler(2)["par"], "reference")

    def test_active_ne_peut_pas_sortir_du_dossier(self):
        d = self.stock / "essai" / "doubler"
        d.mkdir(parents=True)
        (d / "ACTIVE").write_text("../../../secret.py", encoding="utf-8")
        self.assertEqual(self.appeler(2)["par"], "reference")
        self.assertIn("sort du dossier", self.svc.etat("essai", "doubler")["ec_refusee"])


class Disjoncteur(Banc):
    def mauvaise(self):
        self.poser_ec(ec("def doubler(entree):\n    return {'y': 'pas un entier', 'par': 'EC'}\n"))

    def test_une_sortie_hors_contrat_est_remplacee_dans_le_meme_appel(self):
        self.mauvaise()
        r = self.appeler(2)
        self.assertEqual(r, {"y": 4, "par": "reference"})                  # l'utilisateur ne voit jamais la sortie non conforme
        self.assertEqual(self.svc.etat("essai", "doubler")["fautes_recentes"], 1)

    def test_une_exception_de_l_ec_est_rattrapee(self):
        self.poser_ec(ec("def doubler(entree):\n    raise RuntimeError('boum')\n"))
        self.assertEqual(self.appeler(3)["par"], "reference")

    def test_trois_fautes_en_dix_minutes_suspendent_l_ec_et_la_conservent(self):
        self.mauvaise()
        for _ in range(3):
            self.assertEqual(self.appeler(2)["par"], "reference")
            self.t[0] += 10
        e = self.svc.etat("essai", "doubler")
        self.assertIsNotNone(e["suspendue"])
        self.assertTrue((self.stock / "essai" / "doubler" / "SUSPENDUE.json").exists())
        self.assertTrue((self.stock / "essai" / "doubler" / "EC_doubler__EC21.py").exists())       # conservée, jamais détruite
        self.assertEqual(self.alertes[0][0], "essai.doubler")
        self.assertEqual(e["sert"], "reference")
        self.assertEqual(self.appeler(5)["par"], "reference")

    def test_des_fautes_espacees_ne_suspendent_pas(self):
        self.mauvaise()
        for _ in range(4):
            self.appeler(2)
            self.t[0] += P.FENETRE_S + 1
        self.assertIsNone(self.svc.etat("essai", "doubler")["suspendue"])

    def test_reactiver_remet_l_ec_au_service(self):
        self.mauvaise()
        for _ in range(3):
            self.appeler(2)
        self.assertTrue(self.svc.etat("essai", "doubler")["suspendue"])
        self.poser_ec(ec("def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'EC'}\n"))     # l'EC est refaite (nouveau fichier)
        self.svc.reactiver("essai", "doubler")
        self.assertEqual(self.appeler(2)["par"], "EC")
        self.assertFalse((self.stock / "essai" / "doubler" / "SUSPENDUE.json").exists())

    def test_une_suspension_survit_a_un_redemarrage(self):
        self.mauvaise()
        for _ in range(3):
            self.appeler(2)
        neuf = P.ServicePoints(self.stock)
        neuf.declarer(self.m, self.mod)
        self.assertEqual(neuf.appeler("essai", "doubler", {"x": 2})["par"], "reference")
        self.assertTrue(neuf.etat("essai", "doubler")["suspendue"])

    def test_une_derive_de_sens_se_voit_par_l_echantillon(self):
        self.svc.echantillon = 1
        self.poser_ec(ec("def doubler(entree):\n    return {'y': entree['x'] * 3, 'par': 'EC'}\n"))          # conforme au schéma, mais le SENS a changé
        for _ in range(3):
            self.appeler(2)
        self.assertIn("dérive de sens", self.svc.etat("essai", "doubler")["suspendue"]["raison"])


class Contenu(Banc):
    """La vérification et le chargement portent sur le CONTENU, jamais sur une date ni une taille."""

    def test_une_ec_reecrite_de_meme_taille_a_la_meme_date_sert_le_nouveau_code(self):
        import os
        bon = ec("def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'EC'}\n")
        mauvais = bon.replace("entree['x'] * 2", "'pas un entier'")
        mauvais = mauvais.replace("'pas un entier'", "'pas un entier'".ljust(len("entree['x'] * 2")))[:len(bon)]
        self.assertEqual(len(bon), len(mauvais))                                    # même taille : un .pyc périmé se laisserait tromper
        self.poser_ec(mauvais)
        f = self.stock / "essai" / "doubler" / "EC_doubler__EC21.py"
        t = f.stat().st_mtime_ns
        self.assertEqual(self.appeler(2)["par"], "reference")                       # la mauvaise est rattrapée
        self.poser_ec(bon)
        os.utime(f, ns=(t, t))                                                      # même date, à la nanoseconde
        self.svc.reactiver("essai", "doubler")
        self.assertEqual(self.appeler(2)["par"], "EC")

    def test_une_ec_devenue_impure_sans_changer_de_date_est_revérifiée(self):
        import os
        sain = ec("def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'EC'}\n")
        self.poser_ec(sain)
        self.assertEqual(self.appeler(2)["par"], "EC")
        f = self.stock / "essai" / "doubler" / "EC_doubler__EC21.py"
        t = f.stat().st_mtime_ns
        impur = ec("import os\n\ndef doubler(entree):\n    return {'y': 1, 'par': os.getcwd()}\n")
        f.write_text(impur, encoding="utf-8")
        os.utime(f, ns=(t, t))
        self.assertEqual(self.appeler(2)["par"], "reference")                       # la vérification est liée au contenu : l'impureté est vue

    def test_un_fichier_change_entre_la_verification_et_le_chargement_est_refuse(self):
        self.poser_ec(ec("def doubler(entree):\n    return {'y': 0, 'par': 'EC'}\n"))
        f = self.stock / "essai" / "doubler" / "EC_doubler__EC21.py"
        hote = P.HotePython()
        with self.assertRaises(RuntimeError):
            hote.appelable_verifie(f, "doubler", "0" * 64)


class Routage(Banc):
    """La mise en service par paliers : l'ombre, puis une part du trafic, et le retour instantané."""

    EC_BONNE = "def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'EC'}\n"
    EC_JUMELLE = "def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'reference'}\n"        # équivalente à la référence, sortie pour sortie

    def test_en_ombre_la_reference_repond_et_l_ec_calcule_a_cote(self):
        self.poser_ec(ec(self.EC_JUMELLE))
        self.svc.router("essai", "doubler", "ombre")
        for x in range(20):
            self.assertEqual(self.appeler(x)["par"], "reference")
        o = self.svc.etat("essai", "doubler")["ombre"]
        self.assertEqual((o["appels"], o["ecarts"], o["erreurs"]), (20, 0, 0))

    def test_en_ombre_un_ecart_est_compte_sans_que_personne_ne_le_voie(self):
        self.poser_ec(ec(self.EC_BONNE))                                              # sortie conforme au schéma mais « par » diffère
        self.svc.router("essai", "doubler", "ombre")
        r = self.appeler(3)
        self.assertEqual(r["par"], "reference")                                       # l'utilisateur a la référence
        self.assertEqual(self.svc.etat("essai", "doubler")["ombre"]["ecarts"], 1)

    def test_trois_ecarts_en_ombre_suspendent_l_ec(self):
        self.poser_ec(ec(self.EC_BONNE))
        self.svc.router("essai", "doubler", "ombre")
        for x in range(3):
            self.appeler(x)
        self.assertIsNotNone(self.svc.etat("essai", "doubler")["suspendue"])

    def test_une_ec_qui_plante_en_ombre_est_comptee(self):
        self.poser_ec(ec("def doubler(entree):\n    raise RuntimeError('boum')\n"))
        self.svc.router("essai", "doubler", "ombre")
        self.assertEqual(self.appeler(1)["par"], "reference")
        self.assertEqual(self.svc.etat("essai", "doubler")["ombre"]["erreurs"], 1)

    def test_une_part_du_trafic_va_a_l_ec_et_la_meme_entree_va_toujours_du_meme_cote(self):
        self.poser_ec(ec(self.EC_BONNE))
        self.svc.router("essai", "doubler", "service", 50)
        cotes = {x: self.appeler(x)["par"] for x in range(200)}
        n_ec = sum(1 for v in cotes.values() if v == "EC")
        self.assertTrue(60 <= n_ec <= 140, n_ec)                                      # environ la moitié
        for x in (3, 77, 150):
            self.assertEqual(self.appeler(x)["par"], cotes[x])                       # stable
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "service", "part": 50})

    def test_part_zero_et_cent(self):
        self.poser_ec(ec(self.EC_BONNE))
        self.svc.router("essai", "doubler", "service", 0)
        self.assertTrue(all(self.appeler(x)["par"] == "reference" for x in range(30)))
        self.svc.router("essai", "doubler", "service", 100)
        self.assertTrue(all(self.appeler(x)["par"] == "EC" for x in range(30)))

    def test_le_retour_instantane_est_un_aiguillage(self):
        self.poser_ec(ec(self.EC_BONNE))
        self.svc.router("essai", "doubler", "service", 100)
        self.assertEqual(self.appeler(2)["par"], "EC")
        self.svc.router("essai", "doubler", "arret")                                  # un seul geste : rien à restaurer, l'EC reste dans le stock
        self.assertEqual(self.appeler(2)["par"], "reference")
        self.assertTrue((self.stock / "essai" / "doubler" / "EC_doubler__EC21.py").exists())
        self.svc.router("essai", "doubler", "service", 100)
        self.assertEqual(self.appeler(2)["par"], "EC")

    def test_un_routage_illisible_n_ouvre_rien(self):
        self.poser_ec(ec(self.EC_BONNE))
        (self.stock / "essai" / "doubler" / "ROUTAGE.json").write_text("{pas du json", encoding="utf-8")
        self.assertEqual(self.appeler(2)["par"], "reference")
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "arret", "part": 0})

    def test_le_routage_est_valide(self):
        self.poser_ec(ec(self.EC_BONNE))
        with self.assertRaises(ValueError):
            self.svc.router("essai", "doubler", "n'importe quoi")
        self.assertEqual(self.svc.router("essai", "doubler", "service", 250)["part"], 100)        # une part hors bornes est ramenée dans [0, 100]


class AutresFormats(Banc):
    def test_une_ec_wasm_sans_hote_n_est_pas_servie_et_la_reference_repond(self):
        self.poser_ec(ec("binaire", runtime="wasm"))
        self.assertEqual(self.appeler(2)["par"], "reference")
        self.assertIn("sans hôte", self.svc.etat("essai", "doubler")["ec_refusee"])

    def test_un_nouvel_hote_se_branche_sans_toucher_au_module(self):
        class HoteJson:
            """Un hôte d'essai : l'EC est un petit fichier de données, qui multiplie par un facteur."""
            def appelable(self, chemin, fonction):
                facteur = json.loads(Path(chemin).read_text(encoding="utf-8").split("\n")[-1])["facteur"]
                return lambda entree: {"y": entree["x"] * facteur, "par": "hote-json"}
        P.HOTES["essaijson"] = HoteJson
        self.addCleanup(P.HOTES.pop, "essaijson", None)
        self.poser_ec(ec('{"facteur": 5}', runtime="essaijson"), nom="EC_doubler__EC22.essai")
        self.assertEqual(self.appeler(2), {"y": 10, "par": "hote-json"})


class Contrat(unittest.TestCase):
    def test_le_schema_est_un_lecteur_tolerant(self):
        s = {"type": "object", "required": ["a"], "properties": {"a": {"type": "integer"}, "l": {"type": "array", "items": {"type": "string"}}}}
        self.assertEqual(P.valider(s, {"a": 1, "en_plus": True}), [])
        self.assertTrue(P.valider(s, {"a": True}))                        # un booléen n'est pas un entier
        self.assertTrue(P.valider(s, {"a": 1, "l": [1]}))
        self.assertTrue(P.valider(s, []))
        self.assertTrue(P.valider({"enum": ["a", "b"]}, "c"))
        self.assertEqual(P.valider(None, 12), [])

    def test_la_purete(self):
        self.assertEqual(P.analyser_purete("import math\n\ndef f(x):\n    return math.sqrt(x)\n"), [])
        for mal in ("import os\n", "def f(ctx):\n    return 1\n", "def f():\n    return open('x')\n", "import time\n", "X=1\ndef f():\n    global X\n"):
            self.assertTrue(P.analyser_purete(mal), mal)

    def test_self_n_est_admis_que_dans_une_classe_du_fichier(self):
        self.assertEqual(P.analyser_purete("class A:\n    def f(self):\n        return self\n"), [])
        self.assertTrue(P.analyser_purete("def f(self):\n    return 1\n"))
        self.assertTrue(P.analyser_purete("def f():\n    return self\n"))

    def test_une_horloge_ou_un_hasard_lus_par_attribut_sont_refuses(self):
        self.assertEqual(P.analyser_purete("import datetime\n\ndef f(s):\n    return datetime.datetime.strptime(s, '%Y')\n"), [])
        for mal in ("import datetime\n\ndef f():\n    return datetime.datetime.now()\n", "import random\n\ndef f():\n    return random.random()\n"):
            self.assertTrue(P.analyser_purete(mal), mal)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : ec, Banc, Reference, EcServie, Disjoncteur, AutresFormats, Contrat
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
