# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Journal : Empreinte d'une erreur, débarrassée de ce qui change à chaque occurrence (ports, adresses, dates) (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : journal
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #fdb46b
# HÔTE CN    : CN_module.py · signature @1.0
# RÔLE       : Empreinte d'une erreur, débarrassée de ce qui change à chaque occurrence (ports, adresses, dates).
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=signature contrat=@1.0 version=EC0 empreinte=fdb46b ▼▼▼
import hashlib
import re

def _signature(texte: str) -> str:
    """Empreinte d'une erreur, débarrassée de ce qui change à chaque occurrence (ports, adresses, dates)."""
    t = (texte or "").lower()
    t = re.sub(r"\d{4}-\d{2}-\d{2}[t ]\d{2}:\d{2}(:\d{2})?", " ", t)
    t = re.sub(r"0x[0-9a-f]+|\b\d+\b", "N", t)
    t = re.sub(r"/[\w./\-]+", "/PATH", t)
    t = re.sub(r"\s+", " ", t).strip()
    return hashlib.sha1(t[:400].encode("utf-8")).hexdigest()[:16]

def point_signature(entree):
    """Le point d'évolution `signature` (contrat 1.0)."""
    return {"valeur": _signature(entree["texte"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_signature(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de journal (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_signature.json ; corpus doré dans contrats/CN_signature.corpus.json (sorties de l'ancien code, données synthétiques).
