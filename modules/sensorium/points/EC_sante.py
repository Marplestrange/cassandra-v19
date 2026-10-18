# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sensorium : le score de santé (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #115217
# HÔTE CN    : CN_module.py · sante @1.0
# RÔLE       : résume la santé d'une machine en un score, en retirant des points par ressource saturée, certificat expirant, mémoire tuée par le noyau, service en échec ou disque malade.
# MÉTHODE    : fonction pure : un barème par ressource (au-delà de 75, 85 et 95 %), un plafond par famille de problème ; un score borné de 0 à 100 et classé par paliers. Le barème est la politique du dépôt.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=sante contrat=@1.0 version=EC0 empreinte=115217 ▼▼▼

def compute_health_score(metrics, ssl_certs, services, fail2ban, smart, sysctl, dns, oom_count, failed_count):
    """
    Calcul du score de santé (0–100).
    PERF: ssl_certs = liste complète → on filtre ici pour ne pénaliser que les expirés/expirants.
    Ancienne logique: -2pts par cert (même valides!) → -12pts avec 6 sites normaux = score faussé.
    """
    score = 100
    breakdown = {}

    # CPU
    cpu = metrics.get("cpu_pct", 0)
    if   cpu > 95: score -= 20; breakdown["cpu"] = -20
    elif cpu > 85: score -= 12; breakdown["cpu"] = -12
    elif cpu > 75: score -= 5;  breakdown["cpu"] = -5

    # RAM
    ram = metrics.get("ram_pct", 0)
    if   ram > 95: score -= 20; breakdown["ram"] = -20
    elif ram > 85: score -= 12; breakdown["ram"] = -12
    elif ram > 75: score -= 5;  breakdown["ram"] = -5

    # Disque
    disk = metrics.get("disk_pct", 0)
    if   disk > 95: score -= 20; breakdown["disk"] = -20
    elif disk > 85: score -= 12; breakdown["disk"] = -12
    elif disk > 75: score -= 5;  breakdown["disk"] = -5

    # SSL — UNIQUEMENT certs expirés ou expirant dans les 14 jours (pas tous les certs!)
    ssl_problems = []
    for c in (ssl_certs or []):
        days = c.get("days_left", 999)
        if isinstance(days, (int, float)):
            if days <= 0:
                ssl_problems.append(("expired", c.get("domain", "?")))
            elif days <= 14:
                ssl_problems.append(("expiring", c.get("domain", "?")))
    ssl_penalty = min(len(ssl_problems) * 5, 20)
    if ssl_penalty:
        score -= ssl_penalty
        breakdown["ssl"] = -ssl_penalty

    # OOM
    oom_penalty = min(oom_count * 5, 15)
    if oom_penalty:
        score -= oom_penalty
        breakdown["oom"] = -oom_penalty

    # Services en échec
    fail_penalty = min(failed_count * 5, 20)
    if fail_penalty:
        score -= fail_penalty
        breakdown["failed_units"] = -fail_penalty

    # SMART disques
    for d in (smart or []):
        if d.get("health", "PASSED") == "FAILED":
            score -= 10; breakdown["smart"] = -10; break
        if (d.get("reallocated_sectors", 0) or 0) > 0:
            score -= 5; breakdown.setdefault("smart_warn", -5)

    score = max(0, min(100, score))
    status = ("critical"  if score < 50 else
              "warning"   if score < 75 else
              "good"      if score < 90 else "excellent")
    return {
        "score": score,
        "status": status,
        "breakdown": breakdown,
        "alerts_count": len(ssl_problems) + oom_count + failed_count,
    }

def point_sante(entree):
    """Le point d'évolution `sante` (contrat 1.0)."""
    return {"valeur": compute_health_score(entree["metrics"], entree["ssl_certs"], entree["services"], entree["fail2ban"], entree["smart"], entree["sysctl"], entree["dns"], entree["oom_count"], entree["failed_count"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_sante(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_sante.json ; corpus doré dans contrats/CN_sante.corpus.json (sorties de l'ancien code, données synthétiques).
