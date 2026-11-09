#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Retrait du module Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.4.1  #bc6434
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Retire le droit de pilotage donné à l'utilisateur de Cassandra. Ne déconnecte PAS la machine et ne désinstalle PAS Tailscale : le réseau privé est à l'administrateur.
# MÉTHODE    : `tailscale set --operator=` (vide).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.1 empreinte=bc6434 ▼▼▼
set -u
# la minuterie d'abord : sinon elle rendrait aussitôt le droit qu'on retire
if command -v systemctl >/dev/null 2>&1; then
  systemctl disable --now cassandra-tailscale-operateur.timer >/dev/null 2>&1 || true
  UN="${CASSANDRA_UNITE:-cassandra-noyau.service}"
  rm -f "/etc/systemd/system/$UN.d/tailscale-netlink.conf"; rmdir "/etc/systemd/system/$UN.d" 2>/dev/null || true
  rm -f /etc/systemd/system/cassandra-tailscale-operateur.timer /etc/systemd/system/cassandra-tailscale-operateur.service /usr/local/sbin/cassandra-tailscale-operateur
  systemctl daemon-reload >/dev/null 2>&1 || true
fi
if command -v tailscale >/dev/null 2>&1; then tailscale set --operator= >/dev/null 2>&1 || true; fi
echo "tailscale : droit de pilotage retiré (la machine reste connectée)"
exit 0
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
