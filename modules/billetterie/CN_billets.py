"""Billetterie : la signature des billets (ce qui décide si un billet est authentique).

Un billet porte un NUMÉRO (A-0430) et une VERSION (réémettre un billet change sa version : l'ancien QR ne passe plus). Sa signature est un HMAC-SHA256 du numéro
et de la version, avec une clé que le serveur est seul à connaître (créée au premier usage, chiffrée par le noyau). Le QR code porte `CASS1.<numéro>.<signature>` ;
le numéro de contrôle imprimé dessous porte `<numéro>-<signature>` : saisi en entier, il se vérifie comme le QR (pour l'ouvreur sans lecteur).
C'est du nexus : décider qu'un billet est authentique ne s'évolue jamais.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"        # sans 0, O, 1, I : se dicte à voix haute sans se tromper
_NUM = re.compile(r"^(.+)-([A-HJ-NP-Z2-9]{6})$")


def cle(ctx, db) -> bytes:
    """La clé de signature. À obtenir AVANT d'ouvrir une transaction d'écriture (elle en ouvre une pour se créer la première fois)."""
    lu = db.lire("SELECT valeur FROM cles WHERE nom = 'billets'")
    if lu:
        return bytes.fromhex(ctx.dechiffrer(lu[0]["valeur"], "cle_billets"))
    k = os.urandom(32)
    with db.transaction() as tx:
        deja = tx.execute("SELECT valeur FROM cles WHERE nom = 'billets'").fetchone()
        if deja:
            return bytes.fromhex(ctx.dechiffrer(deja[0], "cle_billets"))
        tx.execute("INSERT INTO cles(nom, valeur) VALUES('billets', ?)", (ctx.chiffrer(k.hex(), "cle_billets"),))
    return k


def signature(k: bytes, numero: str, version: int) -> str:
    n = int.from_bytes(hmac.new(k, ("%s|%d" % (numero, int(version))).encode("utf-8"), hashlib.sha256).digest()[:5], "big")
    s = ""
    for _ in range(6):
        s += ALPHABET[n & 31]
        n >>= 5
    return s


def code_controle(k: bytes, numero: str, version: int) -> str:
    return "%s-%s" % (numero, signature(k, numero, version))


def contenu_qr(k: bytes, numero: str, version: int) -> str:
    return "CASS1.%s.%s" % (numero, signature(k, numero, version))


def lire(texte: str) -> dict:
    """Ce que dit un texte lu (QR scanné ou numéro saisi) : {source: qr|num|nu, numero, signature}. Ne dit PAS s'il est authentique (voir `authentique`)."""
    t = str(texte or "").strip()
    if t.startswith("CASS1."):
        corps = t[len("CASS1."):]
        if "." in corps:
            numero, sig = corps.rsplit(".", 1)
            return {"source": "qr", "numero": numero.strip(), "signature": sig.strip().upper()}
        return {"source": "qr", "numero": corps, "signature": ""}
    m = _NUM.match(t.upper())
    if m:
        return {"source": "num", "numero": m.group(1), "signature": m.group(2)}
    return {"source": "nu", "numero": t.upper(), "signature": ""}


def authentique(k: bytes, numero: str, version: int, signature_lue: str) -> bool:
    return bool(signature_lue) and hmac.compare_digest(signature(k, numero, version), str(signature_lue).upper())


def lettre_evenement(evenement_id: int) -> str:
    """La lettre de série d'un événement : 1 -> A, 26 -> Z, 27 -> AA."""
    n, s = int(evenement_id), ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s or "A"
