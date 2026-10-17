# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Vue d'ensemble : façade de la composition du verdict
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : vue
# ZONE       : CN
# VERSION CN : 0.2.0  #cbef68
# VERSION EC : néant
# EC LIÉES   : verdict.composer @1.0 -> points/EC_verdict_composer.*
# RÔLE       : reçoit les relevés des sources, appelle le point d'évolution `verdict.composer`, rend le verdict.
# MÉTHODE    : met les arguments en données (admin, compte, sources, quand) et passe par le noyau (ctx.point), qui valide le contrat et sert l'EC ou la référence.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=cbef68 ▼▼▼
"""La composition de la vue d'ensemble : la FAÇADE du point d'évolution `verdict.composer`.

Le calcul (une fonction PURE) vit dans points/EC_verdict_composer.* : la référence du dépôt, qu'une EC peut remplacer, dans n'importe quel format.
Ce fichier ne contient aucune logique métier ; il n'importe jamais l'EC : il passe par `appeler` (ctx.point du noyau), qui valide le contrat à l'entrée
et à la sortie et qui répond avec la référence si l'EC faillit.
"""
from __future__ import annotations


def composer(admin, compte, s, maintenant="", appeler=None):
    """`s` : {'sites','flotte','metriques','sante','incidents','fil','notifs','autonomie'} : chaque valeur est le résultat d'une capacité, ou None si elle a échoué.
    `appeler(point, entree)` : le noyau (ctx.point). Sans lui, pas de calcul : un CN ne court-circuite jamais le noyau pour atteindre une EC."""
    if appeler is None:
        raise TypeError("composer() : `appeler` (ctx.point) est obligatoire : le calcul passe par le noyau")
    return appeler("verdict.composer", {"admin": bool(admin), "compte": compte if isinstance(compte, str) else "", "sources": s or {}, "quand": maintenant or ""})
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : `composer` est la seule entrée publique ; elle ne calcule rien, elle transmet au noyau et rend ce qu'il garantit conforme au contrat.
# EC : le calcul est le point `verdict.composer` (points/EC_verdict_composer.py, référence EC0) ; remplaçable par une EC sans toucher à ce fichier.
# LIEN : CN_manifeste.toml ([[points_evolution]]) ; contrats/CN_verdict_composer.json (schémas) ; noyau/CN_points.py (résolution, garde de contrat, disjoncteur).
