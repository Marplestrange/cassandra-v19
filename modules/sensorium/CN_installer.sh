#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Installe le Sensorium
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.1.13  #05726b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Installe le Sensorium : son dossier, son unité (dans le dossier de Cassandra, liée dans systemd), puis le démarre.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.13 empreinte=05726b ▼▼▼
# Installe le Sensorium : son dossier, son unité (dans le dossier de Cassandra, liée dans systemd), puis le démarre.
# Idempotent : relancé (par CN_deploy.sh quand le module change), il remet l'unité à jour et redémarre le collecteur.
set -euo pipefail
: "${CASSANDRA_RACINE:?}" "${CASSANDRA_DONNEES:?}" "${CASSANDRA_CONFIG:?}" "${CASSANDRA_UTILISATEUR:?}" "${CASSANDRA_MODULE_DIR:?}"
unite="sensorium.service"
install -d -o root -g root -m 0700 "$CASSANDRA_DONNEES/sensorium"
# la commande que le courtier lance À ROOT pour redémarrer le démon (table fermée : deux modes, une unité) ; le noyau, lui, n'est pas root
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/sensorium
install -m 0755 -o root -g root "$CASSANDRA_MODULE_DIR/commandes/CN_redemarrer" /usr/libexec/cassandra/sensorium/redemarrer
install -m 0755 -o root -g root "$CASSANDRA_MODULE_DIR/commandes/CN_reparer" /usr/libexec/cassandra/sensorium/reparer
# la commande des seuils reçoit, GRAVÉ À L'INSTALLATION, le dossier où elle écrit : le noyau ne lui donne jamais un chemin
sed -e "s|^CONFIG = \"@CONFIG@\"|CONFIG = \"$CASSANDRA_CONFIG\"|" "$CASSANDRA_MODULE_DIR/commandes/CN_seuils" > /usr/libexec/cassandra/sensorium/seuils.new
chmod 0755 /usr/libexec/cassandra/sensorium/seuils.new && chown root:root /usr/libexec/cassandra/sensorium/seuils.new && mv /usr/libexec/cassandra/sensorium/seuils.new /usr/libexec/cassandra/sensorium/seuils
sed -e "s|@RACINE@|$CASSANDRA_RACINE|g" -e "s|@DONNEES@|$CASSANDRA_DONNEES|g" -e "s|@CONFIG@|$CASSANDRA_CONFIG|g" \
    -e "s|@UTILISATEUR@|$CASSANDRA_UTILISATEUR|g" -e "s|@UNITE@|${CASSANDRA_UNITE:-cassandra-noyau.service}|g"     -e "s|@UTILISATEURS@|${CASSANDRA_UTILISATEURS:-/var/www}|g" "$CASSANDRA_MODULE_DIR/CN_sensorium.service.in" > "$CASSANDRA_CONFIG/$unite.new"
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
