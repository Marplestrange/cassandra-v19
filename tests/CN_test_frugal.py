# ══════════════════════════════════════════════
# TITRE      : Bancs de Frugal
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #c431bd
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Prouve que Frugal ne dépense rien quand il n'y a rien à gagner, plafonne ses appels, affine sur la raison d'un échec et ne rend jamais une version non équivalente.
# MÉTHODE    : un modèle de banc scripté (aucune clé) derrière le vrai relais de la cage ; le moteur tourne dans son vrai processus.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c431bd ▼▼▼
"""Bancs de Frugal (orfan/CN_frugal.py)."""
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_moteurs as MO  # noqa: E402
from noyau.CN_points import DelaiEC  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import CN_test_evolution_module as TM  # noqa: E402

SOURCE = "def f(x):\n    t = 0\n    for v in x:\n        t = t + v * 2\n    return t\n"             # un point chaud, aucune règle gratuite n'y change rien
ENTREES = [list(range(3000)), list(range(2500)), list(range(2800))]
STRATEGIES = ("<STRATEGIE>\nFamille : somme native\nPortée : la boucle\nGain : le travail passe en C\nPlan : somme puis double\n</STRATEGIE>\n"
              "<STRATEGIE>\nFamille : formule fermée\nPortée : toute la fonction\nGain : plus de boucle\nPlan : calculer sans parcourir\n</STRATEGIE>")
BONNE = "```python\ndef f(x):\n    return sum(x) * 2\n```"
FAUSSE = "```python\ndef f(x):\n    return 0\n```"
LENTE = "```python\ndef f(x):\n    t = 0\n    for v in x:\n        t = t + v + v\n        t = t + 0\n    return t\n```"      # équivalente mais pas plus rapide
COPIE = "```python\n" + SOURCE + "```"      # la référence recopiée


def contexte(**kw):
    return dict({"point": "a.b", "source_reference": SOURCE, "fonction": "f", "contrat": {}, "entrees": ENTREES, "tombes": [], "budget": 3, "seuils": {}}, **kw)


class Banc:
    """Un modèle scripté : `reponses(role, prompt, n)` rend le texte ; tout appel est noté."""

    def __init__(self, reponses):
        self.reponses, self.appels = reponses, []

    def __call__(self, prompt, role):
        self.appels.append((role, prompt))
        return self.reponses(role, prompt, len(self.appels))


class Frugal(unittest.TestCase):
    def moteur(self, modele, **kw):
        return MO.MoteurProcessus("frugal", appeler_modele=modele, delai_s=kw.pop("delai_s", 90), **kw)

    def test_des_regles_suffisantes_ne_coutent_aucun_appel(self):
        banc = Banc(lambda r, p, n: self.fail("un modèle a été appelé"))
        m = self.moteur(banc)
        r = m.proposer(contexte(source_reference="def f(x):\n    return sorted(x)[0]\n", entrees=[list(range(2000, 0, -1)), list(range(3000, 100, -3)), [5, 3, 9] * 400]))
        self.assertTrue(r)
        self.assertEqual(r[0]["origine"], "frugal")
        self.assertEqual((m.stats["appels_modele"], banc.appels), (0, []))

    def test_sans_point_chaud_et_sans_regle_il_ne_depense_rien(self):
        banc = Banc(lambda r, p, n: self.fail("un modèle a été appelé"))
        m = self.moteur(banc)
        self.assertEqual(m.proposer(contexte(source_reference="def f(x):\n    return x\n", entrees=[[1], [2]])), [])
        self.assertEqual(m.stats["appels_modele"], 0)

    def test_le_fort_propose_en_texte_l_econome_ecrit_et_le_prouve_est_rendu(self):
        def reponses(role, prompt, n):
            if role == "strategie":
                self.assertNotIn("```python\ndef f", prompt.split("Propose")[1])                  # la demande de stratégie ne réclame pas de code
                return STRATEGIES
            return BONNE
        banc = Banc(reponses)
        r = self.moteur(banc).proposer(contexte())
        self.assertEqual([a[0] for a in banc.appels][:2], ["strategie", "executant"])
        self.assertEqual(len(r), 1)                                                              # les deux stratégies ont été écrites, toutes deux prouvées : même texte, rendu une fois
        self.assertIn("sum(x)", r[0]["texte"])
        self.assertIn("stratégie", r[0]["hypothese"])

    def test_une_strategie_fausse_est_affinee_avec_sa_raison(self):
        def reponses(role, prompt, n):
            if role == "strategie":
                return STRATEGIES
            return BONNE if "Problème constaté" in prompt else FAUSSE
        banc = Banc(reponses)
        r = self.moteur(banc).proposer(contexte())
        roles = [a[0] for a in banc.appels]
        self.assertEqual(roles, ["strategie", "executant", "executant", "executant"])           # fort, 2 stratégies écrites fausses, 1 affinage réussi : on s'arrête là
        affinage = banc.appels[3][1]
        self.assertIn("entrée visible n°1", affinage)                                            # la raison de l'échec est renvoyée au modèle économe
        self.assertIn("return 0", affinage)                                                      # avec sa version précédente
        self.assertEqual(len(r), 1)
        self.assertIn("sum(x)", r[0]["texte"])

    def test_une_version_equivalente_mais_lente_est_renvoyee_pour_affinage(self):
        def reponses(role, prompt, n):
            if role == "strategie":
                return STRATEGIES.split("</STRATEGIE>")[0] + "</STRATEGIE>"
            return BONNE if "pas plus rapide" in prompt else LENTE
        banc = Banc(reponses)
        r = self.moteur(banc).proposer(contexte())
        self.assertEqual(len(banc.appels), 3)
        self.assertEqual(len(r), 1)

    def test_le_plafond_d_appels_du_relais_est_respecte(self):
        banc = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else FAUSSE)
        m = self.moteur(banc, max_appels=3)
        self.assertEqual(m.proposer(contexte()), [])
        self.assertEqual(m.stats["appels_modele"], 3)
        self.assertEqual(len(banc.appels), 3)

    def test_le_budget_propre_du_moteur_borne_aussi_les_appels(self):
        banc = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else FAUSSE)
        self.assertEqual(self.moteur(banc).proposer(contexte()), [])
        self.assertLessEqual(len(banc.appels), 6)                                                # 1 fort + 2 stratégies + 2 tours d'affinage : jamais au-delà du plafond de 6

    def test_une_version_non_equivalente_n_est_jamais_rendue(self):
        for reponse in (FAUSSE, LENTE, COPIE, "```python\ndef f(x:\n```", "pas de code du tout", "```python\ndef g(x):\n    return 1\n```"):
            banc = Banc(lambda r, p, n, rep=reponse: STRATEGIES if r == "strategie" else rep)
            self.assertEqual(self.moteur(banc).proposer(contexte()), [], reponse)

    def test_un_modele_fort_muet_laisse_une_tentative_sans_strategie(self):
        def reponses(role, prompt, n):
            if role == "strategie":
                raise RuntimeError("quota")
            return BONNE
        banc = Banc(reponses)
        r = self.moteur(banc).proposer(contexte())
        self.assertEqual(len(r), 1)
        self.assertEqual([a[0] for a in banc.appels], ["strategie", "executant"])

    def test_un_fort_sans_balises_vaut_une_strategie(self):
        banc = Banc(lambda r, p, n: "Remplace la boucle par une somme native puis double le tout." if r == "strategie" else BONNE)
        r = self.moteur(banc).proposer(contexte())
        self.assertEqual(len(banc.appels), 2)
        self.assertEqual(len(r), 1)

    def test_aucun_modele_branche_ne_depense_rien(self):
        self.assertEqual(MO.MoteurProcessus("frugal", delai_s=90).proposer(contexte()), [])

    def test_le_delai_tue_le_moteur(self):
        def lent(role, prompt, n):
            time.sleep(10)
            return STRATEGIES
        with self.assertRaises(DelaiEC):
            self.moteur(Banc(lent), delai_s=8).proposer(contexte())

    def test_une_boucle_repartie_sur_plusieurs_lignes_est_un_point_chaud(self):
        src = "def f(x):" + chr(10) + "    r = {}" + chr(10) + "    for v in x:" + chr(10) + "        if v in r:" + chr(10) + "            r[v] = r[v] + 1" + chr(10) + "        else:" + chr(10) + "            r[v] = 1" + chr(10) + "    return r" + chr(10)
        bon = "```python" + chr(10) + "from collections import Counter" + chr(10) + "def f(x):" + chr(10) + "    return dict(Counter(x))" + chr(10) + "```"
        banc = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else bon)
        r = self.moteur(banc).proposer(contexte(source_reference=src, entrees=[[i % 37 for i in range(5000)], [i % 11 for i in range(4000)]]))
        self.assertTrue(r and "Counter" in r[0]["texte"])                                       # aucune ligne n'a 40 %, la boucle entière en a 99

    def test_un_module_hors_bibliotheque_standard_ou_hors_fonction_pure_est_refuse(self):
        for imp in ("import numpy as np", "import multiprocessing", "from os import path", "import ctypes"):
            rep = "```python" + chr(10) + imp + chr(10) + "def f(x):" + chr(10) + "    return sum(x) * 2" + chr(10) + "```"
            banc = Banc(lambda r, p, n, rep=rep: STRATEGIES if r == "strategie" else rep)
            self.assertEqual(self.moteur(banc, options={"tours": 0}).proposer(contexte()), [], imp)
        ok = "```python" + chr(10) + "import functools" + chr(10) + "def f(x):" + chr(10) + "    return sum(x) * 2" + chr(10) + "```"
        self.assertTrue(self.moteur(Banc(lambda r, p, n: STRATEGIES if r == "strategie" else ok)).proposer(contexte()))

    def test_une_reponse_vide_de_la_passerelle_n_est_pas_une_strategie(self):
        for vide in ("(empty response)[skill result: memory_search]", "ok", ""):
            banc = Banc(lambda r, p, n, vide=vide: vide if r == "strategie" else BONNE)
            self.moteur(banc).proposer(contexte())
            self.assertNotIn("empty response", "".join(p for _, p in banc.appels[1:]))      # le bruit n'est pas recopié comme plan chez l'exécutant

    def test_la_garde_de_duree_juge_chaque_role_a_son_propre_pas(self):
        from orfan import CN_frugal as F, CN_orfan as O
        def modele(prompt, role):
            time.sleep(2 if role == "strategie" else 0.1)
            return STRATEGIES if role == "strategie" else BONNE
        m = F.MoteurFrugal(O, appeler_modele=modele, duree_max_s=3.5)
        self.assertTrue(m.proposer(contexte()))                      # le fort a pris 2 s : l'exécutant (0,1 s) reste permis, il ne doit pas hériter du pas du fort
        appels = []
        def lent(prompt, role):
            appels.append(role)
            time.sleep(2)
            return STRATEGIES if role == "strategie" else FAUSSE
        F.MoteurFrugal(O, appeler_modele=lent, duree_max_s=5).proposer(contexte())
        self.assertLessEqual(len(appels), 3)                         # 2 s par appel, 5 s en tout : un appel de plus ne tiendrait pas

    def test_le_delai_qui_tombe_apres_une_preuve_ne_la_jette_pas(self):
        def reponses(role, prompt, n):
            if role == "strategie":
                return STRATEGIES
            if n == 2:
                return BONNE
            time.sleep(9)                                            # le deuxième exécutant est trop lent : le délai (6 s) tombe pendant son appel
            return BONNE
        m = self.moteur(Banc(reponses), delai_s=6)
        r = m.proposer(contexte())
        self.assertTrue(r and "sum(x)" in r[0]["texte"])             # la première preuve est rendue au lieu de DelaiEC
        self.assertEqual(m.stats.get("delai_partiel"), 1)

    def test_un_point_chaud_mais_minuscule_ne_depense_rien(self):
        src = "def f(x):" + chr(10) + "    t = 0" + chr(10) + "    for v in x:" + chr(10) + "        t = t + v * 2" + chr(10) + "    return t" + chr(10)
        banc = Banc(lambda r, p, n: self.fail("un modèle a été appelé pour une fonction de quelques microsecondes"))
        r = self.moteur(banc).proposer(contexte(source_reference=src, entrees=[list(range(60)), list(range(80))]))
        self.assertEqual(r, [])                                        # 60 passages de boucle : chaud à 90 %, mais quelques µs en tout

    def test_les_reglages_de_l_admin_changent_le_budget_et_restent_bornes(self):
        banc = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else FAUSSE)
        self.moteur(banc, options={"strategies": 1, "tours": 0, "appels_max": 6}).proposer(contexte())
        self.assertEqual([a[0] for a in banc.appels], ["strategie", "executant"])                # une idée demandée, pas d'affinage
        self.assertIn("1 stratégies", banc.appels[0][1])
        banc = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else FAUSSE)
        self.moteur(banc, options={"strategies": 99, "tours": 99, "appels_max": 99}).proposer(contexte())
        self.assertLessEqual(len(banc.appels), 6)                                                # jamais au-delà des bornes du moteur
        banc = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else FAUSSE)
        self.moteur(banc, options={"strategies": "n'importe quoi", "appels_max": 3}).proposer(contexte())
        self.assertEqual(len(banc.appels), 3)                                                    # une valeur illisible est ignorée, les autres tiennent

    def test_le_fort_apprend_ce_que_le_juge_recompense(self):
        banc = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else FAUSSE)
        self.moteur(banc).proposer(contexte(seuils={"gain_min_pct": 5.0, "objectifs": {"latence": 1.0, "memoire": 0.5, "taille": 0.0}}))
        self.assertIn("au moins 5.0 %", banc.appels[0][1])
        self.assertIn("memoire 0.5", banc.appels[0][1])
        self.assertNotIn("taille", banc.appels[0][1].split("Le juge")[1].split("Propose")[0])


class Memoire(unittest.TestCase):
    """Le carnet des idées essayées : sur le disque, d'un appel à l'autre."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reg = MO.Registre(Path(self.tmp.name) / "moteurs.json")

    def tearDown(self):
        self.tmp.cleanup()

    def moteur(self, modele):
        return MO.MoteurProcessus("frugal", appeler_modele=modele, delai_s=90, carnet=self.reg)

    def test_une_idee_ratee_est_inscrite_sur_le_disque_puis_dite_au_fort_et_jamais_reecrite(self):
        banc1 = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else FAUSSE)
        self.moteur(banc1).proposer(contexte())
        fiches = MO.Registre(Path(self.tmp.name) / "moteurs.json").fiches("a.b")                   # relu depuis le fichier : rien ne vit en mémoire vive
        self.assertEqual({f["famille"] for f in fiches}, {"somme native", "formule fermée"})
        self.assertTrue(all(f["issue"] == "fausse" and "entrée visible" in f["detail"] for f in fiches))
        banc2 = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else self.fail("une famille déjà ratée a été réécrite"))
        r = self.moteur(banc2).proposer(contexte())
        self.assertEqual(r, [])
        self.assertEqual([a[0] for a in banc2.appels], ["strategie"])                              # le fort a redit les mêmes familles : zéro appel de plus
        self.assertIn("DÉJÀ essayées", banc2.appels[0][1])
        self.assertIn("somme native", banc2.appels[0][1])

    def test_une_idee_prouvee_est_inscrite_avec_son_gain(self):
        self.moteur(Banc(lambda r, p, n: STRATEGIES if r == "strategie" else BONNE)).proposer(contexte())
        f = {x["famille"]: x for x in self.reg.fiches("a.b")}
        self.assertEqual(f["somme native"]["issue"], "prouvee")
        self.assertGreater(f["somme native"]["rapport"], 1.0)

    def test_la_memoire_est_propre_a_chaque_point(self):
        self.moteur(Banc(lambda r, p, n: STRATEGIES if r == "strategie" else FAUSSE)).proposer(contexte())
        self.assertEqual(self.reg.fiches("autre.point"), [])

    def test_le_carnet_nettoie_ce_que_dit_un_moteur_et_reste_petit(self):
        n = self.reg.noter_fiches("p", [{"famille": "x" * 500, "issue": "fausse", "detail": "d" * 900, "rapport": "n'importe quoi"}, {"famille": "y", "issue": "inventee"}, "texte", {"famille": "", "issue": "fausse"}])
        self.assertEqual(n, 1)
        f = self.reg.fiches("p")[0]
        self.assertEqual((len(f["famille"]), len(f["detail"]), f["rapport"]), (80, 200, 0.0))
        for i in range(40):
            self.reg.noter_fiches("p", [{"famille": "idée %d" % i, "issue": "lente"}])
        self.assertEqual(len(self.reg.fiches("p")), MO.Registre.FICHES_PAR_POINT)
        self.reg.noter_fiches("p", [{"famille": "IDÉE 39", "issue": "prouvee", "rapport": 2}])        # une même famille n'a qu'une fiche : la dernière
        self.assertEqual(len([x for x in self.reg.fiches("p") if x["famille"].lower() == "idée 39"]), 1)

    def test_le_verdict_du_juge_remplace_le_prouve_sur_le_vu_dans_le_carnet(self):
        from noyau.CN_evolution import empreinte_ast
        m = self.moteur(Banc(lambda r, p, n: STRATEGIES if r == "strategie" else BONNE))
        rendus = m.proposer(contexte())
        fam = rendus[0]["famille"]                                                               # deux stratégies, même code : une seule variante rendue, sous la famille du meilleur rapport
        self.assertIn(fam, ("somme native", "formule fermée"))
        h = empreinte_ast(rendus[0]["texte"])
        m.verdicts("a.b", [{"ast": h, "verdict": "equivalente", "gain_pct": 4.0, "retenu": False}, {"ast": "inconnu", "verdict": "divergente", "retenu": False}])
        f = {x["famille"]: x for x in self.reg.fiches("a.b")}
        self.assertEqual(f[fam]["issue"], "refusee")                                 # prouvée sur le vu, refusée par le juge : le carnet le sait
        self.assertIn("gain insuffisant", f[fam]["detail"])
        m.verdicts("a.b", [{"ast": h, "verdict": "equivalente", "gain_pct": 31.0, "retenu": True}])
        self.assertEqual({x["famille"]: x["issue"] for x in self.reg.fiches("a.b")}[fam], "retenue")

    def test_une_famille_refusee_par_le_juge_n_est_pas_reecrite(self):
        self.reg.noter_fiches("a.b", [{"famille": "somme native", "issue": "refusee", "detail": "le juge l'a refusée"}, {"famille": "formule fermée", "issue": "refusee"}])
        banc = Banc(lambda r, p, n: STRATEGIES if r == "strategie" else self.fail("réécrite"))
        self.assertEqual(self.moteur(banc).proposer(contexte()), [])
        self.assertEqual(len(banc.appels), 1)

    def test_apres_six_echecs_de_suite_le_fort_doit_changer_de_famille(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("frugal", str(RACINE / "orfan" / "CN_frugal.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fiches = [{"famille": "f%d" % i, "issue": "fausse", "detail": "", "rapport": 0} for i in range(6)]
        self.assertIn("ABSENTE", mod.MoteurFrugal(None)._memoire_texte(fiches))
        self.assertNotIn("ABSENTE", mod.MoteurFrugal(None)._memoire_texte(fiches[:5]))
        self.assertNotIn("ABSENTE", mod.MoteurFrugal(None)._memoire_texte(fiches + [{"famille": "ok", "issue": "prouvee", "detail": "", "rapport": 2}]))


class RappelDuJuge(TM.Banc):
    """Le noyau dit au moteur ce que le juge a décidé, sans que cela change le jugement."""
    VRAIE = "def somme_min(entree):\n    v = entree['v']\n    return {'y': min(v) + sum(x % 7 for x in v)}\n"

    def test_le_juge_rapporte_ses_verdicts_au_moteur_et_une_panne_du_carnet_ne_change_rien(self):
        recus = []

        class Moteur:
            nom = "banc"

            def __init__(self, casse=False):
                self.casse = casse

            def proposer(self, contexte):
                return [{"texte": RappelDuJuge.VRAIE, "hypothese": "min", "famille": "min natif"}]

            def verdicts(self, gid, essais):
                recus.append((gid, essais))
                if self.casse:
                    raise RuntimeError("carnet en panne")
        ok = self.n.evolution.proposer("labo", "somme_min", Moteur(), 3)
        sans = self.n.evolution.proposer("labo", "somme_min", Moteur(casse=True), 3)
        self.assertEqual(recus[0][0], "labo.somme_min")
        e = recus[0][1][0]
        self.assertTrue(e["ast"] and "retenu" in e and "verdict" in e)
        self.assertEqual(len(recus), 2)
        self.assertEqual(ok["ok"], sans["ok"])
        self.assertIn("ok", sans)                                                               # la panne du carnet n'a pas fait lever le jugement


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant.
# CN : un banc par promesse de Frugal : zéro dépense sans gain possible, plafonds tenus, affinage sur raison, rien de faux rendu.
# LIEN : orfan/CN_frugal.py, noyau/CN_moteurs.py, docs/CN_FRUGALEVO.md.
