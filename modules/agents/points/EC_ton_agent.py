# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : le ton d'un agent (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #000000
# HÔTE CN    : CN_module.py · ton_agent @1.0
# RÔLE       : met en forme le ton réglé pour un agent (fiche ou instance) avant qu'il entre dans son prompt ; Amizo, sans ton réglé, reçoit le sien : précis et sourcé.
# MÉTHODE    : fonction pure : retire les caractères de contrôle, replie les espaces, borne les lignes vides, coupe à la longueur maximale sur une limite de mot ; ton vide = chaîne vide, sauf pour Amizo.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=ton_agent contrat=@1.0 version=EC0 empreinte=000000 ▼▼▼
import re

DEFAUT_AMIZO = "Précis et sourcé : tu donnes d'abord la réponse, puis tes sources avec leur date de lecture, puis ton niveau de confiance. Tu dis « je ne sais pas » plutôt que de deviner."

def ton_agent(agent, ton, longueur_max):
    """Le ton prêt pour le prompt : propre, borné, et un ton d'origine pour Amizo."""
    brut = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(ton or ""))
    propres, vide = [], False
    for ligne in brut.split("\n"):
        ligne = re.sub(r"[ \t]+", " ", ligne).strip()
        if ligne:
            propres.append(ligne)
            vide = False
        elif propres and not vide:
            propres.append("")
            vide = True
    texte = "\n".join(propres).strip()
    if not texte and agent == "amizo":
        texte = DEFAUT_AMIZO
    maxi = max(0, int(longueur_max))
    if len(texte) > maxi:
        coupe = texte[:maxi]
        espace = coupe.rfind(" ")
        texte = (coupe[:espace] if espace > maxi // 2 else coupe).rstrip()
    return texte

def point_ton_agent(entree):
    """Le point d'évolution `ton_agent` (contrat 1.0)."""
    return {"valeur": ton_agent(entree["agent"], entree["ton"], entree["longueur_max"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_ton_agent(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_ton_agent.json ; corpus doré dans contrats/CN_ton_agent.corpus.json (sorties de la référence, données synthétiques).
