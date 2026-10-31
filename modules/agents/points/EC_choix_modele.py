# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : le choix du modèle d'un agent (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #34fff5
# HÔTE CN    : CN_module.py · choix_modele @1.0
# RÔLE       : ordonne les rôles de modèle qu'un agent essaie : son modèle réglé, son secours, les rôles d'origine ; au plafond de coût, le secours seul ; un modèle déconseillé par les épreuves de sûreté est écarté.
# MÉTHODE    : fonction pure : au plafond, le secours seul (Cassandra, sans secours, garde son modèle) ; sinon le modèle réglé, à défaut le rôle d'origine de l'agent, puis le secours ; le rôle vide (le modèle du compte) n'est jamais écarté.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=choix_modele contrat=@1.0 version=EC0 empreinte=34fff5 ▼▼▼
def choix_modele(agent, modele, secours, au_plafond, origine, deconseilles, exiger):
    if au_plafond and (secours or agent != "cassandra"):
        roles = [secours] if secours else []
    else:
        if modele:
            roles = [modele]
        elif agent == "itare":
            roles = ["", origine.get("itare", "")]
        else:
            roles = [origine.get(agent, origine.get("cassandra", ""))]
        roles = roles + ([secours] if secours and secours not in roles else [])
    if exiger:
        roles = [r for r in roles if not r or r not in deconseilles]
    return roles

def point_choix_modele(entree):
    """Le point d'évolution `choix_modele` (contrat 1.0)."""
    return {"valeur": choix_modele(entree["agent"], entree["modele"], entree["secours"], entree["au_plafond"], entree["origine"], entree["deconseilles"], entree["exiger"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_choix_modele(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_choix_modele.json ; corpus doré dans contrats/CN_choix_modele.corpus.json (sorties de la référence, données synthétiques).
