#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Urgence vérifie, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : urgence
# ZONE       : CN
# VERSION CN : 0.2.0  #f32f56
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Urgence vérifie, À ROOT : la commande est posée à root, et elle répond (l'état se lit sans rien changer).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=f32f56 ▼▼▼
# Urgence vérifie, À ROOT : la commande est posée à root, et elle répond (l'état se lit sans rien changer).
set -eu
for c in confiner crise; do
  p="/usr/libexec/cassandra/urgence/$c"
  [ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "urgence : $p absent ou pas à root" >&2; exit 3; }
done
/usr/libexec/cassandra/urgence/confiner etat >/dev/null || { echo "urgence : la commande ne répond pas" >&2; exit 3; }
echo "urgence : prêt"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
