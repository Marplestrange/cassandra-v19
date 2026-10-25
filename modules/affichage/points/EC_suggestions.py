# ═════════════════════════════════════════════════
# TITRE      : Affichage : les suggestions de placement de la journée (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : affichage
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.7.0)  #0c5588
# HÔTE CN    : CN_module.py · suggestions_plan @1.0
# RÔLE       : propose, pour les tâches encore à placer, une heure dans les temps libres de la journée : les plus pressantes d'abord, sans jamais empiéter ni sur un rendez-vous, ni sur un bloc déjà posé, ni sur une autre suggestion.
# MÉTHODE    : fonction pure en minutes depuis minuit du jour (la fenêtre peut passer minuit : la fin dépasse alors 1 440) ; les temps libres sont la fenêtre moins ce qui est occupé, à partir de maintenant ; chaque tâche reçoit un score (retard, échéance du jour, priorité, projet) puis, dans l'ordre du score, le premier temps libre assez long ; chaque suggestion consomme son créneau plus une marge.
# ═════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=suggestions_plan contrat=@1.0 version=EC0 empreinte=0c5588 ▼▼▼

PAS = 5                                   # les heures se posent au multiple de cinq minutes
MARGE = 5                                 # le souffle laissé après chaque tâche posée
DUREE_MIN, DUREE_MAX, DUREE_DEFAUT = 5, 480, 30
MAX_SUGGESTIONS = 10
BASE = 50
BONUS_PRIORITE = (0, 8, 16, 26)           # basse, normale, haute, urgente
BONUS_RETARD = 40                         # une tâche en retard passe devant
BONUS_RETARD_PAR_JOUR, JOURS_RETARD_MAX = 4, 5
BONUS_ECHEANCE_JOUR = 18
BONUS_PROJET = 6


def _entier(v, defaut=0):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return defaut
    return int(v)


def _arrondi(m):
    """Le prochain multiple de cinq minutes, jamais en deçà."""
    return -(-int(m) // PAS) * PAS


def _libres(fenetre, maintenant, occupes):
    """Les temps libres [(début, fin)] de la fenêtre, à partir de maintenant, sans les intervalles occupés ; un temps libre de moins de cinq minutes ne compte pas."""
    debut, fin = fenetre
    cur = max(debut, _arrondi(maintenant)) if maintenant is not None else debut
    libres = []
    for a, b in sorted((max(a, debut), min(b, fin)) for a, b in occupes if a < b):
        if b <= cur or a >= fin:
            continue
        if a > cur:
            libres.append((cur, a))
        cur = max(cur, b)
    if cur < fin:
        libres.append((cur, fin))
    return [(a, b) for a, b in libres if b - a >= PAS]


def _score(t):
    s = BASE + BONUS_PRIORITE[max(0, min(3, t["priorite"]))]
    if t["retard"] > 0:
        s += BONUS_RETARD + BONUS_RETARD_PAR_JOUR * min(t["retard"], JOURS_RETARD_MAX)
    if t["echeance_jour"]:
        s += BONUS_ECHEANCE_JOUR
    if t["projet"]:
        s += BONUS_PROJET
    return s


def _raison(t, creneau):
    r = []
    if t["retard"] > 0:
        r.append("en retard de %d j" % t["retard"])
    elif t["echeance_jour"]:
        r.append("échéance aujourd'hui")
    if t["priorite"] >= 2:
        r.append("priorité " + ("urgente" if t["priorite"] >= 3 else "haute"))
    if t["projet"]:
        r.append("projet en cours")
    r.append("premier temps libre assez long (%d min)" % (creneau[1] - creneau[0]))
    return ", ".join(r)


def _tache(x):
    if not isinstance(x, dict) or isinstance(x.get("id"), bool) or not isinstance(x.get("id"), int):
        return None
    return {"id": x["id"], "titre": str(x.get("titre") or "Sans titre")[:120],
            "duree": max(DUREE_MIN, min(DUREE_MAX, _entier(x.get("duree"), DUREE_DEFAUT) or DUREE_DEFAUT)),
            "retard": max(0, _entier(x.get("retard"))), "priorite": max(0, min(3, _entier(x.get("priorite"), 1))),
            "echeance_jour": bool(x.get("echeance_jour")), "projet": bool(x.get("projet"))}


def suggestions_plan(entree):
    e = entree if isinstance(entree, dict) else {}
    f = e.get("fenetre") if isinstance(e.get("fenetre"), dict) else {}
    fenetre = (_entier(f.get("debut")), _entier(f.get("fin")))
    maintenant = e.get("maintenant")
    maintenant = None if isinstance(maintenant, bool) or not isinstance(maintenant, (int, float)) else int(maintenant)
    occupes = []
    for o in (e.get("occupes") or []):
        if isinstance(o, (list, tuple)) and len(o) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in o):
            occupes.append((int(o[0]), int(o[1])))
    marge = max(0, min(30, _entier(e.get("marge"), MARGE)))
    maxi = max(1, min(MAX_SUGGESTIONS, _entier(e.get("max"), 5)))
    taches, vus = [], set()
    for x in (e.get("taches") or []):
        t = _tache(x)
        if t and t["id"] not in vus:
            vus.add(t["id"])
            taches.append(t)
    if fenetre[1] <= fenetre[0]:
        return {"suggestions": [], "non_places": [{"tache": t["id"], "raison": "journée sans plage"} for t in taches], "creneaux_libres": []}
    libres = _libres(fenetre, maintenant, occupes)
    restant = list(libres)
    suggestions, non_places = [], []
    for t in sorted(taches, key=lambda t: (-_score(t), -t["duree"], t["id"])):
        if len(suggestions) >= maxi:
            non_places.append({"tache": t["id"], "raison": "au-delà des %d propositions" % maxi})
            continue
        place = next(((i, c) for i, c in enumerate(restant) if _arrondi(c[0]) + t["duree"] <= c[1]), None)      # l'heure se pose au multiple de cinq minutes
        if place is None:
            non_places.append({"tache": t["id"], "raison": "aucun temps libre assez long (%d min)" % t["duree"]})
            continue
        i, (a, b) = place
        deb = _arrondi(a)
        suite = deb + t["duree"] + marge
        restant[i:i + 1] = [(suite, b)] if b - suite >= PAS else []
        suggestions.append({"tache": t["id"], "titre": t["titre"], "deb": deb, "duree": t["duree"], "score": _score(t), "raison": _raison(t, (a, b))})
    suggestions.sort(key=lambda s: (s["deb"], s["tache"]))
    return {"suggestions": suggestions, "non_places": non_places, "creneaux_libres": [list(c) for c in libres]}


def point_suggestions_plan(entree):
    """Le point d'évolution `suggestions_plan` (contrat 1.0)."""
    return {"valeur": suggestions_plan(entree)}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_suggestions_plan(entree)` est le point d'évolution. Il décide de l'ordre et de l'heure des suggestions ; il ne peut ni changer la forme de la sortie, ni proposer une tâche absente de la liste reçue,
#      ni empiéter sur ce qui est occupé, ni sur une autre suggestion, ni sortir de la fenêtre.
# CN : appelé par la façade `lire_suggestions_plan` du module (CN_module.py) par ctx.point ; le nexus lit pour le compte qui agit (jamais un autre) ses tâches, son agenda, son plan et sa fenêtre de journée,
#      et ne rend que ce que le point propose : placer une suggestion reste un geste du compte (modifier_plan).
# LIEN : contrat dans contrats/CN_suggestions_plan.json ; corpus doré dans contrats/CN_suggestions_plan.corpus.json.
