# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Securite : machine | tailscale | reseau | public | tout — pour une adresse d'écoute de `ss` (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #3f6748
# HÔTE CN    : CN_module.py · portee @1.0
# RÔLE       : machine | tailscale | reseau | public | tout — pour une adresse d'écoute de `ss`.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=portee contrat=@1.0 version=EC0 empreinte=3f6748 ▼▼▼
import ipaddress

TS = ipaddress.ip_network("100.64.0.0/10")

TS6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")

def portee(adresse):
    """machine | tailscale | reseau | public | tout — pour une adresse d'écoute de `ss`."""
    a = str(adresse or "").strip().strip("[]").split("%")[0]
    if a in ("*", "0.0.0.0", "::", ""):
        return "tout"
    try:
        ip = ipaddress.ip_address(a)
    except ValueError:
        return "tout"
    if ip.is_loopback:
        return "machine"
    if (ip.version == 4 and ip in TS) or (ip.version == 6 and ip in TS6):
        return "tailscale"
    if ip.is_private or ip.is_link_local:
        return "reseau"
    return "public"

def point_portee(entree):
    """Le point d'évolution `portee` (contrat 1.0)."""
    return {"valeur": portee(entree["adresse"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_portee(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de securite (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_portee.json ; corpus doré dans contrats/CN_portee.corpus.json (sorties de l'ancien code, données synthétiques).
