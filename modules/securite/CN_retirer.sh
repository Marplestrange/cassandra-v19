#!/bin/sh
# Sécurité retire, À ROOT : les commandes posées par l'installation (les réglages déjà appliqués à la machine restent : ils tournent sans Cassandra).
set -eu
rm -f "/usr/libexec/cassandra/securite/mesurer" "/usr/libexec/cassandra/securite/agir" "/usr/libexec/cassandra/securite/outils"
rmdir /usr/libexec/cassandra/securite 2>/dev/null || true
echo "securite : commandes retirées"
