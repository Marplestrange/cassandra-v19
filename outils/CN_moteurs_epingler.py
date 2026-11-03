#!/usr/bin/env python3
# ══════════════════════════════════════════════
# TITRE      : Épingler un moteur externe pour le catalogue
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #b8b82b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Résout un paquet de moteur dans un environnement neuf, télécharge chaque dépendance, calcule son empreinte sha256 et écrit l'entrée du catalogue des moteurs (et son sceau si on donne la clé).
# MÉTHODE    : un venv jetable ; `pip install` pour résoudre, `pip freeze` pour figer, `pip download --no-deps` paquet par paquet pour empreinter ; les empreintes sont celles des fichiers de CETTE plateforme.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b8b82b ▼▼▼
"""Usage :
  python outils/CN_moteurs_epingler.py --id openevolve --nom OpenEvolve --paquet openevolve==0.4.1 --adaptateur CN_adaptateur_openevolve \\
         --catalogue <données>/moteurs-catalogue.json [--cle <fichier de la clé de l'instance>]

À lancer sur la machine qui installera le moteur : les fichiers binaires (numpy…) diffèrent selon la plateforme, donc leurs empreintes aussi. Le catalogue est ensuite SCELLÉ avec la clé de
l'instance (`<stock>.cle`) ; un catalogue non scellé, ou modifié depuis, est refusé à l'installation (noyau/CN_installateur.py). C'est cet outil, lancé par l'admin, qui décide ce qui est digne de confiance :
l'installateur, lui, n'installe que ce qui y est écrit, par empreinte.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _lancer(cmd, delai=900):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=delai)
    if r.returncode != 0:
        raise SystemExit("échec : %s\n%s" % (" ".join(cmd[:6]), (r.stdout + r.stderr)[-800:]))
    return r.stdout


def _python(venv):
    return str(Path(venv) / ("Scripts" if sys.platform.startswith("win") else "bin") / ("python.exe" if sys.platform.startswith("win") else "python"))


def epingler(paquet: str, ident: str, nom: str, adaptateur: str, version: str = "") -> dict:
    with tempfile.TemporaryDirectory(prefix="cn_epingler_") as tmp:
        venv = os.path.join(tmp, "v")
        _lancer([sys.executable, "-m", "venv", venv])
        py = _python(venv)
        _lancer([py, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", paquet])
        gel = [l.strip() for l in _lancer([py, "-m", "pip", "freeze", "--disable-pip-version-check"]).splitlines() if "==" in l and not l.startswith("-e")]
        paquets = []
        for requis in gel:
            dossier = os.path.join(tmp, "dl", requis.replace("==", "-").replace("/", "_"))
            os.makedirs(dossier)
            _lancer([py, "-m", "pip", "download", "--disable-pip-version-check", "--no-input", "--no-deps", "-d", dossier, requis])
            fichiers = sorted(os.listdir(dossier))
            if not fichiers:
                raise SystemExit("rien de téléchargé pour %s" % requis)
            paquets.append({"requis": requis, "empreintes": ["sha256:" + hashlib.sha256(open(os.path.join(dossier, f), "rb").read()).hexdigest() for f in fichiers]})
    return {"id": ident, "nom": nom, "version": version or paquet.split("==")[-1], "adaptateur": adaptateur, "paquets": paquets, "plateforme": sys.platform}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True)
    ap.add_argument("--nom", required=True)
    ap.add_argument("--paquet", required=True, help="un paquet épinglé, par ex. openevolve==0.4.1")
    ap.add_argument("--adaptateur", required=True, help="le module d'adaptateur (orfan/adaptateurs/)")
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--cle", help="le fichier de la clé de l'instance : si donné, le catalogue est scellé")
    a = ap.parse_args()
    if "==" not in a.paquet:
        raise SystemExit("le paquet doit être épinglé (nom==version)")
    entree = epingler(a.paquet, a.id, a.nom, a.adaptateur)
    chemin = Path(a.catalogue)
    cat = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {"moteurs": []}
    cat["moteurs"] = [m for m in cat.get("moteurs", []) if m.get("id") != a.id] + [entree]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(cat, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8", newline="\n")
    if a.cle:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from noyau.CN_installateur import sceller_catalogue
        chemin.with_suffix(".sceau").write_text(sceller_catalogue(cat, Path(a.cle).read_bytes()), encoding="utf-8")
    print("%s : %d paquet(s) épinglé(s) → %s%s" % (a.id, len(entree["paquets"]), chemin, " (scellé)" if a.cle else " (NON scellé : aucun moteur ne s'installera)"))


if __name__ == "__main__":
    main()
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════
# EC : néant (un outil d'administration).
# CN : la seule porte par laquelle un moteur externe entre au catalogue ; elle est lancée à la main, par l'admin.
# LIEN : noyau/CN_installateur.py (qui n'installe que ce que ce catalogue épingle), orfan/adaptateurs/ (les adaptateurs).
