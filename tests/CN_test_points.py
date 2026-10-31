# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des points d'évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #e3f637
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des points d'évolution : le contrat, le résolveur de compatibilité, le disjoncteur, la pureté, l'ouverture à d'autres formats.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e3f637 ▼▼▼
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



class CageDesEC(unittest.TestCase):
    """Audit de sécurité C2 : une EC ne sort pas d'elle-même par la réflexion de l'interpréteur."""

    EVASIONS = (
        "def f(x): return __builtins__['__import__']('os').getcwd()",
        "def f(x): return ().__class__.__mro__[1].__subclasses__()",
        "def f(x): return getattr(x, 'real')", "def f(x): return setattr(x, 'a', 1)", "def f(x): return delattr(x, 'a')",
        "def f(x): return vars(x)", "def f(x): return dir(x)", "def f(x): return type(x)", "def f(x): return object", "def f(x): return breakpoint()", "def f(x): return help",
        "def f(x): return '{0.__class__}'.format(x)",
        "def f(x):\n    s = '{0.__cl' + 'ass__}'\n    return s.format(x)",
        "def f(x): return str.format('{0}', x)", "def f(x): return '{0.real}'.format(x)", "def f(x): return '{}'.format_map(x)",
        "import string\ndef f(x): return string.Formatter().format('{0.real}', x)",
        "import operator\ndef f(x): return operator.attrgetter('real')(x)", "import operator\ndef f(x): return operator.methodcaller('real')(x)",
        "import typing\ndef f(x): return typing.ForwardRef('x')", "import typing\ndef f(x): return typing.get_type_hints(f)",
        "def d(g): return g\n@d\ndef f(x): return x", "def d(c): return c\n@d\nclass A: pass",
        "class M(type): pass", "class M: pass\nclass A(metaclass=M): pass",
        "def f(x): return f.__globals__", "def f(x): return f.__code__", "def f(x): return x.__dict__", "def f(x): return [].append.__self__",
        "def f(x):\n    try:\n        1 / 0\n    except Exception as e:\n        return e.__traceback__",
        "def f(x): return (i for i in x).gi_frame.f_globals", "def f(x): return str.mro()",
        "from functools import *\ndef f(x): return x", "from os import path\ndef f(x): return x", "def f(__x__): return __x__", "def f(x): return __name__",
    )

    def test_les_evasions_classiques_sont_refusees(self):
        for mal in self.EVASIONS:
            self.assertTrue(P.analyser_purete(mal), mal)

    def test_ce_que_les_ec_ecrivent_vraiment_passe(self):
        ok = ("import math\n\ndef f(x):\n    return math.sqrt(x)\n", "def f(x):\n    return '{} {}'.format(x, 1.5)\n",
              "def f(x):\n    return '{0:.2f}'.format(x)\n", "class A(Exception):\n    def __init__(self):\n        super().__init__('x')\n\ndef f(x):\n    return A()\n",
              "def f(x):\n    return f'{x!r:>4}'\n")
        for bien in ok:
            self.assertEqual(P.analyser_purete(bien), [], bien)

    def test_super_init_est_la_seule_exception_dunder(self):
        self.assertTrue(P.analyser_purete("class A:\n    def f(self):\n        return super().__init__.__globals__\n"))
        self.assertTrue(P.analyser_purete("class A:\n    def f(self):\n        return self.__init__\n"))

    def test_l_execution_n_a_que_les_natives_de_la_liste_blanche(self):
        b = P.builtins_restreints()
        for dangereux in ("open", "getattr", "type", "object", "eval", "exec", "compile", "globals", "vars", "print", "input", "__builtins__"):
            self.assertNotIn(dangereux, b)
        for sur in ("len", "range", "sorted", "isinstance", "ValueError", "KeyError", "TypeError"):
            self.assertIn(sur, b)

    def test_une_ec_executee_ne_voit_pas_les_natives_dangereuses(self):
        # le texte est exécuté SANS passer par l'analyse : c'est le second rempart qu'on éprouve
        for code, erreur in (("def f(x): return open('x')", NameError), ("def f(x): return type(x)", NameError), ("def f(x): return getattr(x, 'a')", NameError),
                             ("def f(x): return eval('1')", NameError), ("def f(x): return __import__('os')", ImportError)):
            ns = {}
            P.executer_ec(code, "<essai>", ns)
            with self.assertRaises(erreur, msg=code):
                ns["f"](1)

    def test_un_import_n_expose_pas_les_modules_que_l_import_a_lui_meme_importes(self):
        ns = {}
        P.executer_ec("import email.utils\nimport functools\ndef a(x): return email.utils.os\ndef b(x): return functools.sys\ndef c(x): return email.utils.formatdate", "<essai>", ns)
        for nom in ("a", "b"):
            with self.assertRaises(AttributeError):
                ns[nom](1)
        self.assertTrue(callable(ns["c"](1)))
        with self.assertRaises(ImportError):
            P.executer_ec("import os", "<essai>", {})
        with self.assertRaises(ImportError):
            P.executer_ec("from subprocess import run", "<essai>", {})

    def test_strptime_et_strftime_fonctionnent_dans_la_cage_sans_ouvrir_time_ni_strptime_a_l_ec(self):
        """datetime.strptime/strftime/timestamp importent _strptime et time pour leur compte : la cage les laisse faire (liste MESURÉE, exactement ces deux noms),
        mais refuse toujours une instruction `import` de ces modules écrite dans l'EC, à l'analyse comme à l'exécution."""
        self.assertEqual(P.IMPORTS_INTERNES, frozenset({"_strptime", "time"}))
        ns = {}
        P.executer_ec("""from datetime import datetime
def f(x):
    d = datetime.strptime(x, '%Y-%m-%d %H:%M:%S')
    return d.strftime('%d/%m/%Y %H:%M'), d.timestamp() > 0
""", "<essai>", ns)
        self.assertEqual(ns["f"]("2026-10-17 12:30:00"), ("17/10/2026 12:30", True))
        for code in ("import time", "from time import sleep", "import _strptime", "def f(x):\n    import time\n    return time.time()", "def f(x):\n    import _strptime\n    return 1",
                     "def f(x):\n    from time import time\n    return time()"):
            self.assertTrue(P.analyser_purete(code), code)
            ns = {}
            with self.assertRaises(ImportError, msg=code):
                P.executer_ec(code, "<essai>", ns)
                ns["f"](1)
        self.assertTrue(P.analyser_purete("def f(x): return __import__('time')"))
        for autre in ("os", "sys", "subprocess", "socket", "importlib", "ctypes"):
            ns = {}
            P.executer_ec("def f(x): return __import__(%r)" % autre, "<essai>", ns)
            with self.assertRaises(ImportError, msg=autre):
                ns["f"](1)

    def test_le_chargeur_de_l_evaluateur_refuse_les_deux_evasions_prouvees(self):
        from noyau import CN_evaluateur as E
        for mal in self.EVASIONS[:2]:
            with self.assertRaises(E.Impur):
                E.charger_texte(mal, "f")
        self.assertEqual(E.charger_texte("def f(x):\n    return sorted(x)\n", "f")([2, 1]), [1, 2])

    def test_toutes_les_ec_du_depot_passent_la_cage(self):
        racine = Path(__file__).resolve().parent.parent
        fichiers = sorted(racine.glob("modules/*/points/EC_*.py"))
        self.assertTrue(fichiers)
        for f in fichiers:
            texte = f.read_text(encoding="utf-8")
            self.assertEqual(P.analyser_purete(texte), [], str(f))
            P.executer_ec(texte, str(f), {"__name__": "essai"})


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : ec, Banc, Reference, EcServie, Disjoncteur, AutresFormats, Contrat
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
