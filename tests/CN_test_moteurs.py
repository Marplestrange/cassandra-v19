# ══════════════════════════════════════════════
# TITRE      : Bancs des moteurs de recherche d'Évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #3a8137
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du lot 1 de la maquette d'Évolution : le moteur dans son processus, le relais de modèles plafonné, le registre et l'attribution des pièces.
# MÉTHODE    : un vrai processus de moteur (aucune doublure du protocole) ; le modèle est une fonction de banc ; le module Évolution est branché dans un vrai noyau comme au banc du module.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3a8137 ▼▼▼
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

    def test_une_chaine_de_processus_ne_perd_jamais_un_octet_du_suivant(self):
        """Un tube fermé par `tuer()` pendant que son fil lecteur lisait encore voyait son numéro redonné au processus suivant, qui perdait son premier octet (« Extra data » une fois sur dix). Le lecteur ferme maintenant SON tube."""
        racine = Path(__file__).resolve().parent.parent / "orfan"
        ctx = {"point": "a.b", "source_reference": "def f(x):\n    return x\n", "fonction": "f", "entrees": [], "tombes": [], "budget": 1}
        for i in range(40):
            t = P._Travailleur(256, "auto", script=str(racine / "CN_moteur_hote.py"), arguments=(str(racine / "CN_orfan.py"), "deterministe"))
            try:
                t.envoyer({"op": "proposer", "contexte": ctx})
                self.assertEqual(t.recevoir(60).get("op"), "resultat", i)
            finally:
                t.tuer()
            t._lecteur.join(5)
            self.assertTrue(t.proc.stdout.closed, i)                                          # fermé par le lecteur, une seule fois, après sa dernière lecture


class Registre(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.r = MO.Registre(Path(self.tmp.name) / "d" / "moteurs.json")

    def test_une_regle_de_la_cascade_se_change_plusieurs_fois(self):
        self.r.regler_options(course_si_deux=True)
        self.assertTrue(self.r.options()["course_si_deux"])
        self.r.regler_options(course_si_deux=False)                      # la même règle, une seconde fois : elle ne plante pas
        self.assertFalse(self.r.options()["course_si_deux"])
        self.r.regler_options(arret_premiere=False, course_si_deux=True)
        o = self.r.options()
        self.assertEqual((o["arret_premiere"], o["course_si_deux"], o["modele_si_chaud"]), (False, True, True))

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
        self.assertEqual([m["id"] for m in r["resultat"]["moteurs"]], ["frugal", "orfan", "sedal"])
        self.assertTrue(r["resultat"]["isoles"])                                                        # Orfan dans sa cage par défaut

    def test_une_proposition_est_comptee_et_sa_piece_attribuee(self):
        r = self.proposer_stable({"point": "labo.somme_min", "moteur": "deterministe"})
        self.assertTrue(r["resultat"]["ok"], r["resultat"])
        piece = r["resultat"]["piece"]
        self.assertEqual(piece["moteur"], "orfan")
        self.assertEqual(self.registre().moteur_de("labo.somme_min", piece["num"]), "orfan")
        m = {x["id"]: x for x in self.ex("moteurs")["resultat"]["moteurs"]}["orfan"]
        self.assertEqual((m["pieces"], m["essais"] > 0), (1, True))

    def test_un_compte_ordinaire_ne_lit_pas_les_moteurs(self):
        self.assertEqual(self.ex("moteurs", compte=TM.SIMPLE)["statut"], "refuse")

    def test_le_moteur_isole_propose_par_le_relais_et_l_evaluateur_juge_toujours(self):
        r = self.ex("proposer", {"point": "labo.somme_min", "moteur": "modele"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertFalse(r["resultat"]["ok"])                                   # la réponse du modèle de banc est fausse : jugée divergente, rien n'est écrit
        self.assertEqual(self.ex("etat")["resultat"]["pieces"], [])
        m = self.ex("moteurs")["resultat"]
        self.assertTrue(m["isoles"])
        orfan = {x["id"]: x for x in m["moteurs"]}["orfan"]
        self.assertGreaterEqual(orfan["appels_modele"], 1)
        self.assertGreater(orfan["jetons"], 0)

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


class Controle(unittest.TestCase):
    """Le contrôle d'intégrité d'un moteur : le ping du vrai processus, puis chaque étape et la défaillance dite."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reg = MO.Registre(Path(self.tmp.name) / "d" / "moteurs.json")
        self.reg.declarer("orfan", "Orfan", genre="natif", etat="actif")

    def moteur_ok(self):
        class M:
            def ping(self, delai_s):
                return {"ok": True, "duree_s": 0.1}
        return M()

    def moteur_muet(self):
        class M:
            def ping(self, delai_s):
                return {"ok": False, "erreur": "DelaiEC : délai de 20 s dépassé"}
        return M()

    def test_le_vrai_processus_repond_au_ping_sans_modele(self):
        appels = []
        m = MO.MoteurProcessus("deterministe", appeler_modele=lambda p, role: appels.append(p) or "", delai_s=60)
        r = m.ping(60)
        self.assertTrue(r["ok"], r)
        self.assertEqual(appels, [])                                    # un ping ne demande rien au modèle

    def test_un_moteur_qui_ne_demarre_pas_est_une_reponse_negative_pas_une_exception(self):
        m = MO.MoteurProcessus("deterministe", orfan=str(Path(self.tmp.name) / "absent.py"), delai_s=60)
        r = m.ping(10)
        self.assertFalse(r["ok"], r)
        self.assertTrue(r["erreur"])

    def test_tout_va_bien_les_cinq_etapes_passent_et_la_defaillance_est_levee(self):
        self.reg.defaillance("orfan", "ancienne faute")
        r = MO.controler("orfan", self.reg, creer_moteur=self.moteur_ok, appeler_modele=lambda p, role: "ok", programme=lambda: (True, "intact"), a_modele=True)
        self.assertTrue(r["ok"], r)
        self.assertIsNone(r["panne"])
        self.assertEqual([e["ok"] for e in r["etapes"]], [True] * 5)
        m = self.reg.liste()[0]
        self.assertNotIn("defaillance", m)
        self.assertTrue(m["controle"]["ok"])

    def test_un_moteur_sans_modele_ne_depense_aucun_jeton_au_controle(self):
        appels = []
        r = MO.controler("orfan", self.reg, creer_moteur=self.moteur_ok, appeler_modele=lambda p, role: appels.append(p) or "ok", programme=lambda: (True, ""), a_modele=False)
        self.assertTrue(r["ok"], r)
        self.assertEqual(appels, [])

    def test_un_moteur_muet_est_une_defaillance_a_relancer_et_les_etapes_suivantes_ne_sont_pas_faites(self):
        r = MO.controler("orfan", self.reg, creer_moteur=self.moteur_muet, programme=lambda: (True, ""))
        self.assertFalse(r["ok"])
        self.assertEqual(r["panne"]["titre"], "il ne répond plus")
        self.assertTrue(r["panne"]["relance"])
        self.assertEqual([e["ok"] for e in r["etapes"]], [True, True, False, None, None])
        self.assertIn("defaillance", self.reg.liste()[0])

    def test_un_modele_muet_est_une_defaillance_dite(self):
        def muet(prompt, role):
            raise RuntimeError("le modèle n'a pas répondu")
        r = MO.controler("orfan", self.reg, creer_moteur=self.moteur_ok, appeler_modele=muet, programme=lambda: (True, ""), a_modele=True)
        self.assertEqual(r["panne"]["titre"], "son modèle ne répond pas")
        self.assertTrue(r["panne"]["relance"])
        self.assertEqual([e["ok"] for e in r["etapes"]], [True, True, True, False, None])

    def test_un_programme_invalide_est_refuse_et_rien_d_autre_n_est_essaye(self):
        lance = []
        r = MO.controler("orfan", self.reg, creer_moteur=lambda: lance.append(1) or self.moteur_ok(), programme=lambda: (False, "le sceau du catalogue ne correspond pas"))
        self.assertEqual(r["panne"]["titre"], "programme modifié ou invalide")
        self.assertTrue(r["panne"]["refuse"])
        self.assertFalse(r["panne"]["relance"])
        self.assertEqual(lance, [])                                     # un programme douteux n'est jamais lancé
        self.assertTrue(self.reg.liste()[0]["controle"]["refuse"])

    def test_l_isolation_desactivee_est_dite(self):
        r = MO.controler("orfan", self.reg, creer_moteur=self.moteur_ok, isoles=False, programme=lambda: (True, ""))
        self.assertEqual(r["panne"]["titre"], "isolation désactivée")

    def test_un_plafond_atteint_n_est_pas_une_defaillance(self):
        self.reg.plafonner("orfan", jetons_jour=100)
        self.reg.compter("orfan", {"jetons": 150}, essais=1)
        self.reg.defaillance("orfan", "vieille faute")
        r = MO.controler("orfan", self.reg, creer_moteur=self.moteur_ok, programme=lambda: (True, ""))
        self.assertEqual(r["panne"]["titre"], "plafond atteint")
        self.assertEqual([e["ok"] for e in r["etapes"]], [True, True, True, True, False])
        self.assertNotIn("defaillance", self.reg.liste()[0])            # le plafond est une limite, pas une panne : la défaillance ancienne est levée

    def test_une_exception_du_programme_est_une_defaillance_pas_un_crash(self):
        def casse():
            raise OSError("disque illisible")
        r = MO.controler("orfan", self.reg, creer_moteur=self.moteur_ok, programme=casse)
        self.assertFalse(r["ok"])
        self.assertIn("disque illisible", r["panne"]["raison"])

    def test_defaillance_retenue_et_levee(self):
        self.reg.defaillance("orfan", "Erreur : boom")
        self.assertEqual(self.reg.liste()[0]["defaillance"]["raison"], "Erreur : boom")
        self.reg.retablir("orfan")
        self.assertNotIn("defaillance", self.reg.liste()[0])
        self.reg.defaillance("inconnu", "x")                            # un moteur inconnu est ignoré, sans erreur
        self.reg.retablir("inconnu")

    def test_la_course_retient_la_faute_d_un_moteur_et_la_leve_quand_il_va_au_bout(self):
        from noyau import CN_course as C
        reg = self.reg

        class Evo:
            class points:
                @staticmethod
                def reference(m, p):
                    raise AssertionError("non utilisé")

            def __init__(self, r):
                self.r = r

            def proposer(self, module, point, moteur, budget):
                if isinstance(self.r, Exception):
                    raise self.r
                return self.r

            essayer = proposer

        o = C.Orchestrateur(Evo(RuntimeError("le moteur a planté")), reg)
        o._moteur = lambda etage, budget_type="jetons", limite=None: type("X", (), {"stats": {}})()
        o._lancer("orfan/deterministe", "a", "b", 1, ecrire=True)
        self.assertIn("planté", reg.liste()[0]["defaillance"]["raison"])
        o.evo = Evo({"ok": False, "essais": [], "retenus": [], "meilleur": None, "raison": "rien de prouvé", "piece": None})
        o._lancer("orfan/deterministe", "a", "b", 1, ecrire=True)
        self.assertNotIn("defaillance", reg.liste()[0])                 # chercher sans rien trouver n'est pas une faute


class ControleDansLeModule(TM.Banc):
    def test_le_controle_d_orfan_dit_tout_et_note_son_dernier_controle(self):
        r = self.ex("moteur_controler", {"moteur": "orfan"})
        self.assertEqual(r["statut"], "faite", r)
        res = r["resultat"]
        self.assertEqual([e["id"] for e in res["etapes"]], list(MO.ETAPES_CONTROLE))
        self.assertTrue(res["etapes"][0]["ok"], res)                    # le fichier d'Orfan est là et valide
        self.assertTrue(res["etapes"][2]["ok"], res)                    # son vrai processus répond au ping
        m = {x["id"]: x for x in self.ex("moteurs")["resultat"]["moteurs"]}["orfan"]
        self.assertIn("controle", m)

    def test_un_moteur_inconnu_est_une_erreur_dite(self):
        self.assertNotEqual(self.ex("moteur_controler", {"moteur": "absent"})["statut"], "faite")

    def test_un_compte_ordinaire_ne_peut_pas_controler(self):
        self.assertEqual(self.ex("moteur_controler", {"moteur": "orfan"}, compte=TM.SIMPLE)["statut"], "refuse")


class InstallationDepuisLEcran(TM.Banc):
    """Le répertoire à l'écran, la garde d'activation d'un adaptateur généré, les refus de la tâche d'installation."""

    def registre(self):
        return MO.Registre(self.n.rejeu.chemin.parent / "moteurs.json")

    def test_les_moteurs_rendent_le_repertoire_et_ce_que_le_serveur_sait_faire(self):
        r = self.ex("moteurs")["resultat"]
        rep = {e["id"]: e for e in r["repertoire"]}
        self.assertEqual([e["id"] for e in r["repertoire"] if e["statut"] == "livre"], ["orfan", "frugal", "sedal"])
        self.assertEqual(sorted(e["id"] for e in r["repertoire"] if e["statut"] == "disponible"), sorted(["openevolve", "shinka", "codeevolve", "gepa", "llm4ad", "openelm", "dspy", "textgrad", "evoprompt"]))
        self.assertTrue(rep["gepa"]["ecrit"] and not rep["gepa"]["adaptateur_genere"])
        self.assertFalse(rep["dspy"]["ecrit"])                                          # pas d'adaptateur écrit : le repli le génèrera
        self.assertFalse(rep["evoprompt"]["avec_paquet"])                               # une méthode réimplémentée, pas de paquet
        self.assertEqual(rep["codeevolve"]["python"], "3.13.5")
        for cle in ("python", "venv", "bac", "disque_libre_go", "uv", "cle"):
            self.assertIn(cle, r["serveur"])

    def test_un_chercheur_inconnu_ou_deja_installe_ne_lance_aucune_tache(self):
        self.assertNotEqual(self.ex("moteur_installer_tache", {"moteur": "n-existe-pas"})["statut"], "faite")
        self.registre().declarer("gepa", "GEPA", genre="externe", etat="installe", version="0.1.4")
        r = self.ex("moteur_installer_tache", {"moteur": "gepa"})
        self.assertNotEqual(r["statut"], "faite", r)
        self.assertIn("déjà installé", str(r))

    def test_un_compte_ordinaire_ne_peut_ni_installer_ni_mettre_a_jour_ni_approuver(self):
        for cap, args in (("moteur_installer_tache", {"moteur": "gepa"}), ("moteur_maj_tache", {"moteur": "gepa"}), ("moteur_adaptateur_approuver", {"moteur": "gepa", "empreinte": "x"}), ("moteur_adaptateur_lire", {"moteur": "gepa"}),
                          ("moteur_tache", {"tache": "x"}), ("moteur_maj_dispo", {})):
            self.assertEqual(self.ex(cap, args, compte=TM.SIMPLE)["statut"], "refuse", cap)

    def test_une_tache_inconnue_est_une_erreur_dite(self):
        self.assertNotEqual(self.ex("moteur_tache", {"tache": "perdue"})["statut"], "faite")

    def test_un_adaptateur_genere_non_relu_ne_s_active_pas_puis_s_active_une_fois_approuve(self):
        self.registre().declarer("banc-gen", "Banc généré", genre="externe", etat="installe", adaptateur="CN_adaptateur_banc_gen", adaptateur_genere={"empreinte": "e" * 64, "relu": False})
        refus = self.ex("moteur_etat", {"moteur": "banc-gen", "etat": "actif"})
        self.assertNotEqual(refus["statut"], "faite", refus)
        self.assertIn("pas été relu", str(refus))
        self.assertEqual({m["id"]: m["etat"] for m in self.registre().liste()}["banc-gen"], "installe")
        self.registre().approuver_adaptateur("banc-gen", "e" * 64)
        ok = self.ex("moteur_etat", {"moteur": "banc-gen", "etat": "actif"})
        self.assertEqual(ok["statut"], "faite", ok)

    def test_desactiver_un_adaptateur_genere_non_relu_reste_permis(self):
        self.registre().declarer("banc-gen", "Banc généré", genre="externe", etat="actif", adaptateur_genere={"empreinte": "e" * 64, "relu": False})
        self.assertEqual(self.ex("moteur_etat", {"moteur": "banc-gen", "etat": "installe"})["statut"], "faite")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (des bancs).
# CN : tout ce fichier est du nexus : les bancs du lot 1 des moteurs.
# LIEN : noyau/CN_moteurs.py, orfan/CN_moteur_hote.py, modules/evolution.
