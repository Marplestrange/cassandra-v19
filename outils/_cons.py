"""Jetable : les clés lues sur la réponse d'une route dans app.js. usage: python outils/_cons.py /api/x [/api/y ...]"""
import re, sys
s = open("interface/app.js", encoding="utf-8").read().split("\n")
for r in sys.argv[1:]:
    for i, l in enumerate(s):
        if ("'" + r + "'") in l or ('"' + r + '"') in l:
            v = re.search(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:await\s+)?(?:apiPost|apiGet)", l) or re.search(r"(\w+)\s*=\s*await\s+api(?:Post|Get)", l)
            nom = v.group(1) if v else "d"
            blob = "\n".join(s[i:i + 45])
            ks = sorted(set(re.findall(r"\b" + nom + r"\.([a-zA-Z_]\w*)", blob)))
            print(r, "(var %s, l.%d):" % (nom, i + 1), " ".join(ks)[:300])
            break
