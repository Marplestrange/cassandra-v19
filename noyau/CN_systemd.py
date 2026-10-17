# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Dialogue avec systemd (sd_notify), bibliothèque standard seule
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #be7335
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Dialogue avec systemd (sd_notify), bibliothèque standard seule.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=be7335 ▼▼▼
"""Dialogue avec systemd (sd_notify), bibliothèque standard seule.

Le service est de type `notify` : systemd n'estime le noyau démarré que lorsqu'il l'annonce (READY=1),
et le tue puis le relance s'il cesse de donner signe de vie (WATCHDOG=1). Une boucle figée se voit donc
de l'extérieur, ce qu'aucun test interne ne peut garantir.
"""
from __future__ import annotations

import os
import socket


def notifier(message: str) -> bool:
    """Envoie un message à systemd. Rend False hors systemd (développement, tests)."""
    chemin = os.environ.get("NOTIFY_SOCKET", "")
    if not chemin or not hasattr(socket, "AF_UNIX"):
        return False
    if chemin.startswith("@"):
        chemin = "\0" + chemin[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(chemin)
            s.sendall(message.encode("utf-8"))
        return True
    except OSError:
        return False


def pret(statut: str = "") -> bool:
    return notifier("READY=1" + ("\nSTATUS=" + statut if statut else ""))


def battement(statut: str = "") -> bool:
    return notifier("WATCHDOG=1" + ("\nSTATUS=" + statut if statut else ""))


def arret() -> bool:
    return notifier("STOPPING=1")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : notifier, pret, battement, arret
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
