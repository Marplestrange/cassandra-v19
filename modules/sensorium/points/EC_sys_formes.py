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
# VERSION EC : EC0 (référence 0.3.0)  #154d35
# HÔTE CN    : CN_module.py · sys_formes @1.0
# RÔLE       : transforme ce que le Sensorium lit du système (sorties de commandes, fichiers de configuration, JSON de smartctl) en sessions, ports, certificats, disques, état du matériel et sites web déclarés.
# MÉTHODE    : fonctions pures, une par mesure ; le nexus lit les sources et décide des replis (who puis ss puis last ; ss puis netstat) ; l'EC ne lit jamais de fichier ni de commande.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=sys_formes contrat=@1.0 version=EC0 empreinte=154d35 ▼▼▼
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

_MOIS_OPENSSL = {m: i + 1 for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))}

def _date_openssl(v):
    """« Dec 25 12:00:00 2026 GMT » (le fuseau est facultatif) -> datetime, ou None. Sans strptime : il importe _strptime à son premier appel, import que le filtre des EC refuse, et l'`except` qui l'entourait avalait ce refus (le certificat paraissait illisible)."""
    m = re.fullmatch(r"([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d\d):(\d\d):(\d\d)\s+(\d{4})(?:\s+(?:GMT|UTC))?", v)
    if not m or m.group(1) not in _MOIS_OPENSSL:
        return None
    try:
        return datetime(int(m.group(6)), _MOIS_OPENSSL[m.group(1)], int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)))
    except ValueError:
        return None

def certificat(sortie, chemin, indice, now):
    """Un certificat d'après la sortie d'openssl (date, sujet, émetteur, noms alternatifs) ; None quand elle est illisible. `now` : l'instant reçu, en ISO."""
    if not sortie:
        return None
    date_m = re.search(r"notAfter=(.+)", sortie)
    if not date_m:
        return None
    expiry = _date_openssl(date_m.group(1).strip())
    if expiry is None:
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
            "issuer": issuer, "expiry_date": expiry.date().isoformat(),
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
        # Sans strptime/strftime : l'un importe _strptime, l'autre time, que le filtre des EC refuse ; l'`except` ci-dessous avalait le refus
        # et TOUTE date valait `maintenant`.
        jetons = {"%Y": r"(?P<Y>\d{4})", "%m": r"(?P<m>\d{1,2})", "%d": r"(?P<d>\d{1,2})", "%H": r"(?P<H>\d{1,2})", "%M": r"(?P<M>\d{1,2})", "%S": r"(?P<S>\d{1,2})"}
        rx = re.escape(fmt)
        for k, v in jetons.items():
            rx = rx.replace(k, v)
        g = re.fullmatch(rx, texte).groupdict()
        return datetime(int(g["Y"]), int(g["m"]), int(g["d"]), int(g["H"]), int(g["M"]), int(g["S"])).isoformat(" ")
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

def verdict_pare_feu(lignes):
    """Le verdict d'un `iptables -S` : chaque règle atteinte depuis INPUT, sous-chaînes dépliées. Un « tout refuser » sans condition, au bout d'un chemin de sauts eux-mêmes sans condition, filtre autant qu'une politique DROP."""
    pol, ch = {}, {}
    for l in lignes:
        j = l.split()
        if len(j) >= 3 and j[0] == "-P":
            pol[j[1]] = j[2]
        elif len(j) >= 2 and j[0] == "-N":
            ch.setdefault(j[1], [])
        elif len(j) >= 2 and j[0] == "-A":
            ch.setdefault(j[1], []).append(j[2:])
    etat = {"regles": 0, "refus": 0, "refuse_tout": False, "ouverts": []}

    def suivre(nom, prof, vu, sans_condition):
        for j in ch.get(nom, []):
            cible = j[j.index("-j") + 1] if "-j" in j and j.index("-j") + 1 < len(j) else ""
            reste = list(j)
            for opt in ("--reject-with", "--log-prefix", "--log-level"):
                if opt in reste and reste.index(opt) + 1 < len(reste):
                    k = reste.index(opt)
                    del reste[k:k + 2]
            pour_tout = [x for x in reste if x not in ("-j", cible)] == []
            if cible == "ACCEPT" and sans_condition:
                pts = []
                for opt in ("--dport", "--dports"):
                    if opt in reste and reste.index(opt) + 1 < len(reste):
                        for mo in reste[reste.index(opt) + 1].split(","):
                            a, _, b = mo.partition(":")
                            if a.isdigit():
                                pts.append((int(a), int(b) if b.isdigit() else int(a)))
                autres = [x for x in reste if x.startswith("-") and x not in ("-p", "-m", "--dport", "--dports", "-j")]
                if pts and not autres:
                    etat["ouverts"].extend(pts)
            if cible in ch and cible not in vu and prof < 6:
                suivre(cible, prof + 1, vu | {cible}, sans_condition and pour_tout)
                continue
            etat["regles"] += 1
            if cible in ("DROP", "REJECT"):
                etat["refus"] += 1
                if pour_tout and sans_condition:
                    etat["refuse_tout"] = True
            if pour_tout and cible in ("RETURN", "ACCEPT", "DROP", "REJECT"):
                return

    suivre("INPUT", 0, {"INPUT"}, True)
    p = pol.get("INPUT", "?")
    return {"politique": p, "filtre": p in ("DROP", "REJECT") or etat["refuse_tout"],
            "regles": etat["regles"], "refus": etat["refus"], "ouverts": etat["ouverts"]}

def ecoute_ss(texte):
    """Les ports à l'écoute d'après `ss -ltnpH` : [[port, processus, [portées triées]]], dans l'ordre de première apparition."""
    ecoute = {}
    for l in texte.splitlines():
        p = l.split()
        if len(p) < 4:
            continue
        local = p[3]
        m = re.match(r"^\[?(.*?)\]?:(\d+)$", local)
        if not m:
            continue
        adr, port = m.group(1).split("%")[0], int(m.group(2))
        pm = re.search(r'users:\(\("([^"]+)"', l)
        proc = (pm.group(1) if pm else "?").split(" (")[0]
        if adr in ("127.0.0.1", "::1") or adr.startswith("127."):
            portee = "machine"
        elif adr.startswith("100.") or adr.startswith("fd7a:115c"):
            portee = "tailscale"
        elif adr.startswith(("192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.2", "172.30.", "172.31.", "fe80")):
            portee = "réseau local"
        elif adr in ("0.0.0.0", "*", "::"):
            portee = "toutes les interfaces"
        else:
            portee = "adresse publique %s" % adr
        e = ecoute.setdefault(port, {"proc": proc, "portees": set()})
        e["portees"].add(portee)
    return [[port, e["proc"], sorted(e["portees"])] for port, e in ecoute.items()]

def ports_a_sonder(ecoute):
    """Les ports qu'il faut tenter de joindre depuis l'extérieur : ceux qui écoutent ailleurs que sur la machine ou Tailscale."""
    return [port for port, proc, portees in ecoute if not set(portees) <= {"machine", "tailscale"}]

_PORTS_SENSIBLES_EC = {22: "SSH", 23: "Telnet", 3306: "MySQL", 5432: "PostgreSQL", 6379: "Redis", 27017: "MongoDB",
                       2375: "Docker (API nue)", 2376: "Docker", 9200: "Elasticsearch", 11211: "Memcached",
                       5900: "VNC", 3389: "Bureau à distance", 8888: "panneau FastPanel", 9000: "Cassandra"}

def exposition(ecoute, publics, pf4, pf6, ip_pub, now):
    """L'exposition de chaque port : ecoute = [[port, processus, portées]], publics = [[port, joignable de l'extérieur (True/False/None)]], pf4 et pf6 = les verdicts du pare-feu (ou None)."""
    pubs = {port: ouvert for port, ouvert in publics}

    def _ouvert(pf, port):
        return (not pf) or (not pf["filtre"]) or any(a <= port <= b for a, b in pf["ouverts"])

    out = []
    for port, proc, portees in sorted(ecoute, key=lambda x: x[0]):
        pub = pubs.get(port)
        portee = ", ".join(sorted(portees))
        if pub:
            niveau = "PUBLIC (joignable sur %s, via la box)" % ip_pub
        elif "toutes les interfaces" in portees or any(x.startswith("adresse publique") for x in portees):
            if _ouvert(pf4, port):
                niveau = "réseau (%s)" % portee
            else:
                niveau = "réseau : refusé par le pare-feu, sauf le parc et Tailscale"
            if "toutes les interfaces" in portees and pf6:
                niveau += " · IPv6 %s" % ("ouvert" if _ouvert(pf6, port) else "refusé")
        else:
            niveau = portee
        sensible = _PORTS_SENSIBLES_EC.get(port)
        out.append({"port": port, "processus": proc, "portee": portee, "public": 1 if pub else 0,
                    "valeur": "%s · %s%s" % (proc, niveau, (" · %s" % sensible) if sensible else ""),
                    "sensible": 1 if sensible else 0, "ip_publique": ip_pub, "last_check": now})
    return out

def racines_de_domaines(noms):
    """Les domaines de deuxième niveau d'une liste de noms, triés, sans doublon."""
    return sorted({".".join(str(n).strip(".").split(".")[-2:]) for n in noms if n and "." in str(n)})

def courriel_domaine(txt_domaine, txt_dmarc, dkim, ip):
    """Ce que disent SPF, DKIM et DMARC d'un domaine : [texte, gravité]. txt_* = les enregistrements TXT lus ; dkim = [[sélecteur, enregistrements]] ; ip = l'adresse publique de la machine."""
    spf = next((t for t in txt_domaine if t.lower().startswith("v=spf1")), "")
    dmarc = next((t for t in txt_dmarc if t.lower().startswith("v=dmarc1")), "")
    trouves = [s for s, txts in dkim if any("p=" in t for t in txts)]
    pol = (re.search(r"\bp=(\w+)", dmarc) or [None, ""])[1].lower()
    parts = []
    sev = "info"
    if spf:
        fin = (re.search(r"([~\-?+])all\b", spf) or [None, ""])[1]
        parts.append("SPF %s" % {"-": "strict (-all)", "~": "souple (~all)", "?": "neutre (?all)", "+": "OUVERT À TOUS (+all)"}.get(fin, "sans fin"))
        if fin == "+":
            sev = "warning"
        if ip and ("ip4:" + ip) not in spf and "include:" not in spf and " a " not in (spf + " ") and " mx " not in (spf + " "):
            parts.append("cette machine (%s) n'y est pas" % ip)
    else:
        parts.append("AUCUN SPF : n'importe qui peut écrire en son nom")
        sev = "warning"
    parts.append(("DKIM : %s" % ", ".join(trouves)) if trouves else "DKIM : aucune signature trouvée")
    if dmarc:
        parts.append("DMARC %s" % {"none": "en surveillance seulement (p=none)", "quarantine": "met en quarantaine",
                                    "reject": "rejette l'usurpation"}.get(pol, pol or "?"))
    else:
        parts.append("AUCUN DMARC")
        sev = "warning"
    return [" · ".join(parts), sev]

def controles_site(dom, tls, ips, now):
    """Les contrôles d'un site : son certificat vérifié (tls = None quand le site n'est pas en TLS, sinon [vérifié, détail]) et sa résolution DNS publique."""
    res = []
    if tls is not None:
        ok, v = tls
        res.append({"nom": "tls.%s" % dom, "ok": 1 if ok else 0, "valeur": v, "last_check": now})
    res.append({"nom": "dns.%s" % dom, "ok": 1 if ips else 0, "valeur": ("→ %s" % ", ".join(ips[:3])) if ips else "ne résout pas", "last_check": now})
    return res

def controles_coherence(out):
    """Cohérence DNS : un domaine qui pointe ailleurs que la majorité des autres est signalé."""
    out = [dict(x) for x in out]
    dns = [x for x in out if x["nom"].startswith("dns.") and x["ok"]]
    compte = {}
    for x in dns:
        compte[x["valeur"]] = compte.get(x["valeur"], 0) + 1
    if len(dns) >= 3:
        majo = max(compte, key=compte.get)
        for x in dns:
            if x["valeur"] != majo and compte[x["valeur"]] == 1:
                x["valeur"] += " (les autres sites : %s)" % majo[2:]
    return out

def controle_banniere(nom, banniere, attendu, now):
    """Le contrôle d'un service de courriel : sa bannière commence-t-elle comme attendu ?"""
    b = banniere
    return {"nom": "courriel.%s" % nom, "ok": 1 if b.startswith(attendu) else 0,
            "valeur": ("répond : %s" % b) if b.startswith(attendu) else ("ne répond pas comme attendu : %s" % (b or "rien")),
            "last_check": now}

def page_de_connexion(corps):
    """La page lue est-elle la page de connexion de Cassandra ?"""
    return "login-username" in corps or 'id="login' in corps

def controle_connexion(ok, url, now):
    """Le contrôle de l'interface de Cassandra : sa page de connexion."""
    return {"nom": "cassandra.connexion", "ok": 1 if ok else 0,
            "valeur": ("la page de connexion s'affiche (%s)" % url) if ok else ("page de connexion introuvable sur %s" % url),
            "last_check": now}

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
    if op == "verdict_pare_feu":
        return verdict_pare_feu(entree["lignes"])
    if op == "ecoute_ss":
        return ecoute_ss(entree["texte"])
    if op == "ports_a_sonder":
        return ports_a_sonder(entree["ecoute"])
    if op == "exposition":
        return exposition(entree["ecoute"], entree["publics"], entree["pf4"], entree["pf6"], entree["ip_pub"], entree["now"])
    if op == "racines_de_domaines":
        return racines_de_domaines(entree["noms"])
    if op == "courriel_domaine":
        return courriel_domaine(entree["txt_domaine"], entree["txt_dmarc"], entree["dkim"], entree["ip"])
    if op == "controles_site":
        return controles_site(entree["dom"], entree["tls"], entree["ips"], entree["now"])
    if op == "controles_coherence":
        return controles_coherence(entree["out"])
    if op == "controle_banniere":
        return controle_banniere(entree["service"], entree["banniere"], entree["attendu"], entree["now"])
    if op == "page_de_connexion":
        return page_de_connexion(entree["corps"])
    if op == "controle_connexion":
        return controle_connexion(entree["ok"], entree["url"], entree["now"])
    raise ValueError("opération inconnue : %s" % op)

def point_sys_formes(entree):
    """Le point d'évolution `sys_formes` (contrat 1.0) : ce que le Sensorium lit du système, mis en forme : sessions ouvertes, ports à l'écoute, certificats, disques (SMART), matériel (températures, heure, pare-feu), sites web déclarés, tâches planifiées, services, pools PHP, entrées-sorties des disques mouvements de paquets, instantané du serveur, processus, trafic réseau lignes d'erreur des journaux, verdict du pare-feu, exposition des ports, courriel des domaines et contrôles. Le nexus lit les sources ; l'EC ne fait que la forme."""
    return {"valeur": forme(entree["op"], entree)}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_sys_formes(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_sys_formes.json ; corpus doré dans contrats/CN_sys_formes.corpus.json (sorties de l'ancien code, données synthétiques).
