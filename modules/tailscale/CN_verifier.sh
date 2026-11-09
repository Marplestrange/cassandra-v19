#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Vérification du module Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.4.0  #6ec163
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Vérifie que le client Tailscale existe, que tailscaled répond et que l'utilisateur de Cassandra en est l'opérateur.
# MÉTHODE    : lit les préférences de tailscaled ; l'opérateur est ce qui permet de piloter sans root.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.0 empreinte=6ec163 ▼▼▼
set -u
U="${CASSANDRA_UTILISATEUR:-cassandra}"
command -v tailscale >/dev/null 2>&1 || { echo "tailscale : le client est absent" >&2; exit 3; }
[ -S /var/run/tailscale/tailscaled.sock ] || { echo "tailscale : tailscaled ne tourne pas (systemctl start tailscaled)" >&2; exit 3; }
p="$(tailscale debug prefs 2>/dev/null | tr -d '[:space:]')"
case "$p" in
  *\"OperatorUser\":\"$U\"*) ;;
  *) echo "tailscale : $U n'est pas l'opérateur (tailscale set --operator=$U)" >&2; exit 3 ;;
esac
if command -v systemctl >/dev/null 2>&1 && ! systemctl is-active --quiet cassandra-tailscale-operateur.timer 2>/dev/null; then
  echo "tailscale : (avis) la minuterie qui rend le droit d'opérateur après un retrait du réseau n'est pas active : relancer CN_install.sh --module tailscale" >&2
fi
echo "tailscale : le client répond et $U peut le piloter"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
