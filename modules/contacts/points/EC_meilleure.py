# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : quelle fiche garder (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.1)  #86e1ed
# HÔTE CN    : CN_module.py · meilleure @1.0
# RÔLE       : propose, entre deux fiches qui se ressemblent, celle à garder : la plus renseignée, à égalité la plus ancienne.
# MÉTHODE    : fonction pure : un score de remplissage (champs non vides, adresses, photo, favori) ; à égalité la création la plus ancienne ; à égalité totale le plus petit identifiant.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=meilleure contrat=@1.0 version=EC0 empreinte=86e1ed ▼▼▼

def remplissage(c):
    """Combien cette fiche porte d'informations : sert à choisir laquelle garder."""
    n = sum(1 for k in ("display_name", "company", "job_title", "phone", "mobile", "address", "website", "notes", "anniversaire", "vault_ref") if str(c.get(k) or "").strip())
    n += len(c.get("emails") or [])
    if c.get("photo"):
        n += 2
    if c.get("favorite"):
        n += 3
    return n

def meilleure(a, b):
    """Laquelle mérite d'absorber l'autre : la plus renseignée, et à égalité la plus ancienne (la plus citée ailleurs). Une PROPOSITION seulement."""
    ra, rb = remplissage(a), remplissage(b)
    if ra != rb:
        return a["id"] if ra > rb else b["id"]
    if a["created_at"] != b["created_at"]:
        return a["id"] if a["created_at"] < b["created_at"] else b["id"]
    return min(a["id"], b["id"])

def point_meilleure(entree):
    """Le point d'évolution `meilleure` (contrat 1.0)."""
    return {"valeur": meilleure(entree["a"], entree["b"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_meilleure(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_meilleure.json ; corpus doré dans contrats/CN_meilleure.corpus.json (sorties de l'ancien code, données synthétiques).
