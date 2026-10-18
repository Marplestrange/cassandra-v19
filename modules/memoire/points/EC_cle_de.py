# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Memoire : Un slug : segments ascii en minuscules, jamais une phrase, jamais d'accent ni d'espace. La catégorie n'entre PAS dans la clé : une même réalité a une seule clé (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #000000
# HÔTE CN    : CN_module.py · cle_de @1.0
# RÔLE       : Un slug : segments ascii en minuscules, jamais une phrase, jamais d'accent ni d'espace. La catégorie n'entre PAS dans la clé : une même réalité a une seule clé.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=cle_de contrat=@1.0 version=EC0 empreinte=000000 ▼▼▼
import re
import unicodedata

CATEGORIES = ("config", "fix", "incident", "lecon", "pattern", "architecture", "security", "rule", "personne", "fact", "perception", "decision")

def cle_de(cle):
    """Un slug : segments ascii en minuscules, jamais une phrase, jamais d'accent ni d'espace. La catégorie n'entre PAS dans la clé : une même réalité a une seule clé."""
    s = unicodedata.normalize("NFKD", str(cle or "")).encode("ascii", "ignore").decode().lower().strip()
    for c in CATEGORIES:
        if s.startswith(c + "/"):
            s = s[len(c) + 1:]
            break
    s = re.sub(r"[^a-z0-9/._-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return re.sub(r"/{2,}", "/", s).strip("-/.")[:100]

def point_cle_de(entree):
    """Le point d'évolution `cle_de` (contrat 1.0)."""
    return {"valeur": cle_de(entree["cle"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_cle_de(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de memoire (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_cle_de.json ; corpus doré dans contrats/CN_cle_de.corpus.json (sorties de l'ancien code, données synthétiques).
