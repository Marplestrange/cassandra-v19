# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : Date normalisée et TRIABLE : les en-têtes Date arrivent dans une dizaine de formats et de fuseaux, trier la chaîne brute mélangerait janvier et juillet (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #4685e4
# HÔTE CN    : CN_module.py · date_iso @1.0
# RÔLE       : Date normalisée et TRIABLE : les en-têtes Date arrivent dans une dizaine de formats et de fuseaux, trier la chaîne brute mélangerait janvier et juillet.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=date_iso contrat=@1.0 version=EC0 empreinte=4685e4 ▼▼▼
from email.utils import parseaddr, parsedate_to_datetime
from datetime import timezone

def date_iso(brut):
    """Date normalisée et TRIABLE : les en-têtes Date arrivent dans une dizaine de formats et de fuseaux, trier la chaîne brute mélangerait janvier et juillet."""
    if not brut:
        return ""
    try:
        d = parsedate_to_datetime(brut)
        if d is None:
            return ""
        if d.tzinfo is not None:
            d = d.astimezone(timezone.utc).replace(tzinfo=None)
        return d.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""

def point_date_iso(entree):
    """Le point d'évolution `date_iso` (contrat 1.0)."""
    return {"valeur": date_iso(entree["brut"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_date_iso(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_date_iso.json ; corpus doré dans contrats/CN_date_iso.corpus.json (sorties de l'ancien code, données synthétiques).
