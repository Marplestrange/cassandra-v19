# ══════════════════════════════════════════════
# TITRE      : Bancs des moteurs de recherche d'Évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #d7aa10
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du lot 1 de la maquette d'Évolution : le moteur dans son processus, le relais de modèles plafonné, le registre et l'attribution des pièces.
# MÉTHODE    : un vrai processus de moteur (aucune doublure du protocole) ; le modèle est une fonction de banc ; le module Évolution est branché dans un vrai noyau comme au banc du module.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d7aa10 ▼▼▼
"""Bancs des moteurs de recherche : le protocole de processus, le relais, le registre."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from noyau import CN_moteurs as MO  # noqa: E402
from noyau import CN_points as P  # noqa: E402
import CN_test_evolution_module as TM  # noqa: E402

SOURCE = "def f(x):\n    return sorted(x)[0]\n"
BLOC = "idée\n```python\ndef f(x):\n    return min(x)\n```"


def contexte(budget=3):
    return {"point": "a.b", "source_reference": SOURCE, "fonction": "f", "contrat": {}, "entrees": [[3, 1, 2], [9, 4]], "tombes": [], "budget": budget, "seuils": {}}


class Processus(unittest.TestCase):
    def test_orfan_deterministe_dans_son_processus_rend_ses_variantes(self):
        m = MO.MoteurProcessus("deterministe", delai_s=60)
        r = m.proposer(contexte())
        self.assertEqual([c["origine"] for c in r], ["regle"])
        self.assertIn("min(x)", r[0]["texte"])
        self.assertEqual((m.stats["propositions"], m.stats["appels_modele"]), (1, 0))

    def test_le_modele_passe_par_le_relais_et_est_compte(self):
        appels = []
        m = MO.MoteurProcessus("modele", appeler_modele=lambda p, role: appels.append(role) or BLOC, delai_s=60)
        r = m.proposer(contexte(budget=2))
        self.assertEqual(len(r), 2)
        self.assertEqual(m.stats["appels_modele"], 2)
        self.assertEqual(appels, ["executant", "executant"])
        self.assertGreater(m.stats["jetons"], 0)

    def test_au_plafond_le_relais_refuse_et_le_dit_au_moteur(self):
        m = MO.MoteurProcessus("modele", appeler_modele=lambda p, role: BLOC, max_appels=1, delai_s=60)
        with self.assertRaises(P.ErreurEC) as c:
            m.proposer(contexte(budget=3))
        self.assertIn("plafond du relais", str(c.exception))
        self.assertEqual((m.stats["appels_modele"], m.stats["refus"]), (1, 1))

    def test_un_modele_muet_est_une_erreur_dite_pas_une_reponse_inventee(self):
        def muet(p, role):
            raise RuntimeError("quota épuisé")
        m = MO.MoteurProcessus("modele", appeler_modele=muet, delai_s=60)
        with self.assertRaises(P.ErreurEC) as c:
            m.proposer(contexte(budget=1))
        self.assertIn("quota épuisé", str(c.exception))

    def test_sans_modele_branche_le_moteur_a_modele_echoue_net(self):
        with self.assertRaises(P.ErreurEC) as c:
            MO.MoteurProcessus("modele", delai_s=60).proposer(contexte(budget=1))
        self.assertIn("aucun modèle", str(c.exception))

    def test_un_moteur_trop_lent_est_tue_au_delai(self):
        """Le délai court sur toute la recherche, relais compris : un modèle lent ne fait pas durer le moteur au-delà (le banc ne compte pas sur la vitesse de démarrage du processus)."""
        import time

        def lent(prompt, role):
            time.sleep(2.0)
            return BLOC
        m = MO.MoteurProcessus("modele", appeler_modele=lent, delai_s=1.0)
        with self.assertRaises(P.DelaiEC):
            m.proposer(contexte(budget=2))
        self.assertEqual(m.stats["appels_modele"], 1)                     # le second appel n'a jamais lieu

    def test_un_delai_deja_ecoule_tue_avant_de_lancer(self):
        with self.assertRaises(P.DelaiEC):
            MO.MoteurProcessus("deterministe", delai_s=0.0).proposer(contexte())

    def test_un_choix_inconnu_est_refuse_avant_tout(self):
        with self.assertRaises(ValueError):
            MO.MoteurProcessus("magie")


class Registre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.r = MO.Registre(Path(self.tmp.name) / "d" / "moteurs.json")

    def test_declarer_compter_attribuer(self):
        self.r.declarer("orfan", "Orfan", genre="natif", etat="actif")
        self.r.compter("orfan", {"appels_modele": 2, "jetons": 300, "refus": 1}, essais=3)
        self.r.compter("orfan", {"appels_modele": 1, "jetons": 100}, essais=1)
        self.r.attribuer("dns.analyser", 2, "orfan")
        m = self.r.liste()[0]
        self.assertEqual((m["essais"], m["appels_modele"], m["jetons"], m["refus"], m["pieces"]), (4, 3, 400, 1, 1))
        self.assertEqual(self.r.moteur_de("dns.analyser", 2), "orfan")
        self.assertEqual(self.r.moteur_de("dns.analyser", 9), "inconnu")

    def test_redeclarer_garde_les_compteurs(self):
        self.r.declarer("x-moteur", "X")
        self.r.compter("x-moteur", {"jetons": 50}, essais=1)
        self.r.declarer("x-moteur", "X renommé", etat="installe")
        m = self.r.liste()[0]
        self.assertEqual((m["nom"], m["etat"], m["jetons"]), ("X renommé", "installe", 50))
        self.assertEqual(self.r.moteurs_actifs(), [])

    def test_un_identifiant_ou_un_etat_invalide_est_refuse(self):
        for ident in ("", "../x", "a b"):
            with self.assertRaises(ValueError):
                self.r.declarer(ident, "n")
        with self.assertRaises(ValueError):
            self.r.declarer("ok", "n", etat="inconnu")
        with self.assertRaises(ValueError):
            self.r.etat("absent", "actif")

    def test_un_fichier_illisible_se_dit_et_n_est_pas_ecrase(self):
        self.r.chemin.parent.mkdir(parents=True)
        self.r.chemin.write_text("{pas du json", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.r.declarer("orfan", "Orfan")
        self.assertEqual(self.r.chemin.read_text(encoding="utf-8"), "{pas du json")
        self.assertEqual([p.name for p in self.r.chemin.parent.iterdir()], ["moteurs.json"])          # aucun fichier temporaire ne reste


class DansLeModule(TM.Banc):
    def registre(self):
        return MO.Registre(self.n.rejeu.chemin.parent / "moteurs.json")

    def test_les_moteurs_se_lisent_et_orfan_y_est_declare(self):
        r = self.ex("moteurs")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual([m["id"] for m in r["resultat"]["moteurs"]], ["orfan"])
        self.assertFalse(r["resultat"]["isoles"])

    def test_une_proposition_est_comptee_et_sa_piece_attribuee(self):
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "deterministe"})
        self.assertTrue(r["resultat"]["ok"], r["resultat"])
        piece = r["resultat"]["piece"]
        self.assertEqual(piece["moteur"], "orfan")
        self.assertEqual(self.registre().moteur_de("labo.somme_min", piece["num"]), "orfan")
        m = self.ex("moteurs")["resultat"]["moteurs"][0]
        self.assertEqual((m["pieces"], m["essais"] > 0), (1, True))

    def test_un_compte_ordinaire_ne_lit_pas_les_moteurs(self):
        self.assertEqual(self.ex("moteurs", compte=TM.SIMPLE)["statut"], "refuse")

    def test_le_moteur_isole_propose_par_le_relais_et_l_evaluateur_juge_toujours(self):
        self.n.reglages.poser("evolution.moteurs_isoles", "oui", par="essai")
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "modele"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertFalse(r["resultat"]["ok"])                                   # la réponse du modèle de banc est fausse : jugée divergente, rien n'est écrit
        self.assertEqual(self.ex("etat")["resultat"]["pieces"], [])
        m = self.ex("moteurs")["resultat"]
        self.assertTrue(m["isoles"])
        self.assertGreaterEqual(m["moteurs"][0]["appels_modele"], 1)
        self.assertGreater(m["moteurs"][0]["jetons"], 0)

    def test_le_moteur_isole_deterministe_ecrit_la_meme_piece_qu_en_ligne(self):
        self.n.reglages.poser("evolution.moteurs_isoles", "oui", par="essai")
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "deterministe"})
        self.assertTrue(r["resultat"]["ok"], r["resultat"])
        self.assertEqual(r["resultat"]["piece"]["etat"], "ombre")
        self.assertTrue(self.ex("etat")["resultat"]["chaine"]["ok"])


class InstallationDansLeModule(TM.Banc):
    def base(self):
        return self.n.rejeu.chemin.parent

    def catalogue_scelle(self, *moteurs):
        from noyau import CN_installateur as I
        cat = {"moteurs": list(moteurs)}
        chemin = self.base() / "moteurs-catalogue.json"
        chemin.write_text(json.dumps(cat), encoding="utf-8")
        chemin.with_suffix(".sceau").write_text(I.sceller_catalogue(cat, self.n.points._cle()), encoding="utf-8")

    def test_installer_un_moteur_du_catalogue_scelle_puis_le_defaire(self):
        self.assertTrue(self.n.points._cle(), "le noyau de banc exige le sceau : une clé d'instance existe")
        self.catalogue_scelle({"id": "banc-moteur", "nom": "Moteur de banc", "version": "1", "adaptateur": "json", "paquets": []})
        r = self.ex("moteur_installer", {"moteur": "banc-moteur"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertTrue(r["resultat"]["ok"], r["resultat"])
        liste = {m["id"]: m for m in self.ex("moteurs")["resultat"]["moteurs"]}
        self.assertEqual(liste["banc-moteur"]["etat"], "installe")
        self.assertNotIn("banc-moteur", [m["id"] for m in self.ex("moteurs")["resultat"]["moteurs"] if m["etat"] == "actif"])
        a = self.ex("moteur_etat", {"moteur": "banc-moteur", "etat": "actif"})
        self.assertEqual(a["statut"], "faite", a)
        self.assertEqual({m["id"]: m["etat"] for m in self.ex("moteurs")["resultat"]["moteurs"]}["banc-moteur"], "actif")

    def test_un_catalogue_non_scelle_n_installe_rien_et_le_dit(self):
        (self.base() / "moteurs-catalogue.json").write_text(json.dumps({"moteurs": [{"id": "pirate", "adaptateur": "os", "paquets": []}]}), encoding="utf-8")
        r = self.ex("moteur_installer", {"moteur": "pirate"})
        self.assertFalse(r["resultat"]["ok"], r)
        self.assertEqual(r["resultat"]["etapes"][-1]["nom"], "refusée")
        self.assertFalse((self.base() / "moteurs" / "pirate").exists())

    def test_un_etat_inconnu_ou_un_moteur_inconnu_est_une_erreur_dite(self):
        self.assertNotEqual(self.ex("moteur_etat", {"moteur": "orfan", "etat": "magique"})["statut"], "faite")
        self.assertNotEqual(self.ex("moteur_etat", {"moteur": "absent", "etat": "actif"})["statut"], "faite")

    def test_un_compte_ordinaire_ne_peut_ni_installer_ni_activer(self):
        self.assertEqual(self.ex("moteur_installer", {"moteur": "x-y"}, compte=TM.SIMPLE)["statut"], "refuse")
        self.assertEqual(self.ex("moteur_etat", {"moteur": "orfan", "etat": "actif"}, compte=TM.SIMPLE)["statut"], "refuse")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (des bancs).
# CN : tout ce fichier est du nexus : les bancs du lot 1 des moteurs.
# LIEN : noyau/CN_moteurs.py, orfan/CN_moteur_hote.py, modules/evolution.
