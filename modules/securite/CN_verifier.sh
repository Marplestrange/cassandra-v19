#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sécurité vérifie, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : CN
# VERSION CN : 0.3.4  #b7417f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Sécurité vérifie, À ROOT : les deux commandes sont posées, à root, exécutables.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.4 empreinte=b7417f ▼▼▼
# Sécurité vérifie, À ROOT : les deux commandes sont posées, à root, exécutables.
set -eu
for c in mesurer agir outils; do
  p="/usr/libexec/cassandra/securite/$c"
  [ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "securite : $p absent ou pas à root" >&2; exit 1; }
done
echo "securite : commandes présentes"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
