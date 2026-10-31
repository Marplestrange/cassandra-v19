# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : le plan d'une recherche d'Amizo (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #cfb89f
# HÔTE CN    : CN_module.py · planifier_recherche @1.0
# RÔLE       : décide, pour une demande, des requêtes à lancer, du nombre de sources à lire et de l'arrêt ; ne propose rien quand la bibliothèque sait déjà.
# MÉTHODE    : fonction pure : une requête est la demande elle-même, une autre ses mots-clés, les autres les expressions entre guillemets ; bornée par le budget ; rien du tout quand tous les mots de la demande sont déjà dans les titres connus.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=planifier_recherche contrat=@1.0 version=EC0 empreinte=cfb89f ▼▼▼
import re
import unicodedata

STOP = frozenset("le la les de du des un une et en il elle je tu ce que qui est par sur pour avec dans ou pas se te me on au ne son sa ses mon ma mes ton tes the a an and of to in on for with is are "
                 "peux veux fais fait faire dis moi stp svp merci bonjour salut quelle quel quels quelles comment pourquoi quand donc mais alors aussi tout tous toute cherche trouve".split())

def mots_cles(texte):
    t = unicodedata.normalize("NFKD", str(texte or "").lower()).encode("ascii", "ignore").decode()
    vus, sortie = set(), []
    for w in re.findall(r"[a-z0-9]{3,}", t):
        if w not in STOP and w not in vus:
            vus.add(w)
            sortie.append(w)
    return sortie

def planifier_recherche(demande, connus, budget):
    d = " ".join(str(demande or "").split())[:300]
    nb_req = max(1, min(5, int(budget.get("requetes", 3))))
    nb_src = max(1, min(10, int(budget.get("sources", 4))))
    vide = {"requetes": [], "max_sources": 0, "arret": {"apres_sources": 0, "si_concordance": 2}, "deja_connu": False}
    if len(d) < 3:
        return vide
    mots = mots_cles(d)
    savoir = set()
    for c in connus:
        savoir.update(mots_cles(c))
    if mots and all(m in savoir for m in mots):
        return dict(vide, deja_connu=True)
    requetes, vues = [], set()
    candidates = [d[:120], " ".join(mots[:6])]
    for a, b in re.findall(r"«([^»]{3,80})»|\"([^\"]{3,80})\"", d):
        candidates.append((a or b).strip())
    for q in candidates:
        q = " ".join(q.split())[:120]
        if len(q) >= 3 and q.lower() not in vues:
            vues.add(q.lower())
            requetes.append(q)
    requetes = requetes[:nb_req]
    maxi = min(nb_src, 2 * len(requetes))
    return {"requetes": requetes, "max_sources": maxi, "arret": {"apres_sources": maxi, "si_concordance": 2}, "deja_connu": False}

def point_planifier_recherche(entree):
    """Le point d'évolution `planifier_recherche` (contrat 1.0)."""
    return {"valeur": planifier_recherche(entree["demande"], entree["connus"], entree["budget"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_planifier_recherche(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_planifier_recherche.json ; corpus doré dans contrats/CN_planifier_recherche.corpus.json (sorties de la référence, données synthétiques).
