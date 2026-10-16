#!/bin/sh
# Sécurité retire, À ROOT : la commande de mesures posée par l'installation.
set -eu
rm -f "/usr/libexec/cassandra/securite/mesurer"
echo "securite : commande de mesures retirée"
