# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : le classement d'une fiche d'Amizo (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #bfc668
# HÔTE CN    : CN_module.py · classer_fiche @1.0
# RÔLE       : range une page lue : l'étagère, un titre propre, un résumé court et la fraîcheur de la lecture.
# MÉTHODE    : fonction pure : interne si l'adresse est « espace: », sinon externe ; le titre est celui de la page, sinon la première ligne du texte, sinon l'hôte ; le résumé tient en deux phrases au plus ; la fraîcheur se calcule entre la date de lecture et la date donnée (jamais l'horloge).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=classer_fiche contrat=@1.0 version=EC0 empreinte=bfc668 ▼▼▼
import datetime
import re

def _jour(texte):
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(texte or "").strip())
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).toordinal()
    except ValueError:
        return None

def _hote(url):
    m = re.match(r"^https?://([^/:?#@]+)", str(url or "").strip().lower())
    return m.group(1) if m else ""

def classer_fiche(url, titre, texte, lu_le, maintenant):
    interne = str(url or "").strip().lower().startswith("espace:")
    corps = str(texte or "").strip()
    t = " ".join(str(titre or "").split())
    if not t:
        for ligne in corps.split("\n"):
            if ligne.strip():
                t = " ".join(ligne.split())[:120]
                break
    if not t:
        t = _hote(url) or "Sans titre"
    t = t[:200]
    plat = " ".join(corps.split())
    phrases = re.split(r"(?<=[.!?])\s+", plat) if plat else []
    resume = ""
    for p in phrases[:2]:
        resume = (resume + " " + p).strip()
        if len(resume) >= 160:
            break
    if len(resume) > 300:
        coupe = resume[:300]
        espace = coupe.rfind(" ")
        resume = (coupe[:espace] if espace > 150 else coupe).rstrip()
    a, b = _jour(lu_le), _jour(maintenant)
    if a is None or b is None or a > b:
        fraicheur = "inconnue"
    elif b - a <= 30:
        fraicheur = "recente"
    elif b - a <= 365:
        fraicheur = "datee"
    else:
        fraicheur = "ancienne"
    return {"etagere": "interne" if interne else "externe", "titre": t, "resume": resume, "fraicheur": fraicheur}

def point_classer_fiche(entree):
    """Le point d'évolution `classer_fiche` (contrat 1.0)."""
    return {"valeur": classer_fiche(entree["url"], entree["titre"], entree["texte"], entree["lu_le"], entree["maintenant"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_classer_fiche(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_classer_fiche.json ; corpus doré dans contrats/CN_classer_fiche.corpus.json (sorties de la référence, données synthétiques).
