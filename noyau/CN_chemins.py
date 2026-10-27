# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Où vivent les choses sur le disque, vu des modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #32b36f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Où vivent les choses sur le disque, vu des modules.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=32b36f ▼▼▼
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


_SOCIETE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def societes() -> Path:
    """La racine des dossiers de société : $CASSANDRA_SOCIETES, sinon /var/cassandra/societes par défaut."""
    return Path(os.environ.get("CASSANDRA_SOCIETES") or "/var/cassandra/societes")


def espace_societe(societe: str, module: str, creer: bool = False) -> Path:
    """<societes>/<société>/commun/<module> : ce que toute une société partage, pour un module."""
    if not isinstance(societe, str) or not _SOCIETE.match(societe):
        raise ValueError("société invalide : %r" % (societe,))
    if not isinstance(module, str) or not _MODULE.match(module):
        raise ValueError("nom de module invalide : %r" % (module,))
    base = societes()
    p = base / societe / "commun" / module
    if creer:
        p.mkdir(parents=True, exist_ok=True)
    return p


def espace_compte(societe: str, compte: str, module: str, creer: bool = False) -> Path:
    """<societes>/<société>/utilisateurs/<compte>/<module> : les répertoires et documents d'un utilisateur vivent DANS le grand répertoire de sa société."""
    if not isinstance(compte, str) or not re.match(r"^[a-z0-9][a-z0-9._@+-]{0,119}$", compte):
        raise ValueError("compte invalide : %r" % (compte,))
    if not isinstance(module, str) or not _MODULE.match(module):
        raise ValueError("nom de module invalide : %r" % (module,))
    if not isinstance(societe, str) or not _SOCIETE.match(societe):
        raise ValueError("société invalide : %r" % (societe,))
    base = societes()
    p = base / societe / "utilisateurs" / compte / module
    if base.resolve() not in p.resolve().parents:       # un lien symbolique ne doit pas faire sortir de la racine des sociétés
        raise ValueError("l'espace de %s sort de %s" % (compte, base))
    if creer:
        p.mkdir(parents=True, exist_ok=True)
    return p
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : utilisateurs, espace_utilisateur
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
