#!/bin/sh
# ══════════════════════════════════════════════════════
# TITRE      : Évolution pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : evolution
# ZONE       : CN
# VERSION CN : 0.1.0  #3ae2c3
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Prépare la machine pour installer des chercheurs et les enfermer : le module d'environnements de Python (python3-venv), la cage (bubblewrap), et l'ouverture NOMMÉE du service qui laisse la cage créer ses espaces de noms.
# MÉTHODE    : idempotent ; les outils manquants sont installés par le gestionnaire de paquets de la machine ; l'ouverture est un drop-in systemd nommé « evolution.conf », retiré par CN_retirer.sh ; le service n'est relancé que si elle change.
# ══════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3ae2c3 ▼▼▼
set -eu
manquants=""
python3 -c "import ensurepip" >/dev/null 2>&1 || manquants="$manquants python3-venv"
command -v bwrap >/dev/null 2>&1 || manquants="$manquants bubblewrap"
if [ -n "$manquants" ]; then
  if command -v apt-get >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $manquants >/dev/null || echo "evolution : installe à la main :$manquants" >&2
  elif command -v dnf >/dev/null 2>&1; then
    dnf install -y -q $(echo "$manquants" | sed 's/python3-venv//') >/dev/null || echo "evolution : installe à la main :$manquants" >&2
  elif command -v zypper >/dev/null 2>&1; then
    zypper -q install -y $(echo "$manquants" | sed 's/python3-venv//') >/dev/null || echo "evolution : installe à la main :$manquants" >&2
  else
    echo "evolution : installe à la main :$manquants" >&2
  fi
fi
d=/etc/systemd/system/cassandra-noyau.service.d
install -d -m 0755 "$d"
nouveau=$(mktemp)
printf '%s\n' '[Service]' \
  '# Ouverture demandée par le module Évolution : la cage des chercheurs (bubblewrap) crée des espaces de noms (utilisateur, réseau, processus, montage)' \
  '# pour enfermer un chercheur sans réseau ni accès au serveur. Sans elle, le chercheur tourne sans cage.' \
  'RestrictNamespaces=user net ipc uts pid mnt' > "$nouveau"
if ! cmp -s "$nouveau" "$d/evolution.conf" 2>/dev/null; then
  install -m 0644 "$nouveau" "$d/evolution.conf"
  systemctl daemon-reload
  systemctl restart cassandra-noyau
  echo "evolution : la cage des chercheurs est ouverte au service (drop-in evolution.conf), noyau relancé"
else
  echo "evolution : la cage des chercheurs est déjà ouverte au service"
fi
rm -f "$nouveau"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : la préparation de la machine pour la cage des chercheurs.
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : noyau/CN_points.py (bac_os : la cage), noyau/CN_installateur.py (qui installe les chercheurs), CN_deploy.sh (qui relance ce fichier à chaque mise à jour du module)
