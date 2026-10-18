# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Jour : Un item reçu d'un module : la forme est imposée ici, jamais crue sur parole (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : jour
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #54d099
# HÔTE CN    : CN_module.py · propre @1.0
# RÔLE       : Un item reçu d'un module : la forme est imposée ici, jamais crue sur parole.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=propre contrat=@1.0 version=EC0 empreinte=54d099 ▼▼▼

BANDES = (
    ("brule", "Ce qui brûle", "Dépassé, ou qui le sera avant demain."),
    ("regarder", "À regarder", "Rien ne casse aujourd'hui, mais ça se dégrade."),
    ("jour", "Aujourd'hui", "Ce qui tombe dans la journée."),
)

CLES_BANDES = tuple(b[0] for b in BANDES)

def propre(x):
    """Un item reçu d'un module : la forme est imposée ici, jamais crue sur parole."""
    if not isinstance(x, dict) or x.get("bande") not in CLES_BANDES:
        return None
    g = x.get("geste")
    return {"bande": x["bande"], "quoi": str(x.get("quoi") or "")[:30], "titre": str(x.get("titre") or "")[:160], "detail": str(x.get("detail") or "")[:200],
            "nat": str(x.get("nat") or "")[:30], "ref": str(x.get("ref") or "")[:80], "poids": int(x.get("poids") or 0), "ou": str(x.get("ou") or "")[:30],
            "geste": [str(g[0])[:30], str(g[1])[:30]] if isinstance(g, (list, tuple)) and len(g) == 2 else None}

def point_propre(entree):
    """Le point d'évolution `propre` (contrat 1.0)."""
    return {"valeur": propre(entree["x"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_propre(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de jour (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_propre.json ; corpus doré dans contrats/CN_propre.corpus.json (sorties de l'ancien code, données synthétiques).
