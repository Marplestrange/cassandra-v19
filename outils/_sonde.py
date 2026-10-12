"""Jetable : appelle des capacités du serveur local et montre les clés du résultat. usage: python outils/_sonde.py cap '{"arg":1}' ..."""
import json, os, sys, urllib.request
T = open(os.path.join(os.environ["TEMP"], "tok")).read().strip()
a = sys.argv[1:]
for i in range(0, len(a), 2):
    cap, args = a[i], json.loads(a[i + 1] if i + 1 < len(a) else "{}")
    r = urllib.request.Request("http://localhost:9000/api/agir/" + cap, data=json.dumps({"args": args}).encode(), headers={"Authorization": "Bearer " + T, "X-Cassandra": "1", "Content-Type": "application/json"})
    try:
        d = json.loads(urllib.request.urlopen(r, timeout=20).read())
    except urllib.error.HTTPError as e:
        d = json.loads(e.read())
    res = d.get("resultat")
    print("==", cap, d.get("statut"), d.get("erreur") or d.get("raison") or "", json.dumps(res, ensure_ascii=False)[:420] if res is not None else "")
