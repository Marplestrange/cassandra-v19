# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs des fiches du coffre
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #3d6e96
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs des fiches du coffre : identifiant, note, carte, TOTP, historique, retour arrière.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3d6e96 ▼▼▼
"""Bancs des fiches du coffre (Mon coffre-fort) : un identifiant se crée et se modifie sans rien perdre, l'ancien mot de passe va à l'historique chiffré,
le code TOTP suit la norme (vecteur de la RFC 6238), chaque ouverture s'inscrit au journal, et tout se défait. Un faux serveur Vaultwarden."""
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest import mock
from http.server import HTTPServer
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "tests"))
import CN_main as moteur                      # noqa: E402
from CN_test_coffre import FauxVault          # noqa: E402

BEA, CAM = "bea@x.fr", "cam@x.fr"
GRAINE_RFC = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"          # « 12345678901234567890 » en base32 : la clé d'essai de la RFC 6238


class Monde(unittest.TestCase):
    def setUp(self):
        FauxVault.items = {}
        FauxVault.prochain = 1
        self.httpd = HTTPServer(("127.0.0.1", 0), FauxVault)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.shutdown)
        self.url = "http://127.0.0.1:%d" % self.httpd.server_address[1]
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("coffre", "droits", "comptes", "societes"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True)
        self.n.brancher()
        for m in ("droits", "comptes", "societes", "coffre"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.ctx = self.n.executeur.contextes["coffre"]
        self.ctx.reglage = lambda nom, compte=None: self.url if nom == "vault_url" else (8 if nom == "vault_timeout" else "")

    def ex(self, cap, compte=BEA, **args):
        return self.n.executeur.executer("coffre." + cap, "humain", args, compte=compte)

    def s(self, cap, compte=BEA, **args):
        r = self.ex(cap, compte=compte, **args)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]

    def defaire(self, cap, res):
        self.n.catalogue.get("coffre." + cap).defaire(self.ctx, res)

    def login(self, nom="banque", **v):
        return self.s("fiche_ecrire", name=nom, kind="login", creer=True, valeurs=dict({"username": "bea", "password": "un", "uri": "https://banque.test"}, **v))

    def test_une_fiche_se_cree_s_affiche_et_se_defait(self):
        res = self.ex("fiche_ecrire", name="banque", kind="login", creer=True, valeurs={"username": "bea", "password": "un", "uri": "https://banque.test", "totp": GRAINE_RFC})
        self.assertEqual(res["statut"], "faite", res)
        ligne = [r for r in self.s("list")["secrets"] if r["nom"] == "banque"][0]
        self.assertIn('"login"', ligne["fiche"])
        self.assertNotIn("un", ligne["fiche"].replace("username", "").replace("uri", ""))        # la liste ne porte aucune valeur : ni mot de passe ni graine
        self.assertNotIn(GRAINE_RFC, ligne["fiche"])
        d = self.s("fiche", name="banque")["detail"]
        self.assertEqual((d["kind"], d["username"], d["password"]), ("login", "bea", "un"))
        self.defaire("fiche_ecrire", res["resultat"])
        self.assertIsNone(self.s("fiche", name="banque")["detail"])
        self.assertNotIn("banque", self.s("list")["noms"])

    def test_un_nom_pris_est_refuse(self):
        self.login()
        self.assertNotEqual(self.ex("fiche_ecrire", name="banque", kind="login", creer=True, valeurs={})["statut"], "faite")

    def test_la_modification_ne_perd_rien_et_garde_l_ancien_mot_de_passe(self):
        self.login(totp=GRAINE_RFC)
        res = self.ex("fiche_ecrire", name="banque", patch={"password": "deux"})
        self.assertEqual(res["statut"], "faite", res)
        d = self.s("fiche", name="banque")["detail"]
        self.assertEqual((d["password"], d["username"], d["uri"], d["totp"]), ("deux", "bea", "https://banque.test", GRAINE_RFC))
        self.assertEqual(d["historique_n"], 1)
        self.assertEqual([h["password"] for h in self.s("historique", name="banque")["historique"]], ["un"])
        base = sqlite3.connect(str(next(Path(self.tmp.name).rglob("coffre.db"))))
        brut = base.execute("SELECT valeur_chiffree FROM vault_historique").fetchone()[0]
        base.close()
        self.assertNotEqual(brut, "un")
        self.defaire("fiche_ecrire", res["resultat"])
        self.assertEqual(self.s("fiche", name="banque")["detail"]["password"], "un")

    def test_renommer_garde_la_fiche_et_se_defait(self):
        self.login()
        res = self.ex("fiche_ecrire", name="banque", patch={"name": "ma banque", "uri": "https://autre.test"})
        self.assertEqual(res["statut"], "faite", res)
        self.assertEqual(self.s("list")["noms"], ["ma banque"])
        self.assertEqual(self.s("fiche", name="ma banque")["detail"]["uri"], "https://autre.test")
        self.defaire("fiche_ecrire", res["resultat"])
        self.assertEqual(self.s("list")["noms"], ["banque"])
        self.assertEqual(self.s("fiche", name="banque")["detail"]["uri"], "https://banque.test")

    def test_une_note_simple_reste_un_texte_et_prend_un_champ(self):
        self.s("set", name="memo", valeur="bonjour")
        d = self.s("fiche", name="memo")["detail"]
        self.assertEqual((d["kind"], d["value"]), ("note", "bonjour"))
        self.s("fiche_ecrire", name="memo", patch={"value": "salut"})
        self.assertEqual(self.s("get", name="memo")["valeur"], "salut")                  # toujours un texte simple, lisible par l'ancien chemin

    def test_le_totp_suit_la_rfc_6238(self):
        self.login(totp=GRAINE_RFC)
        code = self.s("totp", name="banque")
        self.assertRegex(code["code"], r"^\d{6}$")
        self.assertEqual(code["periode"], 30)
        self.login("rfc", totp="otpauth://totp/x?secret=%s&digits=8" % GRAINE_RFC)
        with mock.patch("time.time", return_value=59):                    # le vecteur de la RFC 6238 : à t = 59 s, le code à 8 chiffres (SHA1) est 94287082
            r = self.s("totp", name="rfc")
        self.assertEqual((r["code"], r["reste"]), ("94287082", 1))

    def test_une_fiche_sans_cle_totp_le_dit(self):
        self.login()
        self.assertNotEqual(self.ex("totp", name="banque")["statut"], "faite")

    def test_chaque_ouverture_s_inscrit_au_journal_et_jamais_la_valeur(self):
        self.login()
        self.s("fiche", name="banque")
        self.s("trace", name="banque", action="copie")
        actions = [(j["action"], j["secret_name"]) for j in self.s("journal")["journal"]]
        self.assertIn(("fiche", "banque"), actions)
        self.assertIn(("copie", "banque"), actions)
        self.assertNotEqual(self.ex("trace", name="banque", action="n'importe quoi")["statut"], "faite")

    def test_la_fiche_d_une_personne_est_invisible_a_une_autre(self):
        self.login()
        self.assertIsNone(self.s("fiche", compte=CAM, name="banque")["detail"])
        self.assertNotEqual(self.ex("fiche_ecrire", compte=CAM, name="banque", patch={"password": "x"})["statut"], "faite")

    def test_deux_fiches_au_meme_mot_de_passe_se_signalent(self):
        self.login("a", password="meme")
        self.login("b", password="meme")
        self.assertEqual(self.s("fiche", name="a")["detail"]["doublons"], ["b"])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Monde
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
