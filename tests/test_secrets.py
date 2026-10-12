"""Bancs des secrets : chiffrés au repos, liés à leur réglage et à leur compte, jamais dans un historique ni un résultat, et défaisables sans être lus."""
import json
import shutil
import sqlite3
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import main as moteur                      # noqa: E402
from noyau import reglages as rgl          # noqa: E402
from noyau.bus import TOUT                 # noqa: E402

MANIFESTE = textwrap.dedent('''
    [module]
    id = "cof"
    nom = "Coffre d'essai"
    version = "0.1.0"
    noyau_min = "0.1.0"
    description = "Un module qui déclare des secrets."

    [[reglages]]
    id = "jeton"
    libelle = "Jeton global"
    type = "secret"

    [[reglages]]
    id = "mdp"
    libelle = "Mot de passe de la boîte"
    type = "secret"
    portee = "compte"

    [[reglages]]
    id = "hote"
    libelle = "Hôte"
    portee = "compte"
''')
CODE = "def brancher(ctx):\n    pass\n"


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        mods = self.base / "modules"
        shutil.copytree(RACINE / "modules" / "reglages", mods / "reglages")
        shutil.copytree(RACINE / "modules" / "droits", mods / "droits")
        (mods / "cof").mkdir()
        (mods / "cof" / "manifeste.toml").write_text(MANIFESTE, encoding="utf-8")
        (mods / "cof" / "module.py").write_text(CODE, encoding="utf-8")
        self.n = moteur.Noyau(self.base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("reglages", "cof"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.droits.regler_admin("chef@x.fr", True)
        self.rg = self.n.reglages

    def ex(self, cap, compte="bea@x.fr", **args):
        return self.n.executeur.executer("reglages." + cap, "humain", args, compte=compte)

    def brut(self, cle, compte=""):
        c = sqlite3.connect(str(self.base / "d" / "noyau.db"))
        try:
            r = c.execute("SELECT valeur FROM reglages WHERE cle=? AND compte=?", (cle, compte)).fetchone()
            return json.loads(r[0]) if r else None
        finally:
            c.close()

    def tout_le_fichier(self):
        return (self.base / "d" / "noyau.db").read_bytes() + b"".join(p.read_bytes() for p in (self.base / "d").glob("noyau.db-*"))


class Chiffrement(Monde):
    def test_le_secret_est_chiffre_au_repos_et_rendu_en_clair_au_module(self):
        self.assertEqual(self.ex("regler_secret", cle="cof.mdp", valeur="Sup3r-Secret-Mdp")["statut"], "faite")
        stocke = self.brut("cof.mdp", "bea@x.fr")
        self.assertTrue(stocke.startswith("enc1:"))
        self.assertNotIn(b"Sup3r-Secret-Mdp", self.tout_le_fichier())
        self.assertEqual(self.rg.valeur("cof.mdp", "bea@x.fr"), "Sup3r-Secret-Mdp")

    def test_la_cle_est_dans_un_fichier_a_part_lisible_de_son_proprietaire(self):
        self.ex("regler_secret", cle="cof.mdp", valeur="x")
        cle = self.base / "d" / "secrets.cle"
        self.assertEqual(len(cle.read_bytes()), 32)
        if sys.platform != "win32":
            self.assertEqual(cle.stat().st_mode & 0o077, 0)

    def test_le_secret_survit_a_un_redemarrage_avec_la_meme_cle(self):
        self.ex("regler_secret", cle="cof.mdp", valeur="persistant")
        n2 = moteur.Noyau(self.base / "d", self.base / "modules", {}, gerer_modules=True)
        n2.brancher()
        n2.activer("cof")
        self.assertEqual(n2.reglages.valeur("cof.mdp", "bea@x.fr"), "persistant")

    def test_une_valeur_chiffree_recopiee_ailleurs_ne_se_lit_pas(self):
        self.ex("regler_secret", cle="cof.mdp", valeur="le-mdp-de-bea")
        chiffre = self.brut("cof.mdp", "bea@x.fr")
        c = sqlite3.connect(str(self.base / "d" / "noyau.db"))
        c.execute("INSERT INTO reglages(cle, compte, valeur, maj, par) VALUES('cof.mdp','leo@x.fr',?,0,'')", (json.dumps(chiffre),))
        c.commit()
        c.close()
        with self.assertRaises(rgl.SecretIllisible):
            self.rg.valeur("cof.mdp", "leo@x.fr")

    def test_une_valeur_alteree_est_dite_illisible_pas_rendue_fausse(self):
        self.ex("regler_secret", cle="cof.mdp", valeur="intact")
        chiffre = self.brut("cof.mdp", "bea@x.fr")
        c = sqlite3.connect(str(self.base / "d" / "noyau.db"))
        c.execute("UPDATE reglages SET valeur=? WHERE cle='cof.mdp'", (json.dumps(chiffre[:-4] + "AAAA"),))
        c.commit()
        c.close()
        with self.assertRaises(rgl.SecretIllisible):
            self.rg.valeur("cof.mdp", "bea@x.fr")

    def test_un_secret_reste_en_clair_d_avant_le_chiffrement_est_chiffre_a_sa_premiere_lecture(self):
        c = sqlite3.connect(str(self.base / "d" / "noyau.db"))
        c.execute("INSERT INTO reglages(cle, compte, valeur, maj, par) VALUES('cof.jeton','',?,0,'')", (json.dumps("ancien-en-clair"),))
        c.commit()
        c.close()
        self.assertEqual(self.rg.valeur("cof.jeton", ""), "ancien-en-clair")
        self.assertTrue(self.brut("cof.jeton").startswith("enc1:"))
        self.assertNotIn(b"ancien-en-clair", self.tout_le_fichier())

    def test_sans_la_bibliotheque_un_secret_n_est_pas_ecrit_en_clair(self):
        ancien = rgl.AESGCM
        rgl.AESGCM = None
        try:
            r = self.ex("regler_secret", cle="cof.mdp", valeur="ne-doit-pas-etre-ecrit")
        finally:
            rgl.AESGCM = ancien
        self.assertEqual(r["statut"], "echec")
        self.assertIsNone(self.brut("cof.mdp", "bea@x.fr"))
        self.assertNotIn(b"ne-doit-pas-etre-ecrit", self.tout_le_fichier())

    def test_un_texte_ordinaire_reste_en_clair(self):
        self.ex("regler", cle="cof.hote", valeur="imap.exemple.fr")
        self.assertEqual(self.brut("cof.hote", "bea@x.fr"), "imap.exemple.fr")


class Journal(Monde):
    def test_ni_l_historique_ni_le_resultat_ni_le_journal_ne_portent_le_secret(self):
        r1 = self.ex("regler_secret", cle="cof.mdp", valeur="premier-secret")
        r2 = self.ex("regler_secret", cle="cof.mdp", valeur="second-secret")
        self.assertEqual((r2["resultat"]["avant"], r2["resultat"]["apres"]), ("***", "***"))
        histo = self.ex("historique", compte="chef@x.fr", cle="cof.mdp", pour_compte="bea@x.fr")["resultat"]["historique"]
        self.assertEqual({h["apres"] for h in histo}, {"***"})
        brut = json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str)
        for s in ("premier-secret", "second-secret"):
            self.assertNotIn(s, brut)
            self.assertNotIn(s.encode(), self.tout_le_fichier())
        self.assertNotIn("premier-secret", json.dumps(r2, default=str))

    def test_la_liste_masque_le_secret(self):
        self.ex("regler_secret", cle="cof.mdp", valeur="x-secret")
        lignes = {l["cle"]: l for l in self.ex("lire")["resultat"]["reglages"]}
        self.assertEqual(lignes["cof.mdp"]["valeur"], "***")


class Retour(Monde):
    def test_le_retour_remet_l_ancien_secret_sans_l_avoir_lu(self):
        self.ex("regler_secret", cle="cof.mdp", valeur="ancien")
        r = self.ex("regler_secret", cle="cof.mdp", valeur="nouveau")
        self.assertEqual(self.rg.valeur("cof.mdp", "bea@x.fr"), "nouveau")
        self.n.catalogue.get("reglages.regler_secret").defaire(self.n.executeur.contextes["reglages"], r["resultat"])
        self.assertEqual(self.rg.valeur("cof.mdp", "bea@x.fr"), "ancien")

    def test_le_retour_d_un_premier_secret_le_retire(self):
        r = self.ex("regler_secret", cle="cof.mdp", valeur="premier")
        self.n.catalogue.get("reglages.regler_secret").defaire(self.n.executeur.contextes["reglages"], r["resultat"])
        self.assertIsNone(self.brut("cof.mdp", "bea@x.fr"))

    def test_reinitialiser_puis_defaire_remet_le_secret(self):
        self.ex("regler_secret", cle="cof.mdp", valeur="garde-moi")
        r = self.ex("reinitialiser", cle="cof.mdp")
        self.assertIsNone(self.brut("cof.mdp", "bea@x.fr"))
        self.n.catalogue.get("reglages.reinitialiser").defaire(self.n.executeur.contextes["reglages"], r["resultat"])
        self.assertEqual(self.rg.valeur("cof.mdp", "bea@x.fr"), "garde-moi")


class Droits(Monde):
    def test_un_compte_pose_son_propre_secret_sans_droit_particulier(self):
        self.assertEqual(self.ex("regler_secret", cle="cof.mdp", valeur="le-mien")["statut"], "faite")

    def test_pas_le_secret_d_un_autre_compte_ni_un_secret_global_sans_le_droit(self):
        self.assertIn(self.ex("regler_secret", cle="cof.mdp", valeur="x", pour_compte="leo@x.fr")["statut"], ("echec", "refuse"))
        self.assertIn(self.ex("regler_secret", cle="cof.jeton", valeur="x")["statut"], ("echec", "refuse"))
        self.assertEqual(self.ex("regler_secret", compte="chef@x.fr", cle="cof.jeton", valeur="global-admin")["statut"], "faite")

    def test_le_secret_d_un_compte_n_est_pas_celui_d_un_autre(self):
        self.ex("regler_secret", cle="cof.mdp", valeur="celui-de-bea")
        self.ex("regler_secret", compte="leo@x.fr", cle="cof.mdp", valeur="celui-de-leo")
        self.assertEqual((self.rg.valeur("cof.mdp", "bea@x.fr"), self.rg.valeur("cof.mdp", "leo@x.fr")), ("celui-de-bea", "celui-de-leo"))


if __name__ == "__main__":
    unittest.main()
