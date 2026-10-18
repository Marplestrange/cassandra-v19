# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Jour : les tuiles du jour (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : jour
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #f84bc9
# HÔTE CN    : CN_module.py · tuiles @1.0
# RÔLE       : compte, pour l'en-tête de la vue du jour, ce qu'il y a à faire, ce qui est en retard, ce qui attend un accord, ce qui est à relire, et dit de quoi chaque nombre est fait.
# MÉTHODE    : fonction pure : un compte par bande et par genre d'item ; une phrase « 2 tâches · 1 rappel » composée de ce qui est compté, jamais inventée.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=tuiles contrat=@1.0 version=EC0 empreinte=f84bc9 ▼▼▼

QUOI_NOM = {"tache": ("tâche", "tâches"), "rappel": ("rappel", "rappels"), "event": ("rendez-vous", "rendez-vous"), "decision": ("décision", "décisions"),
            "mandat": ("envoi à accorder", "envois à accorder"), "note": ("note", "notes"), "mail": ("message", "messages")}

def compo(items, bande=None, quois=()):
    """« 2 tâches · 1 rappel » : de quoi le nombre est fait. Compté, jamais inventé."""
    n = {}
    for x in items:
        if (bande is None or x["bande"] == bande) and x["quoi"] in quois:
            n[x["quoi"]] = n.get(x["quoi"], 0) + 1
    bouts = []
    for q in quois:
        c = n.get(q, 0)
        if c:
            un, plusieurs = QUOI_NOM.get(q, (q, q))
            bouts.append("%d %s" % (c, un if c == 1 else plusieurs))
    return " · ".join(bouts)

def tuiles(items, metas):
    def n(bande=None, quois=()):
        return sum(1 for x in items if (bande is None or x["bande"] == bande) and x["quoi"] in quois)
    ce = metas.get("courrier") or {}
    garde = int(ce.get("gardes") or 0)
    return {"non_lus": int(ce.get("non_lus") or 0) if ce.get("configuree") else 0,
            "a_faire": n("jour", ("tache", "rappel", "event")) + n(None, ("decision",)),
            "en_retard": n("brule", ("tache", "rappel")),
            "accord": n(None, ("mandat",)),
            "a_relire": n(None, ("note",)),
            "non_lus_s": ("sur %d gardé%s" % (garde, "s" if garde > 1 else "")) if garde else "",
            "a_faire_s": " · ".join(x for x in [compo(items, "jour", ("tache", "rappel", "event")), compo(items, None, ("decision",))] if x),
            "en_retard_s": compo(items, "brule", ("tache", "rappel")),
            "accord_s": compo(items, None, ("mandat",)),
            "a_relire_s": compo(items, None, ("note",))}

def point_tuiles(entree):
    """Le point d'évolution `tuiles` (contrat 1.0)."""
    return {"valeur": tuiles(entree["items"], entree["metas"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_tuiles(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de jour (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_tuiles.json ; corpus doré dans contrats/CN_tuiles.corpus.json (sorties de l'ancien code, données synthétiques).
