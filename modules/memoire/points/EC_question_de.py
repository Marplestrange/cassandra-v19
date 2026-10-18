# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Memoire : la question posée à l'utilisateur (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #f1438c
# HÔTE CN    : CN_module.py · question_de @1.0
# RÔLE       : formule en une phrase, sans jargon, la question que Cassandra pose à l'utilisateur quand sa mémoire hésite.
# MÉTHODE    : fonction pure : une phrase par source du doute ; les valeurs sont resserrées et tronquées ; la raison du veto est traduite en mots humains.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=question_de contrat=@1.0 version=EC0 empreinte=f1438c ▼▼▼

def raison_humaine(raison):
    r = str(raison or "").strip()
    if r.startswith("aucun terme du fait"):
        return "Mais je ne retrouve pas ça dans ce qui m'a amenée à le noter."
    if r.startswith("veto d'Itare"):
        motif = r.split(":", 1)[1].strip() if ":" in r else ""
        return ("Mais Itare, en relisant, a un doute : %s" % motif.rstrip(".") + ".") if motif else "Mais Itare, en relisant, a un doute."
    return ("Mais j'hésite : %s." % r.rstrip(".")) if r else "Mais je n'ai pas pu le confirmer."

def question_de(source, valeur, raison="", ancienne="", age_txt=""):
    """Une question se lit d'une traite : ce qu'elle voulait retenir, pourquoi elle hésite, ce qu'on attend (pas de jargon : veto, pièce, clé)."""
    v = " ".join(str(valeur or "").split())[:220]
    if source == "veto":
        return "Je voulais retenir : « %s ». %s Je le garde ?" % (v, raison_humaine(raison))
    if source == "reconciliation":
        return "J'ai deux versions de la même chose. Celle que je retiens : « %s ». Une nouvelle, moins sûre : « %s ». Laquelle est vraie ?" % (" ".join(str(ancienne or "").split())[:200], v[:200])
    if source == "revalidation":
        return "Je m'appuie sur ceci, que j'ai déduit%s sans jamais le vérifier : « %s ». C'est toujours vrai ?" % ((" il y a " + age_txt) if age_txt else "", v[:200])
    return v

def point_question_de(entree):
    """Le point d'évolution `question_de` (contrat 1.0)."""
    return {"valeur": question_de(entree["source"], entree["valeur"], entree["raison"], entree["ancienne"], entree["age_txt"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_question_de(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de memoire (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_question_de.json ; corpus doré dans contrats/CN_question_de.corpus.json (sorties de l'ancien code, données synthétiques).
