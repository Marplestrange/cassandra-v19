#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : FastPanel pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : fastpanel
# ZONE       : CN
# VERSION CN : 0.1.0  #282544
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Donne au service de Cassandra la lecture de la base de FastPanel, par une copie rafraîchie chaque minute (la base d'origine reste à root).
# MÉTHODE    : une minuterie systemd lance CN_copie_panneau.py en root ; le réglage « base_panneau » désigne la copie. Sans FastPanel : rien à faire.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=282544 ▼▼▼
set -eu
: "${CASSANDRA_DONNEES:?}" "${CASSANDRA_CONFIG:?}" "${CASSANDRA_UTILISATEUR:?}" "${CASSANDRA_MODULE_DIR:?}" "${CASSANDRA_PREFIXE:?}"
panneau=""
for p in /usr/local/fastpanel2/app/db/fastpanel2.db /usr/local/fastpanel/app/db/fastpanel.db; do
  [ -f "$p" ] && { panneau="$p"; break; }
done
if [ -z "$panneau" ]; then
  echo "fastpanel : aucun FastPanel sur cette machine : le pont reste en veille"
  exit 0
fi
copie="$CASSANDRA_DONNEES/panneau"
install -d -o root -g "$CASSANDRA_UTILISATEUR" -m 0750 "$copie"
python3 "$CASSANDRA_MODULE_DIR/CN_copie_panneau.py" "$panneau" "$copie/fastpanel.db" "$CASSANDRA_UTILISATEUR"
cat > /etc/systemd/system/cassandra-panneau.service <<EOF
[Unit]
Description=Cassandra : copie de la base de FastPanel (lecture seule pour le noyau)

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $CASSANDRA_PREFIXE/current/modules/fastpanel/CN_copie_panneau.py $panneau $copie/fastpanel.db $CASSANDRA_UTILISATEUR
EOF
cat > /etc/systemd/system/cassandra-panneau.timer <<EOF
[Unit]
Description=Cassandra : copie de la base de FastPanel, chaque minute

[Timer]
OnBootSec=30s
OnUnitActiveSec=60s
AccuracySec=5s

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now cassandra-panneau.timer >/dev/null 2>&1
echo "fastpanel : base du panneau copiée chaque minute dans $copie (le module la retrouve seul)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
