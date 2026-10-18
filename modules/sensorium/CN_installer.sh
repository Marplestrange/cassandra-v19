#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Installe le Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.1.8  #def9e2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Installe le Sensorium : son dossier, son unité (dans le dossier de Cassandra, liée dans systemd), puis le démarre.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.8 empreinte=def9e2 ▼▼▼
# Installe le Sensorium : son dossier, son unité (dans le dossier de Cassandra, liée dans systemd), puis le démarre.
# Idempotent : relancé (par CN_deploy.sh quand le module change), il remet l'unité à jour et redémarre le collecteur.
set -euo pipefail
: "${CASSANDRA_RACINE:?}" "${CASSANDRA_DONNEES:?}" "${CASSANDRA_CONFIG:?}" "${CASSANDRA_UTILISATEUR:?}" "${CASSANDRA_MODULE_DIR:?}"
unite="sensorium.service"
install -d -o root -g root -m 0700 "$CASSANDRA_DONNEES/sensorium"
sed -e "s|@RACINE@|$CASSANDRA_RACINE|g" -e "s|@DONNEES@|$CASSANDRA_DONNEES|g" -e "s|@CONFIG@|$CASSANDRA_CONFIG|g" \
    -e "s|@UTILISATEUR@|$CASSANDRA_UTILISATEUR|g" "$CASSANDRA_MODULE_DIR/CN_sensorium.service.in" > "$CASSANDRA_CONFIG/$unite.new"
chmod 0644 "$CASSANDRA_CONFIG/$unite.new"
mv "$CASSANDRA_CONFIG/$unite.new" "$CASSANDRA_CONFIG/$unite"
if [ "$(readlink "/etc/systemd/system/$unite" 2>/dev/null)" != "$CASSANDRA_CONFIG/$unite" ]; then
  rm -f "/etc/systemd/system/$unite"
  systemctl link "$CASSANDRA_CONFIG/$unite" >/dev/null 2>&1
fi
systemctl daemon-reload
systemctl enable "$unite" >/dev/null 2>&1
systemctl restart "$unite"
echo "sensorium : unité installée et démarrée (données : $CASSANDRA_DONNEES/sensorium)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
