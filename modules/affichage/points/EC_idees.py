# ══════════════════════════════════════════════════════════════════
# TITRE      : Affichage : les idées du panneau conversationnel (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : affichage
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.4.0)  #d007c4
# HÔTE CN    : CN_module.py · idees @1.0
# RÔLE       : classe, pour la page où l'on est et l'interlocuteur du panneau, au plus quelques idées : ce qui brûle d'abord, ce qui touche la page ensuite, chacune avec sa raison.
# MÉTHODE    : fonction pure : les alertes du jour reçues en entrée, l'heure, ce qui vient d'être fait ou refusé ; un geste n'est proposé que s'il figure dans la liste que le nexus transmet, jamais inventé.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=idees contrat=@1.0 version=EC0 empreinte=d007c4 ▼▼▼

BASE = {"brule": 100, "regarder": 60, "jour": 45}
SEUIL_URGENT = 85
MAX_IDEES = 8
OU_ENTREE = {"sites": "sites", "ssl": "sites", "bureau": "accueil", "mail": "accueil", "cloche": "accueil", "proj": "accueil", "securite": "securite",
             "evolution": "evolution", "flotte": "flotte", "fleet": "flotte", "sensorium": "sensorium", "journal": "journaux", "crons": "automatismes",
             "planifie": "automatismes", "memoire": "memoire", "proactif": "proactivite", "fastpanel": "hebergement", "vue": "panorama",
             "tache": "accueil", "rappel": "accueil", "event": "accueil", "decision": "accueil", "mandat": "accueil", "note": "accueil"}


def _txt(v, n):
    return str(v or "")[:n]


def _une(idees, i):
    """Un id, un seul : la meilleure des idées qui le portent."""
    if i["id"] not in idees or idees[i["id"]]["score"] < i["score"]:
        idees[i["id"]] = i


def idees(contexte, items, actes, max_idees):
    c = contexte if isinstance(contexte, dict) else {}
    mode = "cassandra" if c.get("mode") == "cassandra" else "itare"
    entree = _txt(c.get("entree"), 40)
    heure = int(c.get("heure") or 12) % 24
    page = _txt(c.get("page"), 80)
    sortie = {}
    par_nat = {}
    for a in actes or []:
        if isinstance(a, dict) and a.get("id") and a.get("nat") and a.get("qui", mode) == mode:
            par_nat.setdefault(a["nat"], []).append(a)
    for x in items or []:
        if not isinstance(x, dict) or x.get("bande") not in BASE:
            continue
        local = OU_ENTREE.get(x.get("ou") or "", OU_ENTREE.get(x.get("quoi") or "", "")) == entree and entree != ""
        score = BASE[x["bande"]] + min(int(x.get("poids") or 0), 200) // 10 + (12 if local else 0)
        score = min(score, 140)
        raison = _txt(x.get("detail") or x.get("titre"), 100)
        cle = _txt(x.get("ref") or x.get("titre"), 40)
        propose = False
        for a in par_nat.get(x.get("nat") or "", []):
            if a.get("etat") == "refuse":
                continue
            propose = True
            if a.get("etat") == "fait":
                _une(sortie, {"id": "s:%s:%s" % (a["id"], cle), "titre": "Le geste « %s » a-t-il pris effet ?" % _txt(a.get("titre"), 60), "raison": "geste fait à l’instant",
                              "score": 66, "genre": "question", "acte": "", "cible": ""})
            else:
                _une(sortie, {"id": "a:%s:%s" % (a["id"], cle), "titre": _txt(a.get("titre"), 90) + ((" : " + cle) if cle else ""), "raison": raison,
                              "score": score + 2, "genre": "acte", "acte": a["id"], "cible": _txt(x.get("ref"), 80), "risque": _txt(a.get("risque"), 10)})
        if not propose:
            _une(sortie, {"id": "q:%s:%s" % (x.get("quoi") or "", cle), "titre": "Que faire de : %s" % _txt(x.get("titre"), 90), "raison": raison, "score": score,
                          "genre": "question", "acte": "", "cible": ""})
    if mode == "itare":
        if heure < 12:
            _une(sortie, {"id": "h:matin", "titre": "Résumer ma journée", "raison": "ce matin", "score": 45, "genre": "question", "acte": "", "cible": ""})
        elif heure >= 17:
            _une(sortie, {"id": "h:soir", "titre": "Qu’est-ce qui reste à faire avant demain ?", "raison": "fin de journée", "score": 45, "genre": "question", "acte": "", "cible": ""})
        else:
            _une(sortie, {"id": "h:jour", "titre": "Résumer ma journée", "raison": "", "score": 30, "genre": "question", "acte": "", "cible": ""})
    else:
        if heure < 12:
            _une(sortie, {"id": "h:nuit", "titre": "Qu’est-ce qui a changé cette nuit ?", "raison": "ce matin", "score": 45, "genre": "question", "acte": "", "cible": ""})
        else:
            _une(sortie, {"id": "h:parc", "titre": "Où en est le parc ?", "raison": "", "score": 25, "genre": "question", "acte": "", "cible": ""})
    _une(sortie, {"id": "p:page", "titre": "Résume cette page", "raison": page, "score": 8, "genre": "question", "acte": "", "cible": ""})
    n = max(1, min(MAX_IDEES, int(max_idees or 4)))
    classees = sorted(sortie.values(), key=lambda i: (-i["score"], i["id"]))[:n]
    return {"idees": classees, "urgent": any(i["score"] >= SEUIL_URGENT for i in classees)}


def point_idees(entree):
    """Le point d'évolution `idees` (contrat 1.0)."""
    return {"valeur": idees(entree.get("contexte", {}), entree.get("items", []), entree.get("actes", []), entree.get("max", 4))}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_idees(entree)` est le point d'évolution. Il décide de l'ordre et du texte des idées ; il ne peut changer ni la signature, ni la forme de la sortie,
#      ni proposer un geste absent de la liste reçue, ni une idée sans raison pour une alerte.
# CN : appelée par la façade `idees` du module (CN_module.py) par ctx.point ; le nexus fournit les alertes du compte (jamais celles d'un autre), la liste des gestes que le compte peut accomplir, et refait lui-même toute vérification de droit à l'exécution.
# LIEN : contrat dans contrats/CN_idees.json ; corpus doré dans contrats/CN_idees.corpus.json.
