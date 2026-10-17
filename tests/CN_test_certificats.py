# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du module certificats
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #0cd405
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du module certificats : la lecture du certificat servi est simulée, le reste (états, quota, événements, constats) tourne dans un vrai noyau.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=0cd405 ▼▼▼
"""Bancs du module certificats : la lecture du certificat servi est simulée, le reste (états, quota, événements, constats) tourne dans un vrai noyau."""
import importlib.util
import shutil
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("dns", "certificats"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        self.n.etat_modules.poser("certificats", installe=True, actif=False, par="test")        # son installation (CN_installer.sh) est l'affaire de l'administrateur système
        self.assertTrue(self.n.activer("certificats")["ok"])
        self.ctx = self.n.executeur.contextes["certificats"]
        self.panneau = [{"domaine": "a.exemple.fr"}, {"domaine": "www.b.exemple.org"}, {"domaine": "c.exemple.fr"}]
        self.ctx.executer_lecture = lambda cap, **a: self.panneau
        self.certs = {}
        g = self.n.catalogue.get("certificats.etat").faire.__globals__
        g["lire_certificat"] = lambda h, d: self.certs.get(h, {"erreur": "connexion refusée"})
        self.e = self.n.executeur.executer

    def cert(self, jours, emetteur="Let's Encrypt"):
        return {"jours": jours, "echeance": (datetime.utcnow() + timedelta(days=jours)).strftime("%Y-%m-%d"), "emetteur": emetteur, "noms": []}

    def evts(self, t):
        return [x for x in self.n.bus.recents(portee=TOUT, limite=900) if x["type"] == t]

    def etat(self, h):
        o = self.n.registre.lire("certificat", h, portee=TOUT)
        return o["etat"] if o else None

    def sonde(self):
        self.n.lancer("certificats.sonde")

    def ex(self, cap, **args):
        return self.e("certificats." + cap, "humain", args, compte="")


class Sonde(Monde):
    def test_les_etats_et_le_domaine_inconnu_n_est_pas_sans_certificat(self):
        self.certs = {"a.exemple.fr": self.cert(80), "b.exemple.org": self.cert(10), "c.exemple.fr": self.cert(-3)}
        self.n.reglages.poser("certificats.hotes", "d.exemple.fr")
        self.sonde()
        self.assertEqual([self.etat(h) for h in ("a.exemple.fr", "b.exemple.org", "c.exemple.fr", "d.exemple.fr")], ["valide", "proche", "echu", "inconnu"])
        self.assertIn("refusée", self.n.registre.lire("certificat", "d.exemple.fr", portee=TOUT)["donnees"]["erreur"])

    def test_le_passage_sous_le_seuil_est_dit_une_fois(self):
        self.certs = {"a.exemple.fr": self.cert(80)}
        self.sonde()
        self.certs["a.exemple.fr"] = self.cert(15)
        self.sonde()
        self.sonde()
        self.assertEqual(len(self.evts("certificat.proche_expiration")), 1)

    def test_le_seuil_est_un_reglage(self):
        self.certs = {"a.exemple.fr": self.cert(30)}
        self.sonde()
        self.assertEqual(self.etat("a.exemple.fr"), "valide")
        self.n.reglages.poser("certificats.seuil_jours", 45)
        self.sonde()
        self.assertEqual(self.etat("a.exemple.fr"), "proche")

    def test_constats_critique_sous_sept_jours_avec_le_quota(self):
        self.certs = {"a.exemple.fr": self.cert(4), "b.exemple.org": self.cert(15), "c.exemple.fr": self.cert(70)}
        self.sonde()
        self.n.tick()
        ouverts = {e["donnees"]["titre"]: e["donnees"] for e in self.evts("constat.ouvert")}
        self.assertEqual(len(ouverts), 2)
        crit = [d for t, d in ouverts.items() if "a.exemple.fr" in t][0]
        self.assertEqual(crit["niveau"], "critique")
        self.assertIn("Il reste 5 émission(s)", crit["detail"])

    def test_un_certificat_renouvele_resout_le_constat(self):
        self.certs = {"a.exemple.fr": self.cert(4)}
        self.sonde()
        self.n.tick()
        self.certs["a.exemple.fr"] = self.cert(85)
        self.sonde()
        self.n.tick(time.time() + 4000)
        self.assertEqual(len(self.evts("constat.resolu")), 1)

    def test_etat_liste_les_certificats(self):
        self.certs = {"a.exemple.fr": self.cert(80)}
        self.sonde()
        e = {c["hote"]: c for c in self.ex("etat")["resultat"]["certificats"]}
        self.assertEqual((e["a.exemple.fr"]["etat"], e["c.exemple.fr"]["etat"]), ("valide", "inconnu"))


class Quota(Monde):
    def emission(self, domaine):
        self.n.bus.emettre("fastpanel.certificat_renouvele", source="fastpanel", acteur="cassandra", objet=("fastpanel", domaine), donnees={"domaine": domaine})
        self.n.lancer("certificats.emission")

    def test_une_emission_du_panneau_compte_au_domaine_enregistre(self):
        self.emission("www.a.exemple.fr")
        self.emission("blog.a.exemple.fr")
        q = self.ex("quota", domaine="x.a.exemple.fr")["resultat"]
        self.assertEqual((q["domaine"], q["utilisees"], q["restantes"], q["bloque"]), ("exemple.fr", 2, 3, False))
        self.assertEqual(len(self.evts("certificat.renouvele")), 2)

    def test_cinq_emissions_bloquent_et_le_quota_se_libere_apres_sept_jours(self):
        for _ in range(5):
            self.emission("a.exemple.fr")
        q = self.ex("quota", domaine="exemple.fr")["resultat"]
        self.assertTrue(q["bloque"] and q["libre_le"])
        self.ctx.stockage.ecrire("UPDATE emissions SET ts = ts - ?", (8 * 86400,))
        self.assertFalse(self.ex("quota", domaine="exemple.fr")["resultat"]["bloque"])

    def test_le_quota_est_dit_dans_le_constat(self):
        for _ in range(5):
            self.emission("a.exemple.fr")
        self.certs = {"a.exemple.fr": self.cert(3)}
        self.sonde()
        self.n.tick()
        self.assertIn("Quota Let's Encrypt épuisé", " ".join(e["donnees"]["detail"] for e in self.evts("constat.ouvert")))

    def test_le_quota_est_par_domaine(self):
        for _ in range(5):
            self.emission("a.exemple.fr")
        self.assertEqual(self.ex("quota", domaine="b.exemple.org")["resultat"]["restantes"], 5)

    def test_un_evenement_n_est_compte_qu_une_fois(self):
        self.emission("a.exemple.fr")
        self.n.lancer("certificats.emission")
        self.n.lancer("certificats.sonde")
        self.assertEqual(self.ex("quota", domaine="exemple.fr")["resultat"]["utilisees"], 1)

    def test_le_module_n_exige_pas_que_le_panneau_soit_la(self):
        self.assertEqual(self.ex("quota", domaine="exemple.fr")["resultat"]["utilisees"], 0)

    def test_un_evenement_sans_domaine_ne_casse_rien(self):
        self.n.bus.emettre("fastpanel.certificat_renouvele", source="fastpanel", acteur="cassandra", objet=("fastpanel", "x"), donnees={})
        self.n.lancer("certificats.emission")
        self.assertEqual(self.ctx.stockage.lire("SELECT COUNT(*) n FROM emissions")[0]["n"], 0)


class Lecture(Monde):
    def test_relire_un_hote_et_les_refus(self):
        self.certs = {"a.exemple.fr": self.cert(40)}
        r = self.ex("relire_expiration", hote="https://www.a.exemple.fr/accueil")
        self.assertEqual((r["statut"], r["resultat"]["hote"], r["resultat"]["jours"]), ("faite", "a.exemple.fr", 40))
        self.assertEqual(self.ex("relire_expiration", hote="pas un hote")["statut"], "echec")
        self.assertEqual(self.ex("relire_expiration", hote="inconnu.exemple.fr")["resultat"]["erreur"], "connexion refusée")

    def test_la_lecture_reelle_d_un_port_ferme_est_une_erreur_et_pas_une_exception(self):
        spec = importlib.util.spec_from_file_location("c", RACINE / "modules" / "certificats" / "CN_module.py")
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        self.assertIn("erreur", m.lire_certificat("127.0.0.1", 1))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, Sonde, Quota, Lecture
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
