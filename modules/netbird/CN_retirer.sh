#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
# TITRE      : Retrait du module NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : netbird
# ZONE       : CN
# VERSION CN : 0.1.1  #53b3d7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Retire les commandes root `piloter` et `serveur`. Ne coupe PAS NetBird, ne retire NI le conteneur NI le serveur (/opt/netbird-serveur reste tel quel) et ne désinstalle rien : le réseau privé est à l'administrateur.
# MÉTHODE    : suppression de /usr/libexec/cassandra/netbird/piloter (et du dossier s'il est vide).
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=53b3d7 ▼▼▼
set -u
rm -f /usr/libexec/cassandra/netbird/piloter /usr/libexec/cassandra/netbird/serveur
rmdir /usr/libexec/cassandra/netbird 2>/dev/null || true
echo "netbird : commandes root retirées (NetBird, son conteneur et un éventuel serveur restent tels quels)"
exit 0
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : commandes/CN_piloter
