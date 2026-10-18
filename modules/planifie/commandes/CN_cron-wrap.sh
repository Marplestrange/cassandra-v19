#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Enrobage des tâches planifiées Cassandra — version 3
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : CN
# VERSION CN : 0.1.3  #ed9322
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Enrobage des tâches planifiées Cassandra — version 3
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.3 empreinte=ed9322 ▼▼▼
# Enrobage des tâches planifiées Cassandra — version 3
# Exécute la commande, puis dépose un compte rendu dans le spool. Écrit dans un fichier temporaire renommé ensuite : l'ingestion ne lit jamais un compte rendu à moitié écrit.
# Appelé par cron, À ROOT : il ne SOURCE rien que le noyau (sans privilège) puisse écrire. Les options (verrou, fenêtre) sont lues ligne à ligne et seul un chiffre est retenu ;
# la sentinelle de maintenance n'est jamais exécutée, seulement comparée. Le spool est écrit par mktemp (création exclusive), jamais par un nom que le noyau pourrait prévoir.
# Pose : CN_installer.sh du module, qui remplace @SPOOL@, @OPTIONS@, @MAINTENANCE@ et @VERROUS@.
REF="$1"
shift
SPOOL="@SPOOL@"
OPTS="@OPTIONS@"
MAINT="@MAINTENANCE@"
LOCKS="@VERROUS@"
mkdir -p "$LOCKS" 2>/dev/null
SAFE=$(printf '%s' "$REF" | tr -c 'A-Za-z0-9_.-' '_' | cut -c1-120)
VERROU=0; FENETRE=0
if [ -f "$OPTS/$SAFE" ]; then
  V=$(sed -n 's/^verrou=\([01]\)$/\1/p' "$OPTS/$SAFE" 2>/dev/null | head -n 1)
  F=$(sed -n 's/^fenetre=\([0-9]\{1,6\}\)$/\1/p' "$OPTS/$SAFE" 2>/dev/null | head -n 1)
  [ -n "$V" ] && VERROU="$V"
  [ -n "$F" ] && FENETRE="$F"
fi

report() {
  T1=$(date '+%s')
  TMP=$(mktemp "$SPOOL/.run.XXXXXXXX" 2>/dev/null) || return 0
  { echo "$REF|$1|$2|$3"; echo "$4"; } > "$TMP" 2>/dev/null
  chmod 0644 "$TMP" 2>/dev/null
  mv "$TMP" "$SPOOL/$SAFE.$$.$T1" 2>/dev/null
}

START=$(date -u '+%Y-%m-%d %H:%M')
T0=$(date '+%s')

# Maintenance : la sentinelle porte sa date de fin en première ligne, puis les tâches exemptées. Une fin dépassée ne suspend plus rien : un mode qu'on oublie de lever est pire que pas de mode du tout.
if [ -f "$MAINT" ]; then
  FIN=$(head -n 1 "$MAINT" 2>/dev/null)
  MAINTENANT=$(date -u '+%Y-%m-%d %H:%M')
  if [ -n "$FIN" ] && [ "$MAINTENANT" \< "$FIN" ]; then
    if ! grep -qxF "$REF" "$MAINT" 2>/dev/null; then
      report "$START" 0 0 "[Cassandra] non exécutée : mode maintenance jusqu'au $FIN."
      exit 0
    fi
  fi
fi

run() {
  if [ "$FENETRE" -gt 0 ] 2>/dev/null && command -v timeout >/dev/null 2>&1; then
    timeout -k 10 "$FENETRE" sh -c "$*" 2>&1
  else
    sh -c "$*" 2>&1
  fi
}

# Verrou : si l'exécution précédente tourne encore, celle-ci ne démarre pas. On ne l'attend pas : la suivante viendra, et deux copies sur les mêmes fichiers est précisément ce qu'on veut éviter.
if [ "$VERROU" = "1" ] && command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCKS/$SAFE.lock"
  if ! flock -n 9; then
    report "$START" 0 0 "[Cassandra] non démarrée : l'exécution précédente tourne encore."
    exit 0
  fi
fi

OUT=$(run "$*")
CODE=$?
T1=$(date '+%s')
[ "$CODE" = "124" ] && OUT="[Cassandra] fenêtre de $FENETRE s dépassée, commande interrompue.
$OUT"
report "$START" "$(( (T1 - T0) * 1000 ))" "$CODE" "$OUT"
exit $CODE
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
