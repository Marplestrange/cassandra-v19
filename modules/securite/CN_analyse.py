# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : L'analyse de sécurité
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : CN
# VERSION CN : 0.3.4  #737894
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : L'analyse de sécurité : des relevés BRUTS de la machine (commandes/CN_mesurer) -> exposition, pare-feu, accès, défenses, mises à jour, verdict. Fonctions pures, testées sans machine.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.4 empreinte=737894 ▼▼▼
"""L'analyse de sécurité : des relevés BRUTS de la machine (commandes/CN_mesurer) -> exposition, pare-feu, accès, défenses, mises à jour, verdict. Fonctions pures, testées sans machine.

Porté de la V18 (`_sec_*`, `_pf_*`), avec les leçons payées en service :
  - le pare-feu qui compte est celui que le NOYAU applique (iptables -S) : un panneau, un plan ou une annonce ne valent que si le noyau les porte ;
  - « ouvert au réseau local » ne se lit pas sur l'adresse d'écoute seule : sous « refuser par défaut », seul le parc joint la plupart des ports ;
  - un serveur web public est le but d'un hébergeur : seul un AUTRE service public mérite un regard ;
  - une règle finale « tout refuser » filtre autant qu'une politique DROP, et les options de la CIBLE (--reject-with…) ne sont pas des conditions ;
  - une mesure qui manque est DITE manquante (null), jamais comptée « tout va bien ».
"""
from __future__ import annotations

import ipaddress
import re
import shlex

SENSIBLES = {"mysqld": "MySQL", "mariadbd": "MariaDB", "rpcbind": "rpcbind", "redis-server": "Redis", "memcached": "Memcached", "postgres": "PostgreSQL", "prometheus": "Prometheus",
             "node_exporter": "node-exporter", "prometheus-node": "node-exporter", "grafana": "Grafana", "grafana-server": "Grafana", "cupsd": "Impression (CUPS)",
             "avahi-daemon": "avahi", "snmpd": "SNMP", "mongod": "MongoDB", "ollama": "Ollama"}
NOMS = {"sshd": "SSH", "nginx": "Sites web (nginx)", "apache2": "Apache", "exim4": "Courrier (SMTP)", "master": "Courrier (SMTP)", "dovecot": "Courrier (IMAP, POP)", "proftpd": "FTP",
        "vsftpd": "FTP", "pure-ftpd": "FTP", "fastpanel2-ngin": "FastPanel", "fastpanel2": "FastPanel", "docker-proxy": "Docker", "tailscaled": "Tailscale", "named": "DNS",
        "systemd-resolve": "Résolveur DNS", "chronyd": "Horloge (NTP)"}
IGNORES = {"dhclient", "dhcpcd", "systemd-network", "systemd-timesyn"}                      # des CLIENTS qui tiennent un port ouvert : rien à joindre
WEB = ("nginx", "apache2", "httpd", "caddy", "haproxy", "traefik")
GESTES_SENSIBLES = {"mysqld": "mysql_local", "mariadbd": "mysql_local", "rpcbind": "arret:rpcbind", "avahi-daemon": "arret:avahi-daemon", "cupsd": "arret:cups"}
OUTILS = {"lynis": ("Lynis", "Audit de durcissement du système, chaque semaine : un score et des conseils."),
          "trivy": ("Trivy", "Failles connues dans les images Docker, chaque semaine."),
          "clamav": ("ClamAV", "Antivirus des fichiers venus de l'extérieur (sites, documents, dossiers personnels), chaque semaine."),
          "crowdsec": ("CrowdSec", "Bloque les attaquants repérés ici et ceux que sa communauté signale ; réseaux de confiance jamais bannis.")}
TS = ipaddress.ip_network("100.64.0.0/10")
TS6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")
CIBLES = {"ACCEPT": "autorise", "DROP": "refuse", "REJECT": "rejette", "RETURN": "rend la main", "LOG": "note dans le journal"}


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)
_REFERENCES = {}


def _appeler_point(point, entree):
    """Appelle le point d'évolution du module. Sans brancher() (un banc qui appelle la fonction seule), la RÉFÉRENCE du dépôt répond : points/EC_<point>.py, chargée par son chemin."""
    if _point is not None:
        return _point(point, entree)
    if point not in _REFERENCES:
        import importlib.util as _iu
        import pathlib as _pl
        chemin = _pl.Path(__file__).resolve().parent / "points" / ("EC_%s.py" % point)
        spec = _iu.spec_from_file_location("ec_ref_" + point, str(chemin))
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _REFERENCES[point] = getattr(mod, "point_" + point)
    return _REFERENCES[point](entree)


def portee(adresse):
    """machine | tailscale | reseau | public | tout — pour une adresse d'écoute de `ss`. Le calcul est un POINT D'ÉVOLUTION : points/EC_portee.py."""
    return _appeler_point("portee", {"adresse": adresse})["valeur"]


def adresses_machine(texte):
    """Les adresses publiques que porte la machine elle-même ; sans v4 publique, elle est derrière une box. Le calcul est un POINT D'ÉVOLUTION : points/EC_adresses_machine.py."""
    return _appeler_point("adresses_machine", {"texte": texte})["valeur"]


# ── le pare-feu du noyau (iptables -S) ──────────────────────────────────────────────────────────────────────────
def pf_chaines(texte):
    """(lu, {chaîne: politique}, {chaîne: [jetons de chaque règle]})."""
    pol, ch = {}, {}
    if texte is None:
        return False, pol, ch
    for l in texte.splitlines():
        try:
            j = shlex.split(l)
        except ValueError:
            j = l.split()
        if len(j) >= 3 and j[0] == "-P":
            pol[j[1]] = j[2]
            ch.setdefault(j[1], [])
        elif len(j) >= 2 and j[0] == "-N":
            ch.setdefault(j[1], [])
        elif len(j) >= 2 and j[0] == "-A":
            ch.setdefault(j[1], []).append(j[2:])
    return True, pol, ch


def _val(j, *opts):
    """(valeur, niée) de la première option trouvée parmi `opts`."""
    for i, x in enumerate(j):
        if x in opts and i + 1 < len(j):
            return j[i + 1], (i > 0 and j[i - 1] == "!")
    return "", False


def _ports(j):
    v, _ = _val(j, "--dport", "--dports", "--destination-port", "--destination-ports")
    out = []
    for morceau in v.split(","):
        a, _, b = morceau.partition(":")
        if a.isdigit():
            out.append((int(a), int(b) if b.isdigit() else int(a)))
    return out


_OPTIONS_CIBLE = ("--reject-with", "--log-prefix", "--log-level", "--to-destination", "--to-source", "--to-ports", "--set-mark", "--set-xmark")


def _sans_options_cible(j):
    """_sans_options_cible. Le calcul est un POINT D'ÉVOLUTION : points/EC_sans_options_cible.py."""
    return _appeler_point("sans_options_cible", {"j": j})["valeur"]


def pf_lisible(j):
    """Une règle en clair : conditions, cible, et si elle s'applique à tout (aucune condition)."""
    cible, _ = _val(j, "-j", "-g")
    j = _sans_options_cible(j)                 # sans ce retrait, un REJECT final passait pour conditionnel et le verdict restait « ouvert »
    conds = []
    s, ns = _val(j, "-s", "--source")
    if s:
        conds.append(("sauf depuis " if ns else "depuis ") + s)
    i, ni = _val(j, "-i", "--in-interface")
    if i:
        conds.append(("hors interface " if ni else "par ") + i)
    p, _ = _val(j, "-p", "--protocol")
    ports = _ports(j)
    if ports:
        conds.append("%s %s" % ((p or "tcp/udp").upper(), ", ".join(("%d" % a) if a == b else "%d-%d" % (a, b) for a, b in ports)))
    elif p:
        conds.append(p.upper())
    sp, _ = _val(j, "--sport", "--source-port")
    if sp:
        conds.append("depuis le port %s" % sp.replace(":", "-"))
    ic, _ = _val(j, "--icmp-type", "--icmpv6-type")
    if ic:
        conds.append({"8": "ping", "echo-request": "ping", "0": "réponse de ping", "echo-reply": "réponse de ping"}.get(ic, "ICMP " + ic))
    etat, _ = _val(j, "--ctstate", "--state")
    if etat:
        conds.append("connexions déjà établies" if set(etat.split(",")) <= {"RELATED", "ESTABLISHED"} else "état " + etat)
    com, _ = _val(j, "--comment")
    if com:
        conds.append("« %s »" % com[:60])
    connues = {"-p", "--protocol", "-s", "--source", "-i", "--in-interface", "--dport", "--dports", "--ctstate", "--state", "--comment", "-j", "-g", "-m", "!",
               "--destination-port", "--destination-ports", "--sport", "--source-port", "--icmp-type", "--icmpv6-type"}
    autres = [x for x in j if x.startswith("-") and x not in connues]
    if autres:                                   # toute autre option (-m set, --match-set, -d…) est une condition : la règle ne vaut pas pour tout
        conds.append(" ".join(autres)[:60])
    return {"cible": cible, "conditions": conds, "pour_tout": not conds, "proto": (p or "").lower(), "ports": ports, "source": "" if ns else s}


def pf_parcours(pol, ch):
    """Chaque règle ATTEINTE depuis INPUT, dans l'ordre, sous-chaînes dépliées ; et le verdict effectif."""
    lignes = []
    refuse_tout = [False]

    def suivre(nom, prof, vu, sans_condition):
        for j in ch.get(nom, []):
            r = pf_lisible(j)
            r.update({"chaine": nom, "profondeur": prof, "brut": " ".join(j)[:200]})
            if r["cible"] in ch and r["cible"] not in vu and prof < 6:
                r["saut"] = True
                lignes.append(r)
                suivre(r["cible"], prof + 1, vu | {r["cible"]}, sans_condition and r["pour_tout"])
                continue
            lignes.append(r)
            if r["pour_tout"] and r["cible"] in ("DROP", "REJECT") and sans_condition:
                refuse_tout[0] = True            # une règle finale « tout refuser » filtre autant qu'une politique DROP
            if r["pour_tout"] and r["cible"] in ("RETURN", "ACCEPT", "DROP", "REJECT"):
                return                           # au-delà, plus rien n'est atteint dans cette chaîne

    suivre("INPUT", 0, {"INPUT"}, True)
    politique = pol.get("INPUT", "?")
    return {"politique": politique, "regles": lignes, "filtre": politique in ("DROP", "REJECT") or refuse_tout[0],
            "refus": len([x for x in lignes if x["cible"] in ("DROP", "REJECT")]), "autorise": len([x for x in lignes if x["cible"] == "ACCEPT"])}


def pf_admis(v4, port, proto):
    """Qui le pare-feu laisse joindre ce port depuis le réseau : « tous », « reseau » (une plage locale entière), « parc » (des adresses une à une), ou « » (personne).
    Les règles liées à une interface (lo, Tailscale, Docker) ou à l'état « déjà établie » ne comptent pas : elles ne valent pas pour un visiteur du réseau."""
    if not v4 or not v4.get("filtre"):
        return "tous"
    rang = {"": 0, "parc": 1, "reseau": 2, "tous": 3}
    mieux = ""
    for r in v4.get("regles") or []:
        if r.get("saut") or r.get("cible") != "ACCEPT":
            continue
        conds = " ".join(r.get("conditions") or [])
        if "par " in conds or "hors interface" in conds or "connexions déjà établies" in conds or "état " in conds or "ping" in conds or "depuis le port" in conds:
            continue
        if r.get("proto") not in ("", "all", proto):
            continue
        if r.get("ports") and not any(a <= port <= b for a, b in r["ports"]):
            continue
        s = r.get("source") or ""
        if not s:
            niv = "tous"
        else:
            try:
                niv = "parc" if ipaddress.ip_network(s, strict=False).prefixlen >= 32 else "reseau"
            except ValueError:
                niv = "parc"
        if rang[niv] > rang[mieux]:
            mieux = niv
    return mieux


def docker_publies(texte):
    """Les ports publiés par Docker : ils passent par FORWARD, à côté d'INPUT — un pare-feu qui ne regarde qu'INPUT ne les voit pas. Le calcul est un POINT D'ÉVOLUTION : points/EC_docker_publies.py."""
    return _appeler_point("docker_publies", {"texte": texte})["valeur"]


def pf_accord(regles_panneau, ch, politique_panneau, politique_noyau, refuse_tout):
    """Le panneau et le noyau, règle à règle : ce que le panneau déclare est-il appliqué, et le noyau porte-t-il dans la chaîne du panneau des règles qu'il ignore ?"""
    noyau = [pf_lisible(j) for j in ch.get("fastpanel_rules", [])]
    manquantes = []
    for r in regles_panneau or []:
        a, _, b = str(r.get("ports") or "").partition("-")
        if not a.isdigit():
            continue
        a, b = int(a), int(b) if b.isdigit() else int(a)
        proto = str(r.get("proto") or "").lower()
        trouve = any(any(x <= a and b <= y for x, y in n["ports"]) and (proto in ("all", "") or n["proto"] in (proto, "")) for n in noyau)
        if not trouve:
            manquantes.append(str(r.get("nom") or "%s/%s" % (a, proto)))
    connues = len(regles_panneau or [])
    inconnues = max(0, len([n for n in noyau if n["ports"]]) - (connues - len(manquantes)))
    p = str(politique_panneau or "").upper()
    pol_ok = (not p) or (p == "DROP") == (politique_noyau in ("DROP", "REJECT") or refuse_tout)
    return {"accord": not manquantes and not inconnues and pol_ok, "manquantes": manquantes, "inconnues": inconnues, "politique_fp": p, "politique_ok": pol_ok, "chaine_noyau": len(noyau)}


def parefeu(m, panneau=None):
    """Le pare-feu tel que le NOYAU l'applique (la seule vérité). `panneau` : ce que rend le module d'hébergement (règles, politique, essais) quand il existe ;
    le noyau est alors confronté à ce que le panneau déclare."""
    lu4, pol4, ch4 = pf_chaines(m.get("iptables"))
    lu6, pol6, ch6 = pf_chaines(m.get("ip6tables"))
    noyau = {"lu": lu4, "outil": "iptables", "v4": pf_parcours(pol4, ch4) if lu4 else None, "v6": pf_parcours(pol6, ch6) if lu6 else None,
             "docker": docker_publies(m.get("iptables_docker")) if lu4 else []}
    if not lu4:
        t = m.get("nft")
        drop = bool(t and re.search(r"hook input[^\n]*policy drop", t))
        noyau.update({"outil": "nftables", "lu": t is not None,
                      "v4": {"politique": "DROP" if drop else ("ACCEPT" if t is not None else "?"), "regles": [], "filtre": drop, "refus": 0, "autorise": 0}})
    v4 = noyau["v4"] or {}
    noyau["filtre"] = bool(v4.get("filtre"))
    noyau["v6_ouvert"] = bool(noyau["v6"]) and not noyau["v6"]["filtre"] and noyau["filtre"]
    regles = [r for r in v4.get("regles", []) if not r.get("saut")]
    fw = {"source": "systeme", "outil": noyau["outil"], "politique": v4.get("politique", "?"), "filtre": noyau["filtre"], "regles_systeme": len(regles), "panneau": None,
          "panneau_url": "", "noyau": noyau}
    if panneau and panneau.get("ok"):
        fw.update({"source": "fastpanel", "panneau": panneau.get("regles") or [], "politique_panneau": panneau.get("politique") or "", "api_ok": True, "api_erreur": ""})
        if lu4:
            noyau["accord"] = pf_accord(fw["panneau"], ch4, fw["politique_panneau"], v4.get("politique", "?"), v4.get("filtre", False))
    elif panneau:                                           # le panneau existe mais ne répond pas : on le dit, le noyau reste la vérité
        fw.update({"api_ok": False, "api_erreur": panneau.get("erreur") or "panneau injoignable"})
    return fw


# ── l'exposition : un service par ligne, sur quatre anneaux ─────────────────────────────────────────────────────
def exposition(ecoutes, machine, fw, port_cassandra=9000, redirections=None):
    par = {}
    for e in ecoutes or []:
        p = e["processus"]
        if p in IGNORES:
            continue
        nom = "Cassandra" if (p.startswith("python") and str(e["port"]) == str(port_cassandra)) else (SENSIBLES.get(p) or NOMS.get(p) or p)
        s = par.setdefault(nom, {"nom": nom, "processus": p, "ports": set(), "portees": set(), "sensible": p in SENSIBLES, "unite": e.get("unite") or ""})
        s["ports"].add("%s/%s" % (e["port"], e["proto"]))
        s["portees"].add(portee(e["adresse"]))
    derriere_box = not machine.get("public_v4")
    v4 = (fw.get("noyau") or {}).get("v4") if (fw.get("noyau") or {}).get("lu") else None
    mes_ips = set(machine.get("ips_locales") or [])
    sortie = []
    for s in par.values():
        pt = s["portees"]
        ecoute_reseau = bool(pt & {"tout", "reseau", "public"})
        admis = []
        for x in s["ports"]:
            p, _, pr = x.partition("/")
            admis.append(pf_admis(v4, int(p), pr) if v4 else ("tous" if not fw.get("filtre") else ""))
        reseau = ecoute_reseau and any(a in ("tous", "reseau") for a in admis)
        parc = ecoute_reseau and not reseau and "parc" in admis
        ports_tcp = {int(x.split("/")[0]) for x in s["ports"] if x.endswith("/tcp")}
        ports_udp = {int(x.split("/")[0]) for x in s["ports"] if x.endswith("/udp")}
        if "public" in pt or ("tout" in pt and not derriere_box):
            internet = "filtre" if fw.get("filtre") else "oui"
        elif (pt & {"tout", "reseau"}) and derriere_box and redirections is not None:
            vise = [r for r in redirections if r["vers"] in mes_ips and r["port_vers"] in (ports_tcp if r["proto"] == "tcp" else ports_udp)]
            if not vise:
                internet = "non"
            else:
                ok = any(pf_admis(v4, r["port_vers"], r["proto"]) == "tous" for r in vise) if v4 else not fw.get("filtre")
                internet = "oui" if ok else "filtre"
        elif "tout" in pt:
            internet = "box"                     # derrière une box dont on ne lit pas les redirections : on ne sait pas, on le dit
        else:
            internet = "non"
        geste = GESTES_SENSIBLES.get(s["processus"], "") if (s["sensible"] and reseau) else ""
        sortie.append({"nom": s["nom"], "processus": s["processus"], "ports": sorted(s["ports"], key=lambda x: int(x.split("/")[0])), "machine": True,
                       "tailscale": bool(pt & {"tout", "tailscale"}), "reseau": reseau, "parc": parc, "internet": internet, "sensible": s["sensible"], "geste": geste, "unite": s.get("unite") or ""})
    sortie.sort(key=lambda x: (not (x["sensible"] and x["reseau"]), not x["reseau"], x["nom"].lower()))
    return sortie


# ── accès, défenses, mises à jour ───────────────────────────────────────────────────────────────────────────────
def ssh(m):
    cfg = m.get("sshd") or {}
    return {"lu": bool(cfg), "mots_de_passe": cfg.get("passwordauthentication", "?"), "root": cfg.get("permitrootlogin", "?"), "x11": cfg.get("x11forwarding", "?"),
            "port": cfg.get("port", "?"), "echecs_7j": m.get("echecs_ssh_7j") or 0}


def fail2ban(m):
    """fail2ban. Le calcul est un POINT D'ÉVOLUTION : points/EC_fail2ban.py."""
    return _appeler_point("fail2ban", {"m": m})["valeur"]


def maj(m):
    x = m.get("maj") or {}
    auto_installe = bool(x.get("auto_installe"))
    actif = auto_installe and bool(re.search(r'Unattended-Upgrade\s+"1"', x.get("auto_conf") or ""))
    return {"securite_en_attente": int(x.get("securite") or 0), "paquets_en_attente": int(x.get("a_mettre_a_jour") or 0), "auto_installe": auto_installe, "auto_actif": actif,
            "noyau": [], "noyau_ecarts": [], "services_en_echec": list(x.get("unites_en_echec") or []), "reboot_requis": bool(x.get("reboot_requis")), "lu": bool(x.get("apt"))}


def _niveau_outil(k, o):
    """(niveau, texte) de l'outil `k`, pour l'écran et le verdict. Un résultat illisible est « premier passage à venir », jamais « ok »."""
    if not o.get("installe"):
        return "", "non installé" + (" · " + o["pourquoi"] if not o.get("convient", True) and o.get("pourquoi") else "")
    r = o.get("resultat") or {}
    if not r:
        return "pas_encore", "installé · premier passage à venir"
    pl = lambda n, mot: mot + ("s" if n > 1 else "")                    # noqa: E731
    if k == "lynis":
        av = len(r.get("avertissements") or [])
        sg = r.get("suggestions_n", 0)
        return ("regarder" if av else "ok"), "score %s/100 · %d %s · %d %s" % (r.get("score") if r.get("score") is not None else "?", av, pl(av, "avertissement"), sg, pl(sg, "conseil"))
    if k == "trivy":
        imgs = r.get("images") or []
        crit = sum(i.get("critiques", 0) for i in imgs)
        corr = sum(i.get("corrigeables", 0) for i in imgs)
        return ("regarder" if crit else "ok"), "%d %s · %d %s · %d déjà %s par leur auteur, en attente d'une nouvelle image" % (
            len(imgs), pl(len(imgs), "image"), crit, "failles critiques" if crit > 1 else "faille critique", corr, "corrigées" if corr > 1 else "corrigée")
    if k == "clamav":
        n = len(r.get("infectes") or [])
        if n:
            return "panne", "%d FICHIER%s INFECTÉ%s" % (n, "S" if n > 1 else "", "S" if n > 1 else "")
        fait = ("%d fichiers analysés" % r["analyses"]) if r.get("analyses") is not None else ("balayage complet en %d min" % r["duree_min"] if r.get("duree_min") is not None else "balayage complet")
        return ("regarder" if r.get("erreur") else "ok"), "%s · aucune menace · signatures du %s" % (fait, r.get("signatures") or "?")
    if k == "crowdsec":
        if not (r.get("moteur") and r.get("videur")):
            return "panne", "moteur %s · videur %s" % ("actif" if r.get("moteur") else "ARRÊTÉ", "actif" if r.get("videur") else "ARRÊTÉ")
        loc, a24 = r.get("decisions_locales", 0), r.get("alertes_24h", 0)
        return "ok", "%d %s ici · %d de la liste communautaire · %d %s en 24 h" % (loc, "adresses bannies" if loc > 1 else "adresse bannie", r.get("liste_communautaire", 0), a24, pl(a24, "alerte"))
    return "", ""


def outils(m):
    """Lynis, Trivy, ClamAV, CrowdSec : optionnels, jamais requis. L'état vient de leur programme (à root) ; sans lui, seulement ce qui est présent sur la machine. Le calcul est un POINT D'ÉVOLUTION : points/EC_outils_analyse.py."""
    return _appeler_point("outils_analyse", {"m": m})["valeur"]


def verdict(d):
    """Le verdict se CALCULE sur les mesures ; le modèle n'y touche pas."""
    expo = d["exposition"]
    reseau = [s for s in expo if s["reseau"] and s["nom"] != "Cassandra"]
    sensibles = [s for s in reseau if s["sensible"]]
    publics = [s for s in expo if s["internet"] == "oui"]
    publics_sensibles = [s for s in publics if s["sensible"]]
    publics_inattendus = [s for s in publics if s["processus"] not in WEB]
    fw, sh, mj, f2b = d["parefeu"], d["ssh"], d["maj"], d["fail2ban"]
    box = not d["machine"].get("public_v4")
    pl = lambda n, mot: mot + ("s" if n > 1 else "")                    # noqa: E731
    if publics_sensibles:
        niveau = "panne"
        titre = "%s %s joignable%s depuis Internet." % (", ".join(s["nom"] for s in publics_sensibles[:3]), "est" if len(publics_sensibles) == 1 else "sont", "" if len(publics_sensibles) == 1 else "s")
    elif reseau and not fw["filtre"]:
        niveau = "regarder"
        titre = ("Rien n'est exposé à Internet d'ici, mais %d %s à tout le réseau local, sans pare-feu." % (len(reseau), "services s'ouvrent" if len(reseau) > 1 else "service s'ouvre")) if not publics else \
                ("%d %s, et %d %s au réseau local sans pare-feu." % (len(publics), pl(len(publics), "service public"), len(reseau), "ouverts" if len(reseau) > 1 else "ouvert"))
    elif sensibles:
        niveau = "regarder"
        titre = "%d %s %s au réseau local." % (len(sensibles), pl(len(sensibles), "service sensible"), "s'ouvrent" if len(sensibles) > 1 else "s'ouvre")
    else:
        niveau, titre = "stable", "Rien d'ouvert au-delà de ce qui doit l'être."
    sous = []
    if sensibles:
        sous.append("Dont %s, qui n'%s aucune raison de quitter la machine." % (", ".join(s["nom"] for s in sensibles[:4]), "a" if len(sensibles) == 1 else "ont"))
    if sh.get("mots_de_passe") == "yes":
        sous.append("SSH accepte encore les mots de passe.")
    if not mj["auto_actif"]:
        sous.append("Rien n'applique les correctifs de sécurité sans vous.")
    if publics and not box:
        sous.append("« Joignable » se lit sur la machine : un pare-feu chez l'hébergeur, s'il existe, ne se voit pas d'ici.")
    redir = d.get("box_redirections")
    if box and redir is None:
        sous.append("La machine est derrière une box : ce que la box redirige depuis Internet ne se voit pas d'ici.")
    elif box:
        vers = sorted({"%s %d" % (r["proto"].upper(), r["port"]) for r in redir if r["vers"] in (d["machine"].get("ips_locales") or [])})
        sous.append("Derrière la box, qui ne redirige vers cette machine %s (lu par son API)." % ("que " + ", ".join(vers) if vers else "rien"))
    if niveau == "stable" and not sous:
        sous.append("Pare-feu actif, SSH par clé, correctifs appliqués.")
    chiffres = [
        {"v": str(len(publics)), "lib": "exposés à Internet" + (" (hors redirections de la box)" if box and redir is None else ""), "niveau": "panne" if publics_sensibles else ("regarder" if publics_inattendus else "ok")},
        {"v": str(len(reseau)), "lib": "ouverts au réseau local", "niveau": "regarder" if reseau and not fw["filtre"] else "ok"},
        {"v": {"yes": "oui", "no": "non"}.get(sh.get("mots_de_passe"), "?"), "lib": "mots de passe SSH acceptés", "niveau": "regarder" if sh.get("mots_de_passe") == "yes" else "ok"},
        {"v": str(mj["securite_en_attente"]), "lib": "correctif%s de sécurité en attente" % ("s" if mj["securite_en_attente"] > 1 else ""), "niveau": "regarder" if mj["securite_en_attente"] else "ok"}]
    ssh_niv = "regarder" if sh.get("mots_de_passe") == "yes" or sh.get("x11") == "yes" or sh.get("root") == "yes" else "ok"
    conf = d.get("confinement") or {}
    familles = [
        {"page": "exposition", "niveau": "panne" if publics_sensibles else ("regarder" if (reseau and not fw["filtre"]) or sensibles else "ok"), "lib": "Exposition", "n": len(reseau),
         "dit": "%d ouvert%s au réseau local%s · %d public%s" % (len(reseau), "s" if len(reseau) > 1 else "", (" dont %d sensible%s" % (len(sensibles), "s" if len(sensibles) > 1 else "")) if sensibles else "", len(publics), "s" if len(publics) > 1 else "")},
        {"page": "parefeu", "niveau": ("ok" if fw["filtre"] else "panne") if (fw.get("noyau") or {}).get("lu") else "regarder", "lib": "Pare-feu", "n": len(fw.get("panneau") or []) if fw.get("source") == "fastpanel" else fw.get("regles_systeme", 0),
         "dit": (("FastPanel · " if fw.get("source") == "fastpanel" else "Système · ") + ("filtre ce qui n'est pas permis" if fw["filtre"] else "tout accepter (politique %s)" % fw["politique"])) if (fw.get("noyau") or {}).get("lu")
                else "lecture du noyau impossible : aucune affirmation sur ce qui est filtré"},
        {"page": "acces", "niveau": ssh_niv, "lib": "Accès", "n": sum(1 for k in ("mots_de_passe", "x11") if sh.get(k) == "yes"),
         "dit": "SSH %s · %d échec%s en 7 jours" % ("par mot de passe et par clé" if sh.get("mots_de_passe") == "yes" else "par clé seulement", sh.get("echecs_7j", 0), "s" if sh.get("echecs_7j", 0) > 1 else "")},
        {"page": "defenses", "niveau": "regarder" if (not f2b.get("actif")) or conf.get("actif") or conf.get("confine") else "ok", "lib": "Défenses", "n": 0,
         "dit": ("fail2ban actif (%d jail%s)" % (len(f2b["jails"]), "s" if len(f2b["jails"]) > 1 else "") if f2b.get("actif") else "fail2ban absent") + (" · Cassandra confinée" if conf.get("actif") or conf.get("confine") else " · Cassandra libre")},
        {"page": "maj", "niveau": "regarder" if mj["securite_en_attente"] or not mj["auto_actif"] or mj["noyau_ecarts"] or mj["services_en_echec"] else "ok", "lib": "Mises à jour et noyau",
         "n": (1 if mj["securite_en_attente"] else 0) + (0 if mj["auto_actif"] else 1) + len(mj["noyau_ecarts"]),
         "dit": "%d correctif%s en attente · %s · noyau %s" % (mj["securite_en_attente"], "s" if mj["securite_en_attente"] > 1 else "", "correctifs automatiques" if mj["auto_actif"] else "rien d'automatique",
                                                          "conforme" if not mj["noyau_ecarts"] else "%d écart%s" % (len(mj["noyau_ecarts"]), "s" if len(mj["noyau_ecarts"]) > 1 else ""))}]
    O = d.get("outils") or {}
    if O:
        inst = [k for k, o in O.items() if o.get("installe")]
        pire = "panne" if any(O[k].get("niveau") == "panne" for k in inst) else "regarder" if any(O[k].get("niveau") == "regarder" for k in inst) else ("ok" if inst else "")
        familles.append({"page": "outils", "niveau": pire, "lib": "Outils de sécurité", "n": len(inst),
                         "dit": "%d sur %d installé%s%s" % (len(inst), len(O), "s" if len(inst) > 1 else "", (" · " + ", ".join(OUTILS[k][0] for k in inst)) if inst else " · Lynis, Trivy, ClamAV, CrowdSec")})
        if pire == "panne":
            sous.insert(0, " ".join("%s : %s." % (OUTILS[k][0], O[k]["dit"]) for k in inst if O[k].get("niveau") == "panne"))
            niveau, titre = "panne", "Un outil de sécurité a trouvé un problème."
    return {"niveau": niveau, "titre": titre, "sous": " ".join(sous), "chiffres": chiffres, "familles": familles}


def etat(m, heure="", port_cassandra=9000, ailleurs=None, panneau=None, confinement=None):
    """L'état de sécurité de la machine, dans la forme que lit l'écran, depuis les relevés bruts de `mesurer`. Une mesure qui manque est dite manquante."""
    machine = adresses_machine(m.get("ip_addr"))
    fw = parefeu(m, panneau)
    comptes = m.get("comptes") or {"shells": [], "sudo": []}
    d = {"ok": True, "machine": machine, "parefeu": fw, "exposition": exposition(m.get("ecoutes"), machine, fw, port_cassandra), "box_redirections": None,
         "outils": outils(m), "ssh": ssh(m), "comptes": comptes, "cles_fichiers": m.get("cles_ssh") or {}, "cles": [], "fail2ban": fail2ban(m), "maj": maj(m),
         "cage": {"etat": m.get("cage") or "", "commandes_24h": 0, "vetos_24h": 0, "caviardages_24h": 0, "gestes_invites_24h": 0, "sessions": 0},
         "confinement": confinement or {}, "mesure": heure, "hote": m.get("hote") or "", "manques": [k for k in ("ecoutes", "ip_addr", "iptables", "sshd") if m.get(k) is None and not (k == "iptables" and m.get("nft") is not None)]}
    d["verdict"] = verdict(d)
    if d["manques"]:                         # un relevé manque : le verdict ne dit pas « stable », il dit ce qu'il ne sait pas
        noms = {"ecoutes": "les services à l'écoute", "ip_addr": "les adresses de la machine", "iptables": "le pare-feu", "sshd": "la configuration SSH"}
        d["verdict"].update({"niveau": "inconnu", "titre": "Je ne peux pas dire que la machine est sûre.",
                             "sous": "Ces relevés manquent : %s. Ce qui suit en tient compte." % ", ".join(noms[k] for k in d["manques"])})
    d["ailleurs"] = ailleurs or {"mes_cles": 0, "mes_sessions": 0, "certs": 0, "certs_7j": 0, "certs_30j": 0, "cloche": 0}
    d["audit_en_cours"] = False
    d["parefeu_essais"] = [{"jeton": e.get("jeton"), "quoi": e.get("quoi", ""), "reste": e.get("reste", 0)} for e in ((panneau or {}).get("essais") or [])]
    d["votre_ip"] = ""
    return d
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : portee, adresses_machine, pf_chaines, _val, _ports, _sans_options_cible, pf_lisible, pf_parcours …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
