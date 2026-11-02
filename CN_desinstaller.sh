#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le désinstallateur de Cassandra V19
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : (racine)
# ZONE       : CN
# VERSION CN : 0.1.0  #59e040
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Retire Cassandra d'une machine, proprement : les modules par leur propre retrait, les services, puis le dossier ; sans toucher à FastPanel ni aux sites.
# MÉTHODE    : chaque module se retire par SON CN_retirer.sh ; ce que l'installateur a posé AUTOUR (conteneurs, Ollama, outils de sécurité, swap) ne part qu'avec --tout.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=59e040 ▼▼▼
# CN_desinstaller.sh [--oui] [--tout] [--garder-donnees]
#
#   (sans option)        retire Cassandra : ses services, ses modules, son dossier (/var/cassandra) et son utilisateur ; DEMANDE confirmation
#   --oui                ne demande pas (obligatoire sans terminal)
#   --garder-donnees     garde le dossier des données et la configuration (la base, le coffre, les modèles) : une réinstallation les retrouve
#   --tout               retire AUSSI ce que l'installateur a posé autour : conteneurs Vaultwarden et SearXNG (et leurs images), Ollama, le client bw,
#                        les outils de sécurité (Lynis, Trivy, ClamAV), les bibliothèques du sens (torch, sentence-transformers), le swap et les réglages du noyau
#
# Ne touche JAMAIS : FastPanel, les sites, les utilisateurs du panneau (fastuser compris), Docker lui-même, Tailscale, les paquets du système.
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=exploitation/CN_commun.sh
. "$SRC/exploitation/CN_commun.sh"
OUI=0; TOUT=0; GARDER=0
while [ $# -gt 0 ]; do
  case "$1" in
    --oui) OUI=1 ;;
    --tout) TOUT=1 ;;
    --garder-donnees) GARDER=1 ;;
    -h|--aide) sed -n '/^# CN_desinstaller.sh/,/^set -uo/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; exit 0 ;;
    *) echouer "option inconnue : $1 (voir --aide)" ;;
  esac
  shift
done
calculer_chemins
[ "$(id -u)" -eq 0 ] || echouer "à lancer en root"
banniere

echo -e "   ${c_warn}Cassandra va être retirée de cette machine :${c_off}"
echo "     - les services cassandra-*, sensorium, et les modules (par leur propre retrait)"
if [ "$GARDER" -eq 1 ]; then echo "     - le dossier $RACINE SAUF $DONNEES et $CONFIG (gardés)"; else echo "     - le dossier $RACINE ENTIER : la base, les comptes, le coffre, les modèles téléchargés"; fi
[ "$TOUT" -eq 0 ] || echo "     - ET ce qui est posé autour : conteneurs Vaultwarden/SearXNG, Ollama, outils de sécurité, bibliothèques du sens, swap"
echo "     - jamais : FastPanel, les sites, Docker, Tailscale, les utilisateurs du panneau"
if [ "$OUI" -ne 1 ]; then
  [ -t 0 ] || echouer "sans terminal, il faut --oui"
  printf '   Écris OUI pour continuer : '
  read -r reponse
  [ "$reponse" = "OUI" ] || echouer "abandon : rien n'a été retiré"
fi

# ---------------------------------------------------------------- les modules, par leur propre retrait
if [ -d "$PREFIXE/current/modules" ]; then
  exporter_pour_modules
  for d in "$PREFIXE"/current/modules/*/; do
    [ -f "${d}CN_retirer.sh" ] || continue
    export CASSANDRA_MODULE="$(basename "$d")" CASSANDRA_MODULE_DIR="${d%/}"
    dire "module $CASSANDRA_MODULE : retrait"
    (cd "$d" && bash ./CN_retirer.sh) >/dev/null 2>&1 || avertir "le retrait du module $CASSANDRA_MODULE a signalé une erreur (suite)"
  done
fi

# ---------------------------------------------------------------- les services
dire "services"
for u in cassandra-courtier.path cassandra-courtier.service cassandra-vault.service cassandra-panneau.timer cassandra-panneau.service sensorium.service "$UNITE"; do
  systemctl disable --now "$u" >/dev/null 2>&1 || true
done
for u in /etc/systemd/system/cassandra-secu-* /etc/systemd/system/cassandra-courtier.* /etc/systemd/system/cassandra-noyau.service /etc/systemd/system/cassandra-vault.service \
         /etc/systemd/system/cassandra-panneau.* /etc/systemd/system/sensorium.service; do
  [ -e "$u" ] || [ -L "$u" ] || continue
  systemctl disable --now "$(basename "$u")" >/dev/null 2>&1 || true
  rm -f "$u"
done
rm -rf /usr/libexec/cassandra /var/lib/cassandra-securite
systemctl daemon-reload

# ---------------------------------------------------------------- ce qui est posé autour (--tout)
if [ "$TOUT" -eq 1 ]; then
  dire "ce qui est posé autour"
  if command -v docker >/dev/null 2>&1; then
    docker rm -f vaultwarden searxng >/dev/null 2>&1 || true
    docker rmi vaultwarden/server searxng/searxng >/dev/null 2>&1 || true
  fi
  if command -v ollama >/dev/null 2>&1 || [ -f /etc/systemd/system/ollama.service ]; then
    systemctl disable --now ollama >/dev/null 2>&1 || true
    rm -f /etc/systemd/system/ollama.service /usr/local/bin/ollama /usr/bin/ollama
    rm -rf /usr/local/lib/ollama /usr/share/ollama
    userdel ollama >/dev/null 2>&1 || true; groupdel ollama >/dev/null 2>&1 || true
  fi
  rm -f /usr/local/bin/bw
  if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get purge -y -qq lynis clamav clamav-daemon clamav-freshclam trivy >/dev/null 2>&1 || true
    DEBIAN_FRONTEND=noninteractive apt-get autoremove -y -qq >/dev/null 2>&1 || true
  fi
  rm -f /etc/apt/sources.list.d/trivy.list /etc/apt/keyrings/trivy.gpg /usr/share/keyrings/trivy.gpg /usr/local/bin/trivy
  if command -v pip3 >/dev/null 2>&1; then
    pip3 uninstall -y -q --break-system-packages sentence-transformers torch >/dev/null 2>&1 || pip3 uninstall -y -q sentence-transformers torch >/dev/null 2>&1 || true
  fi
  if [ -f /swapfile ]; then swapoff /swapfile >/dev/null 2>&1 || true; sed -i '\#^/swapfile #d' /etc/fstab; rm -f /swapfile; fi
  rm -f /etc/sysctl.d/98-cassandra-securite.conf /etc/sysctl.d/99-cassandra.conf
  rm -f /etc/systemd/system/ollama.service
  systemctl daemon-reload
fi

# ---------------------------------------------------------------- le dossier et l'utilisateur
dire "dossier $RACINE"
if [ "$GARDER" -eq 1 ]; then
  find "$RACINE" -mindepth 1 -maxdepth 1 ! -name "$(basename "$DONNEES")" ! -name "$(basename "$CONFIG")" -exec rm -rf {} + 2>/dev/null || true
else
  rm -rf "${RACINE:?}"
  rm -rf "${UTILISATEURS:?}/${ADMIN_UNIX:?}/data/cassandra"         # son espace Cassandra seulement : le reste du dossier de l'utilisateur est à lui
  userdel "$UTILISATEUR" >/dev/null 2>&1 || true; groupdel "$UTILISATEUR" >/dev/null 2>&1 || true
fi
rm -rf /opt/cassandra-sources.old
echo ""
echo -e "   ${c_ok}✔ Cassandra est retirée.${c_off}  Pour réinstaller : curl -fsSL https://raw.githubusercontent.com/Marplestrange/cassandra-v19/main/CN_amorcer.sh | sudo bash"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
