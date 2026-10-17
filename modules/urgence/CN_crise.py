# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La crise AUTOMATIQUE
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : urgence
# ZONE       : CN
# VERSION CN : 0.2.0  #63bb10
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La crise AUTOMATIQUE : quand la machine est paralysée ou attaquée, Cassandra coupe les envois et retient ses gestes autonomes. Fonctions pures, testées sans machine.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=63bb10 ▼▼▼
"""La crise AUTOMATIQUE : quand la machine est paralysée ou attaquée, Cassandra coupe les envois et retient ses gestes autonomes. Fonctions pures, testées sans machine.

Deux cas, décidés par Drisse (V18, 10-10) :
  - la machine est PARALYSÉE : la moitié ou plus des services critiques, ou des sites, en panne depuis plus de cinq minutes ;
  - la machine subit une ATTAQUE MAJEURE : un afflux d'adresses nouvelles d'un coup, très au-dessus de l'ordinaire.
Le premier palier est volontairement mince : les envois sont coupés et les agents n'écrivent plus. Elle ne ferme ni accès ni clé. Se lève d'un geste, ou le dit quand c'est calme.

Leçons gardées :
  - une mesure qui échoue ne déclenche JAMAIS rien : on ne crie pas au feu sur un doute ;
  - la paralysie doit TENIR (une panne d'une minute n'est pas une crise) ; l'attaque est déjà mesurée sur une fenêtre ;
  - une crise retenue n'est pas redite à chaque minute : une fois par quinze minutes ;
  - une crise en cours qui redevient calme le DIT une fois, mais ne se lève pas seule : c'est à l'humain de décider que c'est fini ;
  - ce qui règle « jusqu'où elle agit seule » est un choix de l'administrateur : en « raconter » elle détecte et le dit, elle ne coupe rien.
"""
from __future__ import annotations

import ipaddress

PART_PARALYSIE = 0.5
DUREE_S = 300
FENETRE_ATTAQUE_MIN = 10
SEUIL_ADRESSES = 40
CALME_S = 900
RETENUE_S = 900
MIN_SERVICES_CONNUS = 4
MIN_SITES = 2
SERVICES_CRITIQUES = ("nginx", "mysql", "mariadb", "php8.2-fpm", "php-fpm", "fastpanel2", "ssh", "sshd", "tailscaled")
RESEAUX_DE_CONFIANCE = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "100.64.0.0/10", "::1/128", "fc00::/7", "fe80::/10", "fd7a:115c:a1e0::/48")


def de_confiance(adresse, extra=()):
    """Une adresse de la maison (réseaux locaux, Tailscale) ou de confiance déclarée : jamais comptée comme un attaquant. Une adresse illisible n'en est pas une non plus."""
    try:
        c = ipaddress.ip_network(str(adresse).strip(), strict=False)
    except ValueError:
        return True
    for n in list(RESEAUX_DE_CONFIANCE) + [x for x in extra if x]:
        try:
            m = ipaddress.ip_network(str(n).strip(), strict=False)
        except ValueError:
            continue
        if m.version == c.version and (c.subnet_of(m) or m.subnet_of(c)):
            return True
    return False


def evaluer(services, sites, adresses, cfg=None):
    """Les mesures -> {paralysie, attaque, detail}. `services` : {nom: {"enabled": bool, "active": bool}} ou None (mesure en échec) ; `sites` : [{"up": bool}] ou None ;
    `adresses` : les adresses repoussées dans la fenêtre, ou None. Une mesure None ne dit rien : elle ne déclenche pas."""
    cfg = cfg or {}
    part = float(cfg.get("part_paralysie", PART_PARALYSIE))
    res = {"paralysie": False, "attaque": False, "detail": []}
    if services:
        connus = {n: s for n, s in services.items() if s and s.get("enabled")}          # ceux qui existent sur cette machine, et eux seuls
        tombes = sorted(n for n, s in connus.items() if not s.get("active"))
        if len(connus) >= MIN_SERVICES_CONNUS and len(tombes) / float(len(connus)) >= part:
            res["paralysie"] = True
            res["detail"].append("%d services critiques sur %d à l'arrêt (%s)" % (len(tombes), len(connus), ", ".join(tombes)))
    if sites and len(sites) >= MIN_SITES:
        bas = [s for s in sites if not s.get("up")]
        if len(bas) / float(len(sites)) >= part:
            res["paralysie"] = True
            res["detail"].append("%d sites sur %d ne répondent plus" % (len(bas), len(sites)))
    if adresses is not None:
        inconnues = {a for a in adresses if not de_confiance(a, cfg.get("confiance", ()))}
        seuil = int(cfg.get("seuil_adresses", SEUIL_ADRESSES))
        if len(inconnues) >= seuil:
            res["attaque"] = True
            res["detail"].append("%d adresses différentes repoussées en %d minutes (seuil %d)" % (len(inconnues), int(cfg.get("fenetre_min", FENETRE_ATTAQUE_MIN)), seuil))
    return res


def decider(mesure, etat, maintenant, cfg=None):
    """Ce que la veille de cette minute décide. `etat` : {actif, paralysie_depuis, calme_depuis, calme_dit, retenue_t} (à rendre à la minute suivante).
    -> {"etat": nouvel état, "action": None | ("declencher", raison, types) | ("retenir", raison, types) | ("calme",)}."""
    cfg = cfg or {}
    e = dict({"actif": False, "paralysie_depuis": None, "calme_depuis": None, "calme_dit": False, "retenue_t": 0.0}, **(etat or {}))
    en_cause = mesure.get("paralysie") or mesure.get("attaque")
    if e["actif"]:
        if en_cause:
            e["calme_depuis"] = None
            return {"etat": e, "action": None}
        e["calme_depuis"] = e["calme_depuis"] or maintenant
        if maintenant - e["calme_depuis"] >= float(cfg.get("calme_s", CALME_S)) and not e["calme_dit"]:
            e["calme_dit"] = True
            return {"etat": e, "action": ("calme",)}
        return {"etat": e, "action": None}
    if mesure.get("paralysie"):
        e["paralysie_depuis"] = e["paralysie_depuis"] or maintenant
    else:
        e["paralysie_depuis"] = None
    tient = bool(e["paralysie_depuis"] and maintenant - e["paralysie_depuis"] >= float(cfg.get("duree_s", DUREE_S)))
    if not (tient or mesure.get("attaque")):
        return {"etat": e, "action": None}
    if maintenant - e["retenue_t"] < float(cfg.get("retenue_s", RETENUE_S)):
        return {"etat": e, "action": None}                                  # déjà retenue il y a moins de quinze minutes : on ne le redit pas
    raison = " · ".join(mesure.get("detail") or []) or "mesure inconnue"
    types = [k for k in ("paralysie", "attaque") if mesure.get(k)]
    if cfg.get("palier") != "auto":
        e["retenue_t"] = maintenant
        return {"etat": e, "action": ("retenir", raison, types)}
    e["paralysie_depuis"] = None
    return {"etat": e, "action": ("declencher", raison, types)}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : de_confiance, evaluer, decider
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
