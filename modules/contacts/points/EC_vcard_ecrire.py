# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Contacts : écriture d'un fichier vCard (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : contacts
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #eaa43e
# HÔTE CN    : CN_module.py · vcard_ecrire @1.0
# RÔLE       : écrit des fiches au format vCard 3.0, échappées et repliées à 75 octets.
# MÉTHODE    : fonction pure : une suite de lignes par fiche, chacune échappée puis repliée ; les champs vides sont omis.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=vcard_ecrire contrat=@1.0 version=EC0 empreinte=eaa43e ▼▼▼

def vc_echapper(s):
    return str(s or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def vc_replier(ligne):
    """Repli à 75 octets, la continuation commençant par une espace (RFC 6350)."""
    if len(ligne.encode("utf-8")) <= 75:
        return ligne
    morceaux, cur = [], b""
    for ch in ligne:
        e = ch.encode("utf-8")
        if len(cur) + len(e) > (75 if not morceaux else 74):
            morceaux.append(cur.decode("utf-8"))
            cur = b""
        cur += e
    if cur:
        morceaux.append(cur.decode("utf-8"))
    return morceaux[0] + "".join("\r\n " + m for m in morceaux[1:])

def vcard_ecrire(fiches):
    lignes = []
    for c in fiches:
        nom = c.get("display_name") or (c.get("emails") or [""])[0]
        bouts = nom.split(" ", 1)
        lignes += ["BEGIN:VCARD", "VERSION:3.0", vc_replier("FN:" + vc_echapper(nom)), vc_replier("N:%s;%s;;;" % (vc_echapper(bouts[1] if len(bouts) > 1 else ""), vc_echapper(bouts[0])))]
        for a in c.get("emails") or []:
            lignes.append(vc_replier("EMAIL;TYPE=INTERNET:" + vc_echapper(a)))
        if c.get("phone"):
            lignes.append(vc_replier("TEL;TYPE=WORK,VOICE:" + vc_echapper(c["phone"])))
        if c.get("mobile"):
            lignes.append(vc_replier("TEL;TYPE=CELL:" + vc_echapper(c["mobile"])))
        if c.get("company") or c.get("job_title"):
            lignes.append(vc_replier("ORG:" + vc_echapper(c.get("company", ""))))
            if c.get("job_title"):
                lignes.append(vc_replier("TITLE:" + vc_echapper(c["job_title"])))
        if c.get("address"):
            lignes.append(vc_replier("ADR;TYPE=WORK:;;%s;;;;" % vc_echapper(c["address"])))
        if c.get("website"):
            lignes.append(vc_replier("URL:" + vc_echapper(c["website"])))
        if c.get("tags"):
            lignes.append(vc_replier("CATEGORIES:" + vc_echapper(c["tags"])))
        if c.get("notes"):
            lignes.append(vc_replier("NOTE:" + vc_echapper(c["notes"])))
        lignes.append("END:VCARD")
    return "\r\n".join(lignes) + "\r\n"

def point_vcard_ecrire(entree):
    """Le point d'évolution `vcard_ecrire` (contrat 1.0) : les fiches en entrée, le texte vCard en sortie."""
    return {"vcard": vcard_ecrire(entree["fiches"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_vcard_ecrire(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de contacts (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_vcard_ecrire.json ; corpus doré dans contrats/CN_vcard_ecrire.corpus.json (sorties de l'ancien code, données synthétiques).
