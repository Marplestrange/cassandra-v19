"""Jetable : signatures des capacités d'un module. usage: python outils/CN__sig.py module"""
import ast, sys, tomllib
mod = sys.argv[1]
m = tomllib.load(open("modules/%s/CN_manifeste.toml" % mod, "rb"))
ids = {c["id"] for c in m["capacites"]}
t = ast.parse(open("modules/%s/CN_module.py" % mod, encoding="utf-8").read())
imp = {}
for n in ast.walk(t):
    if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "implementer" and n.args and isinstance(n.args[0], ast.Constant) and len(n.args) > 1:
        imp[n.args[0].value] = getattr(n.args[1], "id", None)
    if isinstance(n, ast.For) and isinstance(n.iter, ast.Tuple):
        for e in n.iter.elts:
            if isinstance(e, ast.Tuple) and len(e.elts) == 2 and isinstance(e.elts[0], ast.Constant) and isinstance(e.elts[1], ast.Name):
                imp.setdefault(e.elts[0].value, e.elts[1].id)
fn = {n.name: n for n in ast.walk(t) if isinstance(n, ast.FunctionDef)}
for k in [c["id"] for c in m["capacites"]]:
    f = fn.get(imp.get(k) or k)
    if not f:
        print(k, "?"); continue
    a = f.args; names = [x.arg for x in a.args][1:]; d = [ast.unparse(x) for x in a.defaults]
    off = len(names) - len(d)
    print(k, "(", ", ".join(n + ("=" + d[i - off] if i >= off else "") for i, n in enumerate(names)), ")")
