#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Retire le Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.1.4  #5bfdf0
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Retire le Sensorium : arrête et défait son unité. Ses données restent (sensorium/ dans le dossier de données) : rien n'est supprimé sans demande.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.4 empreinte=5bfdf0 ▼▼▼
# Retire le Sensorium : arrête et défait son unité. Ses données restent (sensorium/ dans le dossier de données) : rien n'est supprimé sans demande.
set -u
unite="sensorium.service"
systemctl disable --now "$unite" >/dev/null 2>&1 || true
rm -f "/etc/systemd/system/$unite" "${CASSANDRA_CONFIG:-/var/cassandra/config}/$unite"
systemctl daemon-reload
echo "sensorium : service retiré (données gardées dans ${CASSANDRA_DONNEES:-/var/cassandra/donnees}/sensorium)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
