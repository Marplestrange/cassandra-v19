# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : un rôle, un dossier (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #dcfc33
# HÔTE CN    : CN_module.py · roles_uniques @1.0
# RÔLE       : départage les dossiers qui se disputent un même rôle : le drapeau du serveur tranche, à défaut le nom le plus court.
# MÉTHODE    : fonction pure : un regroupement par rôle, un gagnant par rôle ; les perdants perdent leur rôle et gardent trace de celui qu'ils ont perdu.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=roles_uniques contrat=@1.0 version=EC0 empreinte=dcfc33 ▼▼▼

def roles_uniques(dossiers):
    """UN RÔLE N'APPARTIENT QU'À UN DOSSIER. Sur une boîte OVH, `Trash` porte le drapeau et `Deleted Messages` contient « deleted » : les deux décrochaient
    « corbeille ». Le drapeau du serveur tranche ; à défaut, le nom le plus court. Les perdants redeviennent des dossiers ordinaires, sous leur nom réel."""
    par_role = {}
    for f in dossiers:
        r = f.get("role") or ""
        if r and r != "inbox":
            par_role.setdefault(r, []).append(f)
    for role, lot in par_role.items():
        if len(lot) < 2:
            continue
        drapeaux = [f for f in lot if f.get("role_flag")]
        garde = (drapeaux or sorted(lot, key=lambda f: (len(f["nom"]), f["nom"].lower())))[0]
        for f in lot:
            if f is not garde:
                f["role_ecarte"] = role
                f["role"] = ""
    return dossiers

def point_roles_uniques(entree):
    """Le point d'évolution `roles_uniques` (contrat 1.0)."""
    return {"valeur": roles_uniques(entree["dossiers"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_roles_uniques(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_roles_uniques.json ; corpus doré dans contrats/CN_roles_uniques.corpus.json (sorties de l'ancien code, données synthétiques).
