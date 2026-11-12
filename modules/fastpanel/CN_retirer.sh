#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : FastPanel retrait, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : fastpanel
# ZONE       : CN
# VERSION CN : 0.3.1  #a73fbf
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Retire la minuterie qui copie la base de FastPanel ; la copie est effacée, la base d'origine n'est jamais touchée.
# MÉTHODE    : arrête et défait les deux unités, supprime le dossier de la copie.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.1 empreinte=a73fbf ▼▼▼
set -u
systemctl disable --now cassandra-panneau.timer >/dev/null 2>&1 || true
rm -f /etc/systemd/system/cassandra-panneau.timer /etc/systemd/system/cassandra-panneau.service
systemctl daemon-reload
rm -rf "${CASSANDRA_DONNEES:-/var/cassandra/donnees}/panneau"
echo "fastpanel : copie du panneau retirée"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
