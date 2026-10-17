#!/bin/sh
# La preuve : la mesure dont la sentinelle dépend fonctionne sur cette machine.
df -P / >/dev/null 2>&1 || { echo "sentinelle : df ne répond pas" >&2; exit 1; }
echo "sentinelle : df répond"
exit 0
