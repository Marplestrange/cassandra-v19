#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Installation du module Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.1.2  #802b03
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Pose le client Tailscale s'il manque, le démarre, et donne à l'utilisateur de Cassandra le droit de le piloter (--operator) pour que l'interface connecte la machine sans root.
# MÉTHODE    : l'installateur officiel de Tailscale ; `tailscale set --operator` ne touche ni la connexion ni les réglages réseau.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.2 empreinte=802b03 ▼▼▼
set -eu
set -o pipefail                  # sans cela, un curl en échec donne un script vide à `sh` et l'installation « réussit » sans rien poser
U="${CASSANDRA_UTILISATEUR:-cassandra}"
if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale : installation (installateur officiel)"
  J="$(mktemp)"
  if ! curl -fsSL https://tailscale.com/install.sh | sh >"$J" 2>&1; then
    tail -n 5 "$J" >&2; rm -f "$J"                       # la raison est dite, pas jetée
    echo "tailscale : installation impossible (https://tailscale.com/download)" >&2; exit 3
  fi
  rm -f "$J"
fi
systemctl enable --now tailscaled >/dev/null 2>&1 || echo "tailscale : systemctl n'a pas pu démarrer tailscaled (il tourne peut-être autrement)" >&2
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -S /var/run/tailscale/tailscaled.sock ] && break; sleep 1; done
[ -S /var/run/tailscale/tailscaled.sock ] || { echo "tailscale : tailscaled ne répond pas (pas de socket après 10 s)" >&2; exit 3; }
tailscale set --operator="$U" >/dev/null 2>&1 || { echo "tailscale : le droit de pilotage n'a pas pu être donné à $U" >&2; exit 3; }
echo "tailscale : prêt ($U peut le piloter)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
