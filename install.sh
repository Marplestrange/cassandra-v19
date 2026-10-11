#!/usr/bin/env bash
# install.sh : installe le NOYAU de Cassandra V19 et, à la demande, ses modules.
#
#   ./install.sh                         le noyau seul
#   ./install.sh --module certificats    le noyau + ce module et ses dépendances (dns)
#   ./install.sh --tous                  le noyau + tous les modules du dossier modules/
#   ./install.sh --retirer certificats   retire un module (son retirer.sh, puis son état)
#   ./install.sh --extension ./sentinelle   GREFFE un module après coup, à chaud : copié dans extensions/ (que
#                                        deploy.sh ne touche jamais), prouvé, activé ; le noyau le branche sans redémarrer
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
EXTENSIONS=()
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
    --extension)    [ $# -ge 2 ] || echouer "--extension attend un dossier"; EXTENSIONS+=("$2"); shift 2 ;;
    --sans-service) SANS_SERVICE=1; shift ;;
    -h|--aide)      aide ;;
    *)              echouer "option inconnue : $1 (voir --aide)" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || echouer "à lancer en root"

as_service() { runuser -u "$UTILISATEUR" -- env CASSANDRA_DONNEES="$DONNEES" CASSANDRA_CONFIG="$CONFIG" CASSANDRA_EXTENSIONS="$PREFIXE/extensions" "$@"; }

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
# Un module greffé vit dans extensions/ ; un module livré avec le noyau, dans la version courante.
dossier_module() { # id
  if [ -d "$PREFIXE/extensions/$1" ]; then printf '%s' "$PREFIXE/extensions/$1"; else printf '%s' "$PREFIXE/current/modules/$1"; fi
}

env_module() { # id
  export CASSANDRA_PREFIXE="$PREFIXE" CASSANDRA_DONNEES="$DONNEES" CASSANDRA_CONFIG="$CONFIG" CASSANDRA_JOURNAL="$JOURNAL"
  export CASSANDRA_UTILISATEUR="$UTILISATEUR" CASSANDRA_UNITE="$UNITE" CASSANDRA_MODULE="$1"
  CASSANDRA_MODULE_DIR="$(dossier_module "$1")"; export CASSANDRA_MODULE_DIR
}

# L'état des modules (installé, actif) vit dans la base du noyau ; le menu des modules et ce script lisent le même.
etat_module() { as_service python3 "$PREFIXE/current/main.py" module "$@"; }
actif() { etat_module actif "$1" >/dev/null 2>&1; }

installer_module() { # id
  local id="$1" d
  d="$(dossier_module "$1")"
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
  etat_module installe "$id"
  etat_module activer "$id" --sans-dependances || echouer "module $id installé mais non activé"
  dire "module $id : installé, prouvé et actif"
}

retirer_script() { # id : le retirer.sh seul, sans toucher à la liste
  local d
  d="$(dossier_module "$1")"
  env_module "$1"
  if [ -f "$d/retirer.sh" ]; then (cd "$d" && bash ./retirer.sh) || true; fi
}

# ---------------------------------------------------------------- retrait d'un module
if [ -n "$RETIRER" ]; then
  [ -d "$(dossier_module "$RETIRER")" ] || echouer "module introuvable : $RETIRER"
  dire "module $RETIRER : retrait"
  retirer_script "$RETIRER"
  etat_module desactiver "$RETIRER" --en-cascade --forcer >/dev/null 2>&1 || true
  etat_module oublier "$RETIRER"
  # un module greffé s'efface avec son dossier ; le noyau, lui, garde en mémoire ce qu'il avait branché jusqu'au prochain démarrage
  if [ -d "$PREFIXE/extensions/$RETIRER" ]; then rm -rf "${PREFIXE:?}/extensions/$RETIRER"; fi
  systemctl daemon-reload
  systemctl restart "$UNITE"
  dire "module $RETIRER retiré"
  exit 0
fi

# ---------------------------------------------------------------- greffe d'une extension (à chaud)
if [ "${#EXTENSIONS[@]}" -gt 0 ] && [ -L "$PREFIXE/current" ]; then
  install -d -o root -g root -m 0755 "$PREFIXE/extensions"
  for src in "${EXTENSIONS[@]}"; do
    [ -f "$src/manifeste.toml" ] || echouer "$src : pas de manifeste.toml"
    id="$(basename "$(cd "$src" && pwd)")"
    dire "extension $id : dépôt dans $PREFIXE/extensions"
    rm -rf "${PREFIXE:?}/extensions/$id"
    cp -r "$src" "$PREFIXE/extensions/$id"
    chown -R root:root "$PREFIXE/extensions/$id"; chmod -R go-w "$PREFIXE/extensions/$id"
    if ! SORTIE="$(cd "$PREFIXE/current" && CASSANDRA_EXTENSIONS="$PREFIXE/extensions" python3 main.py verifier 2>&1)"; then
      printf '%s\n' "$SORTIE" >&2; rm -rf "${PREFIXE:?}/extensions/$id"; echouer "extension $id refusée : rien n'est greffé"
    fi
    # ses dépendances livrées avec le noyau d'abord, puis elle
    while read -r m; do
      [ -n "$m" ] || continue
      if [ "$m" = "$id" ] || ! actif "$m"; then CASSANDRA_EXTENSIONS="$PREFIXE/extensions" installer_module "$m"; fi
    done < <(cd "$PREFIXE/current" && CASSANDRA_EXTENSIONS="$PREFIXE/extensions" python3 main.py ordre "$id")
  done
  if systemctl is-active --quiet "$UNITE"; then
    dire "le noyau branche l'extension à chaud (sans redémarrer)"
    sleep 7
    runuser -u "$UTILISATEUR" -- env CASSANDRA_DONNEES="$DONNEES" CASSANDRA_CONFIG="$CONFIG" CASSANDRA_EXTENSIONS="$PREFIXE/extensions" python3 "$PREFIXE/current/main.py" moteurs || true
  fi
  exit 0
fi

# ---------------------------------------------------------------- le noyau
verifier_python

dire "utilisateur et dossiers"
id -u "$UTILISATEUR" >/dev/null 2>&1 || useradd --system --home-dir "$DONNEES" --no-create-home --shell /usr/sbin/nologin "$UTILISATEUR"
install -d -o root -g root -m 0755 "$PREFIXE" "$PREFIXE/releases" "$PREFIXE/extensions"
install -d -o "$UTILISATEUR" -g "$UTILISATEUR" -m 0750 "$DONNEES" "$DONNEES/sauvegardes" "$JOURNAL"
install -d -o root -g "$UTILISATEUR" -m 0750 "$CONFIG"

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
  mapfile -t MODULES < <(cd "$DEST" && CASSANDRA_EXTENSIONS="" python3 main.py ordre)
elif [ "${#MODULES[@]}" -gt 0 ]; then
  mapfile -t MODULES < <(cd "$DEST" && CASSANDRA_EXTENSIONS="" python3 main.py ordre "${MODULES[@]}")
fi
# Un module qui échoue ne fait pas tomber le noyau : il est retiré et le noyau continue avec les précédents.
for m in "${MODULES[@]}"; do installer_module "$m"; done

if [ "${#MODULES[@]}" -gt 0 ]; then
  dire "rechargement avec les modules actifs"
  demarrer
fi
if [ "$SANS_SERVICE" -eq 0 ]; then
  dire "état du noyau"
  as_service python3 "$PREFIXE/current/main.py" etat
fi
dire "terminé : noyau $STAMP${MODULES[*]:+, modules : ${MODULES[*]}}"
