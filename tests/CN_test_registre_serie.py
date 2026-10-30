# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du registre officiel : série, fraîcheur, miroirs, déploiements
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #000000
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du registre officiel : la série qui ne recule jamais (rejeu refusé), la fraîcheur signée par une clé annoncée, les miroirs, le déploiement progressif et la bêta.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼
"""Bancs du registre officiel : la série qui ne recule jamais (rejeu refusé), la fraîcheur signée par une clé annoncée, les miroirs, le déploiement progressif et la bêta."""
import hashlib
import json
import sys
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_test_registre_officiel as _officiel                 # noqa: E402  (le module, pas la classe : ses bancs ne se rejouent pas ici)
R, cle = _officiel.R, _officiel.cle


class Serie(_officiel.Officiel):
    def poser_fraicheur(self, priv, **modif):
        octets = self.fichiers["/index.json"]
        brut = json.loads(octets)
        d = {"serie": brut.get("serie", 0), "index_sha256": hashlib.sha256(octets).hexdigest(), "emis": time.time() - 5, "expire": time.time() + 3600}
        d.update(modif)
        corps = json.dumps(d).encode("utf-8")
        self.fichiers["/fraicheur.json"] = corps
        self.fichiers["/fraicheur.json.sig"] = R.signer(corps, priv)

    def test_la_serie_ne_recule_jamais(self):
        self.publier(serie=5)
        self.assertEqual(self.cycle.registre_officiel()["modules"][0]["id"], "chezacme")
        self.assertEqual(self.cycle.serie_vue(), 5)
        self.publier(serie=3)                                           # un index plus ancien, valide et signé : un rejeu
        with self.assertRaises(R.RegistreErreur) as e:
            self.cycle.registre_officiel()
        self.assertIn("plus ancien", str(e.exception))
        self.assertEqual(self.cycle.serie_vue(), 5)                     # le refus n'abaisse pas la mémoire
        self.publier(serie=5)
        self.cycle.registre_officiel()                                  # la même série reste acceptée (le même index relu)

    def test_un_index_sans_serie_apres_une_serie_est_refuse(self):
        self.publier(serie=4)
        self.cycle.registre_officiel()
        self.publier()                                                  # l'ancien format, sans série
        with self.assertRaises(R.RegistreErreur):
            self.cycle.registre_officiel()

    def test_un_miroir_prend_le_relais_si_le_premier_sert_un_index_ancien_ou_tombe(self):
        self.publier(serie=7)
        self.cycle.registre_officiel()
        miroir = self.url.replace("/index.json", "/m/index.json")
        self.fichiers["/m/index.json"], self.fichiers["/m/index.json.sig"] = self.fichiers["/index.json"], self.fichiers["/index.json.sig"]
        self.fichiers["/m/modules/sentinelle.cmod"] = self.fichiers["/modules/sentinelle.cmod"]
        self.publier(serie=2)                                           # le premier hébergeur sert un vieil index
        c = self.nouveau_cycle()
        c.miroirs = (miroir,)
        c._noter_serie(7)
        r = c.registre_officiel()
        self.assertEqual(c.url_utilisee, miroir)
        self.assertIn("sentinelle", {m["id"] for m in r["modules"]})
        self.fichiers.pop("/index.json")                                # le premier tombe tout à fait
        self.assertEqual(self.nouveau_cycle_avec(miroir).registre_officiel()["officiel"], True)

    def nouveau_cycle_avec(self, miroir):
        c = self.nouveau_cycle()
        c.miroirs = (miroir,)
        return c

    def test_une_fraicheur_annoncee_est_exigee_signee_par_la_bonne_cle_et_non_perimee(self):
        fr_priv, fr_pub = cle(self.base, "fraicheur")
        self.publier(serie=1, fraicheur={"cle": fr_pub, "validite_s": 604800})
        with self.assertRaises(R.RegistreErreur):                       # l'index annonce une fraîcheur qui n'est pas là
            self.cycle.registre_officiel()
        self.poser_fraicheur(fr_priv)
        self.cycle.registre_officiel()
        self.poser_fraicheur(fr_priv, expire=time.time() - 10)          # périmée
        with self.assertRaises(R.RegistreErreur):
            self.cycle.registre_officiel()
        self.poser_fraicheur(fr_priv, serie=99)                         # elle atteste un autre index
        with self.assertRaises(R.RegistreErreur):
            self.cycle.registre_officiel()
        autre_priv, _ = cle(self.base, "autre")
        self.poser_fraicheur(autre_priv)                                # signée par une clé que l'index n'a pas annoncée (une clé de fraîcheur ne se choisit pas seule)
        with self.assertRaises(R.RegistreErreur):
            self.cycle.registre_officiel()

    def test_sans_fraicheur_annoncee_rien_n_est_demande(self):
        self.publier(serie=1)
        self.cycle.registre_officiel()

    def test_le_tirage_d_un_deploiement_est_stable_et_reparti(self):
        pris = sum(R.en_deploiement("%032x" % n, "sentinelle", "1.0.0", 25) for n in range(2000))
        self.assertTrue(400 <= pris <= 600, pris)                       # environ un quart
        self.assertEqual(R.en_deploiement("a" * 32, "m", "1.0", 25), R.en_deploiement("a" * 32, "m", "1.0", 25))
        self.assertTrue(R.en_deploiement("a" * 32, "m", "1.0", 100))
        self.assertFalse(R.en_deploiement("a" * 32, "m", "1.0", 0))
        for p in (10, 50):                                              # une part plus large contient toujours la plus étroite
            for n in range(200):
                i = "%032x" % n
                if R.en_deploiement(i, "m", "1.0", p):
                    self.assertTrue(R.en_deploiement(i, "m", "1.0", p + 40))

    def entree(self, mid, version, **plus):
        a = self.archives[mid]
        return dict({"id": mid, "nom": mid.capitalize(), "version": version, "description": "essai", "url": "modules/%s.cmod" % mid, "sha256": hashlib.sha256(a["octets"]).hexdigest(),
                     "taille": len(a["octets"]), "editeur": a["editeur"]}, **plus)

    def test_le_deploiement_progressif_remplace_la_version_offerte_pour_ceux_qui_en_font_partie(self):
        self.publier(serie=1, progressifs=[self.entree("sentinelle", "0.2.0", pourcent=30)])
        original = R.en_deploiement
        try:
            R.en_deploiement = lambda *a: True
            self.assertEqual(self.modules()["sentinelle"]["version"], "0.2.0")
            R.en_deploiement = lambda *a: False
            self.assertEqual(self.modules()["sentinelle"]["version"], "0.1.2")
        finally:
            R.en_deploiement = original

    def test_la_beta_n_est_vue_que_de_ceux_qui_la_choisissent(self):
        self.publier(serie=1, beta=[self.entree("sentinelle", "0.3.0")])
        self.assertEqual(self.modules()["sentinelle"]["version"], "0.1.2")
        c = self.nouveau_cycle()
        c.canal = "beta"
        self.assertEqual({m["id"]: m for m in c.registre_officiel()["modules"]}["sentinelle"]["version"], "0.3.0")

    def test_l_identifiant_d_installation_est_tire_une_fois_et_garde(self):
        a = self.cycle.id_installation()
        self.assertEqual(len(a), 32)
        self.assertEqual(a, self.nouveau_cycle().id_installation())


for _n in [n for n in dir(_officiel.Officiel) if n.startswith("test_") and n not in vars(Serie)]:      # les bancs hérités tournent dans leur classe d'origine, pas ici
    setattr(Serie, _n, None)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Serie
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
