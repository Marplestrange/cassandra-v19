# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La vue d'ensemble
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : vue
# ZONE       : CN
# VERSION CN : 0.2.0  #01f156
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La vue d'ensemble : lit les modules de supervision (chacun pour LE compte qui regarde) et compose le verdict (composer.py).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=01f156 ▼▼▼
"""La vue d'ensemble : lit les modules de supervision (chacun pour LE compte qui regarde) et compose le verdict (composer.py)."""
import time

from . import CN_composer as composer

SOURCES = (("sites", "sites.vue", False), ("flotte", "flotte.parc", True), ("metriques", "sensorium.metriques", True), ("sante", "sensorium.sante", True),
           ("incidents", "proactif.incidents", True), ("fil", "proactif.fil", True), ("autonomie", "proactif.autonomie", True), ("notifs", "notifications.lister", False))


def brancher(ctx):
    def ensemble(ctx):
        compte = ctx.compte or ""
        admin = ctx.est_admin(compte)
        s = {}
        for cle, cap, admin_seul in SOURCES:
            if admin_seul and not admin:
                continue
            try:
                s[cle] = ctx.executer_lecture(cap)           # None si la capacité échoue : la source est dite muette, jamais comptée « tranquille »
            except Exception:
                s[cle] = None
        return composer.composer(admin, compte, s, time.strftime("%Y-%m-%d %H:%M:%S"), appeler=ctx.point)

    ctx.implementer("ensemble", ensemble)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
