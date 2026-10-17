#!/bin/sh
# Canaux retire, À ROOT : la commande de connexion posée par l'installation.
set -eu
rm -f "/usr/libexec/cassandra/canaux/connecter"
echo "canaux : commande de connexion retirée"
