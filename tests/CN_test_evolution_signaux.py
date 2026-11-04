# ══════════════════════════════════════════════
# TITRE      : Bancs de ce qu'Évolution dit aux autres modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #04c257
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Prouve qu'Évolution déclare et sert ses constats (Notifications), son signal (Aujourd'hui) et ses mesures (Mesures), sans rien inventer et sans faire une alerte d'un retour demandé.
# MÉTHODE    : le banc du module Évolution ; on rompt la chaîne, on fait retirer une pièce par le disjoncteur, et on lit ce que le détecteur, le signal et les séries disent.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=04c257 ▼▼▼
"""Bancs : Évolution parle aux autres modules par ses déclarations (détecteur, signal, mesures), jamais en écrivant chez eux."""
import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))

import CN_test_evolution_module as TM  # noqa: E402


class Signaux(TM.Banc):
    def evo(self):
        return self.n.executeur.contextes["evolution"].evolution()

    def constats(self):
        f = [f for (m, d, f) in self.n.detecteurs if d.id == "evolution_alertes"][0]
        return f(None)

    def signal(self):
        return self.ex("signal_evolution")["resultat"]["items"]

    def test_evolution_declare_son_detecteur_son_signal_et_ses_mesures(self):
        ids = {d.id for (mod, d, f) in self.n.detecteurs if mod == "evolution"}
        self.assertEqual(ids, {"evolution_alertes"})
        r = self.ex("serie", {"mesure": "evolution_essais"})
        self.assertEqual(r["statut"], "faite", r)
        self.assertIn("series", r["resultat"])

    def test_tout_va_bien_donc_rien_a_dire(self):
        self.assertEqual(self.signal(), [])
        sans_bac = [c for c in self.constats() if c["objet"][0] != "evolution_bac"]       # l'absence du bac dépend de l'hôte qui lance le banc
        self.assertEqual(sans_bac, [])

    def test_une_chaine_rompue_brule_et_se_dit_critique(self):
        self.proposer_stable({"point": "labo.somme_min"})
        evo = self.evo()
        with closing(sqlite3.connect(str(evo.rejeu.chemin.parent / "evolution.db"))) as c:         # `with` seul valide la transaction mais ne referme pas : Windows garderait le fichier
            c.execute("UPDATE chaine SET details='{\"ec\": \"EC9\"}' WHERE seq=1")
            c.commit()
        brule = [x for x in self.signal() if x["bande"] == "brule"]
        self.assertEqual(len(brule), 1, brule)
        self.assertEqual(brule[0]["ou"], "evolution")
        crit = [c for c in self.constats() if c["objet"][0] == "evolution_chaine"]
        self.assertEqual([c["niveau"] for c in crit], ["critique"])

    def test_une_amelioration_retiree_par_le_disjoncteur_est_a_regarder(self):
        self.proposer_stable({"point": "labo.somme_min"})
        evo = self.evo()
        p = evo.pieces()[0]
        evo._retirer(p, "suspendue par le disjoncteur : écart avec la référence")
        regarder = [x for x in self.signal() if x["bande"] == "regarder"]
        self.assertEqual(len(regarder), 1, regarder)
        self.assertIn("labo.somme_min", regarder[0]["titre"])
        c = [c for c in self.constats() if c["objet"][0] == "evolution_piece"]
        self.assertEqual([x["niveau"] for x in c], ["attention"])

    def test_un_retour_demande_par_l_admin_n_est_pas_une_alerte(self):
        self.proposer_stable({"point": "labo.somme_min"})
        self.ex("retour", {"point": "labo.somme_min", "raison": "essai"})
        self.assertEqual(self.signal(), [])
        self.assertEqual([c for c in self.constats() if c["objet"][0] == "evolution_piece"], [])

    def test_les_series_disent_les_retraits_et_refusent_une_mesure_inconnue(self):
        self.proposer_stable({"point": "labo.somme_min"})
        self.ex("retour", {"point": "labo.somme_min", "raison": "essai"})
        r = self.ex("serie", {"mesure": "evolution_retraits"})["resultat"]["series"][0]["points"]
        self.assertEqual(len(r), 1)
        self.assertNotEqual(self.ex("serie", {"mesure": "magie"})["statut"], "faite")

    def test_un_compte_ordinaire_ne_lit_pas_le_signal(self):
        r = self.n.executeur.executer("evolution.signal_evolution", "humain", {}, compte="bea")
        self.assertNotEqual(r["statut"], "faite")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (des bancs).
# CN : tout ce fichier est du nexus : les bancs des déclarations d'Évolution aux autres modules.
# LIEN : modules/evolution (constats, signal_evolution, serie), modules/jour, modules/notifications, modules/mesures.
