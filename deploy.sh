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
# shellcheck source=exploitation/commun.sh
. "$SRC/exploitation/commun.sh"
GARDER=5
A_BLANC=0
TESTS=1

aide() { sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --a-blanc)      A_BLANC=1; shift ;;
    --sauter-tests) TESTS=0; shift ;;
    # shellcheck disable=SC2034  # lu par calculer_chemins (exploitation/commun.sh)
    --racine)       [ $# -ge 2 ] || echouer "--racine attend un dossier"; CASSANDRA_RACINE="$2"; shift 2 ;;
    -h|--aide)      aide ;;
    *)              echouer "option inconnue : $1 (voir --aide)" ;;
  esac
done

calculer_chemins
[ "$(id -u)" -eq 0 ] || echouer "à lancer en root"
[ -L "$RACINE/current" ] || echouer "aucune installation dans $RACINE : lancer install.sh d'abord (il migre l'ancienne disposition si besoin)"
[ -e "/etc/systemd/system/$UNITE" ] || echouer "le service $UNITE est absent : lancer install.sh d'abord"

ANCIENNE="$(readlink -f "$RACINE/current")"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$RACINE/releases/$STAMP"

# ---------------------------------------------------------------- préparer
dire "nouvelle version $STAMP (actuelle : $(basename "$ANCIENNE"))"
mkdir -p "$DEST"
tar -C "$SRC" --exclude=.git --exclude=__pycache__ --exclude=donnees --exclude='*.db*' -cf - . | tar -C "$DEST" -xf -
chown -R root:root "$DEST"; chmod -R go-w "$DEST"
abandonner() { rm -rf "$DEST"; echouer "$1"; }

dire "vérification des manifestes"
if ! SORTIE="$(cd "$DEST" && python3 main.py verifier 2>&1)"; then printf '%s\n' "$SORTIE" >&2; abandonner "manifestes invalides : rien n'est déployé"; fi

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
    if ! diff -rq -x __pycache__ "$ANCIENNE/modules/$id" "$DEST/modules/$id" >/dev/null 2>&1; then
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

revenir() {
  avertir "$1 : retour à $(basename "$ANCIENNE")"
  basculer "$ANCIENNE"
  systemctl restart "$UNITE" || avertir "la version précédente ne redémarre pas non plus : voir journalctl -u $UNITE"
  rm -rf "$DEST"
  exit 1
}

dire "bascule"
install -d -o root -g root -m 0755 "$EXTENSIONS_DIR"   # les greffes vivent ici, hors des versions : un déploiement n'y touche jamais
preparer_dossiers             # idempotent : le dossier des demandes au courtier existe aussi sur une installation plus ancienne
creer_premier_admin            # idempotent : fastuser (avec bash) existe après CHAQUE déploiement, pas seulement à l'installation
poser_unite "$DEST"
poser_courtier "$DEST"
basculer "$DEST"
systemctl restart "$UNITE" || { journalctl -u "$UNITE" -n 25 --no-pager >&2; revenir "le noyau ne démarre pas"; }
as_service python3 "$DEST/main.py" etat >/dev/null || revenir "l'état du noyau est illisible"

for id in "${CHANGES[@]}"; do
  as_service python3 "$DEST/main.py" module actif "$id" >/dev/null 2>&1 || continue
  v="$DEST/modules/$id/verifier.sh"
  [ -f "$v" ] || continue
  exporter_pour_modules
  export CASSANDRA_MODULE="$id" CASSANDRA_MODULE_DIR="$PREFIXE/current/modules/$id"
  if [ -f "$DEST/modules/$id/installer.sh" ]; then
    dire "module $id : réinstallation (son installation est idempotente : unité remise à jour, service relancé)"
    (cd "$DEST/modules/$id" && bash ./installer.sh) || revenir "l'installation du module $id échoue"
  fi
  dire "preuve du module $id"
  (cd "$DEST/modules/$id" && bash ./verifier.sh) || revenir "le module $id n'est pas prouvé"
done

# ---------------------------------------------------------------- ménage
# (un grep -v qui ne retient rien rend 1 : sous pipefail ce ménage ferait sortir le script en silence)
{ ls -1dt "$PREFIXE"/releases/*/ 2>/dev/null | sed 's|/$||' | grep -vxF "$DEST" | grep -vxF "$ANCIENNE" | tail -n +"$GARDER" | xargs -r rm -rf; } || true
dire "déployé : $(basename "$DEST") (précédente gardée : $(basename "$ANCIENNE"))"
