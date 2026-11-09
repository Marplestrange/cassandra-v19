#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
# TITRE      : Retrait du module NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : netbird
# ZONE       : CN
# VERSION CN : 0.1.0  #1361ba
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Retire la commande root `piloter`. Ne coupe PAS NetBird, ne retire PAS le conteneur et ne désinstalle rien : le réseau privé est à l'administrateur.
# MÉTHODE    : suppression de /usr/libexec/cassandra/netbird/piloter (et du dossier s'il est vide).
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1361ba ▼▼▼
set -u
rm -f /usr/libexec/cassandra/netbird/piloter
rmdir /usr/libexec/cassandra/netbird 2>/dev/null || true
echo "netbird : commande root retirée (NetBird et son conteneur restent tels quels)"
exit 0
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : commandes/CN_piloter
