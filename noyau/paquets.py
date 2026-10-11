"""Le paquet d'un module : l'unité qu'un module store distribue.

Un paquet (`.cmod`) est une archive tar.gz qui contient :
    <id>/        le dossier du module (manifeste.toml, module.py, scripts...)
    SOMMES       une ligne « sha256  chemin » par fichier, triées : l'empreinte du contenu
    SIGNATURE    la signature Ed25519 de SOMMES par l'éditeur (absente pour un paquet non signé)

Trois garanties, dans cet ordre :
  1. l'archive ne peut ni sortir de son dossier, ni contenir de lien, de périphérique ou de fichier démesuré ;
  2. le contenu extrait correspond exactement à SOMMES (rien n'a été modifié depuis la signature) ;
  3. SOMMES est signé par une clé de confiance (config/cles/<editeur>.pub), sinon le paquet est « non signé ».

La signature passe par OpenSSL (Ed25519, présent partout) : la bibliothèque standard de Python n'en a pas.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from . import manifeste as mf

MAX_FICHIERS = 2000
MAX_OCTETS = 64 * 2 ** 20


class PaquetInvalide(ValueError):
    pass


def _sommes(dossier: Path) -> bytes:
    lignes = []
    for p in sorted(dossier.rglob("*")):
        if p.is_symlink():
            raise PaquetInvalide("lien symbolique refusé : %s" % p.relative_to(dossier))
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            lignes.append("%s  %s" % (h, p.relative_to(dossier).as_posix()))
    return ("\n".join(lignes) + "\n").encode("utf-8")


def _openssl(*args) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["openssl", *args], capture_output=True, timeout=30)
    except FileNotFoundError as ex:
        raise PaquetInvalide("openssl est nécessaire pour signer et vérifier les paquets") from ex


def construire(dossier, cle_privee, sortie=None) -> Path:
    """Fabrique le paquet d'un module : reproductible (même contenu, même archive), signé par `cle_privee` (PEM Ed25519)."""
    dossier = Path(dossier).resolve()
    if not (dossier / "manifeste.toml").is_file():
        raise PaquetInvalide("%s : pas de manifeste.toml" % dossier)
    m = mf.charger(dossier / "manifeste.toml")
    if m.id != dossier.name:
        raise PaquetInvalide("l'id « %s » diffère du dossier « %s »" % (m.id, dossier.name))
    if m.confiance == "interne":
        raise PaquetInvalide("« interne » est réservé aux modules livrés avec le noyau : un paquet ne peut pas le revendiquer")
    sommes = _sommes(dossier)
    with tempfile.TemporaryDirectory() as t:
        f = Path(t) / "SOMMES"
        f.write_bytes(sommes)
        sig = Path(t) / "SIGNATURE"
        r = _openssl("pkeyutl", "-sign", "-inkey", str(cle_privee), "-rawin", "-in", str(f), "-out", str(sig))
        if r.returncode != 0:
            raise PaquetInvalide("signature impossible : %s" % r.stderr.decode(errors="replace")[:200])
        signature = sig.read_bytes()
    sortie = Path(sortie) if sortie else dossier.parent / ("%s-%s.cmod" % (m.id, m.version))

    def entree(nom, donnees, mode=0o644):
        ti = tarfile.TarInfo(nom)
        ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = len(donnees), 0, mode, 0, 0, "", ""
        return ti, io.BytesIO(donnees)

    with tarfile.open(sortie, "w:gz", format=tarfile.PAX_FORMAT) as tar:
        for p in sorted(dossier.rglob("*")):
            rel = (Path(m.id) / p.relative_to(dossier)).as_posix()
            if p.is_dir():
                ti = tarfile.TarInfo(rel + "/")
                ti.type, ti.mode, ti.mtime = tarfile.DIRTYPE, 0o755, 0
                tar.addfile(ti)
            elif p.is_file():
                ti, flux = entree(rel, p.read_bytes(), 0o755 if p.suffix == ".sh" else 0o644)
                tar.addfile(ti, flux)
        for nom, donnees in (("SOMMES", sommes), ("SIGNATURE", signature)):
            ti, flux = entree(nom, donnees)
            tar.addfile(ti, flux)
    return sortie


def _extraire_surement(archive, dest: Path) -> Path:
    """Extrait en vérifiant chaque entrée. Rend le dossier du module."""
    dest.mkdir(parents=True, exist_ok=True)
    racines, total, n = set(), 0, 0
    try:
        tar = tarfile.open(archive, "r:gz")
    except (tarfile.TarError, OSError, EOFError) as ex:
        raise PaquetInvalide("archive illisible : %s" % ex) from ex
    with tar:
        membres = tar.getmembers()
        for ti in membres:
            n += 1
            total += max(ti.size, 0)
            if n > MAX_FICHIERS or total > MAX_OCTETS:
                raise PaquetInvalide("archive démesurée (plus de %d fichiers ou %d Mo)" % (MAX_FICHIERS, MAX_OCTETS // 2 ** 20))
            nom = ti.name
            parts = Path(nom).parts
            if nom.startswith("/") or ".." in parts or not parts:
                raise PaquetInvalide("chemin refusé : %s" % nom)
            if not (ti.isfile() or ti.isdir()):
                raise PaquetInvalide("seuls les fichiers et dossiers sont permis (refusé : %s)" % nom)
            if parts[0] not in ("SOMMES", "SIGNATURE"):
                racines.add(parts[0])
        if len(racines) != 1:
            raise PaquetInvalide("le paquet doit contenir un seul dossier de module (trouvé : %s)" % (", ".join(sorted(racines)) or "aucun"))
        # Extraction à la main : pas d'extractall (son option `filter` n'existe qu'à partir de Python 3.11.4), et rien d'autre
        # que des fichiers et des dossiers, aux droits imposés, qui ne peuvent pas sortir de `dest`.
        base = dest.resolve()
        for ti in membres:
            cible = dest / ti.name
            if base not in cible.resolve().parents and cible.resolve() != base:
                raise PaquetInvalide("chemin refusé : %s" % ti.name)
            if ti.isdir():
                cible.mkdir(parents=True, exist_ok=True)
                continue
            cible.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(ti) as src, open(cible, "wb") as dst:
                shutil.copyfileobj(src, dst)
            os.chmod(cible, 0o755 if cible.suffix == ".sh" else 0o644)
    return dest / next(iter(racines))


def verifier(archive, dossier_cles=None) -> dict:
    """{'id', 'version', 'signe', 'editeur', 'manifeste'}. Lève PaquetInvalide si l'archive est altérée ou dangereuse."""
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        mod = _extraire_surement(archive, t / "x")
        somm = t / "x" / "SOMMES"
        if not somm.is_file():
            raise PaquetInvalide("SOMMES absent : paquet sans empreinte")
        if _sommes(mod) != somm.read_bytes():
            raise PaquetInvalide("le contenu ne correspond pas à SOMMES : le paquet a été modifié")
        m = mf.charger(mod / "manifeste.toml")
        if m.id != mod.name:
            raise PaquetInvalide("l'id « %s » diffère du dossier « %s »" % (m.id, mod.name))
        sig = t / "x" / "SIGNATURE"
        editeur = None
        if sig.is_file() and dossier_cles and Path(dossier_cles).is_dir():
            for cle in sorted(Path(dossier_cles).glob("*.pub")):
                r = _openssl("pkeyutl", "-verify", "-pubin", "-inkey", str(cle), "-rawin", "-in", str(somm), "-sigfile", str(sig))
                if r.returncode == 0:
                    editeur = cle.stem
                    break
        return {"id": m.id, "version": m.version, "signe": editeur is not None, "editeur": editeur, "manifeste": m}


def extraire(archive, dest, dossier_cles=None, exiger_signature=True) -> dict:
    """Vérifie puis dépose le dossier du module dans `dest`/<id>. Un paquet non signé n'est accepté que si on l'a demandé."""
    v = verifier(archive, dossier_cles)
    if exiger_signature and not v["signe"]:
        raise PaquetInvalide("paquet non signé par une clé de confiance (config/cles/*.pub) : refusé")
    with tempfile.TemporaryDirectory() as t:
        mod = _extraire_surement(archive, Path(t) / "x")
        cible = Path(dest) / v["id"]
        if cible.exists():
            shutil.rmtree(cible)
        Path(dest).mkdir(parents=True, exist_ok=True)
        shutil.copytree(mod, cible)
    return v
