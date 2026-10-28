#!/usr/bin/env bash
# Amorçage de Cassandra V19 en UNE commande, sur un serveur Debian ou Ubuntu neuf.
#
#   curl -fsSL https://raw.githubusercontent.com/Marplestrange/cassandra-v19/main/CN_amorcer.sh | sudo bash
#
# Il installe ce qui manque (git, python3, cryptography ; le reste des dépendances, CN_install.sh), récupère les sources dans /opt/cassandra-sources (ou les met à jour),
# puis lance CN_install.sh avec TOUS les modules, et dit comment ouvrir l'application et créer le premier compte.
# Des arguments supplémentaires passent tels quels à CN_install.sh :
#
#   curl -fsSL .../CN_amorcer.sh | sudo bash -s -- --racine /srv/cassandra
#   curl -fsSL .../CN_amorcer.sh | sudo bash -s -- --module billetterie     (le noyau et ce module seulement, au lieu de tous)
#
# Variables : CASSANDRA_DEPOT (autre dépôt), CASSANDRA_BRANCHE (défaut main), CASSANDRA_SOURCES (défaut /opt/cassandra-sources).
# Idempotent : relancé, il met à jour les sources et pose une nouvelle version à côté de l'ancienne (CN_install.sh).
set -euo pipefail

DEPOT="${CASSANDRA_DEPOT:-https://github.com/Marplestrange/cassandra-v19.git}"
BRANCHE="${CASSANDRA_BRANCHE:-main}"
SOURCES="${CASSANDRA_SOURCES:-/opt/cassandra-sources}"

dire() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
echouer() { printf '\n\033[31mÉchec : %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || echouer "à lancer en root (sudo bash …)"
command -v systemctl >/dev/null 2>&1 || echouer "systemd est nécessaire : Cassandra s'installe comme un service"

manque=()
command -v git >/dev/null 2>&1 || manque+=(git)
command -v python3 >/dev/null 2>&1 || manque+=(python3)
command -v curl >/dev/null 2>&1 || manque+=(curl)
python3 -c 'import cryptography' 2>/dev/null || manque+=(python3-cryptography)
if [ "${#manque[@]}" -gt 0 ]; then
  command -v apt-get >/dev/null 2>&1 || echouer "installez d'abord : ${manque[*]} (apt-get n'existe pas ici)"
  dire "installation de : ${manque[*]}"
  DEBIAN_FRONTEND=noninteractive apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${manque[@]}"
fi

dire "sources dans $SOURCES"
if [ -d "$SOURCES/.git" ]; then
  git -C "$SOURCES" fetch --quiet origin "$BRANCHE"
  git -C "$SOURCES" checkout --quiet "$BRANCHE"
  git -C "$SOURCES" reset --quiet --hard "origin/$BRANCHE"
else
  rm -rf "$SOURCES"
  git clone --quiet --depth 1 --branch "$BRANCHE" "$DEPOT" "$SOURCES"
fi

cd "$SOURCES"
chmod +x CN_install.sh
dire "installation (noyau et modules)"
if [ "$#" -gt 0 ]; then
  ./CN_install.sh "$@"
else
  ./CN_install.sh --tous
fi

cat <<'FIN'

──────────────────────────────────────────────────────────────────────────────
Cassandra est installée et tourne comme un service (systemctl status cassandra-noyau).

Pour l'ouvrir : elle écoute sur 127.0.0.1:9000, donc pas depuis l'extérieur.
  - depuis votre poste :    ssh -L 9000:127.0.0.1:9000 UTILISATEUR@CE_SERVEUR
                            puis ouvrez http://127.0.0.1:9000
  - ou derrière un proxy HTTPS (nginx, Caddy) qui renvoie vers 127.0.0.1:9000.

Le PREMIER compte créé sur l'écran de connexion devient le superadministrateur :
créez-le tout de suite, avec un mot de passe solide.

Mises à jour : relancez la même commande (ou ./CN_deploy.sh dans /opt/cassandra-sources).
──────────────────────────────────────────────────────────────────────────────
FIN
