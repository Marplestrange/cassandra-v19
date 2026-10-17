#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Voix pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : voix
# ZONE       : CN
# VERSION CN : 0.1.0  #799d06
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Voix pose, À ROOT : les trois commandes (écouter, parler, télécharger) que le courtier peut lancer.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=799d06 ▼▼▼
# Voix pose, À ROOT : les trois commandes (écouter, parler, télécharger) que le courtier peut lancer.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "voix : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/voix /usr/libexec/cassandra/voix/voix
for c in ecouter parler telecharger; do
  install -m 0755 -o root -g root "$D/commandes/CN_$c" "/usr/libexec/cassandra/voix/$c"
done
echo "voix : commandes posées (les modèles se téléchargent à la demande)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
