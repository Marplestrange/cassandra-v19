# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Notes : lecture de l'en-tête d'une note (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : notes
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #13fe1d
# HÔTE CN    : CN_module.py · lire_entete @1.0
# RÔLE       : sépare l'en-tête d'une note (entre deux lignes « --- ») de son corps et en lit les clés.
# MÉTHODE    : fonction pure : un en-tête non fermé ou absent laisse la note intacte ; une valeur entre crochets devient une liste, true/oui et false/non des booléens.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=lire_entete contrat=@1.0 version=EC0 empreinte=13fe1d ▼▼▼

def lire_entete(texte):
    """Un fichier sans en-tête reste une note valide : on ne refuse pas une note écrite à la main dans un éditeur."""
    t = str(texte or "")
    if not t.startswith("---"):
        return {}, t
    fin = t.find("\n---", 3)
    if fin < 0:
        return {}, t
    meta = {}
    for ligne in t[3:fin].strip("\n").split("\n"):
        if ":" not in ligne:
            continue
        cle, _, val = ligne.partition(":")
        cle, val = cle.strip(), val.strip()
        if not cle:
            continue
        if val.startswith("[") and val.endswith("]"):
            meta[cle] = [x.strip() for x in val[1:-1].split(",") if x.strip()]
        elif val.lower() in ("true", "oui"):
            meta[cle] = True
        elif val.lower() in ("false", "non"):
            meta[cle] = False
        else:
            meta[cle] = val
    return meta, t[fin + 4:].lstrip("\n")

def point_lire_entete(entree):
    """Le point d'évolution `lire_entete` (contrat 1.0)."""
    return {"valeur": lire_entete(entree["texte"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_lire_entete(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de notes (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_lire_entete.json ; corpus doré dans contrats/CN_lire_entete.corpus.json (sorties de l'ancien code, données synthétiques).
