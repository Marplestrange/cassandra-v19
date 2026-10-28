# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module Évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #a8a2f2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module Évolution : ses capacités dans un vrai noyau, avec un module « labo » qui déclare un point d'évolution et un faux module « modeles ».
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a8a2f2 ▼▼▼
"""Bancs du module Évolution : ses capacités dans un vrai noyau, avec un module « labo » qui déclare un point d'évolution et un faux module « modeles »."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur  # noqa: E402

ADMIN, SIMPLE = "root@x.fr", "bea@x.fr"
REF = "def somme_min(entree):\n    v = entree['v']\n    return {'y': sorted(v)[0] + sum([x % 7 for x in v])}\n"
CONTRAT = {"entree": {"type": "object", "required": ["v"], "properties": {"v": {"type": "array"}}},
           "sortie": {"type": "object", "required": ["y"], "properties": {"y": {"type": "integer"}}}}
LABO = '''[module]
id = "labo"
nom = "Labo"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Un module d'essai qui déclare un point d'évolution"
confiance = "interne"

[[droits]]
id = "utiliser"
libelle = "Utiliser le module d'essai"
defaut = true

[[capacites]]
id = "ping"
libelle = "ping"
risque = "lecture"

[[points_evolution]]
id = "somme_min"
libelle = "Somme et minimum"
contrat = "1.0"
reference = "points/EC_somme_min"
fonction = "somme_min"
'''
MODELES = '''[module]
id = "modeles"
nom = "Faux modèles"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Pour les bancs"
confiance = "interne"

[[droits]]
id = "utiliser"
libelle = "Utiliser le module d'essai"
defaut = true

[[capacites]]
id = "completer"
libelle = "Une réponse"
risque = "lecture"
'''


class Banc(unittest.TestCase):
    REPONSE = "idée\n```python\ndef somme_min(entree):\n    return {'y': 0}\n```"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("droits", "comptes", "evolution"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        labo = mods / "labo"
        (labo / "points").mkdir(parents=True)
        (labo / "contrats").mkdir()
        (labo / "CN_manifeste.toml").write_text(LABO, encoding="utf-8")
        (labo / "CN_module.py").write_text("def brancher(ctx):\n    ctx.implementer('ping', lambda c: {'ok': True})\n", encoding="utf-8")
        (labo / "points" / "EC_somme_min.py").write_text(REF, encoding="utf-8")
        (labo / "contrats" / "CN_somme_min.json").write_text(json.dumps(CONTRAT), encoding="utf-8")
        modeles = mods / "modeles"
        modeles.mkdir()
        (modeles / "CN_manifeste.toml").write_text(MODELES, encoding="utf-8")
        (modeles / "CN_module.py").write_text("def brancher(ctx):\n    ctx.implementer('completer', lambda c, **kw: {'ok': True, 'texte': %r, 'modele': 'faux'})\n" % self.REPONSE, encoding="utf-8")
        cfg = {"rejeu": {"minimum": 20}, "evolution": {"seuils": {"pieges_min": 0.3, "ombre_appels": 20, "appels_par_palier": 20}}}
        self.n = moteur.Noyau(base / "d", mods, cfg, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "modeles", "labo", "evolution"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(ADMIN, True)
        for i in range(50):                                          # le trafic réel de labo.somme_min : des listes de 400 éléments, chaque fois différentes
            self.n.rejeu.enregistrer("labo.somme_min", {"v": [(j * 37 + i * 11) % 1009 for j in range(400)]}, None, 0.2)

    def ex(self, cap, args=None, compte=ADMIN):
        return self.n.executeur.executer("evolution." + cap, "humain", args or {}, compte=compte)


class Lectures(Banc):
    def test_les_cibles_classent_le_point_par_ce_qu_il_coute(self):
        r = self.ex("cibles")
        self.assertEqual(r["statut"], "faite", r)
        c = [x for x in r["resultat"]["cibles"] if x["point"] == "labo.somme_min"][0]
        self.assertFalse(c["muet"])
        self.assertEqual(c["corpus"], 50)

    def test_l_etat_dit_les_pieces_le_routage_la_chaine_et_les_seuils(self):
        r = self.ex("etat")["resultat"]
        self.assertEqual(r["pieces"], [])
        self.assertTrue(r["chaine"]["ok"])
        self.assertEqual(r["seuils"]["paliers"], [10, 50, 100])
        self.assertIn("labo.somme_min", {p["point"] for p in r["points"]})

    def test_un_compte_ordinaire_ne_voit_pas_l_evolution(self):
        self.assertEqual(self.ex("cibles", compte=SIMPLE)["statut"], "refuse")
        self.assertEqual(self.ex("proposer", {"point": "labo.somme_min"}, compte=SIMPLE)["statut"], "refuse")


class Gestes(Banc):
    def test_proposer_avec_orfan_deterministe_ecrit_une_piece_en_ombre(self):
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "deterministe"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertTrue(r["resultat"]["ok"], r["resultat"])
        self.assertEqual(r["resultat"]["piece"]["etat"], "ombre")
        etat = self.ex("etat")["resultat"]
        self.assertEqual([p["etat"] for p in etat["pieces"]], ["ombre"])
        self.assertTrue(etat["chaine"]["ok"])

    def test_une_proposition_fausse_du_modele_n_ecrit_rien(self):
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "modele"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertFalse(r["resultat"]["ok"])
        self.assertEqual(r["resultat"]["essais"][0]["verdict"], "divergente")
        self.assertEqual(self.ex("etat")["resultat"]["pieces"], [])

    def test_un_point_inconnu_ou_un_moteur_inconnu_est_une_erreur_dite(self):
        r = self.ex("proposer", {"point": "labo.absent"})
        self.assertNotEqual(r["statut"], "faite")
        self.assertIn("inconnu", json.dumps(r, ensure_ascii=False))
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "magique"})
        self.assertNotEqual(r["statut"], "faite")

    def test_le_retour_ramene_la_charge_a_la_reference(self):
        self.ex("proposer", {"point": "labo.somme_min"})
        r = self.ex("retour", {"point": "labo.somme_min", "raison": "essai"})
        self.assertEqual(r["statut"], "faite", r)
        etat = self.ex("etat")["resultat"]
        self.assertEqual([p["etat"] for p in etat["pieces"]], ["retiree"])
        self.assertGreaterEqual(etat["tombes"]["labo.somme_min"], 1)                       # la pièce retirée, et toute variante écartée avant elle
        pt = [p for p in etat["points"] if p["point"] == "labo.somme_min"][0]
        self.assertEqual(pt["routage"], {"mode": "arret", "part": 0})

    def test_la_visite_sans_piece_echue_ne_fait_rien(self):
        r = self.ex("visiter")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(r["resultat"]["visites"], [])


class Moteur(Banc):
    def test_le_moteur_periodique_fait_avancer_une_piece_dont_les_preuves_tiennent(self):
        self.ex("proposer", {"point": "labo.somme_min"})
        for i in range(25):                                          # du trafic réel : l'ombre compare l'EC à la référence
            self.n.points.appeler("labo", "somme_min", {"v": [(j * 37 + i) % 1009 for j in range(400)]})
        r = self.n.lancer("evolution.tick")
        self.assertEqual(r["statut"], "fait", r)
        etat = self.ex("etat")["resultat"]
        self.assertEqual(etat["pieces"][0]["etat"], "palier_10")

    def test_le_moteur_a_vide_ne_fait_rien_et_le_dit(self):
        r = self.n.lancer("evolution.tick")
        self.assertEqual(r["statut"], "fait", r)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Banc, Lectures, Gestes, Moteur
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
