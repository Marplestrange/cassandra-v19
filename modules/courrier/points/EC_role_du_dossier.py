# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : rôle d'un dossier (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #8b66da
# HÔTE CN    : CN_module.py · role_du_dossier @1.0
# RÔLE       : dit à quoi sert un dossier de la boîte : le serveur l'annonce par un drapeau, à défaut le nom le suggère.
# MÉTHODE    : fonction pure : le drapeau du serveur fait autorité ; à défaut, des mots du nom ; « inbox » seulement pour le nom exact.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=role_du_dossier contrat=@1.0 version=EC0 empreinte=8b66da ▼▼▼

ROLES_DRAPEAUX = (("\\drafts", "drafts"), ("\\sent", "sent"), ("\\trash", "trash"), ("\\junk", "junk"), ("\\archive", "archive"), ("\\all", "all"))

ROLES_NOMS = {"drafts": ("draft", "brouillon"), "sent": ("sent", "envoy"), "trash": ("trash", "corbeille", "deleted"), "junk": ("junk", "spam", "indésirable"), "archive": ("archive",)}

def role_drapeau(flags):
    """Le rôle ANNONCÉ PAR LE SERVEUR : la seule source qui fasse autorité, le nom n'est qu'une supposition."""
    for att, role in ROLES_DRAPEAUX:
        if att in (flags or ""):
            return role
    return ""

def role_du_dossier(nom, flags):
    r = role_drapeau(flags)
    if r:
        return r
    bas = (nom or "").lower()
    for role, motifs in ROLES_NOMS.items():
        if any(m in bas for m in motifs):
            return role
    return "inbox" if bas == "inbox" else ""

def point_role_du_dossier(entree):
    """Le point d'évolution `role_du_dossier` (contrat 1.0)."""
    return {"valeur": role_du_dossier(entree["nom"], entree["flags"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_role_du_dossier(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_role_du_dossier.json ; corpus doré dans contrats/CN_role_du_dossier.corpus.json (sorties de l'ancien code, données synthétiques).
