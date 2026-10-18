# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Planifie : La prochaine exécution attendue, strictement après `ref` (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #6bcade
# HÔTE CN    : CN_module.py · suivante @1.0
# RÔLE       : La prochaine exécution attendue, strictement après `ref`.
# MÉTHODE    : fonction pure extraite automatiquement du nexus : la fermeture est copiée mot pour mot ; le corpus vient des appels littéraux du dépôt et d'une synthèse par type.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=suivante contrat=@1.0 version=EC0 empreinte=6bcade ▼▼▼
from datetime import datetime, timedelta

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

def analyser(expr):
    """(minutes, heures, prédicat_de_jour) ou None. Les recherches d'occurrence en ont besoin sans le plafond de 400 entrées du calendrier."""
    f = normaliser(expr).split()
    if len(f) != 5:
        return None
    mins, hours, doms, months, dows = champ(f[0], 0, 59), champ(f[1], 0, 23), champ(f[2], 1, 31), champ(f[3], 1, 12), champ(f[4], 0, 7)
    if not (mins and hours and doms and months and dows):
        return None
    dows = {0 if x == 7 else x for x in dows}
    dom_tous = champ("*", 1, 31) == doms
    dow_tous = {0, 1, 2, 3, 4, 5, 6} <= dows

    def jour_ok(d):
        if d.month not in months:
            return False
        dow = (d.weekday() + 1) % 7
        if dom_tous and dow_tous:
            return True
        if dom_tous:
            return dow in dows
        if dow_tous:
            return d.day in doms
        return (d.day in doms) or (dow in dows)          # union POSIX : si le jour du mois ET le jour de la semaine sont restreints, l'UN des deux suffit
    return sorted(mins), sorted(hours), jour_ok

def suivante(expr, ref, avance_jours=45):
    """La prochaine exécution attendue, strictement après `ref`."""
    p = analyser(expr)
    if not p:
        return ""
    mins, hours, jour_ok = p
    try:
        d = datetime.strptime(ref[:16], "%Y-%m-%d %H:%M")
    except Exception:
        return ""
    jour = d.replace(hour=0, minute=0)
    for i in range(avance_jours + 1):
        if jour_ok(jour):
            for h in hours:
                if i == 0 and h < d.hour:
                    continue
                for m in mins:
                    if i == 0 and h == d.hour and m <= d.minute:
                        continue
                    return "%s %02d:%02d" % (jour.strftime("%Y-%m-%d"), h, m)
        jour += timedelta(days=1)
    return ""

def point_suivante(entree):
    """Le point d'évolution `suivante` (contrat 1.0)."""
    return {"valeur": suivante(entree["expr"], entree["ref"], entree["avance_jours"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_suivante(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de planifie (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_suivante.json ; corpus doré dans contrats/CN_suivante.corpus.json (sorties de l'ancien code, données synthétiques).
