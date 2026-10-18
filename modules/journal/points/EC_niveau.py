# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Journal : le niveau d'une ligne de journal (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : journal
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #2f996d
# HÔTE CN    : CN_module.py · niveau @1.0
# RÔLE       : range une ligne de journal dans un niveau, quelle que soit la façon dont le programme l'a écrite.
# MÉTHODE    : fonction pure : une table ordonnée de préfixes (critical avant crit, error avant err) ; « 1 », « true », « vrai », « oui » valent avertissement ; le reste prend le défaut.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=niveau contrat=@1.0 version=EC0 empreinte=2f996d ▼▼▼

_ENV_NIVEAUX = (("critical", "critique"), ("crit", "critique"), ("fatal", "critique"), ("alert", "critique"),
                ("error", "erreur"), ("erreur", "erreur"), ("err", "erreur"), ("fail", "erreur"), ("traceback", "erreur"),
                ("warning", "avertissement"), ("warn", "avertissement"), ("avertissement", "avertissement"),
                ("avoir", "avertissement"), ("debug", "info"), ("notice", "info"), ("info", "info"), ("ok", "info"), ("success", "info"))

def _niveau(v, defaut="info") -> str:
    s = str(v if v is not None else "").strip().lower()
    if not s:
        return defaut
    for cle, niveau in _ENV_NIVEAUX:
        if s == cle or s.startswith(cle):
            return niveau
    if s in ("1", "true", "vrai", "oui"):
        return "avertissement"
    return defaut

def point_niveau(entree):
    """Le point d'évolution `niveau` (contrat 1.0)."""
    return {"valeur": _niveau(entree["v"], entree["defaut"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_niveau(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de journal (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_niveau.json ; corpus doré dans contrats/CN_niveau.corpus.json (sorties de l'ancien code, données synthétiques).
