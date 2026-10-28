#!/bin/sh
# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Voix pose, À ROOT
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : voix
# ZONE       : CN
# VERSION CN : 0.1.0  #8788f2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Voix pose, À ROOT : les trois commandes (écouter, parler, télécharger) que le courtier peut lancer.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8788f2 ▼▼▼
# Voix pose, À ROOT : les trois commandes (écouter, parler, télécharger) que le courtier peut lancer.
set -eu
D="${CASSANDRA_MODULE_DIR:?le dossier du module}"
command -v python3 >/dev/null 2>&1 || { echo "voix : python3 est absent" >&2; exit 3; }
install -d -m 0755 -o root -g root /usr/libexec/cassandra /usr/libexec/cassandra/voix /usr/libexec/cassandra/voix/voix
for c in ecouter parler telecharger; do
  install -m 0755 -o root -g root "$D/commandes/CN_$c" "/usr/libexec/cassandra/voix/$c"
done
# Les bibliothèques de la dictée (faster-whisper) et de la lecture (piper). Lourdes, donc non fatales : sans elles le module
# s'installe et dit ce qui manque ; les modèles eux-mêmes se téléchargent à la demande.
if ! python3 -c 'import faster_whisper, piper' 2>/dev/null; then
  command -v pip3 >/dev/null 2>&1 || { command -v apt-get >/dev/null 2>&1 && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip >/dev/null 2>&1 || true; }
  if command -v pip3 >/dev/null 2>&1; then
    echo "voix : installation de faster-whisper et piper-tts (quelques minutes)"
    pip3 install -q --break-system-packages faster-whisper piper-tts >/dev/null 2>&1 || pip3 install -q faster-whisper piper-tts >/dev/null 2>&1       || echo "voix : bibliothèques non installées (pip3 install faster-whisper piper-tts) ; le module fonctionne sans, la dictée et la lecture non" >&2
  else
    echo "voix : pip3 absent, dictée et lecture indisponibles (pip3 install faster-whisper piper-tts)" >&2
  fi
fi
echo "voix : commandes posées (les modèles se téléchargent à la demande)"
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
