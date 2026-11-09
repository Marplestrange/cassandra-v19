# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de la sonde `mesure_etat` du module Mémoire
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #a066a3
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de la sonde `mesure_etat` du module Mémoire : un fait « état courant » peut dépendre d'une mesure du Sensorium (artefact `mesure:<clé>`).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a066a3 ▼▼▼
"""Bancs de la sonde `mesure_etat` du module Mémoire : un fait « état courant » peut dépendre d'une mesure du Sensorium (artefact `mesure:<clé>`).

Deux étages : une Mémoire seule dont le Sensorium est simulé (le vocabulaire de la sonde, les refus, la relecture), puis un vrai noyau monté avec le vrai Sensorium et un faux émetteur.
Règle vérifiée partout : une mesure `inconnu` (muette, jamais lue, invisible pour ce compte) ne contredit RIEN et ne fait jamais expirer un fait."""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from tests.CN_test_memoire import Monde, ROOT  # noqa: E402
from tests.CN_test_sensorium_cloisonnement import ADMIN, MDP, collecteur_simule  # noqa: E402

ORD = "ord@exemple.test"
VALEUR = "le résolveur local répond vite à cet instant précis"


class SondeSimulee(Monde):
    def setUp(self):
        super().setUp()
        self.mesures = {}

    def lecture(self, cap, **a):
        if cap == "sensorium.mesure_etat":
            return self.mesures.get(a["cle"])
        return super().lecture(cap, **a)

    def ecrire(self, cle="dns-vite", etat="ok", mesure="dns.latence", **kw):
        return self.w(cle=cle, valeur=VALEUR, nature="etat-courant", sonde="mesure_etat", sonde_args=[mesure, etat], **kw)

    def test_la_sonde_est_au_vocabulaire_ferme(self):
        self.assertIn("mesure_etat", self.o.SONDES)

    def test_un_fait_qui_dit_vrai_est_pose_avec_son_artefact(self):
        self.mesures["dns.latence"] = {"etat": "ok"}
        m = self.ecrire()
        self.assertTrue(m["ok"], m)
        self.assertEqual(self.ligne(m["id"])["artefact"], "mesure:dns.latence")
        self.assertEqual(self.ligne(m["id"])["sonde_valeur"], "true")

    def test_un_fait_que_la_mesure_dement_est_refuse(self):
        self.mesures["dns.latence"] = {"etat": "alerte"}
        r = self.ecrire(etat="ok")
        self.assertFalse(r.get("ok"), r)
        self.assertIn("répond NON", r["detail"])

    def test_une_mesure_inconnue_ne_permet_pas_d_ecrire_un_fait_ok(self):
        self.mesures["dns.latence"] = {"etat": "inconnu"}
        self.assertEqual(self.ecrire(etat="ok")["refus"], "sonde")
        self.assertEqual(self.ecrire(etat="alerte", cle="autre")["refus"], "sonde")
        self.assertTrue(self.ecrire(etat="inconnu", cle="dit-inconnu")["ok"], "on peut AFFIRMER qu'une mesure est inconnue")

    def test_le_sensorium_qui_ne_repond_pas_ne_permet_rien(self):
        self.assertEqual(self.ecrire()["refus"], "sonde")                 # aucune entrée : lecture = None

    def test_arguments_illisibles(self):
        self.mesures["dns.latence"] = {"etat": "ok"}
        for mesure, etat in (("Majuscule.x", "ok"), ("pas une cle", "ok"), ("dns.latence", "peut-etre"), ("dns.latence", ""), ("../x", "ok")):
            self.assertEqual(self.ecrire(mesure=mesure, etat=etat, cle="k")["refus"], "sonde", (mesure, etat))
        self.assertEqual(self.w(nature="etat-courant", sonde="mesure_etat", sonde_args=["dns.latence"], cle="k2", valeur=VALEUR)["refus"], "sonde")

    def test_la_relecture_contredit_quand_la_mesure_change_d_etat(self):
        self.mesures["dns.latence"] = {"etat": "ok"}
        m = self.ecrire()
        self.moteur("entretien")
        self.assertEqual(self.ligne(m["id"])["statut"], "actif", "rien n'a bougé : rien n'est relu")
        self.mesures["dns.latence"] = {"etat": "alerte"}
        self.moteur("entretien")
        self.assertEqual(self.ligne(m["id"])["statut"], "expire")
        self.assertIn("re-mesuré après un changement de mesure:dns.latence", self.journal("oubli")[-1]["details"])

    def test_une_mesure_qui_devient_inconnue_ne_fait_pas_expirer_le_fait(self):
        self.mesures["dns.latence"] = {"etat": "ok"}
        m = self.ecrire()
        self.mesures["dns.latence"] = {"etat": "inconnu"}                 # le capteur s'est tu
        self.moteur("entretien")
        self.moteur("entretien")
        self.assertEqual(self.ligne(m["id"])["statut"], "actif", "ne pas savoir n'est pas une réfutation")
        self.mesures["dns.latence"] = {"etat": "ok"}                      # il revient : le fait est confirmé
        self.moteur("entretien")
        self.assertEqual(self.ligne(m["id"])["statut"], "actif")
        self.mesures["dns.latence"] = {"etat": "alerte"}
        self.moteur("entretien")
        self.assertEqual(self.ligne(m["id"])["statut"], "expire")

    def test_un_sensorium_absent_ne_fait_pas_expirer_le_fait(self):
        self.mesures["dns.latence"] = {"etat": "ok"}
        m = self.ecrire()
        del self.mesures["dns.latence"]                                    # module désactivé, lecture refusée : None
        self.moteur("entretien")
        self.assertEqual(self.ligne(m["id"])["statut"], "actif", "l'artefact n'a pas « disparu » : on ne le sait simplement plus")


class AvecLeVraiSensorium(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import CN_main as moteur
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        mods = base / "modules"
        for m in ("droits", "modules", "sensorium", "memoire"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        mf = mods / "sensorium" / "CN_manifeste.toml"
        mf.write_text(re.sub(r"\[installation\][^\[]*", "", mf.read_text(encoding="utf-8")), encoding="utf-8")
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        for m in ("droits", "modules", "sensorium", "memoire"):
            assert cls.n.activer(m)["ok"], m
        assert cls.n.identite.creer(ADMIN, MDP)["admin"]
        cls.n.droits.regler_admin(ADMIN, True)
        cls.n.identite.creer("kino1@exemple.test", MDP)
        cls.n.droits.regler("compte", "kino1@exemple.test", "sensorium.alimenter", "accorde")
        r = cls.n.identite.creer(ORD, MDP)
        assert r["ok"] and not r["admin"], r
        cls.g = cls.n.catalogue.get("sensorium.mesure_etat").faire.__globals__
        cls.t = [1_800_000_000.0]
        cls.horloge = mock.patch.dict(cls.g, {"_maintenant": lambda: cls.t[0]})
        cls.horloge.start()
        cls.col = mock.patch.dict(cls.n.catalogue.get("sensorium.monde").faire.__globals__, {"json_de": collecteur_simule})
        cls.col.start()
        cls.n.catalogue.regler_palier("memoire.ecrire", "auto")

    @classmethod
    def tearDownClass(cls):
        cls.col.stop()
        cls.horloge.stop()
        cls.n.arreter()
        cls.tmp.cleanup()

    def sensorium(self, cap, compte, acteur, **a):
        r = self.n.executeur.executer("sensorium." + cap, acteur, a, compte=compte)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def test_un_fait_vit_et_meurt_avec_la_mesure_et_se_tait_quand_elle_se_tait(self):
        K = "kino1@exemple.test"
        self.sensorium("capteur_declarer", K, "compte", cle="dns.latence", fraicheur_s=60, alerte=100)
        self.sensorium("capteur_alimenter", K, "compte", lectures=[{"cle": "dns.latence", "valeur": 12}])
        r = self.n.executeur.executer("memoire.ecrire", "humain", {"categorie": "config", "cle": "dns-vite", "valeur": VALEUR, "nature": "etat-courant",
                                                                  "sonde": "mesure_etat", "sonde_args": ["dns.latence", "ok"]}, compte=ADMIN)
        self.assertEqual(r["statut"], "faite", r)
        mid = r["resultat"]["id"]
        db = self.n.executeur.contextes["memoire"].stockage
        statut = lambda: db.lire("SELECT statut FROM memoires WHERE id=?", (mid,))[0]["statut"]
        self.assertEqual(db.lire("SELECT artefact FROM memoires WHERE id=?", (mid,))[0]["artefact"], "mesure:dns.latence")
        self.n.lancer("memoire.entretien")
        self.assertEqual(statut(), "actif")
        self.t[0] += 120                                                   # le capteur se tait : inconnu
        self.assertEqual(self.sensorium("mesure_etat", ADMIN, "humain", cle="dns.latence")["etat"], "inconnu")
        self.n.lancer("memoire.entretien")
        self.assertEqual(statut(), "actif", "un capteur muet n'est pas une réfutation")
        self.sensorium("capteur_alimenter", K, "compte", lectures=[{"cle": "dns.latence", "valeur": 500}])
        self.n.lancer("memoire.entretien")
        self.assertEqual(statut(), "expire", "la mesure est en alerte : le fait « ok » n'est plus vrai")


    def test_fuite_la_relecture_ne_revele_pas_une_mesure_non_publiee_a_son_proprietaire(self):
        """Un compte ordinaire écrit un fait « la mesure infra.secret est inconnue » : vrai POUR LUI (la mesure ne lui est pas publiée). La relecture, faite par un moteur sans compte,
        ne doit pas lire la mesure en privilégié : sinon le fait expire et la raison, écrite au journal du propriétaire, lui apprend que la mesure existe et répond."""
        K = "kino1@exemple.test"
        self.sensorium("capteur_declarer", K, "compte", cle="infra.secret", fraicheur_s=600)
        self.sensorium("capteur_alimenter", K, "compte", lectures=[{"cle": "infra.secret", "valeur": 1}])
        self.assertEqual(self.sensorium("mesure_etat", ORD, "humain", cle="infra.secret")["etat"], "inconnu", "invisible pour ORD")
        r = self.n.executeur.executer("memoire.ecrire", "humain", {"categorie": "config", "cle": "secret-inconnu", "valeur": VALEUR, "nature": "etat-courant",
                                                                  "sonde": "mesure_etat", "sonde_args": ["infra.secret", "inconnu"]}, compte=ORD)
        self.assertEqual(r["statut"], "faite", r)
        mid = r["resultat"]["id"]
        self.assertTrue(mid, r)
        db = self.n.executeur.contextes["memoire"].stockage
        self.n.lancer("memoire.entretien")
        ligne = db.lire("SELECT statut FROM memoires WHERE id=?", (mid,))[0]
        self.assertEqual(ligne["statut"], "actif", "la mesure a fuité : le fait a expiré parce qu'un moteur privilégié a lu l'état réel")
        self.assertFalse([j for j in db.lire("SELECT details FROM journal WHERE verbe='oubli'") if "infra.secret" in (j["details"] or "")])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : SondeSimulee, AvecLeVraiSensorium
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
