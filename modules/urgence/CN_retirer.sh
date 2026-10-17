#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Urgence retire, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : urgence
# ZONE       : CN
# VERSION CN : 0.2.0  #eedd33
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Urgence retire, À ROOT : la commande posée. Un confinement en cours est LEVÉ d'abord (on ne retire jamais le moyen de rouvrir la porte en la laissant fermée).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=eedd33 ▼▼▼
# Urgence retire, À ROOT : la commande posée. Un confinement en cours est LEVÉ d'abord (on ne retire jamais le moyen de rouvrir la porte en la laissant fermée).
set -eu
p=/usr/libexec/cassandra/urgence/confiner
[ -x "$p" ] && "$p" lever >/dev/null 2>&1 || true
rm -f "$p" /usr/libexec/cassandra/urgence/crise
rmdir /usr/libexec/cassandra/urgence 2>/dev/null || true
echo "urgence : commande retirée (confinement levé s'il y en avait un)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
