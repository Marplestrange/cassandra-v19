# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : nom et adresse d'un en-tête (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #b8d43f
# HÔTE CN    : CN_module.py · adresse_parts @1.0
# RÔLE       : sépare le nom affiché et l'adresse d'un expéditeur ou d'un destinataire.
# MÉTHODE    : fonction pure : l'en-tête est décodé puis analysé ; sans nom, la partie locale de l'adresse en tient lieu.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=adresse_parts contrat=@1.0 version=EC0 empreinte=b8d43f ▼▼▼
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

def decoder_entete(s):
    if s is None:
        return ""
    try:
        sortie = ""
        for txt, enc in decode_header(str(s)):
            sortie += txt.decode(enc or "utf-8", errors="replace") if isinstance(txt, bytes) else txt
        return sortie
    except Exception:
        return str(s)

def adresse_parts(brut):
    """(nom affiché, adresse en minuscules) d'un en-tête From/To."""
    try:
        nom, adr = parseaddr(decoder_entete(brut))
        adr = (adr or "").strip().lower()
        return (nom or "").strip() or (adr.split("@")[0] if adr else ""), adr
    except Exception:
        return str(brut or ""), ""

def point_adresse_parts(entree):
    """Le point d'évolution `adresse_parts` (contrat 1.0)."""
    return {"valeur": adresse_parts(entree["brut"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_adresse_parts(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_adresse_parts.json ; corpus doré dans contrats/CN_adresse_parts.corpus.json (sorties de l'ancien code, données synthétiques).
