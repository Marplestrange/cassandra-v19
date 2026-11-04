# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'audit d'Évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #db4337
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'audit d'Évolution : chaque défaut trouvé à l'audit (deux passages) a ici le banc qui le rejoue.
# MÉTHODE    : les bancs de l'évolution (Banc de CN_test_evolution) et des points (Banc de CN_test_points), un banc par défaut trouvé ; les EC qui bouclent sont de vraies EC dans de vrais processus.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=db4337 ▼▼▼
"""Bancs de l'audit d'Évolution : chaque défaut trouvé à l'audit (deux passages) a ici le banc qui le rejoue.

Isolation (le délai tue l'EC), échec fermé du routage, une seule pièce vivante par point, suspension qui ne tue pas le point, course entre deux propositions,
statistiques partagées entre processus, preuve par entrées distinctes, comparaison au texte JSON, chaîne scellée, sceau des EC, corpus (taille, exclusions, borne).
"""
import json
import sys
import threading
import time
import types
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from noyau import CN_evaluateur as EV  # noqa: E402
from noyau import CN_evolution as E  # noqa: E402
from noyau import CN_manifeste as M  # noqa: E402
from noyau import CN_points as P  # noqa: E402
from noyau import CN_rejeu as R  # noqa: E402
import CN_test_evolution as T  # noqa: E402
import CN_test_points as TP  # noqa: E402

RAPIDE = T.RAPIDE
RAPIDE2 = "def doubler(entree):\n    return {'y': entree['x'] + entree['x']}\n"
RAPIDE3 = "def doubler(entree):\n    x = entree['x']\n    return {'y': x * 2}\n"


class Banc(T.Banc):
    def declarer_contrat(self, contrat, delai_ms=None):
        """Réécrit le contrat du point d'essai (et le déclare de nouveau)."""
        c = dict(contrat, **({"delai_ms": delai_ms} if delai_ms else {}))
        (self.tmp / "modules" / "essai" / "contrats" / "CN_doubler.json").write_text(json.dumps(c), encoding="utf-8")
        self.svc.declarer(types.SimpleNamespace(id="essai", points_evolution=(M.PointEvolution("doubler", "Double", "1.0", "points/EC_doubler", "doubler"),)), self.tmp / "modules" / "essai")

    def etat_piece(self, num):
        return [p["etat"] for p in self.evo.pieces("essai.doubler") if p["num"] == num][0]


class Suspension(Banc):
    def test_une_suspension_ne_tue_pas_le_point_pour_toujours(self):
        self.assertTrue(self.proposer(RAPIDE)["ok"])
        self.svc._suspendre(self.svc._points["essai.doubler"], "essai", "EC1")
        self.evo.tick()
        self.assertEqual(self.etat_piece(1), "retiree")
        r = self.proposer(RAPIDE2)
        self.assertTrue(r["ok"], r)
        self.assertIsNone(self.svc.etat("essai", "doubler")["suspendue"])                       # la pièce neuve repart d'un compte vide
        self.trafic(25)
        self.evo.tick()
        self.assertIn(self.etat_piece(2), ("ombre", "palier_10"))                             # elle n'est pas retirée à tort
        self.assertEqual(self.svc.etat("essai", "doubler")["ec_refusee"], "")


class UneSeulePiece(Banc):
    def test_une_nouvelle_piece_remplace_la_vivante(self):
        self.proposer(RAPIDE)
        self.avancer("en_service")
        self.assertTrue(self.proposer(RAPIDE3)["ok"])
        vivantes = [p for p in self.evo.pieces("essai.doubler", E.ETATS_VIVANTS)]
        self.assertEqual([p["num"] for p in vivantes], [2])
        self.assertEqual(self.etat_piece(1), "retiree")
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "ombre", "part": 0})
        self.assertEqual(self.evo.tombes("essai.doubler"), set())                               # une pièce remplacée n'est pas une tombe

    def test_deux_propositions_en_meme_temps_se_suivent(self):
        res = {}

        def go(k, t):
            try:
                res[k] = self.proposer(t)["ok"]
            except Exception as e:                                                              # une IntegrityError, une PermissionError : le défaut d'avant l'audit
                res[k] = "%s: %s" % (type(e).__name__, e)
        fils = [threading.Thread(target=go, args=("a", RAPIDE)), threading.Thread(target=go, args=("b", RAPIDE2))]
        [f.start() for f in fils]
        [f.join() for f in fils]
        self.assertEqual(res, {"a": True, "b": True})
        self.assertEqual([p["num"] for p in self.evo.pieces("essai.doubler", E.ETATS_VIVANTS)], [2])
        act = (self.tmp / "ec" / "essai" / "doubler" / "ACTIVE").read_text()
        piece = [p for p in self.evo.pieces("essai.doubler") if p["etat"] == "ombre"][0]
        corps = E.Evolution._corps_ec((self.tmp / "ec" / "essai" / "doubler" / act).read_text(encoding="utf-8"))
        self.assertEqual(E.empreinte_ast(corps), piece["ast"])                                  # le fichier servi EST celui qui a été jugé


class EchecFerme(Banc):
    def test_une_ec_sans_routage_ne_sert_pas(self):
        d = self.tmp / "ec" / "essai" / "doubler"
        d.mkdir(parents=True)
        (d / "EC_doubler__EC1.py").write_text(TP.ec("def doubler(entree):\n    return {'y': 6, 'par': 'EC'}\n", version="EC1"), encoding="utf-8")
        (d / "ACTIVE").write_text("EC_doubler__EC1.py", encoding="utf-8")
        self.assertEqual(self.svc.appeler("essai", "doubler", {"x": 3})["y"], 6)
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "arret", "part": 0})
        self.assertEqual(self.svc.appeler("essai", "doubler", {"x": 4}), {"y": 8})              # la référence : l'EC n'a pas été servie

    def test_si_le_routage_echoue_rien_ne_sert_et_la_piece_est_retiree(self):
        def boom(*a, **k):
            raise ValueError("routage en panne")
        self.svc.router = boom
        with self.assertRaises(ValueError):
            self.proposer(RAPIDE)
        self.assertFalse((self.tmp / "ec" / "essai" / "doubler" / "ACTIVE").exists())
        self.assertEqual(self.etat_piece(1), "retiree")
        self.assertEqual(self.svc.etat("essai", "doubler")["sert"], "reference")


class Preuves(Banc):
    def test_deux_cents_fois_la_meme_entree_ne_prouvent_rien(self):
        self.proposer(RAPIDE)
        for _ in range(60):
            self.svc.appeler("essai", "doubler", {"x": 1})
        self.assertEqual(self.evo.tick(), [])
        self.assertEqual(self.etat_piece(1), "ombre")
        self.assertEqual(self.svc.etat("essai", "doubler")["ombre"]["distincts"], 1)

    def test_les_compteurs_survivent_a_un_redemarrage(self):
        self.proposer(RAPIDE)
        self.avancer("palier_10")
        avant = self.svc.etat("essai", "doubler")
        svc2 = P.ServicePoints(self.tmp / "ec")
        svc2.declarer(types.SimpleNamespace(id="essai", points_evolution=(M.PointEvolution("doubler", "Double", "1.0", "points/EC_doubler", "doubler"),)), self.tmp / "modules" / "essai")
        apres = svc2.etat("essai", "doubler")
        self.assertEqual((apres["appels"], apres["ec_appels"]), (avant["appels"], avant["ec_appels"]))        # un autre processus voit le même compte
        evo2 = E.Evolution(svc2, self.rejeu, self.ev, self.tmp / "evolution.db", horloge=lambda: self.t[0], seuils=self.evo.seuils)
        for i in range(400):
            svc2.appeler("essai", "doubler", {"x": i % 60})
        self.assertTrue(evo2.tick())                                                           # le palier avance : plus de blocage après redémarrage

    def test_l_ombre_d_un_autre_processus_compte(self):
        self.proposer(RAPIDE)
        svc2 = P.ServicePoints(self.tmp / "ec")                                                # le démon du Sensorium : un autre processus, le même stock
        svc2.declarer(types.SimpleNamespace(id="essai", points_evolution=(M.PointEvolution("doubler", "Double", "1.0", "points/EC_doubler", "doubler"),)), self.tmp / "modules" / "essai")
        for i in range(30):
            svc2.appeler("essai", "doubler", {"x": i})
        o = self.svc.etat("essai", "doubler")["ombre"]
        self.assertEqual((o["appels"], o["distincts"]), (30, 30))
        self.assertEqual([f["etat"] for f in self.evo.tick()], ["palier_10"])


class Comparaison(Banc):
    def test_un_entier_et_un_flottant_ne_sont_pas_la_meme_reponse(self):
        self.declarer_contrat({"entree": T.CONTRAT["entree"], "sortie": {"type": "object", "required": ["y"]}})
        r = self.ev.evaluer("essai", "doubler", "def doubler(entree):\n    return {'y': float(entree['x'] * 2)}\n", chrono=False)
        self.assertEqual(r["verdict"], "divergente", r)
        self.assertNotEqual(P._canon({"y": 1}), P._canon({"y": 1.0}))
        self.assertNotEqual(P._canon({"a": 1, "b": 2}), P._canon({"b": 2, "a": 1}))

    def test_le_contrat_absent_refuse_le_point(self):
        (self.tmp / "modules" / "essai" / "contrats" / "CN_doubler.json").unlink()
        svc = P.ServicePoints(self.tmp / "ec2")
        defauts = svc.declarer(types.SimpleNamespace(id="essai", points_evolution=(M.PointEvolution("doubler", "Double", "1.0", "points/EC_doubler", "doubler"),)), self.tmp / "modules" / "essai")
        self.assertTrue(defauts and "contrat introuvable" in defauts[0], defauts)
        with self.assertRaises(P.PointDefaillant):
            svc.appeler("essai", "doubler", {"x": 2})

    def test_le_schema_valide_toute_la_liste_et_refuse_ce_qui_n_est_pas_prevu(self):
        s = {"type": "array", "items": {"type": "integer"}, "maxItems": 100}
        self.assertTrue(P.valider(s, [1] * 60 + ["x"]))                                         # le 61e élément était hors de vue avant l'audit
        self.assertTrue(P.valider(s, [1] * 101))
        self.assertTrue(P.valider({"type": "object", "properties": {"a": {}}, "additionalProperties": False}, {"a": 1, "b": 2}))

    def test_un_gain_sans_cas_reserve_ne_se_dit_pas_tenu(self):
        r = self.ev.evaluer("essai", "doubler", RAPIDE, minimum=20)
        self.assertIn(r["verdict"], ("equivalente", "corpus_trop_etroit"))
        self.assertTrue(r["gain_tient"] is True or r["verdict"] == "corpus_trop_etroit")


class Isolation(Banc):
    """Le code d'une EC ne tourne pas dans le serveur : le délai TUE le processus."""

    def test_une_boucle_au_chargement_d_un_candidat_est_dite_et_ne_fige_rien(self):
        self.declarer_contrat(T.CONTRAT, delai_ms=300)
        t0 = time.time()
        r = self.ev.evaluer("essai", "doubler", "while True:\n    pass\ndef doubler(entree):\n    return {'y': 1}\n", chrono=False)
        self.assertEqual(r["verdict"], "erreur", r)
        self.assertLess(time.time() - t0, 30)

    def test_une_boucle_dans_la_fonction_est_tuee_au_delai(self):
        self.declarer_contrat(T.CONTRAT, delai_ms=300)
        r = self.ev.evaluer("essai", "doubler", "def doubler(entree):\n    while True:\n        pass\n", chrono=False)
        self.assertEqual(r["verdict"], "erreur", r)
        self.assertIn("Delai", r["erreur"])

    def test_une_regex_catastrophique_est_tuee_elle_aussi(self):
        self.declarer_contrat(T.CONTRAT, delai_ms=400)
        cand = "import re\ndef doubler(entree):\n    re.match(r'(a+)+$', 'a' * 40 + 'b')\n    return {'y': entree['x'] * 2}\n"
        t0 = time.time()
        r = self.ev.evaluer("essai", "doubler", cand, chrono=False)
        self.assertEqual(r["verdict"], "erreur", r)                                              # avant l'audit : le serveur entier restait pris
        self.assertLess(time.time() - t0, 30)

    def test_une_ec_qui_boucle_en_service_est_tuee_et_la_reference_repond(self):
        d = self.tmp / "ec" / "essai" / "doubler"
        d.mkdir(parents=True)
        (d / "EC_doubler__EC1.py").write_text(TP.ec("def doubler(entree):\n    while True:\n        pass\n", version="EC1"), encoding="utf-8")
        (d / "ACTIVE").write_text("EC_doubler__EC1.py", encoding="utf-8")
        self.declarer_contrat(T.CONTRAT, delai_ms=300)
        self.svc.router("essai", "doubler", "service", 100)
        t0 = time.time()
        self.assertEqual(self.svc.appeler("essai", "doubler", {"x": 5}), {"y": 10})             # la référence, dans le même appel
        self.assertLess(time.time() - t0, 10)
        self.assertEqual(self.svc.etat("essai", "doubler")["fautes_recentes"], 1)

    def test_une_ec_qui_boucle_en_ombre_ne_fige_pas_la_reference(self):
        d = self.tmp / "ec" / "essai" / "doubler"
        d.mkdir(parents=True)
        (d / "EC_doubler__EC1.py").write_text(TP.ec("def doubler(entree):\n    while True:\n        pass\n", version="EC1"), encoding="utf-8")
        (d / "ACTIVE").write_text("EC_doubler__EC1.py", encoding="utf-8")
        self.declarer_contrat(T.CONTRAT, delai_ms=300)
        self.svc.router("essai", "doubler", "ombre")
        t0 = time.time()
        self.assertEqual(self.svc.appeler("essai", "doubler", {"x": 5}), {"y": 10})
        self.assertLess(time.time() - t0, 10)
        self.assertEqual(self.svc.etat("essai", "doubler")["ombre"]["erreurs"], 1)

    def test_un_travailleur_repond_et_se_tue(self):
        t = P._Travailleur(256)
        self.addCleanup(t.tuer)
        r = t.echange({"op": "charger", "texte": "def f(x):\n    return {'a': 1}\n", "fonction": "f"}, 10)
        self.assertTrue(r["ok"], r)
        self.assertEqual(t.echange({"op": "appeler", "entree": {}}, 10)["sortie"], {"a": 1})
        t.tuer()
        self.assertFalse(t.vivant())

    def test_une_ec_qui_lit_l_entree_standard_ne_vole_pas_le_canal(self):
        """shlex.shlex(None) lit « stdin » : dans le travailleur, c'est le canal du serveur. Il y trouve une entrée vide (le défaut qui a fait échouer planifie.segments)."""
        t = P._Travailleur(256)
        self.addCleanup(t.tuer)
        src = "import shlex\ndef f(x):\n    return {'v': list(shlex.shlex(x['cmd'], posix=True))}\n"
        self.assertTrue(t.echange({"op": "charger", "texte": src, "fonction": "f"}, 10)["ok"])
        self.assertEqual(t.echange({"op": "appeler", "entree": {"cmd": None}}, 5)["sortie"], {"v": []})
        self.assertEqual(t.echange({"op": "appeler", "entree": {"cmd": "ls abc"}}, 5)["sortie"], {"v": ["ls", "abc"]})        # le canal est intact


class Sceau(TP.Banc):
    def setUp(self):
        super().setUp()
        self.svc = P.ServicePoints(self.stock, horloge=lambda: self.t[0], exiger_sceau=True)
        self.svc.declarer(self.m, self.mod)

    def test_une_ec_deposee_sans_sceau_ne_sert_pas(self):
        self.poser_ec(TP.ec("def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'EC'}\n"))
        self.assertEqual(self.appeler(4)["par"], "reference")
        self.assertIn("sceau", self.svc.etat("essai", "doubler")["ec_refusee"])
        self.svc.sceller("essai", "doubler", "EC_doubler__EC21.py")
        self.assertEqual(self.appeler(4)["par"], "EC")

    def test_un_fichier_change_apres_le_sceau_ne_sert_plus(self):
        self.poser_ec(TP.ec("def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'EC'}\n"))
        self.svc.sceller("essai", "doubler", "EC_doubler__EC21.py")
        self.assertEqual(self.appeler(4)["par"], "EC")
        f = self.stock / "essai" / "doubler" / "EC_doubler__EC21.py"
        f.write_text(f.read_text(encoding="utf-8").replace("'EC'", "'PIRATE'"), encoding="utf-8")
        self.assertEqual(self.appeler(4)["par"], "reference")

    def test_un_routage_non_signe_n_ouvre_rien(self):
        self.poser_ec(TP.ec("def doubler(entree):\n    return {'y': entree['x'] * 2, 'par': 'EC'}\n"))
        self.svc.sceller("essai", "doubler", "EC_doubler__EC21.py")
        (self.stock / "essai" / "doubler" / "ROUTAGE.json").write_text(json.dumps({"mode": "service", "part": 100, "gen": "x"}), encoding="utf-8")
        self.svc._routes.clear()
        self.assertEqual(self.appeler(4)["par"], "reference")
        self.assertEqual(self.svc.etat("essai", "doubler")["routage"], {"mode": "arret", "part": 0})


class Chaine(Banc):
    def test_la_troncature_de_la_chaine_se_voit(self):
        import sqlite3
        self.proposer(RAPIDE)
        self.trafic(25)
        self.evo.tick()
        self.assertTrue(self.evo.verifier_chaine()["ok"])
        with sqlite3.connect(str(self.tmp / "evolution.db")) as c:
            c.execute("DELETE FROM chaine WHERE seq=(SELECT MAX(seq) FROM chaine)")
        v = self.evo.verifier_chaine()
        self.assertFalse(v["ok"], v)
        self.assertIn("coupée", v.get("raison", ""))

    def test_sans_la_cle_on_ne_refait_pas_une_chaine(self):
        import sqlite3
        evo = E.Evolution(self.svc, self.rejeu, self.ev, self.tmp / "scelle.db", horloge=lambda: self.t[0], seuils=self.evo.seuils, cle=b"k" * 32)
        evo.proposer("essai", "doubler", T.MoteurSimule(RAPIDE))
        self.assertTrue(evo.verifier_chaine()["ok"])
        faux = E.Evolution(self.svc, self.rejeu, self.ev, self.tmp / "scelle.db", horloge=lambda: self.t[0], seuils=self.evo.seuils, cle=b"autre cle" * 4)
        self.assertFalse(faux.verifier_chaine()["ok"])                                          # une autre clé ne valide rien
        with sqlite3.connect(str(self.tmp / "scelle.db")) as c:                                 # un attaquant qui réécrit les mailles en SHA-256 simple
            import hashlib
            prev = "0" * 64
            for r in c.execute("SELECT seq, ts, gid, verbe, details FROM chaine ORDER BY seq").fetchall():
                h = hashlib.sha256(("%s|%r|%s|%s|%s" % (prev, r[1], r[2], r[3], r[4])).encode("utf-8")).hexdigest()
                c.execute("UPDATE chaine SET previous_hash=?, hash=? WHERE seq=?", (prev, h, r[0]))
                prev = h
        self.assertFalse(evo.verifier_chaine()["ok"])


class Budget(Banc):
    def test_le_plafond_de_propositions_par_jour(self):
        self.evo.seuils["propositions_par_jour"] = 2
        self.proposer(FAUSSE_X := "def doubler(entree):\n    return {'y': entree['x'] * 3}\n")
        self.proposer(FAUSSE_X)
        r = self.proposer(RAPIDE)
        self.assertFalse(r["ok"])
        self.assertIn("plafond", r["raison"])
        self.t[0] += 86400 + 1
        self.assertTrue(self.proposer(RAPIDE)["ok"])


class Visites(Banc):
    def test_la_visite_revient_a_chaque_echeance(self):
        self.proposer(RAPIDE)
        self.avancer("en_service")
        self.t[0] += 31 * 86400
        v1 = self.evo.visiter()
        self.assertEqual(len(v1), 1)
        self.t[0] += 5 * 86400
        self.assertEqual(self.evo.visiter(), [])                                                # pas avant l'échéance suivante
        self.t[0] += 30 * 86400
        self.assertEqual(len(self.evo.visiter()), 1)                                            # avant l'audit : une seule visite dans la vie de la pièce

    def test_un_corpus_devenu_trop_etroit_ne_retire_rien_et_ne_laisse_pas_de_tombe(self):
        self.proposer(RAPIDE)
        self.avancer("en_service")
        self.evo.evaluateur.minimum = 10 ** 6                                                   # le corpus ne peut plus juger
        self.t[0] += 31 * 86400
        v = self.evo.visiter()
        self.assertIsNone(v[0]["tenu"])
        self.assertEqual(self.etat_piece(1), "en_service")
        self.assertEqual(self.evo.tombes("essai.doubler"), set())
        self.assertEqual(self.evo.visiter(), [])                                                # reprise le lendemain, pas au prochain tick
        self.t[0] += 86400 + 1
        self.assertEqual(len(self.evo.visiter()), 1)

    def test_le_moteur_ne_fait_qu_une_visite_par_passage(self):
        self.proposer(RAPIDE)
        self.avancer("en_service")
        self.t[0] += 31 * 86400
        self.assertLessEqual(len(self.evo.visiter(maximum=1)), 1)


class Corpus(unittest.TestCase):
    def setUp(self):
        import tempfile
        import shutil
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_une_entree_enorme_n_est_pas_gardee(self):
        r = R.Rejeu(self.tmp / "r.db")
        r.enregistrer("a.b", {"pj": "x" * (R.MAX_ENTREE_OCTETS + 10)}, None, 1.0)
        r.enregistrer("a.b", {"x": 1}, None, 1.0)
        self.assertEqual(r.stats("a.b")["distincts"], 1)

    def test_le_plafond_d_entree_se_regle(self):
        r = R.Rejeu(self.tmp / "r.db", max_entree_octets=R.MAX_ENTREE_OCTETS * 4)
        r.enregistrer("a.b", {"pj": "x" * (R.MAX_ENTREE_OCTETS + 10)}, None, 1.0)
        self.assertEqual(r.stats("a.b")["distincts"], 1)

    def test_un_point_exclu_n_est_jamais_enregistre(self):
        r = R.Rejeu(self.tmp / "r.db", exclus=("courrier.*",))
        r.enregistrer("courrier.corps", {"x": 1}, None, 1.0)
        r.enregistrer("vue.composer", {"x": 1}, None, 1.0)
        self.assertEqual(r.points(), ["vue.composer"])

    def test_la_borne_vaut_pour_chaque_point(self):
        r = R.Rejeu(self.tmp / "r.db", max_par_point=5)
        for i in range(30):
            r.enregistrer("a.un", {"i": i}, None, 1.0)
        for i in range(30):
            r.enregistrer("b.deux", {"i": i}, None, 1.0)
        for i in range(R.PURGE_TOUS_LES):
            r.enregistrer("c.trois", {"i": i}, None, 1.0)
        self.assertLessEqual(r.stats("a.un")["distincts"], 5)
        self.assertLessEqual(r.stats("b.deux")["distincts"], 5)


class BacOS(Banc):
    """L'enveloppe du système autour du processus d'EC (Linux). Ici, sans Linux : la logique de choix, l'échec fermé, l'absence de tombe."""

    def setUp(self):
        super().setUp()
        self._cache = dict(P._BAC)
        self.addCleanup(lambda: (P._BAC.clear(), P._BAC.update(self._cache)))

    def sans_bac(self):
        P._BAC.clear()
        P._BAC["choisi"] = ([], "aucun")

    def test_l_etat_d_un_ecran_n_eprouve_pas_le_bac(self):
        P._BAC.clear()
        self.assertEqual(self.svc._nom_bac(), "à éprouver")                                    # rien n'est lancé pour répondre à un écran
        self.assertNotIn("choisi", P._BAC)
        P.bac_os("auto")
        self.assertIn("choisi", P._BAC)
        self.assertNotEqual(self.svc._nom_bac(), "à éprouver")

    def test_un_mode_inconnu_est_refuse(self):
        with self.assertRaises(ValueError):
            P.bac_os("peut-etre")

    def test_auto_sans_bac_tourne_quand_meme_et_le_dit(self):
        self.sans_bac()
        self.assertEqual(P.bac_os("auto"), ([], "aucun"))
        self.assertEqual(P.bac_os("aucun"), ([], "aucun"))

    def test_requis_sans_bac_echoue_ferme(self):
        self.sans_bac()
        with self.assertRaises(P.BacIndisponible):
            P.bac_os("requis")
        with self.assertRaises(P.BacIndisponible):
            P._Travailleur(256, "requis")                                                       # rien n'est lancé

    def test_un_candidat_n_est_pas_juge_ni_grave_en_tombe_sans_le_bac_exige(self):
        self.sans_bac()
        self.ev.bac_os = "requis"
        r = self.ev.evaluer("essai", "doubler", RAPIDE, chrono=False)
        self.assertEqual(r["verdict"], "indisponible", r)
        self.assertEqual(self.evo.tombes("essai.doubler"), set())

    def test_une_ec_ne_sert_pas_sans_le_bac_exige_mais_sans_faute(self):
        self.sans_bac()
        d = self.tmp / "ec" / "essai" / "doubler"
        d.mkdir(parents=True)
        (d / "EC_doubler__EC1.py").write_text(TP.ec("def doubler(entree):\n    return {'y': 6, 'par': 'EC'}\n", version="EC1"), encoding="utf-8")
        (d / "ACTIVE").write_text("EC_doubler__EC1.py", encoding="utf-8")
        self.svc.router("essai", "doubler", "service", 100)
        self.svc.bac_os = "requis"
        self.svc._hotes_ec.clear()
        for _ in range(5):
            self.assertEqual(self.svc.appeler("essai", "doubler", {"x": 3}), {"y": 6})        # la référence (x * 2)
        e = self.svc.etat("essai", "doubler")
        self.assertEqual((e["fautes_recentes"], e["suspendue"], e["bac"]), (0, None, "indisponible"))

    def test_les_enveloppes_sont_construites_sans_rien_inventer(self):
        import shutil as sh
        vrai = sh.which
        sh.which = lambda n: "/usr/bin/" + n if n in ("bwrap", "unshare") else None
        try:
            noms = [n for n, _ in P._candidats_bac()]
            cmd = dict(P._candidats_bac())
        finally:
            sh.which = vrai
        self.assertEqual(noms, ["bwrap", "unshare"])                                            # la plus stricte d'abord
        self.assertIn("--unshare-all", cmd["bwrap"])                                           # réseau, pid, ipc, uts, utilisateur : tout
        self.assertIn("--die-with-parent", cmd["bwrap"])
        self.assertIn("--net", cmd["unshare"])
        self.assertIn("--kill-child", cmd["unshare"])                                          # tuer l'enveloppe tue le processus d'EC

    def test_le_tmp_vide_precede_les_dossiers_lies(self):
        """Trouvé sur Orion (Linux réel) : le /tmp vide posé APRÈS les liaisons recouvrait le code du travailleur quand il vivait sous /tmp ; il mourait sans un mot."""
        import shutil as sh
        vrai = sh.which
        sh.which = lambda n: "/usr/bin/" + n if n == "bwrap" else None
        try:
            cmd = dict(P._candidats_bac())["bwrap"]
        finally:
            sh.which = vrai
        self.assertIn("/tmp", cmd)
        self.assertLess(cmd.index("--tmpfs"), cmd.index("--ro-bind"))

    def test_un_bac_n_est_cru_qu_apres_avoir_fait_tourner_le_travailleur(self):
        """L'ancienne épreuve lançait `print(42)` : un bac qui cachait le travailleur la passait. Celle-ci charge une fonction dans le vrai travailleur."""
        self.assertTrue(P._bac_marche([]))                                                      # sans enveloppe, le travailleur répond
        self.assertFalse(P._bac_marche([sys.executable, "-c", "import sys; sys.exit(3)", "--"]))   # une enveloppe qui échoue ne passe pas

    @unittest.skipUnless(sys.platform.startswith("linux") and P.bac_os("auto")[1] != "aucun", "bac à sable Linux indisponible ici")
    def test_sous_linux_le_processus_d_ec_tourne_dans_le_bac(self):
        t = P._Travailleur(256, "requis")
        self.addCleanup(t.tuer)
        self.assertIn(t.bac, ("bwrap", "unshare"))
        self.assertTrue(t.echange({"op": "charger", "texte": "def f(x):\n    return {'a': 1}\n", "fonction": "f"}, 20)["ok"])
        self.assertEqual(t.echange({"op": "appeler", "entree": {}}, 10)["sortie"], {"a": 1})


class Comptes(unittest.TestCase):
    def setUp(self):
        import tempfile
        import shutil
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.r = R.Rejeu(self.tmp / "r.db")

    def test_une_entree_part_avec_le_compte_qui_l_a_produite(self):
        self.r.enregistrer("a.b", {"x": 1}, None, 1.0, compte="bea@x.fr")
        self.r.enregistrer("a.b", {"x": 2}, None, 1.0, compte="bea@x.fr")
        self.r.enregistrer("a.b", {"x": 2}, None, 1.0, compte="leo@x.fr")                      # partagée
        self.r.enregistrer("a.b", {"x": 3}, None, 1.0)                                          # le noyau : sans compte
        self.assertEqual(self.r.comptes("a.b"), {"bea@x.fr": 2, "leo@x.fr": 1})
        self.assertEqual(self.r.purger_compte("bea@x.fr"), {"rattachements": 2, "entrees": 1})  # {"x": 1} n'était qu'à elle
        self.assertEqual(sorted(c["entree"]["x"] for c in self.r.corpus("a.b")), [2, 3])         # la partagée et celle du noyau restent
        self.assertEqual(self.r.comptes("a.b"), {"leo@x.fr": 1})

    def test_les_cas_dores_ne_partent_jamais_avec_un_compte(self):
        self.r.importer("a.b", [{"entree": {"x": 9}}])
        self.r.enregistrer("a.b", {"x": 9}, None, 1.0, compte="bea@x.fr")
        self.r.purger_compte("bea@x.fr")
        self.assertEqual([c["entree"]["x"] for c in self.r.corpus("a.b")], [9])

    def test_un_point_exclu_ne_garde_que_sa_mesure(self):
        r = R.Rejeu(self.tmp / "e.db", exclus=R.EXCLUS_PRIVES)
        for i in range(4):
            r.enregistrer("courrier.corps", {"texte": "secret %d" % i}, None, 2.0, compte="bea@x.fr")
        self.assertEqual(r.corpus("courrier.corps"), [])                                        # aucun contenu
        s = r.stats("courrier.corps")
        self.assertEqual((s["appels"], s["duree_moyenne_ms"]), (4, 2.0))                        # mais le point reste ciblable (valeur = appels × durée)
        self.assertEqual(r.comptes(), {})

    def test_une_base_d_avant_les_comptes_se_met_a_niveau(self):
        import sqlite3
        c = sqlite3.connect(str(self.tmp / "vieux.db"))
        c.execute("CREATE TABLE appels(gid TEXT NOT NULL, h TEXT NOT NULL, entree TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 1, origine TEXT NOT NULL DEFAULT 'reel', reserve INTEGER NOT NULL, "
                  "premier REAL NOT NULL, dernier REAL NOT NULL, ms_somme REAL NOT NULL DEFAULT 0, ms_n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(gid, h))")
        c.commit()
        c.close()
        r = R.Rejeu(self.tmp / "vieux.db")
        r.enregistrer("a.b", {"x": 1}, None, 1.0, compte="bea@x.fr")
        self.assertEqual(r.purger_compte("bea@x.fr")["entrees"], 1)

    def test_le_service_transmet_le_compte_et_tolere_un_enregistreur_d_avant(self):
        import shutil
        import tempfile
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        mod = tmp / "modules" / "essai"
        (mod / "points").mkdir(parents=True)
        (mod / "contrats").mkdir()
        (mod / "points" / "EC_doubler.py").write_text(T.LENTE, encoding="utf-8")
        (mod / "contrats" / "CN_doubler.json").write_text(json.dumps(T.CONTRAT), encoding="utf-8")
        svc = P.ServicePoints(tmp / "ec")
        svc.declarer(types.SimpleNamespace(id="essai", points_evolution=(M.PointEvolution("doubler", "Double", "1.0", "points/EC_doubler", "doubler"),)), mod)
        vus = []
        svc.enregistreur = lambda gid, entree, sortie, ms, source, compte=None: vus.append(compte)
        svc.appeler("essai", "doubler", {"x": 1}, compte="bea@x.fr")
        svc.appeler("essai", "doubler", {"x": 2})
        self.assertEqual(vus, ["bea@x.fr", None])
        vieux = []
        svc.enregistreur = lambda gid, entree, sortie, ms, source: vieux.append(gid)           # sans paramètre compte
        svc.appeler("essai", "doubler", {"x": 3}, compte="bea@x.fr")
        self.assertEqual(vieux, ["essai.doubler"])


class Moteur(unittest.TestCase):
    def test_un_reglage_n_importe_pas_n_importe_quoi(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("cn_module_evolution", RACINE / "modules" / "evolution" / "CN_module.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        for bon in ("orfan.CN_orfan", "orfan.autre"):
            self.assertTrue(m._MOTEUR_PERMIS.match(bon), bon)
        for mauvais in ("os", "subprocess", "orfan", "orfan.", "orfan..x", "noyau.CN_points", "orfan.x; import os", "../orfan", "orfanx.CN"):
            self.assertFalse(m._MOTEUR_PERMIS.match(mauvais), mauvais)

    def test_ec_api_n_est_pas_une_dependance_permise(self):
        self.assertNotIn("ec_api", P.STDLIB_PURE)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Banc, Suspension, UneSeulePiece, EchecFerme, Preuves, Comparaison, Isolation, Sceau …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : noyau/CN_points.py, CN_evaluateur.py, CN_evolution.py, CN_rejeu.py, modules/evolution/CN_module.py (ce qu elles éprouvent).
