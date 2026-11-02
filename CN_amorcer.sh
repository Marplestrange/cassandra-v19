#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Amorçage de Cassandra V19 en UNE commande, sur un serveur Linux neuf (Debian, Ubuntu, Fedo
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : (racine)
# ZONE       : CN
# VERSION CN : 0.1.0  #b50828
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Amorçage de Cassandra V19 en UNE commande, sur un serveur Linux neuf (Debian, Ubuntu, Fedora, openSUSE, Arch, Alpine).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b50828 ▼▼▼
# Amorçage de Cassandra V19 en UNE commande, sur un serveur Linux neuf (Debian, Ubuntu, Fedora, openSUSE, Arch, Alpine).
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
# Variables : CASSANDRA_DEPOT (autre dépôt), CASSANDRA_BRANCHE (défaut main), CASSANDRA_COMMIT (une version précise, par son empreinte), CASSANDRA_SOURCES (défaut /opt/cassandra-sources).
# Tout ce qui s'affiche est aussi écrit dans /var/log/cassandra-install.log. Contrôle seul, à tout moment : sudo /opt/cassandra-sources/CN_install.sh --controle
# Idempotent : relancé, il met à jour les sources et pose une nouvelle version à côté de l'ancienne (CN_install.sh).
set -euo pipefail

DEPOT="${CASSANDRA_DEPOT:-https://github.com/Marplestrange/cassandra-v19.git}"
BRANCHE="${CASSANDRA_BRANCHE:-main}"
SOURCES="${CASSANDRA_SOURCES:-/opt/cassandra-sources}"
COMMIT="${CASSANDRA_COMMIT:-}"
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1        # aucune question en route : ni apt, ni « redémarrer les services ? »

# --- habillage (comme l'installateur de la V18) ---
if [ -t 1 ] && [ "${NO_COLOR:-0}" != "1" ]; then
  c_off="\033[0m"; c_bold="\033[1m"; c_dim="\033[2m"; c_ok="\033[1;38;5;48m"; c_warn="\033[1;38;5;214m"; c_err="\033[1;38;5;203m"
  c_inf="\033[38;5;111m"; c_acc="\033[1;38;5;147m"
  L1="\033[38;5;141m"; L2="\033[38;5;134m"; L3="\033[38;5;105m"; L4="\033[38;5;75m"; L5="\033[38;5;81m"; L6="\033[38;5;51m"
else
  c_off=""; c_bold=""; c_dim=""; c_ok=""; c_warn=""; c_err=""; c_inf=""; c_acc=""; L1=""; L2=""; L3=""; L4=""; L5=""; L6=""
fi
banniere() {
  [ "${CASSANDRA_BANNIERE_FAITE:-0}" = "1" ] && return 0
  export CASSANDRA_BANNIERE_FAITE=1
  echo ""
  echo -e "${L1}      ██████╗ █████╗ ███████╗███████╗ █████╗ ███╗   ██╗██████╗ ██████╗  █████╗ ${c_off}"
  echo -e "${L2}     ██╔════╝██╔══██╗██╔════╝██╔════╝██╔══██╗████╗  ██║██╔══██╗██╔══██╗██╔══██╗${c_off}"
  echo -e "${L3}     ██║     ███████║███████╗███████╗███████║██╔██╗ ██║██║  ██║██████╔╝███████║${c_off}"
  echo -e "${L4}     ██║     ██╔══██║╚════██║╚════██║██╔══██║██║╚██╗██║██║  ██║██╔══██╗██╔══██║${c_off}"
  echo -e "${L5}     ╚██████╗██║  ██║███████║███████║██║  ██║██║ ╚████║██████╔╝██║  ██║██║  ██║${c_off}"
  echo -e "${L6}      ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝${c_off}"
  echo ""
  echo -e "        ${c_bold}IA souveraine d'administration système${c_off}  ${c_dim}·${c_off}  ${c_acc}modulaire${c_off}  ${c_dim}·  v19${c_off}"
  echo -e "${c_dim}      ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${c_off}"
  echo ""
}
_T0="$(date +%s)"; export _T0
dire() { echo -e "${c_acc}  ┃${c_off} ${c_bold}$*${c_off}"; }
echouer() { echo -e "\n   ${c_err}✘ $*${c_off}\n" >&2; exit 1; }
banniere

[ "$(id -u)" -eq 0 ] || echouer "à lancer en root (sudo bash …)"
JOURNAL_INSTALL=/var/log/cassandra-install.log
if [ -z "${CASSANDRA_JOURNALISE:-}" ]; then
  export CASSANDRA_JOURNALISE=1
  printf '\n======== %s : amorçage ========\n' "$(date '+%Y-%m-%d %H:%M:%S')" >> "$JOURNAL_INSTALL"
  exec > >(tee -a "$JOURNAL_INSTALL") 2>&1
fi
if command -v flock >/dev/null 2>&1; then
  exec 9>/var/lock/cassandra-install.lock
  flock -n 9 || echouer "une autre installation de Cassandra tourne déjà (verrou /var/lock/cassandra-install.lock)"
fi
# Si quelque chose s'arrête en route : dire où lire, et que relancer est sans danger (chaque étape se reprend là où elle en est).
fin_amorcage() {
  local rc=$?
  [ "$rc" -eq 0 ] || echo -e "\n   ${c_err}✘ L'installation s'est arrêtée (code $rc).${c_off}\n   ${c_dim}Le journal : $JOURNAL_INSTALL · relancer la même commande est sans danger : elle reprend où elle en était.${c_off}\n" >&2
}
trap fin_amorcage EXIT
command -v systemctl >/dev/null 2>&1 || echouer "systemd est nécessaire : Cassandra s'installe comme un service"

manque=()
command -v git >/dev/null 2>&1 || manque+=(git)
command -v python3 >/dev/null 2>&1 || manque+=(python3)
command -v curl >/dev/null 2>&1 || manque+=(curl)
if [ "${#manque[@]}" -gt 0 ]; then
  dire "installation de : ${manque[*]}"
  if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${manque[@]}"
  elif command -v dnf >/dev/null 2>&1; then dnf install -y -q "${manque[@]}"
  elif command -v yum >/dev/null 2>&1; then yum install -y -q "${manque[@]}"
  elif command -v zypper >/dev/null 2>&1; then zypper --non-interactive install "${manque[@]}"
  elif command -v pacman >/dev/null 2>&1; then pacman -S --noconfirm --needed "${manque[@]}"
  elif command -v apk >/dev/null 2>&1; then apk add -q "${manque[@]}"
  else echouer "installez d'abord : ${manque[*]} (aucun gestionnaire de paquets connu)"
  fi
fi

dire "sources dans $SOURCES"
if [ -d "$SOURCES/.git" ]; then
  git -C "$SOURCES" fetch --quiet origin "${COMMIT:-$BRANCHE}" || echouer "le dépôt $DEPOT est injoignable ou la version « ${COMMIT:-$BRANCHE} » n'existe pas"
  if [ -n "$COMMIT" ]; then git -C "$SOURCES" reset --quiet --hard FETCH_HEAD
  else git -C "$SOURCES" checkout --quiet "$BRANCHE" && git -C "$SOURCES" reset --quiet --hard "origin/$BRANCHE"; fi
else
  rm -rf "$SOURCES"
  if [ -n "$COMMIT" ]; then
    git init --quiet "$SOURCES" && git -C "$SOURCES" fetch --quiet --depth 1 "$DEPOT" "$COMMIT" && git -C "$SOURCES" reset --quiet --hard FETCH_HEAD \
      || echouer "impossible de récupérer la version $COMMIT de $DEPOT"
  else
    git clone --quiet --depth 1 --branch "$BRANCHE" "$DEPOT" "$SOURCES" || echouer "impossible de cloner $DEPOT (réseau ? dépôt privé ?)"
  fi
fi

cd "$SOURCES"
chmod +x CN_install.sh
dire "installation (noyau et modules)"
if [ "$#" -gt 0 ]; then
  ./CN_install.sh "$@"
else
  ./CN_install.sh --tous
fi

echo -e "${c_dim}   Mises à jour : relancez la même commande (ou ./CN_deploy.sh dans $SOURCES).${c_off}"
echo ""
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
