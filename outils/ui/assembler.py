"""Assemble l'interface V19 à partir de l'extraction brute de l'interface V18.

usage : python outils/ui/assembler.py [docs/v18/interface_v18.html] [interface/]

Extraction pure : on ne réécrit rien, on découpe l'unique fichier V18 en
index.html + style.css + app.js, on remplace les marqueurs de version, et on
insère compat.js AVANT app.js (le pont V18 -> noyau V19, voir interface/compat.js).
Les découpes se font sur les balises de PREMIER niveau : les <style> et </script>
qui vivent dans des chaînes JS ne comptent pas.
"""
import os
import re
import sys

VERSION = "19.0"
CDN_SCRIPTS = re.compile(r'<script src="https://[^"]+"></script>\s*')


def decouper(h):
    tete_debut = h.index("<head>") + len("<head>")
    tete_fin = h.index("</head>")
    tete = h[tete_debut:tete_fin]
    # feuilles de style de premier niveau dans la tête
    css = []
    pos = 0
    while True:
        a = tete.find("<style>", pos)
        if a < 0:
            break
        b = tete.index("</style>", a)
        css.append(tete[a + 7:b])
        pos = b + 8
    # le <script> principal du corps : le premier <script> sans src après <body>
    corps_debut = h.index("<body>") + len("<body>")
    s_debut = h.index("<script>", corps_debut)
    s_fin = h.index("</script>", s_debut + 8)
    # le script est unique ; un second </script> dans une chaîne JS serait déjà coupé : on contrôle
    reste = h[s_fin + 9:h.rindex("</body>")]
    if "<script>" in reste.split("<div")[0]:
        raise SystemExit("un second <script> de premier niveau : découpe à revoir")
    js = h[s_debut + 8:s_fin]
    marque = h[corps_debut:s_debut]
    # tête sans styles ni scripts : liens, polices, manifest
    liens = re.sub(r"<style>.*?</style>", "", tete, flags=re.S)
    liens = CDN_SCRIPTS.sub("", liens)
    liens = re.sub(r"<meta (charset|name=\"viewport\")[^>]*>\s*", "", liens)
    scripts_cdn = CDN_SCRIPTS.findall(tete)
    return {"liens": liens.strip(), "scripts_cdn": [s.strip() for s in scripts_cdn],
            "css": "\n".join(css), "corps": marque + reste, "js": js}


def versionner(t, build):
    return t.replace("__CASSANDRA_VERSION__", VERSION).replace("__BUILD__", build)


def assembler(src, sortie):
    h = open(src, encoding="utf-8").read()
    d = decouper(h)
    build = "v19-extrait"
    os.makedirs(sortie, exist_ok=True)
    open(os.path.join(sortie, "style.css"), "w", encoding="utf-8", newline="\n").write(versionner(d["css"], build))
    open(os.path.join(sortie, "app.js"), "w", encoding="utf-8", newline="\n").write(versionner(d["js"], build))
    html = ["<!doctype html>", '<html lang="fr">', "<head>", '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
            d["liens"]]
    html += d["scripts_cdn"]
    html += ['<link rel="stylesheet" href="/style.css">', '<link rel="stylesheet" href="/shell.css">', "</head>", "<body>"]
    html.append(versionner(d["corps"], build))
    html.append('<script src="/compat.js"></script>')
    rdir = os.path.join(sortie, "routes")
    if os.path.isdir(rdir):
        html += ['<script src="/routes/%s"></script>' % f for f in sorted(os.listdir(rdir)) if f.endswith(".js")]
    html += ['<script src="/app.js"></script>', '<script src="/shell.js"></script>', "</body>", "</html>"]
    open(os.path.join(sortie, "index.html"), "w", encoding="utf-8", newline="\n").write("\n".join(html))
    return {k: len(v) for k, v in d.items() if isinstance(v, str)}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "docs/v18/interface_v18.html"
    sortie = sys.argv[2] if len(sys.argv) > 2 else "interface"
    print(assembler(src, sortie))
