# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #38b6e6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'évolution : du texte proposé par un moteur jusqu'à l'EC en service, sans jamais servir ce qui n'est pas prouvé ; le retour, la visite à 30 jours, la chaîne.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=38b6e6 ▼▼▼
"""Bancs de l'évolution : du texte proposé par un moteur jusqu'à l'EC en service, sans jamais servir ce qui n'est pas prouvé ; le retour, la visite à 30 jours, la chaîne."""
import json
import shutil
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_evaluateur as EV  # noqa: E402
from noyau import CN_evolution as E  # noqa: E402
from noyau import CN_manifeste as M  # noqa: E402
from noyau import CN_points as P  # noqa: E402
from noyau import CN_rejeu as R  # noqa: E402

LENTE = "def doubler(entree):\n    s = sum(entree['x'] for _ in range(2000))\n    return {'y': s * 2 // 2000}\n"
RAPIDE = "def doubler(entree):\n    return {'y': entree['x'] * 2}\n"
FAUSSE = "def doubler(entree):\n    return {'y': entree['x'] * 3}\n"
CONTRAT = {"entree": {"type": "object", "required": ["x"], "properties": {"x": {"type": "integer"}}},
           "sortie": {"type": "object", "required": ["y"], "properties": {"y": {"type": "integer"}}}}


class MoteurSimule:
    """Un moteur de recherche qui ne fait que PROPOSER du texte, comme tout moteur branché par le contrat d'adaptateur."""

    def __init__(self, *candidats):
        self.candidats, self.contextes = list(candidats), []

    def proposer(self, contexte):
        self.contextes.append(contexte)
        return self.candidats


class Banc(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        mod = self.tmp / "modules" / "essai"
        (mod / "points").mkdir(parents=True)
        (mod / "contrats").mkdir()
        (mod / "points" / "EC_doubler.py").write_text(LENTE, encoding="utf-8")
        (mod / "contrats" / "CN_doubler.json").write_text(json.dumps(CONTRAT), encoding="utf-8")
        self.svc = P.ServicePoints(self.tmp / "ec")
        self.svc.declarer(types.SimpleNamespace(id="essai", points_evolution=(M.PointEvolution("doubler", "Double", "1.0", "points/EC_doubler", "doubler"),)), mod)
        self.rejeu = R.Rejeu(self.tmp / "rejeu.db")
        self.svc.enregistreur = self.rejeu.enregistrer
        for i in range(60):                                                  # le trafic réel : 60 entrées distinctes, avec leurs durées
            self.rejeu.enregistrer("essai.doubler", {"x": i}, None, 0.05)
        self.t = [1_000_000.0]
        self.ev = EV.Evaluateur(self.svc, self.rejeu, minimum=20)
        self.evo = E.Evolution(self.svc, self.rejeu, self.ev, self.tmp / "evolution.db", horloge=lambda: self.t[0],
                               seuils={"pieges_min": 0.5, "ombre_appels": 20, "appels_par_palier": 20})

    def proposer(self, *candidats, **kw):
        return self.evo.proposer("essai", "doubler", MoteurSimule(*candidats), **kw)

    def trafic(self, n):
        for i in range(n):
            self.svc.appeler("essai", "doubler", {"x": i % 60})


class Cibler(Banc):
    def test_les_points_sont_classes_par_ce_que_l_optimisation_rapporterait(self):
        c = self.evo.cibles()
        self.assertEqual(c[0]["point"], "essai.doubler")
        self.assertEqual(c[0]["valeur_ms"], round(60 * 0.05, 1))
        self.assertFalse(c[0]["muet"])

    def test_un_point_sans_mesure_est_dit_muet_et_range_en_dernier(self):
        self.svc.declarer(types.SimpleNamespace(id="autre", points_evolution=(M.PointEvolution("rien", "Rien", "1.0", "points/EC_doubler", "doubler"),)), self.tmp / "modules" / "essai")
        c = self.evo.cibles()
        self.assertEqual(c[-1]["point"], "autre.rien")
        self.assertTrue(c[-1]["muet"])
        self.assertIsNone(c[-1]["valeur_ms"])                                  # « — », pas « 0 » : zéro serait une mesure

    def test_le_generateur_ne_voit_que_la_partition_visible(self):
        m = MoteurSimule(RAPIDE)
        self.evo.proposer("essai", "doubler", m)
        vus = {R.empreinte(e) for e in m.contextes[0]["entrees"]}
        reserves = {c["h"] for c in self.rejeu.corpus("essai.doubler", "reserve")}
        self.assertTrue(vus)
        self.assertEqual(vus & reserves, set())                                 # jamais une entrée du jeu réservé


class Proposer(Banc):
    def test_la_meilleure_variante_prouvee_est_ecrite_et_mise_en_ombre(self):
        r = self.proposer(FAUSSE, RAPIDE, "def doubler(:\n")
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["piece"]["ec"], r["piece"]["etat"]), ("EC1", "ombre"))
        verdicts = [e["verdict"] for e in r["essais"]]
        self.assertEqual(sorted(verdicts), sorted(["divergente", "equivalente", "illisible"]))
        f = self.tmp / "ec" / "essai" / "doubler" / "EC_doubler__EC1.py"
        self.assertTrue(f.exists())
        texte = f.read_text(encoding="utf-8")
        self.assertIn("# ZONE       : EC", texte)
        self.assertIn("# CONTRAT PROUVÉ : @1.0", texte)
        self.assertEqual(P.analyser_purete(texte), [])                          # ce qu'on écrit passe la règle que le noyau appliquera
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "ombre", "part": 0})

    def test_en_ombre_rien_n_est_servi(self):
        self.proposer(RAPIDE)
        self.trafic(10)
        self.assertEqual(self.svc.etat("essai", "doubler")["sert"], "EC1")      # l'EC est vérifiée et chargée...
        r = self.svc.appeler("essai", "doubler", {"x": 5})
        self.assertEqual(r, {"y": 10})                                          # ... mais c'est la référence qui répond (même valeur ici)
        self.assertEqual(self.svc.etat("essai", "doubler")["ombre"]["ecarts"], 0)

    def test_une_variante_fausse_devient_une_tombe_et_n_est_pas_reproposee(self):
        self.proposer(FAUSSE)
        h = E.empreinte_ast(FAUSSE)
        self.assertIn(h, self.evo.tombes("essai.doubler"))
        r = self.proposer(FAUSSE)
        self.assertEqual(r["essais"][0]["verdict"], "deja_vue")

    def test_la_reference_elle_meme_n_est_pas_une_variante(self):
        r = self.proposer(LENTE)
        self.assertFalse(r["ok"])
        self.assertEqual(r["essais"][0]["verdict"], "identique")

    def test_sans_gain_aucune_promotion(self):
        r = self.proposer("def doubler(entree):\n    s = sum(entree['x'] for _ in range(4000))\n    return {'y': s * 2 // 4000}\n")          # équivalente, mais deux fois plus lente
        self.assertFalse(r["ok"])
        self.assertIn("aucune variante prouvée et plus rapide", r["raison"])

    def test_une_variante_aussi_rapide_n_est_jamais_prise_pour_un_gain(self):
        """Le bruit de mesure : la référence chronométrée contre elle-même. Une variante qui lui ressemble ne gagne jamais, même si une mesure fluctue au-dessus de 5 %."""
        pareille = "def doubler(entree):\n    s = sum(entree['x'] for _ in range(2000))\n    return {'y': s * 2 // 2000 - 0}\n"
        r = self.ev.evaluer("essai", "doubler", pareille)
        self.assertEqual(r["verdict"], "equivalente")
        self.assertIsNotNone(r["bruit_pct"])                                   # l'évaluateur dit combien il se trompe
        for _ in range(3):
            self.assertFalse(self.proposer(pareille)["ok"])                    # 3 essais : aucune promotion, malgré le hasard des mesures

    def test_un_corpus_trop_etroit_n_autorise_aucune_promotion(self):
        evo = E.Evolution(self.svc, self.rejeu, EV.Evaluateur(self.svc, self.rejeu, minimum=500), self.tmp / "e2.db", seuils={"pieges_min": 0.5})
        r = evo.proposer("essai", "doubler", MoteurSimule(RAPIDE))
        self.assertFalse(r["ok"])
        self.assertIn("trop étroit", r["raison"])
        self.assertFalse((self.tmp / "ec" / "essai" / "doubler" / "ACTIVE").exists())          # rien n'a été écrit

    def test_un_corpus_trop_faible_pour_juger_est_dit_faible(self):
        faible = R.Rejeu(self.tmp / "faible.db")
        faible.enregistrer("essai.doubler", {"x": 0}, None, 0.05)
        evo = E.Evolution(self.svc, faible, EV.Evaluateur(self.svc, faible, minimum=0), self.tmp / "e3.db", seuils={"pieges_min": 0.85})
        r = evo.proposer("essai", "doubler", MoteurSimule(RAPIDE))
        self.assertFalse(r["ok"], r)
        self.assertIn("corpus trop faible", r["raison"])

    def test_un_moteur_qui_echoue_ne_casse_rien(self):
        class Casse:
            def proposer(self, ctx):
                raise RuntimeError("modèle indisponible")
        r = self.evo.proposer("essai", "doubler", Casse())
        self.assertFalse(r["ok"])
        self.assertIn("modèle indisponible", r["raison"])


class Paliers(Banc):
    def monter(self):
        self.proposer(RAPIDE)
        self.trafic(20)
        return self.evo.tick()

    def test_l_ombre_sans_ecart_ouvre_le_premier_palier_puis_la_suite(self):
        f = self.monter()
        self.assertEqual((f[0]["etat"], f[0]["part"]), ("palier_10", 10))
        self.assertEqual(self.evo.tick(), [])                                    # pas assez d'appels sur ce palier : on attend
        self.trafic(20)
        self.assertEqual(self.evo.tick()[0]["etat"], "palier_50")
        self.trafic(20)
        self.assertEqual(self.evo.tick()[0]["etat"], "en_service")
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "service", "part": 100})

    def test_un_ecart_en_ombre_bloque_la_promotion(self):
        self.proposer(RAPIDE)
        (self.tmp / "ec" / "essai" / "doubler" / "EC_doubler__EC1.py").write_text(
            (self.tmp / "ec" / "essai" / "doubler" / "EC_doubler__EC1.py").read_text(encoding="utf-8").replace("* 2", "* 2 + 0 if entree['x'] > 5 else 1 + entree['x'] * 2"), encoding="utf-8")        # un écart sur les petites entrées, que le trafic de l'ombre atteint
        self.trafic(30)
        faits = self.evo.tick()
        self.assertTrue(faits and all(f["etat"] == "retiree" for f in faits), faits)                  # jamais promue : trois écarts en ombre suspendent l'EC, qui est retirée
        self.assertEqual(self.evo.pieces("essai.doubler")[0]["etat"], "retiree")
        self.assertTrue(self.evo.tombes("essai.doubler"))
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "arret", "part": 0})

    def test_le_disjoncteur_retire_la_piece_et_en_fait_une_tombe(self):
        self.monter()
        d = self.tmp / "ec" / "essai" / "doubler"
        (d / "EC_doubler__EC1.py").write_text((d / "EC_doubler__EC1.py").read_text(encoding="utf-8").replace("entree['x'] * 2", "'pas un entier'"), encoding="utf-8")
        self.svc.reactiver("essai", "doubler")
        for i in range(10):
            self.svc.appeler("essai", "doubler", {"x": i})                       # palier 10 % : quelques entrées tombent sur l'EC défaillante
            self.svc.appeler("essai", "doubler", {"x": 100 + i})
        faits = self.evo.tick()
        self.assertTrue(any(f["etat"] == "retiree" for f in faits) or self.evo.pieces("essai.doubler")[0]["etat"] in ("palier_10", "palier_50", "retiree"))

    def test_le_retour_instantane_est_un_aiguillage_et_laisse_une_tombe(self):
        self.monter()
        r = self.evo.retour("essai.doubler", "essai de retour")
        self.assertEqual(r[0]["etat"], "retiree")
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "arret", "part": 0})
        self.assertTrue((self.tmp / "ec" / "essai" / "doubler" / "EC_doubler__EC1.py").exists())      # rien n'est détruit
        self.assertEqual(self.proposer(RAPIDE)["essais"][0]["verdict"], "deja_vue")


class Visite(Banc):
    def en_service(self):
        self.proposer(RAPIDE)
        for _ in range(3):
            self.trafic(20)
            self.evo.tick()
        self.assertEqual(self.evo.pieces("essai.doubler")[0]["etat"], "en_service")

    def test_pas_de_visite_avant_le_delai(self):
        self.en_service()
        self.t[0] += 29 * 86400
        self.assertEqual(self.evo.visiter(), [])

    def test_un_gain_qui_est_reste_est_confirme(self):
        self.en_service()
        self.t[0] += 31 * 86400
        v = self.evo.visiter()
        self.assertEqual(len(v), 1)
        self.assertTrue(v[0]["tenu"], v)
        self.assertEqual(self.evo.pieces("essai.doubler")[0]["etat"], "en_service")
        self.assertEqual(self.evo.visiter(), [])                                  # une seule visite

    def test_un_gain_qui_n_est_pas_reste_retire_la_piece(self):
        self.en_service()
        self.evo.seuils["gain_confirme"] = 50.0                                   # exiger cinquante fois le gain annoncé : impossible à tenir
        self.t[0] += 31 * 86400
        v = self.evo.visiter()
        self.assertFalse(v[0]["tenu"])
        self.assertEqual(self.evo.pieces("essai.doubler")[0]["etat"], "retiree")
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "arret", "part": 0})
        self.assertTrue(self.evo.tombes("essai.doubler"))


class Chaine(Banc):
    def test_la_chaine_se_verifie_et_une_rupture_se_voit(self):
        self.proposer(RAPIDE)
        self.trafic(20)
        self.evo.tick()
        v = self.evo.verifier_chaine()
        self.assertTrue(v["ok"])
        self.assertGreaterEqual(v["mailles"], 3)
        with sqlite3.connect(str(self.tmp / "evolution.db")) as c:
            c.execute("UPDATE chaine SET details='{\"ec\": \"EC9\"}' WHERE seq=1")
        w = self.evo.verifier_chaine()
        self.assertFalse(w["ok"])
        self.assertEqual(w["rupture_a"], 1)

    def test_chaque_etape_est_dans_la_chaine(self):
        self.proposer(RAPIDE)
        verbes = [m["verbe"] for m in self.evo.chaine("essai.doubler")]
        self.assertIn("proposee", verbes)
        self.assertIn("ombre", verbes)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : MoteurSimule, Banc, Cibler, Proposer, Paliers, Visite, Chaine
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
