# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sensorium : les comptes de FastPanel (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #ab16c5
# HÔTE CN    : CN_module.py · fp_formes @1.0
# RÔLE       : transforme ce que le Sensorium lit de FastPanel (par sa ligne de commande, son API ou les fichiers des serveurs) en comptes mail et FTP, source par source.
# MÉTHODE    : fonctions pures, une par source ; le nexus essaie les sources dans l'ordre (la plus fiable d'abord) et s'arrête à la première qui donne des comptes ; l'EC ne lit jamais de fichier.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=fp_formes contrat=@1.0 version=EC0 empreinte=ab16c5 ▼▼▼
import re

def mail_mogwai(rows, now):
    """Les boîtes mail d'après la table de mogwai (une ligne par boîte)."""
    accounts, seen = [], set()
    for row in rows:
        addr = row.get("address", "")
        if not addr or "@" not in addr or addr in seen:
            continue
        seen.add(addr)
        parts = addr.split("@")
        size_mb = 0
        quota_mb = 0
        try:
            size_mb = round(int(row.get("size", 0) or 0) / 1024 / 1024, 1)
            quota_mb = round(int(row.get("quota", 0) or 0) / 1024 / 1024, 1)
        except Exception:
            pass
        accounts.append({
            "email": addr,
            "domain": parts[1],
            "login": parts[0],
            "quota_mb": quota_mb,
            "used_mb": size_mb,
            "status": "active" if row.get("enabled", "true") == "true" else "suspended",
            "last_check": now,
        })
    return accounts

def mail_api(boxes, now):
    """Les boîtes mail d'après l'API (point d'entrée non officiel)."""
    accounts, seen = [], set()
    for box in boxes:
        addr = box.get("address", box.get("email", ""))
        if not addr or "@" not in addr or addr in seen:
            continue
        seen.add(addr)
        parts = addr.split("@")
        accounts.append({
            "email": addr,
            "domain": parts[1] if len(parts) > 1 else "",
            "login": parts[0],
            "quota_mb": box.get("quota", 0) or 0,
            "used_mb": box.get("size", 0) or 0,
            "status": "active" if box.get("enabled", True) else "suspended",
            "last_check": now,
        })
    return accounts

def mail_postfix(fichiers, now):
    """Les boîtes mail d'après les fichiers de postfix (virtual, vmailbox) : [[chemin, texte]]."""
    accounts, seen = [], set()
    for chemin, texte in fichiers:
        for line in texte.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "@" in line:
                email = line.split()[0]
                if "@" in email and email not in seen:
                    seen.add(email)
                    p = email.split("@")
                    accounts.append({
                        "email": email, "domain": p[1], "login": p[0],
                        "quota_mb": 0, "used_mb": 0, "status": "active",
                        "last_check": now,
                    })
    return accounts

def ftp_base(liste, now):
    """Les comptes FTP d'après la base du panneau : un par identifiant."""
    accounts, seen = [], set()
    for a in liste:
        if a["login"] and a["login"] not in seen:
            seen.add(a["login"])
            a["last_check"] = now
            accounts.append(a)
    return accounts

def _proprietaire(home_dir):
    owner = ""
    m = re.search(r"/var/www/([^/]+)/", home_dir)
    if m:
        owner = m.group(1)
    return owner

def ftp_fichiers(proftpd, pure, vsftpd, now):
    """Les comptes FTP d'après les fichiers des serveurs FTP, dans l'ordre proftpd, pure-ftpd, vsftpd ; chaque texte vaut None quand le fichier n'existe pas."""
    accounts, seen = [], set()
    if proftpd is not None:
        for line in proftpd.splitlines():
            parts = line.split(":")
            if len(parts) >= 6 and parts[0] not in seen:
                login = parts[0]
                home_dir = parts[5] if len(parts) > 5 else ""
                seen.add(login)
                accounts.append({"login": login, "home_dir": home_dir, "status": "active", "owner": _proprietaire(home_dir), "last_check": now})
    if pure is not None:
        for line in pure.splitlines():
            parts = line.split(":")
            if len(parts) >= 8 and parts[0] not in seen:
                login = parts[0]
                home_dir = parts[5] if len(parts) > 5 else ""
                seen.add(login)
                accounts.append({"login": login, "home_dir": home_dir, "status": "active", "owner": _proprietaire(home_dir), "last_check": now})
    if vsftpd is not None:
        for login in vsftpd.splitlines():
            login = login.strip()
            if login and not login.startswith("#") and login not in seen:
                seen.add(login)
                accounts.append({"login": login, "home_dir": "/var/www/%s/data" % login, "status": "active", "owner": login, "last_check": now})
    return accounts

def ftp_dossiers(utilisateurs, now):
    """Les comptes FTP d'après les dossiers data/ftp des utilisateurs : [[utilisateur, [[nom du sous-dossier, chemin]]]]."""
    accounts, seen = [], set()
    for user, subs in utilisateurs:
        for nom, chemin in subs:
            if nom not in seen:
                seen.add(nom)
                accounts.append({"login": nom, "home_dir": chemin, "status": "active", "owner": user, "last_check": now})
    return accounts

def users_base(liste, now):
    """Les comptes du panneau d'après sa base : un par identifiant."""
    users, seen = [], set()
    for u in liste:
        if u["username"] and u["username"] not in seen:
            seen.add(u["username"])
            u["last_check"] = now
            users.append(u)
    return users

def users_api(api_users, now):
    """Les comptes du panneau d'après son API (GET /api/users)."""
    users, seen = [], set()
    for u in api_users:
        uname = u.get("username", u.get("login", ""))
        if not uname or uname in seen:
            continue
        seen.add(uname)
        quota_raw = u.get("quota")
        used_raw = u.get("disk_used", u.get("disk_usage", 0)) or 0
        quota_gb = round(int(quota_raw) / 1024**3, 2) if quota_raw else 0
        used_gb = round(int(used_raw) / 1024**3, 2) if used_raw else 0
        enabled = u.get("enabled", True)
        status = "active" if enabled else "suspended"
        users.append({
            "username": uname,
            "email": u.get("restore_email", u.get("email", "")),
            "status": status,
            "disk_quota_gb": quota_gb,
            "disk_used_gb": used_gb,
            "created_at": u.get("created_at", now),
            "last_login": u.get("last_login", ""),
            "roles": ",".join(u.get("roles", [])),
            "last_check": now,
        })
    return users

def users_dossiers(dossiers, now):
    """Les comptes devinés des dossiers de /var/www : [[nom, sortie de du -sb]]."""
    users = []
    for nom, out in dossiers:
        try:
            used_gb = round(int(out.split()[0]) / 1024**3, 2) if out else 0
        except Exception:
            used_gb = 0
        users.append({
            "username": nom, "email": "", "status": "active",
            "disk_quota_gb": 0, "disk_used_gb": used_gb,
            "created_at": now, "last_login": "", "roles": "ROLE_USER",
            "last_check": now,
        })
    return users

def dbs_base(liste, now):
    """Les bases de données d'après la base du panneau : une par nom."""
    dbs, seen = [], set()
    for d in liste:
        if d["name"] and d["name"] not in seen:
            seen.add(d["name"])
            d["last_check"] = now
            dbs.append(d)
    return dbs

def dbs_api(api_dbs, now):
    """Les bases de données d'après l'API du panneau."""
    dbs, seen = [], set()
    for db in api_dbs:
        name = db.get("name", "")
        if not name or name in seen:
            continue
        seen.add(name)
        dbs.append({
            "name": name,
            "db_user": db.get("db_user", db.get("user", "")),
            "size_mb": float(db.get("size_mb", db.get("size", 0)) or 0),
            "db_type": db.get("type", "mysql"),
            "owner": (db.get("owner", {}) or {}).get("username", ""),
            "last_check": now,
        })
    return dbs

def dbs_mysql(texte, now):
    """Les bases de données d'après information_schema de MySQL (nom et taille, séparés par une tabulation)."""
    dbs, seen = [], set()
    skip = {"information_schema", "performance_schema", "mysql", "sys"}
    for line in texte.splitlines():
        parts = line.split("	")
        if len(parts) >= 2 and parts[0] not in skip and parts[0] not in seen:
            try:
                seen.add(parts[0])
                dbs.append({
                    "name": parts[0], "db_user": "", "size_mb": float(parts[1] or 0),
                    "db_type": "mysql", "owner": "", "last_check": now,
                })
            except Exception:
                pass
    return dbs

def forme(op, entree):
    if op == "mail_mogwai":
        return mail_mogwai(entree["rows"], entree["now"])
    if op == "mail_api":
        return mail_api(entree["boxes"], entree["now"])
    if op == "mail_postfix":
        return mail_postfix(entree["fichiers"], entree["now"])
    if op == "ftp_base":
        return ftp_base(entree["liste"], entree["now"])
    if op == "ftp_fichiers":
        return ftp_fichiers(entree["proftpd"], entree["pure"], entree["vsftpd"], entree["now"])
    if op == "ftp_dossiers":
        return ftp_dossiers(entree["utilisateurs"], entree["now"])
    if op == "users_base":
        return users_base(entree["liste"], entree["now"])
    if op == "users_api":
        return users_api(entree["api_users"], entree["now"])
    if op == "users_dossiers":
        return users_dossiers(entree["dossiers"], entree["now"])
    if op == "dbs_base":
        return dbs_base(entree["liste"], entree["now"])
    if op == "dbs_api":
        return dbs_api(entree["api_dbs"], entree["now"])
    if op == "dbs_mysql":
        return dbs_mysql(entree["texte"], entree["now"])
    raise ValueError("opération inconnue : %s" % op)

def point_fp_formes(entree):
    """Le point d'évolution `fp_formes` (contrat 1.0) : ce que le Sensorium lit de FastPanel, mis en forme : comptes mail (mogwai, API, postfix), comptes FTP (base, fichiers des serveurs, dossiers), comptes du panneau et bases de données (base, API, dossiers, MySQL). Le nexus lit les sources ; l'EC ne fait que la forme."""
    return {"valeur": forme(entree["op"], entree)}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_fp_formes(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_fp_formes.json ; corpus doré dans contrats/CN_fp_formes.corpus.json (sorties de l'ancien code, données synthétiques).
