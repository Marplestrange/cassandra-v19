# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs de l'authentification
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #509fb8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs de l'authentification : cookie Secure et HSTS, coût de scrypt et réécriture des empreintes, inactivité des sessions, ressaisie du second facteur pour un geste sensible, second facteur obligatoire pour les administrateurs (avec période
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=509fb8 ▼▼▼
"""Bancs de l'authentification : cookie Secure et HSTS, coût de scrypt et réécriture des empreintes, inactivité des sessions, ressaisie du second facteur
pour un geste sensible, second facteur obligatoire pour les administrateurs (avec période de grâce)."""
import hashlib
import http.client
import json
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import CN_main as moteur                                   # noqa: E402
from noyau import CN_identite as idt                       # noqa: E402
from noyau.CN_passerelle import Passerelle, cookie_secure_effectif   # noqa: E402
from tests import SCRYPT_PRODUCTION, parametres_de_production      # noqa: E402

MDP = "Abcdefgh1!"


class Secure(unittest.TestCase):
    def test_le_defaut_est_sur(self):
        f = lambda demande, hote, proxy, env="": cookie_secure_effectif(demande, hote, proxy, env=env)
        self.assertFalse(f(None, "127.0.0.1", False))                    # boucle locale, sans proxy : pas de TLS à protéger
        self.assertFalse(f(False, "::1", False))
        self.assertTrue(f(None, "0.0.0.0", False))                       # écoute hors boucle locale
        self.assertTrue(f(False, "127.0.0.1", True))                     # derrière un proxy de confiance (False = pas de choix, le défaut sûr)
        self.assertTrue(f(True, "127.0.0.1", False))                     # forcé
        self.assertFalse(f("non", "0.0.0.0", True))                      # coupé explicitement
        self.assertFalse(f(None, "0.0.0.0", True, env="0"))              # coupé par l'environnement
        self.assertTrue(f(None, "127.0.0.1", False, env="oui"))          # forcé par l'environnement

    def test_la_passerelle_applique_le_defaut_et_pose_hsts_seulement_en_https_par_le_proxy(self):
        class N:
            pass
        self.assertFalse(Passerelle(N(), "127.0.0.1", 0).cookie_secure)
        self.assertTrue(Passerelle(N(), "0.0.0.0", 0).cookie_secure)
        p = Passerelle(N(), "127.0.0.1", 0, proxy_de_confiance=True)
        self.assertTrue(p.cookie_secure)

        class H:
            def __init__(self, proto):
                self.headers = {"X-Forwarded-Proto": proto} if proto else {}
                self.pose = {}

            def send_header(self, k, v):
                self.pose[k] = v
        for proto, attendu in (("https", True), ("http", False), ("", False)):
            h = H(proto)
            p._hsts(h)
            self.assertEqual("Strict-Transport-Security" in h.pose, attendu, proto)
        h = H("https")
        Passerelle(N(), "0.0.0.0", 0)._hsts(h)                            # sans proxy de confiance, l'en-tête X-Forwarded-Proto ne se croit pas
        self.assertEqual(h.pose, {})


class Scrypt(unittest.TestCase):
    def test_le_fichier_de_production_porte_le_cout_d_owasp_et_le_banc_ne_le_cache_pas(self):
        self.assertEqual(SCRYPT_PRODUCTION, dict(n=2 ** 17, r=8, p=1, dklen=32))      # relevé avant que tests/__init__ ne le remplace pour le banc
        self.assertLess(idt._SCRYPT["n"], SCRYPT_PRODUCTION["n"])                      # le banc court au coût réduit...
        with parametres_de_production():
            self.assertEqual(idt._SCRYPT, SCRYPT_PRODUCTION)                         # ...et rétablit le vrai le temps d'un test
        self.assertLess(idt._SCRYPT["n"], SCRYPT_PRODUCTION["n"])

    @parametres_de_production()
    def test_les_parametres_vivent_dans_l_empreinte_et_le_cout_est_celui_d_owasp(self):
        t = time.time()
        h = idt.hacher("Abcdefgh1!")
        duree = time.time() - t
        self.assertTrue(h.startswith("scrypt$n=131072,r=8,p=1$"), h)
        self.assertTrue(idt.hash_ok("Abcdefgh1!", h))
        self.assertFalse(idt.hash_ok("autre", h))
        self.assertTrue(idt.hash_a_jour(h))
        print("\n  scrypt n=2**17 : %.2f s par hachage, mémoire ~%d Mo (maxmem %d Mo)" % (duree, 128 * 2 ** 17 * 8 // 2 ** 20, idt.MAXMEM // 2 ** 20))
        self.assertLess(duree, 5)

    @parametres_de_production()
    def test_une_ancienne_empreinte_reste_verifiable_et_se_dit_perimee(self):
        sel = bytes(range(16))
        ancien = "scrypt$%s$%s" % (sel.hex(), hashlib.scrypt(b"Abcdefgh1!", salt=sel, n=2 ** 14, r=8, p=1, dklen=32).hex())
        self.assertTrue(idt.hash_ok("Abcdefgh1!", ancien))
        self.assertFalse(idt.hash_ok("autre", ancien))
        self.assertFalse(idt.hash_a_jour(ancien))

    def test_des_parametres_hors_bornes_ou_illisibles_sont_refuses(self):
        for h in ("scrypt$n=1073741824,r=8,p=1$00$00", "scrypt$n=131073,r=8,p=1$00$00", "scrypt$n=x,r=8,p=1$00$00", "scrypt$n=16384$00$00", "bcrypt$a$b", "", "scrypt$00"):
            self.assertFalse(idt.hash_ok("x", h), h)

    def test_le_secret_tire_au_hasard_garde_le_cout_leger(self):
        i = type("I", (), {"hacher": idt.Identite.hacher, "secret_ok": idt.Identite.secret_ok})()
        self.assertTrue(i.hacher("code").startswith("scrypt$n=16384,r=8,p=1$"))
        self.assertTrue(i.secret_ok("code", i.hacher("code")))


class FauxFacteur:
    """Un second facteur de banc : la preuve est {"code": "ok"} ; exige() dit pour quels comptes il est posé."""
    def __init__(self, comptes=()):
        self.comptes = set(comptes)

    def exige(self, compte):
        return compte in self.comptes

    def invite(self, compte):
        return {"defi": "d"}

    def verifier(self, compte, preuve, ip=""):
        return {"ok": True} if preuve.get("code") == "ok" else {"ok": False, "error": "refusé"}


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("droits", "comptes"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        self.assertTrue(self.n.activer("comptes")["ok"])
        self.idt = self.n.identite
        self.idt.unix = lambda nom: "/bin/bash"
        self.idt.fastpanel = lambda: False
        for c in ("chef@x.fr", "bea@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP}, compte="operateur")
        self.n.droits.regler_admin("chef@x.fr", True)
        self.facteur = FauxFacteur()
        self.idt.enregistrer_facteur("faux", self.facteur)
        self.g = Passerelle(self.n, "127.0.0.1", 0)
        self.g.demarrer()
        self.addCleanup(self.g.arreter)

    def req(self, methode, chemin, corps=None, jeton=""):
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        h = {"Content-Type": "application/json"}
        if jeton:
            h["Authorization"] = "Bearer " + jeton
        c.request(methode, chemin, body=json.dumps(corps).encode() if corps is not None else None, headers=h)
        r = c.getresponse()
        txt = r.read().decode()
        c.close()
        return r.status, json.loads(txt)

    def entrer(self, compte, preuve=None):
        corps = {"compte": compte, "mot_de_passe": MDP}
        if preuve:
            corps["preuve"] = preuve
        return self.req("POST", "/api/connexion", corps)

    def vieillir(self, jeton, secondes, champs=("cree", "derniere")):
        sid = hashlib.sha256(jeton.encode()).hexdigest()
        for ch in champs:
            self.n.base.ecrire("UPDATE sessions SET %s=%s-? WHERE id=?" % (ch, ch), (secondes, sid))


class Reecriture(Monde):
    @parametres_de_production()
    def test_une_ancienne_empreinte_est_reecrite_a_la_prochaine_connexion_reussie(self):
        sel = bytes(range(16))
        ancien = "scrypt$%s$%s" % (sel.hex(), hashlib.scrypt(MDP.encode(), salt=sel, n=2 ** 14, r=8, p=1, dklen=32).hex())
        self.idt.poser_hash("bea@x.fr", ancien)
        st, r = self.entrer("bea@x.fr")
        self.assertEqual(st, 200, r)
        nouveau = self.idt.hash_de("bea@x.fr")
        self.assertNotEqual(nouveau, ancien)
        self.assertTrue(nouveau.startswith("scrypt$n=131072,r=8,p=1$"))
        self.assertTrue(idt.hash_ok(MDP, nouveau))
        self.idt.poser_hash("bea@x.fr", ancien)
        self.assertEqual(self.entrer("bea@x.fr")[0], 200)                      # et une empreinte à jour n'est pas retouchée
        a_jour = self.idt.hash_de("bea@x.fr")
        self.assertEqual(self.entrer("bea@x.fr")[0], 200)
        self.assertEqual(self.idt.hash_de("bea@x.fr"), a_jour)

    @parametres_de_production()
    def test_un_mauvais_mot_de_passe_ne_reecrit_rien(self):
        sel = bytes(range(16))
        ancien = "scrypt$%s$%s" % (sel.hex(), hashlib.scrypt(MDP.encode(), salt=sel, n=2 ** 14, r=8, p=1, dklen=32).hex())
        self.idt.poser_hash("bea@x.fr", ancien)
        self.assertEqual(self.req("POST", "/api/connexion", {"compte": "bea@x.fr", "mot_de_passe": "Mauvais1!"})[0], 401)
        self.assertEqual(self.idt.hash_de("bea@x.fr"), ancien)


class Inactivite(Monde):
    def test_une_session_inactive_se_ferme_plus_vite_pour_un_administrateur(self):
        _, a = self.entrer("chef@x.fr")
        _, u = self.entrer("bea@x.fr")
        self.assertEqual(self.req("GET", "/api/moi", jeton=a["jeton"])[0], 200)
        self.vieillir(a["jeton"], 3 * 3600, ("derniere",))                    # 3 h sans servir : plus de 2 h (admin), moins de 8 h (utilisateur)
        self.vieillir(u["jeton"], 3 * 3600, ("derniere",))
        self.assertEqual(self.req("GET", "/api/moi", jeton=a["jeton"])[0], 401)
        self.assertEqual(self.req("GET", "/api/moi", jeton=u["jeton"])[0], 200)
        self.vieillir(u["jeton"], 9 * 3600, ("derniere",))
        self.assertEqual(self.req("GET", "/api/moi", jeton=u["jeton"])[0], 401)

    def test_le_delai_est_reglable_et_zero_le_coupe(self):
        _, a = self.entrer("chef@x.fr")
        self.vieillir(a["jeton"], 3 * 3600, ("derniere",))
        self.idt.securite["inactivite_admin_heures"] = 4
        self.assertEqual(self.req("GET", "/api/moi", jeton=a["jeton"])[0], 200)        # 3 h < 4 h : la session vit encore (et son horloge repart)
        self.vieillir(a["jeton"], 30 * 3600, ("derniere",))
        self.idt.securite["inactivite_admin_heures"] = 0
        self.assertEqual(self.req("GET", "/api/moi", jeton=a["jeton"])[0], 200)        # 0 : pas de délai d'inactivité (reste la durée maximale)

    def test_une_session_en_service_n_expire_pas(self):
        _, a = self.entrer("chef@x.fr")
        self.vieillir(a["jeton"], 90 * 60, ("derniere",))
        self.assertEqual(self.req("GET", "/api/moi", jeton=a["jeton"])[0], 200)


class Reverification(Monde):
    GESTE = "/api/agir/comptes.creer"                                         # exige le droit « comptes.gerer », déclaré sensible

    def corps(self):
        return {"args": {"compte": "neuf@x.fr", "mot_de_passe": MDP}, "essai": True}

    def test_le_geste_sensible_d_une_vieille_session_d_administrateur_demande_le_second_facteur(self):
        self.facteur.comptes.add("chef@x.fr")
        _, a = self.entrer("chef@x.fr", {"code": "ok"})
        self.assertEqual(self.req("POST", self.GESTE, self.corps(), a["jeton"])[0], 200)       # fraîche : passe
        self.vieillir(a["jeton"], 2 * 3600, ("cree",))
        st, r = self.req("POST", self.GESTE, self.corps(), a["jeton"])
        self.assertEqual((st, r.get("second_facteur"), r.get("reverification")), (401, True, True), r)
        self.assertEqual(r["methodes"], ["faux"])
        self.assertEqual(self.req("POST", "/api/reverifier", {"preuve": {"code": "non"}}, a["jeton"])[0], 401)
        self.assertEqual(self.req("POST", self.GESTE, self.corps(), a["jeton"])[0], 401)       # une preuve fausse ne lève rien
        self.assertEqual(self.req("POST", "/api/reverifier", {"preuve": {"code": "ok"}}, a["jeton"])[0], 200)
        self.assertEqual(self.req("POST", self.GESTE, self.corps(), a["jeton"])[0], 200)

    def test_les_gestes_ordinaires_et_les_comptes_sans_second_facteur_ne_sont_pas_touches(self):
        _, a = self.entrer("chef@x.fr")                                                         # pas de second facteur posé
        self.vieillir(a["jeton"], 5 * 3600, ("cree", "derniere"))
        self.idt.securite["inactivite_admin_heures"] = 0
        self.assertEqual(self.req("POST", self.GESTE, self.corps(), a["jeton"])[0], 200)
        self.facteur.comptes.add("chef@x.fr")
        self.assertEqual(self.req("GET", "/api/moi", jeton=a["jeton"])[0], 200)                # une lecture ordinaire ne demande rien

    def test_le_delai_se_regle_et_zero_le_coupe(self):
        self.facteur.comptes.add("chef@x.fr")
        _, a = self.entrer("chef@x.fr", {"code": "ok"})
        self.vieillir(a["jeton"], 2 * 3600, ("cree",))
        self.idt.securite["admin_reverif_minutes"] = 0
        self.assertEqual(self.req("POST", self.GESTE, self.corps(), a["jeton"])[0], 200)


class Obligation(Monde):
    def test_activee_par_defaut_l_administrateur_entre_en_grace_et_est_prevenu(self):
        st, r = self.entrer("chef@x.fr")
        self.assertEqual(st, 200, r)
        self.assertEqual(r["avertissement"]["code"], "second_facteur_requis_bientot")
        self.assertEqual(self.entrer("bea@x.fr")[0], 200)                                       # un simple utilisateur n'est pas concerné
        self.idt.securite["admin_second_facteur_obligatoire"] = False                           # et l'administrateur de la machine peut l'éteindre
        self.assertEqual(self.idt.avertissement_connexion("chef@x.fr"), {})

    def test_en_grace_l_administrateur_entre_et_est_prevenu_avec_la_date(self):
        self.idt.securite["admin_second_facteur_obligatoire"] = True
        st, r = self.entrer("chef@x.fr")
        self.assertEqual(st, 200, r)
        self.assertEqual(r["avertissement"]["code"], "second_facteur_requis_bientot")
        self.assertIn("avant le", r["avertissement"]["message"])
        st, r = self.entrer("bea@x.fr")                                                         # un simple utilisateur n'est pas concerné
        self.assertEqual(st, 200)
        self.assertNotIn("avertissement", r)

    def test_la_grace_finie_l_administrateur_sans_second_facteur_est_refuse_avec_un_message_clair(self):
        self.idt.securite["admin_second_facteur_obligatoire"] = True
        self.assertEqual(self.entrer("chef@x.fr")[0], 200)                                      # l'obligation est constatée ici : la grâce court de là
        self.n.base.ecrire("UPDATE identite_etat SET valeur=valeur-? WHERE cle='mfa_admin_depuis'", (8 * 86400,))
        st, r = self.entrer("chef@x.fr")
        self.assertEqual(st, 401, r)
        self.assertIn("période de grâce est terminée", r["erreur"])
        self.assertIn("comptes.admin_second_facteur_obligatoire", r["erreur"])

    def test_un_administrateur_qui_a_pose_son_second_facteur_entre_normalement(self):
        self.idt.securite["admin_second_facteur_obligatoire"] = True
        self.assertEqual(self.entrer("chef@x.fr")[0], 200)
        self.n.base.ecrire("UPDATE identite_etat SET valeur=valeur-? WHERE cle='mfa_admin_depuis'", (30 * 86400,))
        self.facteur.comptes.add("chef@x.fr")
        st, r = self.entrer("chef@x.fr", {"code": "ok"})
        self.assertEqual(st, 200, r)
        self.assertNotIn("avertissement", r)

    def test_on_l_eteint_puis_on_le_rallume_la_grace_repart(self):
        self.idt.securite["admin_second_facteur_obligatoire"] = True
        self.entrer("chef@x.fr")
        self.n.base.ecrire("UPDATE identite_etat SET valeur=valeur-? WHERE cle='mfa_admin_depuis'", (30 * 86400,))
        self.idt.securite["admin_second_facteur_obligatoire"] = False
        self.assertEqual(self.entrer("chef@x.fr")[0], 200)
        self.idt.securite["admin_second_facteur_obligatoire"] = True
        self.assertEqual(self.entrer("chef@x.fr")[0], 200)                                      # nouvelle grâce

    def test_sans_aucun_module_de_second_facteur_on_n_enferme_personne(self):
        self.idt.oublier_facteur("faux")
        self.idt.securite["admin_second_facteur_obligatoire"] = True
        self.assertEqual(self.entrer("chef@x.fr")[0], 200)
        self.n.base.ecrire("UPDATE identite_etat SET valeur=valeur-? WHERE cle='mfa_admin_depuis'", (30 * 86400,))
        self.assertEqual(self.entrer("chef@x.fr")[0], 200)


if __name__ == "__main__":
    unittest.main()
class Etape0(Monde):
    """La sécurité des sessions : origine, cookie, plafond, nouvel appareil, confirmation du mot de passe."""
    def req_cookie(self, chemin, corps, jeton, origine=None, hote=None):
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        h = {"Content-Type": "application/json", "X-Cassandra": "1", "Cookie": "cassandra_session=" + jeton}
        if origine is not None:
            h["Origin"] = origine
        c.request("POST", chemin, body=json.dumps(corps).encode(), headers=h)
        r = c.getresponse()
        txt = r.read().decode()
        c.close()
        return r.status, json.loads(txt)

    def test_une_requete_a_cookie_venue_d_un_autre_site_est_refusee(self):
        jeton = self.entrer("bea@x.fr")[1]["jeton"]
        hote = "127.0.0.1:%d" % self.g.port
        self.assertEqual(self.req_cookie("/api/agir/comptes.moi", {"args": {}}, jeton)[0], 200)                         # sans Origin (curl, un agent) : passe
        self.assertEqual(self.req_cookie("/api/agir/comptes.moi", {"args": {}}, jeton, "http://" + hote)[0], 200)       # le même hôte : passe
        self.assertEqual(self.req_cookie("/api/agir/comptes.moi", {"args": {}}, jeton, "https://mechant.example")[0], 403)
        self.assertEqual(self.req_cookie("/api/agir/comptes.moi", {"args": {}}, jeton, "null")[0], 403)
        st, _ = self.req("POST", "/api/agir/comptes.moi", {"args": {}}, jeton)                                           # un jeton en en-tête n'est pas ambiant : pas concerné
        self.assertEqual(st, 200)

    def test_le_cookie_prend_le_prefixe_host_des_qu_il_est_secure(self):
        class H:
            pass
        sur = Passerelle(self.n, "127.0.0.1", 0, cookie_secure=True)
        self.assertTrue(sur._cookie_session("abc").startswith("__Host-cassandra_session=abc; Path=/;"))
        self.assertIn("; Secure", sur._cookie_session("abc"))
        self.assertNotIn("Domain", sur._cookie_session("abc"))
        self.assertTrue(self.g._cookie_session("abc").startswith("cassandra_session=abc;"))                              # http local : sans préfixe
        h = H()
        h.headers = {"Cookie": "autre=1; __Host-cassandra_session=%s" % ("a" * 64)}
        self.assertEqual(sur._jeton(h), ("a" * 64, True))                                                               # les deux noms se lisent

    def test_au_plus_dix_sessions_par_compte(self):
        ouvertes = [self.idt.ouvrir("bea@x.fr", MDP, "203.0.113.5", "navigateur") for _ in range(12)]
        vivantes = self.idt.sessions("bea@x.fr")
        self.assertEqual(len(vivantes), 10)
        self.assertTrue(self.idt.valider(ouvertes[-1]["jeton"])["ok"])                                                   # la plus récente reste
        self.assertFalse(self.idt.valider(ouvertes[0]["jeton"])["ok"])                                                   # la plus ancienne a cédé la place
        self.assertEqual(len(self.idt.sessions("chef@x.fr")), 0)                                                         # un autre compte n'est pas touché

    def test_un_appareil_jamais_vu_est_reconnu_comme_nouveau(self):
        self.assertEqual(self.idt.appareil_vu("bea@x.fr", "203.0.113.5", "Firefox"), "premier")                          # rien à comparer
        self.assertEqual(self.idt.appareil_vu("bea@x.fr", "203.0.113.5", "Firefox"), "connu")
        self.assertEqual(self.idt.appareil_vu("bea@x.fr", "203.0.113.99", "Firefox"), "connu")                           # même réseau, dernier chiffre différent
        self.assertEqual(self.idt.appareil_vu("bea@x.fr", "198.51.100.7", "Firefox"), "nouveau")
        self.assertEqual(self.idt.appareil_vu("bea@x.fr", "203.0.113.5", "Chrome"), "nouveau")
        self.assertEqual(self.idt.appareil_vu("chef@x.fr", "198.51.100.7", "Firefox"), "premier")                        # un autre compte repart de zéro

    def test_un_geste_sensible_demande_le_mot_de_passe_puis_passe(self):
        jeton = self.entrer("chef@x.fr")[1]["jeton"]
        desactiver = {"args": {"compte": "bea@x.fr"}}
        self.assertEqual(self.req("POST", "/api/agir/comptes.moi", {"args": {}}, jeton)[0], 200)                         # un geste ordinaire ne demande rien
        self.vieillir(jeton, 11 * 60)                                                                                    # la dernière confirmation date de plus de dix minutes
        st, r = self.req("POST", "/api/agir/comptes.desactiver", desactiver, jeton)
        self.assertEqual((st, r.get("confirmation")), (401, True), r)
        self.assertEqual(self.req("POST", "/api/agir/comptes.moi", {"args": {}}, jeton)[0], 200)                         # le reste ne bouge pas
        self.assertEqual(self.req("POST", "/api/confirmer", {"mot_de_passe": "Mauvais1!x"}, jeton)[0], 401)
        self.assertEqual(self.req("POST", "/api/confirmer", {"mot_de_passe": MDP}, jeton)[0], 200)
        st, r = self.req("POST", "/api/agir/comptes.desactiver", desactiver, jeton)
        self.assertEqual((st, r.get("statut")), (200, "faite"), r)
        self.assertEqual(self.req("POST", "/api/confirmer", {"mot_de_passe": MDP}, "")[0], 401)                          # sans session : rien

    def test_la_confirmation_ne_concerne_pas_un_agent_ni_un_reglage_a_zero(self):
        jeton = self.entrer("chef@x.fr")[1]["jeton"]
        self.vieillir(jeton, 11 * 60)
        self.idt.securite["confirmation_minutes"] = 0
        st, r = self.req("POST", "/api/agir/comptes.desactiver", {"args": {"compte": "bea@x.fr"}}, jeton)
        self.assertEqual((st, r.get("statut")), (200, "faite"), r)

# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Secure, Scrypt, FauxFacteur, Monde, Reecriture, Inactivite, Reverification, Obligation
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
