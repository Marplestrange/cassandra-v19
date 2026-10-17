#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sécurité retire, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : CN
# VERSION CN : 0.3.2  #008332
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Sécurité retire, À ROOT : les commandes posées par l'installation (les réglages déjà appliqués à la machine restent : ils tournent sans Cassandra).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.2 empreinte=008332 ▼▼▼
# Sécurité retire, À ROOT : les commandes posées par l'installation (les réglages déjà appliqués à la machine restent : ils tournent sans Cassandra).
set -eu
rm -f "/usr/libexec/cassandra/securite/mesurer" "/usr/libexec/cassandra/securite/agir" "/usr/libexec/cassandra/securite/outils"
rmdir /usr/libexec/cassandra/securite 2>/dev/null || true
echo "securite : commandes retirées"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
