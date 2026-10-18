# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : lecture d'un fichier vCard (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.2)  #b4b46b
# HÔTE CN    : CN_module.py · vcard_lire @1.0
# RÔLE       : lit un fichier vCard (RFC 6350) et rend les fiches qu'il contient, champ par champ.
# MÉTHODE    : fonction pure : dépliage des lignes, puis un petit automate par carte ; tolérante, un champ inconnu est ignoré.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=vcard_lire contrat=@1.0 version=EC0 empreinte=b4b46b ▼▼▼
import re

def vc_lire(s):
    sortie, i = "", 0
    s = s or ""
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            sortie += {"n": "\n", "N": "\n", ",": ",", ";": ";", "\\": "\\"}.get(s[i + 1], s[i + 1])
            i += 2
        else:
            sortie += s[i]
            i += 1
    return sortie

def vcard_lire(texte):
    """Tolérant : un champ inconnu est ignoré, une fiche illisible n'interrompt pas le reste."""
    brut = (texte or "").replace("\r\n", "\n").replace("\r", "\n")
    lignes = []
    for l in brut.split("\n"):
        if l[:1] in (" ", "\t") and lignes:
            lignes[-1] += l[1:]
        else:
            lignes.append(l)
    fiches, cur = [], None
    for l in lignes:
        h = l.lstrip()                                      # pas de strip à droite : un texte qui finit par une espace la garde
        if h.strip().upper() == "BEGIN:VCARD":
            cur = {"emails": [], "tel": [], "cell": []}
            continue
        if h.strip().upper() == "END:VCARD":
            if cur:
                fiches.append(cur)
            cur = None
            continue
        if cur is None or ":" not in h:
            continue
        gauche, _, val = h.partition(":")
        brut_val = val
        nom, params, val = gauche.split(";")[0].upper(), gauche.upper(), vc_lire(val)
        composants = [vc_lire(x).strip() for x in re.split(r"(?<!\\);", brut_val)]          # un « ; » échappé fait partie du texte (« Acme\\; Cie »)
        if nom == "FN":
            cur["display_name"] = val
        elif nom == "N" and not cur.get("display_name"):
            p = composants
            cur["display_name"] = " ".join(x for x in [p[1] if len(p) > 1 else "", p[0]] if x)
        elif nom == "EMAIL" and val:
            cur["emails"].append(val.strip().lower())
        elif nom == "TEL":
            (cur["cell"] if "CELL" in params or "MOBILE" in params else cur["tel"]).append(val)
        elif nom == "ORG":
            cur["company"] = composants[0]
        elif nom == "TITLE":
            cur["job_title"] = val
        elif nom == "ADR":
            cur["address"] = ", ".join(x for x in composants if x)
        elif nom == "URL":
            cur["website"] = val
        elif nom == "CATEGORIES":
            cur["tags"] = val
        elif nom == "NOTE":
            cur["notes"] = val
    return fiches

def point_vcard_lire(entree):
    """Le point d'évolution `vcard_lire` (contrat 1.0) : le texte du fichier en entrée, les fiches lues en sortie."""
    return {"fiches": vcard_lire(entree["texte"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_vcard_lire(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_vcard_lire.json ; corpus doré dans contrats/CN_vcard_lire.corpus.json (sorties de l'ancien code, données synthétiques).
