# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le moteur des mesures
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : mesures
# ZONE       : CN
# VERSION CN : 0.1.0  #38f69b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le moteur des mesures : des POINTS (heure UTC, valeur) -> courbes par tranche, habitude, écarts, tendance, verdict. Aucune entrée/sortie : tout se teste.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=38f69b ▼▼▼
"""Le moteur des mesures : des POINTS (heure UTC, valeur) -> courbes par tranche, habitude, écarts, tendance, verdict. Aucune entrée/sortie : tout se teste.

Les règles viennent de la V18, payées en service :
  - une courbe vide dit POURQUOI (rien à signaler / non configurée / jamais utilisée / muette) : « tout est stable » serait un mensonge par défaut ;
  - l'habitude d'un créneau (jour de semaine, heure) ne vaut qu'après plusieurs occurrences ; avant, on dit « habitude inconnue », on n'invente pas de normale ;
  - la normale d'un créneau est la MOYENNE de ses occurrences (une heure d'un jour = une occurrence), et la valeur courante est la même agrégation sur la dernière heure ;
  - seules les heures ACHEVÉES font une occurrence ;
  - la tendance a pour abscisse l'heure réelle (un trou ne comprime pas le temps) et exige 24 h de mesures ;
  - un seul seuil d'écart pour tout le monde.
"""
from __future__ import annotations

from datetime import datetime, timedelta

PERIODES = {
    "1h": {"minutes": 60, "bucket": "minute", "label": "1 heure"},
    "6h": {"minutes": 360, "bucket": "5min", "label": "6 heures"},
    "24h": {"minutes": 1440, "bucket": "hour", "label": "24 heures"},
    "7d": {"minutes": 10080, "bucket": "hour", "label": "7 jours"},
    "30d": {"minutes": 43200, "bucket": "day", "label": "30 jours"},
}
ETATS = {"a_jour": "à jour", "muette": "muette : plus de nouvelles mesures", "rien_a_signaler": "rien à signaler", "non_configuree": "non configurée",
         "jamais_utilisee": "jamais utilisée", "aucune_source": "aucune source", "aucune_donnee": "aucune donnée"}
HABITUDE_MIN = 3                              # un créneau n'a de « normale » qu'après trois occurrences
HABITUDE_JOURS = 7 * HABITUDE_MIN
SEUIL_ECART = 60                              # un seul seuil d'écart (en %)
SEUIL_SSL_JOURS = 21
SEUIL_SATURATION_JOURS = 30
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
FORMAT = "%Y-%m-%d %H:%M:%S"
_point = None          # le point d'évolution `moteur`, posé par brancher() (mo._point = ctx.point)


def lire_ts(t):
    """« 2026-10-16 12:00:00 » ou « 2026-10-16T12:00:00.123Z » -> datetime naïf UTC ; None si illisible."""
    s = str(t or "").replace("T", " ")[:19]
    try:
        return datetime.strptime(s, FORMAT)
    except ValueError:
        return None


def ecrire_ts(d):
    return d.strftime(FORMAT) if d else None


def par_tranche(points, genre, agregat, bucket):
    """Les points regroupés par tranche. Le calcul est un POINT D'ÉVOLUTION : points/EC_moteur.py (opération « par_tranche »)."""
    return _point("moteur", {"op": "par_tranche", "args": {"points": list(points or []), "genre": genre, "agregat": agregat, "bucket": bucket}})["valeur"]


def serie(mesure, series_brutes, periode="24h", maintenant=None, top=6):
    """La courbe d'une mesure sur une période, dans la forme que lit l'écran. Le calcul est un POINT D'ÉVOLUTION : points/EC_moteur.py (opération « serie »)."""
    maintenant = maintenant or datetime.utcnow()
    return _point("moteur", {"op": "serie", "args": {"mesure": mesure, "series": series_brutes, "periode": periode, "top": top, "maintenant": ecrire_ts(maintenant)}})["valeur"]


def etat_source(mesure, series_brutes, maintenant=None):
    """L'état d'une source, DIT en mots. Le calcul est un POINT D'ÉVOLUTION : points/EC_moteur.py (opération « etat_source »)."""
    maintenant = maintenant or datetime.utcnow()
    return _point("moteur", {"op": "etat_source", "args": {"mesure": mesure, "series": series_brutes, "maintenant": ecrire_ts(maintenant)}})["valeur"]


def fiche_source(mesure, series_brutes, maintenant=None):
    """Une ligne de la liste des sources, dans la forme de l'écran. Le calcul est un POINT D'ÉVOLUTION : points/EC_moteur.py (opération « fiche_source »)."""
    maintenant = maintenant or datetime.utcnow()
    return _point("moteur", {"op": "fiche_source", "args": {"mesure": mesure, "series": series_brutes, "maintenant": ecrire_ts(maintenant)}})["valeur"]


def profil(mesure, series_brutes, maintenant=None, semaines=4):
    """La valeur habituelle pour ce jour de semaine et cette heure, et l'écart de la dernière heure. Le calcul est un POINT D'ÉVOLUTION : points/EC_moteur.py (opération « profil »)."""
    maintenant = maintenant or datetime.utcnow()
    return _point("moteur", {"op": "profil", "args": {"mesure": mesure, "series": series_brutes, "semaines": semaines, "maintenant": ecrire_ts(maintenant)}})["valeur"]


def prevision(mesure, series_brutes, maintenant=None, jours=14):
    """La date de saturation, par régression linéaire sur la moyenne horaire. Le calcul est un POINT D'ÉVOLUTION : points/EC_moteur.py (opération « prevision »)."""
    maintenant = maintenant or datetime.utcnow()
    return _point("moteur", {"op": "prevision", "args": {"mesure": mesure, "series": series_brutes, "jours": jours, "maintenant": ecrire_ts(maintenant)}})["valeur"]


def verdict(mesures, lectures, maintenant=None, seuil_ecart=None):
    """Ce que l'onglet dit à l'ouverture. Le calcul est un POINT D'ÉVOLUTION : points/EC_moteur.py (opération « verdict »)."""
    maintenant = maintenant or datetime.utcnow()
    return _point("moteur", {"op": "verdict", "args": {"mesures": mesures, "lectures": lectures, "seuil_ecart": seuil_ecart, "maintenant": ecrire_ts(maintenant)}})["valeur"]


# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : lire_ts, ecrire_ts, tranche, agreger, _pts, par_tranche, serie, etat_source …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
