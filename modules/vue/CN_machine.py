# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La machine
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : vue
# ZONE       : CN
# VERSION CN : 0.5.0  #a5b4c4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La machine : ce que la page « La machine » du Panorama affiche, composé à partir de ce que les modules relèvent déjà.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.5.0 empreinte=a5b4c4 ▼▼▼
"""La machine : ce que la page « La machine » du Panorama affiche, composé à partir de ce que les modules relèvent déjà.

Une fonction PURE (`composer`) : en entrée, la réponse de chaque source (ou son silence) ; en sortie, des données prêtes à dessiner. Rien n'est
inventé : une source muette donne « inconnu », jamais un zéro ; un module absent ne donne pas de vignette. Les relevés du Sensorium arrivent sous
forme de lignes « clé = texte » : on les relit ici, une fois, pour que l'écran n'ait rien à deviner.

Lot 1 : tout ce qui se lit déjà. Ce que le collecteur ne relève pas encore (ports et distribution des conteneurs, mémoire par processus, nombre de
cœurs, origine d'une adresse…) et les gestes qui n'existent pas (conteneurs, services, processus, redémarrage) viendront avec leurs lots.
"""
from __future__ import annotations

import json
import re

# Les services suivis de près : [unité, ce que c'est, famille, le geste qui existe déjà, pourquoi on ne l'arrête pas d'ici].
# La description est écrite ici une fois par service connu ; un service inconnu garde celle de systemd.
SERVICES = [
    ("cassandra-noyau", "Le noyau de Cassandra : cette interface, les modules, les agents.", "maison", "noyau", "Arrêter Cassandra depuis Cassandra ne laisserait rien pour la relancer : d’ici, elle se relance, elle ne s’arrête pas."),
    ("sensorium", "Le collecteur du Sensorium : il relève la machine, toutes les 30 secondes à 60 minutes selon le capteur.", "maison", "collecteur", ""),
    ("cassandra-courtier", "Le courtier racine : il exécute les commandes nommées que Cassandra demande, une à la fois, puis se rendort.", "maison", "", ""),
    ("ollama", "Les modèles de langage locaux, pour les agents qui ne passent pas par un fournisseur en ligne.", "maison", "ollama", ""),
    ("nginx", "Le serveur web de façade : il reçoit toutes les visites et les passe aux sites et aux conteneurs.", "web", "nginx", "L’arrêter couperait cette interface : d’ici, il se redémarre et se recharge, il ne s’arrête pas."),
    ("apache2", "Le serveur web derrière nginx, pour les sites PHP du panneau.", "web", "", ""),
    ("mysql", "La base de données MySQL des sites.", "données", "", ""),
    ("mariadb", "La base de données MariaDB des sites.", "données", "", ""),
    ("postgresql", "La base de données PostgreSQL.", "données", "", ""),
    ("redis-server", "Le cache en mémoire Redis.", "données", "", ""),
    ("dovecot", "Les boîtes aux lettres : la lecture du courrier (IMAP, POP).", "courrier", "", ""),
    ("exim4", "Le transport du courrier : envoi et réception (SMTP).", "courrier", "", ""),
    ("postfix", "Le transport du courrier : envoi et réception (SMTP).", "courrier", "", ""),
    ("proftpd", "Le transfert de fichiers FTP vers les sites.", "web", "", ""),
    ("fastpanel2", "Le panneau d’hébergement FastPanel.", "web", "", ""),
    ("docker", "Le moteur qui fait tourner les conteneurs.", "système", "", ""),
    ("containerd", "Le socle de Docker : il porte les conteneurs.", "système", "", ""),
    ("cron", "Les tâches planifiées.", "système", "", ""),
    ("fail2ban", "Le gardien : il bannit les adresses qui insistent sur SSH.", "sécurité", "", ""),
    ("ssh", "L’accès distant à la machine.", "sécurité", "", "L’arrêter te fermerait la porte : d’ici, il se redémarre, il ne s’arrête pas."),
    ("certbot", "Le renouvellement des certificats Let’s Encrypt : il se lance deux fois par jour, puis s’arrête.", "sécurité", "", ""),
    ("crowdsec", "CrowdSec : il bloque les attaquants repérés ici et ceux que sa communauté signale.", "sécurité", "", ""),
    ("tailscaled", "Le réseau privé Tailscale.", "réseau", "", ""),
    ("netbird", "Le réseau privé NetBird.", "réseau", "", ""),
    ("unattended-upgrades", "Les mises à jour de sécurité automatiques, chaque nuit.", "système", "", ""),
]
# Ce qui tombe si l'on arrête le service : écrit une fois par service connu, pour que la fiche le dise avant tout geste.
SI_ARRET = {
    "cassandra-noyau": "Cassandra entière s’arrête : interface, agents, alertes.",
    "sensorium": "Plus aucun relevé : toutes les pages disent « inconnu », les alertes se taisent.",
    "cassandra-courtier": "Plus aucun geste root ne passe : relances, bannissements, mises à jour.",
    "ollama": "Les agents réglés sur un modèle local ne répondent plus.",
    "nginx": "Tous les sites et les noms publics des conteneurs ne répondent plus.",
    "apache2": "Les sites PHP du panneau ne répondent plus.",
    "mysql": "Les sites qui ont une base de données tombent en erreur.",
    "mariadb": "Les sites qui ont une base de données tombent en erreur.",
    "postgresql": "Les applications qui ont une base PostgreSQL tombent en erreur.",
    "redis-server": "Les applications qui s’appuient sur le cache ralentissent ou tombent en erreur.",
    "dovecot": "Plus personne ne peut relever son courrier.",
    "exim4": "Le courrier n’entre plus et ne sort plus ; il attend chez les expéditeurs.",
    "postfix": "Le courrier n’entre plus et ne sort plus ; il attend chez les expéditeurs.",
    "proftpd": "Les dépôts de fichiers par FTP échouent.",
    "fastpanel2": "Le panneau ne répond plus ; les sites, eux, continuent.",
    "docker": "Tous les conteneurs s’arrêtent.",
    "containerd": "Tous les conteneurs s’arrêtent.",
    "cron": "Sauvegardes, renouvellements et balayages ne se lancent plus.",
    "fail2ban": "Plus aucun bannissement : les tentatives ne sont plus freinées.",
    "ssh": "Plus personne n’entre sur la machine à distance, toi compris.",
    "certbot": "Les certificats ne se renouvellent plus.",
    "crowdsec": "Les attaquants connus ne sont plus bloqués.",
    "tailscaled": "La machine quitte le réseau Tailscale : elle n’est plus joignable par ses adresses privées.",
    "netbird": "La machine quitte le réseau NetBird.",
    "unattended-upgrades": "Les correctifs de sécurité ne s’installent plus seuls.",
}
# Le rôle d'un conteneur, reconnu au nom de son image (le premier motif trouvé gagne : du plus précis au plus large).
ROLES_IMAGE = (
    ("netbird-server", "le serveur de gestion, de signal et de relais de NetBird"), ("netbirdio/dashboard", "le tableau de bord de NetBird"),
    ("netbirdio/netbird", "le client NetBird de la machine"), ("searxng", "le moteur de recherche que Cassandra interroge"),
    ("vaultwarden", "le gestionnaire de mots de passe"), ("postgres", "une base de données PostgreSQL"), ("mariadb", "une base de données MariaDB"),
    ("mysql", "une base de données MySQL"), ("redis", "un cache en mémoire Redis"), ("traefik", "un serveur de façade (reverse proxy)"),
    ("caddy", "un serveur web de façade"), ("nginx", "un serveur web"), ("portainer", "une console de gestion des conteneurs"),
    ("nextcloud", "un nuage de fichiers"), ("gitea", "une forge Git"), ("grafana", "des tableaux de bord de mesures"), ("prometheus", "un collecteur de mesures"),
    ("uptime-kuma", "une surveillance de disponibilité"), ("watchtower", "la mise à jour automatique des conteneurs"), ("ollama", "des modèles de langage locaux"),
    ("open-webui", "une interface pour modèles de langage"), ("n8n", "des automatisations"), ("minio", "un stockage d’objets"), ("adguard", "un filtre DNS"),
    ("pihole", "un filtre DNS"), ("jellyfin", "une médiathèque"), ("homeassistant", "la domotique"),
)
# Les processus que le courtier refuse d'arrêter (la même table que sa commande « machine ») : la page le dit avant, au lieu d'un bouton qui échoue.
PROCESSUS_PROTEGES = {"ssh": "C’est ta porte d’entrée sur la machine : il se redémarre depuis Services.", "sshd": "C’est ta porte d’entrée sur la machine : il se redémarre depuis Services.",
                      "cassandra-noyau": "C’est Cassandra elle-même : elle se relance depuis Services.", "cassandra-courtier": "C’est le courtier, qui exécute les gestes : il ne se touche pas.",
                      "sensorium": "C’est le collecteur : il se redémarre depuis Services."}
PORTEES = {"machine": ("la machine seule", "ok"), "prive": ("le réseau privé", ""), "public": ("Internet", "w")}
SANTES = {"healthy": "sain", "unhealthy": "en mauvaise santé", "starting": "contrôle de santé en cours", "": "sans contrôle de santé"}
# php<version>-fpm : la version change d'une machine à l'autre
_PHP_FPM = re.compile(r"^php\d+(\.\d+)?-fpm$")
# Le programme qui écoute sur un port -> le service auquel il appartient
PROGRAMME_DE = {"nginx": "nginx", "sshd": "ssh", "mysqld": "mysql", "mariadbd": "mariadb", "exim4": "exim4", "dovecot": "dovecot", "proftpd": "proftpd", "apache2": "apache2",
                "ollama": "ollama", "tailscaled": "tailscaled", "fastpanel2-ngin": "fastpanel2", "fastpanel": "fastpanel2", "postgres": "postgresql", "redis-server": "redis-server", "master": "postfix"}
PUCES = ("●", "•", "○", "*", "-", "✗", "x", "?")       # ce que systemd imprime à la place d'un nom d'unité quand une ligne est mal lue
_PRIVES = re.compile(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|127\.|169\.254\.|fe80:|fd|::1$)")


def _entier(texte, defaut=None):
    m = re.search(r"-?\d+", str(texte or ""))
    return int(m.group(0)) if m else defaut


def _detail(ligne) -> dict:
    d = (ligne or {}).get("detail")
    if isinstance(d, dict):
        return d
    try:
        d = json.loads(d) if d else {}
    except (TypeError, ValueError):
        d = {}
    return d if isinstance(d, dict) else {}


def _ok(s, cle):
    """La réponse d'une source, si elle a répondu ; sinon None. `s[cle]` = (« ok » | « muet » | « absent », valeur)."""
    e = s.get(cle)
    return e[1] if isinstance(e, (tuple, list)) and len(e) == 2 and e[0] == "ok" else None


def _etat(s, cle) -> str:
    e = s.get(cle)
    return e[0] if isinstance(e, (tuple, list)) and len(e) == 2 else "absent"


def _liste(v, cle=None) -> list:
    if cle and isinstance(v, dict):
        v = v.get(cle)
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _json(v, defaut):
    """Une colonne que le collecteur écrit en JSON (les ports, les volumes, les disques)."""
    if isinstance(v, (list, dict)):
        return v
    try:
        x = json.loads(v) if v else defaut
    except (TypeError, ValueError):
        return defaut
    return x if isinstance(x, type(defaut)) else defaut


def role_image(image: str) -> str:
    i = str(image or "").lower()
    return next((role for motif, role in ROLES_IMAGE if motif in i), "")


def _description_service(unite: str) -> str:
    return next((d for u, d, _f, _g, _p in SERVICES if u == unite), "L’interpréteur PHP des sites." if _PHP_FPM.match(unite or "") else "")


def _duree_docker(texte: str) -> str:
    """« Up 36 hours » -> « depuis 36 h » ; « 8 days » -> « 8 j »."""
    t = str(texte or "").strip()
    t = re.sub(r"^about an? hour", "1 h", t, flags=re.I)
    t = re.sub(r"^less than a second|^(\d+) seconds?", lambda m: (m.group(1) or "1") + " s", t, flags=re.I)
    for mot, court in (("minutes", "min"), ("minute", "min"), ("hours", "h"), ("hour", "h"), ("days", "j"), ("day", "j"), ("weeks", "sem."), ("week", "sem."), ("months", "mois"), ("month", "mois")):
        t = re.sub(r"(\d+) %s\b" % mot, r"\1 " + court, t, flags=re.I)
    return t


def etat_conteneur(statut: str):
    """Le statut que Docker imprime, dit en clair : (texte, tourne, en pause). La page d'avant cherchait le mot « run » dans « Up 36 hours »."""
    t = str(statut or "").strip()
    sain = " · sain" if "(healthy)" in t else " · en mauvaise santé" if "(unhealthy)" in t else ""
    nu = re.sub(r"\s*\((healthy|unhealthy|health: starting)\)", "", t)
    if re.match(r"^Up\b", nu, re.I):
        if "(Paused)" in nu:
            return "en pause", True, True
        return "tourne depuis " + _duree_docker(nu[2:].replace("(Paused)", "").strip()) + sain, True, False
    m = re.match(r"^Exited \((-?\d+)\) (.*) ago$", nu, re.I)
    if m:
        return "arrêté depuis %s (code %s)" % (_duree_docker(m.group(2)), m.group(1)), False, False
    if re.match(r"^(Created|Dead|Restarting|Removing)", nu, re.I):
        return {"created": "créé, jamais démarré", "dead": "mort", "restarting": "redémarre en boucle", "removing": "en cours de retrait"}[nu.split()[0].lower()], False, False
    return (nu or "état inconnu"), False, False


def _phrase(ligne) -> str:
    """Une mesure en alerte, dite en une phrase qu'on lit : « Le disque / : plein dans ~2 jours », pas « Prévision disque./ »."""
    cle, val, lib = str(ligne.get("wkey") or ""), str(ligne.get("value") or ""), str(ligne.get("libelle") or ligne.get("wkey") or "")
    if cle.startswith("prevision.disque."):
        return "Le disque %s : %s" % (cle[17:], val)
    if cle.startswith("exposition."):
        programme = val.split(" · ")[0]
        return ("Le port %s (%s) est joignable d’Internet" % (cle[11:], programme)) if "PUBLIC" in val else "Le port %s : %s" % (cle[11:], val)
    if cle == "sauvegarde.hors_machine":
        return val.replace("AUCUNE", "Aucune", 1)
    return "%s : %s" % (lib, val) if val else lib


def _reseau_de(adresse: str, pairs: dict) -> tuple:
    """D'où vient une adresse : une machine du réseau Tailscale (son nom), le réseau local, ou Internet."""
    a = str(adresse or "").strip()
    if not a or a == "local":
        return "la machine elle-même", ""
    if a in pairs:
        return "Tailscale", pairs[a]
    if a.startswith("100.") and 64 <= (_entier(a.split(".")[1], 0) or 0) <= 127:
        return "réseau privé", ""
    if _PRIVES.match(a):
        return "réseau local", ""
    return "Internet", ""


def composer(s: dict, maintenant: str = "") -> dict:
    """`s` : {source: (« ok » | « muet » | « absent », réponse)}. Voir SOURCES dans CN_module.py pour la liste."""
    s = s or {}
    etat = _ok(s, "etat") or {}
    rows = _liste(etat.get("rows"))
    L = {r.get("wkey"): r for r in rows if r.get("wkey")}
    v = lambda cle: str((L.get(cle) or {}).get("value") or "")                    # noqa: E731
    sans_releve = not rows
    source = {"muet": _etat(s, "etat") != "ok" or bool(etat.get("muet")) or sans_releve, "fige": bool(etat.get("fige")), "age_s": etat.get("age_s"),
              "absent": _etat(s, "etat") == "absent", "lu": maintenant}

    # ── la fiche
    os_, archi, nature = (v("system.os").split(" · ") + ["", "", ""])[:3]
    interfaces = []
    for cle in sorted(k for k in L if k.startswith("interface.")):
        morceaux = [m.strip() for m in v(cle).split(" · ")]
        adresses = [a.strip() for a in (morceaux[1] if len(morceaux) > 1 else "").split(",") if a.strip()]
        interfaces.append({"nom": cle[10:], "etat": morceaux[0] if morceaux else "", "v4": [a for a in adresses if ":" not in a], "v6": [a for a in adresses if ":" in a],
                           "defaut": "route par défaut" in v(cle)})
    maj = v("maj.paquets")
    nombres = [int(x) for x in re.findall(r"\d+", maj)]
    machine = {"nom": v("system.hostname") or str(etat.get("hote") or ""), "os": os_, "archi": archi, "nature": nature, "noyau": v("system.kernel"), "allumee": v("system.uptime"),
               "fuseau": v("system.fuseau"), "horloge": v("horloge.synchronisation") or v("system.heure"), "dns": v("dns.sante"),
               "redemarrage": bool(v("system.redemarrage_requis")) and not v("system.redemarrage_requis").lower().startswith("non"), "redemarrage_texte": v("system.redemarrage_requis"),
               "maj": {"texte": maj, "total": nombres[0] if nombres else None, "secu": nombres[1] if len(nombres) > 1 else None},
               "interfaces": interfaces, "pare_feu": [v(k) for k in ("pare_feu.ipv4", "pare_feu.ipv6") if v(k)], "taches": v("cron.root")}

    mat = (_liste(_ok(s, "materiel")) or [None])[0]
    machine["materiel"] = None if mat is None else {
        "cpu": {"modele": str(mat.get("cpu_modele") or ""), "coeurs": _entier(mat.get("cpu_coeurs")), "fils": _entier(mat.get("cpu_fils")), "mhz": _entier(mat.get("cpu_mhz"))},
        "constructeur": str(mat.get("constructeur") or ""), "carte": str(mat.get("carte") or ""), "bios": str(mat.get("bios") or ""), "installee": str(mat.get("installee") or ""),
        "demarree": str(mat.get("demarree") or "").replace("T", " ")[:16], "passerelle": str(mat.get("passerelle") or ""), "inverse": str(mat.get("inverse") or ""),
        "ip_publique": str(mat.get("ip_publique") or ""), "pare_feu_entree": str(mat.get("pare_feu_entree") or ""), "maj_auto": str(mat.get("maj_auto") or ""),
        "disques": [d for d in _json(mat.get("disques"), []) if isinstance(d, list) and len(d) >= 4],
        "temperature": mat.get("temp_max") if isinstance(mat.get("temp_max"), (int, float)) and mat.get("temp_max") else None}

    # ── la santé : la note d'ensemble du Sensorium et sa décomposition (la page d'avant montrait la note des ressources seules)
    hs, d = v("health.score"), _detail(L.get("health.score"))
    m = re.match(r"\s*(\d+)\s*/\s*100\s*(?:\(([^)]*)\))?", hs)
    ress = (_ok(s, "sante") or {}).get("score")
    sante = {"score": int(m.group(1)) if m else None, "mot": (m.group(2) or "") if m else "", "alertes": len(d.get("alertes") or []),
             "ressources": d.get("ressources") if isinstance(d.get("ressources"), (int, float)) else ress}

    # ── les ressources
    me = _ok(s, "metriques")
    ressources = None
    if isinstance(me, dict) and not me.get("muet"):
        n = lambda k: me.get(k) if isinstance(me.get(k), (int, float)) else None    # noqa: E731
        ressources = {"cpu": n("cpu"), "ram": n("ram"), "swap": n("swap"), "disque": n("disk"), "charge": [n("load_1m"), n("load_5m"), n("load_15m")],
                      "ram_go": [n("ram_used_gb"), n("ram_total_gb")], "swap_go": [n("swap_used_gb"), n("swap_total_gb")],
                      "disque_go": [n("disk_used_gb"), n("disk_total_gb")], "disque_libre_go": n("disk_free_gb")}

    # ── les disques : la place, et la prévision du Sensorium
    disques = []
    for cle in sorted(k for k in L if k.startswith("montage.")):
        t = v(cle)
        mm = re.match(r"\s*(\d+)%\s*\(([\d.,]+)/([\d.,]+)\s*Go(?:,\s*([^)]+))?\)(?:.*inodes\s*(\d+)%)?", t)
        pr = L.get("prevision.disque." + cle[8:]) or {}
        disques.append({"montage": cle[8:], "texte": t, "pct": int(mm.group(1)) if mm else None, "utilise_go": float(mm.group(2).replace(",", ".")) if mm else None,
                        "total_go": float(mm.group(3).replace(",", ".")) if mm else None, "type": (mm.group(4) or "") if mm else "", "inodes_pct": int(mm.group(5)) if mm and mm.group(5) else None,
                        "prevision": str(pr.get("value") or ""), "alerte": pr.get("severity") == "warning"})

    # ── ce qui cloche : les mesures en alerte, la plus grave d'abord (la note de santé n'en est pas une : elle les compte)
    rang = {"critique": 0, "avoir": 1, "info": 2}
    poids = {"ressources": 0, "prevision": 0, "service": 0, "system": 0, "docker": 1, "sauvegarde": 1, "noyau": 2}       # à gravité égale : ce qui menace la machine avant ce qui l'expose
    cloche = sorted(({"cle": r["wkey"], "titre": str(r.get("libelle") or r["wkey"]), "texte": str(r.get("value") or ""), "phrase": _phrase(r), "famille": str(r.get("famille") or ""),
                      "gravite": str(r.get("gravite") or "info")} for r in rows if r.get("severity") == "warning" and r.get("wkey") != "health.score"),
                    key=lambda x: (rang.get(x["gravite"], 3), poids.get(x["famille"], 3), x["cle"]))

    # ── processus, mémoire saturée
    memoire = me.get("memory") if isinstance(me, dict) and isinstance(me.get("memory"), dict) and me["memory"].get("total_mo") else None
    acquittes = set((_ok(s, "acquits") or {}).get("signatures") or [])
    oom = None
    if _etat(s, "oom") == "ok":
        oom = []
        for e in _liste(_ok(s, "oom")):
            nom = str(e.get("killed_process") or "").strip()
            sig = "%s_%s" % (e.get("ts"), nom)
            if (nom.lower() in ("", "?", "unknown") and not e.get("memory_used_mb")) or sig in acquittes:
                continue
            oom.append({"processus": nom or "?", "mo": e.get("memory_used_mb") or 0, "quand": str(e.get("ts") or ""), "signature": sig, "service": str(e.get("service") or "")})

    # ── les renvois de nginx (par quel nom public un service ou un conteneur se joint) et les jours restants des certificats, par nom
    proxys = _liste(_ok(s, "proxys"))
    jours_cert = {}
    for c in _liste(_ok(s, "certificats"), "certificats"):
        if isinstance(c.get("jours"), (int, float)):
            for nom in [c.get("hote")] + list(c.get("noms") or []):
                if nom:
                    jours_cert[str(nom)] = int(c["jours"])

    # ── services
    services = None
    if _etat(s, "services") == "ok":
        tous = _liste(_ok(s, "services"))
        par_nom = {str(x.get("name")): x for x in tous}
        ports_de = {}
        for p in _liste(_ok(s, "ports")):
            sv = PROGRAMME_DE.get(str(p.get("process") or ""))
            if sv:
                ports_de.setdefault(sv, []).append("%s/%s" % (p.get("port"), p.get("protocol") or "?"))
        echecs = {str(u.get("unit") or "").replace(".service", "") for u in _liste(_ok(s, "echecs")) if u.get("active_state") == "failed" and u.get("unit") not in PUCES}
        journaux = {str(u.get("unit") or "").replace(".service", ""): [l for l in str(u.get("journal") or "").splitlines() if l.strip()] for u in _liste(_ok(s, "echecs"))}

        def mesures(x, unite, ports_):
            nombre = lambda cle: x.get(cle) if isinstance(x.get(cle), (int, float)) else None    # noqa: E731
            numeros = {_entier(p) for p in ports_}
            return {"pid": nombre("pid") or None, "memoire_mo": nombre("memoire_mo"), "cpu": nombre("cpu_pct"), "depuis": str(x.get("depuis") or "").replace("T", " ")[:16],
                    "redemarrages": nombre("redemarrages") or 0, "si_arret": SI_ARRET.get(unite, "Les sites PHP affichent une erreur 502." if _PHP_FPM.match(unite) else ""),
                    "noms": sorted({str(p.get("nom")) for p in proxys if p.get("nom") and (unite == "nginx" or p.get("port") in numeros)}),      # nginx sert tous les noms ; un autre service, ceux qui mènent à ses ports
                    "journal": journaux.get(unite, [])}
        connus = list(SERVICES) + [(n, "L’interpréteur PHP des sites.", "web", "", "") for n in sorted(par_nom) if _PHP_FPM.match(n)]
        suivis = []
        for unite, description, famille, geste, protege in connus:
            x = par_nom.get(unite)
            if not x and unite not in echecs:
                continue
            x = x or {}
            en_echec = unite in echecs or x.get("status") == "failed"
            actif = bool(x.get("active")) and not en_echec
            ports_ = sorted(set(ports_de.get(unite, [])), key=lambda t: (_entier(t, 0), t))
            suivis.append(dict({"unite": unite, "description": description, "systemd": str(x.get("description") or ""), "famille": famille, "geste": geste, "protege": protege,
                                "etat": "echec" if en_echec else "actif" if actif else "repos" if x.get("unit_file_state") in ("static", "enabled") and unite in ("certbot", "cassandra-courtier") else "arret",
                                "sous_etat": str(x.get("sub_state") or ""), "au_demarrage": bool(x.get("enabled")), "ports": ports_}, **mesures(x, unite, ports_)))
        for unite in sorted(echecs - {x["unite"] for x in suivis}):
            suivis.append(dict({"unite": unite, "description": str((par_nom.get(unite) or {}).get("description") or ""), "systemd": "", "famille": "système", "geste": "", "protege": "",
                                "etat": "echec", "sous_etat": "failed", "au_demarrage": bool((par_nom.get(unite) or {}).get("enabled")), "ports": []}, **mesures(par_nom.get(unite) or {}, unite, [])))
        services = {"total": len(tous), "actifs": sum(1 for x in tous if x.get("active")), "inactifs": sum(1 for x in tous if not x.get("active")),
                    "echecs": sorted(echecs), "suivis": suivis}

    # ── conteneurs : l'entité de Docker, enrichie des relevés du monde (âge de l'image, charge)
    conteneurs = None
    if _etat(s, "conteneurs") == "ok":
        conteneurs = []
        for c in _liste(_ok(s, "conteneurs")):
            nom = str(c.get("name") or "?")
            texte, tourne, pause = etat_conteneur(c.get("status"))
            charge = re.match(r"CPU\s*([\d.,]+)%\s*·\s*mémoire\s*([\d.,]+\s*\w+)", v("conteneur_ressources." + nom))
            age = re.search(r"il y a (\d+) j", v("image." + nom))
            ports_c = [{"hote": str(p[0]), "port": p[1], "interne": p[2], "proto": str(p[3]), "portee": PORTEES.get(p[4], PORTEES["public"])[0], "niveau": PORTEES.get(p[4], PORTEES["public"])[1]}
                       for p in _json(c.get("ports"), []) if isinstance(p, list) and len(p) >= 5]
            publies = {p["port"] for p in ports_c}
            reseau_c = str(c.get("reseau") or "")
            conteneurs.append({"nom": nom, "image": str(c.get("image") or ""), "etat": texte, "tourne": tourne, "pause": pause,
                               "image_age_j": int(age.group(1)) if age else None, "cpu": float(charge.group(1).replace(",", ".")) if charge else None,
                               "memoire": charge.group(2).replace("MiB", " Mo").replace("GiB", " Go").replace("  ", " ").replace(".", ",") if charge else "",
                               "releve": bool(c.get("ident")), "role": role_image(c.get("image")), "distribution": str(c.get("distribution") or ""),
                               "taille_mo": c.get("taille_mo") if isinstance(c.get("taille_mo"), (int, float)) and c.get("taille_mo") else None,
                               "reseau": "host (celui de la machine)" if reseau_c == "host" else reseau_c, "ip": str(c.get("ip") or ""), "politique": str(c.get("politique") or ""),
                               "sante": SANTES.get(str(c.get("sante") or ""), str(c.get("sante") or "")), "redemarrages": _entier(c.get("redemarrages"), 0),
                               "compose": str(c.get("compose") or ""), "ports": ports_c, "maj": str(c.get("maj") or ""), "maj_vue": str(c.get("maj_vue") or "").replace("T", " ")[:16],
                               "volumes": [{"genre": str(x[0]), "source": str(x[1]), "cible": str(x[2])} for x in _json(c.get("volumes"), []) if isinstance(x, list) and len(x) >= 3],
                               "proxys": [{"nom": str(p.get("nom") or ""), "chemin": str(p.get("chemin") or "/"), "vers": str(p.get("vers") or ""), "genre": str(p.get("genre") or ""),
                                           "tls": bool(p.get("tls")), "cert_j": jours_cert.get(str(p.get("nom") or ""))} for p in proxys if p.get("port") in publies]})
    logiciel = {k[9:]: v(k).startswith("install") for k in L if k.startswith("logiciel.")}
    docker_la = bool(conteneurs) or bool(logiciel.get("docker"))
    versions = {str(x.get("nom")): str(x.get("version")) for x in _liste(_ok(s, "logiciels")) if x.get("installe") and x.get("version")}

    roles = {c["nom"]: c["role"] for c in conteneurs or [] if c.get("role")}
    processus = []
    for p in (_liste(me, "processes") or _liste(me, "top_processes")) if isinstance(me, dict) else []:
        genre, a_qui = str(p.get("genre") or ""), str(p.get("a_qui") or "")
        pid = p.get("pid") if isinstance(p.get("pid"), int) else None
        description = _description_service(a_qui) if genre == "service" else (roles.get(a_qui, "")[:1].upper() + roles.get(a_qui, "")[1:] if genre == "conteneur" else "")
        protege = ("L’arrêter arrêterait la machine." if pid == 1 else "Un processus du noyau Linux ne se touche pas." if genre == "noyau" else
                   PROCESSUS_PROTEGES.get(a_qui, "") if genre == "service" else "")
        processus.append({"utilisateur": str(p.get("user") or ""), "cpu": p.get("cpu") if isinstance(p.get("cpu"), (int, float)) else 0, "commande": str(p.get("command") or p.get("name") or "?"),
                          "pid": pid, "mem_mo": p.get("mem_mb") if isinstance(p.get("mem_mb"), (int, float)) else None, "age_s": p.get("age_s") if isinstance(p.get("age_s"), int) else None,
                          "a_qui": {"genre": genre, "nom": a_qui} if genre else None, "description": description, "protege": protege})

    # ── sessions : qui est connecté, et d'où
    ts = _ok(s, "tailscale") or {}
    pairs = {str(p.get("ip")): str(p.get("nom") or "") for p in _liste(ts, "pairs") if p.get("ip")}
    sessions = None
    if _etat(s, "sessions") == "ok":
        sessions = []
        for x in _liste(_ok(s, "sessions")):
            reseau, de = _reseau_de(x.get("ip"), pairs)
            n30, refus_1h = (x.get("connexions_30j") if isinstance(x.get("connexions_30j"), int) else None), _entier(x.get("refus_1h"), 0)
            connu = "" if n30 is None else ("jamais vue avant" if not n30 else "%d connexion%s réussie%s en 30 jours" % (n30, "s" if n30 > 1 else "", "s" if n30 > 1 else ""))
            if refus_1h:
                connu += (" · " if connu else "") + "%d tentative%s refusée%s depuis cette adresse en une heure" % (refus_1h, "s" if refus_1h > 1 else "", "s" if refus_1h > 1 else "")
            sessions.append({"utilisateur": str(x.get("user") or "?"), "adresse": str(x.get("ip") or ""), "depuis": str(x.get("login_time") or "")[:16].replace("T", " "),
                             "type": "ftp" if x.get("type") == "ftp" else "ssh", "reseau": reseau, "machine": de,
                             "anonyme": str(x.get("user") or "") == "sshd",         # « sshd » : personne n'est encore entré, on frappe à la porte
                             "terminal": str(x.get("tty") or ""), "inactivite": str(x.get("inactivite") or ""), "commande": str(x.get("commande") or ""),
                             "methode": str(x.get("methode") or ""), "cle": str(x.get("cle") or ""), "connu": connu, "refus_1h": refus_1h})
    connexions = None
    if _etat(s, "connexions") == "ok":
        connexions = []
        for x in _liste(_ok(s, "connexions")):
            reseau, de = _reseau_de(x.get("ip"), pairs)
            connexions.append({"utilisateur": str(x.get("user") or "?"), "adresse": str(x.get("ip") or ""), "methode": str(x.get("methode") or ""), "cle": str(x.get("cle") or ""),
                               "nombre": _entier(x.get("nombre"), 0), "premiere": str(x.get("premiere") or "").replace("T", " ")[:16], "derniere": str(x.get("derniere") or "").replace("T", " ")[:16],
                               "reseau": reseau, "machine": de})
    ref = v("ssh.echecs")
    refus = {"texte": ref, "total": _entier(ref), "adresses": [[a, int(n)] for a, n in re.findall(r"([0-9a-fA-F:.]{3,45}) \((\d+)\)", ref)]} if ref else None

    # ── les voisins : une vignette seulement si le sujet est trouvé sur la machine
    voisins = []

    def voisin(cle, titre, ou, aller, etat_, chiffre=None, lignes=(), pastille=None, preuve="", details=None):
        if etat_ != "absent":
            voisins.append({"cle": cle, "titre": titre, "ou": ou, "aller": aller, "etat": etat_, "chiffre": chiffre, "lignes": [x for x in lignes if x], "pastille": pastille,
                            "preuve": preuve, "details": details or {}})

    ports = _liste(_ok(s, "ports")) if _etat(s, "ports") == "ok" else None
    expo = [v(k) for k in L if k.startswith("exposition.")]
    publics = sum(1 for t in expo if "PUBLIC" in t)
    if ports is not None:
        voisin("ports", "Ports ouverts", "Sécurité › Exposition", ["securite", "exposition"], "module", len(ports),
               ["%d joignable%s d’Internet" % (publics, "s" if publics > 1 else "") if expo else "", "%d service%s relevé%s" % (len(expo), "s" if len(expo) > 1 else "", "s" if len(expo) > 1 else "") if expo else ""],
               ["%d public%s" % (publics, "s" if publics > 1 else ""), "w"] if publics else (["aucun public", "ok"] if expo else None), "toute machine a des ports")
    f2b = [(k[9:], _entier(v(k), 0)) for k in sorted(L) if k.startswith("fail2ban.")]
    if f2b or logiciel.get("fail2ban-client"):
        voisin("bannies", "Bannissements", "Sécurité › Défenses", ["securite", "defenses"], "module", sum(n for _, n in f2b),
               ["par fail2ban · " + ", ".join(n for n, _ in f2b) if f2b else "fail2ban installé, aucune prison relevée"], None, "fail2ban installé")
    certs = _liste(_ok(s, "certificats"), "certificats")
    if _etat(s, "certificats") == "ok":
        jours = sorted((c.get("jours"), str(c.get("hote") or (c.get("noms") or [""])[0])) for c in certs if isinstance(c.get("jours"), (int, float)))
        voisin("certs", "Certificats", "Sécurité › Certificats", ["certificats", ""], "module", len(certs), ["le plus court : %d j" % jours[0][0], jours[0][1]] if jours else ["aucun certificat suivi"],
               ["%d j" % jours[0][0], "d" if jours[0][0] < 7 else "w" if jours[0][0] < 21 else "ok"] if jours else None, "module Certificats installé")
    elif _liste(_ok(s, "certs_disque")):
        voisin("certs", "Certificats", "Logithèque", ["logitheque", ""], "detecte", len(_liste(_ok(s, "certs_disque"))), [], None, "%d certificats trouvés sur le disque" % len(_liste(_ok(s, "certs_disque"))))

    def reseau_prive(cle, titre, ou, aller, donnees, preuves):
        if _etat(s, cle) == "ok" and isinstance(donnees, dict):
            lp = _liste(donnees, "pairs")
            hors = [str(p.get("nom") or "?") for p in lp if not p.get("en_ligne")]
            relie = donnees.get("etat") == "connecte"
            voisin(cle, titre, ou, aller, "module", "%d / %d" % (len(lp) - len(hors), len(lp)) if lp else ("relié" if relie else "non relié"),
                   ["hors ligne : " + ", ".join(hors[:4]) + ("…" if len(hors) > 4 else "") if hors else ("toutes en ligne" if lp else "aucune autre machine"),
                    "" if relie else "cette machine n’est pas reliée"],
                   ["non relié", "w"] if not relie else (["%d hors ligne" % len(hors), ""] if hors else ["toutes en ligne", "ok"]) if lp else None, preuves[0] if preuves else "module installé")
        elif preuves:
            voisin(cle, titre, "Logithèque", ["logitheque", ""], "muet" if _etat(s, cle) == "muet" else "detecte", None, [], None, " · ".join(preuves))

    reseau_prive("tailscale", "Tailscale", "Parc › Tailscale", ["tailscale", ""], ts, [p for p in ("interface tailscale0" if "interface.tailscale0" in L else "", "tailscale installé" if logiciel.get("tailscale") else "") if p])
    nb = _ok(s, "netbird") or {}
    reseau_prive("netbird", "NetBird", "Parc › NetBird", ["netbird", ""], nb, [p for p in ("interface wt0" if "interface.wt0" in L else "", "conteneur netbird" if any("netbird" in str(c.get("image") or "") for c in _liste(_ok(s, "conteneurs"))) else "") if p])
    if _etat(s, "panneau_sites") == "ok":
        sv = _liste(_ok(s, "panneau_services"))
        arretes = 0          # le panneau dit « arrêtés » des services que systemd voit tourner : on ne reprend pas ce chiffre tant qu'il n'est pas fiable (la page Services fait foi)
        compte = lambda cle: len(_liste(_ok(s, cle))) if _etat(s, cle) == "ok" else None    # noqa: E731
        copies = _liste(_ok(s, "panneau_copies")) if _etat(s, "panneau_copies") == "ok" else None
        voisin("heberg", "Hébergement", "Parc › Hébergement", ["hebergement", ""], "module", len(_liste(_ok(s, "panneau_sites"))), [], ["%d arrêté%s" % (arretes, "s" if arretes > 1 else ""), "w"] if arretes else None,
               "panneau FastPanel", {"sites": len(_liste(_ok(s, "panneau_sites"))), "services": ("%d arrêté%s" % (arretes, "s" if arretes > 1 else "")) if arretes else ("%d actifs" % len(sv) if sv else None),
                                     "bases": compte("panneau_bases"), "boîtes": compte("panneau_mail"), "copies": len(copies) if copies is not None else None, "comptes": compte("panneau_comptes")})
    elif "fastpanel2" in {str(x.get("name")) for x in _liste(_ok(s, "services"))}:
        voisin("heberg", "Hébergement", "Logithèque", ["logitheque", ""], "muet" if _etat(s, "panneau_sites") == "muet" else "detecte", None, [], None, "service fastpanel2")
    if _etat(s, "depots") == "ok":
        dest = _liste(_ok(s, "depots"), "destinations")
        dehors = L.get("sauvegarde.hors_machine") or {}
        voisin("depots", "Dépôts distants", "Sauvegardes › Destinations", ["sauvegardes", ""], "module", len(dest),
               ["aucune copie hors de la machine" if dehors.get("severity") == "warning" else ("dépôt%s de copie" % ("s" if len(dest) > 1 else "") if dest else "aucun dépôt")],
               ["à regarder", "w"] if dehors.get("severity") == "warning" else None, "module Sauvegardes installé")
    # ce que le Sensorium voit sur la machine et qu'aucun module ne suit : une vignette « détecté »
    if logiciel.get("wg") or any(k.startswith("interface.wg") for k in L):
        voisin("wireguard", "WireGuard", "Logithèque", ["logitheque", ""], "detecte", None, [], None, "interface wg" if any(k.startswith("interface.wg") for k in L) else "wg installé")

    # ── les logiciels, Cassandra sur la machine
    cassandra = [{"cle": k, "titre": str(L[k].get("libelle") or k), "texte": v(k)} for k in ("noyau.version", "noyau.service", "code.scelle", "store.total", "courtier.commandes", "courtier.etat", "noyau.sauvegarde") if k in L]
    return {"ok": True, "source": source, "machine": machine, "sante": sante, "ressources": ressources, "disques": disques, "cloche": cloche, "processus": processus, "oom": oom,
            "services": services, "conteneurs": conteneurs, "docker": docker_la, "sessions": sessions, "connexions": connexions, "refus": refus, "voisins": voisins, "memoire": memoire,
            "logiciels": {"installes": sorted(k for k, i in logiciel.items() if i), "absents": sorted(k for k, i in logiciel.items() if not i), "versions": versions}, "cassandra": cassandra}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _entier, _detail, _ok, _etat, _liste, _duree_docker, etat_conteneur, _reseau_de …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
