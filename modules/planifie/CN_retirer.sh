#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Défait ce que l'installation a posé. Les tâches déjà dans la crontab restent (elles tourne
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : CN
# VERSION CN : 0.1.2  #3aa218
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Défait ce que l'installation a posé. Les tâches déjà dans la crontab restent (elles tournent sans Cassandra) : l'enrobage reste donc en place tant qu'une ligne s'en sert.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.2 empreinte=3aa218 ▼▼▼
# Défait ce que l'installation a posé. Les tâches déjà dans la crontab restent (elles tournent sans Cassandra) : l'enrobage reste donc en place tant qu'une ligne s'en sert.
rm -f /usr/libexec/cassandra/planifie/lire_crontabs /usr/libexec/cassandra/planifie/lire_table /usr/libexec/cassandra/planifie/ecrire_crontab /usr/libexec/cassandra/planifie/lancer
rmdir /usr/libexec/cassandra/planifie 2>/dev/null || true
if ! crontab -l 2>/dev/null | grep -q cron-wrap.sh; then rm -f /usr/local/lib/cassandra/cron-wrap.sh; fi
echo "planifie : commandes retirées (la base du module est gardée)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
