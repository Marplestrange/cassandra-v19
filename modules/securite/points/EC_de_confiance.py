# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Securite : de_confiance (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #25d4c7
# HÔTE CN    : CN_module.py · de_confiance @1.0
# RÔLE       : de_confiance.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=de_confiance contrat=@1.0 version=EC0 empreinte=25d4c7 ▼▼▼
import ipaddress

RESEAUX_DE_CONFIANCE = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "100.64.0.0/10", "::1/128", "fc00::/7", "fe80::/10", "fd7a:115c:a1e0::/48")

def de_confiance(adresse, extra=()):
    try:
        c = ipaddress.ip_network(str(adresse).strip(), strict=False)
    except ValueError:
        return True
    for n in list(RESEAUX_DE_CONFIANCE) + [x for x in extra if x]:
        try:
            m = ipaddress.ip_network(str(n).strip(), strict=False)
        except ValueError:
            continue
        if m.version == c.version and (c.subnet_of(m) or m.subnet_of(c)):
            return True
    return False

def point_de_confiance(entree):
    """Le point d'évolution `de_confiance` (contrat 1.0)."""
    return {"valeur": de_confiance(entree["adresse"], entree["extra"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_de_confiance(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de securite (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_de_confiance.json ; corpus doré dans contrats/CN_de_confiance.corpus.json (sorties de l'ancien code, données synthétiques).
