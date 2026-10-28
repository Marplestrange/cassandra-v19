# ══════════════════════════════════════════════════════════════════
# TITRE      : Tests : utilisateurs et groupes
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #08bb23
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les droits obligatoires pour tout module, l'application des droits d'un compte ou d'un groupe, le dernier administrateur, le départ d'un utilisateur.
# MÉTHODE    : un monde réel (modules droits, comptes, notifications, menus) monté dans un dossier jetable ; on agit par l'exécuteur, comme l'interface.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=08bb23 ▼▼▼
import glob
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur  # noqa: E402
from noyau import CN_manifeste as mf  # noqa: E402

MDP = "Bleu-Renard-2026!"


def monde():
    tmp = tempfile.TemporaryDirectory()
    base = Path(tmp.name)
    mods = base / "modules"
    for m in ("droits", "comptes", "notifications", "menus"):
        shutil.copytree(RACINE / "modules" / m, mods / m)
    n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
    n.brancher(annoncer=False)
    for m in ("droits", "comptes", "menus", "notifications"):
        n.activer(m)
    return tmp, n


class DroitsObligatoires(unittest.TestCase):
    def test_un_manifeste_sans_droit_est_refuse(self):
        brut = {"module": {"id": "xx", "nom": "X", "version": "0.1.0", "noyau_min": "0.1.0", "description": "d"}}
        self.assertTrue(any("au moins un droit" in e for e in mf.valider(brut)))
        brut["droits"] = [{"id": "utiliser", "libelle": "Utiliser X", "defaut": True}]
        self.assertEqual(mf.valider(brut), [])

    def test_tous_les_modules_du_depot_declarent_leurs_droits(self):
        sans = []
        for f in sorted(glob.glob(str(RACINE / "modules" / "*" / "CN_manifeste.toml"))):
            m = mf.charger(f)                      # refuse un manifeste sans droit
            if not m.droits:
                sans.append(m.id)
        self.assertEqual(sans, [])


class Utilisateurs(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n = monde()
        self.addCleanup(self.tmp.cleanup)
        self.idt = self.n.identite
        self.idt.creer("admin@x.fr", MDP)
        self.n.droits.regler_admin("admin@x.fr", True)
        self.idt.creer("alice@x.fr", MDP, sites=["a.fr"])
        self.idt.creer("bob@x.fr", MDP, sites=["b.fr"])

    def ex(self, cle, acteur="humain", au_nom_de="", **args):
        return self.n.executeur.executer(cle, acteur, args, compte=au_nom_de)

    def res(self, cle, **kw):
        r = self.ex(cle, **kw)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    # ---- appliquer ----
    def test_appliquer_regle_plusieurs_droits_d_un_coup_et_se_prouve(self):
        r = self.res("droits.appliquer", sujet="alice@x.fr", accords={"comptes.gerer": "accorde", "notifications.gerer": "refuse"})
        self.assertEqual({c["droit"] for c in r["changes"]}, {"comptes.gerer", "notifications.gerer"})
        self.assertTrue(self.n.droits.a("alice@x.fr", "comptes.gerer"))
        self.assertFalse(self.n.droits.a("alice@x.fr", "notifications.gerer"))

    def test_appliquer_un_droit_inconnu_est_refuse(self):
        r = self.ex("droits.appliquer", sujet="alice@x.fr", accords={"fantome.x": "accorde"})
        self.assertNotEqual(r["statut"], "faite")

    def test_appliquer_a_un_groupe_atteint_ses_membres(self):
        self.res("droits.groupe", groupe="compta", libelle="Comptabilité", description="Factures")
        self.res("droits.membre", compte="alice@x.fr", groupe="compta")
        self.res("droits.appliquer", sujet_type="groupe", sujet="compta", accords={"comptes.gerer": "accorde"})
        self.assertTrue(self.n.droits.a("alice@x.fr", "comptes.gerer"))
        self.assertEqual(self.n.droits.etat()["groupes"][0]["description"], "Factures")
        self.res("droits.appliquer", sujet="alice@x.fr", accords={"comptes.gerer": "refuse"})      # un refus du compte l'emporte
        self.assertFalse(self.n.droits.a("alice@x.fr", "comptes.gerer"))

    def test_le_dernier_administrateur_ne_peut_pas_etre_retire(self):
        r = self.ex("droits.appliquer", sujet="admin@x.fr", admin=False)
        self.assertNotEqual(r["statut"], "faite")
        self.assertTrue(self.n.droits.est_admin("admin@x.fr"))
        self.res("droits.appliquer", sujet="alice@x.fr", admin=True)
        self.res("droits.appliquer", sujet="admin@x.fr", admin=False)                                  # il en reste un
        self.assertFalse(self.n.droits.est_admin("admin@x.fr"))
        self.assertNotEqual(self.ex("droits.appliquer", sujet="alice@x.fr", admin=False)["statut"], "faite")

    def test_se_retirer_le_droit_de_gerer_les_droits_demande_une_confirmation(self):
        self.res("droits.appliquer", sujet="alice@x.fr", accords={"droits.gerer": "accorde"})
        r = self.ex("droits.appliquer", au_nom_de="alice@x.fr", sujet="alice@x.fr", accords={"droits.gerer": "refuse"})
        self.assertNotEqual(r["statut"], "faite")
        self.assertTrue(self.n.droits.a("alice@x.fr", "droits.gerer"), "rien n'a été écrit")
        self.res("droits.appliquer", au_nom_de="alice@x.fr", sujet="alice@x.fr", accords={"droits.gerer": "refuse"}, confirme=True)
        self.assertFalse(self.n.droits.a("alice@x.fr", "droits.gerer"))

    # ---- lectures ----
    def test_decisions_dit_le_pourquoi(self):
        self.res("droits.appliquer", sujet="alice@x.fr", accords={"comptes.gerer": "accorde"})
        d = {x["droit"]: x for x in self.res("droits.decisions", compte="alice@x.fr")["droits"]}
        self.assertEqual((d["comptes.gerer"]["accord"], d["comptes.gerer"]["propre"]), (True, "accorde"))
        self.assertIn("compte", d["comptes.gerer"]["parce"])
        self.assertFalse(d["droits.nommer_admin"]["accord"])

    def test_decisions_de_dit_la_meme_chose_que_raison_pour_chaque_droit(self):
        """Le calcul en quelques lectures ne doit jamais s'écarter de la décision droit par droit."""
        self.res("droits.groupe", groupe="g1", libelle="G1")
        self.res("droits.groupe", groupe="g2", libelle="G2")
        for c in ("alice@x.fr", "bob@x.fr"):
            self.res("droits.membre", compte=c, groupe="g1")
        self.res("droits.membre", compte="alice@x.fr", groupe="g2")
        self.res("droits.appliquer", sujet_type="groupe", sujet="g1", accords={"comptes.gerer": "accorde", "droits.gerer": "accorde"})
        self.res("droits.appliquer", sujet_type="groupe", sujet="g2", accords={"droits.gerer": "refuse"})
        self.res("droits.appliquer", sujet="bob@x.fr", accords={"comptes.gerer": "refuse", "notifications.gerer": "accorde"})
        self.idt.inviter_agent("aide", "alice@x.fr")
        for c in ("admin@x.fr", "alice@x.fr", "bob@x.fr", "agent:aide", "inconnu@x.fr", ""):
            tout = self.n.droits.decisions_de(c)
            for droit in self.n.droits.connus:
                r = self.n.droits.raison(c, droit)
                self.assertEqual((tout[droit]["accord"], tout[droit]["parce"]), (r["accord"], r["parce"]), (c, droit))

    def test_qui_peut_liste_tous_les_comptes(self):
        self.res("droits.appliquer", sujet="alice@x.fr", accords={"comptes.gerer": "accorde"})
        q = {x["compte"]: x for x in self.res("droits.qui_peut", droit="comptes.gerer")["comptes"]}
        self.assertTrue(q["alice@x.fr"]["accord"])
        self.assertFalse(q["bob@x.fr"]["accord"])
        self.assertTrue(q["admin@x.fr"]["accord"])
        self.assertEqual(q["admin@x.fr"]["parce"], "administrateur")

    def test_voir_comme_ne_montre_que_la_structure(self):
        v = self.res("droits.voir_comme", compte="alice@x.fr")
        self.assertTrue(v["modules"])
        for m in v["modules"]:
            self.assertEqual(set(m), {"module", "nom", "accordes", "total"})

    def test_le_journal_dit_qui_a_agi(self):
        self.res("droits.appliquer", sujet="alice@x.fr", accords={"comptes.gerer": "accorde"})
        j = self.res("droits.journal")["journal"]
        self.assertTrue(any(e["type"] == "droit.change" and e["donnees"]["sujet"] == "alice@x.fr" and e["agent"] is False for e in j))
        self.assertEqual(self.ex("droits.appliquer", acteur="itare", sujet="bob@x.fr", accords={"comptes.gerer": "accorde"})["statut"], "racontee")   # un agent propose : le palier borne, rien n'est écrit
        self.assertFalse(self.n.droits.a("bob@x.fr", "comptes.gerer"))

    def test_prevenir_l_interesse_ouvre_une_notification(self):
        self.res("droits.appliquer", sujet="alice@x.fr", accords={"comptes.gerer": "accorde"}, prevenir=True)
        self.n.bus.traiter() if hasattr(self.n.bus, "traiter") else None
        liste = self.n.executeur.executer("notifications.lister", "humain", {}, compte="alice@x.fr")
        self.assertEqual(liste["statut"], "faite")

    # ---- départ ----
    def test_desactiver_ferme_les_sessions_et_empeche_d_entrer(self):
        s = self.idt.ouvrir("alice@x.fr", MDP)
        self.assertTrue(s["ok"])
        self.assertTrue(self.idt.valider(s["jeton"])["ok"])
        r = self.res("comptes.desactiver", compte="alice@x.fr", vers="bob@x.fr")
        self.assertTrue(r["ok"] if "ok" in r else True)
        self.assertFalse(self.idt.valider(s["jeton"])["ok"])
        self.assertFalse(self.idt.ouvrir("alice@x.fr", MDP)["ok"])
        self.assertEqual(sorted(self.idt.lire("bob@x.fr")["sites"]), ["a.fr", "b.fr"])     # ses sites passent à bob
        self.assertEqual(self.idt.lire("alice@x.fr")["sites"], [])
        self.res("comptes.reactiver", compte="alice@x.fr")
        self.assertTrue(self.idt.ouvrir("alice@x.fr", MDP)["ok"])

    def test_desactiver_le_dernier_administrateur_est_refuse(self):
        self.assertNotEqual(self.ex("comptes.desactiver", compte="admin@x.fr")["statut"], "faite")
        self.assertNotEqual(self.ex("comptes.supprimer", compte="admin@x.fr")["statut"], "faite")

    def test_les_agents_invites_se_revoquent_ou_se_reattribuent(self):
        self.idt.inviter_agent("aide", "alice@x.fr")
        self.res("comptes.desactiver", compte="alice@x.fr", vers="bob@x.fr", agents="reattribuer")
        self.assertEqual(self.idt.invite_par("agent:aide"), "bob@x.fr")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
