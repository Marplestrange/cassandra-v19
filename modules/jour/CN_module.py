# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le bureau du jour
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : jour
# ZONE       : CN
# VERSION CN : 0.1.0  #37ab1b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le bureau du jour : assemble les signaux que les modules déclarent.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=37ab1b ▼▼▼
"""Le bureau du jour : assemble les signaux que les modules déclarent.

Une source qui échoue ne disparaît pas : elle rend une ligne qui dit qu'elle est en panne. C'est le point le plus important de l'écran — une bande
« ce qui brûle » vide parce qu'une lecture a échoué est indiscernable d'une bande vide parce que tout va bien, et c'est exactement le moment où l'on en a besoin.
"""
import threading
import time

BANDES = (
    ("brule", "Ce qui brûle", "Dépassé, ou qui le sera avant demain."),
    ("regarder", "À regarder", "Rien ne casse aujourd'hui, mais ça se dégrade."),
    ("jour", "Aujourd'hui", "Ce qui tombe dans la journée."),
)
CLES_BANDES = tuple(b[0] for b in BANDES)
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")
QUOI_NOM = {"tache": ("tâche", "tâches"), "rappel": ("rappel", "rappels"), "event": ("rendez-vous", "rendez-vous"), "decision": ("décision", "décisions"),
            "mandat": ("envoi à accorder", "envois à accorder"), "note": ("note", "notes"), "mail": ("message", "messages")}


def propre(x):
    """Un item reçu d'un module : la forme est imposée ici, jamais crue sur parole."""
    if not isinstance(x, dict) or x.get("bande") not in CLES_BANDES:
        return None
    g = x.get("geste")
    return {"bande": x["bande"], "quoi": str(x.get("quoi") or "")[:30], "titre": str(x.get("titre") or "")[:160], "detail": str(x.get("detail") or "")[:200],
            "nat": str(x.get("nat") or "")[:30], "ref": str(x.get("ref") or "")[:80], "poids": int(x.get("poids") or 0), "ou": str(x.get("ou") or "")[:30],
            "geste": [str(g[0])[:30], str(g[1])[:30]] if isinstance(g, (list, tuple)) and len(g) == 2 else None}


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


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)


def tuiles(items, metas):
    """tuiles. Le calcul est un POINT D'ÉVOLUTION : points/EC_tuiles.py."""
    return _point("tuiles", {"items": items, "metas": metas})["valeur"]


def brancher(ctx):
    global _point
    _point = ctx.point
    verrou = threading.Lock()
    garde = {}                     # (compte, module.signal) -> (ts, resultat) pour les sources à cadence

    def aujourdhui(ctx):
        compte = ctx.compte or ""
        admin = ctx.est_admin(compte)
        items, pannes, metas, chrono = [], [], {}, []
        t0 = time.time()
        for m in sorted(ctx.manifestes_actifs(), key=lambda m: m.id):
            for sg in m.signaux:
                if sg.admin and not admin:
                    continue
                cle = (compte, "%s.%s" % (m.id, sg.id))
                r, vu = None, False
                if sg.cadence_s:
                    with verrou:
                        g = garde.get(cle)
                    if g and time.time() - g[0] < sg.cadence_s:
                        r, vu = g[1], True
                        chrono.append("%s gardé" % sg.id)
                if not vu:
                    ts = time.time()
                    r = ctx.executer_lecture("%s.%s" % (m.id, sg.capacite))
                    chrono.append("%s %.1f ms" % (sg.id, (time.time() - ts) * 1000))
                    if r is not None and sg.cadence_s:
                        with verrou:
                            garde[cle] = (time.time(), r)
                if r is None or not isinstance(r.get("items"), list):
                    pannes.append(sg.id)
                    items.append({"bande": "regarder", "quoi": "panne", "titre": "%s : lecture en panne" % sg.libelle, "detail": "La source du module « %s » n'a pas répondu." % m.id,
                                  "nat": "", "ref": "", "poids": 80, "ou": "", "geste": None})
                    continue
                for x in r["items"]:
                    p = propre(x)
                    if p:
                        items.append(p)
                if isinstance(r.get("meta"), dict):
                    metas[sg.id] = r["meta"]
        bandes = []
        for cle, nom, quoi in BANDES:
            dedans = sorted([x for x in items if x["bande"] == cle], key=lambda x: -x["poids"])
            bandes.append({"cle": cle, "n": nom, "quoi": quoi, "items": dedans[:40], "total": len(dedans)})
        t = time.localtime()
        return {"bandes": bandes, "admin": admin, "pannes": pannes, "quand": time.strftime("%Y-%m-%d %H:%M"),
                "jour": "%s %d %s" % (JOURS[t.tm_wday], t.tm_mday, MOIS[t.tm_mon - 1]), "total": len(items), "tuiles": tuiles(items, metas),
                "calcule": time.strftime("%H:%M"), "duree_ms": int((time.time() - t0) * 1000), "sources": chrono}

    ctx.implementer("aujourdhui", aujourdhui)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : propre, compo, tuiles, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
