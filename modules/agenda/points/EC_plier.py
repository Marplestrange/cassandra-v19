# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agenda : RFC 5545 : 75 octets au plus par ligne, la suite commence par une espace (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agenda
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #75c4e2
# HÔTE CN    : CN_module.py · plier @1.0
# RÔLE       : RFC 5545 : 75 octets au plus par ligne, la suite commence par une espace.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=plier contrat=@1.0 version=EC0 empreinte=75c4e2 ▼▼▼

def plier(ligne):
    """RFC 5545 : 75 octets au plus par ligne, la suite commence par une espace."""
    b = ligne.encode("utf-8")
    if len(b) <= 75:
        return ligne
    out, cur = [], ""
    for ch in ligne:
        if len((cur + ch).encode("utf-8")) > (75 if not out else 74):
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n ".join(out)

def point_plier(entree):
    """Le point d'évolution `plier` (contrat 1.0)."""
    return {"valeur": plier(entree["ligne"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_plier(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agenda (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_plier.json ; corpus doré dans contrats/CN_plier.corpus.json (sorties de l'ancien code, données synthétiques).
