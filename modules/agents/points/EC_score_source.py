# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : la confiance d'une source d'Amizo (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #6e6f36
# HÔTE CN    : CN_module.py · score_source @1.0
# RÔLE       : estime la confiance qu'on peut accorder à une adresse : bloquée = zéro, posée par un utilisateur = celle-là, sinon une estimation par l'hôte et par ce que la bibliothèque en a déjà fait vérifier.
# MÉTHODE    : fonction pure : base 0,3 ; https +0,1 ; hôte institutionnel +0,3 ; +0,1 par fiche vérifiée du même hôte (0,3 au plus) ; niveau haute dès 0,75, moyenne dès 0,5, faible au-dessus de zéro.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=score_source contrat=@1.0 version=EC0 empreinte=6e6f36 ▼▼▼
import re

def _hote(url):
    m = re.match(r"^https?://([^/:?#@]+)", str(url or "").strip().lower())
    h = m.group(1) if m else ""
    return h[4:] if h.startswith("www.") else h

def _niveau(c):
    if c >= 0.75:
        return "haute"
    if c >= 0.5:
        return "moyenne"
    if c > 0:
        return "faible"
    return "aucune"

def _institutionnel(h):
    return h.endswith((".gouv.fr", ".gov", ".gov.uk", ".edu", ".europa.eu")) or ".ac." in h

def score_source(url, confiance_connue, bloques, verifiees):
    h = _hote(url)
    if not h:
        return {"confiance": 0.0, "niveau": "aucune", "raisons": ["adresse illisible"]}
    for b in bloques:
        b = str(b).lower()
        if h == b or h.endswith("." + b):
            return {"confiance": 0.0, "niveau": "aucune", "raisons": ["source bloquée par un utilisateur"]}
    if confiance_connue is not None:
        c = round(min(1.0, max(0.0, float(confiance_connue))), 2)
        return {"confiance": c, "niveau": _niveau(c), "raisons": ["confiance posée par un utilisateur"]}
    c, raisons = 0.3, ["source encore inconnue"]
    if str(url).strip().lower().startswith("https://"):
        c += 0.1
        raisons.append("connexion chiffrée")
    if _institutionnel(h):
        c += 0.3
        raisons.append("organisme public ou universitaire")
    n = int(verifiees.get(h, 0))
    if n > 0:
        c += min(0.3, 0.1 * n)
        raisons.append("%d fiche(s) déjà vérifiée(s)" % n)
    c = round(min(1.0, max(0.0, c)), 2)
    return {"confiance": c, "niveau": _niveau(c), "raisons": raisons}

def point_score_source(entree):
    """Le point d'évolution `score_source` (contrat 1.0)."""
    return {"valeur": score_source(entree["url"], entree["confiance_connue"], entree["bloques"], entree["verifiees"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_score_source(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_score_source.json ; corpus doré dans contrats/CN_score_source.corpus.json (sorties de la référence, données synthétiques).
