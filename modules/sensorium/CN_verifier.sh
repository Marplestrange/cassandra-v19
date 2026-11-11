#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La preuve que le Sensorium fonctionne
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.4.0  #a6de37
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La preuve que le Sensorium fonctionne : le service est actif, le collecteur répond, ET le noyau (qui n'est pas root) l'entend aussi.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.0 empreinte=a6de37 ▼▼▼
# La preuve que le Sensorium fonctionne : le service est actif, le collecteur répond, ET le noyau (qui n'est pas root) l'entend aussi.
set -u
sock="/run/sensorium/knowledge.sock"
ping='import socket,sys
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); s.settimeout(10); s.connect(sys.argv[1]); s.sendall(b"PING"); r=s.recv(16); sys.exit(0 if r==b"PONG" else 1)'
# On attend une RÉPONSE, pas un fichier : le fichier-socket d'une installation retirée traîne dans /run et existe avant que le nouveau collecteur n'écoute.
for _ in $(seq 1 90); do
  if systemctl is-active --quiet sensorium.service && [ -S "$sock" ] && python3 -c "$ping" "$sock" >/dev/null 2>&1; then break; fi
  sleep 1
done
systemctl is-active --quiet sensorium.service || { echo "sensorium : le service n'est pas actif" >&2; journalctl -u sensorium.service -n 15 --no-pager >&2; exit 1; }
python3 -c "$ping" "$sock" || { echo "sensorium : le collecteur ne répond pas à PING (root)" >&2; exit 1; }
if [ -n "${CASSANDRA_UTILISATEUR:-}" ]; then
  runuser -u "$CASSANDRA_UTILISATEUR" -- python3 -c "$ping" "$sock" || { echo "sensorium : le noyau (utilisateur $CASSANDRA_UTILISATEUR) ne peut pas joindre le socket" >&2; exit 1; }
fi
for c in redemarrer reparer seuils; do
  p="/usr/libexec/cassandra/sensorium/$c"
  [ -x "$p" ] && [ "$(stat -c %U "$p")" = "root" ] || { echo "sensorium : $p absent ou pas à root" >&2; exit 1; }
done
echo "sensorium : le collecteur répond, au noyau aussi, et sa commande de redémarrage est posée"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
