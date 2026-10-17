# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Planifie : description d'une expression cron (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #aa2e31
# HÔTE CN    : CN_module.py · decrire @1.0
# RÔLE       : dit en français ce que planifie une expression cron.
# MÉTHODE    : fonction pure : les raccourcis sont ramenés à cinq champs, chaque champ est développé, puis une phrase est composée ; au moindre doute, l'expression d'origine est rendue plutôt qu'une paraphrase fausse.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=decrire contrat=@1.0 version=EC0 empreinte=aa2e31 ▼▼▼

JOURS_FR = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]

RACCOURCIS = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *"}

def champ(spec, bas, haut):
    """Développe un champ cron en ensemble de valeurs (`*`, `a`, `a-b`, `a,b,c`, `*/n`, `a-b/n`). Ensemble vide si le champ est illisible : le cron est alors non projetable plutôt que d'inventer des exécutions."""
    spec = (spec or "").strip()
    if not spec:
        return set()
    out = set()
    for part in spec.split(","):
        part = part.strip()
        pas = 1
        if "/" in part:
            part, _, s = part.partition("/")
            try:
                pas = max(1, int(s))
            except ValueError:
                return set()
        if part in ("*", ""):
            a, b = bas, haut
        elif "-" in part:
            try:
                a, b = [int(x) for x in part.split("-", 1)]
            except ValueError:
                return set()
        else:
            try:
                a = b = int(part)
            except ValueError:
                return set()
        if a > b or a < bas or b > haut:
            return set()
        out.update(range(a, b + 1, pas))
    return out

def normaliser(expr):
    """Ramène `@daily` & co. à cinq champs. `@reboot` reste tel quel (non projetable)."""
    e = (expr or "").strip()
    return RACCOURCIS.get(e.lower(), e)

def decrire(expr):
    """L'expression en français lisible. Au moindre doute, l'expression d'origine plutôt qu'une paraphrase fausse."""
    e = normaliser(expr)
    if e.lower() == "@reboot":
        return "à chaque démarrage"
    f = e.split()
    if len(f) != 5:
        return e
    mi, ho, dom, mon, dow = f
    tous = lambda s: s.strip() in ("*", "")

    def pas(s):
        if s.startswith("*/"):
            try:
                return int(s[2:])
            except ValueError:
                return 0
        return 0
    jours = ""
    if not tous(dow):
        d = champ(dow, 0, 7)
        if d:
            noms = sorted({JOURS_FR[0 if x == 7 else x] for x in d})
            jours = " le " + ", ".join(noms) if len(noms) < 7 else ""
    if not tous(dom):
        jours += " le %s du mois" % dom
    if not tous(mon):
        jours += " (mois %s)" % mon
    smi, sho = pas(mi), pas(ho)
    if smi and tous(ho):
        return ("toutes les %d minutes" % smi) + jours
    if sho and mi.isdigit():
        return ("toutes les %d heures (à H+%s)" % (sho, mi)) + jours
    if tous(mi) and tous(ho):
        return "chaque minute" + jours
    if mi.isdigit() and tous(ho):
        return ("à la minute %s de chaque heure" % mi) + jours
    if mi.isdigit() and ho.isdigit():
        base = "à %02d:%02d" % (int(ho), int(mi))
        return (base + jours) if jours else base + " chaque jour"
    return e

def point_decrire(entree):
    """Le point d'évolution `decrire` (contrat 1.0)."""
    return {"texte": decrire(entree["expr"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_decrire(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de planifie (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_decrire.json ; corpus doré dans contrats/CN_decrire.corpus.json (sorties de l'ancien code, données synthétiques).
