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
# VERSION EC : EC0 (référence 0.3.0)  #56b8cd
# HÔTE CN    : CN_module.py · fp_formes @1.0
# RÔLE       : transforme ce que le Sensorium lit de FastPanel (par sa ligne de commande, son API ou les fichiers des serveurs) en comptes mail et FTP, source par source.
# MÉTHODE    : fonctions pures, une par source ; le nexus essaie les sources dans l'ordre (la plus fiable d'abord) et s'arrête à la première qui donne des comptes ; l'EC ne lit jamais de fichier.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=fp_formes contrat=@1.0 version=EC0 empreinte=56b8cd ▼▼▼
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
    raise ValueError("opération inconnue : %s" % op)

def point_fp_formes(entree):
    """Le point d'évolution `fp_formes` (contrat 1.0) : ce que le Sensorium lit de FastPanel, mis en forme : comptes mail (mogwai, API, postfix) et comptes FTP (base, fichiers des serveurs, dossiers). Le nexus lit les sources ; l'EC ne fait que la forme."""
    return {"valeur": forme(entree["op"], entree)}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_fp_formes(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_fp_formes.json ; corpus doré dans contrats/CN_fp_formes.corpus.json (sorties de l'ancien code, données synthétiques).
