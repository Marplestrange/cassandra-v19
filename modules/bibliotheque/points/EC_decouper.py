# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Bibliotheque : Le texte en passages ordonnés : les paragraphes s'additionnent jusqu'à ~900 caractères ; un paragraphe trop long se coupe à une fin de phrase (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : bibliotheque
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #c6709b
# HÔTE CN    : CN_module.py · decouper @1.0
# RÔLE       : Le texte en passages ordonnés : les paragraphes s'additionnent jusqu'à ~900 caractères ; un paragraphe trop long se coupe à une fin de phrase.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=decouper contrat=@1.0 version=EC0 empreinte=c6709b ▼▼▼
import re

PASSAGE_CIBLE, PASSAGE_MAX = 900, 1400

def decouper(corps, titre=""):
    """Le texte en passages ordonnés : les paragraphes s'additionnent jusqu'à ~900 caractères ; un paragraphe trop long se coupe à une fin de phrase."""
    morceaux = []
    for para in re.split(r"\n\s*\n", str(corps or "").replace("\r\n", "\n")):
        para = para.strip()
        while len(para) > PASSAGE_MAX:
            coupe = max(para.rfind(". ", 0, PASSAGE_MAX), para.rfind("\n", 0, PASSAGE_MAX))
            coupe = coupe + 1 if coupe > PASSAGE_MAX // 3 else PASSAGE_MAX
            morceaux.append(para[:coupe].strip())
            para = para[coupe:].strip()
        if para:
            morceaux.append(para)
    out = []
    for m in morceaux:
        if out and len(out[-1]) + len(m) + 2 <= PASSAGE_CIBLE:
            out[-1] += "\n\n" + m
        else:
            out.append(m)
    return out or [str(titre or "").strip() or "(vide)"]

def point_decouper(entree):
    """Le point d'évolution `decouper` (contrat 1.0)."""
    return {"valeur": decouper(entree["corps"], entree["titre"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_decouper(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de bibliotheque (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_decouper.json ; corpus doré dans contrats/CN_decouper.corpus.json (sorties de l'ancien code, données synthétiques).
