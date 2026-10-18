# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Sensorium : la pente d'une série (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #8f94b3
# HÔTE CN    : CN_module.py · pente @1.0
# RÔLE       : calcule la tendance d'une mesure sur quelques jours : de combien elle monte ou descend par jour, et si la droite colle aux points.
# MÉTHODE    : fonction pure : régression linéaire par les moindres carrés ; moins de six points ou des abscisses toutes égales ne donnent aucune pente.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=pente contrat=@1.0 version=EC0 empreinte=8f94b3 ▼▼▼

def _pente(points):
    """(pente par jour, r²) d'une série [(t_jours, y)], ou (None, 0)."""
    n = len(points)
    if n < 6:
        return None, 0.0
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    if sxx <= 0:
        return None, 0.0
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points)
    a = sxy / sxx
    syy = sum((p[1] - my) ** 2 for p in points)
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else 0.0
    return a, r2

def point_pente(entree):
    """Le point d'évolution `pente` (contrat 1.0)."""
    return {"valeur": _pente(entree["points"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_pente(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de sensorium (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_pente.json ; corpus doré dans contrats/CN_pente.corpus.json (sorties de l'ancien code, données synthétiques).
