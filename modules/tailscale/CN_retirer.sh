#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Retrait du module Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.1.1  #0e7e0b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Retire le droit de pilotage donné à l'utilisateur de Cassandra. Ne déconnecte PAS la machine et ne désinstalle PAS Tailscale : le réseau privé est à l'administrateur.
# MÉTHODE    : `tailscale set --operator=` (vide).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=0e7e0b ▼▼▼
set -u
if command -v tailscale >/dev/null 2>&1; then tailscale set --operator= >/dev/null 2>&1 || true; fi
echo "tailscale : droit de pilotage retiré (la machine reste connectée)"
exit 0
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
