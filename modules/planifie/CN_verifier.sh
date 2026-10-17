#!/bin/sh
# La preuve que le module peut travailler : les trois commandes sont à root, l'enrobage est posé, et la lecture des crontabs répond.
set -eu
for c in lire_crontabs lire_table ecrire_crontab lancer; do
  p="/usr/libexec/cassandra/planifie/$c"
  [ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "planifie : $p absent ou pas à root" >&2; exit 3; }
done
[ -x /usr/local/lib/cassandra/cron-wrap.sh ] || { echo "planifie : l'enrobage manque" >&2; exit 3; }
/usr/libexec/cassandra/planifie/lire_crontabs >/dev/null || { echo "planifie : la lecture des crontabs échoue" >&2; exit 3; }
echo "planifie : prêt"
