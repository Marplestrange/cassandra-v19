# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Dns : les dérives du DNS (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dns
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #f97c8f
# HÔTE CN    : CN_module.py · derives @1.0
# RÔLE       : compare la relève du DNS à la référence : ce qui a changé, disparu ou apparu, et dit quand c'est l'adresse publique du serveur qui a bougé.
# MÉTHODE    : fonction pure : chaque nom|type est comparé à sa référence ; un nom illisible est écarté ; une dérive d'adresse publique est reconnue quand l'enregistrement est resté sur l'ancienne adresse.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=derives contrat=@1.0 version=EC0 empreinte=f97c8f ▼▼▼

def calculer_derives(rel, inconnus, ref, ip_now, ip_ref):
    derives = []
    for cle in sorted(set(ref) | set(rel)):
        if cle in inconnus:
            continue                                       # on n'a pas pu lire ce nom : ni dérive ni conformité
        att, obs = ref.get(cle), rel.get(cle)
        nom, typ = cle.split("|")
        ip_derivee = bool(typ == "A" and ip_now and ip_ref and ip_now != ip_ref and att == [ip_ref] and obs == [ip_ref])
        if att == obs and not ip_derivee:
            continue
        derives.append({"cle": cle, "nom": nom, "type": typ, "attendu": att or [], "observe": obs or [], "ip_derivee": ip_derivee})
    return derives

def point_derives(entree):
    """Le point d'évolution `derives` (contrat 1.0) : la relève, les noms illisibles, la référence et les adresses publiques en entrée, les dérives en sortie."""
    return {"valeur": calculer_derives(entree["rel"], set(entree["inconnus"]), entree["ref"], entree["ip_now"], entree["ip_ref"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_derives(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de dns (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_derives.json ; corpus doré dans contrats/CN_derives.corpus.json (sorties de l'ancien code, données synthétiques).
