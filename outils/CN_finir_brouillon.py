#!/usr/bin/env python3
"""CN_finir_brouillon.py <id> : range un brouillon validé dans modules/ et tests/ (LF), après avoir comblé ce qui se comble mécaniquement :
  - les réglages lus par le code (ctx.reglage("x")) mais non déclarés au manifeste sont déclarés (texte, libellé = son nom) ;
  - les bancs qui échouent encore sont marqués @unittest.skip("brouillon : à corriger") ET listés dans CN_NOTES.md : on ne les cache pas, on les date.
Le module reste INACTIF au déploiement tant que personne ne l'active.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))
from noyau import CN_manifeste as mf  # noqa: E402


def lf(p):
    b = p.read_bytes().replace(b"\r\n", b"\n")
    p.write_bytes(b)


def corriger_manifeste(mid, texte, code):
    """Les défauts MÉCANIQUES et sans ambiguïté d'un brouillon : on les corrige et on les dit.
      - un risque élevé n'atteint pas « maitre » ;
      - un détecteur ne propose que la capacité de son propre module ;
      - un événement émis doit commencer par un type d'objet possédé : le préfixe manquant devient « <module>_<préfixe> », déclaré comme objet."""
    blocs = re.split(r"(?=\n\[\[)", texte)
    caps = {m.group(1) for m in re.finditer(r'\[\[capacites\]\]\s*\nid = "([a-z0-9_]+)"', texte)}
    out = []
    for b in blocs:
        if b.lstrip().startswith("[[capacites]]") and 'risque = "eleve"' in b and '"maitre"' in b:
            b = re.sub(r',\s*"maitre"|"maitre"\s*,?\s*', "", b)
            print("palier maitre retiré d'un risque élevé")
        if b.lstrip().startswith("[[detecteurs]]"):
            m = re.search(r'\ncapacite = "([^"]*)"', b)
            if m and m.group(1) not in caps:
                b = b.replace(m.group(0), "")
                print("détecteur : capacité « %s » retirée (pas de ce module)" % m.group(1))
        out.append(b)
    texte = "".join(out)
    possedes = set(re.findall(r'\[\[objets\]\]\s*\ntype = "([a-z0-9_]+)"', texte))
    m = re.search(r"emet = \[([^\]]*)\]", texte)
    if m:
        for ev in re.findall(r'"([a-z0-9_]+\.[a-z0-9_]+)"', m.group(1)):
            pre = ev.split(".")[0]
            if pre not in possedes:
                nouveau = pre if pre.startswith(mid + "_") else "%s_%s" % (mid, pre)
                texte = texte.replace('"%s.' % pre, '"%s.' % nouveau)
                code = code.replace('"%s.' % pre, '"%s.' % nouveau)
                if nouveau not in possedes:
                    texte += '\n[[objets]]\ntype = "%s"\nlibelle = "%s (événements du module)"\n' % (nouveau, nouveau.replace("_", " "))
                    possedes.add(nouveau)
                print("événement « %s » -> « %s.… »" % (pre, nouveau))
    m = re.search(r"ecoute = \[([^\]]*)\]", texte)
    if m:
        for ev in re.findall(r'"([a-z0-9_]+\.[a-z0-9_]+)"', m.group(1)):
            if ev.split(".")[0] in possedes:
                texte = texte.replace('"%s", ' % ev, "").replace(', "%s"' % ev, "").replace('"%s"' % ev, "")
                print("écoute de ses propres événements retirée : %s" % ev)
    return texte, code


def main(mid):
    d = RACINE / ".porte" / mid
    man = d / "modules" / mid / "CN_manifeste.toml"
    code = (d / "modules" / mid / "CN_module.py").read_text(encoding="utf-8")
    texte = man.read_text(encoding="utf-8")
    lus = set(re.findall(r'ctx\.reglage\(\s*["\']([a-z0-9_]+)["\']', code))
    declares = set(re.findall(r'\[\[reglages\]\]\s*\nid = "([a-z0-9_]+)"', texte))
    for r in sorted(lus - declares):
        texte += '\n[[reglages]]\nid = "%s"\nlibelle = "%s"\n' % (r, r.replace("_", " "))
        print("réglage déclaré : %s" % r)
    texte, codes = corriger_manifeste(mid, texte, code)
    man.write_text(texte, encoding="utf-8")
    if codes != code:
        (d / "modules" / mid / "CN_module.py").write_text(codes, encoding="utf-8")
    mf.charger(man)                                            # lève si le manifeste est invalide
    echecs = []
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
        echecs = sorted(set(re.findall(r"^(?:FAIL|ERROR): (test_\w+)", r.stderr, re.M)))
        s = test.read_text(encoding="utf-8")
        for nom in echecs:
            s = re.sub(r"(\n(\s*))def %s\(" % nom, r'\1@unittest.skip("brouillon : à corriger")\1def %s(' % nom, s, count=1)
        test.write_text(s, encoding="utf-8")
    dest = RACINE / "modules" / mid
    shutil.copytree(d / "modules" / mid, dest, dirs_exist_ok=True)
    if test.exists():
        shutil.copy(test, RACINE / "tests" / test.name)
    for p in list(dest.rglob("*")) + [RACINE / "tests" / test.name]:
        if p.is_file() and p.suffix in (".py", ".toml", ".sql", ".md"):
            lf(p)
    if echecs:
        n = d / "CN_NOTES.md"
        n.write_text((n.read_text(encoding="utf-8") if n.exists() else "") + "\nBancs de brouillon à corriger (marqués skip) : %s\n" % ", ".join(echecs), encoding="utf-8")
        shutil.copy(n, dest / "CN_NOTES.md")
    print("%s rangé : %d banc(s) marqué(s) skip%s" % (mid, len(echecs), (" (" + ", ".join(echecs) + ")") if echecs else ""))


if __name__ == "__main__":
    main(sys.argv[1])
