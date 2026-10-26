# ══════════════════════════════════════════════════════════════════
# TITRE      : Le registre officiel de Cassandra : l'adresse, la racine de confiance, l'index signé
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #059b55
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le registre officiel de Cassandra, EN DUR : son adresse, ses deux clés racine, la lecture de son index signé (éditeurs vérifiés, révocations) et les niveaux de confiance.
# MÉTHODE    : l'index est un fichier JSON accompagné de sa signature Ed25519 (index.json.sig, en base64) ; une clé racine EMBARQUÉE ici le vérifie, jamais une clé du disque ; un index périmé, ou signé par une autre clé, est refusé ; les éditeurs et les révocations qu'il porte sont donc couverts par la même signature
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=059b55 ▼▼▼
"""Le registre officiel, dont l'application connaît l'adresse et la clé : ce n'est pas un réglage.

    URL_OFFICIELLE   où vit l'index (une page statique : le dépôt `cassandra-registre`, publié) ; elle changera de domaine un jour, pas de forme.
    CLES_RACINE      deux clés publiques Ed25519, la principale et celle de secours : la confiance de TOUT ce que le registre dit vient d'elles. La clé privée de chacune est hors ligne,
                     jamais dans le dépôt ni dans l'outil d'intégration continue. En cas de perte ou de fuite de la principale, la secours signe un index qui annonce la rotation.
    L'index          {"format": 1, "emis": ts, "expire": ts, "modules": [...], "editeurs": [...], "revocations": [...]} ; sa signature couvre les OCTETS exacts du fichier.

Trois niveaux de confiance, que l'application montre :
    officiel         l'archive est signée par une clé racine (écrite ou relue par l'équipe de Cassandra)
    verifie          elle est signée par un éditeur que l'index signé déclare vérifié
    local            elle est signée par une clé que l'administrateur a posée lui-même (config/cles)
    (rien)           non signée : seule la politique « tous » l'accepte
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from . import CN_manifeste as mf

URL_OFFICIELLE = "https://marplestrange.github.io/cassandra-registre/index.json"
FORMAT = 1
TOLERANCE_HORLOGE_S = 3600            # une horloge en avance d'une heure ne rend pas un index « du futur »

CLES_RACINE = {
    "principale": """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEA+cKesWjI5Zt2PBUaAE1ZPYK8ZLu+9MSu+W2zj4yek1g=
-----END PUBLIC KEY-----
""",
    "secours": """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAccbKbL0DNQ585E44qW9G44qBygDeIHiPjwsPMPLPQAo=
-----END PUBLIC KEY-----
""",
}
NIVEAUX = ("officiel", "verifie", "local")
_ID = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
_PEM = re.compile(r"^-----BEGIN PUBLIC KEY-----\n[A-Za-z0-9+/=\n]{40,200}-----END PUBLIC KEY-----\n?$")


class RegistreErreur(ValueError):
    pass


def _openssl(*args) -> subprocess.CompletedProcess:
    return subprocess.run(["openssl", *args], capture_output=True)


def signature_valide(octets: bytes, signature_b64: bytes, cles: dict) -> str:
    """Le NOM de la clé de `cles` ({nom: PEM}) qui a signé `octets`, ou "" ; la signature est en base64 (un fichier texte qu'on peut relire et comparer)."""
    try:
        brut = base64.b64decode(bytes(signature_b64).strip(), validate=True)
    except (ValueError, TypeError):
        return ""
    if len(brut) != 64:                                    # une signature Ed25519 fait 64 octets
        return ""
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        (t / "m").write_bytes(octets)
        (t / "s").write_bytes(brut)
        for nom, pem in cles.items():
            (t / "k.pub").write_text(pem, encoding="utf-8")
            if _openssl("pkeyutl", "-verify", "-pubin", "-inkey", str(t / "k.pub"), "-rawin", "-in", str(t / "m"), "-sigfile", str(t / "s")).returncode == 0:
                return nom
    return ""


def signer(octets: bytes, cle_privee) -> bytes:
    """La signature base64 de `octets` (l'outil de publication, hors ligne, s'en sert ; le client ne signe jamais)."""
    with tempfile.TemporaryDirectory() as t:
        (Path(t) / "m").write_bytes(octets)
        r = _openssl("pkeyutl", "-sign", "-inkey", str(cle_privee), "-rawin", "-in", str(Path(t) / "m"), "-out", str(Path(t) / "s"))
        if r.returncode != 0:
            raise RegistreErreur("signature impossible : %s" % r.stderr.decode("utf-8", "replace")[:120])
        return base64.b64encode((Path(t) / "s").read_bytes()) + b"\n"


def lire_index_signe(octets: bytes, signature: bytes, cles_racine: dict | None = None, maintenant: float | None = None) -> dict:
    """Vérifie la signature (une clé racine) puis le contenu : format, validité dans le temps. Rend {'signe_par', 'emis', 'expire', 'brut'}. Refuse tout le reste."""
    cles = CLES_RACINE if cles_racine is None else cles_racine
    qui = signature_valide(octets, signature, cles)
    if not qui:
        raise RegistreErreur("la signature de l'index ne correspond à aucune clé racine : index refusé")
    try:
        brut = json.loads(octets.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as ex:
        raise RegistreErreur("l'index n'est pas un JSON lisible") from ex
    if not isinstance(brut, dict) or brut.get("format") != FORMAT:
        raise RegistreErreur("format d'index inconnu (attendu : %d) : mettez Cassandra à jour" % FORMAT)
    now = time.time() if maintenant is None else maintenant
    emis, expire = brut.get("emis"), brut.get("expire")
    if not isinstance(emis, (int, float)) or not isinstance(expire, (int, float)):
        raise RegistreErreur("l'index doit dater son émission et son expiration")
    if emis > now + TOLERANCE_HORLOGE_S:
        raise RegistreErreur("l'index est daté du futur : horloge de la machine, ou index forgé")
    if expire < now:
        raise RegistreErreur("l'index a expiré : on ne s'appuie pas sur un registre qui n'est plus tenu à jour")
    return {"signe_par": qui, "emis": emis, "expire": expire, "brut": brut}


def lire_editeurs(brut: dict) -> dict:
    """{id : {'nom', 'cle' (PEM)}} : les éditeurs que l'index signé déclare VÉRIFIÉS. Une entrée mal formée est écartée."""
    sortie = {}
    for x in brut.get("editeurs") or []:
        if isinstance(x, dict) and _ID.match(str(x.get("id", ""))) and x.get("verifie") is True and isinstance(x.get("cle"), str) and _PEM.match(x["cle"].replace("\r", "")):
            sortie[x["id"]] = {"nom": str(x.get("nom") or x["id"])[:60], "cle": x["cle"].replace("\r", "")}
    return sortie


def lire_revocations(brut: dict) -> list:
    """[{'id', 'versions' (« <2.0 », vide = toutes), 'raison'}]."""
    sortie = []
    for x in brut.get("revocations") or []:
        if isinstance(x, dict) and _ID.match(str(x.get("id", ""))):
            v = str(x.get("versions", "")).strip()
            if v and mf.lire_requis("xx " + v) is None:
                continue
            sortie.append({"id": x["id"], "versions": v, "raison": str(x.get("raison", ""))[:300]})
    return sortie


def revocation_de(mid: str, version: str, revocations: list) -> str:
    """La raison pour laquelle cette version de ce module est révoquée, ou ""."""
    for r in revocations:
        if r["id"] == mid and (not r["versions"] or mf.satisfait(version, r["versions"])):
            return r["raison"] or "révoqué par le registre"
    return ""


def niveau_de(editeur: str) -> str:
    """Le niveau de confiance d'après le NOM de la clé qui a signé (voir Cycle._dossier_cles) : cassandra-* = officiel, ed_* = éditeur vérifié, le reste = une clé posée par l'administrateur."""
    if not editeur:
        return ""
    if editeur.startswith("cassandra-"):
        return "officiel"
    if editeur.startswith("ed_"):
        return "verifie"
    return "local"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : URL_OFFICIELLE, CLES_RACINE, signature_valide, signer, lire_index_signe, lire_editeurs, lire_revocations, revocation_de, niveau_de.
# EC : néant.
# LIEN : noyau/CN_cycle.py (qui s'en sert pour le registre), outils/CN_registre.py (la publication, hors ligne), docs/CN_REGISTRE.md.
