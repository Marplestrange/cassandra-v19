#!/usr/bin/env bash
# pousser.sh : envoie le dépôt sur une machine par SSH et y lance install.sh ou deploy.sh.
#
#   outils/pousser.sh amizo install --tous        première installation, tous les modules
#   outils/pousser.sh amizo install --module dns
#   outils/pousser.sh amizo deploy                mise à jour
#   outils/pousser.sh amizo deploy --a-blanc      voir ce qui changerait
#
# Pas besoin de Git ni d'accès au dépôt sur la machine cible : l'arbre de travail part par tar sur SSH.
set -euo pipefail
[ $# -ge 2 ] || { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 2; }
HOTE="$1"; ACTION="$2"; shift 2
case "$ACTION" in install|deploy) ;; *) echo "action inconnue : $ACTION (install | deploy)" >&2; exit 2 ;; esac
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREPARATION="/root/cassandra-v19-envoi"

tar -C "$RACINE" --exclude=.git --exclude=__pycache__ --exclude=donnees --exclude='*.db*' -cf - . \
  | ssh -o BatchMode=yes "$HOTE" "rm -rf $PREPARATION && mkdir -p $PREPARATION && tar -C $PREPARATION -xf -"
# shellcheck disable=SC2029
ssh -o BatchMode=yes "$HOTE" "cd $PREPARATION && bash ./$ACTION.sh $*"
