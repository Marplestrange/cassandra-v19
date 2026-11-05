# ══════════════════════════════════════════════
# TITRE      : Le générateur d'adaptateurs (le repli)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #9765dd
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Quand aucun adaptateur n'est écrit à la main pour un chercheur, en génère un d'après l'interface réelle du paquet installé, le vérifie sans l'exécuter, l'éprouve dans la cage avec un faux modèle et l'épingle par son empreinte ; il reste « à relire » : le chercheur ne s'active pas avant l'accord de l'admin.
# MÉTHODE    : introspection du paquet dans SON environnement ; un modèle écrit ; l'arbre syntaxique refuse les imports dangereux ; un essai à blanc dans le bac, sans réseau ni clé ; le fichier va dans l'environnement du moteur (jamais dans le code de Cassandra) et un adaptateur écrit à la main passe toujours devant.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9765dd ▼▼▼
"""L'adaptateur généré n'est qu'un pont : il traduit le contexte de Cassandra pour le paquet du chercheur et rend du TEXTE (des variantes). Le juge du noyau décide de tout ensuite,
comme pour n'importe quel moteur ; le moteur tourne dans la cage (sans clé, sans réseau, sans écriture), et ses appels de modèle passent par le relais, compté et plafonné.

Le repli ne joue que quand l'adaptateur MANQUE : un adaptateur écrit à la main (orfan/adaptateurs/) est cherché en premier par l'hôte du moteur et l'emporte toujours.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

try:
    from .CN_installateur import InstallationRefusee
except ImportError:                                                  # chargé par son chemin (un banc)
    from noyau.CN_installateur import InstallationRefusee            # type: ignore

INTERDITS = {"subprocess", "socket", "requests", "urllib", "http", "ftplib", "smtplib", "telnetlib", "ctypes", "multiprocessing", "pty", "pickle", "shutil", "webbrowser", "asyncio", "threading", "importlib"}
APPELS_INTERDITS = {"system", "popen", "__import__", "fork", "execv", "execve", "spawn", "rmtree", "remove", "unlink", "rename", "chmod", "setattr_"}
TAILLE_MAX = 40_000

_SONDE = r'''
import importlib, inspect, json, sys
sortie = []
for nom in sys.argv[1:]:
    try:
        m = importlib.import_module(nom)
    except Exception as e:
        sortie.append({"module": nom, "erreur": "%s : %s" % (type(e).__name__, str(e)[:200])})
        continue
    info = {"module": nom, "version": str(getattr(m, "__version__", "")), "doc": (inspect.getdoc(m) or "")[:1500], "membres": []}
    for k in sorted(dir(m)):
        if k.startswith("_"):
            continue
        o = getattr(m, k, None)
        if inspect.ismodule(o):
            continue
        try:
            sig = str(inspect.signature(o))
        except Exception:
            sig = ""
        info["membres"].append({"nom": k, "type": type(o).__name__, "sig": sig[:200], "doc": (inspect.getdoc(o) or "").split("\n")[0][:160]})
        if len(info["membres"]) >= 60:
            break
    sortie.append(info)
print(json.dumps(sortie))
'''


def verifier_code(code: str) -> str:
    """Une raison dite si le code ne doit pas être gardé, sinon « ». Il n'est JAMAIS exécuté ici."""
    if len(code.encode("utf-8")) > TAILLE_MAX:
        return "trop long (%d octets)" % len(code.encode("utf-8"))
    try:
        arbre = ast.parse(code)
    except SyntaxError as e:
        ligne = (code.splitlines()[e.lineno - 1] if e.lineno and e.lineno <= len(code.splitlines()) else "")[:120]
        return "code invalide : %s — ligne : %s" % (e, ligne.strip())
    importer, proposer = False, False
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in INTERDITS:
                    return "import interdit : %s" % a.name
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] in INTERDITS:
                return "import interdit : %s" % n.module
        elif isinstance(n, ast.Call):
            f = n.func
            nom = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if nom in APPELS_INTERDITS:
                return "appel interdit : %s" % nom
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "IMPORTER" for t in n.targets):
            importer = isinstance(n.value, (ast.List, ast.Tuple))
        elif isinstance(n, ast.FunctionDef) and n.name == "proposer" and len(n.args.args) >= 2:
            proposer = True
    if not proposer:
        return "il manque la fonction proposer(contexte, modele)"
    if not importer:
        return "il manque la liste IMPORTER"
    return ""


def extraire_code(texte: str) -> str:
    m = re.search(r"```(?:python)?\s*\n(.*?)```", texte or "", re.S)
    code = ((m.group(1) if m else texte) or "").strip() + "\n"
    try:
        ast.parse(code)
    except SyntaxError:
        if '\\"' in code:                                                          # certains modèles échappent leurs guillemets comme dans du JSON : on essaie sans, seulement si le code tel quel ne se lit pas
            propre = code.replace('\\"', '"')
            try:
                ast.parse(propre)
                return propre
            except SyntaxError:
                pass
    return code


def sonder(python, importer: list, executer, delai_s: float = 120.0) -> list:
    """L'interface réelle du paquet, lue dans SON environnement."""
    if not importer:
        return []
    import tempfile
    if getattr(executer, "__name__", "") == "_executer":                           # l'exécuteur de l'installateur ne garde que la fin de la sortie : la sonde (plusieurs Ko de JSON) se lit en entier
        from noyau.CN_epinglage import _executer_plein as executer
    with tempfile.TemporaryDirectory(prefix="cn_sonde_") as vide:                  # certains paquets écrivent (./logs/) en s'important : on les laisse dans un dossier jetable
        code, sortie = executer([str(python), "-I", "-c", _SONDE, *importer], delai_s, vide)
    try:
        return json.loads(sortie[sortie.index("["):])
    except (ValueError, json.JSONDecodeError):
        return [{"module": ",".join(importer), "erreur": "sonde illisible : %s" % sortie[-160:]}]


def _exemple(adaptateurs: Path) -> str:
    try:
        texte = (adaptateurs / "CN_adaptateur_gepa.py").read_text(encoding="utf-8")
    except OSError:
        return ""
    a = texte.find('"""', texte.find("▼▼▼ BORNE"))
    return texte[a:a + 6000] if a >= 0 else texte[:6000]


def prompt(rep: dict, api: list, exemple: str, erreur: str = "") -> str:
    return (
        "Tu écris UN adaptateur Python (un seul fichier) qui branche le chercheur « %s » sur Cassandra.\n\n"
        "CONTRAT. Le fichier expose :\n  IMPORTER = [...]   # les modules du chercheur que l'installation doit pouvoir importer\n"
        "  def proposer(contexte, modele) -> list   # rend des variantes : [{\"texte\": <le code COMPLET de la fonction réécrite>, \"hypothese\": <une phrase>}]\n\n"
        "contexte est un dict : source_reference (le code de la fonction de référence), fonction (son nom), entrees (une liste d'arguments d'exemple), budget (le nombre de variantes voulues), tombes (des variantes déjà refusées, à ne pas reproduire).\n"
        "modele(prompt, role) -> str est le SEUL accès à un modèle de langage (role : \"executant\" ou \"strategie\") ; il est compté et plafonné par Cassandra. Si le chercheur a besoin d'un client compatible OpenAI, "
        "modele.url (adresse locale), modele.cle et modele.nom les donnent : n'utilise rien d'autre.\n"
        "Le moteur tourne dans une cage : AUCUN réseau, AUCUNE clé, AUCUNE écriture de fichier, AUCUN lancement de programme. Interdits : subprocess, socket, requests, urllib, http, shutil, threading, asyncio, importlib, pickle, ctypes, os.system. "
        "Importe le paquet du chercheur DANS proposer (pas en haut du fichier). Le code doit rendre ce qu'il a trouvé même si le chercheur échoue en route (attrape les exceptions, rends une liste, possiblement vide). Au plus `budget` variantes.\n\n"
        "%s\n"
        "INTERFACE RÉELLE du paquet installé (lue dans son environnement) :\n%s\n\n"
        "EXEMPLE d'un adaptateur écrit à la main pour un autre chercheur (GEPA), pour le style et le contrat :\n%s\n\n"
        "%sRéponds avec UN SEUL bloc ```python contenant le fichier complet, sans explication."
        % (rep["nom"], ("MÉTHODE À RÉIMPLÉMENTER (il n'y a pas de paquet) : %s\nUtilise seulement la bibliothèque standard et modele(). IMPORTER = [].\n" % rep["methode"]) if rep.get("methode") else
           "Description du chercheur : %s\n" % rep.get("desc", ""), json.dumps(api, ensure_ascii=False, indent=1)[:9000] if api else "(aucun paquet)", exemple, ("TA VERSION PRÉCÉDENTE A ÉCHOUÉ : %s\nCorrige-la.\n\n" % erreur) if erreur else ""))


_CONTEXTE_BLANC = {"point": "controle.essai", "source_reference": "def f(x):\n    return sorted(x)[0]\n", "fonction": "f", "contrat": {}, "entrees": [[3, 1, 2], [9, 4]], "tombes": [], "budget": 2, "seuils": {}}
_REPONSE_BLANCHE = "Idée : prendre le minimum directement.\n```python\ndef f(x):\n    return min(x)\n```"


def generer(entree: dict, rep: dict, python, racine, etape, appeler_modele, executer, adaptateurs: Path, bac: str = "auto", essais: int = 2, mot=None) -> dict:
    """Écrit, vérifie et éprouve l'adaptateur d'un chercheur. Rend {empreinte, code} ; lève InstallationRefusee avec la raison dite."""
    module = str(entree["adaptateur"])
    api = sonder(python, rep.get("importer") or [], executer)
    erreurs = [a for a in api if a.get("erreur")]
    if erreurs and rep.get("importer"):
        etape("adaptateur généré", False, "le paquet ne se charge pas pour être lu : %s" % erreurs[0]["erreur"])
        raise InstallationRefusee("paquet illisible")
    exemple = _exemple(Path(adaptateurs))
    erreur = ""
    code, empreinte = "", ""
    for tentative in range(1, int(essais) + 1):
        try:
            texte = appeler_modele(prompt(rep, api, exemple, erreur), "strategie")
        except Exception as e:
            etape("adaptateur généré", False, "aucun modèle n'a répondu : %s" % str(e)[:160])
            raise InstallationRefusee("pas de modèle pour écrire l'adaptateur")
        code = extraire_code(texte)
        raison = verifier_code(code)
        if raison:
            erreur = raison
            try:
                (Path(racine).parent / ("rejet_%s.txt" % module)).write_text("# rejeté : %s\n# réponse brute du modèle :\n%s\n" % (raison, texte), encoding="utf-8")     # de quoi comprendre un refus (écrasé à chaque essai)
            except OSError:
                pass
            continue
        sp =_site_packages(python, executer)
        if not sp:
            etape("adaptateur généré", False, "le dossier du paquet n'a pas été trouvé")
            raise InstallationRefusee("site-packages introuvable")
        fichier = Path(sp) / (module + ".py")
        fichier.write_text(code, encoding="utf-8", newline="\n")
        empreinte = hashlib.sha256(code.encode("utf-8")).hexdigest()
        raison = essai_a_blanc(entree, python, module, bac, mot)
        if raison:
            erreur = raison
            fichier.unlink(missing_ok=True)
            continue
        etape("adaptateur généré", True, "écrit d'après l'interface du paquet (essai %d), essai à blanc réussi dans la cage · empreinte %s…" % (tentative, empreinte[:12]))
        return {"empreinte": empreinte, "code": code}
    etape("adaptateur généré", False, "rejeté après %d essai(s) : %s" % (essais, erreur))
    raise InstallationRefusee("adaptateur rejeté")


def _site_packages(python, executer) -> str:
    code, sortie = executer([str(python), "-I", "-c", "import site; print(site.getsitepackages()[0])"], 60.0, None)
    chemin = (sortie.strip().splitlines() or [""])[-1].strip()
    return chemin if code == 0 and chemin and Path(chemin).is_dir() else ""


def essai_a_blanc(entree: dict, python, module: str, bac: str = "auto", mot=None) -> str:
    """Le moteur démarre DANS LA CAGE avec l'adaptateur, reçoit un contexte de jouet et un faux modèle, et doit rendre une liste. Rend une raison dite en cas d'échec, sinon « »."""
    if mot is None:
        try:
            from . import CN_moteurs as mot
        except ImportError:
            from noyau import CN_moteurs as mot                                        # type: ignore
    appels = []

    def faux(prompt, role="executant"):
        appels.append(role)
        return _REPONSE_BLANCHE

    try:
        m = mot.MoteurProcessus("adaptateur:" + module, appeler_modele=faux, python=str(python), bac=bac, delai_s=90, nom="essai-a-blanc")
        r = m.proposer(dict(_CONTEXTE_BLANC))
    except Exception as e:
        return "l'essai à blanc a échoué : %s : %s" % (type(e).__name__, str(e)[:240])
    if not isinstance(r, list):
        return "l'adaptateur n'a pas rendu une liste"
    return ""
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════
# EC : néant (la garde ne s'évolue pas).
# CN : le repli des adaptateurs : écrit, vérifié sans être exécuté, éprouvé dans la cage, épinglé, puis relu par l'admin avant toute activation.
# LIEN : noyau/CN_installateur.py (qui l'appelle), orfan/adaptateurs/ (ceux écrits à la main, toujours prioritaires), orfan/CN_moteur_hote.py (l'hôte).
