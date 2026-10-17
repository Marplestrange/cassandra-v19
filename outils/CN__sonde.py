# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Jetable
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #e5e277
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Jetable : appelle des capacités du serveur local et montre les clés du résultat. usage: python outils/CN__sonde.py cap '{"arg":1}' ...
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=e5e277 ▼▼▼
"""Jetable : appelle des capacités du serveur local et montre les clés du résultat. usage: python outils/CN__sonde.py cap '{"arg":1}' ..."""
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
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : constantes et configuration
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
