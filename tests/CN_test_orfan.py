# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs d'Orfan v1
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #d9b556
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs d'Orfan v1 : le profil, les optimisations déterministes (équivalentes, une règle à la fois), le moteur à modèle, et la chaîne complète avec le noyau.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d9b556 ▼▼▼
"""Bancs d'Orfan v1 : le profil, les optimisations déterministes (équivalentes, une règle à la fois), le moteur à modèle, et la chaîne complète avec le noyau."""
import json
import shutil
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
from orfan import CN_orfan as O  # noqa: E402

BOUCLE = ("def f(entree):\n"
          "    total = 0\n"
          "    for i in range(50):\n"
          "        total += i * entree['x']\n"
          "    return {'y': total}\n")


def executer(source, fonction, entree):
    ns = {}
    exec(compile(source, "<essai>", "exec"), ns)
    return ns[fonction](json.loads(json.dumps(entree)))


class Profil(unittest.TestCase):
    def test_la_ligne_la_plus_executee_est_designee(self):
        chauds = O.profil(BOUCLE, "f", [{"x": 1}, {"x": 2}, {"x": 3}])
        self.assertEqual({c["ligne"] for c in chauds[:2]}, {3, 4})               # la boucle : son en-tête (une exécution de plus que le corps) et son corps
        self.assertTrue(any("total += i * entree['x']" in c["texte"] for c in chauds[:2]))
        self.assertGreater(chauds[0]["part_pct"], 30)
        self.assertGreater(chauds[0]["part_pct"] + chauds[1]["part_pct"], 90)    # à elle seule, la boucle fait presque tout le travail

    def test_une_entree_qui_plante_ne_casse_pas_le_profil(self):
        self.assertTrue(O.profil(BOUCLE, "f", [{"mauvais": 1}, {"x": 2}]))

    def test_sans_entree_pas_de_profil(self):
        self.assertEqual(O.profil(BOUCLE, "f", []), [])


class Optimisations(unittest.TestCase):
    CAS = {
        "liste intermédiaire inutile": ("def f(e):\n    return {'y': any([v > 100 for v in e['v']]), 's': sum([v * 2 for v in e['v']])}\n", {"v": [1, 5, 200, 3]}),
        "tri pour un extremum": ("def f(e):\n    return {'a': sorted(e['v'])[0], 'b': sorted(e['v'])[-1]}\n", {"v": [5, 2, 9, 1]}),
        "test de vide par la longueur": ("def f(e):\n    return {'vide': len(e['v']) == 0, 'plein': len(e['v']) > 0}\n", {"v": []}),
        "list(générateur)": ("def f(e):\n    return {'y': list(v + 1 for v in e['v'])}\n", {"v": [1, 2, 3]}),
        "constructeurs vides": ("def f(e):\n    d = dict()\n    l = list()\n    d['a'] = l\n    return d\n", {"v": []}),
    }

    def test_chaque_regle_s_applique_et_rend_le_meme_resultat(self):
        for nom, (source, entree) in self.CAS.items():
            variantes = [v for v in O.optimisations(source) if v["hypothese"].startswith(nom)]
            self.assertEqual(len(variantes), 1, nom)
            v = variantes[0]
            self.assertNotEqual(v["texte"].strip(), source.strip(), nom)
            self.assertEqual(executer(v["texte"], "f", entree), executer(source, "f", entree), nom)         # équivalente
            self.assertTrue(v["hypothese"] and v["origine"] == "regle")

    def test_une_regle_ne_s_applique_pas_a_ce_qu_elle_ne_comprend_pas(self):
        source = "def f(e):\n    return {'a': sorted(e['v'], key=lambda x: -x)[0], 'b': sorted(e['v'])[1]}\n"
        self.assertEqual(O.optimisations(source), [])                             # une clé de tri, ou un autre indice : pas un extremum

    def test_une_fonction_deja_nette_ne_donne_rien(self):
        self.assertEqual(O.MoteurDeterministe().proposer({"source_reference": BOUCLE}), [])

    def test_une_regle_a_la_fois(self):
        source = self.CAS["liste intermédiaire inutile"][0] + "\n\ndef g(e):\n    return sorted(e['v'])[0]\n"
        noms = [v["hypothese"].split(" : ")[0] for v in O.optimisations(source)]
        self.assertEqual(sorted(noms), ["liste intermédiaire inutile", "tri pour un extremum"])


class Modele(unittest.TestCase):
    CONTEXTE = {"point": "m.p", "source_reference": BOUCLE, "fonction": "f", "contrat": {"sortie": {"type": "object", "required": ["y"]}},
                "entrees": [{"x": 1}, {"x": 2}], "tombes": ["a", "b"], "budget": 1, "seuils": {}}

    def test_le_prompt_porte_la_fonction_le_profil_le_contrat_et_les_tombes(self):
        p = O.construire_prompt(self.CONTEXTE, O.profil(BOUCLE, "f", self.CONTEXTE["entrees"]))
        self.assertIn("def f(entree)", p)
        self.assertIn("ligne 4", p)
        self.assertIn('"required": ["y"]', p)
        self.assertIn("2 variante(s) ont DÉJÀ échoué", p)
        self.assertIn("bibliothèque standard pure", p)

    def test_les_blocs_de_code_sont_extraits_avec_leur_hypothese(self):
        reponse = "Je sors le produit de la boucle.\n```python\ndef f(entree):\n    return {'y': 1225 * entree['x']}\n```\nvoilà"
        b = O.extraire_blocs(reponse)
        self.assertEqual(len(b), 1)
        self.assertIn("return {'y': 1225", b[0]["texte"])
        self.assertIn("produit de la boucle", b[0]["hypothese"])
        self.assertEqual(O.extraire_blocs("pas de code ici"), [])

    def test_le_moteur_a_modele_appelle_le_modele_avec_le_profil(self):
        vus = []
        m = O.MoteurModele(lambda prompt: vus.append(prompt) or "idée\n```python\ndef f(entree):\n    return {'y': 1}\n```")
        r = m.proposer(self.CONTEXTE)
        self.assertEqual(len(r), 1)
        self.assertIn("ligne 4", vus[0])

    def test_le_stratege_decide_puis_l_executant_ecrit(self):
        appels = []
        m = O.MoteurModele(lambda p: appels.append(("executant", p)) or "```python\ndef f(entree):\n    return {'y': 1}\n```",
                           lambda p: appels.append(("stratege", p)) or "Sortir la somme de la boucle : somme des i = 1225.")
        m.proposer(self.CONTEXTE)
        self.assertEqual([a[0] for a in appels], ["stratege", "executant"])
        self.assertIn("1225", appels[1][1])                                       # l'exécutant reçoit la stratégie
        self.assertIn("Ne rends PAS de code", appels[0][1])

    def test_un_profil_qui_echoue_ne_bloque_pas_le_modele(self):
        casse = dict(self.CONTEXTE, source_reference="def f(entree):\n    return {'y': 1}\n", fonction="inexistante")
        r = O.MoteurModele(lambda p: "```python\ndef f(entree):\n    return {'y': 2}\n```").proposer(casse)
        self.assertEqual(len(r), 1)

    def test_la_composition_ecarte_les_doublons_et_garde_l_ordre_gratuit_d_abord(self):
        double = {"texte": "def f(e):\n    return {'y': any([v for v in e['v']])}\n"}
        libre = O.MoteurDeterministe()
        modele = O.MoteurModele(lambda p: "```python\ndef f(e):\n    return {'y': any(v for v in e['v'])}\n```")           # même arbre que la variante déterministe
        ctx = dict(self.CONTEXTE, source_reference=double["texte"], fonction="f", entrees=[{"v": [0, 1]}])
        r = O.MoteurComposite(libre, modele).proposer(ctx)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["origine"], "regle")


class AvecLeNoyau(unittest.TestCase):
    """La chaîne complète : Orfan propose, le noyau juge, écrit, met en ombre."""

    REF = ("def somme_min(entree):\n"
           "    v = entree['v']\n"
           "    return {'y': sorted(v)[0] + sum([x % 7 for x in v])}\n")
    CONTRAT = {"entree": {"type": "object", "required": ["v"], "properties": {"v": {"type": "array"}}},
               "sortie": {"type": "object", "required": ["y"], "properties": {"y": {"type": "integer"}}}}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        mod = self.tmp / "modules" / "essai"
        (mod / "points").mkdir(parents=True)
        (mod / "contrats").mkdir()
        (mod / "points" / "EC_somme_min.py").write_text(self.REF, encoding="utf-8")
        (mod / "contrats" / "CN_somme_min.json").write_text(json.dumps(self.CONTRAT), encoding="utf-8")
        self.svc = P.ServicePoints(self.tmp / "ec")
        self.svc.declarer(types.SimpleNamespace(id="essai", points_evolution=(M.PointEvolution("somme_min", "Somme", "1.0", "points/EC_somme_min", "somme_min"),)), mod)
        self.rejeu = R.Rejeu(self.tmp / "rejeu.db")
        for i in range(50):                                                      # des listes de 400 éléments, différentes à chaque fois
            self.rejeu.enregistrer("essai.somme_min", {"v": [(j * 37 + i * 11) % 1009 for j in range(400)]}, None, 0.2)
        self.evo = E.Evolution(self.svc, self.rejeu, EV.Evaluateur(self.svc, self.rejeu, minimum=20), self.tmp / "evolution.db", seuils={"pieges_min": 0.3})

    def test_orfan_deterministe_trouve_un_gain_reel_que_le_noyau_prouve(self):
        r = self.evo.proposer("essai", "somme_min", O.MoteurDeterministe())
        self.assertTrue(r["ok"], r)
        self.assertGreater(r["piece"]["gain_annonce_pct"], 5)
        self.assertEqual(r["piece"]["etat"], "ombre")
        texte = (self.tmp / "ec" / "essai" / "somme_min" / "EC_somme_min__EC1.py").read_text(encoding="utf-8")
        self.assertIn("min(", texte)                                              # le tri a été remplacé par un parcours
        self.assertEqual(P.analyser_purete(texte), [])

    def test_une_proposition_fausse_du_modele_est_rejetee_par_le_noyau(self):
        faux = O.MoteurModele(lambda p: "j'essaie\n```python\ndef somme_min(entree):\n    return {'y': 0}\n```")
        r = self.evo.proposer("essai", "somme_min", faux)
        self.assertFalse(r["ok"])
        self.assertEqual(r["essais"][0]["verdict"], "divergente")
        self.assertFalse((self.tmp / "ec" / "essai" / "somme_min" / "ACTIVE").exists())     # rien n'a été écrit : un modèle qui se trompe ne coûte qu'un essai

    def test_le_moteur_voit_la_partition_visible_et_les_tombes(self):
        vus = {}
        class Espion:
            def proposer(self, ctx):
                vus.update(ctx)
                return []
        self.evo.proposer("essai", "somme_min", Espion())
        reserves = {c["h"] for c in self.rejeu.corpus("essai.somme_min", "reserve")}
        self.assertEqual({R.empreinte(e) for e in vus["entrees"]} & reserves, set())
        self.assertIn("def somme_min", vus["source_reference"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : executer, Profil, Optimisations, Modele, AvecLeNoyau
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
