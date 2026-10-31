# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agents : le rapport du matin (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agents
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #e94c59
# HÔTE CN    : CN_module.py · rapport_matin @1.0
# RÔLE       : résume en trois phrases au plus, par agent, ce que le journal dit de la période : chaque phrase renvoie à une ligne précise du journal.
# MÉTHODE    : fonction pure : retient les événements de l'agent dans [debut, fin[, sépare actes, lectures, échecs et gestes restés racontés ou refusés, et bâtit une phrase par groupe qui cite le dernier acte ; la ligne citée est celle de cet acte.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=rapport_matin contrat=@1.0 version=EC0 empreinte=e94c59 ▼▼▼
def _cle(e):
    c = e.get("objet_id")
    return str(c) if c else "?"

def _pluriel(n, mot):
    return "%d %s%s" % (n, mot, "s" if n > 1 else "")

def rapport_matin(evenements, agents, debut, fin):
    sortie, silencieux = {}, []
    for a in agents:
        mien = [e for e in evenements if e.get("acteur") == a["id"] and debut <= float(e.get("ts", 0)) < fin]
        mien.sort(key=lambda e: int(e.get("id", 0)))
        faites = [e for e in mien if e.get("type") == "capacite.faite"]
        actes = [e for e in faites if not (e.get("donnees") or {}).get("lecture")]
        lectures = [e for e in faites if (e.get("donnees") or {}).get("lecture")]
        echecs = [e for e in mien if e.get("type") == "capacite.echouee"]
        restes = [e for e in mien if e.get("type") in ("capacite.racontee", "capacite.refusee")]
        phrases = []
        if actes:
            texte = "%s a fait %s" % (a["nom"], _pluriel(len(actes), "acte"))
            if lectures:
                texte += " et %s" % _pluriel(len(lectures), "lecture")
            phrases.append({"phrase": texte + " ; le dernier acte : %s." % _cle(actes[-1]), "journal": int(actes[-1]["id"])})
        elif lectures:
            phrases.append({"phrase": "%s n'a fait que %s ; la dernière : %s." % (a["nom"], _pluriel(len(lectures), "lecture"), _cle(lectures[-1])), "journal": int(lectures[-1]["id"])})
        if echecs:
            phrases.append({"phrase": "%s %s échoué ; le dernier : %s." % (_pluriel(len(echecs), "acte"), "a" if len(echecs) == 1 else "ont", _cle(echecs[-1])), "journal": int(echecs[-1]["id"])})
        if restes:
            phrases.append({"phrase": "%s %s raconté ou refusé, rien n'a été fait ; le dernier : %s." % (_pluriel(len(restes), "geste"), "est resté" if len(restes) == 1 else "sont restés", _cle(restes[-1])), "journal": int(restes[-1]["id"])})
        if phrases:
            sortie[a["id"]] = phrases[:3]
        else:
            silencieux.append(a["id"])
    return {"agents": sortie, "silencieux": silencieux}

def point_rapport_matin(entree):
    """Le point d'évolution `rapport_matin` (contrat 1.0)."""
    return {"valeur": rapport_matin(entree["evenements"], entree["agents"], entree["debut"], entree["fin"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_rapport_matin(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agents par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_rapport_matin.json ; corpus doré dans contrats/CN_rapport_matin.corpus.json (sorties de la référence, données synthétiques).
