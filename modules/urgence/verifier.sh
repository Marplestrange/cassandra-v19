#!/bin/sh
# Urgence vérifie, À ROOT : la commande est posée à root, et elle répond (l'état se lit sans rien changer).
set -eu
p=/usr/libexec/cassandra/urgence/confiner
[ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "urgence : $p absent ou pas à root" >&2; exit 3; }
"$p" etat >/dev/null || { echo "urgence : la commande ne répond pas" >&2; exit 3; }
echo "urgence : prêt"
