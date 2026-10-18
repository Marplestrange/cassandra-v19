# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Modeles : les appels d'outils d'un message (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : modeles
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #18c990
# HÔTE CN    : CN_module.py · appels_de @1.0
# RÔLE       : lit les appels d'outils d'un modèle, quelle que soit sa façon de les écrire, en une forme unique.
# MÉTHODE    : fonction pure : l'identifiant manquant est fabriqué, les arguments texte sont lus en JSON, des arguments illisibles sont gardés sous `_brut` (tronqués à 2000 caractères).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=appels_de contrat=@1.0 version=EC0 empreinte=18c990 ▼▼▼
import json

def appels_de(brut_calls):
    """Les appels d'outils d'un message, normalisés : [{id, nom, arguments (dict)}]. Des arguments illisibles sont rendus tels quels sous `_brut` : le modèle se corrige au tour suivant."""
    out = []
    for i, tc in enumerate(brut_calls or []):
        f = (tc or {}).get("function") or {}
        a = f.get("arguments")
        if isinstance(a, str):
            try:
                a = json.loads(a) if a.strip() else {}
            except ValueError:
                a = {"_brut": a[:2000]}
        out.append({"id": str((tc or {}).get("id") or "call_%d" % i), "nom": str(f.get("name") or ""), "arguments": a if isinstance(a, dict) else {"_brut": str(a)[:2000]}})
    return out

def point_appels_de(entree):
    """Le point d'évolution `appels_de` (contrat 1.0) : les appels d'outils bruts d'un modèle en entrée, les appels normalisés en sortie."""
    return {"valeur": appels_de(entree["brut_calls"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_appels_de(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de modeles (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_appels_de.json ; corpus doré dans contrats/CN_appels_de.corpus.json (sorties de l'ancien code, données synthétiques).
