#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : CN_pousser.sh
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #cf3b08
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : CN_pousser.sh : envoie le dépôt sur une machine par SSH et y lance CN_install.sh ou CN_deploy.sh.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=cf3b08 ▼▼▼
# CN_pousser.sh : envoie le dépôt sur une machine par SSH et y lance CN_install.sh ou CN_deploy.sh.
#
#   outils/CN_pousser.sh amizo install --tous        première installation, tous les modules
#   outils/CN_pousser.sh amizo install --module dns
#   outils/CN_pousser.sh amizo deploy                mise à jour
#   outils/CN_pousser.sh amizo deploy --a-blanc      voir ce qui changerait
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
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
