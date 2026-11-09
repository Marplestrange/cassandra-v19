#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Installation du module Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.4.1  #4a54e4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Pose le client Tailscale s'il manque, le démarre, et donne à l'utilisateur de Cassandra le droit de le piloter (--operator) pour que l'interface connecte la machine sans root.
# MÉTHODE    : l'installateur officiel de Tailscale ; `tailscale set --operator` ne touche ni la connexion ni les réglages réseau.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.1 empreinte=4a54e4 ▼▼▼
set -eu
set -o pipefail                  # sans cela, un curl en échec donne un script vide à `sh` et l'installation « réussit » sans rien poser
U="${CASSANDRA_UTILISATEUR:-cassandra}"
if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale : installation (installateur officiel)"
  J="$(mktemp)"; S="$(mktemp)"
  # Le script est d'abord téléchargé EN ENTIER puis exécuté : un téléchargement coupé en route ne s'exécute pas à moitié (ce que `curl | sh` permet).
  if ! curl -fsSL -o "$S" https://tailscale.com/install.sh || [ ! -s "$S" ] || ! head -n1 "$S" | grep -q '^#!'; then
    rm -f "$J" "$S"; echo "tailscale : téléchargement de l'installateur impossible (https://tailscale.com/download)" >&2; exit 3
  fi
  if ! sh "$S" >"$J" 2>&1; then
    tail -n 5 "$J" >&2; rm -f "$J" "$S"                  # la raison est dite, pas jetée
    echo "tailscale : installation impossible (https://tailscale.com/download)" >&2; exit 3
  fi
  rm -f "$J" "$S"
fi
systemctl enable --now tailscaled >/dev/null 2>&1 || echo "tailscale : systemctl n'a pas pu démarrer tailscaled (il tourne peut-être autrement)" >&2
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -S /var/run/tailscale/tailscaled.sock ] && break; sleep 1; done
[ -S /var/run/tailscale/tailscaled.sock ] || { echo "tailscale : tailscaled ne répond pas (pas de socket après 10 s)" >&2; exit 3; }
tailscale set --operator="$U" >/dev/null 2>&1 || { echo "tailscale : le droit de pilotage n'a pas pu être donné à $U" >&2; exit 3; }

# `tailscale logout` (« Retirer du réseau ») efface les préférences, l'opérateur compris : Cassandra ne peut plus rien piloter et le client exige root pour le rendre. Une minuterie
# root, toutes les 15 s, rend le droit SI l'opérateur est ABSENT (jamais s'il est un autre compte : c'est le choix de l'administrateur).
if command -v systemctl >/dev/null 2>&1 && [ -d /etc/systemd/system ]; then
  cat > /usr/local/sbin/cassandra-tailscale-operateur <<'SCRIPT'
#!/bin/sh
U="${CASSANDRA_UTILISATEUR:-cassandra}"
command -v tailscale >/dev/null 2>&1 || exit 0
p="$(tailscale debug prefs 2>/dev/null | tr -d '[:space:]')"
[ -n "$p" ] || exit 0
case "$p" in *\"OperatorUser\":\"[!\"]*) exit 0 ;; esac
tailscale set --operator="$U" >/dev/null 2>&1 || true
SCRIPT
  chmod 755 /usr/local/sbin/cassandra-tailscale-operateur
  cat > /etc/systemd/system/cassandra-tailscale-operateur.service <<UNITE
[Unit]
Description=Cassandra : rendre le droit d'opérateur Tailscale s'il manque
After=tailscaled.service

[Service]
Type=oneshot
Environment=CASSANDRA_UTILISATEUR=$U
ExecStart=/usr/local/sbin/cassandra-tailscale-operateur
UNITE
  cat > /etc/systemd/system/cassandra-tailscale-operateur.timer <<'UNITE'
[Unit]
Description=Cassandra : surveiller le droit d'opérateur Tailscale

[Timer]
OnBootSec=20s
OnUnitActiveSec=15s
AccuracySec=1s

[Install]
WantedBy=timers.target
UNITE
  # `tailscale netcheck` (« Santé du réseau ») interroge lui-même les routes de la machine par netlink, que l'unité du noyau interdit (RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6) :
  # « netlinkrib: address family not supported ». Un complément AJOUTE AF_NETLINK à la liste (les valeurs se cumulent) : le service lit les routes et les adresses, sans aucune
  # capacité réseau pour les changer. Il prend effet au prochain démarrage du noyau ; CN_retirer.sh le retire.
  UN="${CASSANDRA_UNITE:-cassandra-noyau.service}"
  mkdir -p "/etc/systemd/system/$UN.d"
  cat > "/etc/systemd/system/$UN.d/tailscale-netlink.conf" <<'UNITE'
[Service]
RestrictAddressFamilies=AF_NETLINK
UNITE
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable --now cassandra-tailscale-operateur.timer >/dev/null 2>&1 || echo "tailscale : la minuterie du droit d'opérateur n'a pas pu démarrer" >&2
fi
echo "tailscale : prêt ($U peut le piloter)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
