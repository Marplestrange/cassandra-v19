#!/bin/sh
# Urgence retire, À ROOT : la commande posée. Un confinement en cours est LEVÉ d'abord (on ne retire jamais le moyen de rouvrir la porte en la laissant fermée).
set -eu
p=/usr/libexec/cassandra/urgence/confiner
[ -x "$p" ] && "$p" lever >/dev/null 2>&1 || true
rm -f "$p" /usr/libexec/cassandra/urgence/crise
rmdir /usr/libexec/cassandra/urgence 2>/dev/null || true
echo "urgence : commande retirée (confinement levé s'il y en avait un)"
