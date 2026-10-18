# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : Combien cette fiche porte d'informations : sert à choisir laquelle garder (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #725692
# HÔTE CN    : CN_module.py · remplissage @1.0
# RÔLE       : Combien cette fiche porte d'informations : sert à choisir laquelle garder.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=remplissage contrat=@1.0 version=EC0 empreinte=725692 ▼▼▼

def remplissage(c):
    """Combien cette fiche porte d'informations : sert à choisir laquelle garder."""
    n = sum(1 for k in ("display_name", "company", "job_title", "phone", "mobile", "address", "website", "notes", "anniversaire", "vault_ref") if str(c.get(k) or "").strip())
    n += len(c.get("emails") or [])
    if c.get("photo"):
        n += 2
    if c.get("favorite"):
        n += 3
    return n

def point_remplissage(entree):
    """Le point d'évolution `remplissage` (contrat 1.0)."""
    return {"valeur": remplissage(entree["c"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_remplissage(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_remplissage.json ; corpus doré dans contrats/CN_remplissage.corpus.json (sorties de l'ancien code, données synthétiques).
