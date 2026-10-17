#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La preuve que le module peut travailler
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : certificats
# ZONE       : CN
# VERSION CN : 0.2.0  #fcf3a8
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La preuve que le module peut travailler : Python sait ouvrir une connexion TLS vérifiée.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=fcf3a8 ▼▼▼
# La preuve que le module peut travailler : Python sait ouvrir une connexion TLS vérifiée.
python3 -c "import ssl; ssl.create_default_context()" || { echo "certificats : pas de contexte TLS" >&2; exit 3; }
echo "certificats : TLS disponible"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
