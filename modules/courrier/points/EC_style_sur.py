# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : Les seules propriétés de mise en forme, avec des valeurs sans url(), sans expression, sans @import, sans accolade (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #b5570f
# HÔTE CN    : CN_module.py · style_sur @1.0
# RÔLE       : Les seules propriétés de mise en forme, avec des valeurs sans url(), sans expression, sans @import, sans accolade.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=style_sur contrat=@1.0 version=EC0 empreinte=b5570f ▼▼▼
import re

STYLES = {"color", "background-color", "font-size", "font-weight", "font-style", "font-family", "text-align", "text-decoration", "width", "height", "max-width", "min-width", "margin", "margin-top",
          "margin-bottom", "margin-left", "margin-right", "padding", "padding-top", "padding-bottom", "padding-left", "padding-right", "border", "border-top", "border-bottom", "border-left",
          "border-right", "border-collapse", "border-spacing", "line-height", "vertical-align", "white-space", "display", "text-transform", "letter-spacing"}

VALEUR_STYLE = re.compile(r"^[-#a-z0-9.,%()\s\"'!]+$", re.I)

def style_sur(valeur):
    """Les seules propriétés de mise en forme, avec des valeurs sans url(), sans expression, sans @import, sans accolade."""
    sortie = []
    for decl in (valeur or "").split(";"):
        if ":" not in decl:
            continue
        prop, _, val = decl.partition(":")
        prop, val = prop.strip().lower(), val.strip()
        bas = val.lower()
        if prop in STYLES and VALEUR_STYLE.match(val) and not any(x in bas for x in ("url(", "expression", "javascript", "@import", "behavior", "binding", "\\")):
            sortie.append("%s:%s" % (prop, val))
    return ";".join(sortie)

def point_style_sur(entree):
    """Le point d'évolution `style_sur` (contrat 1.0)."""
    return {"valeur": style_sur(entree["valeur"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_style_sur(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_style_sur.json ; corpus doré dans contrats/CN_style_sur.corpus.json (sorties de l'ancien code, données synthétiques).
