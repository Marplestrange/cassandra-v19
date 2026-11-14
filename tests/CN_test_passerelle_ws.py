# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bancs du flux WebSocket de la passerelle
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tests
# ZONE       : CN
# VERSION CN : 0.1.0  #e04107
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Bancs du flux WebSocket de la passerelle
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e04107 ▼▼▼
"""Bancs du flux WebSocket de la passerelle (GET /ws). Un vrai noyau, une vraie passerelle sur un port libre, un client écrit à la main sur un socket :
la poignée de main (RFC 6455), l'authentification (cookie ou jeton en paramètre), le refus d'un autre site, les pings, la fermeture, la limite par compte."""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from noyau import CN_passerelle as pg                       # noqa: E402
from tests.CN_test_noyau import MDP, monde_passerelle       # noqa: E402

CLE = "dGhlIHNhbXBsZSBub25jZQ=="                             # l'exemple de la RFC 6455 §1.3
ACCEPT = "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def lire_entete(s):
    tampon = b""
    while b"\r\n\r\n" not in tampon:
        b = s.recv(1)
        if not b:
            break
        tampon += b
    tete, _, _ = tampon.partition(b"\r\n\r\n")
    lignes = tete.decode("latin-1").split("\r\n")
    return int(lignes[0].split()[1]), {k.lower(): v for k, _, v in (l.partition(": ") for l in lignes[1:])}


def lire_n(s, n):
    b = b""
    while len(b) < n:
        x = s.recv(n - len(b))
        if not x:
            raise EOFError
        b += x
    return b


def lire_trame(s):
    b0, b1 = lire_n(s, 2)
    n = b1 & 0x7F
    if n == 126:
        n = struct.unpack(">H", lire_n(s, 2))[0]
    return b0 & 0x0F, lire_n(s, n)


def trame_client(op, charge=b"", masquee=True):
    m = b"\x01\x02\x03\x04"
    corps = bytes(c ^ m[i % 4] for i, c in enumerate(charge)) if masquee else charge
    return bytes([0x80 | op, (0x80 if masquee else 0) | len(charge)]) + (m if masquee else b"") + corps


class Flux(unittest.TestCase):
    def setUp(self):
        self.tmp, self.n, self.g = monde_passerelle()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.g.arreter)
        self.socks = []
        self.addCleanup(lambda: [s.close() for s in self.socks])
        import http.client
        c = http.client.HTTPConnection("127.0.0.1", self.g.port, timeout=10)
        c.request("POST", "/api/connexion", body=json.dumps({"compte": "chef@x.fr", "mot_de_passe": MDP}).encode(), headers={"Content-Type": "application/json"})
        r = c.getresponse()
        r.read()
        cookie = r.getheader("Set-Cookie")
        c.close()
        self.jeton = cookie.split(";")[0].split("=", 1)[1]
        self.cookie = cookie.split(";")[0]

    def ouvrir(self, chemin="/ws", entetes=None, cle=CLE, upgrade=True, cookie=True):
        s = socket.create_connection(("127.0.0.1", self.g.port), timeout=10)
        self.socks.append(s)
        h = {"Host": "127.0.0.1:%d" % self.g.port}
        if upgrade:
            h.update({"Upgrade": "websocket", "Connection": "Upgrade", "Sec-WebSocket-Key": cle, "Sec-WebSocket-Version": "13"})
        if cookie:
            h["Cookie"] = self.cookie
        h.update(entetes or {})
        s.sendall(("GET %s HTTP/1.1\r\n%s\r\n\r\n" % (chemin, "\r\n".join("%s: %s" % kv for kv in h.items()))).encode("latin-1"))
        return s

    def test_la_poignee_de_main_donne_la_cle_de_la_rfc_et_une_premiere_trame(self):
        s = self.ouvrir()
        st, e = lire_entete(s)
        self.assertEqual((st, e.get("sec-websocket-accept"), e.get("upgrade").lower()), (101, ACCEPT, "websocket"))
        op, charge = lire_trame(s)
        self.assertEqual(op, 1)
        self.assertIn(json.loads(charge)["type"], ("metrics", "vie"))          # sans le module sensorium : un battement, jamais des zéros inventés

    def test_le_jeton_en_parametre_vaut_le_cookie(self):
        s = self.ouvrir("/ws?token=" + self.jeton, cookie=False)
        self.assertEqual(lire_entete(s)[0], 101)

    def test_sans_session_c_est_401(self):
        self.assertEqual(lire_entete(self.ouvrir(cookie=False))[0], 401)
        self.assertEqual(lire_entete(self.ouvrir("/ws?token=" + "0" * 64, cookie=False))[0], 401)

    def test_un_autre_site_est_refuse(self):
        self.assertEqual(lire_entete(self.ouvrir(entetes={"Origin": "https://pirate.example"}))[0], 403)
        self.assertEqual(lire_entete(self.ouvrir(entetes={"Origin": "http://127.0.0.1:%d" % self.g.port}))[0], 101)

    def test_une_requete_sans_upgrade_ou_mal_formee_est_refusee(self):
        st, _ = lire_entete(self.ouvrir(upgrade=False))
        self.assertEqual(st, 426)                                              # le proxy n'a pas transmis l'Upgrade : on le dit
        self.assertEqual(lire_entete(self.ouvrir(cle="trop-court"))[0], 400)
        self.assertEqual(lire_entete(self.ouvrir(entetes={"Sec-WebSocket-Version": "8"}))[0], 400)

    def test_un_ping_recoit_son_pong_et_la_fermeture_est_rendue(self):
        s = self.ouvrir()
        lire_entete(s)
        lire_trame(s)
        s.sendall(trame_client(0x9, b"salut"))
        self.assertEqual(lire_trame(s), (0xA, b"salut"))
        s.sendall(trame_client(0x8, struct.pack(">H", 1000)))
        self.assertEqual(lire_trame(s)[0], 0x8)
        self.assertEqual(s.recv(10), b"")                                      # puis la connexion se ferme

    def test_une_trame_non_masquee_ferme_le_flux(self):
        s = self.ouvrir()
        lire_entete(s)
        lire_trame(s)
        s.sendall(trame_client(0x1, b"x", masquee=False))
        s.settimeout(5)
        try:
            while s.recv(100):
                pass
        except (ConnectionResetError, socket.timeout) as e:
            self.assertNotIsInstance(e, socket.timeout, "le flux aurait dû se fermer")

    def test_la_limite_par_compte(self):
        ancien = pg.WS_PAR_COMPTE
        pg.WS_PAR_COMPTE = 2
        self.addCleanup(setattr, pg, "WS_PAR_COMPTE", ancien)
        ouverts = []
        for _ in range(2):
            s = self.ouvrir()
            self.assertEqual(lire_entete(s)[0], 101)
            ouverts.append(s)
        self.assertEqual(lire_entete(self.ouvrir())[0], 429)
        ouverts[0].sendall(trame_client(0x8))                                  # un flux qui part libère sa place
        lire_trame(ouverts[0])
        ouverts[0].close()
        import time
        for _ in range(50):
            if self.g._flux.get("chef@x.fr", 0) < 2:
                break
            time.sleep(0.1)
        self.assertEqual(lire_entete(self.ouvrir())[0], 101)

    def test_une_session_fermee_arrete_le_flux(self):
        ancien = pg.WS_PAS
        pg.WS_PAS = 0.2
        self.addCleanup(setattr, pg, "WS_PAS", ancien)
        s = self.ouvrir()
        lire_entete(s)
        lire_trame(s)
        self.n.executeur.executer("comptes.fermer_session", "humain", {"jeton": self.jeton}, compte="chef@x.fr")
        dernier = None
        while True:
            try:
                op, charge = lire_trame(s)
            except EOFError:
                break
            dernier = (op, charge)
            if op == 0x8:
                break
        self.assertEqual(dernier[0], 0x8)
        self.assertEqual(struct.unpack(">H", dernier[1][:2])[0], 1008)


if __name__ == "__main__":
    unittest.main()
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Flux
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
