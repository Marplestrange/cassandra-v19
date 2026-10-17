#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Renommage atomique : le préfixe CN_ sur tous les fichiers du projet
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #0d19bf
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : donne le préfixe CN_ à chaque fichier suivi (hors noms imposés de l'extérieur) et réécrit toutes les références.
# MÉTHODE    : plan complet d'abord ; imports Python réécrits par l'arbre syntaxique (alias gardé : le corps du code ne change pas) ; chaînes réécrites par règles ; contrôle des résidus.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=0d19bf ▼▼▼
"""Renommage atomique (docs/FORMAT.md §3 bis et §8). Usage :
    python outils/CN_renommer.py                         SIMULATION : plan, nombre de références réécrites par règle, résidus ; n'écrit rien
    python outils/CN_renommer.py --racine DOSSIER        travaille sur une copie du dépôt (à essayer d'abord)
    python outils/CN_renommer.py --appliquer             renomme (git mv) et réécrit
    python outils/CN_renommer.py --residus               contrôle seulement : une ancienne référence subsiste-t-elle ?

Règles de réécriture
  1. imports Python : par l'arbre syntaxique ; « from noyau import base » devient « from noyau import CN_base as base » (le nom local ne change pas) ;
  2. noms dotés d'une extension (module.py, manifeste.toml, installer.sh…) : remplacés partout, sauf dans les fichiers servis de interface/ (le serveur retire le préfixe) ;
  3. noms dotés (« tests.test_vue », « noyau.contexte ») : remplacés dans toute chaîne ;
  4. programmes racine (commandes/) et unités système (exploitation/*.service) : seulement les références QUALIFIÉES par leur dossier (« commandes/confiner ») : le nom installé,
     lui, ne change jamais (docs/FORMAT.md §3 bis) ;
  5. « unittest discover -s tests » reçoit le motif des tests renommés.
Les documents de la règle (NEXUS, FORMAT, BORNES, EVOLUTION) et cet outil ne sont pas réécrits : ils décrivent le renommage.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import CN_bornes as B  # noqa: E402

NOMS_IMPOSES = set(B.NOMS_IMPOSES) | {".gitattributes", ".gitignore"}
PREFIXES = ("CN_", "EC_")
TEXTE = {".py", ".sh", ".md", ".toml", ".js", ".html", ".css", ".json", ".sql", ".yml", ".yaml", ".service", ".path", ".in", ".txt", ".borne", ".exemple", ".conf", ""}
NON_REECRITS = {"docs/NEXUS.md", "docs/FORMAT.md", "docs/BORNES.md", "docs/EVOLUTION.md", "outils/CN_renommer.py", "tests/test_renommer.py"}
SERVIS = "interface/"                                    # fichiers servis : le serveur retire le préfixe, les références par URL ne changent pas
MOTIF_TESTS = 'unittest discover -s tests'
RE_URL = re.compile(r"https?://[^\s\"')>]+")


def fichiers(racine: Path) -> list[str]:
    if (racine / ".git").exists():
        try:
            s = subprocess.run(["git", "ls-files"], cwd=racine, capture_output=True, text=True, check=True).stdout
            return [l for l in s.splitlines() if l and (racine / l).is_file()]
        except Exception:
            pass
    out = []
    for r, ds, fs in os.walk(racine):
        ds[:] = [d for d in ds if d not in {".git", "__pycache__"}]
        out += [str(Path(r, f).relative_to(racine)).replace(os.sep, "/") for f in fs]
    return out


def nouveau_nom(chemin: str) -> str | None:
    p = Path(chemin)
    n = p.name
    if n in NOMS_IMPOSES or n.startswith(PREFIXES) or "__pycache__" in p.parts or ".git" in p.parts:
        return None
    return str(p.with_name("CN_" + n)).replace(os.sep, "/")


def plan(racine: Path) -> dict[str, str]:
    tout = fichiers(racine)
    carte = {}
    for c in tout:
        if c.endswith(".borne"):
            continue
        n = nouveau_nom(c)
        if n:
            carte[c] = n
    for c in tout:                                       # un compagnon suit son fichier
        if c.endswith(".borne"):
            base = c[:-6]
            if base in carte:
                carte[c] = carte[base] + ".borne"
            elif nouveau_nom(c) and not Path(c).name.startswith(PREFIXES):
                carte[c] = nouveau_nom(c)
    return carte


def est_qualifie(chemin: str) -> bool:
    """Un fichier dont le nom nu a un autre sens sur la machine (programme racine, unité système) : seules ses références qualifiées sont réécrites."""
    return "/commandes/" in "/" + chemin or (chemin.startswith("exploitation/") and chemin.endswith((".service", ".path")))


def dotted(chemin: str) -> str:
    return chemin[:-3].replace("/", ".") if chemin.endswith(".py") else ""


class Reecriture:
    def __init__(self, racine: Path, carte: dict[str, str]):
        self.racine, self.carte = racine, carte
        self.py = {c: n for c, n in carte.items() if c.endswith(".py")}
        self.dotted = {dotted(c): dotted(n) for c, n in self.py.items() if "." in dotted(c)}      # un nom à un seul segment (« main ») est un mot de la prose : seuls les imports le réécrivent
        stems: dict[str, list[str]] = {}
        for c in self.py:
            stems.setdefault(Path(c).stem, []).append(c)
        self.stems_uniques = {s: v[0] for s, v in stems.items() if len(v) == 1 and s not in sys.stdlib_module_names and s != "__init__"}
        libres, qualifies = {}, {}
        for c, n in carte.items():
            if c.endswith(".borne"):
                continue
            b, nb = Path(c).name, Path(n).name
            if est_qualifie(c):
                qualifies[c.rsplit("/", 2)[-2] + "/" + b if c.count("/") >= 1 else b] = c.rsplit("/", 2)[-2] + "/" + nb
            elif "." in b and not c.startswith(SERVIS) and not b.endswith(".sql"):      # une migration garde son identité sans préfixe : ses noms dans les chaînes ne changent pas
                libres[b] = nb
        self.libres, self.qualifies = libres, qualifies
        self.re_libres = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(libres, key=len, reverse=True)) + r")(?![\w])") if libres else None
        self.re_qualifies = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(qualifies, key=len, reverse=True)) + r")(?![\w])") if qualifies else None
        self.re_dotted = re.compile(r"(?<![\w.])(" + "|".join(re.escape(k) for k in sorted(self.dotted, key=len, reverse=True)) + r")(?![\w])") if self.dotted else None
        self.stats: dict[str, int] = {}

    def _n(self, regle: str, k: int = 1):
        self.stats[regle] = self.stats.get(regle, 0) + k

    # ── 1. les imports Python ────────────────────────────────────────────
    def _resoudre(self, nom_dotted: str):
        """Le chemin du fichier .py désigné par un nom pointé, ou None."""
        c = nom_dotted.replace(".", "/") + ".py"
        if c in self.py:
            return c
        if "." not in nom_dotted and nom_dotted in self.stems_uniques:
            return self.stems_uniques[nom_dotted]
        return None

    def imports(self, chemin: str, source: str) -> str:
        try:
            arbre = ast.parse(source)
        except SyntaxError:
            return source
        paquet = str(Path(chemin).parent).replace(os.sep, "/").replace("/", ".") if "/" in chemin else ""
        remplacements = []
        for n in ast.walk(arbre):
            if isinstance(n, ast.ImportFrom):
                base = n.module or ""
                if n.level:
                    parts = paquet.split(".") if paquet else []
                    parts = parts[:len(parts) - (n.level - 1)] if n.level > 1 else parts
                    absolu = ".".join(parts + ([base] if base else []))
                else:
                    absolu = base
                nouveau_module = n.module
                if absolu and (f := self._resoudre(absolu)) and f in self.py:
                    feuille = Path(f).stem
                    if base.split(".")[-1] == feuille:
                        nouveau_module = ".".join(base.split(".")[:-1] + ["CN_" + feuille]) if base else None
                noms = []
                change = nouveau_module != n.module
                for a in n.names:
                    sous = self._resoudre((absolu + "." + a.name) if absolu else a.name)
                    if sous and sous in self.py and a.name != "*":
                        alias = a.asname or a.name
                        noms.append("CN_%s as %s" % (a.name, alias))
                        change = True
                    else:
                        noms.append(a.name + ((" as " + a.asname) if a.asname else ""))
                if change:
                    nm = ("." * n.level) + (nouveau_module or "")
                    remplacements.append((n, "from %s import %s" % (nm, ", ".join(noms))))
            elif isinstance(n, ast.Import):
                noms, change = [], False
                for a in n.names:
                    f = self._resoudre(a.name)
                    if f and f in self.py and Path(f).stem == a.name.split(".")[-1]:
                        feuille = a.name.split(".")[-1]
                        nouveau = ".".join(a.name.split(".")[:-1] + ["CN_" + feuille])
                        if a.asname:
                            noms.append("%s as %s" % (nouveau, a.asname))
                        elif "." not in a.name:
                            noms.append("%s as %s" % (nouveau, a.name))
                        else:
                            noms.append(nouveau)
                        change = True
                    else:
                        noms.append(a.name + ((" as " + a.asname) if a.asname else ""))
                if change:
                    remplacements.append((n, "import " + ", ".join(noms)))
        if not remplacements:
            return source
        lignes = source.split("\n")
        for n, texte in sorted(remplacements, key=lambda r: (r[0].lineno, r[0].col_offset), reverse=True):
            debut, fin = n.lineno - 1, n.end_lineno - 1
            avant = lignes[debut][:n.col_offset]
            apres = lignes[fin][n.end_col_offset:]
            lignes[debut:fin + 1] = [avant + texte + apres]
            self._n("imports Python")
        return "\n".join(lignes)

    def _regles(self, s: str) -> str:
        if self.re_libres:                                 # le contenu d'une unité ou d'un programme racine référence bien des fichiers du dépôt (main.py) : ses propres noms, eux, ne sont pas dans cette liste
            s, k = self.re_libres.subn(lambda m: self.libres[m.group(1)], s)
            self._n("noms avec extension", k)
        if self.re_qualifies:
            s, k = self.re_qualifies.subn(lambda m: self.qualifies[m.group(1)], s)
            self._n("références qualifiées (commandes/, exploitation/)", k)
        s, k = re.subn(r"commandes/(\$\{?[A-Za-z_]\w*\}?)", r"commandes/CN_\1", s)
        self._n("références de commandes en boucle (shell)", k)
        s, k = re.subn(r'("commandes"\s*/\s*)"([A-Za-z_]\w*)"', r'\1"CN_\2"', s)             # RACINE / "modules" / "urgence" / "commandes" / "confiner" (un chemin bâti par morceaux)
        self._n("chemins de commandes bâtis par morceaux (Python)", k)
        s, k = re.subn(r"(\./)(\$\{?[A-Za-z_]\w*\}?\.sh)", r"\1CN_\2", s)                    # bash ./$ACTION.sh : un script dont le nom est bâti par une variable
        self._n("scripts dont le nom est bâti par une variable (shell)", k)
        if self.re_dotted:
            s, k = self.re_dotted.subn(lambda m: self.dotted[m.group(1)], s)
            self._n("noms pointés de modules", k)
        return s

    # ── 2 à 5. les chaînes ───────────────────────────────────────────────
    def textes(self, chemin: str, source: str) -> str:
        if chemin.startswith(SERVIS) and chemin.endswith((".js", ".css", ".html")):
            return source                                  # servis : les URL gardent leur nom, le serveur retire le préfixe
        morceaux, urls = RE_URL.split(source), RE_URL.findall(source)     # une adresse web (ollama.com/install.sh) n'est pas un fichier du dépôt : on n'y touche pas
        sortie = []
        for i, m in enumerate(morceaux):
            sortie.append(self._regles(m))
            if i < len(urls):
                sortie.append(urls[i])
        s = "".join(sortie)
        if MOTIF_TESTS in s and "-p " not in s.split(MOTIF_TESTS, 1)[1][:30]:
            s = s.replace(MOTIF_TESTS, MOTIF_TESTS + ' -p "CN_test*.py"')
            self._n("motif de découverte des tests")
        return s

    def tout(self) -> dict[str, str]:
        """Le nouveau contenu de chaque fichier texte modifié, indexé par son ANCIEN chemin."""
        out = {}
        for c in fichiers(self.racine):
            if c in NON_REECRITS or Path(c).suffix not in TEXTE:
                continue
            try:
                src = (self.racine / c).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            s = self.imports(c, src) if c.endswith(".py") else src
            s = self.textes(c, s)
            if s != src:
                out[c] = s
        return out


def residus(racine: Path, carte: dict[str, str] | None = None) -> list[str]:
    """Ce qui subsiste d'une ancienne référence après le renommage : un oubli à corriger."""
    carte = carte if carte is not None else plan(racine)
    out = [f"fichier sans préfixe : {c}" for c in fichiers(racine) if nouveau_nom(c) and not c.endswith(".borne")]
    return out


def principal(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = argv[1:]
    racine = Path(args[args.index("--racine") + 1]).resolve() if "--racine" in args else B.RACINE
    if "--residus" in args:
        r = residus(racine, {})
        print("\n".join(r) if r else "aucun résidu")
        return 1 if r else 0
    carte = plan(racine)
    rew = Reecriture(racine, carte)
    contenus = rew.tout()
    print(f"{len(carte)} fichier(s) à renommer ; {len(contenus)} fichier(s) dont le contenu change.")
    for regle, k in sorted(rew.stats.items()):
        print(f"   {k:>6}  {regle}")
    if "--appliquer" not in args:
        print("(simulation : rien n'est écrit ; --appliquer pour renommer)")
        return 0
    git = (racine / ".git").exists()
    for c, s in contenus.items():
        (racine / c).write_text(s, encoding="utf-8", newline="\n")
    for ancien, neuf in sorted(carte.items()):
        cible = racine / neuf
        cible.parent.mkdir(parents=True, exist_ok=True)
        if git:
            subprocess.run(["git", "mv", ancien, neuf], cwd=racine, check=True, capture_output=True)
        else:
            os.replace(racine / ancien, cible)
    print(f"renommé : {len(carte)} fichier(s).")
    r = residus(racine)
    print("\n".join(r) if r else "aucun fichier sans préfixe")
    return 1 if r else 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus (outil du dépôt, jamais évolutif).
# EC : néant. Il renomme et réécrit ; il ne s'exécute qu'une fois, sur demande, après simulation.
# LIEN : docs/FORMAT.md §3 bis et §8 (la règle et la mise en place) ; outils/CN_bornes.py (qui vérifie ensuite le format) ; tests/test_renommer.py.
