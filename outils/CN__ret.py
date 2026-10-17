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
