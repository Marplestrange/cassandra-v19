# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'état d'une mesure (fonctions pures du Sensorium)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #f2129e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'état d'une mesure (fonctions pures du Sensorium) : tri-état, fraîcheur, confiance, horloge, fusion des annonces, visibilité, prévision, impact.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=f2129e ▼▼▼
"""Bancs de l'état d'une mesure (fonctions pures du Sensorium) : tri-état, fraîcheur, confiance, horloge, fusion des annonces, visibilité, prévision, impact."""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "modules" / "sensorium"))
import CN_mesures_etat as e  # noqa: E402

T = 1_800_000_000.0                 # une horloge fiable


def pente_simple(pts):
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    syy = sum((p[1] - my) ** 2 for p in pts)
    a = sxy / sxx
    return a, (sxy * sxy) / (sxx * syy) if syy else 0.0


class Etat(unittest.TestCase):
    CAP = {"fraicheur_s": 60, "confiance_min": 0.4}

    def test_sans_lecture_c_est_inconnu_jamais_ok(self):
        r = e.calculer_etat(None, self.CAP, T)
        self.assertEqual((r["etat"], r["raison"]), ("inconnu", "jamais lue"))

    def test_une_lecture_fraiche_et_saine_est_ok(self):
        self.assertEqual(e.calculer_etat({"recu_a": T - 10, "gravite": "ok"}, self.CAP, T)["etat"], "ok")

    def test_une_lecture_en_alerte(self):
        r = e.calculer_etat({"recu_a": T - 10, "gravite": "critical"}, self.CAP, T)
        self.assertEqual((r["etat"], r["niveau"]), ("alerte", "critical"))

    def test_un_capteur_muet_n_est_pas_ok_meme_si_sa_derniere_lecture_l_etait(self):
        r = e.calculer_etat({"recu_a": T - 61, "gravite": "ok"}, self.CAP, T)
        self.assertEqual(r["etat"], "inconnu")
        self.assertIn("muette", r["raison"])

    def test_un_capteur_muet_ne_cache_pas_une_alerte(self):
        self.assertEqual(e.calculer_etat({"recu_a": T - 9999, "gravite": "critical"}, self.CAP, T)["etat"], "inconnu")

    def test_la_frontiere_de_fraicheur_est_incluse(self):
        self.assertEqual(e.calculer_etat({"recu_a": T - 60, "gravite": "ok"}, self.CAP, T)["etat"], "ok")

    def test_confiance_insuffisante_donne_inconnu(self):
        r = e.calculer_etat({"recu_a": T, "gravite": "ok", "confiance": 0.2}, self.CAP, T)
        self.assertEqual(r["etat"], "inconnu")
        self.assertIn("confiance", r["raison"])

    def test_horloge_non_fiable_donne_inconnu_pour_tout(self):
        for maintenant in (0.0, 86400.0, e.HORLOGE_MIN - 1):
            self.assertEqual(e.calculer_etat({"recu_a": maintenant, "gravite": "ok"}, self.CAP, maintenant)["etat"], "inconnu")

    def test_lecture_du_futur_horloge_reculee(self):
        r = e.calculer_etat({"recu_a": T + 10_000, "gravite": "ok"}, self.CAP, T)
        self.assertEqual(r["etat"], "inconnu")
        self.assertIn("reculé", r["raison"])

    def test_petit_recul_d_horloge_ne_donne_pas_un_age_negatif(self):
        r = e.calculer_etat({"recu_a": T + 5, "gravite": "ok"}, self.CAP, T)
        self.assertEqual((r["etat"], r["age_s"]), ("ok", 0.0))

    def test_gravite_illisible_n_est_pas_une_alerte_inventee(self):
        self.assertEqual(e.calculer_etat({"recu_a": T, "gravite": "n'importe quoi"}, self.CAP, T)["etat"], "ok")

    def test_sans_declaration_une_fraicheur_par_defaut_s_applique(self):
        self.assertEqual(e.calculer_etat({"recu_a": T - 301, "gravite": "ok"}, None, T)["etat"], "inconnu")


class Seuils(unittest.TestCase):
    def test_pire_haut(self):
        g = lambda v: e.gravite_des_seuils(v, 70, 90, "haut")
        self.assertEqual([g(10), g(70), g(89), g(90)], ["ok", "warning", "warning", "critical"])

    def test_pire_bas(self):
        g = lambda v: e.gravite_des_seuils(v, 20, 5, "bas")
        self.assertEqual([g(50), g(20), g(6), g(5)], ["ok", "warning", "warning", "critical"])

    def test_valeur_non_numerique_ou_booleenne_n_alerte_pas(self):
        for v in ("beaucoup", None, True, float("nan"), float("inf")):
            self.assertEqual(e.gravite_des_seuils(v, 1, 2), "ok")


class Confiance(unittest.TestCase):
    def test_defaut_et_bornes(self):
        self.assertEqual(e.confiance_effective(None), 1.0)
        self.assertEqual(e.confiance_effective(7), 1.0)
        self.assertEqual(e.confiance_effective(-3), 0.0)

    def test_une_heure_fausse_abaisse_la_confiance(self):
        self.assertEqual(e.confiance_effective(0.9, 4000), 0.5)
        self.assertEqual(e.confiance_effective(0.9, 10), 0.9)

    def test_decalage(self):
        self.assertEqual(e.decalage(T + 40, T), 40.0)
        self.assertIsNone(e.decalage(None, T))
        self.assertIsNone(e.decalage("demain", T))


class Cles(unittest.TestCase):
    def test_cles(self):
        for ok in ("dns.latence", "monde.ssl.exemple.test", "kino-lyon.horloge:derive", "a"):
            self.assertTrue(e.cle_valide(ok), ok)
        for ko in ("", "A.majuscule", ".point", "avec espace", "x" * 121, None, 5, "a;b", "../etc"):
            self.assertFalse(e.cle_valide(ko), ko)

    def test_espace(self):
        self.assertEqual(e.espace_de("dns.resolveur.latence"), "dns")
        self.assertEqual(e.espace_de("monde:ssl"), "monde")


class Annonces(unittest.TestCase):
    def test_pas_de_changement_pas_d_annonce(self):
        self.assertFalse(e.doit_annoncer("ok", "ok", None, T))

    def test_premier_changement_s_annonce(self):
        self.assertTrue(e.doit_annoncer("ok", "alerte", None, T))

    def test_le_va_et_vient_est_fusionne(self):
        self.assertFalse(e.doit_annoncer("ok", "alerte", T - 5, T))
        self.assertTrue(e.doit_annoncer("ok", "alerte", T - 30, T))


class Visibilite(unittest.TestCase):
    def test_defaut_personne_sauf_les_privilegies(self):
        self.assertFalse(e.visible_pour("instance", "1", False))
        self.assertFalse(e.visible_pour(None, "1", False))
        self.assertTrue(e.visible_pour("instance", "1", True))

    def test_publiee_pour_certaines_societes(self):
        self.assertTrue(e.visible_pour("societes:1,2", "2", False))
        self.assertFalse(e.visible_pour("societes:1,2", "3", False))
        self.assertFalse(e.visible_pour("societes:1,2", "", False))
        self.assertFalse(e.visible_pour("societes:1,2", "12", False), "pas de correspondance par préfixe")

    def test_toutes(self):
        self.assertTrue(e.visible_pour("toutes", "", False))

    def test_valeurs_de_visibilite(self):
        for ok in ("instance", "toutes", "societes:1", "societes:a_b,c-d"):
            self.assertTrue(e.visibilite_valide(ok), ok)
        for ko in ("", "societes:", "societes:1,", "tous", "societes:1;2", None, 3):
            self.assertFalse(e.visibilite_valide(ko), ko)

    def test_la_vue_minimale_n_a_que_quatre_champs_et_une_raison(self):
        m = e.minimal("dns.x", "DNS", {"etat": "ok", "raison": ""}, 5.0)
        self.assertEqual(set(m), {"cle", "libelle", "etat", "depuis", "raison"})

    def test_invisible_et_inconnu_se_ressemblent(self):
        self.assertEqual(e.invisible("a.b"), {"cle": "a.b", "libelle": "", "etat": "inconnu", "depuis": None, "raison": ""})


class Prevision(unittest.TestCase):
    def test_montee_reguliere(self):
        pts = [(j, 50 + 2 * j) for j in range(10)]         # 68 au dernier point, +2 par jour
        r = e.prevision(pts, 100, "haut", pente_simple)
        self.assertTrue(r["conclu"])
        self.assertAlmostEqual(r["jours_avant_seuil"], 16.0, places=1)

    def test_baisse_vers_un_seuil_bas(self):
        pts = [(j, 80 - 5 * j) for j in range(8)]          # 45 au dernier point
        r = e.prevision(pts, 20, "bas", pente_simple)
        self.assertTrue(r["conclu"])
        self.assertAlmostEqual(r["jours_avant_seuil"], 5.0, places=1)

    def test_trop_peu_de_points(self):
        r = e.prevision([(0, 1), (1, 2), (2, 3)], 10, "haut", pente_simple)
        self.assertFalse(r["conclu"])

    def test_mauvais_cote(self):
        pts = [(j, 50 - j) for j in range(10)]
        r = e.prevision(pts, 100, "haut", pente_simple)
        self.assertFalse(r["conclu"])
        self.assertIn("ne s'approche pas", r["raison"])

    def test_tendance_irreguliere_ne_conclut_pas(self):
        pts = [(0, 10), (1, 90), (2, 5), (3, 85), (4, 12), (5, 80), (6, 11)]
        r = e.prevision(pts, 100, "haut", pente_simple)
        self.assertFalse(r["conclu"])

    def test_seuil_deja_atteint(self):
        pts = [(j, 90 + j) for j in range(8)]
        self.assertEqual(e.prevision(pts, 95, "haut", pente_simple)["jours_avant_seuil"], 0.0)

    def test_sans_seuil(self):
        self.assertFalse(e.prevision([(j, j) for j in range(8)], None, "haut", pente_simple)["conclu"])

    def test_points_pollues_ignores(self):
        pts = [(j, 10 + j) for j in range(8)] + [("x", 3), (3, None), (4, True)]
        self.assertTrue(e.prevision(pts, 100, "haut", pente_simple)["conclu"])


class Impact(unittest.TestCase):
    LIENS = [("site/exemple.test", "depend_de", "cert/exemple.test"), ("site/exemple.test", "depend_de", "serveur/a"),
             ("cert/exemple.test", "depend_de", "domaine/exemple.test"), ("page/doc", "depend_de", "site/exemple.test")]

    def test_remonte_les_dependances(self):
        r = e.impact(self.LIENS, "domaine/exemple.test")
        self.assertEqual([t["objet"] for t in r["touches"]], ["cert/exemple.test", "site/exemple.test", "page/doc"])
        self.assertEqual([t["distance"] for t in r["touches"]], [1, 2, 3])
        self.assertFalse(r["tronque"])

    def test_une_boucle_ne_boucle_pas(self):
        liens = [("a", "depend_de", "b"), ("b", "depend_de", "a")]
        r = e.impact(liens, "a")
        self.assertEqual([t["objet"] for t in r["touches"]], ["b"])

    def test_profondeur_bornee_et_dite(self):
        liens = [("n%d" % (i + 1), "depend_de", "n%d" % i) for i in range(20)]
        r = e.impact(liens, "n0", profondeur=3)
        self.assertEqual(len(r["touches"]), 3)
        self.assertTrue(r["tronque"])

    def test_nombre_de_noeuds_borne_et_dit(self):
        liens = [("x%d" % i, "depend_de", "racine") for i in range(50)]
        r = e.impact(liens, "racine", noeuds_max=10)
        self.assertEqual(len(r["touches"]), 10)
        self.assertTrue(r["tronque"])

    def test_objet_sans_dependant(self):
        self.assertEqual(e.impact(self.LIENS, "page/doc")["touches"], [])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : pente_simple, Etat, Seuils, Confiance, Cles, Annonces, Visibilite, Prevision …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
