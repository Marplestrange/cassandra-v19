# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Salon : Le champ, normalisé : noms propres, `tous` -> _TOUS_ ; un humain se nomme par son compte (« humain:x »). Jamais lu dans le corps (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : salon
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #f6f084
# HÔTE CN    : CN_module.py · destinataires_de @1.0
# RÔLE       : Le champ, normalisé : noms propres, `tous` -> _TOUS_ ; un humain se nomme par son compte (« humain:x »). Jamais lu dans le corps.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=destinataires_de contrat=@1.0 version=EC0 empreinte=f6f084 ▼▼▼
import re

TOUS = "_TOUS_"

def nom_propre(nom):
    return re.sub(r"[^a-z0-9_\-]", "", str(nom or "").strip().lower())[:32]

def destinataires_de(d):
    """Le champ, normalisé : noms propres, `tous` -> _TOUS_ ; un humain se nomme par son compte (« humain:x »). Jamais lu dans le corps."""
    if isinstance(d, str):
        d = re.split(r"[,\s]+", d)
    out = []
    for x in d or []:
        x = str(x or "").strip().lstrip("@")
        if x.lower() in ("tous", "all", "_tous_"):
            x = TOUS
        elif x.lower().startswith("humain:"):
            x = "humain:" + x[7:].strip()[:80]
        else:
            x = nom_propre(x.lower().replace("invité:", "").replace("invite:", ""))
        if x and x not in out:
            out.append(x)
    return out

def point_destinataires_de(entree):
    """Le point d'évolution `destinataires_de` (contrat 1.0)."""
    return {"valeur": destinataires_de(entree["d"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_destinataires_de(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de salon (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_destinataires_de.json ; corpus doré dans contrats/CN_destinataires_de.corpus.json (sorties de l'ancien code, données synthétiques).
