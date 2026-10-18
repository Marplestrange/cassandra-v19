# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie : ce qu'une formule rapporte (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.1.0)  #91ee30
# HÔTE CN    : CN_evenements.py · commission @1.0
# RÔLE       : dit, pour une formule de rémunération et un nombre de places vendues, le forfait, la commission, le fixe et le total en centimes.
# MÉTHODE    : fonction pure ; trois groupes de formules (artiste, cachet, revendeur indépendant) qui ne se mélangent pas ; palier au-delà d'un nombre de places ; fixe du revendeur dû dès la première place.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=commission contrat=@1.0 version=EC0 empreinte=91ee30 ▼▼▼
def par_place(f, n):
    if f["palier"] and f["palier_n"] > 0:
        return f["com"] * min(n, f["palier_n"]) + f["palier_com"] * max(0, n - f["palier_n"])
    return f["com"] * n

def commission(f, places):
    n = max(0, int(places))
    role = f["role"]
    if role == "artiste":
        forfait, com, fixe = f["forfait"], f["com"] * n, 0
    elif role == "cachet":
        forfait, com, fixe = f["forfait"], 0, 0
    else:
        forfait, com, fixe = 0, par_place(f, n), (f["fixe"] if n > 0 else 0)
    return {"forfait": forfait, "commission": com, "fixe": fixe, "total": forfait + com + fixe}

def point_commission(entree):
    """Le point d'évolution `commission` (contrat 1.0) : la formule et le nombre de places en entrée, forfait, commission, fixe et total (centimes) en sortie."""
    return {"valeur": commission(entree["formule"], entree["places"])}
# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_commission(entree)` est le point d'évolution. Une EC peut changer la façon de calculer (nouveaux paliers, arrondis) ; elle ne peut changer ni la signature ni la forme de la sortie,
#      ni les invariants du contrat (des centimes entiers, un cachet reste un cachet, le fixe n'est dû qu'à partir de la première place).
# CN : appelée par `commission` de CN_evenements.py, par ctx.point : le CN décide (publier, verser, refuser), l'EC ne fait que calculer.
# LIEN : contrat dans contrats/CN_commission.json ; corpus doré dans contrats/CN_commission.corpus.json (recoupé par une écriture indépendante, place par place).
