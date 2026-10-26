# ══════════════════════════════════════════════════════════════════
# TITRE      : Affichage : la disposition des menus (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : affichage
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.7.0)  #663330
# HÔTE CN    : CN_module.py · disposition @1.0
# RÔLE       : range les entrées de menu que les modules déclarent en groupes (barre du haut), entrées et sous-entrées (colonne de gauche), et en entrées du menu de l'avatar ; dit le pire niveau d'alerte de chaque entrée, de chaque groupe et du tout.
# MÉTHODE    : fonction pure : une table de groupes, un repli par famille, un pont vers les onglets de l'ancienne interface ; chaque entrée reçue paraît une seule fois, rien n'est inventé, un groupe sans entrée n'existe pas.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=disposition contrat=@1.0 version=EC0 empreinte=663330 ▼▼▼

# Les groupes de la barre du haut : (id, libellé, icône, ordre, interlocuteur par défaut du panneau).
GROUPES = (
    ("desk", "Desk", "desk", 10, "itare"),
    ("metier", "Métier", "chart", 20, "cassandra"),
    ("parc", "Parc", "fleet", 30, "cassandra"),
    ("secu", "Sécurité", "shield", 40, "cassandra"),
    ("obs", "Observatoire", "eye", 50, "cassandra"),
    ("auto", "Autonomie", "spark", 60, "cassandra"),
    ("modules", "Modules", "puzzle", 90, "cassandra"),
)
GROUPE_REPLI = "modules"
MAX_GROUPES = 7

# Un module qui ne dit pas son groupe est rangé selon sa famille ; une famille inconnue va au groupe de repli.
REPLI_FAMILLE = {"securite": "secu", "supervision": "obs", "reseau": "parc", "hebergement": "parc", "sites": "parc", "systeme": "parc",
                 "flotte": "parc", "evolution": "auto", "agents": "auto", "echanges": "desk", "communication": "desk", "travail": "desk",
                 "gestion": "metier", "finance": "metier"}

# Les modules dont la page n'est plus une entrée : le salon vit dans le panneau conversationnel.
MASQUES = ("salon",)

# Le pont vers l'ancienne interface : ce que ses onglets offrent déjà. Une entrée du pont paraît si les modules dont elle dépend sont actifs,
# et elle remplace l'entrée qu'un module déclarerait pour le même module (l'écran de l'ancienne interface existe, il fait foi).
PONT = (
    {"id": "accueil", "libelle": "Aujourd’hui", "groupe": "desk", "icone": "clock", "onglet": "bureau", "modules": (), "ordre": 10, "role": "utilisateur", "vues": ()},
    {"id": "agenda", "libelle": "Agenda", "groupe": "desk", "icone": "calendar", "onglet": "bureau", "modules": (), "ordre": 20, "role": "utilisateur",
     "vues": (("calendrier", "Calendrier"), ("taches", "Tâches"), ("rappels", "Rappels"))},
    {"id": "projets", "libelle": "Projets", "groupe": "desk", "icone": "panorama", "onglet": "bureau", "modules": (), "ordre": 30, "role": "utilisateur", "vues": ()},
    {"id": "notes", "libelle": "Notes", "groupe": "desk", "icone": "scroll", "onglet": "bureau", "modules": (), "ordre": 40, "role": "utilisateur", "vues": ()},
    {"id": "courrier", "libelle": "Courrier", "groupe": "desk", "icone": "mail", "onglet": "bureau", "modules": (), "ordre": 50, "role": "utilisateur", "vues": ()},
    {"id": "repertoire", "libelle": "Répertoire", "groupe": "desk", "icone": "contacts", "onglet": "bureau", "modules": (), "ordre": 60, "role": "utilisateur", "vues": ()},
    {"id": "documents", "libelle": "Documents", "groupe": "desk", "icone": "folder", "onglet": "bureau", "modules": (), "ordre": 70, "role": "utilisateur", "vues": ()},
    {"id": "panorama", "libelle": "Panorama", "groupe": "parc", "icone": "panorama", "onglet": "overview", "modules": ("vue",), "ordre": 10, "role": "admin", "vues": (
        ("verdict", "Le verdict"),
        ("gestes", "Ce qui demande un geste"),
        ("cass", "Cassandra, maintenant"),
        ("sites", "Les sites"),
        ("flotte", "La flotte"),
        ("fil", "Ce qui a changé"),
        ("machine", "La machine"),
        ("systeme", "Détails système")
    )},
    {"id": "securite", "libelle": "Sécurité", "groupe": "secu", "icone": "shield", "onglet": "securite", "modules": ("securite",), "ordre": 10, "role": "admin", "vues": ()},
    {"id": "evolution", "libelle": "Évolution", "groupe": "auto", "icone": "evo", "onglet": "evolution", "modules": ("evolution",), "ordre": 10, "role": "admin", "vues": ()},
    {"id": "proactivite", "libelle": "Proactivité", "groupe": "auto", "icone": "bolt", "onglet": "proactive", "modules": ("proactif",), "ordre": 20, "role": "admin", "vues": ()},
    {"id": "memoire", "libelle": "Mémoire", "groupe": "auto", "icone": "brain", "onglet": "memory", "modules": ("memoire",), "ordre": 30, "role": "utilisateur", "vues": ()},
)

# D'où vient une alerte du jour : le champ « ou » de l'item, ou à défaut son genre, rangé vers l'entrée qui la porte.
OU_VERS = {"sites": "sites:sites", "ssl": "sites:sites", "bureau": "accueil", "mail": "courrier", "cloche": "accueil", "proj": "projets", "securite": "securite",
           "evolution": "evolution", "flotte": "flotte:flotte", "fleet": "flotte:flotte", "sensorium": "sensorium:sensorium", "journal": "journal:journal", "crons": "planifie:taches",
           "planifie": "planifie:taches", "memoire": "memoire", "proactif": "proactivite", "fastpanel": "fastpanel:hebergement", "vue": "panorama",
           "tache": "agenda", "rappel": "agenda", "event": "agenda", "decision": "projets", "mandat": "accueil", "note": "notes"}
NIVEAUX = {"brule": "danger", "regarder": "alerte"}
RANG = {"": 0, "alerte": 1, "danger": 2}


def _cle(e):
    return (e["ordre"], e["libelle"].lower(), e["id"])


def _pire(a, b):
    return a if RANG[a] >= RANG[b] else b


def _entier(v, defaut=0):
    try:
        return max(0, min(9999, int(v)))
    except (TypeError, ValueError):
        return defaut


def _entree(brut, badges, niveaux):
    """Une entrée rangée : ce que l'interface a besoin de savoir, rien de plus."""
    n = _entier(badges.get(brut["id"], 0))
    niv = niveaux.get(brut["id"], "") if niveaux.get(brut["id"], "") in RANG else ""
    return {"id": brut["id"], "libelle": brut["libelle"], "icone": brut.get("icone", ""), "module": brut.get("module", ""), "ecran": brut.get("ecran", ""),
            "onglet": brut.get("onglet", ""), "vue": brut.get("vue", ""), "role": brut.get("role", "utilisateur"), "droit": brut.get("droit", ""),
            "ordre": _entier(brut.get("ordre", 100), 100), "badge": {"n": n, "niveau": niv}, "enfants": []}


def _groupe_de(brut, existants):
    g = brut.get("groupe", "")
    if g in existants:
        return g
    g = REPLI_FAMILLE.get(str(brut.get("famille", "")).lower(), GROUPE_REPLI)
    return g if g in existants else GROUPE_REPLI


def _niveaux_depuis(signaux):
    """Le pire niveau par entrée, d'après les alertes du jour : {ou: {"brule": n, "regarder": n}} -> {entrée: niveau}."""
    out = {}
    for ou, compte in sorted((signaux or {}).items()):
        cible = OU_VERS.get(ou)
        if not cible or not isinstance(compte, dict):
            continue
        for bande, niv in NIVEAUX.items():
            if _entier(compte.get(bande, 0)) > 0:
                out[cible] = _pire(out.get(cible, ""), niv)
    return out


def disposition(entrees, modules, badges, signaux):
    actifs = set(modules or [])
    existants = {g[0] for g in GROUPES}
    niveaux = _niveaux_depuis(signaux)
    badges = badges or {}
    couverts = set()
    for p in PONT:
        if all(m in actifs for m in p["modules"]):
            couverts.update(p["modules"])
    entrees = [e for e in (entrees or []) if isinstance(e, dict) and e.get("id") and e.get("libelle") and e.get("module") not in MASQUES]
    # les entrées déclarées par les modules, rangées ; celles dont le pont couvre le module cèdent la place
    declarees = [e for e in entrees if e["module"] not in couverts]
    ponts = []
    for p in PONT:
        if not all(m in actifs for m in p["modules"]):
            continue
        brut = dict(p, module=p["modules"][0] if p["modules"] else "", ecran="")
        ent = _entree(brut, badges, niveaux)
        for i, (vue, lib) in enumerate(p["vues"]):
            ent["enfants"].append({"id": "%s.%s" % (p["id"], vue), "libelle": lib, "icone": "", "module": ent["module"], "ecran": "", "onglet": p["onglet"], "vue": vue,
                                   "role": p["role"], "droit": "", "ordre": 10 * (i + 1), "badge": {"n": 0, "niveau": ""}, "enfants": []})
        ponts.append((p["groupe"], ent))
    par_id = {e["id"]: e for e in declarees}
    avatar, groupes = [], {}
    orphelines = []
    for e in sorted(declarees, key=_cle):
        if e.get("zone") == "avatar":
            avatar.append(_entree(e, badges, niveaux))
            continue
        parent = e.get("parent", "")
        if parent and parent in par_id and par_id[parent].get("zone") != "avatar":
            continue                                               # une sous-entrée : elle vient sous son parent
        g = _groupe_de(e, existants)
        if g == GROUPE_REPLI and e.get("groupe", "") not in existants:
            orphelines.append(e["id"])
        ent = _entree(e, badges, niveaux)
        for f in sorted((x for x in declarees if x.get("parent") == e["id"]), key=_cle):
            ent["enfants"].append(_entree(f, badges, niveaux))
        groupes.setdefault(g, []).append(ent)
    for g, ent in ponts:
        groupes.setdefault(g, []).append(ent)
    sortie, global_niv = [], ""
    for gid, lib, ico, ordre, interl in sorted(GROUPES, key=lambda g: (g[3], g[0])):
        xs = groupes.get(gid)
        if not xs:
            continue
        xs.sort(key=_cle)
        niv = ""
        for x in xs:
            niv = _pire(niv, x["badge"]["niveau"])
            for f in x["enfants"]:
                niv = _pire(niv, f["badge"]["niveau"])
        global_niv = _pire(global_niv, niv)
        sortie.append({"id": gid, "libelle": lib, "icone": ico, "ordre": ordre, "interlocuteur": interl, "niveau": niv, "entrees": xs})
    return {"groupes": sortie[:MAX_GROUPES], "avatar": avatar, "orphelines": sorted(orphelines), "niveau": global_niv or "ok"}


def point_disposition(entree):
    """Le point d'évolution `disposition` (contrat 1.0)."""
    return {"valeur": disposition(entree["entrees"], entree.get("modules", []), entree.get("badges", {}), entree.get("signaux", {}))}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_disposition(entree)` est le point d'évolution. Il décide de l'ordre, des regroupements, des libellés des groupes et du pont vers les onglets de l'ancienne interface ;
#      il ne peut changer ni la signature ni la forme de la sortie, ni les invariants du contrat (une entrée reçue paraît une seule fois, un groupe vide n'existe pas, le pire niveau remonte).
# CN : appelée par la façade `disposition` du module (CN_module.py) par ctx.point ; c'est le nexus qui ne lui transmet que les entrées que le compte a le droit de voir, et qui retire de la sortie ce que le rôle ou le droit ne permet pas.
# LIEN : contrat dans contrats/CN_disposition.json ; corpus doré dans contrats/CN_disposition.corpus.json.
