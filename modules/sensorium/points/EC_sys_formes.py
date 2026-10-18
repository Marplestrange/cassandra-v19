# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sensorium : les mesures du système (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #00812a
# HÔTE CN    : CN_module.py · sys_formes @1.0
# RÔLE       : transforme ce que le Sensorium lit du système (sorties de commandes, fichiers de configuration, JSON de smartctl) en sessions, ports, certificats, disques, état du matériel et sites web déclarés.
# MÉTHODE    : fonctions pures, une par mesure ; le nexus lit les sources et décide des replis (who puis ss puis last ; ss puis netstat) ; l'EC ne lit jamais de fichier ni de commande.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=sys_formes contrat=@1.0 version=EC0 empreinte=00812a ▼▼▼
from datetime import datetime
import re

def _ip_de_pair(peer):
    ip = None
    m = re.search(r"\[::ffff:((\d{1,3}\.){3}\d{1,3})\]", peer)
    if m:
        ip = m.group(1)
    else:
        m = re.match(r"((\d{1,3}\.){3}\d{1,3}):\d+", peer)
        if m:
            ip = m.group(1)
        else:
            m = re.match(r"\[([^\]]+)\]:\d+", peer)
            if m:
                ip = m.group(1)
    return ip

def sessions_base(who_out, ss_out, now):
    """Les sessions ouvertes : `who` d'abord, puis les connexions SSH établies d'après `ss`. Un utilisateur sur un terminal, une adresse en SSH, n'apparaissent qu'une fois."""
    sessions = []
    seen = set()
    for line in who_out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        user = parts[0]
        tty = parts[1] if len(parts) > 1 else "?"
        ip_m = re.search(r"\(([\d.:a-fA-F]+)\)", line)
        ip = ip_m.group(1) if ip_m else "local"
        login_time = " ".join(parts[2:4]) if len(parts) >= 4 else parts[2] if len(parts) >= 3 else now
        key = f"{user}:{tty}"
        if key not in seen:
            seen.add(key)
            sessions.append({"user": user, "ip": ip, "login_time": login_time, "last_check": now})
    for line in ss_out.splitlines():
        if not line.strip() or line.startswith("Netid"):
            continue
        parts = line.split()
        local_idx = -1
        for i, p in enumerate(parts):
            if p.endswith(":22") or ":22 " in p or p == "[::]:22" or "]:22" in p:
                local_idx = i
                break
        if local_idx < 0:
            local_idx = 4
        peer_idx = local_idx + 1
        if peer_idx >= len(parts):
            continue
        ip = _ip_de_pair(parts[peer_idx])
        if not ip or ip in ("127.0.0.1", "::1"):
            continue
        proc_str = " ".join(parts[peer_idx + 1:]) if peer_idx + 1 < len(parts) else ""
        user_m = re.search(r'users=\(\("([^"]+)"', proc_str)
        user = user_m.group(1) if user_m else "sshd"
        key = f"ssh:{ip}"
        if key not in seen:
            seen.add(key)
            sessions.append({"user": user, "ip": ip, "login_time": now, "last_check": now})
    return sessions

def sessions_last(last_out, now):
    """Repli quand ni `who` ni `ss` ne donnent rien : les connexions encore ouvertes d'après `last`."""
    sessions = []
    seen = set()
    for line in last_out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        user = parts[0]
        ip_m = re.search(r"([\d.]+)", parts[2]) if len(parts) > 2 else None
        ip = ip_m.group(1) if ip_m else "local"
        key = f"{user}:{ip}"
        if key not in seen:
            seen.add(key)
            sessions.append({"user": user, "ip": ip, "login_time": now, "last_check": now})
    return sessions

def ports_ss(out, now):
    """Les ports à l'écoute d'après `ss -tulnp`, triés par numéro."""
    ports = []
    seen = set()
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("Netid"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0].lower()
        local = ""
        for col in parts[3:6]:
            if re.search(r":\d+$", col) or re.search(r"\]:\d+$", col):
                local = col
                break
        if not local:
            continue
        port_m = re.search(r":([\d]+)$", local)
        if not port_m:
            continue
        port = int(port_m.group(1))
        if port == 0:
            continue
        proc_col = " ".join(parts[5:]) if len(parts) > 5 else ""
        pname_m = re.search(r'"([^"]+)"', proc_col)
        process = pname_m.group(1)[:40] if pname_m else "system"
        key = f"{proto}:{port}"
        if key not in seen:
            seen.add(key)
            ports.append({"port": port, "protocol": proto, "process": process, "pid": 0, "last_check": now})
    return sorted(ports, key=lambda x: x["port"])

def ports_netstat(out, now):
    """Repli : les ports à l'écoute d'après `netstat -tulnp`."""
    ports = []
    seen = set()
    for line in out.splitlines():
        m = re.search(r"(tcp6?|udp6?)\s+\d+\s+\d+\s+[\d.:*]+:(\d+)\s+[\d.:*]+\s+\w+\s*(\S*)", line)
        if m:
            proto = m.group(1).lower()
            port = int(m.group(2))
            proc = m.group(3).split("/")[-1][:40] if "/" in m.group(3) else "system"
            key = f"{proto}:{port}"
            if key not in seen:
                seen.add(key)
                ports.append({"port": port, "protocol": proto, "process": proc, "pid": 0, "last_check": now})
    return sorted(ports, key=lambda x: x["port"])

def _nom_de_fichier(chemin):
    return chemin.rstrip("/").rsplit("/", 1)[-1]

def _radical(chemin):
    nom = _nom_de_fichier(chemin)
    i = nom.rfind(".")
    return nom[:i] if 0 < i < len(nom) - 1 else nom

def certificat(sortie, chemin, indice, now):
    """Un certificat d'après la sortie d'openssl (date, sujet, émetteur, noms alternatifs) ; None quand elle est illisible. `now` : l'instant reçu, en ISO."""
    if not sortie:
        return None
    date_m = re.search(r"notAfter=(.+)", sortie)
    if not date_m:
        return None
    try:
        expiry = datetime.strptime(date_m.group(1).strip(), "%b %d %H:%M:%S %Y %Z")
    except Exception:
        try:
            expiry = datetime.strptime(date_m.group(1).strip(), "%b %d %H:%M:%S %Y")
        except Exception:
            return None
    days = (expiry - datetime.fromisoformat(now)).days
    domain = indice
    san_m = re.search(r"DNS:([\w.*-]+)", sortie)
    if san_m:
        domain = san_m.group(1)
    elif not domain:
        cn_m = re.search(r"CN\s*=\s*([\w.*-]+)", sortie)
        domain = cn_m.group(1) if cn_m else _radical(chemin)
    if not domain or domain.strip(" -") == "":
        domain = _radical(chemin)
    issuer = ""
    iss_m = re.search(r"issuer=(.+)", sortie)
    if iss_m:
        s = iss_m.group(1)
        o_m = re.search(r"\bO\s*=\s*([^,/\n]+)", s)
        cn_m = re.search(r"\bCN\s*=\s*([^,/\n]+)", s)
        issuer = (o_m.group(1).strip() if o_m else (cn_m.group(1).strip() if cn_m else s.strip()))[:60]
    return {"domain": domain, "days_left": days, "cert_path": chemin,
            "issuer": issuer, "expiry_date": expiry.strftime("%Y-%m-%d"),
            "status": "expired" if days <= 0 else ("expiring" if days <= 30 else "valid"),
            "last_check": now}

def disque_smart(d, dev, now):
    """Un disque d'après le JSON de smartctl : santé, température, heures, secteurs réalloués ou en attente, usure."""
    attrs = {a.get("id"): a for a in ((d.get("ata_smart_attributes") or {}).get("table") or [])}

    def brut(i):
        a = attrs.get(i)
        return int((a.get("raw") or {}).get("value") or 0) if a else None

    def normal(i):
        a = attrs.get(i)
        return int(a.get("value")) if a and a.get("value") is not None else None
    nv = d.get("nvme_smart_health_information_log") or {}
    usure = nv.get("percentage_used")
    if usure is None:
        for i in (231, 202, 177, 233):
            v = normal(i)
            if v is not None and 0 <= v <= 100:
                usure = 100 - v
                break
    st = (d.get("smart_status") or {}).get("passed")
    return {
        "device": dev, "model": (d.get("model_name") or d.get("model_family") or "")[:60],
        "health": "PASSED" if st is True else ("FAILED" if st is False else "unknown"),
        "temperature": (d.get("temperature") or {}).get("current"),
        "power_on_hours": (d.get("power_on_time") or {}).get("hours"),
        "reallocated_sectors": brut(5) if brut(5) is not None else nv.get("media_errors"),
        "pending_sectors": brut(197),
        "uncorrectable": brut(198) if brut(198) is not None else brut(187),
        "usure_pct": usure,
        "last_check": now}

def temperature_max(valeurs):
    """La température la plus haute parmi les mesures plausibles (en degrés) ; None quand il n'y en a aucune."""
    temps = [v for v in valeurs if 0 < v < 150]
    return round(max(temps), 1) if temps else None

def heure_systeme(td):
    """L'heure est-elle synchronisée, et le fuseau, d'après `timedatectl show`."""
    td = td or ""
    m = re.search(r"Timezone=(\S+)", td)
    return {"heure_synchro": "oui" if "NTPSynchronized=yes" in td else ("non" if "NTPSynchronized=no" in td else ""),
            "fuseau": m.group(1) if m else ""}

def nom_du_systeme(texte):
    """Le nom lisible de l'OS d'après /etc/os-release ; vide quand il n'y est pas."""
    try:
        osr = dict(l.split("=", 1) for l in texte.splitlines() if "=" in l)
        return osr.get("PRETTY_NAME", "").strip('"')
    except Exception:
        return ""

def nombre_regles_nft(texte):
    """Le nombre de règles d'un jeu nftables."""
    return len([l for l in (texte or "").splitlines() if l.strip().startswith(("ip ", "tcp ", "udp ", "ct ", "iif", "oif", "counter", "drop", "accept", "reject"))])

def nombre_regles_iptables(texte):
    """Le nombre de règles d'après `iptables -S`."""
    return len([l for l in (texte or "").splitlines() if l.startswith("-A ")])

def sites_nginx(contenu):
    """Les noms de site qu'un fichier nginx déclare : [(domaine, ssl, racine, ip d'écoute)]."""
    ssl = bool(re.search(r"ssl_certificate", contenu))
    root_m = re.search(r"root\s+([^;]+);", contenu)
    root = root_m.group(1).strip() if root_m else ""
    ip_m = re.search(r"^\s*listen\s+(\d{1,3}(?:\.\d{1,3}){3}|\[[0-9a-fA-F:]+\]):\d+", contenu, re.M)
    ip = ip_m.group(1) if ip_m else ""
    trouves = []
    for sn in re.findall(r"server_name\s+([^;]+);", contenu):
        for domain in sn.strip().split():
            if domain and not domain.startswith(("_", "*", "#")):
                trouves.append([domain, ssl, root, ip])
    return trouves

def sites_apache(contenu):
    """Les noms de site qu'un fichier apache déclare : [(domaine, ssl, racine)]."""
    ssl = bool(re.search(r"SSLEngine\s+on", contenu, re.IGNORECASE))
    root_m = re.search(r"DocumentRoot\s+(\S+)", contenu)
    root = root_m.group(1).strip() if root_m else ""
    trouves = []
    for sn in re.findall(r"ServerName\s+(\S+)", contenu):
        trouves.append([sn.strip(), ssl, root])
    for sa in re.findall(r"ServerAlias\s+(.+)", contenu):
        for d in sa.strip().split():
            trouves.append([d, ssl, root])
    return trouves

def certificats_nginx(contenu):
    """Les certificats qu'un fichier nginx déclare : l'indice de domaine (son premier server_name) et les chemins."""
    sn_m = re.search(r"server_name\s+([^;]+);", contenu)
    hint = sn_m.group(1).strip().split()[0] if sn_m else ""
    return {"indice": hint, "chemins": re.findall(r"ssl_certificate\s+([^;]+);", contenu)}

def certificats_apache(contenu):
    """Les certificats qu'un fichier apache déclare."""
    sn_m = re.search(r"ServerName\s+(\S+)", contenu)
    hint = sn_m.group(1) if sn_m else ""
    return {"indice": hint, "chemins": re.findall(r"SSLCertificateFile\s+(\S+)", contenu)}

def cron_lignes(texte, utilisateur, now):
    """Les tâches planifiées d'un fichier crontab : une ligne par tâche, l'utilisateur lu dans la sixième colonne des fichiers système, sinon celui donné."""
    jobs = []
    for line in texte.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 7 and re.match(r"[a-zA-Z_][a-zA-Z0-9_-]*$", parts[5]):
            jobs.append({"user": parts[5], "schedule": " ".join(parts[:5]),
                         "command": " ".join(parts[6:])[:200], "last_check": now})
        elif len(parts) >= 6:
            jobs.append({"user": utilisateur, "schedule": " ".join(parts[:5]),
                         "command": " ".join(parts[5:])[:200], "last_check": now})
    return jobs

def services_api(liste, now):
    """Les services d'après l'API du panneau."""
    return [{"name": s.get("name", ""), "status": s.get("status", "unknown"),
             "version": s.get("version", ""), "last_check": now} for s in liste]

def services_systemctl(etats, now):
    """Les services d'après systemctl : [[nom, état]] ; seuls les états connus comptent."""
    return [{"name": svc, "status": st, "version": "", "last_check": now}
            for svc, st in etats
            if st in ("active", "inactive", "failed", "activating", "deactivating")]

def pools_php(confs, ps_sortie, journaux, jour, now):
    """Les pools PHP-FPM : confs [[chemin, texte]] (plafond pm.max_children, socket), processus vivants d'après `ps`, saturations du jour dans les journaux (textes)."""
    pools = {}
    for chemin, content in confs:
        nom = None
        for l in content.splitlines():
            t = l.strip()
            m = re.match(r"^\[([^\]]+)\]$", t)
            if m and m.group(1) != "global":
                nom = m.group(1)
                pools.setdefault(nom, {"pool": nom, "socket": "", "max_children": None, "conf": chemin})
            elif nom and t.startswith("listen") and "=" in t and not t.startswith("listen."):
                pools[nom]["socket"] = t.split("=", 1)[1].strip()
            elif nom and t.startswith("pm.max_children") and "=" in t:
                try:
                    pools[nom]["max_children"] = int(t.split("=", 1)[1].strip())
                except ValueError:
                    pass
    vivants = {}
    for l in (ps_sortie or "").splitlines():
        m = re.search(r"php-fpm: pool (\S+)", l)
        if m:
            v = vivants.setdefault(m.group(1), [0, 0])
            v[0] += 1
            if l.strip().startswith("R"):
                v[1] += 1
    satures = {}
    for texte in journaux:
        for l in texte.splitlines()[-3000:]:
            m = re.search(r"\[pool (\S+)\] server reached pm.max_children", l)
            if m and jour in l:
                satures[m.group(1)] = satures.get(m.group(1), 0) + 1
    out = []
    for nom in sorted(set(pools) | set(vivants)):
        p = pools.get(nom, {"pool": nom, "socket": "", "max_children": None})
        n, actifs = vivants.get(nom, [0, 0])
        out.append({"pool": nom, "socket": p.get("socket", ""), "total_processes": n, "active_processes": actifs,
                    "idle_processes": max(0, n - actifs), "max_children": p.get("max_children"),
                    "slow_requests": satures.get(nom, 0), "last_check": now})
    return out

def diskstats_lire(texte):
    """Les compteurs d'entrées-sorties par disque d'après /proc/diskstats (les partitions sont ignorées)."""
    stats = {}
    try:
        for line in texte.splitlines():
            parts = line.split()
            if len(parts) < 14:
                continue
            dev = parts[2]
            if re.search(r"\d+$", dev) and not re.match(r"^[sv]d[a-z]$", dev):
                continue
            stats[dev] = {
                "reads": int(parts[3]),
                "read_sects": int(parts[5]),
                "writes": int(parts[7]),
                "write_sects": int(parts[9]),
            }
    except Exception:
        pass
    return stats

def diskstats_delta(s1, s2, now):
    """Le débit et les opérations par disque entre deux relevés des compteurs."""
    result = []
    for dev in s1:
        if dev not in s2:
            continue
        d1, d2 = s1[dev], s2[dev]
        result.append({
            "ts": now,
            "device": dev,
            "read_bytes": (d2["read_sects"] - d1["read_sects"]) * 512,
            "write_bytes": (d2["write_sects"] - d1["write_sects"]) * 512,
            "read_iops": d2["reads"] - d1["reads"],
            "write_iops": d2["writes"] - d1["writes"],
        })
    return result

_PAQUETS = {
    "dpkg": re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) (install|upgrade|remove|purge) (\S+) (\S+) (\S+)"),
    "dnf": re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})\S* SUBDEBUG (Upgrade|Installed|Erase|Upgraded|Install): (\S+)"),
}

def paquets_lignes(source, lignes):
    """Les mouvements de paquets d'un journal (dpkg ou dnf) : [instant ISO, nom du paquet, texte]."""
    rx = _PAQUETS[source]
    res = []
    for l in lignes:
        m = rx.match(l)
        if not m:
            continue
        if source == "dpkg":
            ts, act, pq, avant, apres = m.groups()
            verbe = {"install": "installé", "upgrade": "mis à jour", "remove": "retiré", "purge": "purgé"}[act]
            txt = "%s %s" % (pq.split(":")[0], verbe) + ((" (%s → %s)" % (avant, apres)) if act == "upgrade" else "")
        else:
            ts, act, pq = m.groups()
            verbe = {"Upgrade": "mis à jour", "Upgraded": "remplacé", "Installed": "installé", "Install": "installé", "Erase": "retiré"}.get(act, act)
            txt = "%s %s" % (pq, verbe)
        res.append([ts.replace(" ", "T"), pq.split(":")[0][:80], txt[:300]])
    return res

def _cpu_pct(stat1, stat2):
    try:
        cpu1 = [int(x) for x in stat1.splitlines()[0].split()[1:]]
        cpu2 = [int(x) for x in stat2.splitlines()[0].split()[1:]]
        total = sum(b - a for a, b in zip(cpu1, cpu2))
        idle = cpu2[3] - cpu1[3]
        return round((1 - idle / total) * 100, 1) if total > 0 else 0.0
    except Exception:
        return 0.0

def _charge(texte):
    try:
        parts = texte.split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except Exception:
        return 0.0, 0.0, 0.0

def instantane_serveur(stat1, stat2, loadavg, mi, now):
    """L'instantané du serveur : processeur (deux relevés de /proc/stat), charge, mémoire et swap (octets, d'après /proc/meminfo en ko). Une lecture manquante (None) vaut zéro."""
    la1, la5, la15 = _charge(loadavg)
    mem_total = mi.get("MemTotal", 0) * 1024
    mem_avail = mi.get("MemAvailable", mi.get("MemFree", 0)) * 1024
    swap_total = mi.get("SwapTotal", 0) * 1024
    swap_free = mi.get("SwapFree", 0) * 1024
    return {
        "ts": now,
        "cpu": _cpu_pct(stat1, stat2),
        "la1": la1,
        "la5": la5,
        "la15": la15,
        "mem_used": mem_total - mem_avail,
        "mem_total": mem_total,
        "swap_used": swap_total - swap_free,
        "swap_total": swap_total,
    }

def processus_agreges(stats, uptime):
    """Les douze processus les plus gourmands : stats = les textes de /proc/<pid>/stat, regroupés par nom ; uptime = le texte de /proc/uptime (ou None)."""
    hz = 100
    processes = []
    for stat_text in stats:
        try:
            name_m = re.search(r"\((.+)\)", stat_text)
            name = name_m.group(1) if name_m else "?"
            rest = re.sub(r"\(.+\)\s+", "", stat_text).split()
            utime = int(rest[11])
            stime = int(rest[12])
            rss = int(rest[21]) * 4096
            processes.append({"name": name, "cpu_ticks": utime + stime, "mem": rss})
        except Exception:
            continue
    agg = {}
    for p in processes:
        n = p["name"]
        if n not in agg:
            agg[n] = {"name": n, "cpu_ticks": 0, "mem": 0, "count": 0}
        agg[n]["cpu_ticks"] += p["cpu_ticks"]
        agg[n]["mem"] += p["mem"]
        agg[n]["count"] += 1
    uptime_s = 1.0
    try:
        uptime_s = float(uptime.split()[0])
    except Exception:
        pass
    result = []
    for v in agg.values():
        cpu_pct = round(v["cpu_ticks"] / hz / uptime_s * 100, 2) if uptime_s > 0 else 0.0
        result.append({
            "name": v["name"],
            "avg_cpu": cpu_pct,
            "max_cpu": cpu_pct,
            "mem_mb": round(v["mem"] / 1024 / 1024, 1),
            "count": v["count"],
        })
    return sorted(result, key=lambda x: x["avg_cpu"], reverse=True)[:12]

def netdev_lire(texte):
    """Les compteurs réseau par interface d'après /proc/net/dev (sans `lo`)."""
    stats = {}
    try:
        lines = texte.splitlines()[2:]
        for line in lines:
            if ":" not in line:
                continue
            iface, data = line.split(":", 1)
            iface = iface.strip()
            if iface == "lo":
                continue
            parts = data.split()
            if len(parts) < 9:
                continue
            stats[iface] = {
                "rx_bytes": int(parts[0]),
                "rx_packets": int(parts[1]),
                "tx_bytes": int(parts[8]),
                "tx_packets": int(parts[9]),
            }
    except Exception:
        pass
    return stats

def netdev_delta(s1, s2, now):
    """Le trafic par interface entre deux relevés des compteurs."""
    result = []
    for iface in s1:
        if iface not in s2:
            continue
        d1, d2 = s1[iface], s2[iface]
        result.append({
            "ts": now,
            "interface": iface,
            "rx_bytes": d2["rx_bytes"] - d1["rx_bytes"],
            "tx_bytes": d2["tx_bytes"] - d1["tx_bytes"],
            "rx_packets": d2["rx_packets"] - d1["rx_packets"],
            "tx_packets": d2["tx_packets"] - d1["tx_packets"],
        })
    return result

_MOIS_ANGLAIS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

def _date_de_ligne(texte, fmt, maintenant):
    try:
        if "%b" in fmt:
            for i, m in enumerate(_MOIS_ANGLAIS):
                if "-%s-" % m in texte:
                    texte = texte.replace("-%s-" % m, "-%02d-" % (i + 1))
                    break
            fmt = fmt.replace("%b", "%m")
        return datetime.strptime(texte, fmt).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return maintenant

def lignes_d_erreur(rx, fmt, texte, maintenant):
    """Les lignes d'erreur d'un morceau de journal : [date « AAAA-MM-JJ HH:MM:SS », niveau en majuscules, message (500 caractères)]. Le mois abrégé est traduit à la main : `%b` dépend de la langue du processus. Une date illisible vaut `maintenant`."""
    expr = re.compile(rx)
    trouvees = []
    for brute in texte.splitlines():
        m = expr.match(brute)
        if m:
            trouvees.append([_date_de_ligne(m.group(1), fmt, maintenant), m.group(2).upper(), m.group(3).strip()[:500]])
    return trouvees

def forme(op, entree):
    if op == "sessions_base":
        return sessions_base(entree["who"], entree["ss"], entree["now"])
    if op == "sessions_last":
        return sessions_last(entree["last"], entree["now"])
    if op == "ports_ss":
        return ports_ss(entree["sortie"], entree["now"])
    if op == "ports_netstat":
        return ports_netstat(entree["sortie"], entree["now"])
    if op == "certificat":
        return certificat(entree["sortie"], entree["chemin"], entree["indice"], entree["now"])
    if op == "disque_smart":
        return disque_smart(entree["d"], entree["dev"], entree["now"])
    if op == "temperature_max":
        return temperature_max(entree["valeurs"])
    if op == "heure_systeme":
        return heure_systeme(entree["td"])
    if op == "nom_du_systeme":
        return nom_du_systeme(entree["texte"])
    if op == "regles_nft":
        return nombre_regles_nft(entree["texte"])
    if op == "regles_iptables":
        return nombre_regles_iptables(entree["texte"])
    if op == "sites_nginx":
        return sites_nginx(entree["contenu"])
    if op == "sites_apache":
        return sites_apache(entree["contenu"])
    if op == "certificats_nginx":
        return certificats_nginx(entree["contenu"])
    if op == "certificats_apache":
        return certificats_apache(entree["contenu"])
    if op == "cron_lignes":
        return cron_lignes(entree["texte"], entree["utilisateur"], entree["now"])
    if op == "services_api":
        return services_api(entree["liste"], entree["now"])
    if op == "services_systemctl":
        return services_systemctl(entree["etats"], entree["now"])
    if op == "pools_php":
        return pools_php(entree["confs"], entree["ps"], entree["journaux"], entree["jour"], entree["now"])
    if op == "diskstats_lire":
        return diskstats_lire(entree["texte"])
    if op == "diskstats_delta":
        return diskstats_delta(entree["s1"], entree["s2"], entree["now"])
    if op == "paquets_lignes":
        return paquets_lignes(entree["source"], entree["lignes"])
    if op == "instantane_serveur":
        return instantane_serveur(entree["stat1"], entree["stat2"], entree["loadavg"], entree["mi"], entree["now"])
    if op == "processus_agreges":
        return processus_agreges(entree["stats"], entree["uptime"])
    if op == "netdev_lire":
        return netdev_lire(entree["texte"])
    if op == "netdev_delta":
        return netdev_delta(entree["s1"], entree["s2"], entree["now"])
    if op == "lignes_d_erreur":
        return lignes_d_erreur(entree["rx"], entree["fmt"], entree["texte"], entree["maintenant"])
    raise ValueError("opération inconnue : %s" % op)

def point_sys_formes(entree):
    """Le point d'évolution `sys_formes` (contrat 1.0) : ce que le Sensorium lit du système, mis en forme : sessions ouvertes, ports à l'écoute, certificats, disques (SMART), matériel (températures, heure, pare-feu), sites web déclarés, tâches planifiées, services, pools PHP, entrées-sorties des disques mouvements de paquets, instantané du serveur, processus, trafic réseau et lignes d'erreur des journaux. Le nexus lit les sources ; l'EC ne fait que la forme."""
    return {"valeur": forme(entree["op"], entree)}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_sys_formes(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_sys_formes.json ; corpus doré dans contrats/CN_sys_formes.corpus.json (sorties de l'ancien code, données synthétiques).
