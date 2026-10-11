#!/usr/bin/env bash
# Retire le Sensorium : arrête et défait son unité. Ses données restent (sensorium/ dans le dossier de données) : rien n'est supprimé sans demande.
set -u
unite="sensorium.service"
systemctl disable --now "$unite" >/dev/null 2>&1 || true
rm -f "/etc/systemd/system/$unite" "${CASSANDRA_CONFIG:-/var/cassandra/config}/$unite"
systemctl daemon-reload
echo "sensorium : service retiré (données gardées dans ${CASSANDRA_DONNEES:-/var/cassandra/donnees}/sensorium)"
