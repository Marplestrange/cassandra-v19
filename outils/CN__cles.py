"""Jetable : forme (clés) du résultat d'une capacité du serveur local. usage: python outils/CN__cles.py cap '{"args"}' [profondeur]"""
import json, os, sys, urllib.request
T = open(os.path.join(os.environ["TEMP"], "tok")).read().strip()
cap, args, prof = sys.argv[1], json.loads(sys.argv[2] if len(sys.argv) > 2 else "{}"), int(sys.argv[3] if len(sys.argv) > 3 else 2)
r = urllib.request.Request("http://localhost:9000/api/agir/" + cap, data=json.dumps({"args": args}).encode(), headers={"Authorization": "Bearer " + T, "X-Cassandra": "1", "Content-Type": "application/json"})
d = json.loads(urllib.request.urlopen(r, timeout=20).read()).get("resultat")
def forme(x, p):
    if isinstance(x, dict):
        return "{" + ", ".join("%s: %s" % (k, forme(v, p - 1) if p > 0 else type(v).__name__) for k, v in x.items()) + "}"
    if isinstance(x, list):
        return "[" + (forme(x[0], p - 1) if x and p > 0 else "%d" % len(x)) + "]"
    return type(x).__name__
print(forme(d, prof))
