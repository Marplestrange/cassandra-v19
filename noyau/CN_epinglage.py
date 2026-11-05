# ══════════════════════════════════════════════
# TITRE      : L'épinglage d'un chercheur : du répertoire au catalogue scellé
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #50517a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : « Préparer » un chercheur : résoudre son paquet dans un environnement jetable, épingler chaque dépendance par son empreinte sha256, écrire l'entrée dans le catalogue et le sceller de la clé de l'instance (ce que faisait l'outil en ligne de commande).
# MÉTHODE    : un venv jetable ; `pip install` pour résoudre, `pip freeze` pour figer, `pip download --no-deps` paquet par paquet pour empreinter ; un commit GitHub est résolu en archive épinglée ; un catalogue déjà là mais dont le sceau ne tient pas n'est jamais réécrit.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=50517a ▼▼▼
"""L'épinglage, en bibliothèque : la même démarche que `outils/CN_moteurs_epingler.py`, avec un rapport d'avancement et un `executer` injectable (les bancs).

Seul ce qui est ÉPINGLÉ ici s'installera : l'installateur (noyau/CN_installateur.py) n'installe que ce que le catalogue scellé écrit, par empreinte.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

try:
    from .CN_installateur import InstallationRefusee, lire_catalogue, sceller_catalogue, _executer
except ImportError:                                                  # chargé par son chemin (un banc)
    from noyau.CN_installateur import InstallationRefusee, lire_catalogue, sceller_catalogue, _executer          # type: ignore

_DEPOT = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _python_de(venv: str) -> str:
    return str(Path(venv) / ("Scripts" if sys.platform.startswith("win") else "bin") / ("python.exe" if sys.platform.startswith("win") else "python"))


def _empreinte_url(url: str, delai: float = 180.0) -> str:
    with urllib.request.urlopen(url, timeout=delai) as r:
        return "sha256:" + hashlib.sha256(r.read()).hexdigest()


def _executer_plein(commande: list, delai_s: float, cwd=None) -> tuple:
    """Comme l'exécuteur de l'installateur, mais sans couper la sortie : `pip freeze` d'un gros paquet (77 lignes) dépasse de loin les 600 derniers caractères qu'on garde pour un message d'erreur."""
    import subprocess
    try:
        r = subprocess.run(commande, capture_output=True, timeout=delai_s, cwd=cwd, text=True, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return 124, "délai de %.0f s dépassé" % delai_s
    except OSError as e:
        return 127, str(e)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def resoudre_commit(depot: str, ref: str = "HEAD", ouvrir=None) -> str:
    """Le commit EXACT qu'une branche désigne aujourd'hui (l'épinglage ne fige jamais « main » : un commit)."""
    if not _DEPOT.match(depot):
        raise InstallationRefusee("dépôt invalide : %r" % (depot,))
    if _COMMIT.match(ref):
        return ref
    ouvrir = ouvrir or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"Accept": "application/vnd.github+json", "User-Agent": "cassandra"}), timeout=30))
    with ouvrir("https://api.github.com/repos/%s/commits/%s" % (depot, ref)) as r:
        sha = str(json.loads(r.read().decode("utf-8")).get("sha", ""))
    if not _COMMIT.match(sha):
        raise InstallationRefusee("le commit de %s n'a pas pu être résolu" % depot)
    return sha


def epingler(rep: dict, interpreteur: str = "", progres=None, executer=None, delai_s: float = 900.0, empreinte_url=None, commit=None, executer_plein=None) -> dict:
    """Rend l'entrée du catalogue d'un chercheur du répertoire : {id, nom, version, adaptateur, paquets:[{requis, empreintes}], interpreteur?}.
    `progres(texte)` est appelé à chaque pas. Lève InstallationRefusee avec une raison dite."""
    dire = progres or (lambda t: None)
    ex = executer or _executer
    plein = executer_plein or (executer if executer is not None else _executer_plein)             # le gel des versions se lit en entier
    empreinter = empreinte_url or _empreinte_url
    ident = rep["id"]
    entree = {"id": ident, "nom": rep["nom"], "version": "", "adaptateur": rep.get("adaptateur") or ("CN_adaptateur_" + ident), "paquets": []}
    if rep.get("adaptateur") is None:
        entree["adaptateur_genere"] = True
    if interpreteur:
        entree["interpreteur"] = interpreteur
    if rep.get("importer"):
        entree["importer"] = list(rep["importer"])
    if not rep.get("paquet") and not rep.get("github"):                                    # une méthode réimplémentée : rien à épingler
        entree["version"] = "méthode"
        dire("aucun paquet à épingler : la méthode est réimplémentée")
        return entree
    if rep.get("github"):
        dire("recherche du commit de %s" % rep["github"])
        sha = commit or resoudre_commit(rep["github"], rep.get("ref", "HEAD"))
        spec = "%s @ https://codeload.github.com/%s/tar.gz/%s" % (rep.get("paquet_nom", ident), rep["github"], sha)
        entree["version"] = sha[:12]
    else:
        spec, entree["version"] = rep["paquet"], ""
    with tempfile.TemporaryDirectory(prefix="cn_epingler_") as tmp:
        venv = os.path.join(tmp, "v")
        dire("environnement jetable")
        code, sortie = ex([interpreteur or sys.executable, "-m", "venv", venv], delai_s, None)
        if code:
            raise InstallationRefusee("environnement jetable non créé : %s" % sortie[-200:])
        py = _python_de(venv)
        dire("résolution de %s (pip)" % rep["nom"])
        code, sortie = ex([py, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", spec], delai_s, None)
        if code:
            raise InstallationRefusee("le paquet ne se résout pas : %s" % sortie[-300:])
        code, gel_txt = plein([py, "-m", "pip", "freeze", "--disable-pip-version-check"], delai_s, None)
        gel = [l.strip() for l in gel_txt.splitlines() if "==" in l and not l.startswith("-e")]
        if " @ " in spec:                                                                      # une archive : pip freeze la montre en fichier local, on garde l'adresse DONNÉE
            nom_archive = spec.split(" @ ", 1)[0].strip().lower().replace("_", "-")
            gel = [spec] + [l for l in gel if l.split("==")[0].strip().lower().replace("_", "-") != nom_archive]
        elif not entree["version"]:
            nom = spec.strip().lower().replace("_", "-")
            for l in gel:
                if l.split("==")[0].strip().lower().replace("_", "-") == nom:
                    entree["version"] = l.split("==")[1]
        if code or not gel:
            raise InstallationRefusee("rien à épingler : pip n'a rien figé")
        for i, requis in enumerate(gel, 1):
            dire("empreinte %d/%d : %s" % (i, len(gel), requis.split(" @ ")[0].split("==")[0]))
            if " @ " in requis:
                entree["paquets"].append({"requis": requis, "empreintes": [empreinter(requis.split(" @ ", 1)[1])]})
                continue
            dossier = os.path.join(tmp, "dl", requis.replace("==", "-").replace("/", "_"))
            os.makedirs(dossier)
            code, sortie = ex([py, "-m", "pip", "download", "--disable-pip-version-check", "--no-input", "--no-deps", "-d", dossier, requis], delai_s, None)
            fichiers = sorted(os.listdir(dossier)) if os.path.isdir(dossier) else []
            if code or not fichiers:
                raise InstallationRefusee("téléchargement impossible pour %s : %s" % (requis, sortie[-200:]))
            entree["paquets"].append({"requis": requis, "empreintes": ["sha256:" + hashlib.sha256(open(os.path.join(dossier, f), "rb").read()).hexdigest() for f in fichiers]})
    entree["plateforme"] = sys.platform
    return entree


def inscrire(chemin: str | Path, entree: dict, cle: bytes) -> dict:
    """Écrit l'entrée au catalogue et le SCELLE. Un catalogue qui existe mais dont le sceau ne tient pas n'est jamais réécrit : il a été modifié, on ne le fait pas passer pour sain."""
    chemin = Path(chemin)
    if chemin.exists():
        cat = lire_catalogue(chemin, cle)                                                  # lève InstallationRefusee si le sceau ne correspond pas
    else:
        cat = {"moteurs": []}
    cat["moteurs"] = [m for m in cat.get("moteurs", []) if m.get("id") != entree["id"]] + [entree]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(cat, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8", newline="\n")
    chemin.with_suffix(".sceau").write_text(sceller_catalogue(cat, cle), encoding="utf-8")
    return cat
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════
# EC : néant (l'épinglage est la garde : il ne s'évolue pas).
# CN : la seule porte par laquelle un chercheur entre au catalogue scellé, depuis l'écran comme depuis la ligne de commande.
# LIEN : noyau/CN_repertoire.py (ce qui est proposé), noyau/CN_installateur.py (qui n'installe que ce qui est épinglé), outils/CN_moteurs_epingler.py (la version en ligne de commande).
