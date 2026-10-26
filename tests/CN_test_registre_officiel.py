# ═══════════════════════════════════════════════════════════════════════════
# TITRE      : Le registre officiel : index signé, éditeurs vérifiés, révocations, niveaux de confiance
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #b6a67b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le registre officiel : l'index signé par la racine EMBARQUÉE, les éditeurs vérifiés, les révocations et les trois niveaux de confiance.
# MÉTHODE    : un vrai serveur HTTP local sert un index signé et des archives signées (openssl, Ed25519) ; la racine de l'essai remplace celle de l'application
# ═══════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b6a67b ▼▼▼
"""Ce qui compte : un index qui n'est pas signé par la racine embarquée, qui est modifié, périmé ou daté du futur, n'est JAMAIS cru ; une archive n'est « officielle » que si une clé
racine l'a signée, « vérifiée » que si l'index SIGNÉ déclare son éditeur ; une clé posée à la main ne se fait pas passer pour l'officiel ; une version révoquée ne s'installe pas."""
import base64
import hashlib
import http.server
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_cycle as C, CN_manifeste as mf, CN_paquets as paquets, CN_registre_officiel as R  # noqa: E402


def cle(dossier: Path, nom: str):
    priv = dossier / (nom + ".pem")
    subprocess.run(["openssl", "genpkey", "-algorithm", "ed25519", "-out", str(priv)], check=True, capture_output=True)
    pub = subprocess.run(["openssl", "pkey", "-in", str(priv), "-pubout"], check=True, capture_output=True).stdout.decode().replace(chr(13), "")
    return priv, pub


@unittest.skipUnless(shutil.which("openssl"), "openssl absent")
class Officiel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        b = self.base = Path(self.tmp.name)
        self.racine_priv, self.racine_pub = cle(b, "racine")
        self.acme_priv, self.acme_pub = cle(b, "acme")
        self.intrus_priv, self.intrus_pub = cle(b, "intrus")
        self.fichiers = {}
        self.archives = {}
        self.ajouter_archive("sentinelle", self.racine_priv, "cassandra")                 # un module officiel : signé par la racine
        self.ajouter_archive("chezacme", self.acme_priv, "acme")                          # un module d'éditeur
        self.ajouter_archive("louche", self.intrus_priv, "intrus")                        # signé par une clé que personne ne connaît
        self.editeurs = [{"id": "acme", "nom": "Acme", "verifie": True, "cle": self.acme_pub}]
        self.revocations = []
        self.emis, self.expire = time.time() - 60, time.time() + 86400
        parent = self

        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path in parent.fichiers:
                    corps = parent.fichiers[self.path]
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(corps)))
                    self.end_headers()
                    self.wfile.write(corps)
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, *a):
                pass

        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.addCleanup(self.srv.shutdown)
        self.url = "http://127.0.0.1:%d/index.json" % self.srv.server_address[1]
        self.ext = b / "ext"
        self.ext.mkdir()
        (b / "cles").mkdir()
        self.cycle = self.nouveau_cycle()
        self.publier()

    def nouveau_cycle(self, racine=None):
        return C.Cycle(self.ext, self.base / "d", self.base / "cles", lambda: [(mf.charger(f), True) for f in sorted(self.ext.glob("*/CN_manifeste.toml"))], lambda: set(),
                       cles_racine=racine if racine is not None else {"principale": self.racine_pub}, url_officielle=self.url)

    def ajouter_archive(self, mid, priv, editeur):
        src = self.base / "src" / mid
        if src.parent.exists() and src.exists():
            shutil.rmtree(src)
        shutil.copytree(RACINE / "exemples" / "sentinelle", src)
        f = src / "CN_manifeste.toml"
        t = f.read_text(encoding="utf-8").replace('id = "sentinelle"', 'id = "%s"' % mid, 1)
        f.write_text(t, encoding="utf-8")
        a = paquets.construire(src, priv, self.base / (mid + ".cmod")).read_bytes()
        self.archives[mid] = {"octets": a, "editeur": editeur}
        self.fichiers["/modules/%s.cmod" % mid] = a

    def index(self, **remplace) -> dict:
        brut = {"format": 1, "emis": self.emis, "expire": self.expire, "editeurs": self.editeurs, "revocations": self.revocations, "modules": [
            {"id": mid, "nom": mid.capitalize(), "version": "0.1.2", "description": "essai", "url": "modules/%s.cmod" % mid, "sha256": hashlib.sha256(a["octets"]).hexdigest(),
             "taille": len(a["octets"]), "editeur": a["editeur"]} for mid, a in self.archives.items()]}
        brut.update(remplace)
        return brut

    def publier(self, priv=None, **remplace):
        octets = (json.dumps(self.index(**remplace), sort_keys=True) + "\n").encode()
        self.fichiers["/index.json"] = octets
        self.fichiers["/index.json.sig"] = R.signer(octets, priv or self.racine_priv)

    def modules(self):
        return {m["id"]: m for m in self.cycle.registre_officiel()["modules"]}

    def test_l_index_signe_par_la_racine_donne_les_modules_et_leurs_niveaux(self):
        r = self.cycle.registre_officiel()
        self.assertEqual((r["officiel"], r["signe_par"]), (True, "principale"))
        m = {x["id"]: x for x in r["modules"]}
        self.assertEqual((m["sentinelle"]["niveau"], m["chezacme"]["niveau"], m["louche"]["niveau"]), ("officiel", "verifie", ""))
        self.assertEqual([e["id"] for e in r["editeurs"]], ["acme"])

    def test_un_module_officiel_et_un_module_d_editeur_verifie_s_examinent_avec_leur_niveau(self):
        e = self.cycle.telecharger_officiel("sentinelle")
        self.assertEqual((e["niveau"], e["editeur"], e["autorise"]), ("officiel", "cassandra-principale", True))
        e = self.cycle.telecharger_officiel("chezacme")
        self.assertEqual((e["niveau"], e["editeur"], e["autorise"]), ("verifie", "ed_acme", True))

    def test_une_archive_signee_par_un_inconnu_est_refusee_meme_listee_par_le_registre(self):
        e = self.cycle.telecharger_officiel("louche")
        self.assertEqual((e["niveau"], e["signe"], e["autorise"]), ("", False, False))
        self.assertTrue(any("non signé" in r for r in e["raisons"]), e["raisons"])

    def test_un_editeur_que_l_index_ne_declare_pas_verifie_n_est_pas_cru(self):
        self.editeurs = []
        self.publier()
        e = self.cycle.telecharger_officiel("chezacme")
        self.assertEqual((e["niveau"], e["autorise"]), ("", False))
        self.editeurs = [{"id": "acme", "nom": "Acme", "verifie": False, "cle": self.acme_pub}]       # candidat non vérifié : sa clé ne compte pas
        self.publier()
        self.assertFalse(self.cycle.telecharger_officiel("chezacme")["autorise"])

    def test_un_index_modifie_ou_signe_par_une_autre_cle_est_refuse(self):
        octets = self.fichiers["/index.json"]
        self.fichiers["/index.json"] = octets.replace(b'"essai"', b'"truque"')
        with self.assertRaisesRegex(R.RegistreErreur, "signature"):
            self.cycle.registre_officiel()
        self.publier(priv=self.intrus_priv)
        with self.assertRaisesRegex(R.RegistreErreur, "signature"):
            self.cycle.registre_officiel()

    def test_un_index_perime_date_du_futur_ou_de_format_inconnu_est_refuse(self):
        self.expire = time.time() - 10
        self.publier()
        with self.assertRaisesRegex(R.RegistreErreur, "expiré"):
            self.cycle.registre_officiel()
        self.expire, self.emis = time.time() + 86400, time.time() + 3 * 86400
        self.publier()
        with self.assertRaisesRegex(R.RegistreErreur, "futur"):
            self.cycle.registre_officiel()
        self.emis = time.time() - 60
        self.publier(format=2)
        with self.assertRaisesRegex(R.RegistreErreur, "format"):
            self.cycle.registre_officiel()

    def test_une_signature_mal_formee_ne_passe_pas(self):
        octets = self.fichiers["/index.json"]
        for mauvaise in (b"", b"pas du base64 !!", base64.b64encode(b"x" * 10), base64.b64encode(b"x" * 64)):
            self.assertEqual(R.signature_valide(octets, mauvaise, {"principale": self.racine_pub}), "")
        self.assertEqual(R.signature_valide(octets, self.fichiers["/index.json.sig"], {"principale": self.racine_pub}), "principale")
        self.assertEqual(R.signature_valide(octets, self.fichiers["/index.json.sig"], {"autre": self.intrus_pub}), "")

    def test_une_version_revoquee_ne_s_installe_pas_et_une_installee_est_signalee(self):
        e = self.cycle.telecharger_officiel("sentinelle")
        self.cycle.installer(e["jeton"], e["empreinte_permissions"])
        self.assertEqual(self.cycle.registre_officiel()["installes_revoques"], [])
        self.revocations = [{"id": "sentinelle", "versions": "<1.0", "raison": "lit des fichiers hors de son espace"}]
        self.publier()
        r = self.cycle.registre_officiel()
        self.assertEqual([(x["id"], x["version"]) for x in r["installes_revoques"]], [("sentinelle", "0.1.2")])
        self.assertIn("hors de son espace", r["installes_revoques"][0]["raison"])
        self.assertTrue({x["id"]: x for x in r["modules"]}["sentinelle"]["revoque"])
        with self.assertRaisesRegex(C.CycleErreur, "révoqué"):
            self.cycle.telecharger_officiel("sentinelle")

    def test_une_revocation_de_toutes_les_versions_et_une_plage_ne_touchent_que_ce_qu_elles_visent(self):
        rev = R.lire_revocations({"revocations": [{"id": "aa", "versions": "<2.0", "raison": "x"}, {"id": "bb", "raison": "tout"}, {"id": "Mal Ecrit", "raison": "x"}, {"id": "cc", "versions": ">=", "raison": "x"}]})
        self.assertEqual([r["id"] for r in rev], ["aa", "bb"])
        self.assertTrue(R.revocation_de("aa", "1.9", rev))
        self.assertFalse(R.revocation_de("aa", "2.0", rev))
        self.assertTrue(R.revocation_de("bb", "99.0", rev))
        self.assertFalse(R.revocation_de("zz", "1.0", rev))

    def test_les_editeurs_verifies_servent_aussi_a_une_archive_deposee_a_la_main(self):
        self.cycle.registre_officiel()                                                    # l'index vérifié reste en cache
        e = self.cycle.examiner(self.archives["chezacme"]["octets"])
        self.assertEqual((e["niveau"], e["autorise"]), ("verifie", True))
        autre = self.nouveau_cycle()
        autre.cache_officiel.unlink()                                                      # sans cache : l'éditeur est inconnu
        self.assertEqual(autre.examiner(self.archives["chezacme"]["octets"])["niveau"], "")

    def test_une_cle_posee_a_la_main_ne_se_fait_pas_passer_pour_l_officiel(self):
        (self.base / "cles" / "cassandra-faux.pub").write_text(self.intrus_pub, encoding="utf-8")        # un nom réservé : ignoré
        (self.base / "cles" / "ed_faux.pub").write_text(self.intrus_pub, encoding="utf-8")
        e = self.cycle.examiner(self.archives["louche"]["octets"])
        self.assertEqual((e["niveau"], e["signe"]), ("", False))
        (self.base / "cles" / "mon_equipe.pub").write_text(self.intrus_pub, encoding="utf-8")            # un nom ordinaire : une clé de l'administrateur
        e = self.cycle.examiner(self.archives["louche"]["octets"])
        self.assertEqual((e["niveau"], e["editeur"], e["autorise"]), ("local", "mon_equipe", True))

    def test_la_racine_embarquee_n_est_pas_celle_de_l_essai(self):
        autre = self.nouveau_cycle(racine=dict(R.CLES_RACINE))                            # la vraie racine de l'application : elle ne reconnaît pas la signature de l'essai
        with self.assertRaisesRegex(R.RegistreErreur, "signature"):
            autre.registre_officiel()

    def test_un_hote_qui_n_est_pas_celui_du_registre_est_ecarte_de_l_index(self):
        b = self.index()
        b["modules"].append({"id": "ailleurs", "nom": "Ailleurs", "version": "1.0.0", "description": "x", "url": "http://exemple.invalid/x.cmod", "sha256": "1" * 64, "editeur": "cassandra"})
        octets = (json.dumps(b, sort_keys=True) + "\n").encode()
        self.fichiers["/index.json"], self.fichiers["/index.json.sig"] = octets, R.signer(octets, self.racine_priv)
        self.assertNotIn("ailleurs", self.modules())


class Application(unittest.TestCase):
    def test_la_racine_embarquee_a_deux_cles_valides_et_une_adresse_https(self):
        self.assertEqual(sorted(R.CLES_RACINE), ["principale", "secours"])
        for nom, pem in R.CLES_RACINE.items():
            with tempfile.TemporaryDirectory() as t:
                (Path(t) / "k").write_text(pem, encoding="utf-8")
                self.assertEqual(subprocess.run(["openssl", "pkey", "-pubin", "-in", str(Path(t) / "k"), "-noout"], capture_output=True).returncode, 0, nom)
        self.assertNotEqual(R.CLES_RACINE["principale"], R.CLES_RACINE["secours"])
        self.assertTrue(R.URL_OFFICIELLE.startswith("https://"))

    def test_les_niveaux_se_lisent_dans_le_nom_de_la_cle(self):
        self.assertEqual([R.niveau_de(x) for x in ("cassandra-principale", "ed_acme", "mon_equipe", "")], ["officiel", "verifie", "local", ""])


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : le banc du registre officiel.
# EC : néant.
# LIEN : noyau/CN_registre_officiel.py, noyau/CN_cycle.py (registre_officiel, telecharger_officiel), cassandra-registre (l'outil de publication).
