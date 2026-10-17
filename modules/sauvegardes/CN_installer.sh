#!/bin/sh
# Sauvegardes pose, À ROOT : les trois commandes rclone que le courtier peut lancer (et rien d'autre).
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v rclone >/dev/null 2>&1 || { echo "sauvegardes : rclone est absent" >&2; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "sauvegardes : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/sauvegardes
for c in copier lister purger; do
  install -m 0755 -o root -g root "$D/commandes/CN_$c" "/usr/libexec/cassandra/sauvegardes/$c"
done
echo "sauvegardes : commandes rclone posées"
