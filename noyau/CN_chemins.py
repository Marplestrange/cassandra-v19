# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Où vivent les choses sur le disque, vu des modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #fb691a
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Où vivent les choses sur le disque, vu des modules.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=fb691a ▼▼▼
"""Où vivent les choses sur le disque, vu des modules.

Cassandra tient dans UN dossier (/var/cassandra). Les dossiers des utilisateurs suivent la convention de FastPanel :
/var/www/<utilisateur>/data/ est le « home » de l'utilisateur, et Cassandra y range son espace dans cassandra/.
Un module ne reçoit jamais un chemin libre : il demande l'espace d'un utilisateur, et ne sort pas de cet espace.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

_UNIX = re.compile(r"^[a-z_][a-z0-9_-]{0,31}$")
_MODULE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")


def utilisateurs() -> Path:
    """La racine des dossiers d'utilisateurs : $CASSANDRA_UTILISATEURS, /var/www par défaut (comme FastPanel)."""
    return Path(os.environ.get("CASSANDRA_UTILISATEURS") or "/var/www")


def espace_utilisateur(unix: str, module: str, creer: bool = False) -> Path:
    """/var/www/<unix>/data/cassandra/<module> : l'espace d'un module chez un utilisateur.
    Refuse un nom d'utilisateur ou de module qui sortirait de l'arborescence."""
    if not isinstance(unix, str) or not _UNIX.match(unix):
        raise ValueError("nom d'utilisateur invalide : %r" % (unix,))
    if not isinstance(module, str) or not _MODULE.match(module):
        raise ValueError("nom de module invalide : %r" % (module,))
    base = utilisateurs()
    p = base / unix / "data" / "cassandra" / module
    if base.resolve() not in p.resolve().parents:       # un lien symbolique ne doit pas faire sortir de /var/www
        raise ValueError("l'espace de %s sort de %s" % (unix, base))
    if creer:
        p.mkdir(parents=True, exist_ok=True)
    return p
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : utilisateurs, espace_utilisateur
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
