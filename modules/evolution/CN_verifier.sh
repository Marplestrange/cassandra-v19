#!/bin/sh
# ══════════════════════════════════════════════════════
# TITRE      : Évolution prouve
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : evolution
# ZONE       : CN
# VERSION CN : 0.1.0  #328020
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Dit si la cage des chercheurs s'ouvre pour le service ; ne bloque JAMAIS un déploiement (la cage est un mieux : sans elle, le chercheur tourne sans enveloppe et l'écran le dit).
# MÉTHODE    : essaie bubblewrap sous l'utilisateur du service et lit la restriction d'espaces de noms du service ; toujours code 0.
# ══════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=328020 ▼▼▼
set -u
: "${CASSANDRA_UTILISATEUR:?}"
command -v bwrap >/dev/null 2>&1 || { echo "evolution : pas de cage (bubblewrap absent) : les chercheurs tournent sans enveloppe"; exit 0; }
if runuser -u "$CASSANDRA_UTILISATEUR" -- bwrap --ro-bind / / --unshare-all --proc /proc --dev /dev true >/dev/null 2>&1; then
  echo "evolution : la cage s'ouvre pour l'utilisateur du service"
else
  echo "evolution : la cage ne s'ouvre pas (espaces de noms interdits par le noyau Linux ?) : les chercheurs tournent sans enveloppe"
fi
if systemctl show cassandra-noyau -p RestrictNamespaces 2>/dev/null | grep -q user; then
  echo "evolution : le service laisse la cage créer ses espaces de noms"
else
  echo "evolution : le service restreint encore les espaces de noms"
fi
exit 0
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : la préparation de la machine pour la cage des chercheurs.
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/evolution/CN_installer.sh, noyau/CN_points.py (bac_os)
