# ═══════════════════════════════════════════════════════════════════════════
# TITRE      : L'installation d'un module par archive, de bout en bout
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #f72602
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'installation d'un module par archive, de bout en bout : le téléversement HTTP, les capacités du module modules, les droits, le catalogue.
# MÉTHODE    : un vrai noyau, une vraie passerelle HTTP, une vraie archive signée du module d'exemple
# ═══════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=f72602 ▼▼▼
"""Le chemin que prend l'administrateur depuis la page App Store : il dépose une archive (POST d'octets), lit l'examen, consent aux permissions montrées, installe, puis désinstalle.
Un compte sans le droit d'installer, ou sans session, n'obtient rien ; une capacité qui ne reçoit pas de fichier refuse d'en recevoir."""
import http.client
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
import CN_main as moteur  # noqa: E402
from noyau import CN_paquets as paquets  # noqa: E402
from noyau.CN_passerelle import Passerelle  # noqa: E402

MDP = "Essai-Casse-26!"
ADMIN, SIMPLE = "chef@x.fr", "bea@x.fr"


@unittest.skipUnless(shutil.which("openssl"), "openssl absent")
class Installation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        b = self.base = Path(self.tmp.name)
        config = b / "config"
        (config / "cles").mkdir(parents=True)
        priv = b / "editeur.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(priv)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(priv), "-pubout", "-out", str(config / "cles" / "atek.pub")], check=True, capture_output=True)
        patcher = mock.patch.dict(os.environ, {"CASSANDRA_CONFIG": str(config)})
        patcher.start()
        self.addCleanup(patcher.stop)
        mods = b / "modules"
        for m in ("droits", "comptes", "modules"):
            shutil.copytree(RACINE / "modules" / m, mods / m, ignore=shutil.ignore_patterns("__pycache__"))
        self.n = moteur.Noyau(b / "d", mods, {}, gerer_modules=True, exiger_compte=True, extensions=b / "ext")
        self.n.brancher()
        for m in ("droits", "comptes", "modules"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.n.identite.fastpanel = lambda: False
        for c in (ADMIN, SIMPLE):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP}, compte="operateur")
        self.n.droits.regler_admin(ADMIN, True)
        self.g = Passerelle(self.n, "127.0.0.1", 0)
        self.g.demarrer()
        self.addCleanup(self.g.arreter)
        src = b / "src" / "sentinelle"
        shutil.copytree(RACINE / "exemples" / "sentinelle", src)
        self.archive = paquets.construire(src, priv, b / "s.cmod").read_bytes()

    def req(self, methode, chemin, corps=None, brut=None, jeton=None, entetes=None):
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        h = dict(entetes or {})
        data = brut
        if corps is not None:
            data = json.dumps(corps).encode()
            h["Content-Type"] = "application/json"
        if brut is not None:
            h.setdefault("Content-Type", "application/octet-stream")
        if jeton:
            h["Authorization"] = "Bearer " + jeton
        c.request(methode, chemin, body=data, headers=h)
        r = c.getresponse()
        texte = r.read().decode()
        c.close()
        try:
            return r.status, json.loads(texte)
        except ValueError:
            return r.status, texte

    def session(self, compte):
        st, corps = self.req("POST", "/api/connexion", {"compte": compte, "mot_de_passe": MDP})
        self.assertEqual(st, 200, corps)
        return corps["jeton"]

    def test_sans_session_ou_sans_le_droit_rien_n_est_recu(self):
        st, _ = self.req("POST", "/api/televerser/modules.examiner", brut=self.archive)
        self.assertEqual(st, 401)
        st, corps = self.req("POST", "/api/televerser/modules.examiner", brut=self.archive, jeton=self.session(SIMPLE))
        self.assertNotEqual(st, 200, corps)
        self.assertFalse((self.base / "d" / "quarantaine").exists() and list((self.base / "d" / "quarantaine").glob("*.cmod")))

    def test_une_capacite_qui_ne_recoit_pas_de_fichier_refuse_d_en_recevoir(self):
        st, corps = self.req("POST", "/api/televerser/modules.lister", brut=b"abc", jeton=self.session(ADMIN))
        self.assertEqual(st, 404, corps)

    def test_un_fichier_vide_ou_demesure_est_refuse_sans_etre_lu(self):
        jeton = self.session(ADMIN)
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        c.request("POST", "/api/televerser/modules.examiner", body=b"", headers={"Authorization": "Bearer " + jeton, "Content-Type": "application/octet-stream"})
        r = c.getresponse()
        r.read()
        self.assertEqual(r.status, 400)
        c.close()
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        c.putrequest("POST", "/api/televerser/modules.examiner")
        for k, v in (("Authorization", "Bearer " + jeton), ("Content-Type", "application/octet-stream"), ("Content-Length", str(40 * 2 ** 20))):
            c.putheader(k, v)
        c.endheaders()                                                    # 40 Mo annoncés, aucun octet envoyé
        r = c.getresponse()
        r.read()
        self.assertEqual(r.status, 400)
        c.close()

    def test_le_chemin_de_l_administrateur_deposer_examiner_consentir_installer_desinstaller(self):
        jeton = self.session(ADMIN)
        st, rep = self.req("POST", "/api/televerser/modules.examiner", brut=self.archive, jeton=jeton)
        self.assertEqual((st, rep["statut"]), (200, "faite"), rep)
        e = rep["resultat"]
        self.assertEqual((e["id"], e["statut"], e["signe"], e["autorise"]), ("sentinelle", "nouveau", True, True))
        # sans le bon consentement : refusé
        st, rep = self.req("POST", "/api/agir/modules.installer", {"args": {"jeton": e["jeton"], "consentement": "faux"}}, jeton=jeton)
        self.assertNotEqual(rep.get("statut"), "faite", rep)
        self.assertFalse((self.base / "ext" / "sentinelle").exists())
        # avec : installé, et le catalogue le voit
        st, rep = self.req("POST", "/api/agir/modules.installer", {"args": {"jeton": e["jeton"], "consentement": e["empreinte_permissions"]}}, jeton=jeton)
        self.assertEqual((st, rep["statut"]), (200, "faite"), rep)
        self.assertTrue((self.base / "ext" / "sentinelle" / "CN_manifeste.toml").is_file())
        st, cat = self.req("POST", "/api/agir/modules.lister", {"args": {}}, jeton=jeton)
        m = next(x for x in cat["resultat"]["modules"] if x["id"] == "sentinelle")
        self.assertTrue(m["extension"])
        self.assertIn(m["etat"], ("inactif", "a_installer"))             # déposé, jamais activé d'office
        st, v = self.req("POST", "/api/agir/modules.versions", {"args": {"module": "sentinelle"}}, jeton=jeton)
        self.assertEqual([x["acte"] for x in v["resultat"]["journal"]], ["installe"])
        # désinstaller : le dossier part en sauvegarde
        st, rep = self.req("POST", "/api/agir/modules.desinstaller", {"args": {"module": "sentinelle"}}, jeton=jeton)
        self.assertEqual((st, rep["statut"]), (200, "faite"), rep)
        self.assertFalse((self.base / "ext" / "sentinelle").exists())
        self.assertTrue(list((self.base / "d" / "modules_sauvegardes" / "sentinelle").iterdir()))

    def depose(self, mid, corps):
        d = self.base / "ext" / mid
        d.mkdir(parents=True, exist_ok=True)
        entete = '[module]\nid = "%s"\nnom = "%s"\nversion = "0.1.0"\nnoyau_min = "0.1.0"\ndescription = "essai"\nconfiance = "local"\nimportance = "optionnel"\nsans = "rien"\n[[droits]]\nid = "utiliser"\nlibelle = "Utiliser"\ndefaut = true\n' % (mid, mid.capitalize())
        (d / "CN_manifeste.toml").write_text(entete + corps, encoding="utf-8")
        (d / "CN_module.py").write_text("def brancher(ctx):\n    pass\n", encoding="utf-8")

    def test_un_module_lit_ce_que_les_autres_branchent_chez_lui_sans_les_connaitre(self):
        self.depose("hote", '[[points_extension]]\nid = "colonne"\nlibelle = "Une colonne"\nattend = ["titre"]\n')
        self.depose("invite", '[[contributions]]\npoint = "hote:colonne"\nid = "prix"\nlibelle = "Prix"\n[contributions.donnees]\ntitre = "Prix"\n')

        def lire():
            return self.n.executeur.executer("modules.contributions", "humain", {}, compte=ADMIN)["resultat"]
        self.assertEqual(lire()["points"], [])                                               # rien n'est actif : rien ne se branche
        for m in ("hote", "invite"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        r = lire()
        self.assertEqual([p["point"] for p in r["points"]], ["hote:colonne"])
        self.assertEqual([(c["module"], c["id"], c["donnees"]) for c in r["points"][0]["contributions"]], [("invite", "prix", {"titre": "Prix"})])
        self.assertTrue(self.n.desactiver("invite")["ok"])
        self.assertEqual(lire()["points"][0]["contributions"], [])                           # un module désactivé ne contribue plus

    def test_la_sante_d_un_module_se_lit_avec_un_verdict(self):
        r = self.n.executeur.executer("modules.sante", "humain", {"module": "droits"}, compte=ADMIN)
        self.assertEqual(r["statut"], "faite", r)
        sante = r["resultat"]
        self.assertIn(sante["verdict"], ("sain", "a_surveiller", "en_echec"))
        self.assertEqual((sante["module"], sante["extension"]), ("droits", False))
        for cle in ("moteurs", "detecteurs_coupes", "capacites_24h", "constats_ouverts", "mode_sur"):
            self.assertIn(cle, sante)
        r = self.n.executeur.executer("modules.sante", "humain", {"module": "inconnu"}, compte=ADMIN)
        self.assertNotEqual(r["statut"], "faite")

    def test_le_mode_sur_ignore_les_extensions(self):
        with mock.patch.dict(os.environ, {"CASSANDRA_MODE_SUR": "1"}):
            self.assertIsNone(moteur._extensions())
        with mock.patch.dict(os.environ, {"CASSANDRA_MODE_SUR": "0", "CASSANDRA_EXTENSIONS": "/tmp/x"}):
            self.assertEqual(moteur._extensions(), "/tmp/x")

    def test_les_agents_ne_peuvent_pas_installer(self):
        r = self.n.executeur.executer("modules.installer", "cassandra", {"jeton": "abc", "consentement": "x"}, compte=ADMIN)
        self.assertNotEqual(r["statut"], "faite")


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le banc de l'installation de bout en bout.
# EC : néant.
# LIEN : noyau/CN_cycle.py, noyau/CN_passerelle.py (_televerser), modules/modules (les capacités).
