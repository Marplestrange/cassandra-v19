# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : les outils présentés (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #9c0f20
# HÔTE CN    : CN_module.py · choisir_outils @1.0
# RÔLE       : choisit, parmi des centaines d'outils, ceux qu'on présente d'emblée au modèle : les plus proches de la demande, puis les lectures peu risquées.
# MÉTHODE    : fonction pure : un score par recouvrement de mots (sans mots vides) entre la demande et le nom et la description de l'outil ; à score égal les lectures d'abord, puis l'ordre alphabétique ; les autres restent joignables par la recherche.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=choisir_outils contrat=@1.0 version=EC0 empreinte=9c0f20 ▼▼▼
import re
import unicodedata

STOP = frozenset("le la les de du des un une et en il elle je tu ce que qui est par sur pour avec dans ou pas se te me on au ne son sa ses mon ma mes ton tes the a an and of to in on for with is are "
                 "peux veux fais fait faire dis moi stp svp merci bonjour salut est-ce quelle quel quels quelles comment pourquoi quand donc mais alors aussi tout tous toute".split())

def mots(texte):
    t = unicodedata.normalize("NFKD", str(texte or "").lower()).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z0-9]{3,}", t) if w not in STOP}

def score(outil, ms):
    cible = mots(outil["cle"].replace(".", " ").replace("_", " ") + " " + outil["description"])
    return len(ms & cible)

def choisir_outils(outils, texte, maxi):
    """Les outils présentés d'emblée : ceux dont le nom ou le libellé touche la demande d'abord, puis les lectures (peu risquées, utiles pour vérifier), jusqu'à `maxi`.
    Les autres restent joignables par outil_cherche / outil_appeler : présenter deux cents outils à chaque tour coûterait 30 000 jetons."""
    ms = mots(texte)
    notes = sorted(((score(o, ms), 0 if o["risque"] == "lecture" else 1, o["cle"], o) for o in outils), key=lambda x: (-x[0], x[1], x[2]))
    pris = [x[3] for x in notes if x[0] > 0][:maxi]
    for x in notes:
        if len(pris) >= maxi:
            break
        if x[3] not in pris and x[3]["risque"] == "lecture":
            pris.append(x[3])
    return pris

def point_choisir_outils(entree):
    """Le point d'évolution `choisir_outils` (contrat 1.0)."""
    return {"valeur": choisir_outils(entree["outils"], entree["texte"], entree["maxi"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_choisir_outils(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_choisir_outils.json ; corpus doré dans contrats/CN_choisir_outils.corpus.json (sorties de l'ancien code, données synthétiques).
