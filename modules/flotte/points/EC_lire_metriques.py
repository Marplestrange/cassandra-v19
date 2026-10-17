# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Flotte : lecture des métriques d'une machine (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : flotte
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #5c8a5a
# HÔTE CN    : CN_module.py · lire_metriques @1.0
# RÔLE       : transforme la sortie CPU:/RAM:/DISK:/HOST:/KERN:/UP: d'une machine du registre en mesures.
# MÉTHODE    : fonction pure : une ligne « CLÉ:valeur » par mesure, la virgule décimale acceptée, une valeur illisible ignorée.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=lire_metriques contrat=@1.0 version=EC0 empreinte=5c8a5a ▼▼▼

def lire_metriques(sortie):
    """La sortie CPU:/RAM:/DISK:/HOST:/KERN:/UP: des machines du registre -> dict."""
    r = {}
    for l in (sortie or "").splitlines():
        if ":" not in l:
            continue
        k, _, v = l.partition(":")
        v = v.strip().replace(",", ".")
        try:
            if k in ("CPU", "RAM", "DISK"):
                r[{"CPU": "cpu", "RAM": "ram", "DISK": "disque"}[k]] = round(float(v.rstrip("%")), 1)
            elif k == "HOST":
                r["hote"] = v
            elif k == "KERN":
                r["noyau"] = v
            elif k == "UP":
                r["uptime"] = v[:60]
        except ValueError:
            pass
    return r

def point_lire_metriques(entree):
    """Le point d'évolution `lire_metriques` (contrat 1.0)."""
    return {"valeur": lire_metriques(entree["sortie"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_lire_metriques(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de flotte (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_lire_metriques.json ; corpus doré dans contrats/CN_lire_metriques.corpus.json (sorties de l'ancien code, données synthétiques).
