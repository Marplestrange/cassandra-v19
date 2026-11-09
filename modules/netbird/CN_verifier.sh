#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
# TITRE      : Vérification du module NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : netbird
# ZONE       : CN
# VERSION CN : 0.1.0  #2cd3b0
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Vérifie que la commande root `piloter` est posée, à root, et que le courtier l'atteint ; dit ce qui existe sur la machine (client natif, Docker, conteneur).
# MÉTHODE    : stat de la commande, `piloter etat` lancée comme le courtier la lance ; le courtier lui-même (cassandra-courtier.path) doit être armé.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=2cd3b0 ▼▼▼
set -u
p="/usr/libexec/cassandra/netbird/piloter"
[ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "netbird : $p absent ou pas à root (CN_install.sh --module netbird)" >&2; exit 3; }
if command -v systemctl >/dev/null 2>&1 && ! systemctl is-active --quiet cassandra-courtier.path 2>/dev/null; then
  echo "netbird : le courtier n'est pas armé (systemctl status cassandra-courtier.path) : le module ne pourra pas piloter Docker" >&2; exit 3
fi
r="$("$p" etat "${CASSANDRA_NETBIRD_CONTENEUR:-netbird}" 2>&1)" || { echo "netbird : la commande ne répond pas : $r" >&2; exit 3; }
echo "netbird : la commande root répond ($r)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : commandes/CN_piloter
