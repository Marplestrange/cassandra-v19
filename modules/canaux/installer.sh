#!/bin/sh
# Canaux pose, À ROOT : la commande de connexion Telegram que le courtier peut lancer.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "canaux : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/canaux
install -m 0755 -o root -g root "$D/commandes/connecter" "/usr/libexec/cassandra/canaux/connecter"
echo "canaux : commande de connexion posée"
