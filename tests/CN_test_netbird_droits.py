# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des droits du module netbird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #6aeab9
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des droits du module netbird : qui peut installer et administrer un serveur NetBird, et qui voit ses menus.
# MÉTHODE    : un vrai noyau avec les modules droits et menus ; on attribue le droit « netbird.serveur » comme le ferait l'administrateur, on vérifie ce qui passe et ce qui est refusé.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=6aeab9 ▼▼▼
"""Bancs des droits du module netbird : le droit « netbird.serveur » est sensible, jamais accordé d'office, et ouvre l'installation du serveur, son administration et leurs menus."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402

CAP_SERVEUR = "netbird.serveur_etat"          # une lecture du serveur : elle porte le droit « serveur » sans rien installer ni appeler
CAP_CLIENT = "netbird.etat"                   # l'état du client : droit « utiliser », accordé à tous


class DroitsNetBird(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Un seul noyau pour tous les bancs (l'activer coûte cher) : chaque banc a SON compte, aucun n'en dépend d'un autre.
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        base = Path(cls.tmp.name)
        mods = base / "modules"
        for m in ("droits", "menus", "netbird"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        cls.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        cls.n.brancher()
        for m in ("droits", "menus"):
            cls.n.activer(m)
        cls.n.etat_modules.poser("netbird", installe=True, actif=False, par="test")
        assert cls.n.activer("netbird")["ok"]
        # Ici on teste QUI peut, pas ce que le courtier répond : un compte autorisé ne doit pas attendre un vrai courtier.
        g = cls.n.catalogue.get("netbird.etat").faire.__globals__
        g["_racine"] = lambda verbe, args=(), entree=None, delai=30, commande="piloter": {"ok": False, "erreur": "banc : pas de courtier", "courtier": False}
        g["_direct"] = lambda args, delai=15: (None, "absent")

    def ex(self, cle, au_nom_de="", **args):
        return self.n.executeur.executer(cle, "humain", args, compte=au_nom_de)

    def menus(self, compte):
        def plat(noeuds):
            return [t for n in noeuds for t in [n["libelle"]] + plat(n.get("enfants") or [])]
        return sorted(set(plat(self.ex("menus.lire_menu", role="admin", compte=compte)["resultat"]["arbre"])))

    def test_le_droit_serveur_est_declare_et_sensible(self):
        d = {x["droit"]: x for x in self.n.droits.catalogue()}
        self.assertIn("netbird.serveur", d)
        self.assertTrue(d["netbird.serveur"]["sensible"])
        self.assertFalse(d["netbird.serveur"]["defaut"], "jamais accordé d'office")
        self.assertTrue(d["netbird.utiliser"]["defaut"])

    def test_un_compte_sans_le_droit_ne_touche_pas_au_serveur(self):
        r = self.ex(CAP_SERVEUR, au_nom_de="sandrine")
        self.assertEqual((r["statut"], r["droit"]), ("refuse", "netbird.serveur"))
        for cap in ("serveur_installer", "serveur_retirer", "api_machines", "cle_creer", "politique_creer"):
            self.assertEqual(self.ex("netbird." + cap, au_nom_de="sandrine")["statut"], "refuse", cap)

    def test_le_client_reste_ouvert_a_tous_pour_la_lecture(self):
        self.assertEqual(self.ex(CAP_CLIENT, au_nom_de="sandrine")["statut"], "faite")

    def test_l_administrateur_accorde_le_droit_puis_le_retire(self):
        self.assertEqual(self.ex("droits.regler", sujet="lucie", droit="netbird.serveur")["statut"], "faite")
        self.assertNotEqual(self.ex(CAP_SERVEUR, au_nom_de="lucie")["statut"], "refuse")
        self.ex("droits.regler", sujet="lucie", droit="netbird.serveur", valeur="herite")
        self.assertEqual(self.ex(CAP_SERVEUR, au_nom_de="lucie")["statut"], "refuse")

    def test_le_droit_peut_aussi_s_accorder_a_un_groupe(self):
        self.ex("droits.groupe", groupe="reseau", libelle="Réseau")
        self.ex("droits.regler", sujet_type="groupe", sujet="reseau", droit="netbird.serveur")
        self.ex("droits.membre", compte="jules", groupe="reseau")
        self.assertNotEqual(self.ex(CAP_SERVEUR, au_nom_de="jules")["statut"], "refuse")
        self.assertEqual(self.ex(CAP_SERVEUR, au_nom_de="paul")["statut"], "refuse", "pas membre")

    def test_on_ne_s_octroie_pas_le_droit_soi_meme(self):
        r = self.ex("droits.regler", au_nom_de="hugo", sujet="hugo", droit="netbird.serveur")
        self.assertEqual(r["statut"], "refuse")

    def test_les_menus_serveur_et_administration_suivent_le_droit(self):
        avant = self.menus("nina")
        self.assertIn("Client", avant)
        self.assertNotIn("Serveur", avant)
        self.assertNotIn("Administration", avant)
        self.ex("droits.regler", sujet="nina", droit="netbird.serveur")
        apres = self.menus("nina")
        self.assertIn("Serveur", apres)
        self.assertIn("Administration", apres)

    def test_un_administrateur_detient_tout(self):
        self.ex("droits.admin", compte="marie")
        self.assertNotEqual(self.ex(CAP_SERVEUR, au_nom_de="marie")["statut"], "refuse")
        self.assertIn("Serveur", self.menus("marie"))


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : DroitsNetBird (le droit « serveur », ses refus, ses accords, ses menus)
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/netbird/CN_manifeste.toml, noyau/CN_droits.py, tests/CN_test_netbird_gestion.py
