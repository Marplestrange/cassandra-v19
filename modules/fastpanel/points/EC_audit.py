# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Fastpanel : l'audit des sites du panneau (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : fastpanel
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #d91c41
# HÔTE CN    : CN_module.py · audit @1.0
# RÔLE       : range les sites du panneau par ce qui demande de l'attention : certificats échus ou proches, versions de PHP en fin de support ou bientôt.
# MÉTHODE    : fonction pure sur les sites déjà lus : un tri par état de certificat ; la fin de support d'une version de PHP vient d'une table (la politique du dépôt) comparée à l'instant reçu.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=audit contrat=@1.0 version=EC0 empreinte=d91c41 ▼▼▼
import re
from datetime import datetime, timedelta, timezone

FIN_SUPPORT_PHP = {
    "5.6": "2018-12-31", "7.0": "2019-01-10", "7.1": "2019-12-01", "7.2": "2020-11-30", "7.3": "2021-12-06", "7.4": "2022-11-28",
    "8.0": "2023-11-26", "8.1": "2025-12-31", "8.2": "2026-12-31", "8.3": "2027-12-31", "8.4": "2028-12-31",
}

def audit_certificats(sites):
    return {"echus": [s["domaine"] for s in sites if s["ssl"]["etat"] == "echu"],
            "proches": [{"domaine": s["domaine"], "jours": s["ssl"]["jours"], "echeance": s["ssl"]["echeance"]} for s in sorted((s for s in sites if s["ssl"]["etat"] == "proche"), key=lambda x: x["ssl"]["jours"])],
            "sans": [s["domaine"] for s in sites if s["ssl"]["etat"] == "aucun"],
            "inconnus": [s["domaine"] for s in sites if s["ssl"]["etat"] == "inconnu"],
            "actifs": sum(1 for s in sites if s["ssl"]["etat"] in ("actif", "proche")), "total": len(sites)}

def audit_php(sites, maintenant=None):
    auj = maintenant
    aujourdhui, bientot = auj.strftime("%Y-%m-%d"), (auj + timedelta(days=120)).strftime("%Y-%m-%d")
    finis, proches, inconnus = [], [], []
    for s in sites:
        m = re.search(r"(\d+\.\d+)", s.get("php") or "")
        if not m:
            if (s.get("gestionnaire") or "").lower() in ("php_fpm", "mpm_itk", "fastuser", "php", "apache"):
                inconnus.append({"domaine": s["domaine"], "gestionnaire": s["gestionnaire"]})
            continue
        fin = FIN_SUPPORT_PHP.get(m.group(1))
        if not fin:
            continue
        if fin < aujourdhui:
            finis.append({"domaine": s["domaine"], "php": m.group(1), "fin": fin})
        elif fin < bientot:
            proches.append({"domaine": s["domaine"], "php": m.group(1), "fin": fin})
    return {"fin_de_support": finis, "bientot": proches, "version_non_lue": inconnus}

def point_audit(entree):
    """Le point d'évolution `audit` (contrat 1.0) : l'audit des certificats ou du PHP des sites du panneau ; l'instant est une entrée (UTC, « AAAA-MM-JJ HH:MM:SS »)."""
    op, sites = entree["op"], entree["sites"]
    if op == "certificats":
        return {"valeur": audit_certificats(sites)}
    if op == "php":
        return {"valeur": audit_php(sites, datetime.strptime(entree["maintenant"][:19], "%Y-%m-%d %H:%M:%S"))}
    raise ValueError("opération inconnue : %s" % op)

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_audit(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de fastpanel (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_audit.json ; corpus doré dans contrats/CN_audit.corpus.json (sorties de l'ancien code, données synthétiques).
