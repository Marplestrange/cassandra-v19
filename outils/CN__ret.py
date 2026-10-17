# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Jetable
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #3cc69d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Jetable : affiche les 'return' (et leurs clés) des fonctions V18 nommées. usage: python outils/CN__ret.py f1 f2 ...
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3cc69d ▼▼▼
"""Jetable : affiche les 'return' (et leurs clés) des fonctions V18 nommées. usage: python outils/CN__ret.py f1 f2 ..."""
import ast, sys
SRC = r"C:\Users\Admin\Documents\Cassandra\V18\cassandra.py"
t = ast.parse(open(SRC, encoding="utf-8").read())
want = set(sys.argv[1:])
src = open(SRC, encoding="utf-8").read().split("\n")
for n in ast.walk(t):
    if isinstance(n, ast.FunctionDef) and n.name in want:
        print("==", n.name, "(%s)" % ", ".join(a.arg for a in n.args.args), "L%d" % n.lineno)
        for r in ast.walk(n):
            if isinstance(r, ast.Return) and r.value is not None:
                seg = " ".join(x.strip() for x in src[r.lineno - 1:r.end_lineno])
                print("  ", seg[:230])
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : constantes et configuration
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
