# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : ce que le modèle lit d'un acte (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #2b89b6
# HÔTE CN    : CN_module.py · resume_resultat @1.0
# RÔLE       : dit au modèle ce qui est arrivé à l'acte qu'il a demandé : fait, simplement raconté, simulé, refusé, échoué ou annulé.
# MÉTHODE    : fonction pure : une phrase par statut ; un résultat trop long est tronqué avec le nombre de caractères perdus.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=resume_resultat contrat=@1.0 version=EC0 empreinte=2b89b6 ▼▼▼
import json

RESULTAT_MAX = 6000

def court(x, maxi=RESULTAT_MAX):
    t = x if isinstance(x, str) else json.dumps(x, ensure_ascii=False, default=str)
    return t if len(t) <= maxi else t[:maxi - 40] + "… [tronqué, %d caractères]" % len(t)

def resume_resultat(r):
    """Ce que le modèle lit d'un acte : le résultat, ou pourquoi il n'y en a pas — jamais un silence."""
    st = r.get("statut")
    if st == "faite":
        return court(r.get("resultat"))
    if st == "racontee":
        return "Non exécuté : cet outil est au palier « raconter » — l'acte n'a pas eu lieu, il a été seulement raconté au journal. %s" % (r.get("simulation") or "")
    if st == "simulee":
        return "Simulé, non exécuté : %s" % (r.get("simulation") or "")
    if st == "refuse":
        return "Refusé : %s" % r.get("raison", "")
    if st == "echec":
        return "Échec : %s" % r.get("erreur", "")
    if st in ("annulee", "annulation_impossible"):
        return "L'acte a été fait puis ANNULÉ parce que sa preuve a échoué (%s) : rien n'est resté." % r.get("motif", "") if st == "annulee" else "L'acte a échoué à sa preuve et n'a pas pu être annulé : à vérifier à la main (%s)." % r.get("motif", "")
    return court(r)

def point_resume_resultat(entree):
    """Le point d'évolution `resume_resultat` (contrat 1.0)."""
    return {"texte": resume_resultat(entree["r"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_resume_resultat(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_resume_resultat.json ; corpus doré dans contrats/CN_resume_resultat.corpus.json (sorties de l'ancien code, données synthétiques).
