#!/bin/sh
# ══════════════════════════════════════════════════════
# TITRE      : Évolution retire, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : evolution
# ZONE       : CN
# VERSION CN : 0.1.0  #433383
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Referme l'ouverture nommée du service (la cage des chercheurs n'a plus ses espaces de noms) ; les outils installés restent.
# MÉTHODE    : supprime le drop-in evolution.conf, recharge systemd et relance le noyau.
# ══════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=433383 ▼▼▼
set -u
if [ -f /etc/systemd/system/cassandra-noyau.service.d/evolution.conf ]; then
  rm -f /etc/systemd/system/cassandra-noyau.service.d/evolution.conf
  systemctl daemon-reload
  systemctl restart cassandra-noyau || true
fi
echo "evolution : ouverture de la cage retirée"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : la préparation de la machine pour la cage des chercheurs.
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/evolution/CN_installer.sh (qui pose l'ouverture), CN_deploy.sh
