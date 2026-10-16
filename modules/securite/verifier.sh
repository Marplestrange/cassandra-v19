#!/bin/sh
# Sécurité vérifie, À ROOT : les deux commandes sont posées, à root, exécutables.
set -eu
for c in mesurer agir; do
  p="/usr/libexec/cassandra/securite/$c"
  [ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "securite : $p absent ou pas à root" >&2; exit 1; }
done
echo "securite : commandes présentes"
