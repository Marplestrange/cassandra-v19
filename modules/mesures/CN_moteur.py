# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le moteur des mesures
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : mesures
# ZONE       : CN
# VERSION CN : 0.1.0  #5199b0
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le moteur des mesures : des POINTS (heure UTC, valeur) -> courbes par tranche, habitude, écarts, tendance, verdict. Aucune entrée/sortie : tout se teste.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=5199b0 ▼▼▼
"""Le moteur des mesures : des POINTS (heure UTC, valeur) -> courbes par tranche, habitude, écarts, tendance, verdict. Aucune entrée/sortie : tout se teste.

Les règles viennent de la V18, payées en service :
  - une courbe vide dit POURQUOI (rien à signaler / non configurée / jamais utilisée / muette) : « tout est stable » serait un mensonge par défaut ;
  - l'habitude d'un créneau (jour de semaine, heure) ne vaut qu'après plusieurs occurrences ; avant, on dit « habitude inconnue », on n'invente pas de normale ;
  - la normale d'un créneau est la MOYENNE de ses occurrences (une heure d'un jour = une occurrence), et la valeur courante est la même agrégation sur la dernière heure ;
  - seules les heures ACHEVÉES font une occurrence ;
  - la tendance a pour abscisse l'heure réelle (un trou ne comprime pas le temps) et exige 24 h de mesures ;
  - un seul seuil d'écart pour tout le monde.
"""
from __future__ import annotations

from datetime import datetime, timedelta

PERIODES = {
    "1h": {"minutes": 60, "bucket": "minute", "label": "1 heure"},
    "6h": {"minutes": 360, "bucket": "5min", "label": "6 heures"},
    "24h": {"minutes": 1440, "bucket": "hour", "label": "24 heures"},
    "7d": {"minutes": 10080, "bucket": "hour", "label": "7 jours"},
    "30d": {"minutes": 43200, "bucket": "day", "label": "30 jours"},
}
ETATS = {"a_jour": "à jour", "muette": "muette : plus de nouvelles mesures", "rien_a_signaler": "rien à signaler", "non_configuree": "non configurée",
         "jamais_utilisee": "jamais utilisée", "aucune_source": "aucune source", "aucune_donnee": "aucune donnée"}
HABITUDE_MIN = 3                              # un créneau n'a de « normale » qu'après trois occurrences
HABITUDE_JOURS = 7 * HABITUDE_MIN
SEUIL_ECART = 60                              # un seul seuil d'écart (en %)
SEUIL_SSL_JOURS = 21
SEUIL_SATURATION_JOURS = 30
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
FORMAT = "%Y-%m-%d %H:%M:%S"


def lire_ts(t):
    """« 2026-10-16 12:00:00 » ou « 2026-10-16T12:00:00.123Z » -> datetime naïf UTC ; None si illisible."""
    s = str(t or "").replace("T", " ")[:19]
    try:
        return datetime.strptime(s, FORMAT)
    except ValueError:
        return None


def ecrire_ts(d):
    return d.strftime(FORMAT) if d else None


def tranche(d, bucket):
    if bucket == "minute":
        return d.strftime("%Y-%m-%d %H:%M")
    if bucket == "5min":
        return d.replace(minute=d.minute - d.minute % 5).strftime("%Y-%m-%d %H:%M")
    if bucket == "day":
        return d.strftime("%Y-%m-%d")
    return d.strftime("%Y-%m-%d %H")


def agreger(valeurs, agregat):
    v = [x for x in valeurs if x is not None]
    if not v:
        return None
    if agregat == "min":
        return min(v)
    if agregat == "max":
        return max(v)
    if agregat == "somme":
        return sum(v)
    return sum(v) / len(v)


def _pts(points):
    """[(datetime, valeur)] trié, sans point illisible."""
    out = []
    for p in points or []:
        d = lire_ts(p[0] if isinstance(p, (list, tuple)) else p.get("ts"))
        v = p[1] if isinstance(p, (list, tuple)) else p.get("v")
        if d is not None and (v is None or isinstance(v, (int, float))):
            out.append((d, v))
    out.sort(key=lambda x: x[0])
    return out


def par_tranche(points, genre, agregat, bucket):
    """Les points regroupés par tranche : un compteur SOMME (un point sans valeur compte un), une jauge s'agrège (moyenne par défaut)."""
    groupes = {}
    for d, v in _pts(points):
        groupes.setdefault(tranche(d, bucket), []).append(1 if (genre == "compteur" and v is None) else v)
    sortie = []
    for k in sorted(groupes):
        v = sum(groupes[k]) if genre == "compteur" else agreger(groupes[k], agregat)
        sortie.append({"ts": k, "v": None if v is None else round(v, 2)})
    return sortie


def serie(mesure, series_brutes, periode="24h", maintenant=None, top=6):
    """La courbe d'une mesure sur une période, dans la forme que lit l'écran. `mesure` : dict de la déclaration ; `series_brutes` : [{"nom", "points"}] ou None (source muette)."""
    p = PERIODES.get(periode) or PERIODES["24h"]
    maintenant = maintenant or datetime.utcnow()
    depuis = maintenant - timedelta(minutes=p["minutes"])
    base = {"ok": True, "key": mesure["id"], "label": mesure["libelle"], "unit": mesure.get("unite", ""), "family": mesure.get("famille", ""), "kind": mesure["genre"],
            "period": periode, "bucket": p["bucket"], "from": ecrire_ts(depuis), "to": ecrire_ts(maintenant), "aggregated": False}
    if series_brutes is None:
        return dict(base, points=[], series=[], reason="source muette : la lecture a échoué", count=0)
    dans = []
    for s in series_brutes:
        pts = [(d, v) for d, v in _pts(s.get("points")) if depuis <= d <= maintenant]
        dans.append((s.get("nom") or mesure["libelle"], pts))
    if mesure.get("groupee"):
        agr = mesure.get("agregat", "moy")
        def cle(x):
            vals = [v for _, v in x[1] if v is not None]
            return agreger(vals, agr) if vals else None
        mauvais_bas = mesure.get("pire") == "bas"
        classes = [x for x in dans if cle(x) is not None]
        classes.sort(key=lambda x: cle(x), reverse=not mauvais_bas)             # les N PIRES : les plus hauts, ou les plus bas quand « pire » est bas
        dans = classes[:max(1, int(top))]
    sortie = [{"name": nom, "points": par_tranche([(ecrire_ts(d), v) for d, v in pts], mesure["genre"], mesure.get("agregat", "moy"), p["bucket"])} for nom, pts in dans]
    valeurs = [x["v"] for s in sortie for x in s["points"] if x["v"] is not None]
    return dict(base, series=sortie, points=sortie[0]["points"] if sortie else [], min=min(valeurs) if valeurs else None, max=max(valeurs) if valeurs else None,
                avg=round(sum(valeurs) / len(valeurs), 2) if valeurs else None, last=valeurs[-1] if valeurs else None, count=len(valeurs))


def etat_source(mesure, series_brutes, maintenant=None):
    """L'état d'une source, DIT en mots : une courbe vide doit expliquer pourquoi."""
    maintenant = maintenant or datetime.utcnow()
    if series_brutes is None:
        return {"etat": "aucune_source", "premiere": None, "derniere": None}
    tous = [d for s in series_brutes for d, _ in _pts(s.get("points"))]
    premiere, derniere = (min(tous), max(tous)) if tous else (None, None)
    if derniere is None:
        etat = mesure.get("vide") or ("rien_a_signaler" if mesure["genre"] == "compteur" else "aucune_donnee")
    else:
        fr = mesure.get("fraicheur_s") or 0
        etat = "muette" if fr and (maintenant - derniere).total_seconds() > fr else "a_jour"
    return {"etat": etat, "premiere": ecrire_ts(premiere), "derniere": ecrire_ts(derniere)}


def fiche_source(mesure, series_brutes, maintenant=None):
    """Une ligne de la liste des sources, dans la forme de l'écran."""
    maintenant = maintenant or datetime.utcnow()
    e = etat_source(mesure, series_brutes, maintenant)
    age = (maintenant - lire_ts(e["premiere"])).total_seconds() if e["premiere"] else None
    habitude = bool(age is not None and age >= HABITUDE_JOURS * 86400)
    dans = None if (habitude or age is None) else max(1, int((HABITUDE_JOURS * 86400 - age) // 86400) + 1)
    return {"key": mesure["id"], "label": mesure["libelle"], "unit": mesure.get("unite", ""), "family": mesure.get("famille", ""), "kind": mesure["genre"],
            "desc": mesure.get("description", ""), "available": series_brutes is not None, "etat": e["etat"], "etat_texte": ETATS.get(e["etat"], e["etat"]),
            "premiere": e["premiere"], "derniere": e["derniere"], "habitude_connue": habitude, "habitude_dans_jours": dans, "nature": mesure.get("nature", "serie"),
            "pire": mesure.get("pire", "haut"), "forecast": bool(mesure.get("plafond")), "grouped": bool(mesure.get("groupee"))}


def _occurrences(mesure, points):
    """Une occurrence = une heure d'un jour, agrégée à part : {(jour_semaine, heure): [valeurs d'heure]} et la valeur par heure."""
    par_heure = {}
    for d, v in _pts(points):
        par_heure.setdefault(d.replace(minute=0, second=0, microsecond=0), []).append(1 if (mesure["genre"] == "compteur" and v is None) else v)
    sortie = {}
    for h, vals in par_heure.items():
        sortie[h] = sum(vals) if mesure["genre"] == "compteur" else agreger(vals, mesure.get("agregat", "moy"))
    return sortie


def profil(mesure, series_brutes, maintenant=None, semaines=4):
    """La valeur habituelle pour ce jour de semaine et cette heure, et l'écart de la dernière heure. Sur un historique trop court, on le DIT."""
    maintenant = maintenant or datetime.utcnow()
    if series_brutes is None:
        return {"ok": True, "key": mesure["id"], "enough": False, "reason": "source absente"}
    points = [p for s in series_brutes for p in (s.get("points") or [])]
    heure_courante = maintenant.replace(minute=0, second=0, microsecond=0)
    debut = heure_courante - timedelta(weeks=max(1, int(semaines))) + timedelta(hours=1)     # la plus ancienne est toujours entamée : on la saute
    occ = {h: v for h, v in _occurrences(mesure, points).items() if debut <= h < heure_courante and v is not None}
    creneaux = {}
    for h, v in occ.items():
        creneaux.setdefault((h.weekday(), h.hour), []).append(v)
    creneau = (maintenant.weekday(), maintenant.hour)
    vus = len(creneaux.get(creneau, []))
    normale = (sum(creneaux[creneau]) / vus) if vus else None
    recents = [(d, v) for d, v in _pts(points) if d >= maintenant - timedelta(minutes=60)]
    if recents:
        vals = [1 if (mesure["genre"] == "compteur" and v is None) else v for _, v in recents]
        valeur = round(sum(vals) if mesure["genre"] == "compteur" else agreger(vals, mesure.get("agregat", "moy")), 2)
    else:
        valeur = 0 if mesure["genre"] == "compteur" else None
    assez = vus >= HABITUDE_MIN
    ecart = round((valeur - normale) / abs(normale) * 100) if (assez and normale not in (None, 0) and valeur is not None) else None
    jour, heure = JOURS[maintenant.weekday()], maintenant.hour
    return {"ok": True, "key": mesure["id"], "label": mesure["libelle"], "enough": assez, "slot": "%d-%02d" % creneau, "slot_label": "%s %d h" % (jour, heure),
            "baseline": None if normale is None else round(normale, 2), "samples": vus, "current": valeur, "deviation_pct": ecart,
            "slots_known": len(creneaux), "days_known": len({c[0] for c in creneaux}),
            "reason": "" if assez else "habitude inconnue : le créneau %s %d h n'a été vu que %d fois, il en faut %d" % (jour, heure, vus, HABITUDE_MIN)}


def prevision(mesure, series_brutes, maintenant=None, jours=14):
    """La date de saturation, par régression linéaire sur la moyenne horaire. L'abscisse est l'heure réelle ; moins de 24 h de mesures : aucune tendance fiable."""
    maintenant = maintenant or datetime.utcnow()
    if not mesure.get("plafond"):
        return {"ok": False, "reason": "mesure non projetable"}
    if series_brutes is None:
        return {"ok": True, "key": mesure["id"], "enough": False, "reason": "source absente"}
    depuis = maintenant - timedelta(days=max(3, int(jours)))
    heures = {}
    for s in series_brutes:
        for d, v in _pts(s.get("points")):
            if v is not None and d >= depuis:
                heures.setdefault(d.replace(minute=0, second=0, microsecond=0), []).append(v)
    pts = sorted((h, sum(v) / len(v)) for h, v in heures.items())
    if len(pts) < 24:
        return {"ok": True, "key": mesure["id"], "enough": False, "reason": "moins de 24 heures de mesures : aucune tendance fiable"}
    t0 = pts[0][0]
    xy = [((h - t0).total_seconds() / 3600.0, y) for h, y in pts]
    n = len(xy)
    sx, sy = sum(x for x, _ in xy), sum(y for _, y in xy)
    sxx, sxy = sum(x * x for x, _ in xy), sum(x * y for x, y in xy)
    denom = n * sxx - sx * sx
    if not denom:
        return {"ok": True, "key": mesure["id"], "enough": False, "reason": "mesures constantes"}
    pente = (n * sxy - sx * sy) / denom                      # par heure
    actuel = xy[-1][1]
    if pente <= 0.0001:
        return {"ok": True, "key": mesure["id"], "enough": True, "trend": round(pente * 24, 3), "current": round(actuel, 1), "saturation_days": None,
                "note": "tendance stable ou décroissante — aucune saturation en vue"}
    h_restantes = (mesure["plafond"] - actuel) / pente
    return {"ok": True, "key": mesure["id"], "label": mesure["libelle"], "enough": True, "current": round(actuel, 1), "trend": round(pente * 24, 3),
            "saturation_days": round(h_restantes / 24, 1), "saturation_date": ecrire_ts(maintenant + timedelta(hours=h_restantes))[:10],
            "note": "à ce rythme (%+.2f %s/jour)" % (pente * 24, mesure.get("unite", ""))}


def _ligne(niveau, titre, detail="", gestes=None):
    return {"niveau": niveau, "titre": titre, "detail": detail, "gestes": gestes or []}


def verdict(mesures, lectures, maintenant=None, seuil_ecart=SEUIL_ECART):
    """Ce que l'onglet dit à l'ouverture. `lectures` : {id_mesure: series_brutes ou None}. Une lecture qui échoue devient une ligne « sans nouvelles » : un verdict muet ferait croire que tout va bien."""
    maintenant = maintenant or datetime.utcnow()
    lignes, fiches = [], []
    for m in mesures:
        sb = lectures.get(m["id"])
        f = fiche_source(m, sb, maintenant)
        fiches.append(f)
        if sb is None:
            continue
        # échéance : une jauge « en jours » dont plus bas est pire (jours avant expiration d'un certificat)
        if m.get("unite") == "j" and m.get("pire") == "bas":
            derniers = {}
            for s in sb:
                pts = [(d, v) for d, v in _pts(s.get("points")) if v is not None]
                if pts:
                    derniers[s.get("nom") or m["libelle"]] = pts[-1][1]
            if derniers:
                nom, j = min(derniers.items(), key=lambda x: x[1])
                if j < 7:
                    lignes.append(_ligne("panne", "%s : %d jour(s)" % (nom, j), m["libelle"]))
                elif j < SEUIL_SSL_JOURS:
                    lignes.append(_ligne("regarder", "%s : %d jours" % (nom, j), m["libelle"]))
        # disponibilité : une courbe groupée en % dont plus bas est pire, dont le dernier point est à zéro (tombé)
        elif m.get("groupee") and m.get("unite") == "%" and m.get("pire") == "bas":
            for s in sb:
                pts = [(d, v) for d, v in _pts(s.get("points")) if v is not None]
                if pts and pts[-1][1] <= 0 and (maintenant - pts[-1][0]).total_seconds() < 3600 * 6:
                    lignes.append(_ligne("panne", "%s ne répond pas" % (s.get("nom") or m["libelle"]), "dernière mesure %s" % ecrire_ts(pts[-1][0])[:16]))
        # tendance : saturation proche
        if m.get("plafond"):
            pv = prevision(m, sb, maintenant)
            j = pv.get("saturation_days")
            if pv.get("enough") and j is not None:
                if j <= 7:
                    lignes.append(_ligne("panne", "%s plein dans %d jour(s)" % (m["libelle"], j), pv.get("note", "")))
                elif j <= SEUIL_SATURATION_JOURS:
                    lignes.append(_ligne("regarder", "%s plein dans %d jours" % (m["libelle"], j), pv.get("note", "")))
        # écart à l'habitude (jamais pour une photo, ni une courbe par élément)
        if m.get("nature") != "etat" and not m.get("groupee"):
            p = profil(m, sb, maintenant)
            if p.get("enough") and p.get("deviation_pct") is not None and abs(p["deviation_pct"]) >= seuil_ecart:
                lignes.append(_ligne("regarder", "%s : %+d %% par rapport à l'habitude" % (m["libelle"], p["deviation_pct"]),
                                     "%s %s · habituellement %s" % (p["current"], m.get("unite", ""), p["baseline"])))
    ecartees = [m["id"] for m in mesures if lectures.get(m["id"]) is None]
    muettes = [f for f in fiches if f["etat"] == "muette"]
    muettes += [f for f in fiches if not f["available"]]
    pas_encore = [f for f in fiches if f["available"] and f["kind"] == "jauge" and f["etat"] == "a_jour" and not f["habitude_connue"] and f["nature"] != "etat"]
    if muettes:
        vus = sorted({str(f.get("derniere") or "")[:16] for f in muettes})
        lignes.append(_ligne("muet", "Sans nouvelles : %s" % ", ".join(f["label"] for f in muettes[:5]) + (" (+%d)" % (len(muettes) - 5) if len(muettes) > 5 else ""),
                             "Dernière mesure %s. Ce qui suit date d'avant." % (vus[-1] if vus and vus[-1] else "?")))
    if pas_encore:
        dans = max([f.get("habitude_dans_jours") or 0 for f in pas_encore] or [0])
        lignes.append(_ligne("pas_encore", "%d mesure%s : habitude encore inconnue" % (len(pas_encore), "s" if len(pas_encore) > 1 else ""),
                             "%s — mesurées, mais pas assez longtemps pour savoir ce qui est normal à cette heure ce jour-là. Aucun écart n'est affiché tant que ce n'est pas le cas "
                             "(encore %d jour%s)." % (", ".join(f["label"] for f in pas_encore[:6]), dans, "s" if dans > 1 else "")))
    lignes.sort(key=lambda l: {"panne": 0, "regarder": 1, "muet": 2, "pas_encore": 3}.get(l["niveau"], 9))
    n_panne = sum(1 for l in lignes if l["niveau"] == "panne")
    n_regarder = sum(1 for l in lignes if l["niveau"] == "regarder")
    a_jour = sum(1 for f in fiches if f["etat"] in ("a_jour", "rien_a_signaler"))
    if n_panne:
        premiere = next(l for l in lignes if l["niveau"] == "panne")
        niveau, titre = "panne", premiere["titre"] + ("." if n_panne == 1 else " — et %d autre%s." % (n_panne - 1, "s" if n_panne > 2 else ""))
        sous = (("%d point%s à regarder ensuite. " % (n_regarder, "s" if n_regarder > 1 else "")) if n_regarder else "") + ("Certaines sources sont sans nouvelles." if muettes else "Le reste des mesures est dans ses habitudes.")
    elif n_regarder:
        niveau, titre = "regarder", "Rien ne casse, mais %d point%s à regarder." % (n_regarder, "s" if n_regarder > 1 else "")
        sous = "Aucune panne. " + ("Certaines sources sont sans nouvelles." if muettes else "Le reste est dans ses habitudes.")
    elif muettes or ecartees:
        niveau, titre, sous = "inconnu", "Je ne peux pas dire que tout va bien.", "Des mesures manquent : ce qui est affiché date d'avant leur silence."
    else:
        niveau, titre = "stable", "Tout est stable."
        sous = "Aucune panne, aucune échéance sous %d jours, rien d'inhabituel — sur %d sources lues à l'instant." % (SEUIL_SSL_JOURS, a_jour)
    return {"ok": True, "niveau": niveau, "titre": titre, "sous_titre": sous, "lignes": lignes,
            "sources": {"a_jour": a_jour, "muettes": [f["label"] for f in muettes], "non_configurees": [f["label"] for f in fiches if f["etat"] == "non_configuree"],
                        "pas_encore": [f["label"] for f in pas_encore]},
            "seuils": {"ssl_jours": SEUIL_SSL_JOURS, "disque_jours": SEUIL_SATURATION_JOURS, "ecart_pct": seuil_ecart, "habitude_jours": HABITUDE_JOURS},
            "lu_le": ecrire_ts(maintenant)}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : lire_ts, ecrire_ts, tranche, agreger, _pts, par_tranche, serie, etat_source …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
