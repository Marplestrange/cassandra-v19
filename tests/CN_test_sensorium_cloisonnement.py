# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du cloisonnement du Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #c8c144
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du cloisonnement du Sensorium : un compte ordinaire ne lit pas l'infrastructure de l'instance ; un administrateur la lit toujours.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c8c144 ▼▼▼
"""Bancs du cloisonnement du Sensorium : un compte ordinaire ne lit pas l'infrastructure de l'instance ; un administrateur la lit toujours.

Un vrai noyau est monté (droits, modules, sensorium) avec un administrateur et deux comptes ordinaires, dont un dans une autre société. Le collecteur est simulé : aucun socket, aucun service réel."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

MDP = "Zq7-Essai-Vrai-9482!"
ADMIN, SIMPLE, AUTRE = "premier@exemple.test", "simple@exemple.test", "autre@exemple.test"
MONDE = [{"wkey": "system.hostname", "value": "serveur-secret", "severity": "info", "observed_at": "2026-11-09 00:00:00", "detail": "{}"},
         {"wkey": "ssl.client-prive.exemple.test", "value": "expire dans 3 jours", "severity": "warning", "observed_at": "2026-11-09 00:00:00", "detail": "{}"}]


def collecteur_simule(requete, delai=5.0):
    if requete.startswith("GET_WORLD"):
        return json.loads(json.dumps(MONDE))
    if requete.startswith("GET_ENTITY"):
        return [{"nom": "infra-secrete"}]
    if requete.startswith("GET_DAEMON"):
        return {"pid": 1}
    if requete.startswith("GET_METRICS"):
        return {"cpu": 12.0, "ram": 40.0, "disk": 50.0, "swap": 0.0, "load_1m": 0.3}
    if requete.startswith("GET_DASHBOARD"):
        return {"health_status": "bon", "health_score": 90}
    return []


class Banc(unittest.TestCase):
    """Un noyau monté, partagé par les bancs de la classe. Les sous-classes ajoutent leurs modules par `MODULES`."""
    MODULES = ("droits", "modules", "sensorium")

    @classmethod
    def setUpClass(cls):
        import CN_main as moteur
        cls.tmp = tempfile.TemporaryDirectory()
        base = Path(cls.tmp.name)
        mods = base / "modules"
        cls.poser_modules_d_essai(mods)                                              # une sous-classe peut poser un module d'essai avant le montage
        for m in cls.MODULES:
            if not (mods / m).exists():
                shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        mf = mods / "sensorium" / "CN_manifeste.toml"
        mf.write_text(re.sub(r"\[installation\][^\[]*", "", mf.read_text(encoding="utf-8")), encoding="utf-8")          # pas d'installation de service root dans un banc
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        for m in cls.MODULES:
            r = cls.n.activer(m)
            assert r["ok"], (m, r)
        assert cls.n.identite.creer(ADMIN, MDP)["admin"]
        cls.n.droits.regler_admin(ADMIN, True)
        r = cls.n.identite.creer(SIMPLE, MDP)
        assert r["ok"] and not r["admin"], r
        cls.societe2 = cls.n.identite.societe_creer("Seconde société", "2")
        r = cls.n.identite.creer(AUTRE, MDP, societe="2")
        assert r["ok"] and not r["admin"], r
        g = cls.n.catalogue.get("sensorium.monde").faire.__globals__
        cls.patch = mock.patch.dict(g, {"json_de": collecteur_simule})
        cls.patch.start()

    @classmethod
    def poser_modules_d_essai(cls, mods):
        pass

    @classmethod
    def tearDownClass(cls):
        cls.patch.stop()
        cls.n.arreter()
        cls.tmp.cleanup()

    def ex(self, cap, compte, societe="", **args):
        return self.n.executeur.executer(cap, "humain", args, compte=compte, societe=societe)


LECTURES = ("monde", "entite", "etat", "historique", "changements", "demon", "modules", "gestes_journal", "fenetres", "erreurs_navigateur", "metriques", "sante")
ARGS = {"entite": {"nom": "ssl"}, "historique": {"cle": "ssl.x"}}


class Fuite(Banc):
    def test_un_compte_ordinaire_ne_lit_aucune_lecture_d_infrastructure(self):
        for cap in LECTURES:
            r = self.ex("sensorium." + cap, SIMPLE, **ARGS.get(cap, {}))
            self.assertEqual(r["statut"], "refuse", (cap, r))
            self.assertEqual(r.get("droit"), "sensorium.voir_infra", (cap, r))
            self.assertNotIn("serveur-secret", json.dumps(r))
            # la société « 2 » n'a de toute façon pas ce module : un module d'instance n'est ouvert que dans la principale (noyau/CN_identite.py : module_ouvert)
            r = self.ex("sensorium." + cap, AUTRE, **ARGS.get(cap, {}))
            self.assertEqual(r["statut"], "refuse", (cap, r))
            self.assertNotIn("serveur-secret", json.dumps(r))

    def test_un_administrateur_lit_tout_comme_avant(self):
        for cap in LECTURES:
            r = self.ex("sensorium." + cap, ADMIN, **ARGS.get(cap, {}))
            self.assertEqual(r["statut"], "faite", (cap, r))
        self.assertIn("serveur-secret", json.dumps(self.ex("sensorium.monde", ADMIN)["resultat"]))

    def test_un_compte_ordinaire_a_qui_on_donne_le_droit_lit(self):
        self.n.droits.regler("compte", SIMPLE, "sensorium.voir_infra", "accorde")
        try:
            self.assertEqual(self.ex("sensorium.monde", SIMPLE)["statut"], "faite")
            self.assertEqual(self.ex("sensorium.monde", AUTRE)["statut"], "refuse", "le droit d'un compte n'est pas celui d'un autre")
        finally:
            self.n.droits.regler("compte", SIMPLE, "sensorium.voir_infra", None)
        self.assertEqual(self.ex("sensorium.monde", SIMPLE)["statut"], "refuse")

    def test_la_securite_reste_fermee_et_serie_reste_ouverte(self):
        self.assertEqual(self.ex("sensorium.secu", SIMPLE)["statut"], "refuse")
        self.assertNotEqual(self.ex("sensorium.serie", SIMPLE, mesure="cpu", depuis="2026-11-01 00:00:00", jusqu_a="2026-11-02 00:00:00").get("droit"), "sensorium.voir_infra")

    def test_le_droit_est_sensible_et_jamais_par_defaut(self):
        module, d = self.n.droits.connus["sensorium.voir_infra"]
        self.assertTrue(d.sensible)
        self.assertFalse(d.defaut)

    def test_les_autres_modules_ne_recoivent_plus_le_monde_au_nom_d_un_compte_ordinaire(self):
        """La lecture d'un module pour un autre (executer_lecture) est au nom du compte qui regarde : refusée, donc None."""
        ctx = self.n.executeur.contextes["sensorium"]
        lecture = ctx._intro["lecture"]
        self.assertIsNone(lecture("sensorium.monde", {}, SIMPLE, ""))
        self.assertIsNotNone(lecture("sensorium.monde", {}, ADMIN, ""))
        self.assertIsNotNone(lecture("sensorium.monde", {}, "", ""))          # un moteur du noyau (sans compte) lit toujours
        self.assertIsNone(lecture("sensorium.monde", {}, AUTRE, "2"))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : collecteur_simule, Banc, Fuite
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
