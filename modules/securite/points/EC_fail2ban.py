# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Securite : fail2ban (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #571097
# HÔTE CN    : CN_module.py · fail2ban @1.0
# RÔLE       : fail2ban.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=fail2ban contrat=@1.0 version=EC0 empreinte=571097 ▼▼▼
import re

def fail2ban(m):
    f = m.get("fail2ban") or {}
    if not f.get("actif"):
        return {"actif": False, "jails": []}
    jails = []
    for j, s in (f.get("jails") or {}).items():
        def n(lib):
            x = re.search(lib + r":\s*(\d+)", s or "")
            return int(x.group(1)) if x else 0
        ips = re.search(r"Banned IP list:\s*(.*)", s or "")
        jails.append({"jail": j, "echecs": n("Total failed"), "bannies": n("Currently banned"), "total": n("Total banned"), "ips": [x for x in (ips.group(1).split() if ips else []) if x][:50]})
    return {"actif": True, "jails": jails}

def point_fail2ban(entree):
    """Le point d'évolution `fail2ban` (contrat 1.0)."""
    return {"valeur": fail2ban(entree["m"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_fail2ban(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de securite (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_fail2ban.json ; corpus doré dans contrats/CN_fail2ban.corpus.json (sorties de l'ancien code, données synthétiques).
