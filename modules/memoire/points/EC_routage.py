# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Memoire : le routage de la mémoire (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #fd23a6
# HÔTE CN    : CN_module.py · routage @1.0
# RÔLE       : aiguille une question vers la bonne mémoire (ce qu'on retient, un épisode, la personne, les leçons, l'état du monde) par des règles fermées.
# MÉTHODE    : fonction pure : une chaîne d'expressions régulières ; la première qui reconnaît la question donne la route ; une question vide va au noyau.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=routage contrat=@1.0 version=EC0 empreinte=fd23a6 ▼▼▼
import re

RE_DECL_ECRITURE = re.compile(r"(?i)\b(?:retiens|retenir|note que|notes que|souviens-toi|m[ée]morise|n'oublie pas|garde en m[ée]moire|[àa] retenir)\b")

ROUTES = (
    ("ecriture", RE_DECL_ECRITURE),
    ("episode", re.compile(r"(?i)\b(?:la derni[èe]re fois|derni[èe]re fois|hier|la semaine derni[èe]re|on avait|tu avais|l'autre jour)\b")),
    ("personne", re.compile(r"(?i)\b(?:je suis|je pr[ée]f[èe]re|mon pr[ée]nom|tutoie|vouvoie|mes horaires|je m'appelle|qui suis-je|tu sais sur moi)\b")),
    ("lecon", re.compile(r"(?i)\b(?:le[çc]ons?|qu'as-tu appris|as-tu appris|erreurs? pass[ée]es?|retour d'exp[ée]rience)\b")),
    ("perception", re.compile(r"(?i)\b(?:disque|espace (?:libre|disque)|joignable|en ligne|hors ligne|hors-ligne|\bram\b|charge|cpu|certificat|ssl|sauvegardes?|tourne(?:nt)?|up\b|down\b|[ée]tat (?:de|du|des)|"
                              r"ça va|ca va|vivant|r[ée]pond|(?:est|sont)[- ](?:il|elle|ils|elles) install[ée]e?s?|install[ée]e?s? \?|mises? [àa] jour|conteneurs?|temp[ée]rature|uptime|"
                              r"red[ée]marrage requis|pare-feu actif|inodes?|raid|synchronis[ée]e?|interfaces? r[ée]seau|ports? ouverts?|[ée]coute sur)")),
)

def routage(question):
    """Le routage par règles, zéro appel de modèle : une chaîne fermée sur la question."""
    q = (question or "").strip()
    if not q:
        return "noyau"
    for nom, rx in ROUTES:
        if rx.search(q):
            return nom
    return "defaut"

def point_routage(entree):
    """Le point d'évolution `routage` (contrat 1.0)."""
    return {"valeur": routage(entree["question"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_routage(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de memoire (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_routage.json ; corpus doré dans contrats/CN_routage.corpus.json (sorties de l'ancien code, données synthétiques).
