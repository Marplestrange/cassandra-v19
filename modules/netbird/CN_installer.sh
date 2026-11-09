#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
# TITRE      : Installation du module NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : netbird
# ZONE       : CN
# VERSION CN : 0.1.0  #d51bd6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Pose les commandes root `piloter` (le client NetBird, natif ou Docker) et `serveur` (un serveur NetBird auto-hébergé) que le courtier lance. N'installe ni NetBird ni Docker ni serveur : ce sont des gestes du module, à la demande.
# MÉTHODE    : `install` en root dans /usr/libexec/cassandra/netbird ; Cassandra ne peut ni la modifier ni en lancer une autre.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d51bd6 ▼▼▼
set -euo pipefail
: "${CASSANDRA_MODULE_DIR:?}"
command -v python3 >/dev/null 2>&1 || { echo "netbird : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/netbird
install -m 0755 -o root -g root "$CASSANDRA_MODULE_DIR/commandes/CN_piloter" /usr/libexec/cassandra/netbird/piloter
install -m 0755 -o root -g root "$CASSANDRA_MODULE_DIR/commandes/CN_serveur" /usr/libexec/cassandra/netbird/serveur
natif="absent"; docker="absent"
command -v netbird >/dev/null 2>&1 && natif="présent"
command -v docker >/dev/null 2>&1 && docker="présent"
echo "netbird : commandes root posées (piloter, serveur) (client natif : $natif ; Docker : $docker)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : commandes/CN_piloter (la commande posée), exploitation/CN_courtier.py (qui la lance)
