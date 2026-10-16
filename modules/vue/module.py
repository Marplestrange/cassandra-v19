"""La vue d'ensemble : lit les modules de supervision (chacun pour LE compte qui regarde) et compose le verdict (composer.py)."""
import time

from . import composer

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
        return composer.composer(admin, compte, s, time.strftime("%Y-%m-%d %H:%M:%S"))

    ctx.implementer("ensemble", ensemble)
