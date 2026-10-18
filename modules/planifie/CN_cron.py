# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les tâches planifiées
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : planifie
# ZONE       : CN
# VERSION CN : 0.1.1  #e290c6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les tâches planifiées : la logique pure (expressions cron, occurrences, description en français, verdict d'une tâche, collisions, dérive).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=e290c6 ▼▼▼
"""Les tâches planifiées : la logique pure (expressions cron, occurrences, description en français, verdict d'une tâche, collisions, dérive).

Portée de la V18. Rien ici ne touche le système : le module lit et écrit les crontabs par le courtier, et passe les temps et les durées à ces fonctions.
"""
from __future__ import annotations

import hashlib
import os
import re
import shlex
from datetime import datetime, timedelta

JOURS_FR = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]
RACCOURCIS = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *", "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@hourly": "0 * * * *"}
WRAPPERS = {"sudo", "nohup", "command", "builtin", "exec", "stdbuf", "nice", "ionice", "time", "env", "setsid"}
WRAPPERS_UN_ARG = {"timeout"}
SEPARATEURS = {";", "|", "||", "&&", "&", "\n"}
LOURDES = re.compile(r"\b(mysqldump|pg_dump|rsync|tar|borg|restic|duplicity|gzip|bzip2|xz|zip|7z|dd|find|du|clamscan|freshclam|apt-get|apt|yum|dnf|certbot|ffmpeg|convert|composer|npm|docker)\b")
SAUVEGARDE = re.compile(r"\b(backup|sauvegarde|mysqldump|pg_dump|borg|restic|duplicity|rsync|dump)\b", re.I)
DESTRUCTEURS = [r"\brm\s+-[rf]", r"\bdd\s+if=", r"\bmkfs", r"\breboot\b", r"\bshutdown\b", r"\bsed\s+-i\b", r"\b(perl|python3?|ruby)\s+.*-i\b", r"\bchmod\b", r"\bchown\b",
                r"\btee\b", r"\bkill(all)?\b", r"\bpkill\b", r"\buserdel\b", r"\bmkswap\b", r"\biptables\b", r"\bsystemctl\s+(stop|disable|mask|restart)\b", r"\btruncate\b"]
DESTRUCTEURS_EN_PLUS = [
    (r">\s*/(etc|boot|usr|bin|sbin|lib|var/lib)/", "écriture dans une arborescence système"),
    (r"\b(curl|wget)\b[^|]*\|\s*(sudo\s+)?(ba)?sh\b", "exécution directe d'un contenu téléchargé"),
]
ETAT_ORDRE = {"cassé": 0, "échec": 1, "muet": 2, "inconnu": 3, "ok": 4, "désactivé": 5}


# ------------------------------------------------------------------ expressions
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


def occurrences(expr, du, au, max_par_jour=4):
    """Les exécutions d'une expression sur une plage. Jour par jour, jamais minute par minute (un `*/5` noierait le calendrier) : au-delà de `max_par_jour`, la première heure et un indicateur récurrent."""
    p = analyser(expr)
    if not p:
        return []
    mins, hours, jour_ok = p
    try:
        d, fin = datetime.strptime(du[:10], "%Y-%m-%d"), datetime.strptime(au[:10], "%Y-%m-%d")
    except Exception:
        return []
    out = []
    while d <= fin and len(out) < 400:
        if jour_ok(d):
            heures = sorted((h, m) for h in hours for m in mins)
            if len(heures) > max_par_jour:
                out.append({"at": "%s %02d:%02d" % (d.strftime("%Y-%m-%d"), *heures[0]), "recurrent": len(heures)})
            else:
                out += [{"at": "%s %02d:%02d" % (d.strftime("%Y-%m-%d"), h, m), "recurrent": 0} for h, m in heures]
        d += timedelta(days=1)
    return out


def decrire(expr, appeler):
    """L'expression en français lisible. Au moindre doute, l'expression d'origine plutôt qu'une paraphrase fausse. Le calcul est un POINT D'ÉVOLUTION : points/EC_decrire.py."""
    return appeler("decrire", {"expr": expr})["texte"]


def precedente(expr, ref, retour_jours=21):
    """La dernière exécution ATTENDUE à `ref` ou avant : la référence contre laquelle se mesure le silence."""
    p = analyser(expr)
    if not p:
        return ""
    mins, hours, jour_ok = p
    try:
        d = datetime.strptime(ref[:16], "%Y-%m-%d %H:%M")
    except Exception:
        return ""
    jour = d.replace(hour=0, minute=0)
    for i in range(retour_jours + 1):
        if jour_ok(jour):
            for h in reversed(hours):
                if i == 0 and h > d.hour:
                    continue
                for m in reversed(mins):
                    if i == 0 and h == d.hour and m > d.minute:
                        continue
                    return "%s %02d:%02d" % (jour.strftime("%Y-%m-%d"), h, m)
        jour -= timedelta(days=1)
    return ""


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


def apercu(expr, ref, appeler, n=5):
    """Les prochaines exécutions, pour vérifier AVANT d'enregistrer : `0 5 * * 7` et `0 5 7 * *` se ressemblent et ne veulent pas du tout dire la même chose. Le calcul est un POINT D'ÉVOLUTION : points/EC_apercu.py."""
    return appeler("apercu", {"expr": expr, "ref": ref, "n": n})["valeur"]


def intervalle_min(expr, ref):
    """Les minutes entre deux occurrences, ou 0 si ce n'est pas régulier."""
    a = suivante(expr, ref)
    b = suivante(expr, a) if a else ""
    if not a or not b:
        return 0
    try:
        return int((datetime.strptime(b[:16], "%Y-%m-%d %H:%M") - datetime.strptime(a[:16], "%Y-%m-%d %H:%M")).total_seconds() // 60)
    except Exception:
        return 0


def reference(user, commande):
    """L'identifiant stable d'une tâche : son propriétaire et sa commande (les identifiants numériques diffèrent d'une source à l'autre)."""
    return hashlib.sha1(("%s|%s" % ((user or "").strip(), (commande or "").strip()[:300])).encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------ la commande
def segments(cmd):
    """Une commande shell découpée en segments ; None si elle n'est pas analysable (l'appelant la traite alors avec prudence)."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        tokens = list(lexer)
    except ValueError:
        return None
    segs, cur = [], []
    for t in tokens:
        if t in SEPARATEURS:
            segs.append(cur)
            cur = []
        else:
            cur.append(t)
    segs.append(cur)
    return [s for s in segs if s]


def cibles(commande):
    """Les exécutables invoqués par une commande planifiée, chemin complet conservé."""
    segs = segments(commande or "")
    if segs is None:
        return []
    out = []
    for tokens in segs:
        i = 0
        while i < len(tokens):
            t = tokens[i]
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", t):
                i += 1
            elif t in WRAPPERS:
                i += 1
            elif t in WRAPPERS_UN_ARG:
                i += 2
            else:
                break
        if i < len(tokens) and tokens[i]:
            out.append(tokens[i])
    return out


def cibles_manquantes(commande, existe=None, est_executable=None, trouver=None):
    """Les cibles introuvables ou non exécutables parmi celles qu'on sait vérifier. Aveugle à tout ce qui est ambigu (chemin relatif, variable, substitution) : accuser à tort un cron qui marche ferait perdre sa crédibilité à la liste."""
    import shutil
    existe = existe or os.path.isfile
    est_executable = est_executable or (lambda p: os.access(p, os.X_OK))
    trouver = trouver or shutil.which
    manque = []
    for t in cibles(commande):
        if "$" in t or "*" in t or t.startswith("~"):
            continue
        if t.startswith("/"):
            if not (existe(t) and est_executable(t)):
                manque.append(t)
        elif "/" not in t and trouver(t) is None:
            manque.append(t)
    return manque


def destructeur(commande):
    """Le motif destructeur reconnu dans la commande, ou « ». On ne demande confirmation que sur ce qui détruit vraiment : un avertissement qui s'affiche à chaque enregistrement n'avertit plus de rien."""
    cmd = (commande or "").strip()
    for pat in DESTRUCTEURS:
        if re.search(pat, cmd):
            return "motif destructeur : %s" % pat.replace(r"\b", "").replace("\\s+", " ")
    for pat, libelle in DESTRUCTEURS_EN_PLUS:
        if re.search(pat, cmd):
            return libelle
    return ""


def valider(expr, commande):
    """Refuse ce qui ne tournerait pas, ou tournerait n'importe quand. -> (ok, expression normalisée | raison)"""
    e, cmd = normaliser(expr), (commande or "").strip()
    if not cmd:
        return False, "commande vide"
    if e.lower() != "@reboot":
        if len(e.split()) != 5:
            return False, "expression cron invalide (%d champs, 5 requis)" % len(e.split())
        if not analyser(e):
            return False, "expression cron illisible : aucune exécution ne correspond à « %s »" % expr
    if "\n" in cmd or "%" in cmd.replace("\\%", ""):
        return False, "le caractère % doit être échappé (\\%) dans une crontab : cron coupe la commande au premier % non échappé"
    return True, e


# ------------------------------------------------------------------ le verdict
def etat(job, maintenant):
    """Muet, ok, échec, cassé, inconnu ou désactivé. « Inconnu » est un état à part entière : sans donnée d'exécution on ne peut rien affirmer, et prétendre le contraire masquerait les pannes qu'on cherche."""
    if not job.get("actif"):
        return "désactivé", "cron désactivé"
    manque = job.get("cibles_manquantes") or []
    if manque:                                            # avant le silence : le cron se déclenche, le journal enregistre une exécution, il paraît « ok » — et ne fait rien
        return "cassé", "introuvable ou non exécutable : %s" % ", ".join(manque[:3])
    code = job.get("dernier_code")
    if code is not None and code != 0:
        return "échec", "dernière exécution en échec (code %s) le %s" % (code, job.get("derniere") or "?")
    expr = job.get("horaire") or ""
    if normaliser(expr).lower() == "@reboot":
        return "inconnu", "déclenché au démarrage, non projetable"
    prev = job.get("attendue_avant") or ""
    if not prev:
        return "inconnu", "planning illisible ou aucune exécution attendue récemment"
    last = (job.get("derniere") or "").strip()[:16].replace("T", " ")
    if not last:
        return "inconnu", "aucune trace d'exécution dans le journal"
    try:                                                  # marge d'UNE occurrence : un créneau manquant ne prouve rien (la collecte a pu passer juste avant), deux ne s'expliquent plus par le décalage
        avant = (datetime.strptime(prev[:16], "%Y-%m-%d %H:%M") - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M")
        tol = precedente(expr, avant) or prev
    except Exception:
        tol = prev
    if last >= tol:
        return "ok", "dernière exécution le %s" % last
    try:
        retard = int((datetime.strptime(prev[:16], "%Y-%m-%d %H:%M") - datetime.strptime(last[:16], "%Y-%m-%d %H:%M")).total_seconds() // 3600)
    except Exception:
        retard = 0
    return "muet", "attendu le %s, dernière trace le %s (%dh de retard)" % (prev, last, retard)


def collisions(jobs, appeler, seuil=3):
    """Les créneaux où trop de tâches LOURDES démarrent ensemble : elles se disputent le disque et le processeur au même instant, chacune s'allonge, la fenêtre de nuit déborde. Trois `echo` à la même minute n'ont jamais posé de problème. Le calcul est un POINT D'ÉVOLUTION : points/EC_collisions.py."""
    return appeler("collisions", {"jobs": jobs, "seuil": seuil})["valeur"]


def repartir(collision):
    """Répartit les tâches d'un créneau saturé sur des minutes distinctes : on décale les minutes, jamais l'heure (une sauvegarde à 3 h a été placée là pour la fenêtre creuse)."""
    try:
        h, m = [int(x) for x in collision["at"].split(":")]
    except Exception:
        return []
    return [{"ref": t["ref"], "libelle": t["libelle"], "at": "%02d:%02d" % ((h + (m + i * 10) // 60) % 24, (m + i * 10) % 60)} for i, t in enumerate(collision.get("taches", []))]


def derive(durees, appeler, mini=8):
    """Compare le premier tiers des durées au dernier : une moyenne globale masquerait la pente. Une tâche qui ne tombe jamais en erreur mais met trois fois plus de temps qu'il y a trois semaines. Le calcul est un POINT D'ÉVOLUTION : points/EC_derive.py."""
    return appeler("derive", {"durees": durees, "mini": mini})["valeur"]


def boucle(ref, apres, suivants, appeler):
    """Deux tâches qui s'attendent l'une l'autre ne partiraient jamais, et rien ne le dirait. `suivants` : ref -> ref qu'elle attend. Le calcul est un POINT D'ÉVOLUTION : points/EC_boucle.py."""
    return appeler("boucle", {"ref": ref, "apres": apres, "suivants": suivants})["valeur"]
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : champ, normaliser, analyser, occurrences, decrire, precedente, suivante, apercu …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
