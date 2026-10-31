# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du durcissement des secrets
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #217f48
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du durcissement des secrets : journal des lectures, âge et rotation, secrets-pièges.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=217f48 ▼▼▼
"""Bancs du durcissement des secrets : journal des lectures, âge et rotation, secrets-pièges."""
import json
import shutil
import sqlite3
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                      # noqa: E402
from noyau import CN_reglages as rgl          # noqa: E402
from noyau.CN_bus import TOUT                 # noqa: E402

MANIFESTE = textwrap.dedent('''
    [module]
    id = "cof"
    nom = "Module d'essai"
    version = "0.1.0"
    noyau_min = "0.1.0"
    description = "Un module qui déclare des secrets."

    [[droits]]
    id = "utiliser"
    libelle = "Utiliser"
    defaut = true

    [[reglages]]
    id = "jeton"
    libelle = "Jeton global"
    type = "secret"

    [[reglages]]
    id = "mdp"
    libelle = "Mot de passe de la boîte"
    type = "secret"
    portee = "compte"
''')
CODE = "def brancher(ctx):\n    pass\n"
VALEUR = "valeur-inventee-pour-le-banc-4410"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        mods = self.base / "modules"
        shutil.copytree(RACINE / "modules" / "reglages", mods / "reglages")
        shutil.copytree(RACINE / "modules" / "droits", mods / "droits")
        (mods / "cof").mkdir()
        (mods / "cof" / "CN_manifeste.toml").write_text(MANIFESTE, encoding="utf-8")
        (mods / "cof" / "CN_module.py").write_text(CODE, encoding="utf-8")
        self.n = moteur.Noyau(self.base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("reglages", "cof"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin("chef@x.fr", True)
        self.rg = self.n.reglages

    def ex(self, cap, compte="bea@x.fr", acteur="humain", **args):
        return self.n.executeur.executer("reglages." + cap, acteur, args, compte=compte)

    def sql(self, requete, params=()):
        c = sqlite3.connect(str(self.base / "d" / "noyau.db"))
        try:
            r = c.execute(requete, params).fetchall()
            c.commit()
            return r
        finally:
            c.close()

    def tout_le_fichier(self):
        return (self.base / "d" / "noyau.db").read_bytes() + b"".join(p.read_bytes() for p in (self.base / "d").glob("noyau.db-*"))


class JournalDesLectures(Monde):
    def test_lire_un_secret_laisse_module_compte_nom_moment_jamais_la_valeur(self):
        self.ex("regler_secret", cle="cof.mdp", valeur=VALEUR)
        avant = time.time()
        self.assertEqual(self.rg.valeur("cof.mdp", "bea@x.fr"), VALEUR)
        r = self.ex("secrets_lectures", compte="chef@x.fr")
        self.assertEqual(r["statut"], "faite", r)
        ligne = r["resultat"]["lectures"][0]
        self.assertEqual((ligne["module"], ligne["cle"], ligne["compte"], ligne["piege"]), ("cof", "cof.mdp", "bea@x.fr", False))
        self.assertGreaterEqual(ligne["ts"], avant - 1)
        self.assertEqual(r["resultat"]["par_secret"][0]["lectures"], 1)
        self.assertNotIn(VALEUR.encode(), self.tout_le_fichier())
        self.assertNotIn(VALEUR, json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str))

    def test_la_liste_d_administration_et_l_ecriture_ne_comptent_pas_comme_une_lecture(self):
        self.ex("regler_secret", cle="cof.mdp", valeur=VALEUR)
        self.ex("lire")
        self.ex("lire", compte="chef@x.fr")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reglages_lectures")[0][0], 0)

    def test_un_secret_non_pose_ou_un_texte_ordinaire_ne_laissent_pas_de_trace(self):
        self.rg.valeur("cof.jeton")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reglages_lectures")[0][0], 0)

    def test_une_erreur_de_lecture_ne_porte_pas_la_valeur(self):
        self.ex("regler_secret", cle="cof.mdp", valeur=VALEUR)
        self.sql("UPDATE reglages SET valeur=? WHERE cle='cof.mdp'", (json.dumps("enc1:AAAA" + "A" * 40),))
        with self.assertRaises(rgl.SecretIllisible) as e:
            self.rg.valeur("cof.mdp", "bea@x.fr")
        self.assertNotIn(VALEUR, str(e.exception))
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reglages_lectures")[0][0], 0, "une lecture qui échoue n'est pas une lecture réussie")

    def test_le_journal_est_ferme_aux_non_administrateurs_et_aux_agents(self):
        self.assertEqual(self.ex("secrets_lectures", compte="bea@x.fr")["statut"], "refuse")
        for acteur in ("itare", "cassandra", "agent"):
            self.assertEqual(self.ex("secrets_lectures", compte="chef@x.fr", acteur=acteur)["statut"], "refuse", acteur)

    def test_le_journal_est_elague_au_demarrage(self):
        self.ex("regler_secret", cle="cof.mdp", valeur=VALEUR)
        self.rg.valeur("cof.mdp", "bea@x.fr")
        self.sql("UPDATE reglages_lectures SET ts=?", (time.time() - 400 * 86400,))
        self.rg.demarrer()
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reglages_lectures")[0][0], 0)


class AgeEtRotation(Monde):
    def test_la_date_de_pose_est_gardee_et_l_age_se_lit_sans_valeur(self):
        self.ex("regler_secret", cle="cof.jeton", compte="chef@x.fr", valeur=VALEUR)
        r = self.ex("secrets_ages", compte="chef@x.fr")
        self.assertEqual(r["statut"], "faite", r)
        s = {x["cle"]: x for x in r["resultat"]["secrets"]}["cof.jeton"]
        self.assertEqual((s["age_jours"], s["a_renouveler"], s["estimee"]), (0, False, False))
        self.assertNotIn(VALEUR, json.dumps(r, default=str))

    def test_un_secret_de_plus_de_90_jours_est_signale_et_le_seuil_se_regle(self):
        self.ex("regler_secret", cle="cof.jeton", compte="chef@x.fr", valeur=VALEUR)
        self.ex("regler_secret", cle="cof.mdp", valeur=VALEUR + "-bis")
        self.sql("UPDATE reglages_poses SET pose=? WHERE cle='cof.jeton'", (time.time() - 100 * 86400,))
        r = self.ex("secrets_ages", compte="chef@x.fr")["resultat"]
        self.assertEqual((r["seuil_jours"], [x["cle"] for x in r["a_renouveler"]]), (90, ["cof.jeton"]))
        self.assertEqual(self.ex("regler", cle="reglages.secret_age_max_jours", compte="chef@x.fr", valeur=120)["statut"], "faite")
        self.assertEqual(self.ex("secrets_ages", compte="chef@x.fr")["resultat"]["a_renouveler"], [])
        self.assertEqual(len(self.ex("secrets_ages", compte="chef@x.fr", seuil_jours=0)["resultat"]["secrets"]), 2)

    def test_un_secret_pose_avant_la_date_de_pose_est_date_de_sa_derniere_modification(self):
        self.ex("regler_secret", cle="cof.jeton", compte="chef@x.fr", valeur=VALEUR)
        self.sql("DELETE FROM reglages_poses")
        self.sql("UPDATE reglages SET maj=?", (time.time() - 200 * 86400,))
        s = self.ex("secrets_ages", compte="chef@x.fr")["resultat"]["secrets"][0]
        self.assertEqual((s["estimee"], s["a_renouveler"]), (True, True))

    def test_renouveler_remet_l_age_a_zero_retirer_efface_la_date_et_le_retour_arriere_ne_rajeunit_pas(self):
        self.ex("regler_secret", cle="cof.jeton", compte="chef@x.fr", valeur=VALEUR)
        vieux = time.time() - 100 * 86400
        self.sql("UPDATE reglages_poses SET pose=?", (vieux,))
        r = self.ex("regler_secret", cle="cof.jeton", compte="chef@x.fr", valeur=VALEUR + "-neuf")
        self.assertEqual(self.sql("SELECT pose FROM reglages_poses")[0][0] > vieux + 86400, True)
        self.assertEqual(r["resultat"]["avant_pose"], vieux)
        self.rg.poser_chiffre("cof.jeton", "", r["resultat"]["avant_chiffre"], "chef", r["resultat"]["avant_pose"])
        self.assertAlmostEqual(self.sql("SELECT pose FROM reglages_poses")[0][0], vieux, places=3)
        self.assertEqual(self.rg.valeur("cof.jeton"), VALEUR)
        self.ex("reinitialiser", cle="cof.jeton", compte="chef@x.fr")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reglages_poses")[0][0], 0)

    def test_les_ages_sont_fermes_aux_agents(self):
        for acteur in ("itare", "cassandra", "agent"):
            self.assertEqual(self.ex("secrets_ages", compte="chef@x.fr", acteur=acteur)["statut"], "refuse", acteur)


class SecretsPieges(Monde):
    PIEGE = "fastpanel.jeton_admin_ancien"

    def test_lire_un_piege_leve_l_alarme_au_journal_critique_et_au_bus(self):
        with self.assertLogs("noyau.CN_reglages", level="CRITICAL") as j:
            v = self.rg.valeur(self.PIEGE, "bea@x.fr")
        self.assertIn(self.PIEGE, "\n".join(j.output))
        self.assertTrue(v and v.startswith("fp_"))
        evts = self.n.bus.recents(portee=TOUT, limite=50, type_prefixe="noyau.piege_touche")
        self.assertEqual(len(evts), 1)
        constats = self.n.bus.recents(portee=TOUT, limite=50, type_prefixe="constat.ouvert")
        crit = [e for e in constats if e["donnees"].get("detecteur") == "piege_secret"]
        self.assertEqual(len(crit), 1)
        self.assertEqual(crit[0]["donnees"]["niveau"], "critique")
        self.assertEqual(crit[0]["compte"], "", "l'alerte va aux administrateurs, pas au compte qui a lu")

    def test_la_lecture_est_notee_comme_piege_et_visible_de_l_administrateur(self):
        self.rg.valeur(self.PIEGE, "bea@x.fr")
        r = self.ex("pieges", compte="chef@x.fr")["resultat"]
        self.assertIn(self.PIEGE, r["pieges"])
        self.assertEqual([(x["cle"], x["compte"]) for x in r["touches"]], [(self.PIEGE, "bea@x.fr")])
        self.assertEqual(self.ex("pieges", compte="bea@x.fr")["statut"], "refuse")

    def test_la_valeur_fausse_est_stable_ne_ressemble_a_aucun_vrai_secret_et_ne_se_stocke_pas(self):
        self.ex("regler_secret", cle="cof.jeton", compte="chef@x.fr", valeur=VALEUR)
        a = self.rg.valeur(self.PIEGE)
        self.assertEqual(a, self.rg.valeur(self.PIEGE))
        self.assertNotEqual(a, self.rg.valeur("dns.cle_zone_secours"))
        self.assertNotIn(VALEUR, a)
        self.assertNotIn(a.encode(), self.tout_le_fichier())

    def test_un_piege_ne_se_voit_pas_dans_les_listes_et_ne_s_ecrit_pas(self):
        noms = {x["cle"] for x in self.ex("lire", compte="chef@x.fr")["resultat"]["reglages"]}
        self.assertFalse(noms & set(rgl.PIEGES))
        self.assertNotEqual(self.ex("regler_secret", compte="chef@x.fr", cle=self.PIEGE, valeur="x")["statut"], "faite")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM reglages WHERE cle=?", (self.PIEGE,))[0][0], 0)

    def test_aucun_module_ne_declare_un_nom_de_piege(self):
        declares = set()
        for toml in (RACINE / "modules").glob("*/CN_manifeste.toml"):
            mod = toml.parent.name
            texte = toml.read_text(encoding="utf-8")
            for bloc in texte.split("[[reglages]]")[1:]:
                ligne = next((l for l in bloc.splitlines() if l.strip().startswith("id")), "")
                declares.add("%s.%s" % (mod, ligne.split("=", 1)[-1].strip().strip('"')))
        self.assertFalse(declares & set(rgl.PIEGES), "un nom de piège est réel : toute lecture légitime lèverait l'alarme")

    def test_le_noyau_ne_gele_rien_seul(self):
        self.rg.valeur(self.PIEGE, "bea@x.fr")
        self.assertEqual(self.n.freins(), set())
        self.assertFalse(self.n.en_crise())


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde, JournalDesLectures, AgeEtRotation, SecretsPieges
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
