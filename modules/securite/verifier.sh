#!/bin/sh
# Sécurité vérifie, À ROOT : la commande de mesures est-elle posée et exécutable ?
set -eu
[ -x "/usr/libexec/cassandra/securite/mesurer" ] || { echo "securite : mesurer absent" >&2; exit 1; }
echo "securite : commande de mesures présente"
