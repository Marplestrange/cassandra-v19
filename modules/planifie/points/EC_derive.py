# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Planifie : la dérive des durées (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #eef890
# HÔTE CN    : CN_module.py · derive @1.0
# RÔLE       : repère une tâche qui s'allonge sans jamais échouer, en comparant le premier tiers de ses durées au dernier.
# MÉTHODE    : fonction pure : moyenne du premier tiers contre moyenne du dernier tiers ; une dérive se dit à partir d'un facteur de 1,6 et d'au moins huit mesures.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=derive contrat=@1.0 version=EC0 empreinte=eef890 ▼▼▼

def derive(durees, mini=8):
    """Compare le premier tiers des durées au dernier : une moyenne globale masquerait la pente. Une tâche qui ne tombe jamais en erreur mais met trois fois plus de temps qu'il y a trois semaines."""
    if len(durees) < mini:
        return {}
    n = max(2, len(durees) // 3)
    a, b = sum(durees[:n]) / float(n), sum(durees[-n:]) / float(n)
    if a <= 0 or b / a < 1.6:
        return {}
    return {"avant_ms": int(a), "apres_ms": int(b), "facteur": round(b / a, 1), "mesures": len(durees)}

def point_derive(entree):
    """Le point d'évolution `derive` (contrat 1.0)."""
    return {"valeur": derive(entree["durees"], entree["mini"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_derive(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de planifie (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_derive.json ; corpus doré dans contrats/CN_derive.corpus.json (sorties de l'ancien code, données synthétiques).
