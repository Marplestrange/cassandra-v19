#!/bin/sh
# Sécurité pose, À ROOT : la commande de mesures que le courtier peut lancer.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "securite : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/securite
install -m 0755 -o root -g root "$D/commandes/mesurer" "/usr/libexec/cassandra/securite/mesurer"
echo "securite : commande de mesures posée"
