#!/bin/sh
# Défait ce que l'installation a posé. Les tâches déjà dans la crontab restent (elles tournent sans Cassandra) : l'enrobage reste donc en place tant qu'une ligne s'en sert.
rm -f /usr/libexec/cassandra/planifie/lire_crontabs /usr/libexec/cassandra/planifie/lire_table /usr/libexec/cassandra/planifie/ecrire_crontab /usr/libexec/cassandra/planifie/lancer
rmdir /usr/libexec/cassandra/planifie 2>/dev/null || true
if ! crontab -l 2>/dev/null | grep -q cron-wrap.sh; then rm -f /usr/local/lib/cassandra/cron-wrap.sh; fi
echo "planifie : commandes retirées (la base du module est gardée)"
