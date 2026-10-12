"""Bancs du module webauthn : un authentificateur logiciel (ES256) signe de vraies assertions, dans un vrai noyau avec sa passerelle."""
import hashlib
import http.client
import json
import secrets
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

import main as moteur                      # noqa: E402
from noyau.bus import TOUT                 # noqa: E402
from noyau.passerelle import Passerelle    # noqa: E402

from cryptography.hazmat.primitives import hashes                      # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec               # noqa: E402

MDP = "Abcdefgh1!"
RP = "cassandra.exemple.fr"
ORIGINE = "https://" + RP


def b64u(b):
    import base64
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def cbor_enc(v):
    def tete(t, n):
        if n < 24:
            return bytes([(t << 5) | n])
        if n < 256:
            return bytes([(t << 5) | 24, n])
        if n < 65536:
            return bytes([(t << 5) | 25]) + n.to_bytes(2, "big")
        return bytes([(t << 5) | 26]) + n.to_bytes(4, "big")
    if isinstance(v, bool):
        raise ValueError
    if isinstance(v, int):
        return tete(0, v) if v >= 0 else tete(1, -1 - v)
    if isinstance(v, bytes):
        return tete(2, len(v)) + v
    if isinstance(v, str):
        b = v.encode()
        return tete(3, len(b)) + b
    if isinstance(v, dict):
        return tete(5, len(v)) + b"".join(cbor_enc(k) + cbor_enc(x) for k, x in v.items())
    if isinstance(v, list):
        return tete(4, len(v)) + b"".join(cbor_enc(x) for x in v)
    raise ValueError(type(v))


class Authentificateur:
    """Une clé de sécurité logicielle : ES256, compteur, vérification de l'utilisateur au choix."""

    def __init__(self, rp=RP, uv=True):
        self.cle = ec.generate_private_key(ec.SECP256R1())
        self.cred = secrets.token_bytes(16)
        self.compteur = 0
        self.rp, self.uv = rp, uv

    def cose(self, alg=-7):
        n = self.cle.public_key().public_numbers()
        return {1: 2, 3: alg, -1: 1, -2: n.x.to_bytes(32, "big"), -3: n.y.to_bytes(32, "big")}

    def cred_id(self):
        return b64u(self.cred)

    def attestation(self, defi, origine=ORIGINE, type_="webauthn.create", up=True, alg=-7, rp=None):
        flags = (0x01 if up else 0) | (0x04 if self.uv else 0) | 0x40
        ad = hashlib.sha256((rp or self.rp).encode()).digest() + bytes([flags]) + self.compteur.to_bytes(4, "big") + bytes(16) + len(self.cred).to_bytes(2, "big") + self.cred + cbor_enc(self.cose(alg))
        cd = json.dumps({"type": type_, "challenge": defi, "origin": origine}).encode()
        return b64u(cd), b64u(cbor_enc({"fmt": "none", "attStmt": {}, "authData": ad}))

    def assertion(self, defi, origine=ORIGINE, type_="webauthn.get", up=True, uv=None, compteur=None, rp=None, corrompre=False):
        self.compteur = self.compteur + 1 if compteur is None else compteur
        uv = self.uv if uv is None else uv
        flags = (0x01 if up else 0) | (0x04 if uv else 0)
        ad = hashlib.sha256((rp or self.rp).encode()).digest() + bytes([flags]) + self.compteur.to_bytes(4, "big")
        cd = json.dumps({"type": type_, "challenge": defi, "origin": origine}).encode()
        sig = self.cle.sign(ad + hashlib.sha256(cd).digest(), ec.ECDSA(hashes.SHA256()))
        if corrompre:
            sig = sig[:-1] + bytes([sig[-1] ^ 1])
        return {"cred_id": self.cred_id(), "client_data": b64u(cd), "auth_data": b64u(ad), "signature": b64u(sig), "defi": defi}


class Monde(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        mods = base / "modules"
        for m in ("droits", "comptes", "webauthn"):
            shutil.copytree(RACINE / "modules" / m, mods / m)
        self.n = moteur.Noyau(base / "d", mods, {}, gerer_modules=True, exiger_compte=True)
        self.n.brancher()
        for m in ("comptes", "webauthn"):
            self.assertTrue(self.n.activer(m)["ok"], m)
        self.n.identite.unix = lambda nom: "/bin/bash"
        self.n.identite.fastpanel = lambda: False
        self.n.reglages.poser("webauthn.rp_id", RP)
        for c in ("chef@x.fr", "bea@x.fr"):
            self.n.executeur.executer("comptes.creer", "humain", {"compte": c, "mot_de_passe": MDP}, compte="operateur")
        self.g = Passerelle(self.n, "127.0.0.1", 0)
        self.g.demarrer()
        self.addCleanup(self.g.arreter)
        self.cle = Authentificateur()

    def ex(self, cap, compte="bea@x.fr", acteur="humain", **args):
        return self.n.executeur.executer("webauthn." + cap, acteur, args, compte=compte)

    def req(self, chemin, corps, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        h = {"Content-Type": "application/json", "X-Cassandra": "1"}
        if cookie:
            h["Cookie"] = cookie
        c.request("POST", chemin, body=json.dumps(corps).encode(), headers=h)
        r = c.getresponse()
        txt = r.read().decode()
        ck = r.getheader("Set-Cookie")
        c.close()
        return r.status, json.loads(txt), ck

    def enregistrer(self, cle=None, compte="bea@x.fr", libelle="Ma clé", **kw):
        cle = cle or self.cle
        defi = self.ex("defi_creer", compte=compte)["resultat"]["defi"]
        cd, att = cle.attestation(defi, **kw)
        return self.ex("enregistrer", compte=compte, defi=defi, client_data=cd, attestation=att, libelle=libelle)

    def connexion(self, compte="bea@x.fr", preuve=None):
        corps = {"compte": compte, "mot_de_passe": MDP}
        if preuve:
            corps["preuve"] = preuve
        return self.req("/api/connexion", corps)

    def preuve(self, cle=None, **kw):
        cle = cle or self.cle
        st, c, _ = self.connexion()
        self.assertEqual((st, c.get("second_facteur")), (401, True), c)
        a = cle.assertion(c["invite"]["defi"], **kw)
        return a


class Enregistrement(Monde):
    def test_enregistrer_une_cle_est_prouve_et_ne_montre_jamais_la_cle_publique(self):
        r = self.enregistrer()
        self.assertEqual(r["statut"], "faite", r)
        e = self.ex("etat")["resultat"]
        self.assertEqual([c["id"] for c in e["cles"]], [self.cle.cred_id()[-8:]])
        self.assertNotIn("cose", json.dumps(e))
        self.assertTrue(e["disponible"] and not e["exigee"])

    def test_le_retour_d_un_enregistrement_retire_la_cle(self):
        r = self.enregistrer()
        self.n.catalogue.get("webauthn.enregistrer").defaire(self.n.executeur.contextes["webauthn"], r["resultat"])
        self.assertEqual(self.ex("etat")["resultat"]["cles"], [])

    def test_les_refus(self):
        cas = {
            "origine": dict(origine="https://pirate.exemple.org"),
            "http": dict(origine="http://" + RP),
            "type": dict(type_="webauthn.get"),
            "non_presentee": dict(up=False),
            "autre_domaine": dict(rp="autre.exemple.fr"),
            "algorithme": dict(alg=-8),
        }
        for nom, kw in cas.items():
            r = self.enregistrer(cle=Authentificateur(), **kw)
            self.assertEqual(r["statut"], "echec", nom)
        self.assertEqual(self.ex("etat")["resultat"]["cles"], [])

    def test_un_defi_ne_sert_qu_une_fois_et_le_compte_doit_etre_le_meme(self):
        defi = self.ex("defi_creer")["resultat"]["defi"]
        cd, att = self.cle.attestation(defi)
        self.assertEqual(self.ex("enregistrer", compte="chef@x.fr", defi=defi, client_data=cd, attestation=att)["statut"], "echec")     # le défi de Bea, présenté par Chef
        defi = self.ex("defi_creer")["resultat"]["defi"]
        cd, att = self.cle.attestation(defi)
        self.assertEqual(self.ex("enregistrer", defi=defi, client_data=cd, attestation=att)["statut"], "faite")
        self.assertEqual(self.ex("enregistrer", defi=defi, client_data=cd, attestation=att)["statut"], "echec")                          # rejeu

    def test_un_defi_perime_est_refuse(self):
        defi = self.ex("defi_creer")["resultat"]["defi"]
        g = self.n.catalogue.get("webauthn.etat").faire.__globals__
        for k, v in list(g["DEFIS"].items()):
            g["DEFIS"][k] = (v[0], time.time() - 1, v[2])
        cd, att = self.cle.attestation(defi)
        self.assertEqual(self.ex("enregistrer", defi=defi, client_data=cd, attestation=att)["statut"], "echec")

    def test_la_meme_cle_ne_s_enregistre_pas_deux_fois(self):
        self.assertEqual(self.enregistrer()["statut"], "faite")
        self.assertEqual(self.enregistrer()["statut"], "echec")

    def test_sans_domaine_regle_on_le_dit(self):
        self.n.reglages.retirer("webauthn.rp_id")
        r = self.ex("defi_creer")
        self.assertEqual(r["statut"], "echec")
        self.assertIn("rp_id", json.dumps(r))

    def test_sans_compte_pas_de_cle(self):
        self.assertEqual(self.n.executeur.executer("webauthn.etat", "humain", {}, compte="operateur")["statut"], "echec")


class SecondFacteur(Monde):
    def setUp(self):
        super().setUp()
        self.enregistrer()

    def exiger(self):
        r = self.ex("exiger", exiger=True)
        self.assertEqual(r["statut"], "faite", r)
        return r["resultat"]["secours"]

    def test_enregistrer_n_exige_rien_la_connexion_reste_au_mot_de_passe(self):
        st, c, ck = self.connexion()
        self.assertEqual(st, 200)
        self.assertIn("cassandra_session", ck)

    def test_exiger_sans_cle_est_refuse_et_rend_huit_codes_sinon(self):
        self.assertEqual(self.ex("exiger", compte="chef@x.fr", exiger=True)["statut"], "echec")
        codes = self.exiger()
        self.assertEqual(len(codes), 8)
        self.assertEqual(self.ex("etat")["resultat"]["secours_restants"], 8)
        journal = json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str)
        for code in codes:
            self.assertNotIn(code, journal)

    def test_exigee_la_connexion_demande_une_signature_puis_ouvre(self):
        self.exiger()
        st, c, ck = self.connexion()
        self.assertEqual((st, c["second_facteur"], ck), (401, True, None))
        self.assertEqual(set(c["invite"]), {"defi", "ids", "rp_id", "secours"})
        self.assertEqual(c["invite"]["ids"], [self.cle.cred_id()])
        st, c, ck = self.connexion(preuve=self.cle.assertion(c["invite"]["defi"]))
        self.assertEqual(st, 200, c)
        self.assertIn("cassandra_session", ck)

    def test_les_signatures_fausses_sont_refusees(self):
        self.exiger()
        for nom, kw in {"corrompue": dict(corrompre=True), "origine": dict(origine="https://pirate.exemple.org"), "type": dict(type_="webauthn.create"),
                        "non_presentee": dict(up=False), "autre_domaine": dict(rp="autre.exemple.fr")}.items():
            a = self.preuve(**kw)
            st, c, ck = self.connexion(preuve=a)
            self.assertEqual((st, ck), (401, None), nom)
            self.assertNotIn("jeton", c, nom)

    def test_un_defi_rejoue_est_refuse(self):
        self.exiger()
        st, c, _ = self.connexion()
        a = self.cle.assertion(c["invite"]["defi"])
        self.assertEqual(self.connexion(preuve=a)[0], 200)
        self.cle.compteur += 1
        a2 = self.cle.assertion(c["invite"]["defi"])
        self.assertEqual(self.connexion(preuve=a2)[0], 401)

    def test_un_compteur_qui_recule_signale_une_cle_clonee(self):
        self.exiger()
        st, c, _ = self.connexion()
        self.assertEqual(self.connexion(preuve=self.cle.assertion(c["invite"]["defi"], compteur=10))[0], 200)
        st, c, _ = self.connexion()
        self.assertEqual(self.connexion(preuve=self.cle.assertion(c["invite"]["defi"], compteur=5))[0], 401)

    def test_une_cle_d_un_autre_compte_ne_passe_pas(self):
        self.exiger()
        autre = Authentificateur()
        self.enregistrer(cle=autre, compte="chef@x.fr")
        a = self.preuve(cle=autre)
        self.assertEqual(self.connexion(preuve=a)[0], 401)

    def test_un_code_de_secours_ne_sert_qu_une_fois(self):
        codes = self.exiger()
        self.assertEqual(self.connexion(preuve={"secours": codes[0]})[0], 200)
        self.assertEqual(self.connexion(preuve={"secours": codes[0]})[0], 401)
        self.assertEqual(self.connexion(preuve={"secours": "faux-code-xxxx"})[0], 401)
        self.assertEqual(self.ex("etat")["resultat"]["secours_restants"], 7)

    def test_regenerer_invalide_les_anciens_codes_et_se_defait(self):
        anciens = self.exiger()
        r = self.ex("secours_regenerer")
        self.assertEqual(r["statut"], "faite", r)
        self.assertEqual(self.connexion(preuve={"secours": anciens[0]})[0], 401)
        self.n.catalogue.get("webauthn.secours_regenerer").defaire(self.n.executeur.contextes["webauthn"], r["resultat"])
        self.assertEqual(self.connexion(preuve={"secours": anciens[1]})[0], 200)

    def test_on_ne_retire_pas_la_derniere_cle_exigee(self):
        self.exiger()
        court = self.cle.cred_id()[-8:]
        r = self.ex("supprimer", court=court)
        self.assertEqual(r["statut"], "echec")
        self.assertIn("dernière", json.dumps(r, ensure_ascii=False))
        self.assertEqual(self.ex("exiger", exiger=False)["statut"], "faite")
        r = self.ex("supprimer", court=court)
        self.assertEqual(r["statut"], "faite", r)
        self.n.catalogue.get("webauthn.supprimer").defaire(self.n.executeur.contextes["webauthn"], r["resultat"])
        self.assertEqual(len(self.ex("etat")["resultat"]["cles"]), 1)

    def test_le_retour_d_exiger_remet_l_etat_et_les_codes_d_avant(self):
        anciens = self.exiger()
        self.ex("secours_regenerer")
        r = self.ex("exiger", exiger=False)
        self.n.catalogue.get("webauthn.exiger").defaire(self.n.executeur.contextes["webauthn"], r["resultat"])
        self.assertTrue(self.ex("etat")["resultat"]["exigee"])

    def test_un_second_facteur_defaillant_refuse_l_entree(self):
        self.exiger()
        facteur = self.n.identite.seconds_facteurs["webauthn"]
        facteur.exige = lambda compte: 1 / 0
        st, c, ck = self.connexion()
        self.assertEqual((st, ck), (401, None))
        self.assertIn("indisponible", json.dumps(c, ensure_ascii=False))

    def test_debrancher_le_module_retire_le_facteur(self):
        self.exiger()
        self.n.desactiver("webauthn")
        self.assertEqual(self.connexion()[0], 200)

    def test_un_compte_sans_cle_n_est_pas_concerne(self):
        self.exiger()
        self.assertEqual(self.connexion(compte="chef@x.fr")[0], 200)


class Passkey(Monde):
    def setUp(self):
        super().setUp()
        self.enregistrer()

    def passkey(self, **kw):
        st, c, _ = self.req("/api/public/webauthn.passkey_defi", {})
        self.assertEqual(st, 200, c)
        defi = c["resultat"]["defi"]
        a = self.cle.assertion(defi, **kw)
        return self.req("/api/public/webauthn.passkey_ouvrir", {"args": a})

    def test_entrer_sans_mot_de_passe_avec_verification_de_l_utilisateur(self):
        st, c, ck = self.passkey()
        self.assertEqual(st, 200, c)
        self.assertEqual(c["compte"], "bea@x.fr")
        self.assertIn("cassandra_session", ck)
        v = self.n.identite.valider(c["jeton"])
        self.assertTrue(v["ok"] and v["compte"] == "bea@x.fr")

    def test_sans_pin_ni_empreinte_la_cle_seule_ne_suffit_pas(self):
        st, c, ck = self.passkey(uv=False)
        self.assertNotEqual(st, 200)
        self.assertIsNone(ck)

    def test_signature_fausse_cle_inconnue_et_rejeu(self):
        self.assertNotEqual(self.passkey(corrompre=True)[0], 200)
        inconnue = Authentificateur()
        st, c, _ = self.req("/api/public/webauthn.passkey_defi", {})
        a = inconnue.assertion(c["resultat"]["defi"])
        self.assertNotEqual(self.req("/api/public/webauthn.passkey_ouvrir", {"args": a})[0], 200)
        st, c, _ = self.req("/api/public/webauthn.passkey_defi", {})
        a = self.cle.assertion(c["resultat"]["defi"])
        self.assertEqual(self.req("/api/public/webauthn.passkey_ouvrir", {"args": a})[0], 200)
        self.cle.compteur += 1
        a2 = self.cle.assertion(c["resultat"]["defi"])
        self.assertNotEqual(self.req("/api/public/webauthn.passkey_ouvrir", {"args": a2})[0], 200)

    def test_un_defi_de_connexion_classique_ne_sert_pas_a_la_passkey(self):
        self.ex("exiger", exiger=True)
        st, c, _ = self.connexion()
        a = self.cle.assertion(c["invite"]["defi"])
        self.assertNotEqual(self.req("/api/public/webauthn.passkey_ouvrir", {"args": a})[0], 200)

    def test_les_echecs_comptent_contre_le_compte(self):
        for _ in range(12):
            self.passkey(corrompre=True)
        st, c, _ = self.passkey()
        self.assertNotEqual(st, 200)
        self.assertIn("essais", json.dumps(c, ensure_ascii=False).lower())

    def test_le_jeton_n_apparait_pas_au_journal(self):
        st, c, _ = self.passkey()
        journal = json.dumps(self.n.bus.recents(portee=TOUT, limite=900), default=str)
        self.assertNotIn(c["jeton"], journal)


if __name__ == "__main__":
    unittest.main()
