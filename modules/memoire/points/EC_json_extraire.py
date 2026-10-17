# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Memoire : extraction d'un objet JSON (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #69078c
# HÔTE CN    : CN_module.py · json_extraire @1.0
# RÔLE       : retrouve le premier objet JSON valide dans la réponse d'un modèle, même entouré de texte ou d'une clôture.
# MÉTHODE    : fonction pure : on tente le texte entier, puis chaque accolade ouvrante avec son équilibrage ; rien de valide rend None.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=json_extraire contrat=@1.0 version=EC0 empreinte=69078c ▼▼▼
import re

def json_extraire(texte):
    """Le premier objet JSON d'une réponse de modèle (avec ou sans clôture markdown)."""
    import json
    t = str(texte or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        pass
    i = t.find("{")
    while i >= 0:
        prof = 0
        for j in range(i, len(t)):
            prof += (t[j] == "{") - (t[j] == "}")
            if prof == 0:
                try:
                    return json.loads(t[i:j + 1])
                except ValueError:
                    break
        i = t.find("{", i + 1)
    return None

def point_json_extraire(entree):
    """Le point d'évolution `json_extraire` (contrat 1.0)."""
    return {"valeur": json_extraire(entree["texte"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_json_extraire(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de memoire (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_json_extraire.json ; corpus doré dans contrats/CN_json_extraire.corpus.json (sorties de l'ancien code, données synthétiques).
