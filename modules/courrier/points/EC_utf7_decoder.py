# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : noms de dossiers IMAP (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #cfef73
# HÔTE CN    : CN_module.py · utf7_decoder @1.0
# RÔLE       : décode les noms de dossiers d'une boîte IMAP.
# MÉTHODE    : fonction pure : chaque séquence entre « & » et « - » est du base64 en UTF-16 ; une séquence illisible est laissée telle quelle.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=utf7_decoder contrat=@1.0 version=EC0 empreinte=cfef73 ▼▼▼
import base64
import re

def utf7_decoder(s):
    """« envoy&AOk-s » -> « envoyés »."""
    def un(m):
        if m.group(1) == "":
            return "&"
        b = m.group(1).replace(",", "/")
        b += "=" * (-len(b) % 4)
        try:
            return base64.b64decode(b).decode("utf-16-be")
        except Exception:
            return m.group(0)
    return re.sub(r"&([^-]*)-", un, s or "")

def point_utf7_decoder(entree):
    """Le point d'évolution `utf7_decoder` (contrat 1.0)."""
    return {"valeur": utf7_decoder(entree["s"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_utf7_decoder(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_utf7_decoder.json ; corpus doré dans contrats/CN_utf7_decoder.corpus.json (sorties de l'ancien code, données synthétiques).
