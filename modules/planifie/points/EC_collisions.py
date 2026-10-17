# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Planifie : collisions de tâches lourdes (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #5529f8
# HÔTE CN    : CN_module.py · collisions @1.0
# RÔLE       : repère les minutes où plusieurs tâches lourdes (sauvegardes, archives, mises à jour) démarrent ensemble et se disputent le disque et le processeur.
# MÉTHODE    : fonction pure : chaque tâche lourde et active est projetée sur ses minutes de départ (une tâche diffuse, plus de quatre départs, est écartée) ; un créneau est en collision au seuil donné (deux au minimum).
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=collisions contrat=@1.0 version=EC0 empreinte=5529f8 ▼▼▼
import re

RACCOURCIS = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *"}

LOURDES = re.compile(r"\b(mysqldump|pg_dump|rsync|tar|borg|restic|duplicity|gzip|bzip2|xz|zip|7z|dd|find|du|clamscan|freshclam|apt-get|apt|yum|dnf|certbot|ffmpeg|convert|composer|npm|docker)\b")

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

def collisions(jobs, seuil=3):
    """Les créneaux où trop de tâches LOURDES démarrent ensemble : elles se disputent le disque et le processeur au même instant, chacune s'allonge, la fenêtre de nuit déborde. Trois `echo` à la même minute n'ont jamais posé de problème."""
    par = {}
    for j in jobs:
        if not j.get("actif") or not LOURDES.search(j.get("commande") or ""):
            continue
        p = analyser(j.get("horaire") or "")
        if not p:
            continue
        mins, hours, _ = p
        if len(mins) * len(hours) > 4:                    # une tâche qui part plusieurs fois par heure est diffuse par nature
            continue
        for h in hours:
            for m in mins:
                par.setdefault("%02d:%02d" % (h, m), []).append(j)
    out = [{"at": c, "nombre": len(lot), "taches": [{"ref": x["ref"], "libelle": (x.get("description") or x.get("commande") or "")[:80], "id": x.get("id")} for x in lot]}
           for c, lot in sorted(par.items()) if len(lot) >= max(2, int(seuil))]
    out.sort(key=lambda x: -x["nombre"])
    return out

def point_collisions(entree):
    """Le point d'évolution `collisions` (contrat 1.0)."""
    return {"valeur": collisions(entree["jobs"], entree["seuil"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_collisions(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de planifie (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_collisions.json ; corpus doré dans contrats/CN_collisions.corpus.json (sorties de l'ancien code, données synthétiques).
