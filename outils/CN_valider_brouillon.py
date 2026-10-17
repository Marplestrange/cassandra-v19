#!/usr/bin/env python3
"""CN_valider_brouillon.py <id> : la validation MÉCANIQUE d'un brouillon de portage (.porte/<id>/), sans le copier ni le lire en entier.

Rend : manifeste chargé ?, syntaxe, garde-fous (grep), bancs (copiés dans un dossier temporaire avec le module, pour ne rien déposer dans modules/).
Un brouillon qui passe n'est PAS bon pour autant : il faut le relire. Cela dit seulement s'il vaut la peine d'être relu.
"""
import ast
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_manifeste as mf  # noqa: E402

GARDE_FOUS = [
    (r"subprocess|os\.system|shell=True", "appel système"),
    (r"threading|Thread\(", "thread (interdit : un moteur)"),
    (r"sqlite3", "sqlite3 direct (ctx.stockage)"),
    (r"(^|[^\w])/(var|etc|root|home|usr|opt)/", "chemin en dur"),
    (r"^\s*(from|import)\s+(modules|noyau)\b", "import entre modules"),
    (r"time\.sleep\(\s*[1-9]", "sleep long"),
    (r"password|mot_de_passe|api_key|secret", "mot sensible (vérifier le masque)"),
]


def main(mid):
    d = RACINE / ".porte" / mid
    man = d / "modules" / mid / "CN_manifeste.toml"
    code = d / "modules" / mid / "CN_module.py"
    out = []
    m = None
    try:
        m = mf.charger(man)
        out.append("manifeste OK : %d capacités (%d écrivent), %d moteurs, %d détecteurs, %d réglages, %d droits"
                   % (len(m.capacites), sum(1 for c in m.capacites if c.ecrit), len(m.moteurs), len(m.detecteurs), len(m.reglages), len(m.droits)))
        sans_droit = [c.id for c in m.capacites if c.ecrit and not c.droit]
        if sans_droit:
            out.append("  ! écritures sans droit : %s" % ", ".join(sans_droit))
    except mf.ManifesteInvalide as ex:
        out.append("MANIFESTE INVALIDE : " + " | ".join(ex.erreurs)[:600])
    except OSError as ex:
        out.append("manifeste absent : %s" % ex)
        print("\n".join(out))
        return 1
    try:
        arbre = ast.parse(code.read_text(encoding="utf-8"))
        out.append("syntaxe OK (%d lignes)" % len(code.read_text(encoding="utf-8").splitlines()))
        impl = {n.args[0].value for n in ast.walk(arbre) if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "implementer" and n.args and isinstance(n.args[0], ast.Constant)}
        manque = [c.id for c in m.capacites if c.id not in impl] if m else []
        if manque:
            out.append("  ! déclarées mais non implémentées : %s" % ", ".join(manque))
    except SyntaxError as ex:
        out.append("SYNTAXE : %s" % ex)
    texte = code.read_text(encoding="utf-8")
    for motif, nom in GARDE_FOUS:
        n = len(re.findall(motif, texte, re.M | re.I))
        if n:
            out.append("  garde-fou « %s » : %d" % (nom, n))
    test = d / "tests" / ("CN_test_%s.py" % mid)
    if test.exists():
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            shutil.copytree(RACINE / "modules", t / "modules")
            shutil.copytree(d / "modules" / mid, t / "modules" / mid, dirs_exist_ok=True)
            shutil.copytree(RACINE / "tests", t / "tests", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copy(RACINE / "CN_main.py", t / "CN_main.py")
            shutil.copytree(RACINE / "noyau", t / "noyau")
            shutil.copy(test, t / "tests" / test.name)
            r = subprocess.run([sys.executable, "-m", "unittest", test.stem], cwd=t / "tests", capture_output=True, text=True, encoding="utf-8", errors="replace")
        fin = [l for l in (r.stderr or "").splitlines() if l.startswith(("Ran ", "OK", "FAILED")) or l.startswith(("FAIL:", "ERROR:"))]
        out.append("bancs : " + " | ".join(fin[:8]))
    else:
        out.append("pas de bancs")
    notes = d / "CN_NOTES.md"
    if notes.exists():
        out.append("notes de l'auteur : %d lignes (%s)" % (len(notes.read_text(encoding="utf-8").splitlines()), notes))
    print("\n".join(out))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]) or 0)
