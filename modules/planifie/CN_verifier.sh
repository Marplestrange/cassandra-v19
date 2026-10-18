#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La preuve que le module peut travailler
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : CN
# VERSION CN : 0.1.2  #771cf8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La preuve que le module peut travailler : les trois commandes sont à root, l'enrobage est posé, et la lecture des crontabs répond.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.2 empreinte=771cf8 ▼▼▼
# La preuve que le module peut travailler : les trois commandes sont à root, l'enrobage est posé, et la lecture des crontabs répond.
set -eu
for c in lire_crontabs lire_table ecrire_crontab lancer; do
  p="/usr/libexec/cassandra/planifie/$c"
  [ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "planifie : $p absent ou pas à root" >&2; exit 3; }
done
[ -x /usr/local/lib/cassandra/cron-wrap.sh ] || { echo "planifie : l'enrobage manque" >&2; exit 3; }
/usr/libexec/cassandra/planifie/lire_crontabs >/dev/null || { echo "planifie : la lecture des crontabs échoue" >&2; exit 3; }
echo "planifie : prêt"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
