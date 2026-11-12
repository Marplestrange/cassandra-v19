#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════
# TITRE      : Vérification du module NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : netbird
# ZONE       : CN
# VERSION CN : 0.1.1  #e477ed
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Vérifie que les commandes root `piloter` et `serveur` sont posées, à root, et que le courtier les atteint ; dit ce qui existe sur la machine (client natif, Docker, conteneur, serveur).
# MÉTHODE    : stat de la commande, `piloter etat` lancée comme le courtier la lance ; le courtier lui-même (cassandra-courtier.path) doit être armé.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=e477ed ▼▼▼
set -u
p="/usr/libexec/cassandra/netbird/piloter"
[ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "netbird : $p absent ou pas à root (CN_install.sh --module netbird)" >&2; exit 3; }
if command -v systemctl >/dev/null 2>&1 && ! systemctl is-active --quiet cassandra-courtier.path 2>/dev/null; then
  echo "netbird : le courtier n'est pas armé (systemctl status cassandra-courtier.path) : le module ne pourra pas piloter Docker" >&2; exit 3
fi
s="/usr/libexec/cassandra/netbird/serveur"
[ -x "$s" ] && [ "$(stat -c %U "$s")" = "root" ] || { echo "netbird : $s absent ou pas à root (CN_install.sh --module netbird)" >&2; exit 3; }
r="$("$p" etat "${CASSANDRA_NETBIRD_CONTENEUR:-netbird}" 2>&1)" || { echo "netbird : la commande ne répond pas : $r" >&2; exit 3; }
rs="$("$s" etat 2>&1)" || { echo "netbird : la commande serveur ne répond pas : $rs" >&2; exit 3; }
echo "netbird : les commandes root répondent ($r ; serveur : $rs)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : commandes/CN_piloter
