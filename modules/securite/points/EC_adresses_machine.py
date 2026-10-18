# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Securite : Les adresses publiques que porte la machine elle-même ; sans v4 publique, elle est derrière une box (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : securite
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #0470ee
# HÔTE CN    : CN_module.py · adresses_machine @1.0
# RÔLE       : Les adresses publiques que porte la machine elle-même ; sans v4 publique, elle est derrière une box.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=adresses_machine contrat=@1.0 version=EC0 empreinte=0470ee ▼▼▼
import ipaddress
import re

TS = ipaddress.ip_network("100.64.0.0/10")

TS6 = ipaddress.ip_network("fd7a:115c:a1e0::/48")

def adresses_machine(texte):
    """Les adresses publiques que porte la machine elle-même ; sans v4 publique, elle est derrière une box."""
    v4, v6, locaux, ips = [], [], [], []
    for ligne in (texte or "").splitlines():
        m = re.search(r"\binet6?\s+([0-9a-fA-F:.]+)/", ligne)
        if not m:
            continue
        c = re.search(r"\binet\s+([0-9.]+/\d+)", ligne)
        if c:
            try:
                n = ipaddress.ip_network(c.group(1), strict=False)
                if n.is_private and not n.is_loopback and n.network_address not in TS and " docker" not in ligne and " br-" not in ligne:
                    if str(n) not in locaux:
                        locaux.append(str(n))
                    ips.append(c.group(1).split("/")[0])
            except (ValueError, TypeError):
                pass
        try:
            ip = ipaddress.ip_address(m.group(1))
        except ValueError:
            continue
        if ip.is_global and not (ip.version == 4 and ip in TS) and not (ip.version == 6 and ip in TS6):
            (v4 if ip.version == 4 else v6).append(str(ip))
    return {"public_v4": v4, "public_v6": v6, "reseaux_locaux": locaux, "ips_locales": ips}

def point_adresses_machine(entree):
    """Le point d'évolution `adresses_machine` (contrat 1.0)."""
    return {"valeur": adresses_machine(entree["texte"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_adresses_machine(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de securite (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_adresses_machine.json ; corpus doré dans contrats/CN_adresses_machine.corpus.json (sorties de l'ancien code, données synthétiques).
