#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Planifie pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : CN
# VERSION CN : 0.1.3  #facec8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Planifie pose, À ROOT : trois petites commandes que le courtier peut lancer (et rien d'autre), l'enrobage des tâches, et les dossiers que l'enrobage écrit.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.3 empreinte=facec8 ▼▼▼
# Planifie pose, À ROOT : trois petites commandes que le courtier peut lancer (et rien d'autre), l'enrobage des tâches, et les dossiers que l'enrobage écrit.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
U="${CASSANDRA_UTILISATEUR:-cassandra}"
DONNEES="${CASSANDRA_DONNEES:?le dossier des données}"
command -v crontab >/dev/null 2>&1 || { echo "planifie : crontab est absent (apt install cron)" >&2; exit 3; }
command -v python3 >/dev/null 2>&1 || { echo "planifie : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/planifie /usr/local/lib/cassandra /etc/cassandra
for c in lire_crontabs lire_table ecrire_crontab lancer; do
  install -m 0755 -o root -g root "$D/commandes/CN_$c" "/usr/libexec/cassandra/planifie/$c"
done
[ -f /etc/cassandra/planifie.utilisateurs ] || printf '# Les utilisateurs dont Cassandra peut réécrire la crontab (un par ligne).\nroot\n' > /etc/cassandra/planifie.utilisateurs
chmod 0644 /etc/cassandra/planifie.utilisateurs
SPOOL="$DONNEES/cron-runs"; OPTS="$DONNEES/cron-opts"; MAINT="$DONNEES/cron-maintenance"; LOCKS="/run/cassandra-cron"
install -d -m 0755 -o "$U" -g "$U" "$SPOOL" "$OPTS"
sed -e "s|@SPOOL@|$SPOOL|" -e "s|@OPTIONS@|$OPTS|" -e "s|@MAINTENANCE@|$MAINT|" -e "s|@VERROUS@|$LOCKS|" "$D/commandes/CN_cron-wrap.sh" > /usr/local/lib/cassandra/cron-wrap.sh.neuf
chown root:root /usr/local/lib/cassandra/cron-wrap.sh.neuf
chmod 0755 /usr/local/lib/cassandra/cron-wrap.sh.neuf
mv /usr/local/lib/cassandra/cron-wrap.sh.neuf /usr/local/lib/cassandra/cron-wrap.sh
echo "planifie : commandes et enrobage posés (crontabs réécrivables : $(grep -v '^#' /etc/cassandra/planifie.utilisateurs | tr '\n' ' '))"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
