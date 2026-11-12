#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : FastPanel preuve
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : fastpanel
# ZONE       : CN
# VERSION CN : 0.3.0  #3c119a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Prouve que le pont tient : sans FastPanel il dort, avec lui la copie existe, se lit, et la minuterie tourne.
# MÉTHODE    : cherche FastPanel ; si présent, ouvre la copie en lecture et compte ses tables.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.0 empreinte=3c119a ▼▼▼
set -eu
: "${CASSANDRA_DONNEES:?}" "${CASSANDRA_UTILISATEUR:?}"
panneau=""
for p in /usr/local/fastpanel2/app/db/fastpanel2.db /usr/local/fastpanel/app/db/fastpanel.db; do
  [ -f "$p" ] && { panneau="$p"; break; }
done
if [ -z "$panneau" ]; then
  echo "fastpanel : pas de FastPanel ici : rien à prouver, le pont dort"
  exit 0
fi
copie="$CASSANDRA_DONNEES/panneau/fastpanel.db"
[ -f "$copie" ] || { echo "fastpanel : la copie de la base du panneau manque" >&2; exit 1; }
systemctl is-active --quiet cassandra-panneau.timer || { echo "fastpanel : la minuterie de copie ne tourne pas" >&2; exit 1; }
runuser -u "$CASSANDRA_UTILISATEUR" -- python3 -c 'import sqlite3, sys; n = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True).execute("select count(*) from sqlite_master").fetchone()[0]; sys.exit(0 if n else 1)' "$copie" \
  || { echo "fastpanel : le service de Cassandra ne lit pas la copie" >&2; exit 1; }
echo "fastpanel : la base du panneau est copiée et lisible par le noyau"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
