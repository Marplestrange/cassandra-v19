#!/bin/sh
# Canaux vérifie, À ROOT : la commande de connexion est-elle posée et exécutable ?
set -eu
[ -x "/usr/libexec/cassandra/canaux/connecter" ] || { echo "canaux : connecter absent" >&2; exit 1; }
echo "canaux : commande de connexion présente"
