#!/usr/bin/env bash
# install.sh : installe le NOYAU de Cassandra V19 et, à la demande, ses modules.
#
#   ./install.sh                         le noyau seul
#   ./install.sh --module certificats    le noyau + ce module et ses dépendances (dns)
#   ./install.sh --tous                  le noyau + tous les modules du dossier modules/
#   ./install.sh --retirer certificats   retire un module (son retirer.sh, puis la liste des modules actifs)
#
# Idempotent : relancé, il pose une nouvelle version à côté de l'ancienne (releases/) et bascule d'un coup.
# Chaque module s'installe par SON script (modules/<id>/installer.sh), se prouve par SA vérification
# (verifier.sh) et, si la preuve manque, se retire seul par SON retrait (retirer.sh).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIXE="${CASSANDRA_PREFIXE:-/opt/cassandra}"
DONNEES="${CASSANDRA_DONNEES:-/var/lib/cassandra}"
CONFIG="${CASSANDRA_CONFIG:-/etc/cassandra}"
JOURNAL="${CASSANDRA_JOURNAL:-/var/log/cassandra}"
UTILISATEUR="${CASSANDRA_UTILISATEUR:-cassandra}"
UNITE="cassandra-noyau.service"
MODULES=()
RETIRER=""
TOUS=0
SANS_SERVICE=0

dire()    { printf '\033[1m==>\033[0m %s\n' "$*"; }
avertir() { printf '\033[33m!!\033[0m %s\n' "$*" >&2; }
echouer() { printf '\033[31mxx\033[0m %s\n' "$*" >&2; exit 1; }

aide() { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --module)       [ $# -ge 2 ] || echouer "--module attend un identifiant"; MODULES+=("$2"); shift 2 ;;
    --tous)         TOUS=1; shift ;;
    --retirer)      [ $# -ge 2 ] || echouer "--retirer attend un identifiant"; RETIRER="$2"; shift 2 ;;
    --sans-service) SANS_SERVICE=1; shift ;;
    -h|--aide)      aide ;;
    *)              echouer "option inconnue : $1 (voir --aide)" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || echouer "à lancer en root"

as_service() { runuser -u "$UTILISATEUR" -- env CASSANDRA_DONNEES="$DONNEES" CASSANDRA_CONFIG="$CONFIG" "$@"; }

# ---------------------------------------------------------------- prérequis
verifier_python() {
  python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null && return 0
  if command -v apt-get >/dev/null 2>&1; then
    dire "Python 3.11 ou plus requis : installation par apt"
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 >/dev/null
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' && return 0
  fi
  echouer "Python 3.11 ou plus est nécessaire (tomllib, SQLite avec JSON)"
}

# ---------------------------------------------------------------- un module
env_module() { # id
  export CASSANDRA_PREFIXE="$PREFIXE" CASSANDRA_DONNEES="$DONNEES" CASSANDRA_CONFIG="$CONFIG" CASSANDRA_JOURNAL="$JOURNAL"
  export CASSANDRA_UTILISATEUR="$UTILISATEUR" CASSANDRA_UNITE="$UNITE" CASSANDRA_MODULE="$1"
  export CASSANDRA_MODULE_DIR="$PREFIXE/current/modules/$1"
}

actif() { grep -qxF "$1" "$CONFIG/modules.actifs" 2>/dev/null; }

installer_module() { # id
  local id="$1" d="$PREFIXE/current/modules/$1"
  [ -d "$d" ] || echouer "module introuvable : $id"
  dire "module $id : installation"
  env_module "$id"
  if [ -f "$d/installer.sh" ]; then
    (cd "$d" && bash ./installer.sh) || { avertir "module $id : l'installation a échoué, retrait"; retirer_script "$id"; echouer "module $id non installé"; }
  fi
  if [ -f "$d/verifier.sh" ]; then
    if ! (cd "$d" && bash ./verifier.sh); then
      avertir "module $id : la vérification échoue, retrait"
      retirer_script "$id"
      echouer "module $id non installé (pas de preuve qu'il fonctionne)"
    fi
  fi
  actif "$id" || printf '%s\n' "$id" >> "$CONFIG/modules.actifs"
  dire "module $id : installé et prouvé"
}

retirer_script() { # id : le retirer.sh seul, sans toucher à la liste
  local d="$PREFIXE/current/modules/$1"
  env_module "$1"
  if [ -f "$d/retirer.sh" ]; then (cd "$d" && bash ./retirer.sh) || true; fi
}

# ---------------------------------------------------------------- retrait d'un module
if [ -n "$RETIRER" ]; then
  [ -d "$PREFIXE/current/modules/$RETIRER" ] || echouer "module introuvable : $RETIRER"
  dire "module $RETIRER : retrait"
  retirer_script "$RETIRER"
  if [ -f "$CONFIG/modules.actifs" ]; then
    grep -vxF "$RETIRER" "$CONFIG/modules.actifs" > "$CONFIG/modules.actifs.new" || true
    mv "$CONFIG/modules.actifs.new" "$CONFIG/modules.actifs"
  fi
  systemctl daemon-reload
  systemctl restart "$UNITE"
  dire "module $RETIRER retiré"
  exit 0
fi

# ---------------------------------------------------------------- le noyau
verifier_python

dire "utilisateur et dossiers"
id -u "$UTILISATEUR" >/dev/null 2>&1 || useradd --system --home-dir "$DONNEES" --no-create-home --shell /usr/sbin/nologin "$UTILISATEUR"
install -d -o root -g root -m 0755 "$PREFIXE" "$PREFIXE/releases"
install -d -o "$UTILISATEUR" -g "$UTILISATEUR" -m 0750 "$DONNEES" "$DONNEES/sauvegardes" "$JOURNAL"
install -d -o root -g "$UTILISATEUR" -m 0750 "$CONFIG"
[ -f "$CONFIG/modules.actifs" ] || : > "$CONFIG/modules.actifs"
chown root:"$UTILISATEUR" "$CONFIG/modules.actifs"; chmod 0640 "$CONFIG/modules.actifs"

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$PREFIXE/releases/$STAMP"
dire "version $STAMP"
mkdir -p "$DEST"
tar -C "$SRC" --exclude=.git --exclude=__pycache__ --exclude=donnees --exclude='*.db*' -cf - . | tar -C "$DEST" -xf -
chown -R root:root "$DEST"; chmod -R go-w "$DEST"

dire "vérification des manifestes avant bascule"
if ! SORTIE="$(cd "$DEST" && python3 main.py verifier 2>&1)"; then printf '%s
' "$SORTIE" >&2; rm -rf "$DEST"; echouer "manifestes invalides : rien n'est installé"; fi

ln -sfn "$DEST" "$PREFIXE/current.new"
mv -T "$PREFIXE/current.new" "$PREFIXE/current"

dire "service systemd"
sed -e "s|@PREFIXE@|$PREFIXE|g" -e "s|@DONNEES@|$DONNEES|g" -e "s|@CONFIG@|$CONFIG|g" -e "s|@JOURNAL@|$JOURNAL|g" \
    -e "s|@UTILISATEUR@|$UTILISATEUR|g" -e "s|@UNITE@|$UNITE|g" "$DEST/exploitation/$UNITE" > "/etc/systemd/system/$UNITE"
systemctl daemon-reload

demarrer() {
  [ "$SANS_SERVICE" -eq 0 ] || return 0
  systemctl enable "$UNITE" >/dev/null 2>&1
  systemctl restart "$UNITE" || { journalctl -u "$UNITE" -n 25 --no-pager >&2; echouer "le noyau ne démarre pas"; }
}

dire "démarrage du noyau (le service annonce lui-même qu'il est prêt)"
demarrer

if [ "$TOUS" -eq 1 ]; then
  mapfile -t MODULES < <(cd "$DEST" && python3 main.py ordre)
elif [ "${#MODULES[@]}" -gt 0 ]; then
  mapfile -t MODULES < <(cd "$DEST" && python3 main.py ordre "${MODULES[@]}")
fi
# Un module qui échoue ne fait pas tomber le noyau : il est retiré et le noyau continue avec les précédents.
for m in "${MODULES[@]}"; do installer_module "$m"; done
chown root:"$UTILISATEUR" "$CONFIG/modules.actifs"

if [ "${#MODULES[@]}" -gt 0 ]; then
  dire "rechargement avec les modules actifs"
  demarrer
fi
if [ "$SANS_SERVICE" -eq 0 ]; then
  dire "état du noyau"
  as_service python3 "$PREFIXE/current/main.py" etat
fi
dire "terminé : noyau $STAMP${MODULES[*]:+, modules : ${MODULES[*]}}"
