#!/usr/bin/env bash
# deploy.sh : pousse une mise à jour du noyau et de ses modules, sur une machine où install.sh est déjà passé.
#
#   ./deploy.sh              déploie ce dossier (celui où se trouve ce script)
#   ./deploy.sh --a-blanc    prépare, vérifie et dit ce qui changerait, sans rien basculer
#   ./deploy.sh --sauter-tests
#
# Déroulé : nouvelle version à côté de l'ancienne (releases/) -> vérification des manifestes -> bancs ->
# sauvegarde de la base -> bascule atomique du lien « current » -> redémarrage (le service annonce qu'il est
# prêt) -> vérification de chaque module ACTIF qui a changé. À la moindre preuve manquante : retour à la
# version précédente, seul, et le script le dit. Les modules non actifs ne sont jamais activés ici
# (c'est le rôle de install.sh --module).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIXE="${CASSANDRA_PREFIXE:-/opt/cassandra}"
DONNEES="${CASSANDRA_DONNEES:-/var/lib/cassandra}"
CONFIG="${CASSANDRA_CONFIG:-/etc/cassandra}"
JOURNAL="${CASSANDRA_JOURNAL:-/var/log/cassandra}"
UTILISATEUR="${CASSANDRA_UTILISATEUR:-cassandra}"
UNITE="cassandra-noyau.service"
GARDER=5
A_BLANC=0
TESTS=1

dire()    { printf '\033[1m==>\033[0m %s\n' "$*"; }
avertir() { printf '\033[33m!!\033[0m %s\n' "$*" >&2; }
echouer() { printf '\033[31mxx\033[0m %s\n' "$*" >&2; exit 1; }
aide() { sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --a-blanc)      A_BLANC=1; shift ;;
    --sauter-tests) TESTS=0; shift ;;
    -h|--aide)      aide ;;
    *)              echouer "option inconnue : $1 (voir --aide)" ;;
  esac
done

[ "$(id -u)" -eq 0 ] || echouer "à lancer en root"
[ -L "$PREFIXE/current" ] || echouer "aucune installation dans $PREFIXE : lancer install.sh d'abord"
[ -f "/etc/systemd/system/$UNITE" ] || echouer "le service $UNITE est absent : lancer install.sh d'abord"

as_service() { runuser -u "$UTILISATEUR" -- env CASSANDRA_DONNEES="$DONNEES" CASSANDRA_CONFIG="$CONFIG" "$@"; }
ANCIENNE="$(readlink -f "$PREFIXE/current")"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$PREFIXE/releases/$STAMP"

# ---------------------------------------------------------------- préparer
dire "nouvelle version $STAMP (actuelle : $(basename "$ANCIENNE"))"
mkdir -p "$DEST"
tar -C "$SRC" --exclude=.git --exclude=__pycache__ --exclude=donnees --exclude='*.db*' -cf - . | tar -C "$DEST" -xf -
chown -R root:root "$DEST"; chmod -R go-w "$DEST"
abandonner() { rm -rf "$DEST"; echouer "$1"; }

dire "vérification des manifestes"
if ! SORTIE="$(cd "$DEST" && python3 main.py verifier 2>&1)"; then printf '%s
' "$SORTIE" >&2; abandonner "manifestes invalides : rien n'est déployé"; fi

if [ "$TESTS" -eq 1 ] && [ -d "$DEST/tests" ]; then
  dire "bancs"
  (cd "$DEST" && python3 -m unittest discover -s tests >/tmp/cassandra-bancs.log 2>&1) || { tail -25 /tmp/cassandra-bancs.log >&2; abandonner "les bancs échouent : rien n'est déployé"; }
  tail -3 /tmp/cassandra-bancs.log | sed 's/^/    /'
fi

# ---------------------------------------------------------------- ce qui change, module par module
declare -A AVANT APRES
while read -r id v; do if [ -n "$id" ]; then AVANT["$id"]="$v"; fi; done < <(cd "$ANCIENNE" && python3 main.py versions 2>/dev/null || true)
while read -r id v; do if [ -n "$id" ]; then APRES["$id"]="$v"; fi; done < <(cd "$DEST" && python3 main.py versions)
CHANGES=()
dire "modules"
for id in $(printf '%s\n' "${!AVANT[@]}" "${!APRES[@]}" | sort -u); do
  a="${AVANT[$id]:-}"; b="${APRES[$id]:-}"
  if [ -z "$a" ]; then printf '    + %-14s %s (nouveau, non activé)\n' "$id" "$b"
  elif [ -z "$b" ]; then printf '    - %-14s %s (disparu)\n' "$id" "$a"
  elif [ "$a" != "$b" ]; then printf '    ~ %-14s %s -> %s\n' "$id" "$a" "$b"; CHANGES+=("$id")
  else
    # même version, code différent ? on le dit : une version qui ne bouge pas malgré un changement est un oubli
    if ! diff -rq "$ANCIENNE/modules/$id" "$DEST/modules/$id" >/dev/null 2>&1; then
      avertir "$id : le contenu a changé mais la version reste $a"
      CHANGES+=("$id")
    else printf '    = %-14s %s\n' "$id" "$b"; fi
  fi
done

if [ "$A_BLANC" -eq 1 ]; then
  rm -rf "$DEST"; dire "à blanc : rien n'a été basculé"; exit 0
fi

# ---------------------------------------------------------------- sauvegarde, bascule, preuve
if [ -f "$DONNEES/noyau.db" ]; then
  SAUV="$DONNEES/sauvegardes/noyau-$STAMP.db"
  dire "sauvegarde de la base : $(basename "$SAUV")"
  as_service python3 - "$DONNEES/noyau.db" "$SAUV" <<'PY'
import sqlite3, sys
src = sqlite3.connect("file:%s?mode=ro" % sys.argv[1], uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()
PY
  ls -1t "$DONNEES"/sauvegardes/noyau-*.db 2>/dev/null | tail -n +11 | xargs -r rm -f
fi

basculer() { ln -sfn "$1" "$PREFIXE/current.new"; mv -T "$PREFIXE/current.new" "$PREFIXE/current"; }
revenir() {
  avertir "$1 : retour à $(basename "$ANCIENNE")"
  basculer "$ANCIENNE"
  systemctl restart "$UNITE" || avertir "la version précédente ne redémarre pas non plus : voir journalctl -u $UNITE"
  rm -rf "$DEST"
  exit 1
}

dire "bascule"
install -d -o root -g root -m 0755 "$PREFIXE/extensions"   # les greffes vivent ici, hors des versions : un déploiement n'y touche jamais
sed -e "s|@PREFIXE@|$PREFIXE|g" -e "s|@DONNEES@|$DONNEES|g" -e "s|@CONFIG@|$CONFIG|g" -e "s|@JOURNAL@|$JOURNAL|g" \
    -e "s|@UTILISATEUR@|$UTILISATEUR|g" -e "s|@UNITE@|$UNITE|g" "$DEST/exploitation/$UNITE" > "/etc/systemd/system/$UNITE.new"
mv "/etc/systemd/system/$UNITE.new" "/etc/systemd/system/$UNITE"
systemctl daemon-reload
basculer "$DEST"
systemctl restart "$UNITE" || { journalctl -u "$UNITE" -n 25 --no-pager >&2; revenir "le noyau ne démarre pas"; }
as_service python3 "$DEST/main.py" etat >/dev/null || revenir "l'état du noyau est illisible"

for id in "${CHANGES[@]}"; do
  grep -qxF "$id" "$CONFIG/modules.actifs" 2>/dev/null || continue
  v="$DEST/modules/$id/verifier.sh"
  [ -f "$v" ] || continue
  dire "preuve du module $id"
  export CASSANDRA_PREFIXE="$PREFIXE" CASSANDRA_DONNEES="$DONNEES" CASSANDRA_CONFIG="$CONFIG" CASSANDRA_JOURNAL="$JOURNAL"
  export CASSANDRA_UTILISATEUR="$UTILISATEUR" CASSANDRA_UNITE="$UNITE" CASSANDRA_MODULE="$id" CASSANDRA_MODULE_DIR="$PREFIXE/current/modules/$id"
  (cd "$DEST/modules/$id" && bash ./verifier.sh) || revenir "le module $id n'est pas prouvé"
done

# ---------------------------------------------------------------- ménage
# (un grep -v qui ne retient rien rend 1 : sous pipefail ce ménage ferait sortir le script en silence)
{ ls -1dt "$PREFIXE"/releases/*/ 2>/dev/null | sed 's|/$||' | grep -vxF "$DEST" | grep -vxF "$ANCIENNE" | tail -n +"$GARDER" | xargs -r rm -rf; } || true
dire "déployé : $(basename "$DEST") (précédente gardée : $(basename "$ANCIENNE"))"
