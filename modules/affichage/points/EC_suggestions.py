# ══════════════════════════════════════════════════════════════════════════
# TITRE      : Suggestions proactives de planification (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : affichage
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.1.0)  #suggestions
# HÔTE CN    : CN_module.py · suggestions_plan @1.0
# RÔLE       : Propose des placements optimaux de tâches dans les créneaux libres de la journée.
# MÉTHODE    : fonction pure : analyse les tâches non planifiées, les créneaux libres, et suggère les meilleures places.
# ══════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=suggestions_plan contrat=@1.0 version=EC0 empreinte=suggestions ▼▼▼

# Score de base pour une suggestion
SCORE_BASE = 50
# Bonus quand la tâche correspond à un projet en cours
BONUS_PROJET = 15
# Bonus pour une tâche urgente (échéance proche)
BONUS_URGENT = 20
# Pénalité pour une tâche longue dans un petit créneau
PENALITE_LONGUE = -10


def _trouver_libres(plan,events,debut,fin):
    """Retourne la liste des intervalles libres [(debut, fin), ...] entre debut et fin."""
    ocupes = []
    # les blocs du plan
    for b in (plan or []):
        d = max(b.get("deb", 0), debut)
        f = min(b.get("deb", 0) + b.get("duree", 30), fin)
        if d < f:
            ocupes.append((d, f))
    # les événements de l'agenda
    for e in (events or []):
        d = max(e.get("d", 0), debut)
        f = min(e.get("f", d + 30), fin)
        if d < f:
            ocupes.append((d, f))
    if not ocupes:
        return [(debut, fin)]
    # fusionner et trier
    ocupes.sort()
    fusion = [ocupes[0]]
    for d, f in ocupes[1:]:
        if d <= fusion[-1][1]:
            fusion[-1] = (fusion[-1][0], max(fusion[-1][1], f))
        else:
            fusion.append((d, f))
    # extraire les libres
    libres = []
    courant = debut
    for d, f in fusion:
        if courant < d:
            libres.append((courant, d))
        courant = max(courant, f)
    if courant < fin:
        libres.append((courant, fin))
    return libres


def _score_tache(tache, creneau, projet_en_cours):
    """Calcule le score d'une tâche dans un créneau donné."""
    score = SCORE_BASE
    duree = tache.get("duree", 30)
    taille_cr = creneau[1] - creneau[0]
    # pénalité si la tâche est plus longue que le créneau
    if duree > taille_cr:
        return None
    # bonus projet en cours
    if projet_en_cours and tache.get("projet"):
        score += BONUS_PROJET
    # bonus urgence (échéance proche)
    if tache.get("echeance"):
        score += BONUS_URGENT
    # pénalité tâche longue dans petit créneau
    if duree > 60 and taille_cr < 90:
        score += PENALITE_LONGUE
    # préférer le matin pour les tâches importantes
    if creneau[0] < 720:  # avant 12h
        score += 5
    return score


def suggestions_plan(entree):
    """Le point d'évolution `suggestions_plan` (contrat 1.0).

    Entrée :
        {
            "jours": "YYYY-MM-DD",
            "taches": [...],  # tâches non planifiées avec id, titre, duree, projet, echeance
            "plan": [...],    # blocs déjà planifiés {deb, duree, ...}
            "events": [...],  # événements Agenda {d, f, ...}
            "debut": 8,       # heure de début de la journée de travail
            "fin": 20,        # heure de fin
            "projets": [...], # ids des projets en cours
            "max": 5          # nombre max de suggestions
        }

    Sortie :
        {
            "suggestions": [
                {"tache": id, "titre": "...", "debut": minute, "duree": minute, "score": nombre, "raison": "..."},
                ...
            ],
            "creneaux_libres": [(debut, fin), ...]
        }
    """
    jour = entree.get("jours", "")
    taches = entree.get("taches", [])
    plan = entree.get("plan", [])
    events = entree.get("events", [])
    debut = int(entree.get("debut", 8) * 60)  # convertir en minutes
    fin = int(entree.get("fin", 20) * 60)
    projets = set(entree.get("projets", []))
    max_sug = max(1, min(int(entree.get("max", 5)), 10))

    # trouver les créneaux libres
    libres = _trouver_libres(plan, events, debut, fin)

    # calculer les suggestions
    suggestions = []
    for t in taches:
        for cr in libres:
            score = _score_tache(t, cr, t.get("projet") in projets)
            if score is not None:
                suggestions.append({
                    "tache": t.get("id"),
                    "titre": t.get("titre", "Sans titre"),
                    "debut": cr[0],
                    "duree": t.get("duree", 30),
                    "score": score,
                    "raison": _raison(t, cr, score)
                })
                break  # une suggestion par tâche (la meilleure position)

    # trier par score décroissant
    suggestions.sort(key=lambda x: -x["score"])

    return {
        "suggestions": suggestions[:max_sug],
        "creneaux_libres": libres
    }


def _raison(tache, creneau, score):
    """Génère une raison lisible pour la suggestion."""
    raisons = []
    if creneau[0] < 720:
        raisons.append("matin")
    if tache.get("projet"):
        raisons.append("projet en cours")
    if tache.get("echeance"):
        raisons.append("échéance proche")
    if not raisons:
        raisons.append("créneau libre")
    return ", ".join(raisons)


def point_suggestions_plan(entree):
    """Le point d'évolution `suggestions_plan` (contrat 1.0)."""
    return {"valeur": suggestions_plan(entree)}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_suggestions_plan(entree)` est le point d'évolution. Il analyse les tâches non planifiées,
#      calcule les créneaux libres de la journée, et suggère les meilleurs placements.
# CN : appelé par la façade `suggestions_plan` du module (CN_module.py) via ctx.point ;
#      le nexus fournit les tâches du compte, les événements, le plan existant et les projets en cours.
# LIEN : à définir (contrat, corpus).