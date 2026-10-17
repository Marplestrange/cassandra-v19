#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Générateur d'en-têtes : pose le format universel sur l'existant
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #6e1f68
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : ajoute à chaque fichier existant l'en-tête, la borne CN et l'explicatif du format docs/CN_FORMAT.md, sans toucher au code.
# MÉTHODE    : le titre et le rôle sont repris de l'ancien commentaire ; la méthode reste « à compléter » pour que l'auteur la relise ; simulation par défaut.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=6e1f68 ▼▼▼
"""Générateur d'en-têtes. Usage :
    python outils/CN_entete.py                       simulation : liste ce qui serait fait, n'écrit rien
    python outils/CN_entete.py --ecrire              écrit (un fichier à la fois, puis scelle les empreintes)
    python outils/CN_entete.py --module vue          un seul module
    python outils/CN_entete.py --fichier F           un seul fichier
Ne modifie jamais une ligne de code : il AJOUTE des lignes de commentaire avant et après. Idempotent (un fichier déjà en format est sauté).
Les migrations SQL et le JSON (immuables ou sans commentaires) reçoivent un fichier compagnon « nom.ext.borne ».
"""
from __future__ import annotations

import ast
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import CN_bornes as B  # noqa: E402

RACINE = B.RACINE
GENERES = {"interface/index.html", "interface/app.js", "interface/style.css"}      # produits par l'assembleur : c'est lui qui posera leur en-tête
HORS_V1 = {".html", ".css"}                                                         # doctype, @charset : à traiter à part
VERSION_NOYAU = re.compile(r'VERSION_NOYAU\s*=\s*"([^"]+)"')


def version_de(chemin: str) -> str:
    p = chemin.split("/")
    if p[0] == "modules" and len(p) > 2:
        m = (RACINE / "modules" / p[1] / "CN_manifeste.toml")
        if not m.exists():
            m = RACINE / "modules" / p[1] / "CN_manifeste.toml"
        if m.exists():
            v = re.search(r'^version\s*=\s*"([^"]+)"', m.read_text(encoding="utf-8"), re.M)
            if v:
                return v.group(1)
    f = RACINE / "noyau" / "CN_manifeste.py"
    if f.exists():
        v = VERSION_NOYAU.search(f.read_text(encoding="utf-8"))
        if v:
            return v.group(1)
    return "0.1.0"


def titre_et_role(chemin: str, texte: str) -> tuple[str, str]:
    ext = Path(chemin).suffix
    nom = Path(chemin).name
    brut = re.sub(r"^(CN|EC)_", "", nom)
    titre = role = ""
    if ext == ".py":
        try:
            doc = ast.get_docstring(ast.parse(texte)) or ""
        except SyntaxError:
            doc = ""
        if doc:
            premier = doc.strip().split("\n\n")[0].replace("\n", " ").strip()
            role = premier[:240]
            titre = premier.split(".")[0].split(":")[0].strip()[:90]
    elif ext == ".sh":
        for l in texte.splitlines()[1:12]:
            m = re.match(r"^#\s*(.+)", l)
            if m and not m.group(1).startswith(("!", "─", "═", "-")):
                role = m.group(1).strip()
                titre = role.split(":")[0].strip()[:90]
                break
    elif ext == ".toml":
        n = re.search(r'^nom\s*=\s*"([^"]+)"', texte, re.M)
        d = re.search(r'^description\s*=\s*"([^"]+)"', texte, re.M)
        if n:
            titre = "Manifeste du module " + n.group(1)
            role = d.group(1) if d else titre
    elif ext == ".md":
        m = re.search(r"^#\s+(.+)$", texte, re.M)
        if m:
            titre = m.group(1).strip()[:90]
            role = titre
    elif ext in (".js", ".mjs", ".ts"):
        m = re.search(r"/\*\*?\s*(.+?)(?:\*/|\n)", texte, re.S) or re.match(r"^//\s*(.+)", texte)
        if m:
            role = m.group(1).strip().strip("*").strip()[:240]
            titre = role.split(".")[0][:90]
    if not titre:
        titre = brut
    if not role:
        role = titre
    return titre.replace("\n", " "), role.replace("\n", " ")


def noms_definis(texte: str, ext: str) -> str:
    if ext == ".py":
        try:
            t = ast.parse(texte)
            n = [x.name for x in t.body if isinstance(x, (ast.FunctionDef, ast.ClassDef))]
            return ", ".join(n[:8]) + (" …" if len(n) > 8 else "") if n else "constantes et configuration"
        except SyntaxError:
            return "à compléter"
    return "à compléter"


def entete_pour(chemin: str, texte: str, jeton: str) -> dict:
    module = B.module_de(chemin)
    titre, role = titre_et_role(chemin, texte)
    ext = Path(chemin).suffix
    ferme = {"<!--": " -->", "/*": " */"}.get(jeton, "")
    def l(txt): return f"{jeton} {txt}{ferme}" if txt else f"{jeton}{ferme}"
    barre = jeton + " " + "═" * 78 + ferme
    champs = [("TITRE", titre), ("LICENCE", "AGPL-3.0"), ("AUTEUR", "Atek Drisse"), ("GIT", "github.com/Marplestrange"), ("MAIL", "marplestrange@cassandra.center"),
              ("MODULE", module), ("ZONE", "CN"), ("VERSION CN", version_de(chemin) + "  #000000"), ("VERSION EC", "néant"), ("EC LIÉES", "néant"),
              ("RÔLE", role), ("MÉTHODE", "à compléter par l'auteur (comment le fichier s'y prend)")]
    tete = [barre] + [l(f"{k:<10} : {v}") for k, v in champs] + [barre]
    ouvre = l("▼▼▼ BORNE CN version=" + version_de(chemin) + " empreinte=000000 ▼▼▼")
    ferme_b = l("▲▲▲ FIN BORNE CN ▲▲▲")
    expl = [l("═══ EXPLICATIF CN / EC " + "═" * 55),
            l("CN : tout ce fichier est du nexus : " + noms_definis(texte, ext)),
            l("EC : néant (aucun point d'évolution déclaré pour l'instant)"),
            l("LIEN : à compléter (contrat, fichiers voisins)")]
    return {"tete": tete, "ouvre": ouvre, "ferme": ferme_b, "expl": expl, "module": module}


def est_en_format(texte: str) -> bool:
    """Déjà au format : un en-tête (TITRE) dans les soixante premières lignes ET une vraie ligne de marqueur de borne."""
    lignes = texte.splitlines()
    a_titre = any(re.match(r"^\s*(#|//|;;|--|/\*|<!--)\s*TITRE\s*:", l) for l in lignes[:60])
    a_borne = any((m := B.marqueur(l)) and m.startswith(("BORNE CN", "BORNE EC")) for l in lignes)
    return a_titre and a_borne


def transformer(chemin: str, texte: str) -> str | None:
    ext = Path(chemin).suffix
    jeton = B.COMMENTAIRE.get(ext)
    if jeton is None or est_en_format(texte):
        return None
    lignes = texte.replace("\r\n", "\n").split("\n")
    prefixe = []
    while lignes and (lignes[0].startswith("#!") or re.match(r"^#.*coding[:=]", lignes[0])):
        prefixe.append(lignes.pop(0))
    while lignes and lignes[-1] == "":
        lignes.pop()
    e = entete_pour(chemin, texte, jeton)
    sortie = prefixe + e["tete"] + [e["ouvre"]] + lignes + [e["ferme"], ""] + e["expl"]
    return "\n".join(sortie) + "\n"


def cibles(module: str | None, fichier: str | None) -> list[str]:
    tous = [fichier] if fichier else [c for c in B.fichiers_suivis() if (RACINE / c).is_file()]
    out = []
    for c in tous:
        nom = Path(c).name
        if nom in B.NOMS_IMPOSES or c in GENERES or any(p in B.IGNORER_DOSSIERS for p in Path(c).parts):
            continue
        if module and B.module_de(c) != module:
            continue
        out.append(c)
    return out


def compagnon(chemin: str) -> str:
    """Fichier compagnon pour un fichier sans commentaires possibles (JSON, migration SQL immuable, binaire)."""
    donnees = (RACINE / chemin).read_bytes()
    emp = hashlib.sha256(donnees.replace(b"\r\n", b"\n")).hexdigest()[:6]
    module = B.module_de(chemin)
    brut = re.sub(r"^(CN|EC)_", "", Path(chemin).name)
    titre = ("Migration " + brut) if chemin.endswith(".sql") else brut
    champs = [("TITRE", titre), ("LICENCE", "AGPL-3.0"), ("AUTEUR", "Atek Drisse"), ("GIT", "github.com/Marplestrange"), ("MAIL", "marplestrange@cassandra.center"),
              ("MODULE", module), ("ZONE", "CN"), ("VERSION CN", version_de(chemin) + "  #" + emp), ("VERSION EC", "néant"), ("EC LIÉES", "néant"),
              ("RÔLE", titre + " (fichier sans commentaires possibles ou immuable : en-tête porté ici)"), ("MÉTHODE", "à compléter par l'auteur")]
    return "\n".join(["# " + "═" * 78] + [f"# {k:<10} : {v}" for k, v in champs] + ["# " + "═" * 78, f"# FICHIER    : {Path(chemin).name}  (empreinte du contenu #{emp})", ""])


def principal(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = argv[1:]
    module = args[args.index("--module") + 1] if "--module" in args else None
    fichier = args[args.index("--fichier") + 1] if "--fichier" in args else None
    ecrire = "--ecrire" in args
    faits = sautes = compagnons = 0
    for c in cibles(module, fichier):
        ext = Path(c).suffix
        if ext in B.SANS_COMMENTAIRE:
            cpg = RACINE / (c + ".borne")
            if cpg.exists():
                sautes += 1
                continue
            compagnons += 1
            if ecrire:
                cpg.write_text(compagnon(c), encoding="utf-8", newline="\n")
            else:
                print("compagnon :", c)
            continue
        if ext in HORS_V1 or ext not in B.COMMENTAIRE:
            sautes += 1
            continue
        texte = B.lire(c)
        if texte is None:
            sautes += 1
            continue
        neuf = transformer(c, texte)
        if neuf is None:
            sautes += 1
            continue
        if ext == ".py":                                  # la preuve : l'arbre syntaxique est IDENTIQUE avant et après (seuls des commentaires ont été ajoutés)
            try:
                if ast.dump(ast.parse(texte)) != ast.dump(ast.parse(neuf)):
                    print("REFUSÉ (le code aurait changé) :", c)
                    sautes += 1
                    continue
            except SyntaxError:
                print("REFUSÉ (syntaxe illisible) :", c)
                sautes += 1
                continue
        faits += 1
        if ecrire:
            (RACINE / c).write_text(neuf, encoding="utf-8", newline="\n")
            B.sceller(c)
        else:
            print("en-tête   :", c)
    verbe = "écrits" if ecrire else "à écrire"
    print(f"\n{faits} fichier(s) {verbe}, {compagnons} compagnon(s) {verbe}, {sautes} sauté(s) (déjà en format, hors v1 ou exempts).")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus (outil du dépôt, jamais évolutif).
# EC : néant. Il ne modifie jamais une ligne de code, il ajoute des commentaires avant et après.
# LIEN : docs/CN_FORMAT.md ; outils/CN_bornes.py (qui vérifie ce qu'il génère et scelle les empreintes).
