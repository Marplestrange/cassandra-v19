# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Projets : Une date ISO, ou ''. Jamais une approximation (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : projets
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #a37d29
# HÔTE CN    : CN_module.py · date_ok @1.0
# RÔLE       : Une date ISO, ou ''. Jamais une approximation.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=date_ok contrat=@1.0 version=EC0 empreinte=a37d29 ▼▼▼
from datetime import datetime
import re

RE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def date_ok(v):
    """Une date ISO, ou ''. Jamais une approximation."""
    v = str(v or "").strip()
    if v and not RE_DATE.match(v):
        raise ValueError("date invalide « %s » (AAAA-MM-JJ attendu)" % v)
    if v:
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date impossible « %s »" % v)
    return v

def point_date_ok(entree):
    """Le point d'évolution `date_ok` (contrat 1.0)."""
    return {"valeur": date_ok(entree["v"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_date_ok(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de projets (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_date_ok.json ; corpus doré dans contrats/CN_date_ok.corpus.json (sorties de l'ancien code, données synthétiques).
