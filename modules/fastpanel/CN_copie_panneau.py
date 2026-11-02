# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Copie cohérente de la base de FastPanel
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : fastpanel
# ZONE       : CN
# VERSION CN : 0.1.0  #08f26d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Pose, pour le service de Cassandra, une copie en lecture de la base SQLite de FastPanel (qui n'est lisible que par root).
# MÉTHODE    : lancé par une minuterie systemd en root ; l'API de sauvegarde de SQLite donne une copie cohérente même si la base est en WAL.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=08f26d ▼▼▼
"""python CN_copie_panneau.py SOURCE DESTINATION UTILISATEUR : copie SOURCE vers DESTINATION (0640, root:UTILISATEUR), remplacée d'un coup."""
import grp
import os
import sqlite3
import sys

source, destination, utilisateur = sys.argv[1], sys.argv[2], sys.argv[3]
temporaire = destination + ".new"
try:
    os.unlink(temporaire)
except OSError:
    pass
src = sqlite3.connect("file:%s?mode=ro" % source, uri=True, timeout=10)
dst = sqlite3.connect(temporaire)
with dst:
    src.backup(dst)
dst.close()
src.close()
os.chown(temporaire, 0, grp.getgrnam(utilisateur).gr_gid)
os.chmod(temporaire, 0o640)
os.replace(temporaire, destination)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : à compléter
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
