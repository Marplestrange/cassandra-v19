# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'unicité des identifiants de réglage
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #000000
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Un même identifiant de réglage ne se déclare pas dans deux modules, sauf exception écrite et justifiée : deux réglages de même nom qui disent des choses différentes finissent par être pris l'un pour l'autre.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
"""Un même identifiant de réglage ne se déclare pas dans deux modules, sauf exception écrite et justifiée : deux réglages de même nom qui disent des choses différentes finissent par être pris l'un pour l'autre."""
import sys
import tomllib
import unittest
from collections import defaultdict
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# identifiant -> (modules autorisés, pourquoi). Chaque module est qualifié (« module.reglage »), donc sans collision réelle ; la raison dit
# pourquoi ce n'est pas la même donnée. Ne l'allonger qu'avec une raison écrite : sinon, RENOMMER (voir les réglages d'envoi de courriel : la billetterie
# a « courriels_* » pour la société, le courrier « smtp_* » pour la boîte personnelle).
EXCEPTIONS = {
    "delai": ({"dolibarr", "fastpanel"}, "délai d'attente des requêtes vers deux services externes distincts"),
    "delai_s": ({"certificats", "courrier", "flotte", "web"}, "délai d'attente, en secondes, d'une connexion propre à chaque module (port 443, IMAP, SSH, page)"),
    "jeton": ({"fastpanel", "telegram"}, "jeton d'accès de deux services différents (API FastPanel, robot Telegram)"),
    "url": ({"dolibarr", "fastpanel"}, "adresse de deux services externes différents"),
}


def declares():
    d = defaultdict(set)
    for p in sorted((RACINE / "modules").glob("*/CN_manifeste.toml")):
        with open(p, "rb") as f:
            m = tomllib.load(f)
        for r in m.get("reglages", []):
            d[r["id"]].add(m["module"]["id"])
    return d


class ReglagesUniques(unittest.TestCase):
    def test_un_identifiant_de_reglage_n_est_declare_que_par_un_module(self):
        fautes = []
        for rid, mods in sorted(declares().items()):
            if len(mods) < 2:
                continue
            ok = EXCEPTIONS.get(rid)
            if ok is None or not mods <= ok[0]:
                fautes.append("« %s » est déclaré par %s" % (rid, ", ".join(sorted(mods))))
        self.assertEqual(fautes, [], "même identifiant de réglage dans plusieurs modules : le RENOMMER dans l'un d'eux (préfixe du métier, comme courriels_* pour la billetterie) "
                                     "ou, si c'est vraiment un autre service, l'ajouter à EXCEPTIONS avec la raison, dans tests/CN_test_reglages_uniques.py")

    def test_les_exceptions_sont_vivantes(self):
        d = declares()
        mortes = [rid for rid, (mods, _) in EXCEPTIONS.items() if len(d.get(rid, ())) < 2]
        self.assertEqual(mortes, [], "exception devenue inutile : la retirer de EXCEPTIONS")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : declares, ReglagesUniques
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
