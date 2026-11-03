# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La tuile (`groupe`) et le responsable (`proprietaire`) d'un module se déclarent au manifes
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #876f46
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La tuile (`groupe`) et le responsable (`proprietaire`) d'un module se déclarent au manifeste. La page d'accueil d'une tuile en dépend : rangés par la famille, `sauvegardes` et `mandats` tombaient hors de la tuile que la décision du 18-10 le
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=876f46 ▼▼▼
"""La tuile (`groupe`) et le responsable (`proprietaire`) d'un module se déclarent au manifeste. La page d'accueil d'une tuile en dépend : rangés par la famille,
`sauvegardes` et `mandats` tombaient hors de la tuile que la décision du 18-10 leur donne."""
import copy
import importlib.util
import sys
import tomllib
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_manifeste as M  # noqa: E402


def groupes_de_laffichage():
    spec = importlib.util.spec_from_file_location("ec_disposition", RACINE / "modules" / "affichage" / "points" / "EC_disposition.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return {g[0] for g in mod.GROUPES}


def manifestes():
    for f in sorted((RACINE / "modules").glob("*/CN_manifeste.toml")):
        yield f, tomllib.loads(f.read_text(encoding="utf-8"))


class GroupeDeclare(unittest.TestCase):
    def test_chaque_module_livre_declare_une_tuile_que_l_affichage_connait(self):
        connus, sans, inconnus = groupes_de_laffichage(), [], []
        for f, d in manifestes():
            g = d["module"].get("groupe")
            if not g:
                sans.append(d["module"]["id"])
            elif g not in connus:
                inconnus.append((d["module"]["id"], g))
        self.assertEqual(sans, [], "modules sans tuile : %s" % sans)
        self.assertEqual(inconnus, [], "tuiles que l'affichage ne connaît pas : %s" % inconnus)

    def test_la_decision_du_18_10_est_tenue(self):
        tuile = {d["module"]["id"]: d["module"].get("groupe") for f, d in manifestes()}
        self.assertEqual(tuile["sauvegardes"], "secu")           # la famille « supervision » la rangeait en Observatoire
        self.assertEqual(tuile["mandats"], "auto")               # la famille « echanges » les rangeait dans Desk
        self.assertEqual(tuile["droits"], "parametres")          # ses écrans vivent dans ceux des comptes
        self.assertEqual(tuile["bibliotheque"], "bibliotheque")  # la tuile d'Amizo : son module y est seul

    def test_chaque_module_a_un_proprietaire_qui_est_un_agent_et_les_tuiles_tiennent_le_leur(self):
        agents = {"cassandra", "itare", "amizo"}
        attendu = {"desk": "itare", "metier": "itare", "bibliotheque": "amizo", "parc": "cassandra", "secu": "cassandra", "obs": "cassandra", "auto": "cassandra", "parametres": "cassandra"}
        ecarts = []
        for f, d in manifestes():
            m = d["module"]
            self.assertIn(m.get("proprietaire"), agents, m["id"])
            if m["proprietaire"] != attendu[m["groupe"]]:
                ecarts.append((m["id"], m["groupe"], m["proprietaire"]))
        self.assertEqual(ecarts, [], "modules dont le responsable n'est pas celui de leur tuile : %s" % ecarts)

    def test_le_validateur_accepte_une_tuile_et_un_responsable_et_refuse_le_reste(self):
        f, d = next(iter(manifestes()))
        bon = copy.deepcopy(d)
        bon["module"]["groupe"], bon["module"]["proprietaire"] = "parc", "drisse"
        self.assertEqual([e for e in M.valider(bon) if "groupe" in e or "proprietaire" in e], [])
        for champ, valeur in (("groupe", "Parc"), ("groupe", "p"), ("groupe", "x" * 22), ("groupe", 3),
                              ("proprietaire", "  "), ("proprietaire", "x" * 81), ("proprietaire", 7)):
            mauvais = copy.deepcopy(d)
            mauvais["module"][champ] = valeur
            self.assertTrue(any(champ in e for e in M.valider(mauvais)), (champ, valeur))

    def test_le_manifeste_construit_porte_les_deux_champs_et_les_menus_heritent_de_la_tuile(self):
        f, d = next((f, d) for f, d in manifestes() if d["module"]["id"] == "certificats")
        m = M.charger(f)
        self.assertEqual(m.groupe, "secu")
        self.assertEqual(m.proprietaire, "cassandra")
        spec = importlib.util.spec_from_file_location("menus_module", RACINE / "modules" / "menus" / "CN_module.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        plat = mod.construire_plat([m])
        self.assertTrue(plat)
        self.assertEqual({e["groupe"] for e in plat}, {"secu"})


class TuileBibliotheque(unittest.TestCase):
    def test_la_tuile_paraît_entre_metier_et_parc_avec_l_entree_du_module_et_la_barre_tient_a_9(self):
        def charger(nom, chemin):
            spec = importlib.util.spec_from_file_location(nom, RACINE / chemin)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        D = charger("ec_disposition", "modules/affichage/points/EC_disposition.py")
        menus = charger("menus_module", "modules/menus/CN_module.py")
        ordre = [g[0] for g in sorted(D.GROUPES, key=lambda g: g[3])]
        self.assertEqual(ordre[ordre.index("metier") + 1:ordre.index("parc")], ["bibliotheque"])
        self.assertGreaterEqual(D.MAX_GROUPES, len(D.GROUPES))
        plat = menus.construire_plat([M.charger(RACINE / "modules" / "bibliotheque" / "CN_manifeste.toml")])
        v = D.disposition(plat, ["bibliotheque"], {}, {})
        self.assertEqual([g["id"] for g in v["groupes"]], ["bibliotheque"])
        self.assertEqual([e["libelle"] for e in v["groupes"][0]["entrees"]], ["Bibliothèque"])
        self.assertEqual(v["orphelines"], [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : groupes_de_laffichage, manifestes, GroupeDeclare
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
