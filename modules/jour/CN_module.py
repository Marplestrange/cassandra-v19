# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le bureau du jour
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : jour
# ZONE       : CN
# VERSION CN : 0.1.1  #20ba4d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le bureau du jour : assemble les signaux que les modules déclarent.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=20ba4d ▼▼▼
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


_REFERENCES = {}


def _appeler_point(point, entree):
    """Appelle le point d'évolution du module. Sans brancher() (un banc qui appelle la fonction seule), la RÉFÉRENCE du dépôt répond : points/EC_<point>.py, chargée par son chemin."""
    if _point is not None:
        return _point(point, entree)
    if point not in _REFERENCES:
        import importlib.util as _iu
        import pathlib as _pl
        chemin = _pl.Path(__file__).resolve().parent / "points" / ("EC_%s.py" % point)
        spec = _iu.spec_from_file_location("ec_ref_" + point, str(chemin))
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _REFERENCES[point] = getattr(mod, "point_" + point)
    return _REFERENCES[point](entree)


def propre(x):
    """Un item reçu d'un module : la forme est imposée ici, jamais crue sur parole. Le calcul est un POINT D'ÉVOLUTION : points/EC_propre.py."""
    return _appeler_point("propre", {"x": x})["valeur"]


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
