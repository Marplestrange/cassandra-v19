#!/bin/sh
# Planifie pose, À ROOT : trois petites commandes que le courtier peut lancer (et rien d'autre), l'enrobage des tâches, et les dossiers que l'enrobage écrit.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
U="${CASSANDRA_UTILISATEUR:-cassandra}"
DONNEES="${CASSANDRA_DONNEES:?le dossier des données}"
command -v crontab >/dev/null 2>&1 || { echo "planifie : crontab est absent (apt install cron)" >&2; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "planifie : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/planifie /usr/local/lib/cassandra /etc/cassandra
for c in lire_crontabs lire_table ecrire_crontab lancer; do
  install -m 0755 -o root -g root "$D/commandes/$c" "/usr/libexec/cassandra/planifie/$c"
done
[ -f /etc/cassandra/planifie.utilisateurs ] || printf '# Les utilisateurs dont Cassandra peut réécrire la crontab (un par ligne).\nroot\n' > /etc/cassandra/planifie.utilisateurs
chmod 0644 /etc/cassandra/planifie.utilisateurs
SPOOL="$DONNEES/cron-runs"; OPTS="$DONNEES/cron-opts"; MAINT="$DONNEES/cron-maintenance"; LOCKS="/run/cassandra-cron"
install -d -m 0755 -o "$U" -g "$U" "$SPOOL" "$OPTS"
sed -e "s|@SPOOL@|$SPOOL|" -e "s|@OPTIONS@|$OPTS|" -e "s|@MAINTENANCE@|$MAINT|" -e "s|@VERROUS@|$LOCKS|" "$D/commandes/cron-wrap.sh" > /usr/local/lib/cassandra/cron-wrap.sh.neuf
chown root:root /usr/local/lib/cassandra/cron-wrap.sh.neuf
chmod 0755 /usr/local/lib/cassandra/cron-wrap.sh.neuf
mv /usr/local/lib/cassandra/cron-wrap.sh.neuf /usr/local/lib/cassandra/cron-wrap.sh
echo "planifie : commandes et enrobage posés (crontabs réécrivables : $(grep -v '^#' /etc/cassandra/planifie.utilisateurs | tr '\n' ' '))"
