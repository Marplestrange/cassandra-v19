# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Notes : dossier_ok (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : notes
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #78a429
# HÔTE CN    : CN_module.py · dossier_ok @1.0
# RÔLE       : dossier_ok.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=dossier_ok contrat=@1.0 version=EC0 empreinte=78a429 ▼▼▼

PROFONDEUR = 2

def segment_ok(s):
    s = str(s or "").strip()
    return bool(s) and len(s) <= 64 and s not in (".", "..") and not s.startswith(".") and not any(x in s for x in ("/", "\\", "\x00"))

def dossier_ok(ch):
    ch = str(ch or "").strip().replace("\\", "/")
    if not ch:
        return True
    if ch.startswith("/") or (len(ch) > 1 and ch[1] == ":"):
        return False
    parts = ch.strip("/").split("/")
    return len(parts) <= PROFONDEUR and all(segment_ok(x) for x in parts)

def point_dossier_ok(entree):
    """Le point d'évolution `dossier_ok` (contrat 1.0)."""
    return {"valeur": dossier_ok(entree["ch"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_dossier_ok(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de notes (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_dossier_ok.json ; corpus doré dans contrats/CN_dossier_ok.corpus.json (sorties de l'ancien code, données synthétiques).
