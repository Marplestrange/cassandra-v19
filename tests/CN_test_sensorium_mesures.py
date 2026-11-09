# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des mesures de première classe du Sensorium, sur un vrai noyau monté
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #9ac3ca
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des mesures de première classe du Sensorium, sur un vrai noyau monté : capteurs enfichables (avec un faux émetteur), état à trois valeurs, capteur muet, clés suivies et événements, plafonds, cloisonnement entre comptes et sociétés, vu
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9ac3ca ▼▼▼
"""Bancs des mesures de première classe du Sensorium, sur un vrai noyau monté : capteurs enfichables (avec un faux émetteur), état à trois valeurs, capteur muet, clés suivies et événements,
plafonds, cloisonnement entre comptes et sociétés, vue minimale sans fuite, relations et impact, prévision, auto-observation. Aucun socket, aucun service réel : le collecteur est simulé."""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from tests.CN_test_sensorium_cloisonnement import ADMIN, AUTRE, MDP, MONDE, SIMPLE, Banc, collecteur_simule  # noqa: E402

KINO, KINO2 = "kino1@exemple.test", "kino2@exemple.test"
T0 = 1_800_000_000.0
SECRET = 4242.5                 # une valeur qu'aucune vue minimale ne doit jamais montrer


class Horloge:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t

    def avance(self, s):
        self.t += s


class Mesures(Banc):
    MODULES = ("droits", "modules", "sensorium")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for k in (KINO, KINO2):
            r = cls.n.identite.creer(k, MDP)
            assert r["ok"] and not r["admin"], r
            cls.n.droits.regler("compte", k, "sensorium.alimenter", "accorde")
        cls.g = cls.n.catalogue.get("sensorium.mesure_etat").faire.__globals__
        cls.h = Horloge()
        cls.patch_h = mock.patch.dict(cls.g, {"_maintenant": cls.h})
        cls.patch_h.start()

    @classmethod
    def tearDownClass(cls):
        cls.patch_h.stop()
        super().tearDownClass()

    def setUp(self):
        self.h.t += 100000                       # chaque banc part d'un instant neuf : pas de limite de débit héritée du précédent
        self.n.base.ecrire("DELETE FROM evenements WHERE type='mesure.change'")
        db = self.n.executeur.contextes["sensorium"].stockage
        for t in ("espaces", "capteurs", "lectures", "historique", "suivies", "visibilites", "liens", "compteurs"):
            db.ecrire("DELETE FROM sensorium_" + t)

    # ---- aides
    def faire(self, cap, compte, acteur=None, societe="", **args):
        acteur = acteur or ("compte" if compte in (KINO, KINO2) else "humain")          # un nœud satellite agit comme un compte ; une personne comme un humain
        return self.n.executeur.executer("sensorium." + cap, acteur, args, compte=compte, societe=societe)

    def ok(self, cap, compte, **args):
        r = self.faire(cap, compte, **args)
        self.assertEqual(r["statut"], "faite", (cap, r))
        return r["resultat"]

    def lire(self, cap, compte, **args):
        r = self.n.executeur.executer("sensorium." + cap, "humain", args, compte=compte)
        return r

    def declarer(self, cle="dns.latence", compte=KINO, **kw):
        args = dict(cle=cle, libelle="Latence DNS", unite="ms", fraicheur_s=60, alerte=100, critique=300, pire="haut")
        args.update(kw)
        return self.ok("capteur_declarer", compte, **args)

    def alimenter(self, cle="dns.latence", valeur=10, compte=KINO, **kw):
        return self.ok("capteur_alimenter", compte, lectures=[dict(cle=cle, valeur=valeur, **kw)])

    def evenements(self):
        return [dict(e, donnees=json.loads(e["donnees"])) for e in self.n.base.lire("SELECT * FROM evenements WHERE type='mesure.change' ORDER BY id")]

    def vue_pour(self, compte, societe="", cle=None):
        """Comme un module ouvert dans la société du demandeur : executer_lecture, au nom du compte et de sa société."""
        lecture = self.n.executeur.contextes["sensorium"]._intro["lecture"]
        return lecture("sensorium.mesure_etat" if cle else "sensorium.vue_minimale", {"cle": cle} if cle else {}, compte, societe)


class Capteurs(Mesures):
    def test_un_faux_emetteur_declare_alimente_et_son_etat_se_lit(self):
        r = self.declarer()
        self.assertTrue(r["ok"] and r["nouveau"] and r["espace"] == "dns")
        self.assertEqual(self.alimenter(valeur=10)["acceptees"], ["dns.latence"])
        d = self.ok("mesure_detail", ADMIN, cle="dns.latence")
        self.assertEqual((d["etat"], d["valeur"], d["gravite"], d["unite"]), ("ok", 10.0, "ok", "ms"))

    def test_les_seuils_donnent_la_gravite(self):
        self.declarer()
        for v, etat, niveau in ((150, "alerte", "warning"), (400, "alerte", "critical"), (5, "ok", "ok")):
            self.h.avance(5)
            self.alimenter(valeur=v)
            d = self.ok("mesure_detail", ADMIN, cle="dns.latence")
            self.assertEqual((d["etat"], d["gravite"]), (etat, niveau), v)

    def test_la_gravite_donnee_par_l_emetteur_prime_sur_les_seuils(self):
        self.declarer()
        self.alimenter(valeur=5, gravite="critical")
        self.assertEqual(self.ok("mesure_detail", ADMIN, cle="dns.latence")["etat"], "alerte")

    def test_la_capacite_d_alimentation_agit_seule_des_le_premier_appel(self):
        self.assertEqual(self.n.catalogue.savoir("sensorium.capteur_alimenter")["palier"], "auto")
        self.declarer()
        self.assertEqual(self.faire("capteur_alimenter", KINO, lectures=[{"cle": "dns.latence", "valeur": 1}])["statut"], "faite")

    def test_un_compte_sans_le_droit_alimenter_est_refuse(self):
        r = self.faire("capteur_declarer", SIMPLE, cle="x.y")
        self.assertEqual((r["statut"], r.get("droit")), ("refuse", "sensorium.alimenter"))
        r = self.faire("capteur_alimenter", SIMPLE, lectures=[])
        self.assertEqual(r["statut"], "refuse")

    def test_les_fautes_d_un_emetteur_ne_font_pas_retrograder_la_capacite(self):
        for _ in range(8):
            r = self.faire("capteur_alimenter", KINO, lectures=[{"cle": "inconnu.truc", "valeur": 1}, "n'importe quoi", {"valeur": 3}])
            self.assertEqual(r["statut"], "faite")
            self.assertEqual(len(r["resultat"]["refusees"]), 3)
        self.assertEqual(self.faire("capteur_alimenter", KINO, lectures="pas une liste")["statut"], "faite")
        self.assertEqual(self.n.catalogue.savoir("sensorium.capteur_alimenter")["palier"], "auto")

    def test_cles_et_parametres_illisibles_sont_refuses_dans_la_reponse(self):
        for kw in (dict(cle="Majuscule.x"), dict(cle="sansespace"), dict(cle="monde.x"), dict(cle="sensorium.x"), dict(cle="dns.x", fraicheur_s=1),
                   dict(cle="dns.x", pire="milieu"), dict(cle="dns.x", confiance_min=3), dict(cle="dns.x", alerte="beaucoup"), dict(cle="../etc")):
            r = self.faire("capteur_declarer", KINO, **kw)
            self.assertEqual(r["statut"], "faite", kw)
            self.assertFalse(r["resultat"]["ok"], kw)
            self.assertTrue(r["resultat"]["refuse"], kw)

    def test_un_espace_appartient_au_compte_qui_le_declare_en_premier(self):
        self.declarer(compte=KINO)
        r = self.faire("capteur_declarer", KINO2, cle="dns.autre")
        self.assertFalse(r["resultat"]["ok"])
        self.assertIn("autre compte", r["resultat"]["refuse"])
        r = self.faire("capteur_alimenter", KINO2, lectures=[{"cle": "dns.latence", "valeur": 7}])
        self.assertEqual(r["resultat"]["acceptees"], [])
        self.assertEqual(r["resultat"]["refusees"][0]["motif"], "capteur d'un autre compte")
        self.assertIsNone(self.ok("mesure_detail", ADMIN, cle="dns.latence")["valeur"], "la lecture usurpée n'a rien écrit")

    def test_un_compte_peut_avoir_plusieurs_espaces_et_un_autre_aussi(self):
        self.declarer("dns.a", KINO)
        self.declarer("horloge.b", KINO)
        self.assertTrue(self.faire("capteur_declarer", KINO2, cle="kino2.horloge")["resultat"]["ok"])

    def test_plafond_de_capteurs_par_compte(self):
        for i in range(50):
            self.assertTrue(self.faire("capteur_declarer", KINO, cle="dns.c%d" % i)["resultat"]["ok"], i)
        r = self.faire("capteur_declarer", KINO, cle="dns.c50")["resultat"]
        self.assertFalse(r["ok"])
        self.assertIn("plafond", r["refuse"])
        self.assertTrue(self.faire("capteur_declarer", KINO, cle="dns.c0", libelle="mise à jour")["resultat"]["ok"], "redéclarer un capteur existant n'est pas un ajout")
        self.assertTrue(self.faire("capteur_declarer", KINO2, cle="kino2.a")["resultat"]["ok"], "le plafond est par compte")

    def test_plafond_de_lectures_par_appel_et_debit_par_cle(self):
        for i in range(60):
            self.declarer("dns.l%d" % i, KINO) if i < 50 else None
        lots = [{"cle": "dns.l%d" % (i % 50), "valeur": i} for i in range(55)]
        r = self.ok("capteur_alimenter", KINO, lectures=lots)
        self.assertEqual(len(r["acceptees"]), 50)
        self.assertTrue(any("plus de 50" in x["motif"] for x in r["refusees"]))
        r = self.ok("capteur_alimenter", KINO, lectures=[{"cle": "dns.l0", "valeur": 1}])
        self.assertEqual(r["refusees"][0]["motif"], "trop_vite")
        self.h.avance(2)
        self.assertEqual(self.ok("capteur_alimenter", KINO, lectures=[{"cle": "dns.l0", "valeur": 1}])["acceptees"], ["dns.l0"])

    def test_historique_plafonne_et_espace_de_cinq_minutes(self):
        self.declarer()
        for i in range(30):
            self.h.avance(60)
            self.alimenter(valeur=i)
        n = self.n.executeur.contextes["sensorium"].stockage.lire("SELECT COUNT(*) AS n FROM sensorium_historique WHERE cle='dns.latence'")[0]["n"]
        self.assertTrue(5 <= n <= 8, n)             # une demi-heure à raison d'un point toutes les cinq minutes (et un au premier point)

    def test_retirer_un_capteur_ne_retire_que_les_siens(self):
        self.declarer()
        self.alimenter()
        self.assertFalse(self.faire("capteur_retirer", KINO2, acteur="humain", cle="dns.latence")["resultat"]["ok"])
        self.assertTrue(self.faire("capteur_retirer", KINO, acteur="humain", cle="dns.latence")["resultat"]["ok"])
        with self.assertRaises(Exception):
            self.ok("mesure_detail", ADMIN, cle="dns.latence")

    def test_le_retour_arriere_d_une_declaration(self):
        r = self.faire("capteur_declarer", KINO, cle="dns.neuf")
        self.assertEqual(r["statut"], "faite")
        fait = self.n.base.lire("SELECT id FROM evenements WHERE type='capacite.faite' AND objet_id='sensorium.capteur_declarer' ORDER BY id DESC LIMIT 1")[0]["id"]
        self.assertEqual(self.n.executeur.defaire_acte(fait, "essai")["statut"], "defaite")
        db = self.n.executeur.contextes["sensorium"].stockage
        self.assertFalse(db.lire("SELECT 1 FROM sensorium_capteurs WHERE cle='dns.neuf'"))
        self.assertFalse(db.lire("SELECT 1 FROM sensorium_espaces WHERE espace='dns'"))


class Etat(Mesures):
    def test_un_capteur_muet_n_est_jamais_ok(self):
        self.declarer()
        self.alimenter(valeur=1)
        self.assertEqual(self.ok("mesure_detail", ADMIN, cle="dns.latence")["etat"], "ok")
        self.h.avance(61)
        d = self.ok("mesure_detail", ADMIN, cle="dns.latence")
        self.assertEqual(d["etat"], "inconnu")
        self.assertIn("muette", d["raison"])
        self.assertAlmostEqual(d["depuis"], self.h.t - 1, delta=2, msg="inconnu DEPUIS l'instant où la fraîcheur a été dépassée")

    def test_un_capteur_declare_sans_lecture_est_inconnu(self):
        self.declarer()
        self.assertEqual(self.ok("mesure_detail", ADMIN, cle="dns.latence")["raison"], "jamais lue")

    def test_une_horloge_non_fiable_rend_tout_inconnu(self):
        self.declarer()
        self.alimenter(valeur=1)
        with mock.patch.dict(self.g, {"_maintenant": lambda: 5000.0}):
            self.assertEqual(self.ok("mesure_detail", ADMIN, cle="dns.latence")["etat"], "inconnu")
            self.assertFalse(self.ok("autoobservation", ADMIN)["horloge_fiable"])

    def test_l_heure_de_l_emetteur_ne_juge_jamais_la_fraicheur(self):
        self.declarer()
        self.alimenter(valeur=1, observe_a=T0 - 10 ** 6)
        d = self.ok("mesure_detail", ADMIN, cle="dns.latence")
        self.assertEqual(d["etat"], "ok", "une lecture reçue à l'instant est fraîche, quoi que l'émetteur dise de l'heure")
        self.assertLess(d["decalage_s"], -1000)
        self.assertLessEqual(d["confiance"], 0.5)

    def test_confiance_insuffisante(self):
        self.declarer(confiance_min=0.6)
        self.alimenter(valeur=1, confiance=0.2)
        d = self.ok("mesure_detail", ADMIN, cle="dns.latence")
        self.assertEqual(d["etat"], "inconnu")
        self.assertIn("confiance", d["raison"])
        self.h.avance(2)
        self.alimenter(valeur=1, observe_a=T0 - 10 ** 6, confiance=0.9)         # décalage d'horloge : confiance plafonnée à 0,5 < 0,6
        self.assertEqual(self.ok("mesure_detail", ADMIN, cle="dns.latence")["etat"], "inconnu")

    def test_depuis_quand_ne_bouge_qu_au_changement_d_etat(self):
        self.declarer()
        self.alimenter(valeur=1)
        d1 = self.ok("mesure_detail", ADMIN, cle="dns.latence")["depuis"]
        self.h.avance(10)
        self.alimenter(valeur=2)
        self.assertEqual(self.ok("mesure_detail", ADMIN, cle="dns.latence")["depuis"], d1)
        self.h.avance(10)
        self.alimenter(valeur=500)
        self.assertEqual(self.ok("mesure_detail", ADMIN, cle="dns.latence")["depuis"], self.h.t)


class Suivi(Mesures):
    def test_une_cle_non_suivie_n_emet_rien(self):
        self.declarer()
        self.alimenter(valeur=1)
        self.h.avance(2)
        self.alimenter(valeur=999)
        self.h.avance(300)
        self.n.lancer("sensorium.suivi_mesures")
        self.assertEqual(self.evenements(), [])

    def test_une_cle_suivie_emet_avant_apres_depuis(self):
        self.declarer()
        self.assertTrue(self.ok("mesure_suivre", ADMIN, cle="dns.latence", motif="essai")["ok"])
        self.alimenter(valeur=1)
        self.h.avance(40)
        self.alimenter(valeur=500)
        evs = self.evenements()
        self.assertEqual([(e["donnees"]["avant"], e["donnees"]["apres"]) for e in evs], [("inconnu", "ok"), ("ok", "alerte")])
        e = evs[-1]
        self.assertEqual((e["objet_type"], e["objet_id"], e["compte"], e["donnees"]["suiveur"]), ("mesure", "dns.latence", ADMIN, ADMIN))
        self.assertEqual(e["donnees"]["depuis"], self.h.t)

    def test_le_va_et_vient_est_fusionne(self):
        self.declarer()
        self.ok("mesure_suivre", ADMIN, cle="dns.latence")
        self.alimenter(valeur=1)
        self.h.avance(31)
        for v in (500, 1, 500, 1, 500, 1):
            self.h.avance(2)
            self.alimenter(valeur=v)
        evs = self.evenements()
        self.assertLessEqual(len(evs), 3, [(e["donnees"]["avant"], e["donnees"]["apres"]) for e in evs])
        self.assertGreater(self.ok("autoobservation", ADMIN)["compteurs"].get("evenements_fusionnes", 0), 0)

    def test_un_capteur_qui_se_tait_passe_inconnu_et_s_annonce_par_le_moteur_de_fraicheur(self):
        self.declarer()
        self.ok("mesure_suivre", ADMIN, cle="dns.latence")
        self.alimenter(valeur=1)
        self.h.avance(61)
        self.assertEqual(self.n.lancer("sensorium.suivi_mesures").get("statut"), "fait")
        derniers = [(e["donnees"]["avant"], e["donnees"]["apres"]) for e in self.evenements()]
        self.assertEqual(derniers[-1], ("ok", "inconnu"))
        self.n.lancer("sensorium.suivi_mesures")
        self.assertEqual(len(self.evenements()), len(derniers), "pas d'annonce en double")
        c = self.evenements()[-1]["donnees"]
        self.assertIn("muette", c["raison"])
        self.h.avance(2)
        self.alimenter(valeur=1)
        self.assertEqual(self.evenements()[-1]["donnees"]["apres"], "inconnu", "dans la fusion de 30 s, le retour attend")
        self.h.avance(31)
        self.alimenter(valeur=1)
        self.assertEqual(self.evenements()[-1]["donnees"]["apres"], "ok", "le retour du capteur s'annonce à la lecture suivante, une fois la fusion passée")

    def test_un_constat_resume_les_mesures_suivies_muettes(self):
        for i in range(3):
            self.declarer("dns.m%d" % i)
            self.alimenter("dns.m%d" % i, 1)
            self.ok("mesure_suivre", ADMIN, cle="dns.m%d" % i)
        self.h.avance(61)
        ctx = self.n.executeur.contextes["sensorium"]
        res = self.g["suivies_muettes"](ctx)
        self.assertEqual(len(res), 1)
        self.assertIn("3 mesures suivies", res[0]["titre"])

    def test_plafonds_de_suivi(self):
        for i in range(50):
            self.assertTrue(self.ok("mesure_suivre", ADMIN, cle="dns.s%d" % i)["ok"], i)
        r = self.ok("mesure_suivre", ADMIN, cle="dns.s50")
        self.assertFalse(r["ok"])
        self.assertIn("plafond", r["refuse"])
        self.assertTrue(self.ok("mesure_suivre", ADMIN, cle="dns.s0")["ok"], "re-suivre une clé déjà suivie n'est pas un ajout")

    def test_on_ne_suit_pas_ce_qu_on_ne_voit_pas(self):
        self.n.droits.regler("compte", SIMPLE, "sensorium.suivre", "accorde")
        try:
            self.declarer()
            r = self.ok("mesure_suivre", SIMPLE, cle="dns.latence")
            self.assertFalse(r["ok"])
            self.assertEqual(r["refuse"], "clé inconnue ou non visible pour ce compte")
            self.assertEqual(self.ok("mesure_suivre", SIMPLE, cle="dns.nexiste.pas")["refuse"], r["refuse"], "le refus ne dit pas si la clé existe")
        finally:
            self.n.droits.regler("compte", SIMPLE, "sensorium.suivre", None)

    def test_le_retour_arriere_d_un_suivi(self):
        self.ok("mesure_suivre", ADMIN, cle="dns.latence")
        r = self.ok("mesure_ne_plus_suivre", ADMIN, cle="dns.latence")
        self.assertTrue(r["ok"])
        self.assertEqual(self.ok("mesures_suivies", ADMIN)["suivies"], [])

    def test_les_mesures_du_monde_suivies_se_lisent_et_se_perimment_quand_le_collecteur_se_tait(self):
        cle = "monde.ssl.client-prive.exemple.test"
        self.assertTrue(self.ok("mesure_suivre", ADMIN, cle=cle)["ok"])
        self.n.lancer("sensorium.monde")
        d = self.ok("mesure_detail", ADMIN, cle=cle)
        self.assertEqual((d["etat"], d["gravite"]), ("alerte", "warning"))
        self.assertEqual(d["valeur"], "expire dans 3 jours")
        def muet(requete, delai=5.0):
            raise OSError("collecteur arrêté")
        with mock.patch.dict(self.n.catalogue.get("sensorium.monde").faire.__globals__, {"json_de": muet}):
            self.h.avance(200)
            self.n.lancer("sensorium.monde")
            self.n.lancer("sensorium.suivi_mesures")
            d = self.ok("mesure_detail", ADMIN, cle=cle)
        self.assertEqual(d["etat"], "inconnu", "un collecteur muet ne veut jamais dire « ok »")
        self.assertEqual(self.evenements()[-1]["donnees"]["apres"], "inconnu")

    def test_une_mesure_du_monde_non_suivie_n_est_pas_ingeree(self):
        self.n.lancer("sensorium.monde")
        db = self.n.executeur.contextes["sensorium"].stockage
        self.assertEqual(db.lire("SELECT COUNT(*) AS n FROM sensorium_lectures")[0]["n"], 0)


class VueMinimale(Mesures):
    def preparer(self):
        self.declarer("dns.secret", KINO, libelle="DNS du site client", alerte=10 ** 6, critique=10 ** 7)
        self.alimenter("dns.secret", SECRET, observe_a=T0, detail="serveur-interne-12.exemple.test")

    def test_par_defaut_personne_d_autre_ne_voit_rien_et_l_inexistant_se_ressemble(self):
        self.preparer()
        reel = self.vue_pour(SIMPLE, "1", cle="dns.secret")
        fantome = self.vue_pour(SIMPLE, "1", cle="dns.fantome")
        self.assertEqual(reel["etat"], "inconnu")
        self.assertEqual({k: v for k, v in reel.items() if k != "cle"}, {k: v for k, v in fantome.items() if k != "cle"}, "aucun oracle d'existence")
        self.assertEqual(self.vue_pour(SIMPLE, "1")["mesures"], [])

    def test_un_administrateur_voit_l_etat_en_quatre_champs_jamais_la_valeur_par_cette_voie(self):
        self.preparer()
        m = self.ok("mesure_etat", ADMIN, cle="dns.secret")
        self.assertEqual(set(m), {"cle", "libelle", "etat", "depuis", "raison"})
        self.assertEqual(m["etat"], "ok")
        txt = json.dumps(self.ok("vue_minimale", ADMIN))
        self.assertNotIn(str(SECRET), txt)
        self.assertNotIn("serveur-interne", txt)
        self.assertNotIn("ms", json.loads(txt)["mesures"][0], "pas d'unité")

    def test_publiee_pour_une_societe_seulement_celle_ci_la_voit_et_sans_valeur(self):
        self.preparer()
        self.assertTrue(self.ok("mesure_publier", ADMIN, cle="dns.secret", visibilite="societes:2", libelle="Résolution DNS")["ok"])
        vu = self.vue_pour(AUTRE, "2", cle="dns.secret")
        self.assertEqual((vu["etat"], vu["libelle"]), ("ok", "DNS du site client"))
        self.assertEqual(set(vu), {"cle", "libelle", "etat", "depuis", "raison"})
        self.assertEqual(self.vue_pour(SIMPLE, "1", cle="dns.secret")["libelle"], "", "la société 1 ne la voit pas : publiée pour la 2 seulement")
        self.assertEqual([m["cle"] for m in self.vue_pour(AUTRE, "2")["mesures"]], ["dns.secret"])
        self.assertNotIn(str(SECRET), json.dumps(self.vue_pour(AUTRE, "2")))
        self.assertNotIn("serveur-interne", json.dumps(self.vue_pour(AUTRE, "2")))

    def test_la_societe_vient_de_l_acte_pas_d_un_argument(self):
        self.preparer()
        self.ok("mesure_publier", ADMIN, cle="dns.secret", visibilite="societes:2")
        for pirate in ("2", "societes:2", "toutes"):
            r = self.faire("mesure_etat", SIMPLE, acteur="humain", cle="dns.secret", societe_demandee=pirate)
            self.assertEqual(r["statut"], "echec", "un argument inconnu est refusé, jamais interprété")
        self.assertEqual(self.vue_pour(SIMPLE, "1", cle="dns.secret")["etat"], "inconnu")

    def test_publier_toutes_puis_remettre_a_l_instance(self):
        self.preparer()
        self.ok("mesure_publier", ADMIN, cle="dns.secret", visibilite="toutes")
        self.assertEqual(self.vue_pour(SIMPLE, "1", cle="dns.secret")["etat"], "ok")
        self.assertEqual(self.vue_pour(AUTRE, "2", cle="dns.secret")["etat"], "ok")
        self.ok("mesure_publier", ADMIN, cle="dns.secret", visibilite="instance")
        self.assertEqual(self.vue_pour(AUTRE, "2", cle="dns.secret")["libelle"], "")

    def test_une_mesure_publiee_et_muette_dit_inconnu_avec_sa_raison_mais_pas_les_chiffres(self):
        self.preparer()
        self.ok("mesure_publier", ADMIN, cle="dns.secret", visibilite="toutes")
        self.h.avance(500)
        vu = self.vue_pour(SIMPLE, "1", cle="dns.secret")
        self.assertEqual((vu["etat"], vu["raison"]), ("inconnu", "muette"))
        self.assertNotIn("attendue", json.dumps(vu))

    def test_seul_un_administrateur_publie(self):
        self.preparer()
        self.n.droits.regler("compte", SIMPLE, "sensorium.publier", "accorde")
        try:
            r = self.ok("mesure_publier", SIMPLE, cle="dns.secret", visibilite="toutes")
            self.assertFalse(r["ok"])
            self.assertEqual(self.vue_pour(AUTRE, "2", cle="dns.secret")["libelle"], "")
        finally:
            self.n.droits.regler("compte", SIMPLE, "sensorium.publier", None)
        self.assertEqual(self.faire("mesure_publier", KINO, cle="dns.secret", visibilite="toutes")["statut"], "refuse", "sans le droit publier")

    def test_visibilites_illisibles_refusees(self):
        self.preparer()
        for v in ("tous", "societes:", "societes:1;2", "", None, "*"):
            self.assertFalse(self.ok("mesure_publier", ADMIN, cle="dns.secret", visibilite=v)["ok"], v)
        self.assertFalse(self.ok("mesure_publier", ADMIN, cle="dns.fantome", visibilite="toutes")["ok"])

    def test_le_detail_exige_voir_infra_meme_pour_une_cle_publiee(self):
        self.preparer()
        self.ok("mesure_publier", ADMIN, cle="dns.secret", visibilite="toutes")
        for cap in ("mesure_detail", "mesures_suivies", "autoobservation", "liens", "impact", "prevision_mesure"):
            r = self.lire(cap, SIMPLE, **({"cle": "dns.secret"} if cap in ("mesure_detail", "prevision_mesure") else {"objet": "a/b"} if cap in ("liens", "impact") else {}))
            self.assertEqual((r["statut"], r.get("droit")), ("refuse", "sensorium.voir_infra"), cap)
            self.assertNotIn(str(SECRET), json.dumps(r))

    def test_une_mesure_du_monde_publiee_se_montre_en_etat_seulement(self):
        cle = "monde.ssl.client-prive.exemple.test"
        self.ok("mesure_publier", ADMIN, cle=cle, visibilite="societes:1", libelle="Certificat du client")
        self.n.lancer("sensorium.monde")
        vu = self.vue_pour(SIMPLE, "1", cle=cle)
        self.assertEqual((vu["etat"], vu["libelle"]), ("alerte", "Certificat du client"))
        self.assertNotIn("3 jours", json.dumps(vu))
        self.assertEqual(self.vue_pour(AUTRE, "2", cle=cle)["libelle"], "")

    def test_la_voie_directe_depuis_une_societe_secondaire_reste_fermee(self):
        self.preparer()
        self.ok("mesure_publier", ADMIN, cle="dns.secret", visibilite="toutes")
        r = self.n.executeur.executer("sensorium.mesure_etat", "humain", {"cle": "dns.secret"}, compte=AUTRE)
        self.assertEqual(r["statut"], "refuse")
        self.assertIn("pas ouvert", r["raison"])


class Relations(Mesures):
    def test_lier_et_mesurer_l_impact(self):
        for de, rel, vers in (("site/exemple.test", "certifie_par", "cert/exemple.test"), ("site/exemple.test", "heberge_par", "serveur/a"),
                              ("cert/exemple.test", "depend_de", "domaine/exemple.test"), ("page/doc", "decrit", "site/exemple.test")):
            self.assertTrue(self.ok("lien_poser", KINO, de=de, relation=rel, vers=vers)["ok"])
        r = self.ok("impact", ADMIN, objet="domaine/exemple.test")
        self.assertEqual([t["objet"] for t in r["touches"]], ["cert/exemple.test", "site/exemple.test", "page/doc"])
        self.assertEqual([t["objet"] for t in self.ok("impact", ADMIN, objet="serveur/a")["touches"]], ["site/exemple.test", "page/doc"])
        l = self.ok("liens", ADMIN, objet="site/exemple.test")
        self.assertEqual(len(l["depend_de"]), 2)
        self.assertEqual(l["dependants"][0]["objet"], "page/doc")

    def test_refus_et_plafonds(self):
        for kw in (dict(de="a/b", relation="aime", vers="c/d"), dict(de="a/b", relation="depend_de", vers="a/b"), dict(de="a b", relation="depend_de", vers="c/d"),
                   dict(de="", relation="depend_de", vers="c/d"), dict(de="../x", relation="depend_de", vers="c/d")):
            self.assertFalse(self.ok("lien_poser", KINO, **kw)["ok"], kw)
        for i in range(500):
            self.assertTrue(self.ok("lien_poser", KINO, de="s/%d" % i, vers="hub")["ok"], i)
        r = self.ok("lien_poser", KINO, de="s/501", vers="hub")
        self.assertFalse(r["ok"])
        self.assertIn("plafond", r["refuse"])
        self.assertEqual(len(self.ok("impact", ADMIN, objet="hub")["touches"]), 200)
        self.assertTrue(self.ok("impact", ADMIN, objet="hub")["tronque"])

    def test_on_ne_retire_que_ses_propres_liens(self):
        self.ok("lien_poser", KINO, de="a/b", vers="c/d")
        self.assertFalse(self.ok("lien_retirer", KINO2, de="a/b", vers="c/d")["ok"], "le lien d'un autre compte")
        self.assertEqual(len(self.ok("liens", ADMIN, objet="a/b")["depend_de"]), 1)
        self.assertTrue(self.ok("lien_retirer", ADMIN, de="a/b", vers="c/d")["ok"], "un administrateur peut nettoyer")
        self.ok("lien_poser", KINO, de="a/b", vers="c/d")
        self.assertTrue(self.ok("lien_retirer", KINO, de="a/b", vers="c/d")["ok"])

    def test_retour_arriere_d_un_lien(self):
        self.ok("lien_poser", KINO, de="a/b", vers="c/d")
        self.assertTrue(self.ok("lien_retirer", KINO, de="a/b", vers="c/d")["ok"])
        self.assertEqual(self.ok("impact", ADMIN, objet="c/d")["touches"], [])

    def test_un_objet_inexistant_au_registre_peut_etre_lie(self):
        self.assertTrue(self.ok("lien_poser", KINO, de="page/bibliotheque-42", relation="decrit", vers="site/pas-encore")["ok"])


class Prevision(Mesures):
    def remplir(self, valeurs, pas=600):
        self.declarer("disque.plein", KINO, fraicheur_s=3600, alerte=80, critique=90, unite="%")
        for v in valeurs:
            self.h.avance(pas)
            self.alimenter("disque.plein", v)

    def test_combien_de_jours_avant_le_seuil(self):
        self.remplir([50 + i for i in range(10)])           # +1 point par dix minutes = +144 points par jour
        p = self.ok("prevision_mesure", ADMIN, cle="disque.plein")
        self.assertTrue(p["conclu"], p)
        self.assertEqual((p["niveau"], p["seuil"]), ("critique", 90.0))
        self.assertAlmostEqual(p["jours_avant_seuil"], (90 - 59) / 144.0, places=2)

    def test_trop_peu_de_points_ne_conclut_pas(self):
        self.remplir([50, 51, 52])
        p = self.ok("prevision_mesure", ADMIN, cle="disque.plein")
        self.assertFalse(p["conclu"])
        self.assertIn("six points", p["raison"])

    def test_une_mesure_qui_baisse_ne_s_approche_pas_du_seuil(self):
        self.remplir([70 - i for i in range(10)])
        p = self.ok("prevision_mesure", ADMIN, cle="disque.plein", niveau="alerte")
        self.assertFalse(p["conclu"])

    def test_capteur_inconnu(self):
        self.assertEqual(self.faire("prevision_mesure", ADMIN, acteur="humain", cle="x.y")["statut"], "echec")


class AutoObservation(Mesures):
    def test_les_compteurs_disent_ce_qui_est_accepte_et_refuse(self):
        self.declarer()
        self.alimenter(valeur=1)
        self.alimenter(valeur=2)                                         # trop vite
        self.faire("capteur_alimenter", KINO, lectures=[{"cle": "inconnu.x", "valeur": 1}])
        self.faire("capteur_declarer", KINO2, cle="dns.pirate")
        a = self.ok("autoobservation", ADMIN)
        self.assertEqual((a["capteurs"], a["lectures"], a["espaces"]), (1, 1, 1))
        self.assertEqual(a["compteurs"]["lectures_acceptees"], 1)
        self.assertEqual(a["compteurs"]["lectures_refusees"], 2)
        self.assertEqual(a["compteurs"]["refus_espace_autre"], 1)
        self.assertEqual(a["plafonds"]["capteurs_par_compte"], 50)
        self.assertTrue(a["horloge_fiable"])

    def test_le_tour_de_suivi_se_voit(self):
        self.n.lancer("sensorium.suivi_mesures")
        a = self.ok("autoobservation", ADMIN)
        self.assertEqual(a["compteurs"]["tours_suivi"], 1)
        self.assertIsNotNone(a["dernier_tour_suivi_il_y_a_s"])
        self.h.avance(400)
        self.assertTrue(self.ok("autoobservation", ADMIN)["suivi_en_retard"])


class Compatibilite(Mesures):
    def test_les_lectures_existantes_ne_changent_pas_pour_un_administrateur(self):
        etat = self.ok("etat", ADMIN)
        self.assertTrue(etat["ok"])
        self.assertEqual({r["wkey"] for r in etat["rows"]}, {r["wkey"] for r in MONDE})
        self.assertEqual(self.ok("monde", ADMIN)[0]["wkey"], "system.hostname")

    def test_le_releve_du_monde_survit_a_une_ingestion_en_panne(self):
        capt = self.n.catalogue.get("sensorium.secu").faire.__globals__["capt"]
        with mock.patch.object(capt, "ingerer_monde", side_effect=RuntimeError("base fermée")):
            r = self.n.lancer("sensorium.monde")
        self.assertEqual(r.get("statut"), "fait")
        self.assertTrue(self.ok("etat", ADMIN)["rows"], "l'écran lit toujours le monde")


MANIFESTE_EMETTEUR = """[module]
id = "emetteur"
nom = "Émetteur d'essai"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Un module du noyau qui nourrit un capteur du Sensorium, comme le fera le Serveur DNS."
importance = "optionnel"
sans = "Rien : c'est un module d'essai."

[[droits]]
id = "voir"
libelle = "Voir l'émetteur d'essai"

[[moteurs]]
id = "pousser"
libelle = "Déclare, alimente et suit un capteur"
mode = "periodique"
toutes_les_s = 30
duree_max_s = 10

[permissions]
agir = true
agir_moteur = ["sensorium.capteur_declarer", "sensorium.capteur_alimenter", "sensorium.mesure_suivre"]
"""
CODE_EMETTEUR = """
def brancher(ctx):
    def pousser(ctx):
        a = lambda cap, **args: ctx.agir(cap, args, acteur="cassandra")
        etat["declare"] = a("sensorium.capteur_declarer", cle="dns.latence_locale", libelle="Latence du résolveur local", unite="ms", fraicheur_s=120, alerte=150, critique=800)
        etat["alimente"] = a("sensorium.capteur_alimenter", lectures=[{"cle": "dns.latence_locale", "valeur": etat["valeur"], "confiance": 0.9}])
        etat["suit"] = a("sensorium.mesure_suivre", cle="dns.latence_locale", motif="essai")
    etat = {"valeur": 42}
    ctx.moteur("pousser", pousser)
    ctx.etat_essai = etat
"""


class ViaUnModule(Mesures):
    """La voie prévue pour le Serveur DNS : un module du noyau, depuis son moteur, par ctx.agir (compte système « noyau », acteur « cassandra »)."""
    MODULES = ("droits", "modules", "sensorium", "emetteur")

    @classmethod
    def poser_modules_d_essai(cls, mods):
        (mods / "emetteur").mkdir(parents=True)
        (mods / "emetteur" / "CN_manifeste.toml").write_text(MANIFESTE_EMETTEUR, encoding="utf-8")
        (mods / "emetteur" / "CN_module.py").write_text(CODE_EMETTEUR, encoding="utf-8")

    def test_un_module_declare_alimente_et_suit_depuis_son_moteur(self):
        self.assertEqual(self.n.lancer("emetteur.pousser").get("statut"), "fait")
        etat = self.n.executeur.contextes["emetteur"].etat_essai
        self.assertEqual((etat["declare"]["statut"], etat["alimente"]["statut"], etat["suit"]["statut"]), ("faite", "faite", "faite"), etat)
        d = self.ok("mesure_detail", ADMIN, cle="dns.latence_locale")
        self.assertEqual((d["etat"], d["valeur"], d["capteur"]["proprietaire"]), ("ok", 42.0, "noyau"))
        self.assertEqual(d["suivie_par"], ["noyau"])
        self.h.avance(2)
        self.n.executeur.contextes["emetteur"].etat_essai["valeur"] = 900
        self.n.lancer("emetteur.pousser")
        evs = self.evenements()
        self.assertEqual([(e["donnees"]["avant"], e["donnees"]["apres"], e["compte"]) for e in evs][-1], ("ok", "alerte", "noyau"))

    def test_un_module_hors_de_sa_liste_ne_peut_pas_agir(self):
        ctx = self.n.executeur.contextes["emetteur"]
        ctx._en_moteur.valeur = True
        try:
            with self.assertRaises(PermissionError):
                ctx.agir("sensorium.mesure_publier", {"cle": "dns.x", "visibilite": "toutes"}, acteur="cassandra")
        finally:
            ctx._en_moteur.valeur = False


class SuiviEtVisibilite(Mesures):
    """Un suiveur ne reçoit des événements que pour ce qu'il peut encore voir (docs/CN_SENSORIUM_EVOLUTION.md §4 bis)."""

    def setUp(self):
        super().setUp()
        self.n.droits.regler("compte", SIMPLE, "sensorium.suivre", "accorde")
        self.addCleanup(self.n.droits.regler, "compte", SIMPLE, "sensorium.suivre", None)
        self.declarer("infra.cert", KINO, fraicheur_s=600, alerte=50)
        self.alimenter("infra.cert", 1)

    def pour(self, compte):
        return [e for e in self.evenements() if e["compte"] == compte]

    def test_fuite_un_suiveur_depublie_ne_recoit_plus_rien(self):
        self.ok("mesure_publier", ADMIN, cle="infra.cert", visibilite="toutes")
        self.assertTrue(self.ok("mesure_suivre", SIMPLE, cle="infra.cert")["ok"])
        self.ok("mesure_publier", ADMIN, cle="infra.cert", visibilite="instance")
        self.assertEqual(self.vue_pour(SIMPLE, "1", cle="infra.cert")["etat"], "inconnu")
        self.h.avance(40)
        self.alimenter("infra.cert", 99)                       # le capteur passe en alerte
        self.assertEqual(self.pour(SIMPLE), [], "l'événement est parti vers un compte qui ne voit plus la mesure")
        self.assertGreater(self.ok("autoobservation", ADMIN)["compteurs"].get("evenements_masques", 0), 0)

    def test_republier_rend_les_evenements_sans_re_suivre(self):
        self.ok("mesure_publier", ADMIN, cle="infra.cert", visibilite="toutes")
        self.ok("mesure_suivre", SIMPLE, cle="infra.cert")
        self.ok("mesure_publier", ADMIN, cle="infra.cert", visibilite="instance")
        self.h.avance(40)
        self.alimenter("infra.cert", 99)
        self.ok("mesure_publier", ADMIN, cle="infra.cert", visibilite="toutes")
        self.h.avance(40)
        self.alimenter("infra.cert", 1)
        self.assertEqual([e["donnees"]["apres"] for e in self.pour(SIMPLE)], ["ok"], "le suivi n'a jamais été retiré : il était muet")

    def test_un_suiveur_qui_voit_toujours_recoit(self):
        self.ok("mesure_publier", ADMIN, cle="infra.cert", visibilite="societes:1")
        self.ok("mesure_suivre", SIMPLE, cle="infra.cert")
        self.h.avance(40)
        self.alimenter("infra.cert", 99)
        self.assertEqual([e["donnees"]["apres"] for e in self.pour(SIMPLE)][-1], "alerte")

    def test_fuite_les_chiffres_de_la_raison_ne_vont_qu_aux_suiveurs_privilegies(self):
        self.ok("mesure_publier", ADMIN, cle="infra.cert", visibilite="societes:1")
        self.ok("mesure_suivre", SIMPLE, cle="infra.cert")
        self.ok("mesure_suivre", ADMIN, cle="infra.cert")
        self.h.avance(61)
        self.n.lancer("sensorium.suivi_mesures")
        self.h.avance(700)
        self.n.lancer("sensorium.suivi_mesures")
        simple, admin = self.pour(SIMPLE), self.pour(ADMIN)
        self.assertTrue(simple and admin)
        self.assertEqual(simple[-1]["donnees"]["raison"], "muette")
        self.assertRegex(admin[-1]["donnees"]["raison"], r"muette depuis \d+ s \(attendue toutes les \d+ s\)")

    def test_un_suiveur_d_une_autre_societe_ne_recoit_que_si_sa_societe_est_publiee(self):
        db = self.n.executeur.contextes["sensorium"].stockage
        db.ecrire("INSERT INTO sensorium_suivies(cle, suiveur, motif, cree_le) VALUES ('infra.cert', ?, '', 0)", (AUTRE,))
        self.ok("mesure_publier", ADMIN, cle="infra.cert", visibilite="societes:1")
        self.h.avance(40)
        self.alimenter("infra.cert", 99)
        self.assertEqual(self.pour(AUTRE), [])


class Privilege(Mesures):
    """La règle du compte vide (docs/CN_SENSORIUM_EVOLUTION.md §6 bis) : un moteur sans compte lit en PRIVILÉGIÉ ; s'il travaille pour quelqu'un il passe `pour`, et ne regarde jamais plus que lui."""

    def lecture(self, compte, societe, cle, **extra):
        lecture = self.n.executeur.contextes["sensorium"]._intro["lecture"]
        return lecture("sensorium.mesure_etat", dict(cle=cle, **extra), compte, societe)

    def setUp(self):
        super().setUp()
        self.declarer("dns.interne", KINO)
        self.alimenter("dns.interne", 5)

    def test_un_moteur_sans_compte_lit_en_privilegie(self):
        self.assertEqual(self.lecture("", "", "dns.interne")["etat"], "ok")

    def test_pour_restreint_un_moteur_a_la_vue_de_celui_pour_qui_il_travaille(self):
        self.assertEqual(self.lecture("", "", "dns.interne", pour=SIMPLE)["etat"], "inconnu")
        self.assertEqual(self.lecture("", "", "dns.interne", pour="*")["libelle"], "")
        self.ok("mesure_publier", ADMIN, cle="dns.interne", visibilite="societes:2")
        self.assertEqual(self.lecture("", "", "dns.interne", pour=AUTRE)["etat"], "ok")
        self.assertEqual(self.lecture("", "", "dns.interne", pour=SIMPLE)["libelle"], "", "SIMPLE est dans la société 1")
        self.assertEqual(self.lecture("", "", "dns.interne", pour="*")["libelle"], "", "personne : seulement « toutes »")
        self.ok("mesure_publier", ADMIN, cle="dns.interne", visibilite="toutes")
        self.assertEqual(self.lecture("", "", "dns.interne", pour="*")["etat"], "ok")

    def test_un_compte_ordinaire_ne_gagne_rien_a_passer_pour(self):
        for pour in (ADMIN, "", None, "noyau", "*"):
            r = self.lecture(SIMPLE, "1", "dns.interne", pour=pour)
            self.assertEqual((r["etat"], r["libelle"]), ("inconnu", ""), pour)
        self.ok("mesure_publier", ADMIN, cle="dns.interne", visibilite="societes:2")
        self.assertEqual(self.lecture(SIMPLE, "1", "dns.interne", pour=AUTRE)["libelle"], "", "il ne prend pas la vue d'un autre")

    def test_un_module_du_noyau_agissant_sous_noyau_est_privilegie(self):
        ctx = self.n.executeur.contextes["sensorium"]
        ctx._compte.valeur = "noyau"
        try:
            self.assertTrue(self.g["privilegie"](ctx))
        finally:
            ctx._compte.valeur = ""


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Horloge, Mesures, Capteurs, Etat, Suivi, VueMinimale, Relations, Prevision …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
