# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : décodage d'un en-tête (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #1be9b9
# HÔTE CN    : CN_module.py · decoder_entete @1.0
# RÔLE       : rend lisible un en-tête de message : sujet, nom d'expéditeur, accents encodés.
# MÉTHODE    : fonction pure : chaque mot encodé est décodé dans son jeu de caractères ; un en-tête illisible est rendu tel quel.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=decoder_entete contrat=@1.0 version=EC0 empreinte=1be9b9 ▼▼▼
from email.header import decode_header

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

def point_decoder_entete(entree):
    """Le point d'évolution `decoder_entete` (contrat 1.0)."""
    return {"valeur": decoder_entete(entree["s"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_decoder_entete(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_decoder_entete.json ; corpus doré dans contrats/CN_decoder_entete.corpus.json (sorties de l'ancien code, données synthétiques).
