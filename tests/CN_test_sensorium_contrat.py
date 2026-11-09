# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Tests de contrat des mesures du Sensorium (docs/CN_SENSORIUM_EVOLUTION
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #129266
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Tests de contrat des mesures du Sensorium (docs/CN_SENSORIUM_EVOLUTION.md §15), écrits pour s'exécuter contre N'IMPORTE QUELLE implémentation par le canal du protocole.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=129266 ▼▼▼
"""Tests de contrat des mesures du Sensorium (docs/CN_SENSORIUM_EVOLUTION.md §15), écrits pour s'exécuter contre N'IMPORTE QUELLE implémentation par le canal du protocole.

Seule la fonction `appeler(nom, **champs)` connaît le transport : ici l'exécuteur du noyau Python (l'étalon) ; un client d'un autre collecteur la remplacerait. Les bancs ne regardent que le JSON rendu."""
import sys
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from tests.CN_test_sensorium_mesures import ADMIN, KINO, T0, Mesures  # noqa: E402

T = {"bool": bool, "str": str, "num": (int, float), "list": list, "dict": dict}
# (champ, type, peut être None)
FORMES = {
    "capteur_declarer": [("ok", "bool", 0), ("cle", "str", 0), ("espace", "str", 0), ("nouveau", "bool", 0), ("espace_nouveau", "bool", 0)],
    "capteur_alimenter": [("ok", "bool", 0), ("acceptees", "list", 0), ("refusees", "list", 0), ("t", "num", 0)],
    "mesure_etat": [("cle", "str", 0), ("libelle", "str", 0), ("etat", "str", 0), ("depuis", "num", 1), ("raison", "str", 0)],
    "vue_minimale": [("mesures", "list", 0), ("maintenant", "num", 0)],
    "mesure_detail": [(c, t, 1) for c, t in (("cle", "str"), ("libelle", "str"), ("unite", "str"), ("etat", "str"), ("raison", "str"), ("age_s", "num"), ("depuis", "num"),
                                               ("valeur", "num"), ("gravite", "str"), ("observe_a", "num"), ("recu_a", "num"), ("confiance", "num"), ("decalage_s", "num"),
                                               ("detail", "str"), ("capteur", "dict"), ("visibilite", "str"), ("suivie_par", "list"))],
    "prevision_mesure": [("conclu", "bool", 0), ("raison", "str", 0), ("cle", "str", 0), ("niveau", "str", 0), ("seuil", "num", 1), ("points", "num", 0)],
    "impact": [("depart", "str", 0), ("touches", "list", 0), ("tronque", "bool", 0)],
    "liens": [("objet", "str", 0), ("depend_de", "list", 0), ("dependants", "list", 0)],
    "lien_poser": [("ok", "bool", 0), ("de", "str", 0), ("relation", "str", 0), ("vers", "str", 0), ("nouveau", "bool", 0)],
}
CLES_EVENEMENT = {"cle", "avant", "apres", "depuis", "raison", "suiveur"}
CLES_MINIMALES = {"cle", "libelle", "etat", "depuis", "raison"}


class Contrat(Mesures):
    def appeler(self, nom, _compte=None, **champs):
        """LE canal : à remplacer pour tester une autre implémentation."""
        compte = _compte or (KINO if nom in ("capteur_declarer", "capteur_alimenter", "lien_poser") else ADMIN)
        return self.ok(nom, compte, **champs)

    def conforme(self, nom, rep):
        for champ, typ, nul in FORMES[nom]:
            self.assertIn(champ, rep, (nom, champ))
            if rep[champ] is None:
                self.assertTrue(nul, (nom, champ, "ne peut pas être nul"))
            else:
                self.assertIsInstance(rep[champ], T[typ], (nom, champ))
        return rep

    def monter(self, valeur=10, **kw):
        self.conforme("capteur_declarer", self.appeler("capteur_declarer", cle="dns.latence", fraicheur_s=60, alerte=100, critique=300, pire="haut", confiance_min=0.4))
        return self.conforme("capteur_alimenter", self.appeler("capteur_alimenter", lectures=[dict(cle="dns.latence", valeur=valeur, **kw)]))

    def test_formes_des_reponses(self):
        r = self.monter()
        self.assertEqual((r["acceptees"], r["refusees"]), (["dns.latence"], []))
        self.conforme("mesure_etat", self.appeler("mesure_etat", cle="dns.latence"))
        self.conforme("mesure_detail", self.appeler("mesure_detail", cle="dns.latence"))
        self.conforme("vue_minimale", self.appeler("vue_minimale"))
        self.conforme("prevision_mesure", self.appeler("prevision_mesure", cle="dns.latence"))
        self.conforme("lien_poser", self.appeler("lien_poser", de="site/a", relation="depend_de", vers="dns/b"))
        self.conforme("impact", self.appeler("impact", objet="dns/b"))
        self.conforme("liens", self.appeler("liens", objet="site/a"))

    def test_une_lecture_refusee_porte_un_motif_dans_la_reponse_pas_dans_une_erreur(self):
        self.monter()
        r = self.appeler("capteur_alimenter", lectures=[{"cle": "inconnu.x", "valeur": 1}, {"cle": "dns.latence", "valeur": 2}])
        self.assertEqual(r["acceptees"], [])
        self.assertEqual({x["motif"] for x in r["refusees"]}, {"capteur non déclaré", "trop_vite"})
        for x in r["refusees"]:
            self.assertEqual(set(x), {"cle", "motif"})

    def test_semantique_etat(self):
        """§15 règle 1 et 3 : cas fixes."""
        self.monter(valeur=10)
        self.assertEqual(self.appeler("mesure_etat", cle="dns.latence")["etat"], "ok")
        self.h.avance(2)
        self.appeler("capteur_alimenter", lectures=[{"cle": "dns.latence", "valeur": 100}])
        d = self.appeler("mesure_detail", cle="dns.latence")
        self.assertEqual((d["etat"], d["gravite"]), ("alerte", "warning"), "valeur == alerte")
        self.h.avance(2)
        self.appeler("capteur_alimenter", lectures=[{"cle": "dns.latence", "valeur": 300}])
        self.assertEqual(self.appeler("mesure_detail", cle="dns.latence")["gravite"], "critical", "valeur == critique")
        self.h.avance(61)
        self.assertEqual(self.appeler("mesure_etat", cle="dns.latence")["etat"], "inconnu", "maintenant - recu_a > fraicheur_s")
        self.h.avance(-60)                                                  # exactement la frontière: incluse
        self.appeler("capteur_alimenter", lectures=[{"cle": "dns.latence", "valeur": 1}])
        self.h.avance(60)
        self.assertEqual(self.appeler("mesure_etat", cle="dns.latence")["etat"], "ok")

    def test_semantique_horloge_de_l_emetteur_et_confiance(self):
        self.monter(valeur=1, observe_a=T0 - 5000, confiance=0.9)
        d = self.appeler("mesure_detail", cle="dns.latence")
        self.assertEqual(d["etat"], "ok")
        self.assertEqual(d["confiance"], 0.5)
        self.assertLess(d["decalage_s"], -300)

    def test_semantique_evenement_et_fusion(self):
        self.conforme("capteur_declarer", self.appeler("capteur_declarer", cle="dns.latence", fraicheur_s=60, alerte=100))
        self.appeler("mesure_suivre", cle="dns.latence")
        self.appeler("capteur_alimenter", lectures=[{"cle": "dns.latence", "valeur": 1}])
        self.h.avance(31)
        self.appeler("capteur_alimenter", lectures=[{"cle": "dns.latence", "valeur": 500}])
        evs = self.evenements()
        self.assertEqual(len(evs), 2)
        for e in evs:
            self.assertEqual(set(e["donnees"]), CLES_EVENEMENT)
        self.assertEqual((evs[0]["donnees"]["avant"], evs[0]["donnees"]["apres"]), ("inconnu", "ok"))
        self.assertEqual((evs[1]["donnees"]["avant"], evs[1]["donnees"]["apres"]), ("ok", "alerte"))

    def test_semantique_visibilite_et_vue_minimale(self):
        self.monter(valeur=4242)
        m = self.vue_pour("simple@exemple.test", "1", cle="dns.latence")
        fantome = self.vue_pour("simple@exemple.test", "1", cle="dns.n.existe.pas")
        self.assertEqual(set(m), CLES_MINIMALES)
        self.assertEqual({k: v for k, v in m.items() if k != "cle"}, {k: v for k, v in fantome.items() if k != "cle"})
        self.appeler("mesure_publier", cle="dns.latence", visibilite="toutes")
        vu = self.vue_pour("simple@exemple.test", "1", cle="dns.latence")
        self.assertEqual(set(vu), CLES_MINIMALES)
        self.assertNotIn("4242", str(vu))

    def test_semantique_plafonds(self):
        for i in range(50):
            self.appeler("capteur_declarer", cle="dns.c%d" % i)
        r = self.appeler("capteur_declarer", cle="dns.c50")
        self.assertFalse(r["ok"])
        self.assertIn("refuse", r)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Contrat
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
