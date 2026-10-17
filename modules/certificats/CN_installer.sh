#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Certificats ne pose rien sur le système
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : certificats
# ZONE       : CN
# VERSION CN : 0.2.0  #ad8288
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Certificats ne pose rien sur le système : il lit le port 443 et tient un registre dans sa base. Il n'exige que le module ssl de Python.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=ad8288 ▼▼▼
# Certificats ne pose rien sur le système : il lit le port 443 et tient un registre dans sa base. Il n'exige que le module ssl de Python.
python3 -c "import ssl, socket" || { echo "certificats : le module ssl de Python manque" >&2; exit 3; }
echo "certificats : prêt (rien à installer)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
