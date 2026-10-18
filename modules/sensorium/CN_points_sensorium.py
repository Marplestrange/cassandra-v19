# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sensorium : le service des points d'évolution du démon
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.1.5  #b331c1
# VERSION EC : néant
# EC LIÉES   : points/EC_*.py (les points du Sensorium)
# RÔLE       : donne au démon du Sensorium (un processus à part, sans noyau) l'accès aux points d'évolution de son module : le même service que le noyau, la même pile de sûreté.
# MÉTHODE    : charge le service des points du noyau (disjoncteur, ombre, routage) sur le stock d'EC du noyau, en lecture ; garde ses appels dans son propre fichier de rejeu, que le noyau absorbe ; si ce service ne se charge pas, exécute la référence du dépôt directement : jamais de mesure perdue.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.5 empreinte=b331c1 ▼▼▼
"""Le démon du Sensorium tourne seul : il n'a ni noyau, ni contexte, ni `ctx.point`. Ce module lui en tient lieu.

   - Le stock d'EC est celui du noyau (<données>/ec) : une EC mise en service par l'évolution sert aussi le démon, et son routage (ombre, paliers) le suit.
   - Le démon n'écrit pas dans ce stock (son unité systemd est en lecture seule hors de son dossier) : s'il doit suspendre une EC, il le dit au journal ; c'est le noyau qui la suspendra.
   - Ses appels (les entrées seulement) vont dans <données>/sensorium/rejeu_sensorium.db ; le module Évolution les absorbe dans le corpus de rejeu du noyau.
   - Dernier recours : la référence du dépôt (points/EC_*.py) est exécutée telle quelle. Une panne du service ne doit jamais faire perdre une mesure."""
import json
import logging
import os
import sys
import time
from pathlib import Path

_ICI = Path(__file__).resolve().parent
_RACINE = _ICI.parent.parent
_SVC = None
_REJEU = None
_DECLARES = {}
_ECHEC = ""
log = logging.getLogger("sensorium.points")


def _charger(donnees):
    """Monte le service des points, une fois. Rend (service, rejeu) ou lève."""
    global _SVC, _REJEU, _DECLARES
    if str(_RACINE) not in sys.path:
        sys.path.insert(0, str(_RACINE))
    from noyau.CN_manifeste import charger
    from noyau.CN_points import ServicePoints
    from noyau.CN_rejeu import Rejeu
    donnees = Path(donnees)
    manifeste = charger(_ICI / "CN_manifeste.toml")
    svc = ServicePoints(donnees.parent / "ec")
    defauts = svc.declarer(manifeste, _ICI)
    if defauts:
        raise RuntimeError("points du Sensorium mal déclarés : %s" % defauts)
    try:
        rejeu = Rejeu(donnees / "rejeu_sensorium.db")
        svc.enregistreur = rejeu.enregistrer
    except Exception as e:                                           # pas de corpus pour cette fois : le service, lui, marche
        log.warning("rejeu du Sensorium indisponible : %s", e)
        rejeu = None
    _DECLARES = {p.id: p for p in manifeste.points_evolution}
    _SVC, _REJEU = svc, rejeu
    return svc, rejeu


def _reference_directe(nom, entree):
    """La référence du dépôt, exécutée telle quelle (sans disjoncteur ni routage) : le dernier recours."""
    p = _DECLARES.get(nom)
    if p is None:
        manifeste_p = _ICI / "points" / ("EC_%s.py" % nom)
        fonction = "point_" + nom
    else:
        manifeste_p = _ICI / (p.reference + ".py")
        fonction = p.fonction or p.id.split(".")[-1]
    espace = {}
    exec(compile(manifeste_p.read_text(encoding="utf-8"), str(manifeste_p), "exec"), espace)
    return espace[fonction](json.loads(json.dumps(entree)))


def appeler(nom, entree, donnees=None):
    """Appelle le point `nom` du Sensorium. `donnees` : le dossier de données du démon (<données>/sensorium)."""
    global _ECHEC
    donnees = donnees or os.environ.get("CASSANDRA_DATA_DIR") or "/var/lib/cassandra/sensorium"
    if _SVC is None and not _ECHEC:
        try:
            _charger(donnees)
        except Exception as e:
            _ECHEC = "%s : %s" % (type(e).__name__, e)
            log.error("service des points indisponible, la référence du dépôt servira : %s", _ECHEC)
    if _SVC is not None:
        try:
            return _SVC.appeler("sensorium", nom, entree)
        except (PermissionError, OSError) as e:                      # écriture refusée (suspension, routage) : on le dit, la référence répond
            log.warning("point %s : %s — la référence répond", nom, e)
    return _reference_directe(nom, entree)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : il branche le démon sur le service des points du noyau et ne décide de rien.
# EC : néant. Les points du Sensorium sont dans points/EC_*.py, déclarés dans CN_manifeste.toml.
# LIEN : noyau/CN_points.py (le service), noyau/CN_rejeu.py (absorber), modules/evolution/CN_module.py (qui absorbe le rejeu du démon), CN_sensorium.py (qui appelle appeler()).
