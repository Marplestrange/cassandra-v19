#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : CN_install.sh
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : (racine)
# ZONE       : CN
# VERSION CN : 0.1.0  #54532a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : CN_install.sh : installe le NOYAU de Cassandra V19 et, à la demande, ses modules.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=54532a ▼▼▼
# CN_install.sh : installe le NOYAU de Cassandra V19 et, à la demande, ses modules.
#
#   ./CN_install.sh                         le noyau seul, dans UN dossier : /var/cassandra
#   ./CN_install.sh --module certificats    le noyau + ce module et ses dépendances (dns)
#   ./CN_install.sh --tous                  le noyau + tous les modules du dossier modules/
#   ./CN_install.sh --retirer certificats   retire un module (son CN_retirer.sh, puis son état)
#   ./CN_install.sh --extension ./sentinelle   GREFFE un module après coup, à chaud : copié dans extensions/ (que
#                                        CN_deploy.sh ne touche jamais), prouvé, activé ; le noyau le branche sans redémarrer
#   ./CN_install.sh --extension mod.cmod [--non-signe]   un PAQUET : vérifié (intégrité, signature d'une clé de config/cles/) avant tout
#   ./CN_install.sh --racine /srv/cassandra    un autre dossier racine ;  --admin NOM : le premier administrateur (défaut : fastuser)
#
# La disposition (un dossier pour Cassandra, les dossiers des utilisateurs à la manière de FastPanel) est décrite dans
# exploitation/CN_commun.sh. Une ancienne installation (/opt, /var/lib, /etc) est migrée dans le dossier unique.
#
# Idempotent : relancé, il pose une nouvelle version à côté de l'ancienne (releases/) et bascule d'un coup.
# Chaque module s'installe par SON script (modules/<id>/CN_installer.sh), se prouve par SA vérification
# (CN_verifier.sh) et, si la preuve manque, se retire seul par SON retrait (CN_retirer.sh).
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=exploitation/CN_commun.sh
. "$SRC/exploitation/CN_commun.sh"
MODULES=()
EXTENSIONS=()
RETIRER=""
TOUS=0
SANS_SERVICE=0
NON_SIGNE=0

aide() { sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
  case "$1" in
    --module)       [ $# -ge 2 ] || echouer "--module attend un identifiant"; MODULES+=("$2"); shift 2 ;;
    --tous)         TOUS=1; shift ;;
    --retirer)      [ $# -ge 2 ] || echouer "--retirer attend un identifiant"; RETIRER="$2"; shift 2 ;;
    --extension)    [ $# -ge 2 ] || echouer "--extension attend un dossier"; EXTENSIONS+=("$2"); shift 2 ;;
    # shellcheck disable=SC2034  # lus par calculer_chemins (exploitation/CN_commun.sh)
    --racine)       [ $# -ge 2 ] || echouer "--racine attend un dossier"; CASSANDRA_RACINE="$2"; shift 2 ;;
    # shellcheck disable=SC2034
    --admin)        [ $# -ge 2 ] || echouer "--admin attend un nom d'utilisateur"; CASSANDRA_ADMIN="$2"; shift 2 ;;
    --non-signe)    NON_SIGNE=1; shift ;;
    --sans-service) SANS_SERVICE=1; shift ;;
    -h|--aide)      aide ;;
    *)              echouer "option inconnue : $1 (voir --aide)" ;;
  esac
done
calculer_chemins

[ "$(id -u)" -eq 0 ] || echouer "à lancer en root"

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

# Les dépendances du noyau : « cryptography » (les secrets, l'IBAN, WebAuthn) est INDISPENSABLE ; le reste sert aux gestes
# (openssl : certificats ; sudo/cron : planifié ; iptables : urgence ; ssh : flotte). Installés par apt quand ils manquent.
assurer_dependances() {
  python3 -c 'import cryptography' 2>/dev/null && return 0
  if command -v apt-get >/dev/null 2>&1; then
    dire "dépendances : python3-cryptography et outils système (apt)"
    DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-cryptography openssl sudo cron iptables openssh-client curl >/dev/null       || avertir "apt n'a pas tout installé : voir ci-dessus"
  fi
  python3 -c 'import cryptography' 2>/dev/null || echouer "la bibliothèque Python « cryptography » manque (apt install python3-cryptography, ou pip install cryptography) : sans elle, aucun secret ne s'écrit"
}

# ---------------------------------------------------------------- un module
# Un module greffé vit dans extensions/ ; un module livré avec le noyau, dans la version courante.
dossier_module() { # id
  if [ -d "$EXTENSIONS_DIR/$1" ]; then printf '%s' "$EXTENSIONS_DIR/$1"; else printf '%s' "$PREFIXE/current/modules/$1"; fi
}

env_module() { # id
  exporter_pour_modules
  export CASSANDRA_MODULE="$1"
  CASSANDRA_MODULE_DIR="$(dossier_module "$1")"; export CASSANDRA_MODULE_DIR
}

# L'état des modules (installé, actif) vit dans la base du noyau ; le menu des modules et ce script lisent le même.
etat_module() { as_service python3 "$PREFIXE/current/CN_main.py" module "$@"; }
actif() { etat_module actif "$1" >/dev/null 2>&1; }

installer_module() { # id
  local id="$1" d
  d="$(dossier_module "$1")"
  [ -d "$d" ] || echouer "module introuvable : $id"
  dire "module $id : installation"
  env_module "$id"
  if [ -f "$d/CN_installer.sh" ]; then
    (cd "$d" && bash ./CN_installer.sh) || { avertir "module $id : l'installation a échoué, retrait"; retirer_script "$id"; echouer "module $id non installé"; }
  fi
  if [ -f "$d/CN_verifier.sh" ]; then
    if ! (cd "$d" && bash ./CN_verifier.sh); then
      avertir "module $id : la vérification échoue, retrait"
      retirer_script "$id"
      echouer "module $id non installé (pas de preuve qu'il fonctionne)"
    fi
  fi
  etat_module installe "$id"
  etat_module activer "$id" --sans-dependances || echouer "module $id installé mais non activé"
  dire "module $id : installé, prouvé et actif"
}

retirer_script() { # id : le CN_retirer.sh seul, sans toucher à l'état
  local d
  d="$(dossier_module "$1")"
  env_module "$1"
  if [ -f "$d/CN_retirer.sh" ]; then (cd "$d" && bash ./CN_retirer.sh) || true; fi
}

installation_presente() {
  [ -L "$RACINE/current" ] || echouer "aucune installation dans $RACINE : lancer d'abord ./CN_install.sh (il migre l'ancienne disposition si besoin)"
}

# ---------------------------------------------------------------- retrait d'un module
if [ -n "$RETIRER" ]; then
  installation_presente
  [ -d "$(dossier_module "$RETIRER")" ] || echouer "module introuvable : $RETIRER"
  dire "module $RETIRER : retrait"
  retirer_script "$RETIRER"
  etat_module desactiver "$RETIRER" --en-cascade --forcer >/dev/null 2>&1 || true
  etat_module oublier "$RETIRER"
  # un module greffé s'efface avec son dossier ; le noyau, lui, garde en mémoire ce qu'il avait branché jusqu'au prochain démarrage
  if [ -d "$EXTENSIONS_DIR/$RETIRER" ]; then rm -rf "${EXTENSIONS_DIR:?}/$RETIRER"; fi
  systemctl restart "$UNITE"
  dire "module $RETIRER retiré"
  exit 0
fi

# ---------------------------------------------------------------- greffe d'une extension (à chaud)
if [ "${#EXTENSIONS[@]}" -gt 0 ]; then
  installation_presente
  install -d -o root -g root -m 0755 "$EXTENSIONS_DIR"
  for src in "${EXTENSIONS[@]}"; do
    if [ -f "$src" ]; then
      # un paquet : intégrité et signature vérifiées AVANT d'être déposé où que ce soit
      DEPOT="$(mktemp -d)"
      drapeau=(); [ "$NON_SIGNE" -eq 1 ] && drapeau=(--non-signe)
      if ! RES="$(CASSANDRA_CONFIG="$CONFIG" python3 "$PREFIXE/current/CN_main.py" paquet extraire "$src" "$DEPOT" "${drapeau[@]}" 2>&1)"; then
        rm -rf "$DEPOT"; echouer "paquet refusé : $RES"
      fi
      dire "paquet : $RES"
      src="$DEPOT/${RES%% *}"
    fi
    [ -f "$src/CN_manifeste.toml" ] || echouer "$src : pas de CN_manifeste.toml"
    id="$(basename "$(cd "$src" && pwd)")"
    dire "extension $id : dépôt dans $EXTENSIONS_DIR"
    rm -rf "${EXTENSIONS_DIR:?}/$id"
    cp -r "$src" "$EXTENSIONS_DIR/$id"
    chown -R root:root "$EXTENSIONS_DIR/$id"; chmod -R go-w "$EXTENSIONS_DIR/$id"
    if ! SORTIE="$(cd "$PREFIXE/current" && CASSANDRA_EXTENSIONS="$EXTENSIONS_DIR" python3 CN_main.py verifier 2>&1)"; then
      printf '%s\n' "$SORTIE" >&2; rm -rf "${EXTENSIONS_DIR:?}/$id"; echouer "extension $id refusée : rien n'est greffé"
    fi
    # ses dépendances livrées avec le noyau d'abord, puis elle
    while read -r m; do
      [ -n "$m" ] || continue
      if [ "$m" = "$id" ] || ! actif "$m"; then installer_module "$m"; fi
    done < <(cd "$PREFIXE/current" && CASSANDRA_EXTENSIONS="$EXTENSIONS_DIR" python3 CN_main.py ordre "$id")
  done
  if systemctl is-active --quiet "$UNITE"; then
    dire "le noyau branche l'extension à chaud (sans redémarrer)"
    sleep 7
    as_service python3 "$PREFIXE/current/CN_main.py" moteurs || true
  fi
  exit 0
fi

# ---------------------------------------------------------------- le noyau
verifier_python
assurer_dependances
migrer_ancienne_disposition

dire "dossiers : $RACINE (Cassandra), $UTILISATEURS/<utilisateur> (les utilisateurs, comme FastPanel)"
preparer_dossiers
creer_premier_admin

STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="$RACINE/releases/$STAMP"
dire "version $STAMP"
mkdir -p "$DEST"
tar -C "$SRC" --exclude=.git --exclude=__pycache__ --exclude=donnees --exclude='*.db*' -cf - . | tar -C "$DEST" -xf -
chown -R root:root "$DEST"; chmod -R go-w "$DEST"

dire "vérification des manifestes avant bascule"
if ! SORTIE="$(cd "$DEST" && python3 CN_main.py verifier 2>&1)"; then
  printf '%s\n' "$SORTIE" >&2; rm -rf "$DEST"; echouer "manifestes invalides : rien n'est installé"
fi

basculer "$DEST"

dire "service systemd (l'unité vit dans $CONFIG, liée depuis /etc/systemd/system)"
poser_unite "$DEST"
poser_courtier "$DEST"

demarrer() {
  [ "$SANS_SERVICE" -eq 0 ] || return 0
  systemctl enable "$UNITE" >/dev/null 2>&1
  systemctl restart "$UNITE" || { journalctl -u "$UNITE" -n 25 --no-pager >&2; echouer "le noyau ne démarre pas"; }
}

dire "démarrage du noyau (le service annonce lui-même qu'il est prêt)"
demarrer

if [ "$TOUS" -eq 1 ]; then
  mapfile -t MODULES < <(cd "$DEST" && CASSANDRA_EXTENSIONS="" python3 CN_main.py ordre)
elif [ "${#MODULES[@]}" -gt 0 ]; then
  mapfile -t MODULES < <(cd "$DEST" && CASSANDRA_EXTENSIONS="" python3 CN_main.py ordre "${MODULES[@]}")
fi
# Un module qui échoue ne fait pas tomber le noyau : il est retiré et le noyau continue avec les précédents.
for m in "${MODULES[@]}"; do installer_module "$m"; done

if [ "$SANS_SERVICE" -eq 0 ]; then
  dire "état du noyau"
  as_service python3 "$PREFIXE/current/CN_main.py" etat
fi
dire "terminé : noyau $STAMP${MODULES[*]:+, modules : ${MODULES[*]}}"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
