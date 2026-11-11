# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La vue d'ensemble
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : vue
# ZONE       : CN
# VERSION CN : 0.4.1  #83320c
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La vue d'ensemble : lit les modules de supervision (chacun pour LE compte qui regarde) et compose le verdict (composer.py).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.4.1 empreinte=83320c ▼▼▼
"""La vue d'ensemble : lit les modules de supervision (chacun pour LE compte qui regarde) et compose le verdict (composer.py)."""
import time

from . import CN_composer as composer
from . import CN_machine as machine_

SOURCES = (("sites", "sites.vue", False), ("flotte", "flotte.parc", True), ("metriques", "sensorium.metriques", True), ("sante", "sensorium.sante", True),
           ("incidents", "proactif.incidents", True), ("fil", "proactif.fil", True), ("autonomie", "proactif.autonomie", True), ("notifs", "notifications.lister", False))


# Ce que la page « La machine » lit : (clé du composeur, capacité, arguments). Aucune n'écrit.
MACHINE = (("etat", "sensorium.etat", {}), ("metriques", "sensorium.metriques", {}), ("sante", "sensorium.sante", {}),
           ("services", "sensorium.entite", {"nom": "system_services"}), ("echecs", "sensorium.entite", {"nom": "failed_units"}), ("ports", "sensorium.entite", {"nom": "open_ports"}),
           ("conteneurs", "sensorium.entite", {"nom": "docker_containers"}), ("sessions", "sensorium.entite", {"nom": "active_sessions"}),
           ("oom", "sensorium.entite", {"nom": "oom_events"}), ("acquits", "securite.oom_acquits", {}), ("certs_disque", "sensorium.entite", {"nom": "ssl_certificates"}),
           ("certificats", "certificats.etat", {}), ("tailscale", "tailscale.etat", {}), ("netbird", "netbird.etat", {}), ("depots", "sauvegardes.destinations", {}),
           ("panneau_sites", "fastpanel.sites", {}), ("panneau_services", "fastpanel.services", {}), ("panneau_bases", "fastpanel.bases", {}), ("panneau_mail", "fastpanel.mail", {}),
           ("panneau_copies", "fastpanel.sauvegardes", {}), ("panneau_comptes", "fastpanel.utilisateurs", {}),
           ("proxys", "sensorium.entite", {"nom": "reverse_proxies"}), ("materiel", "sensorium.entite", {"nom": "hardware_state"}),
           ("logiciels", "sensorium.entite", {"nom": "logiciels"}), ("connexions", "sensorium.entite", {"nom": "ssh_logins"}))


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

    def machine(ctx):
        """La page « La machine » : réservée aux administrateurs. Chaque source est lue pour le compte qui regarde ; absente (module non installé),
        muette (elle n'a pas répondu) ou lue, c'est dit tel quel au composeur, qui n'invente rien."""
        if not ctx.est_admin(ctx.compte or ""):
            return {"ok": False, "raison": "La machine est réservée aux administrateurs."}
        s = {}
        for cle, cap, args in MACHINE:
            try:
                v = ctx.executer_lecture(cap, **args)
                s[cle] = ("ok", v) if v is not None else ("muet", None)
            except PermissionError:
                s[cle] = ("absent", None)
            except Exception:
                s[cle] = ("muet", None)
        return machine_.composer(s, time.strftime("%Y-%m-%d %H:%M:%S"))

    ctx.implementer("ensemble", ensemble)
    ctx.implementer("machine", machine)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
