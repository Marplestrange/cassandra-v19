# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des réglages du Centre de notifications
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #a443cc
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des réglages du Centre de notifications : préférences, politique, sourdines, essai, webhook chiffré.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a443cc ▼▼▼
"""Bancs des réglages du Centre : les préférences d'une personne, la politique de canaux (la machine, puis la personne), les sourdines datées, l'essai de la cloche,
le webhook de la machine (son adresse chiffrée, réservée à un administrateur). Chaque geste a sa preuve et son retour."""
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402

CHEF, BEA = "chef@x.fr", "bea@x.fr"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("notifications", "droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "notifications"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin(CHEF, True)
        self.ctx = self.n.executeur.contextes["notifications"]

    def ex(self, capacite, compte=BEA, acteur="humain", **args):
        return self.n.executeur.executer("notifications." + capacite, acteur, args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex(cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def defaire(self, cap, res):
        self.n.catalogue.get("notifications." + cap).defaire(self.ctx, res)

    def test_les_preferences_se_posent_et_se_defont(self):
        with mock.patch("zoneinfo.ZoneInfo", lambda nom: nom if nom == "Europe/Paris" else (_ for _ in ()).throw(KeyError(nom))):     # la machine d'essai n'a pas toujours la base des fuseaux
            r = self.ex("prefs", fuseau="Europe/Paris", calme_debut="21:30")
            self.assertNotEqual(self.ex("prefs", fuseau="Mars/Olympus")["statut"], "faite")
        self.assertEqual(r["statut"], "faite", r)
        p = self.s("politique")["prefs"]
        self.assertEqual((p["fuseau"], p["calme_debut"], p["calme_fin"], p["calmes"]), ("Europe/Paris", "21:30", "08:00", True))
        self.defaire("prefs", r["resultat"])
        self.assertEqual(self.s("politique")["prefs"]["fuseau"], "")

    def test_une_heure_fausse_est_refusee(self):
        self.assertNotEqual(self.ex("prefs", calme_fin="25:99")["statut"], "faite")

    def test_la_politique_d_une_personne_ne_touche_pas_celle_d_une_autre(self):
        self.s("politique_ecrire", niveau="info", canaux=["telegram"])
        self.assertEqual(self.s("politique")["moi"]["info"], ["cloche", "telegram"])      # la cloche reçoit toujours
        self.assertEqual(self.s("politique", compte="zoe@x.fr")["moi"]["info"], ["cloche"])

    def test_la_politique_de_la_machine_est_reservee_a_un_administrateur(self):
        self.assertNotEqual(self.ex("politique_ecrire", niveau="avoir", canaux=["telegram"], machine=True)["statut"], "faite")
        r = self.ex("politique_ecrire", compte=CHEF, niveau="avoir", canaux=["telegram"], machine=True)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.s("politique")["machine"]["avoir"], ["cloche", "telegram"])
        self.assertEqual(self.s("politique")["moi"]["avoir"], ["cloche", "telegram"])                  # la personne hérite de la machine tant qu'elle n'a rien choisi
        self.defaire("politique_ecrire", r["resultat"])
        self.assertEqual(self.s("politique")["machine"]["avoir"], ["cloche", "mail"])

    def test_une_sourdine_se_pose_se_leve_et_se_defait(self):
        r = self.ex("sourdine", portee="source", cible="securite", heures=3)
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual([x["cible"] for x in self.s("politique")["sourdines"]], ["securite"])
        self.assertEqual(self.s("politique", compte="zoe@x.fr")["sourdines"], [])         # une sourdine est celle d'une personne
        self.defaire("sourdine", r["resultat"])
        self.assertEqual(self.s("politique")["sourdines"], [])
        self.s("sourdine", portee="source", cible="securite", heures=2)
        lev = self.s("sourdine", portee="source", cible="securite", heures=0)
        self.assertTrue(lev["levee"])
        self.assertEqual(self.s("politique")["sourdines"], [])

    def test_l_essai_de_la_cloche_arrive_et_les_autres_canaux_disent_non(self):
        r = self.ex("essai", canal="cloche")
        self.assertEqual(r["statut"], "faite", r)
        self.assertTrue(r["resultat"]["ok"])
        self.assertEqual(len(self.s("lister")["notifications"]), 1)
        mail = self.s("essai", canal="mail")
        self.assertFalse(mail["ok"])
        self.assertIn("pas encore", mail["detail"])
        self.assertFalse(self.s("politique")["canaux"]["essais"]["mail"]["ok"])
        self.defaire("essai", r["resultat"])
        self.assertEqual(self.s("lister")["notifications"], [])

    def test_le_webhook_est_chiffre_et_reserve_a_un_administrateur(self):
        self.assertNotEqual(self.ex("webhook_ecrire", url="https://exemple.test/h", actif=True)["statut"], "faite")
        r = self.ex("webhook_ecrire", compte=CHEF, url="https://exemple.test/h?cle=SECRET", actif=True)
        self.assertEqual(r["statut"], "faite", r)
        w = self.s("politique", compte=CHEF)["canaux"]["webhook"]
        self.assertEqual((w["declare"], w["url"]), (True, "https://exemple.test/h?cle=SECRET"))
        self.assertFalse(self.s("politique")["canaux"]["webhook"]["declare"])           # une personne ordinaire ne le voit pas
        base = sqlite3.connect(str(next(Path(self.tmp.name).rglob("notifications.db"))))
        brut = base.execute("SELECT url_chiffree FROM notif_webhook").fetchone()[0]
        base.close()
        self.assertNotIn("SECRET", brut)
        self.assertNotEqual(self.ex("webhook_ecrire", compte=CHEF, url="ftp://x", actif=True)["statut"], "faite")
        self.defaire("webhook_ecrire", r["resultat"])
        self.assertFalse(self.s("politique", compte=CHEF)["canaux"]["webhook"]["declare"])

    def test_les_sources_sont_reservees_a_un_administrateur(self):
        self.assertNotEqual(self.ex("sources")["statut"], "faite")
        self.s("emettre", compte=CHEF, titre="x", source="securite", niveau="info", dest=[CHEF])
        self.assertEqual([x["source"] for x in self.s("sources", compte=CHEF)["sources"]], ["securite"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
