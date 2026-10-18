# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Dolibarr : Dolibarr rend souvent des nombres en texte (« 1 » pour 1) : on compare ce qui compte (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dolibarr
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.1)  #b87697
# HÔTE CN    : CN_module.py · egaux @1.0
# RÔLE       : Dolibarr rend souvent des nombres en texte (« 1 » pour 1) : on compare ce qui compte.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=egaux contrat=@1.0 version=EC0 empreinte=b87697 ▼▼▼

def _egaux(a, b):
    """Dolibarr rend souvent des nombres en texte (« 1 » pour 1) : on compare ce qui compte."""
    if a is None or b is None:
        return a is b or str(a or "") == str(b or "")
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return str(a) == str(b)

def point_egaux(entree):
    """Le point d'évolution `egaux` (contrat 1.0)."""
    return {"valeur": _egaux(entree["a"], entree["b"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_egaux(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de dolibarr (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_egaux.json ; corpus doré dans contrats/CN_egaux.corpus.json (sorties de l'ancien code, données synthétiques).
