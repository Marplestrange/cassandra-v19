# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agenda : Un mot (daily, weekly, quotidien…) ou une RRULE (avec ou sans « RRULE: ») -> la règle normalisée, ou '' si vide. Lève sur le reste (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agenda
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #000000
# HÔTE CN    : CN_module.py · regle_de @1.0
# RÔLE       : Un mot (daily, weekly, quotidien…) ou une RRULE (avec ou sans « RRULE: ») -> la règle normalisée, ou '' si vide. Lève sur le reste.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=regle_de contrat=@1.0 version=EC0 empreinte=000000 ▼▼▼

RECUR_MOTS = {"daily": "FREQ=DAILY", "weekly": "FREQ=WEEKLY", "monthly": "FREQ=MONTHLY", "yearly": "FREQ=YEARLY",
              "quotidien": "FREQ=DAILY", "hebdomadaire": "FREQ=WEEKLY", "mensuel": "FREQ=MONTHLY", "annuel": "FREQ=YEARLY"}

def regle_de(rec):
    """Un mot (daily, weekly, quotidien…) ou une RRULE (avec ou sans « RRULE: ») -> la règle normalisée, ou '' si vide. Lève sur le reste."""
    r = str(rec or "").strip()
    if not r:
        return ""
    if r.upper().startswith("RRULE:"):
        r = r[6:].strip()
    if r.lower() in RECUR_MOTS:
        return RECUR_MOTS[r.lower()]
    if "FREQ=" in r.upper():
        return r
    raise ValueError("récurrence : %s ou une règle RRULE (FREQ=WEEKLY;BYDAY=MO,WE)" % ", ".join(sorted(set(RECUR_MOTS))))

def point_regle_de(entree):
    """Le point d'évolution `regle_de` (contrat 1.0)."""
    return {"valeur": regle_de(entree["rec"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_regle_de(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agenda (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_regle_de.json ; corpus doré dans contrats/CN_regle_de.corpus.json (sorties de l'ancien code, données synthétiques).
