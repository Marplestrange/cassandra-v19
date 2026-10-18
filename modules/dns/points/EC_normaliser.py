# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Dns : normaliser (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dns
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #1f3ac6
# HÔTE CN    : CN_module.py · normaliser @1.0
# RÔLE       : normaliser.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=normaliser contrat=@1.0 version=EC0 empreinte=1f3ac6 ▼▼▼
import ipaddress

CLOUDFLARE = ("173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20",
              "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13", "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
              "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32")

def normaliser(typ, val):
    if typ in ("A", "AAAA"):
        try:
            ip = ipaddress.ip_address(val)
            if any(ip in ipaddress.ip_network(r) for r in CLOUDFLARE):
                return "<cloudflare>"
        except ValueError:
            pass
    return val.lower() if typ in ("MX", "CNAME", "NS") else val

def point_normaliser(entree):
    """Le point d'évolution `normaliser` (contrat 1.0)."""
    return {"valeur": normaliser(entree["typ"], entree["val"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_normaliser(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de dns (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_normaliser.json ; corpus doré dans contrats/CN_normaliser.corpus.json (sorties de l'ancien code, données synthétiques).
