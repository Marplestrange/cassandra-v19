#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Urgence pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : urgence
# ZONE       : CN
# VERSION CN : 0.2.0  #7d701e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Urgence pose, À ROOT : la commande de confinement que le courtier peut lancer, et rien d'autre. Elle exige iptables et systemd.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=7d701e ▼▼▼
# Urgence pose, À ROOT : la commande de confinement que le courtier peut lancer, et rien d'autre. Elle exige iptables et systemd.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "urgence : python3 est absent" >&2; exit 3; }
command -v iptables >/dev/null 2>&1 || { echo "urgence : iptables est absent (apt install iptables) : le confinement réseau serait impossible" >&2; exit 3; }
command -v systemd-run >/dev/null 2>&1 || { echo "urgence : systemd-run est absent : l'échéance du confinement serait impossible" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/urgence
for c in confiner crise; do
  install -m 0755 -o root -g root "$D/commandes/CN_$c" "/usr/libexec/cassandra/urgence/$c"
done
install -d -m 0750 -o root -g root /var/lib/cassandra-securite
echo "urgence : commandes posées (confiner, crise)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
