# ══════════════════════════════════════════════
# TITRE      : Le générateur d'adaptateurs (le repli)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #cc9bd5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Quand aucun adaptateur n'est écrit à la main pour un chercheur, en génère un d'après l'interface réelle du paquet installé, le vérifie sans l'exécuter, l'éprouve dans la cage avec un faux modèle et l'épingle par son empreinte ; il reste « à relire » : le chercheur ne s'active pas avant l'accord de l'admin.
# MÉTHODE    : introspection du paquet dans SON environnement ; un modèle écrit ; l'arbre syntaxique refuse les imports dangereux ; un essai à blanc dans le bac, sans réseau ni clé ; le fichier va dans l'environnement du moteur (jamais dans le code de Cassandra) et un adaptateur écrit à la main passe toujours devant.
# ══════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=cc9bd5 ▼▼▼
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
    """Le code de la réponse. Le code d'un adaptateur peut LUI-MÊME contenir trois apostrophes inversées (une expression régulière qui lit des blocs de code) : le premier « ``` » rencontré n'est donc pas forcément la fin. On prend d'abord de la première barrière à la dernière ; si cela ne se lit pas (plusieurs blocs), de la première à la suivante."""
    texte = texte or ""
    candidats = []
    for motif in (r"```(?:python)?[ \t]*\n(.*)```", r"```(?:python)?[ \t]*\n(.*?)```"):
        m = re.search(motif, texte, re.S)
        if m:
            candidats.append(m.group(1).strip() + "\n")
    candidats.append(texte.strip() + "\n")
    for code in candidats:
        try:
            ast.parse(code)
            return code
        except SyntaxError:
            continue
    return candidats[0]


def sonder(python, importer: list, executer, delai_s: float = 120.0) -> list:
    """L'interface réelle du paquet, lue dans SON environnement."""
    if not importer:
        return []
    import tempfile
    if getattr(executer, "__name__", "") == "_executer":                           # l'exécuteur de l'installateur ne garde que la fin de la sortie : la sonde (plusieurs Ko de JSON) se lit en entier
        from noyau.CN_epinglage import _executer_plein as executer
    with tempfile.TemporaryDirectory(prefix="cn_sonde_") as vide:                  # certains paquets écrivent (./logs/) en s'important : on les laisse dans un dossier jetable
        code, sortie = executer([str(python), "-I", "-c", _SONDE, *importer], delai_s, vide)
    for ligne in sortie.splitlines():                                              # le paquet peut écrire des avertissements AVANT ou APRÈS la ligne de JSON (transformers, par exemple)
        ligne = ligne.strip()
        if ligne.startswith("["):
            try:
                r = json.loads(ligne)
            except ValueError:
                continue
            if isinstance(r, list):
                return r
    return [{"module": ",".join(importer), "erreur": "sonde illisible : %s" % sortie[-700:]}]


def _exemple(adaptateurs: Path) -> str:
    try:
        texte = (adaptateurs / "CN_adaptateur_gepa.py").read_text(encoding="utf-8")
    except OSError:
        return ""
    a = texte.find('"""', texte.find("▼▼▼ BORNE"))
    return texte[a:a + 6000] if a >= 0 else texte[:6000]


PIED = (
    "\n\ndef proposer(contexte, modele):\n"
    "    from CN_gabarit_adaptateur import executer\n"
    "    return executer(contexte, modele, produire, __name__)\n"
)


def assembler(code: str) -> str:
    """Le fichier final : l'opérateur écrit par le modèle, puis `proposer` (fixe, relu une fois) qui passe par le gabarit commun."""
    return code.rstrip() + "\n" + PIED


def _avale(handler) -> bool:
    """Un « except » dont le corps ne fait que `pass`, `return`, `return None` ou `return []` : une panne avalée."""
    for n in handler.body:
        if isinstance(n, ast.Pass):
            continue
        if isinstance(n, ast.Return) and (n.value is None or (isinstance(n.value, ast.Constant) and n.value.value is None) or (isinstance(n.value, ast.List) and not n.value.elts)):
            continue
        return False
    return True


def verifier_operateur(code: str, rep: dict) -> str:
    """Une raison dite si ce que le modèle a écrit n'est pas un bon OPÉRATEUR (`produire`), sinon « »."""
    try:
        arbre = ast.parse(code)
    except SyntaxError:
        return ""                                                                  # verifier_code le dira, avec la ligne
    attendu = set(rep.get("importer") or [])
    produire, racines, noms = False, set(), set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.FunctionDef) and n.name == "proposer":
            return "ne définis pas proposer : il est ajouté pour toi, définis seulement produire(contexte, modele)"
        if isinstance(n, ast.FunctionDef) and n.name == "produire" and len(n.args.args) >= 2:
            produire = True
        elif isinstance(n, ast.Import):
            for a in n.names:
                racines.add(a.name.split(".")[0])
                if a.name.split(".")[0] in attendu:
                    noms.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            racines.add((n.module or "").split(".")[0])
            if (n.module or "").split(".")[0] in attendu:
                noms.update(a.asname or a.name for a in n.names)
        elif isinstance(n, ast.ExceptHandler) and _avale(n):
            return "n'avale pas les erreurs (« except … : pass » ou « return [] ») : laisse-les remonter, le gabarit les dit et te les redonnera"
    if not produire:
        return "il manque la fonction produire(contexte, modele)"
    if attendu and not rep.get("reimplemente") and not rep.get("methode"):
        if not (attendu & racines):
            return "n'utilise pas le paquet du chercheur (%s) : importe-le dans produire et appelle-le pour de vrai" % ", ".join(sorted(attendu))
        appele = False
        for n in ast.walk(arbre):
            if isinstance(n, ast.Call):
                f = n.func
                while isinstance(f, ast.Attribute):
                    f = f.value
                if isinstance(f, ast.Name) and f.id in noms:
                    appele = True
                    break
        if not appele:
            return "importe le paquet (%s) mais n'en APPELLE rien (hériter d'une de ses classes ne compte pas) : appelle son interface réelle, par exemple sa fonction ou sa classe principale, pour qu'il serve vraiment" % ", ".join(sorted(attendu))
    return ""


def prompt(rep: dict, api: list, exemple: str, erreur: str = "", precedent: str = "") -> str:
    if rep.get("methode"):
        quoi = "MÉTHODE À RÉIMPLÉMENTER (il n'y a pas de paquet) : %s\nUtilise seulement la bibliothèque standard et modele(). IMPORTER = [].\n" % rep["methode"]
    elif rep.get("reimplemente"):
        quoi = ("MÉTHODE À RÉIMPLÉMENTER : le paquet est installé mais n'expose rien qui marche avec le relais de Cassandra (il veut ses propres modèles ou un environnement) ; réimplémente sa MÉTHODE : %s\n"
                "Utilise modele(). IMPORTER = %s (l'installation vérifie que le paquet se charge ; tu n'as pas à l'appeler).\n" % (rep["reimplemente"], json.dumps(rep.get("importer") or [])))
    else:
        quoi = "Description du chercheur : %s\nTu DOIS utiliser le paquet du chercheur pour de vrai (importe-le dans produire et appelle son interface réelle ci-dessous), pas seulement demander une réécriture au modèle.\n" % rep.get("desc", "")
    return (
        "Tu écris l'OPÉRATEUR d'un adaptateur Python qui branche le chercheur « %s » sur Cassandra. Un gabarit relu à la main fait tout le reste (extraire le code, écarter les doublons, vérifier que chaque variante rend le même résultat que la référence) : toi, tu n'écris QUE ceci :\n\n"
        "  IMPORTER = [...]   # les modules du chercheur que l'installation doit pouvoir importer\n"
        "  def produire(contexte, modele) -> list   # rend des propositions : une liste de textes (le code COMPLET de la fonction réécrite) ou de {\"texte\": ..., \"hypothese\": <une phrase>}\n\n"
        "NE DÉFINIS PAS proposer : il est ajouté pour toi. N'attrape PAS les exceptions pour les cacher (« except …: pass », « return [] ») : laisse-les remonter, le gabarit les dira et on te les redonnera pour que tu corriges.\n\n"
        "contexte est un dict : source_reference (le code de la fonction de référence), fonction (son nom), entrees (une liste d'arguments d'exemple), budget (le nombre de variantes voulues), tombes (des variantes déjà refusées, à ne pas reproduire).\n"
        "modele(prompt, role) -> str est le SEUL accès à un modèle de langage (role : \"executant\" ou \"strategie\") ; il est compté et plafonné par Cassandra. Si le chercheur a besoin d'un client compatible OpenAI, "
        "modele.url (adresse locale), modele.cle et modele.nom les donnent : n'utilise rien d'autre.\n"
        "Le moteur tourne dans une cage : AUCUN réseau, AUCUNE clé, AUCUNE écriture de fichier, AUCUN lancement de programme. Interdits : subprocess, socket, requests, urllib, http, shutil, threading, asyncio, importlib, pickle, ctypes, os.system. "
        "Importe le paquet du chercheur DANS produire (pas en haut du fichier). Rends au plus `budget` propositions.\n\n"
        "%s\n"
        "INTERFACE RÉELLE du paquet installé (lue dans son environnement) :\n%s\n\n"
        "%sRéponds avec UN SEUL bloc ```python contenant IMPORTER et produire (et leurs aides), sans explication."
        % (rep["nom"], quoi, json.dumps(api, ensure_ascii=False, indent=1)[:9000] if api else "(aucun paquet)", ("TA VERSION PRÉCÉDENTE A ÉCHOUÉ : %s\nVoici ton code précédent ; corrige CETTE erreur précise (lis l'interface réelle du paquet : un nom de champ ou de méthode deviné est la cause la plus fréquente) :\n```python\n%s\n```\n\n" % (erreur, precedent[:6000])) if erreur else ""))


_CONTEXTE_BLANC = {"point": "controle.essai", "source_reference": "def f(x):\n    return sorted(x)[0]\n", "fonction": "f", "contrat": {}, "entrees": [[3, 1, 2], [9, 4]], "tombes": [], "budget": 2, "seuils": {}, "controle": True}
_REPONSE_BLANCHE = "Idée : prendre le minimum directement.\n```python\ndef f(x):\n    return min(x)\n```"


def generer(entree: dict, rep: dict, python, racine, etape, appeler_modele, executer, adaptateurs: Path, bac: str = "auto", essais: int = 3, mot=None) -> dict:
    """Écrit, vérifie et éprouve l'adaptateur d'un chercheur. Rend {empreinte, code} ; lève InstallationRefusee avec la raison dite."""
    module = str(entree["adaptateur"])
    api = sonder(python, rep.get("importer") or [], executer)
    erreurs = [a for a in api if a.get("erreur")]
    if erreurs and rep.get("importer"):
        etape("adaptateur généré", False, "le paquet ne se charge pas pour être lu : %s" % erreurs[0]["erreur"])
        raise InstallationRefusee("paquet illisible")
    exemple = _exemple(Path(adaptateurs))
    erreur, precedent = "", ""
    code, empreinte = "", ""
    for tentative in range(1, int(essais) + 1):
        try:
            texte = appeler_modele(prompt(rep, api, exemple, erreur, precedent), "strategie")
        except Exception as e:
            etape("adaptateur généré", False, "aucun modèle n'a répondu : %s" % str(e)[:160])
            raise InstallationRefusee("pas de modèle pour écrire l'adaptateur")
        brut = extraire_code(texte)
        raison = verifier_operateur(brut, rep)
        code = assembler(brut) if not raison else brut
        raison = raison or verifier_code(code)
        if raison:
            erreur, precedent = raison, brut
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
        raison = essai_a_blanc(entree, python, module, bac, mot, rep.get("memoire_mo"))
        if raison:
            erreur, precedent = raison, brut
            fichier.unlink(missing_ok=True)
            try:
                (Path(racine).parent / ("rejet_%s.txt" % module)).write_text("# rejeté à l'essai à blanc : %s\n# code :\n%s\n" % (raison, brut), encoding="utf-8")
            except OSError:
                pass
            continue
        etape("adaptateur généré", True, "écrit d'après l'interface du paquet (essai %d), essai à blanc réussi dans la cage · empreinte %s…" % (tentative, empreinte[:12]))
        return {"empreinte": empreinte, "code": code}
    etape("adaptateur généré", False, "rejeté après %d essai(s) : %s" % (essais, erreur))
    raise InstallationRefusee("adaptateur rejeté")


def _site_packages(python, executer) -> str:
    code, sortie = executer([str(python), "-I", "-c", "import site; print(site.getsitepackages()[0])"], 60.0, None)
    chemin = (sortie.strip().splitlines() or [""])[-1].strip()
    return chemin if code == 0 and chemin and Path(chemin).is_dir() else ""


def essai_a_blanc(entree: dict, python, module: str, bac: str = "auto", mot=None, memoire_mo=None) -> str:
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
        plus = {"memoire_mo": int(memoire_mo)} if memoire_mo else {}                      # un chercheur qui charge torch ne tient pas dans le plafond de mémoire par défaut
        m = mot.MoteurProcessus("adaptateur:" + module, appeler_modele=faux, python=str(python), bac=bac, delai_s=90, nom="essai-a-blanc", **plus)
        r = m.proposer(dict(_CONTEXTE_BLANC))
    except Exception as e:
        return "l'essai à blanc a échoué : %s : %s" % (type(e).__name__, str(e)[:240])
    if not isinstance(r, list):
        return "l'adaptateur n'a pas rendu une liste"
    if not r:                                                                      # le faux modèle propose une variante équivalente et plus simple : un adaptateur qui fonctionne en rend au moins une (une liste vide cache un échec avalé en silence)
        return "l'adaptateur n'a rendu aucune variante à l'essai à blanc, alors que le faux modèle en proposait une valable : il échoue sans le dire"
    return ""
# ▲▲▲ FIN BORNE CN ▲▲▲
# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════
# EC : néant (la garde ne s'évolue pas).
# CN : le repli des adaptateurs : écrit, vérifié sans être exécuté, éprouvé dans la cage, épinglé, puis relu par l'admin avant toute activation.
# LIEN : noyau/CN_installateur.py (qui l'appelle), orfan/adaptateurs/ (ceux écrits à la main, toujours prioritaires), orfan/CN_moteur_hote.py (l'hôte).
