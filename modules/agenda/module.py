"""L'agenda.

Porté de la V18 (`itare_event_*`, `itare_reminder_*`, `itare_calendar_items`, `itare_agenda_list`, `ical_parse`, `rrule_expand`, `_caldav_*`), avec ses leçons :
  - il est à la PERSONNE : un identifiant deviné ne rend, ne modifie et n'efface rien de l'agenda d'un autre ; l'administrateur n'y voit rien ;
  - un fichier .ics réimporté met à jour au lieu de dupliquer (UID) ; une récurrence que le moteur ne sait pas développer est DITE, l'événement de base est gardé :
    perdre des occurrences en silence est le pire cas ;
  - une récurrence n'est plus développée en lignes à l'import : la règle est gardée avec l'événement et développée à la lecture, sur la plage demandée (sinon un
    quotidien vieux de trois ans tombait sous le plafond de 200 occurrences avant d'atteindre aujourd'hui) ; l'occurrence se calcule depuis le début de la série
    (un 31 janvier ramené au 28 février revient au 31 mars) ;
  - une panne CalDAV ne fait JAMAIS disparaître l'agenda local ; le mot de passe CalDAV est un réglage secret, jamais au journal ;
  - la vue temporelle unique rassemble ce qui tombe quand : une tâche en retard est collée à aujourd'hui (⚠), une tâche confiée à un autre n'est pas à mon agenda ;
  - un événement se relie à du contenu ET à de l'infrastructure ; un lien porte l'ÉTAT de ce qu'il désigne (« Claire Mercier », pas « contact:12 ») ;
  - le journal d'un événement dit ce qui a bougé (« Déplacé du 11 au 12 ») et n'est jamais la cause d'un échec : il s'écrit après.
"""
from __future__ import annotations

import base64
import calendar
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

SYSTEME = ("cassandra", "itare", "noyau", "operateur")
LIENS = ("note", "mail", "url", "projet", "contact", "tache", "domaine", "serveur", "certificat", "constat")
ETATS_RAPPEL = ("attente", "fait")
RECUR_MOTS = {"daily": "FREQ=DAILY", "weekly": "FREQ=WEEKLY", "monthly": "FREQ=MONTHLY", "yearly": "FREQ=YEARLY",
              "quotidien": "FREQ=DAILY", "hebdomadaire": "FREQ=WEEKLY", "mensuel": "FREQ=MONTHLY", "annuel": "FREQ=YEARLY"}
JOURS_RRULE = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
NON_GERES = ("BYMONTHDAY", "BYSETPOS", "BYWEEKNO", "BYYEARDAY", "BYMONTH", "BYHOUR", "BYMINUTE", "BYSECOND")
MAX_OCCURRENCES = 400
FENETRE_DEFAUT = 90
MAX_ICS = 5 * 1024 * 1024
MAX_EVENEMENTS_ICS = 2000
RE_ALARME = re.compile(r"^(\d{1,4})\s*(m|min|h|d|j)$", re.I)
RE_ECH = re.compile(r"^\+(\d+)\s*(min|m|h|d|j)$", re.I)


# ---------------------------------------------------------------------- dates
def lire_instant(s, journee=None):
    """'+30m' '+2h' '+3d' ; 'AAAA-MM-JJ HH:MM' ; 'AAAA-MM-JJTHH:MM' ; 'AAAA-MM-JJ'. -> ('AAAA-MM-JJ HH:MM' | 'AAAA-MM-JJ', date_seule). Lève si illisible."""
    s = str(s or "").strip()
    if not s:
        return "", False
    m = RE_ECH.match(s)
    if m:
        n, u = int(m.group(1)), m.group(2).lower()
        return (datetime.now() + timedelta(minutes={"m": n, "min": n, "h": n * 60, "d": n * 1440, "j": n * 1440}[u])).strftime("%Y-%m-%d %H:%M"), False
    for fmt, seule in (("%Y-%m-%d %H:%M", False), ("%Y-%m-%dT%H:%M", False), ("%Y-%m-%d %H:%M:%S", False), ("%Y-%m-%d", True)):
        try:
            d = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return (d.strftime("%Y-%m-%d") if seule else d.strftime("%Y-%m-%d %H:%M")), seule
    raise ValueError("date illisible « %s » (AAAA-MM-JJ, AAAA-MM-JJ HH:MM, +3d, +2h, +30m)" % s[:40])


def en_datetime(s):
    s = str(s or "").strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:16] if " " in s else s[:10], fmt)
        except ValueError:
            continue
    return None


def minutes_alarme(a):
    m = RE_ALARME.match(str(a or "").strip())
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2).lower()
    return n * {"m": 1, "min": 1, "h": 60, "d": 1440, "j": 1440}[u]


# ---------------------------------------------------------------------- récurrence
def regle_de(rec):
    """Un mot (daily, weekly, quotidien…) ou une RRULE (avec ou sans « RRULE: ») -> la règle normalisée, ou '' si vide. Lève sur le reste."""
    r = str(rec or "").strip()
    if not r:
        return ""
    if r.upper().startswith("RRULE:"):
        r = r[6:].strip()
    if r.lower() in RECUR_MOTS:
        return RECUR_MOTS[r.lower()]
    if "FREQ=" in r.upper():
        return r
    raise ValueError("récurrence : %s ou une règle RRULE (FREQ=WEEKLY;BYDAY=MO,WE)" % ", ".join(sorted(set(RECUR_MOTS))))


def analyser_regle(rule):
    """-> (dict, '') ou (None, motif). Une règle non gérée n'est pas une erreur du fichier : l'appelant garde l'événement de base et le dit."""
    parts = {}
    for kv in str(rule or "").split(";"):
        k, _, v = kv.partition("=")
        if k.strip():
            parts[k.strip().upper()] = v.strip()
    freq = parts.get("FREQ", "").upper()
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
        return None, "FREQ=%s non gérée" % (freq or "absente")
    for k in NON_GERES:
        if k in parts:
            return None, "%s non gérée" % k
    try:
        interval = max(1, int(parts.get("INTERVAL", "1")))
    except ValueError:
        interval = 1
    count = None
    if parts.get("COUNT"):
        try:
            count = max(1, int(parts["COUNT"]))
        except ValueError:
            return None, "COUNT illisible"
    until = None
    if parts.get("UNTIL"):
        try:
            until = datetime.strptime(parts["UNTIL"].strip()[:8], "%Y%m%d") + timedelta(days=1)       # jusqu'à la fin de ce jour
        except ValueError:
            return None, "UNTIL illisible"
    bydays = []
    if parts.get("BYDAY"):
        if freq != "WEEKLY":
            return None, "BYDAY hors d'une règle hebdomadaire non géré"
        for d in parts["BYDAY"].split(","):
            d = d.strip().upper()[-2:]                       # « 2TH » : le préfixe d'ordre n'est pas géré, on ne garde que le jour
            if d not in JOURS_RRULE:
                return None, "BYDAY illisible"
            bydays.append(JOURS_RRULE[d])
    return {"freq": freq, "interval": interval, "count": count, "until": until, "bydays": sorted(set(bydays))}, ""


def ajouter_mois(base, n):
    y, m = divmod(base.month - 1 + n, 12)
    y += base.year
    m += 1
    return base.replace(year=y, month=m, day=min(base.day, calendar.monthrange(y, m)[1]))


def occurrences(rule, debut, journee, du, au, limite=MAX_OCCURRENCES):
    """Les débuts d'une série tombant dans [du, au] (datetimes), chaînes « AAAA-MM-JJ[ HH:MM] ». Rend ([], motif) si la règle n'est pas gérée."""
    r, motif = analyser_regle(rule)
    if r is None:
        return [], motif
    base = en_datetime(debut)
    if base is None:
        return [], "date de départ illisible"
    if journee:
        base = base.replace(hour=0, minute=0)
    fmt = "%Y-%m-%d" if journee else "%Y-%m-%d %H:%M"
    out, freq, iv, count, until = [], r["freq"], r["interval"], r["count"], r["until"]
    if freq == "WEEKLY" and r["bydays"]:
        debut_sem = base - timedelta(days=base.weekday())
        k = 0 if count else max(0, (du - debut_sem).days // (7 * iv) - 1)
        ordre = 0
        for _ in range(100000):
            sem = debut_sem + timedelta(weeks=k * iv)
            for off in r["bydays"]:
                d = sem + timedelta(days=off)
                if d < base:
                    continue
                ordre += 1
                if (count and ordre > count) or (until and d >= until) or d > au:
                    return out, ""
                if d >= du:
                    out.append(d.strftime(fmt))
                    if len(out) >= limite:
                        return out, ""
            k += 1
        return out, ""
    if count:
        i = 0
    elif freq == "DAILY":
        i = max(0, (du - base).days // iv - 1)
    elif freq == "WEEKLY":
        i = max(0, (du - base).days // (7 * iv) - 1)
    elif freq == "MONTHLY":
        i = max(0, ((du.year - base.year) * 12 + du.month - base.month) // iv - 1)
    else:
        i = max(0, (du.year - base.year) // iv - 1)
    for _ in range(100000):
        if freq == "DAILY":
            o = base + timedelta(days=i * iv)
        elif freq == "WEEKLY":
            o = base + timedelta(weeks=i * iv)
        elif freq == "MONTHLY":
            o = ajouter_mois(base, i * iv)
        else:
            try:
                o = base.replace(year=base.year + i * iv)
            except ValueError:                                # 29 février
                o = base.replace(year=base.year + i * iv, day=28)
        if (count and i >= count) or (until and o >= until) or o > au:
            break
        if o >= du:
            out.append(o.strftime(fmt))
            if len(out) >= limite:
                break
        i += 1
    return out, ""


# ---------------------------------------------------------------------- iCalendar
def ical_unescape(v):
    return (v or "").replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def ical_escape(v):
    return str(v or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r", "").replace("\n", "\\n")


def ical_instant(brut, params):
    """(valeur normalisée, journée entière). VALUE=DATE, UTC suffixé Z (ramené à l'heure locale), heures locales avec TZID : chaînes naïves comme partout ailleurs."""
    brut = (brut or "").strip()
    p = (params or "").upper()
    journee = "VALUE=DATE" in p and "DATE-TIME" not in p
    try:
        if journee or (len(brut) == 8 and brut.isdigit()):
            return datetime.strptime(brut[:8], "%Y%m%d").strftime("%Y-%m-%d"), 1
        if brut.endswith("Z"):
            d = datetime.strptime(brut[:15], "%Y%m%dT%H%M%S")
            decalage = datetime.now() - datetime.now(timezone.utc).replace(tzinfo=None)
            # ARRONDI À LA MINUTE : les deux horloges sont lues à quelques microsecondes d'écart, et sans arrondi 09:00Z devenait 10:59.
            d = d + timedelta(minutes=round(decalage.total_seconds() / 60.0))
            return d.strftime("%Y-%m-%d %H:%M"), 0
        return datetime.strptime(brut[:15], "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M"), 0
    except ValueError:
        return brut, 0


def ical_lire(texte):
    """Les VEVENT d'un flux iCalendar (RFC 5545). Une ligne longue est coupée et poursuivie par une espace : on déplie d'abord, sinon les titres longs sont tronqués."""
    texte = re.sub(r"\r?\n[ \t]", "", texte or "")
    out = []
    for bloc in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", texte, re.S):
        ev = {"uid": "", "titre": "", "description": "", "lieu": "", "debut": "", "fin": "", "journee": 0, "rrule": "", "url": ""}
        for m in re.finditer(r"(?im)^([A-Z-]+)((?:;[^:\r\n]*)?):(.*)$", bloc):
            cle, params, brut = m.group(1).upper(), m.group(2) or "", m.group(3).rstrip(chr(13) + chr(10))
            val = brut.strip()                                  # un texte garde ses espaces de fin ; un champ technique non
            if cle == "UID" and not ev["uid"]:
                ev["uid"] = val
            elif cle == "SUMMARY" and not ev["titre"]:
                ev["titre"] = ical_unescape(brut)
            elif cle == "DESCRIPTION" and not ev["description"]:
                ev["description"] = ical_unescape(brut)
            elif cle == "LOCATION" and not ev["lieu"]:
                ev["lieu"] = ical_unescape(brut)
            elif cle == "URL" and not ev["url"]:
                ev["url"] = val
            elif cle == "DTSTART" and not ev["debut"]:
                ev["debut"], ev["journee"] = ical_instant(val, params)
            elif cle == "DTEND" and not ev["fin"]:
                ev["fin"], _ = ical_instant(val, params)
            elif cle == "RRULE" and not ev["rrule"]:
                ev["rrule"] = val
        if ev["debut"] and ev["titre"]:
            out.append(ev)
    return out


def plier(ligne):
    """RFC 5545 : 75 octets au plus par ligne, la suite commence par une espace."""
    b = ligne.encode("utf-8")
    if len(b) <= 75:
        return ligne
    out, cur = [], ""
    for ch in ligne:
        if len((cur + ch).encode("utf-8")) > (75 if not out else 74):
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n ".join(out)


# ---------------------------------------------------------------------- le module
def brancher(ctx):
    db = ctx.stockage

    def compte_agit():
        c = ctx.compte
        if not c or c in SYSTEME:
            raise ValueError("un agenda est celui d'un compte : aucun compte n'agit")
        return c

    def qui_agit(compte):
        a = ctx.acteur or ""
        return compte if a in ("", "humain", "compte") else a

    def lecture(cap, **a):
        try:
            return ctx.executer_lecture(cap, **a)
        except Exception:
            return None

    # ------------------------------------------------------------------ accès
    def evenement_brut(eid, compte):
        try:
            r = db.lire("SELECT * FROM evenements WHERE id=? AND compte=?", (int(eid), compte))
        except (TypeError, ValueError):
            return None
        return dict(r[0]) if r else None

    def exiger(eid, compte):
        e = evenement_brut(eid, compte)
        if e is None:
            raise ValueError("événement introuvable")
        return e

    def noter(eid, texte, acteur=""):
        """Écrit après l'acte, en silence : un journal qui ferait échouer ce qu'il journalise serait pire que pas de journal."""
        try:
            return db.ecrire("INSERT INTO journal(evenement_id, texte, acteur, ts) VALUES (?,?,?,?)", (int(eid), str(texte or "")[:300], str(acteur or "")[:80], time.time()))
        except Exception:
            return None

    def projet_lisible(pid):
        e = lecture("projets.equipe", id=int(pid))
        return e if e else None

    # ------------------------------------------------------------------ événements
    def propre(v, n):
        return str(v or "").strip()[:n]

    def valeurs(compte, e, titre, debut, fin, description, lieu, journee, projet_id, recurrence, alarme, url):
        """Les champs d'un événement après patch (e = l'existant ou None), validés. Rend un dict de colonnes."""
        t = propre(titre, 200) if titre is not None else (e["titre"] if e else "")
        if not t:
            raise ValueError("un titre est requis")
        d_brut = debut if debut is not None else (e["debut"] if e else "")
        d, seule = lire_instant(d_brut)
        if not d:
            raise ValueError("une date de début est requise")
        jr = (1 if seule else 0) if journee is None else (1 if journee else 0)
        if jr and len(d) > 10:
            d = d[:10]
        if jr == 0 and seule:
            d += " 09:00"
        f_brut = fin if fin is not None else (e["fin"] if e else "")
        f, _ = lire_instant(f_brut) if f_brut else ("", False)
        if f:
            f = f[:10] if jr else (f + " 00:00" if len(f) == 10 else f)
            if (en_datetime(f) or datetime.max) < (en_datetime(d) or datetime.min):
                raise ValueError("la fin précède le début")
        rec = e["recurrence"] if (recurrence is None and e) else regle_de(recurrence)
        if rec:
            r, motif = analyser_regle(rec)
            if r is None:
                raise ValueError("récurrence non gérée (%s)" % motif)
        al = e["alarme"] if (alarme is None and e) else propre(alarme, 40)
        if al and minutes_alarme(al) is None:
            raise ValueError("alarme : 15m, 2h, 1d")
        u = e["url"] if (url is None and e) else propre(url, 400)
        if u and not re.match(r"^https?://", u, re.I):
            raise ValueError("l'adresse doit commencer par http:// ou https://")
        pid = e["projet_id"] if (projet_id is None and e) else (int(projet_id) if projet_id else None)
        if pid and (e is None or pid != e["projet_id"]) and not projet_lisible(pid):
            raise ValueError("projet introuvable")
        return {"titre": t, "description": (e["description"] if (description is None and e) else str(description or "")[:8000]),
                "lieu": (e["lieu"] if (lieu is None and e) else propre(lieu, 300)), "debut": d, "fin": f, "journee": jr, "projet_id": pid, "recurrence": rec, "alarme": al, "url": u}

    def evenement_enregistrer(c, id=0, titre=None, debut=None, fin=None, description=None, lieu=None, journee=None, projet_id=None, recurrence=None, alarme=None, url=None):
        compte = compte_agit()
        qui = qui_agit(compte)
        if id:
            e = exiger(id, compte)
            v = valeurs(compte, e, titre, debut, fin, description, lieu, journee, projet_id, recurrence, alarme, url)
            avant = {k: e[k] for k in v}
            db.ecrire("UPDATE evenements SET %s WHERE id=?" % ",".join("%s=?" % k for k in v), list(v.values()) + [e["id"]])
            vus = []
            if v["debut"] != e["debut"]:
                vus.append(noter(e["id"], "Déplacé du %s au %s" % (e["debut"][:16], v["debut"][:16]), qui))
            elif v["titre"] != e["titre"]:
                vus.append(noter(e["id"], "Renommé — « %s »" % v["titre"], qui))
            return {"id": e["id"], "compte": compte, "cree": False, "avant": avant, "maj": v, "journal": [x for x in vus if x]}
        v = valeurs(compte, None, titre, debut, fin, description, lieu, journee, projet_id, recurrence, alarme, url)
        uid = "loc-" + hashlib.sha1(("%s|%s|%s|%s" % (compte, v["titre"], v["debut"], time.time())).encode("utf-8", "replace")).hexdigest()[:24]
        eid = db.ecrire("INSERT INTO evenements(compte, uid, titre, description, lieu, debut, fin, journee, source, projet_id, recurrence, alarme, url, cree) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (compte, uid, v["titre"], v["description"], v["lieu"], v["debut"], v["fin"], v["journee"], "manuel", v["projet_id"], v["recurrence"], v["alarme"], v["url"], time.time()))
        noter(eid, "Créé", qui)
        ctx.emettre("evenement.cree", objet=("evenement", str(eid)), donnees={"id": eid, "titre": v["titre"][:80], "debut": v["debut"]})
        return {"id": eid, "compte": compte, "cree": True, "maj": v, "journal": []}

    def prouver_enregistre(c, res):
        e = evenement_brut(res["id"], res["compte"])
        return e is not None and all(e[k] == x for k, x in res["maj"].items())

    def defaire_enregistre(c, res):
        if res["cree"]:
            effacer_evenement(res["id"])
            return
        a = res["avant"]
        db.ecrire("UPDATE evenements SET %s WHERE id=?" % ",".join("%s=?" % k for k in a), list(a.values()) + [res["id"]])
        for j in res["journal"]:
            db.ecrire("DELETE FROM journal WHERE id=?", (j,))

    def effacer_evenement(eid):
        for t in ("liens", "journal"):
            db.ecrire("DELETE FROM %s WHERE evenement_id=?" % t, (eid,))
        db.ecrire("DELETE FROM evenements WHERE id=?", (eid,))

    def instantane(eid):
        return {"evenement": dict(db.lire("SELECT * FROM evenements WHERE id=?", (eid,))[0]),
                "liens": [dict(r) for r in db.lire("SELECT * FROM liens WHERE evenement_id=?", (eid,))],
                "journal": [dict(r) for r in db.lire("SELECT * FROM journal WHERE evenement_id=?", (eid,))]}

    def reposer(snap):
        with db.transaction() as cx:
            for t, lignes in (("evenements", [snap["evenement"]]), ("liens", snap["liens"]), ("journal", snap["journal"])):
                for ligne in lignes:
                    ks = list(ligne)
                    cx.execute("INSERT OR REPLACE INTO %s(%s) VALUES (%s)" % (t, ",".join(ks), ",".join("?" * len(ks))), [ligne[k] for k in ks])

    def evenement_supprimer(c, id=0):
        compte = compte_agit()
        e = exiger(id, compte)
        snap = instantane(e["id"])
        effacer_evenement(e["id"])                # sans cela les liens survivraient à leur événement et s'accumuleraient
        return {"id": e["id"], "compte": compte, "copie": snap}

    def prouver_supprime(c, res):
        return evenement_brut(res["id"], res["compte"]) is None

    def defaire_supprime(c, res):
        reposer(res["copie"])

    # ------------------------------------------------------------------ lecture des événements
    def jour_borne(s, fin=False):
        d = en_datetime(str(s or "")[:10])
        if d is None:
            raise ValueError("date attendue au format AAAA-MM-JJ")
        return d.replace(hour=23, minute=59, second=59) if fin else d

    def plage(du, au):
        d0 = jour_borne(du) if du else datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        d1 = jour_borne(au, True) if au else d0 + timedelta(days=FENETRE_DEFAUT)
        if d1 < d0:
            raise ValueError("la fin de la plage précède son début")
        return d0, d1

    def etendre(e, d0, d1):
        """L'événement et, s'il se répète, ses occurrences tombant dans la plage. Une occurrence porte `occurrence_de` et garde la durée de la série."""
        base = {k: e[k] for k in ("id", "uid", "titre", "description", "lieu", "debut", "fin", "journee", "source", "projet_id", "recurrence", "alarme", "url")}
        if not e["recurrence"]:
            return [base] if d0.strftime("%Y-%m-%d") <= e["debut"][:10] <= d1.strftime("%Y-%m-%d") else []
        starts, _ = occurrences(e["recurrence"], e["debut"], e["journee"], d0, d1)
        a, b = en_datetime(e["debut"]), en_datetime(e["fin"]) if e["fin"] else None
        duree = (b - a) if (a and b) else None
        out = []
        for s in starts:
            o = dict(base, debut=s, occurrence_de=e["id"] if s != e["debut"] else None)
            if duree is not None:
                o["fin"] = (en_datetime(s) + duree).strftime("%Y-%m-%d" if e["journee"] else "%Y-%m-%d %H:%M")
            out.append(o)
        return out

    def evenements_de(compte, d0, d1, limite=500):
        out = []
        for r in db.lire("SELECT * FROM evenements WHERE compte=? AND (recurrence<>'' OR (debut>=? AND debut<=?)) ORDER BY debut", (compte, d0.strftime("%Y-%m-%d"), d1.strftime("%Y-%m-%d") + "~")):
            out += etendre(dict(r), d0, d1)
        out.sort(key=lambda x: x["debut"])
        return out[:max(1, min(int(limite or 500), 2000))]

    def evenements(c, du="", au="", limite=500):
        compte = compte_agit()
        d0, d1 = plage(du, au)
        return {"evenements": evenements_de(compte, d0, d1, limite), "du": d0.strftime("%Y-%m-%d"), "au": d1.strftime("%Y-%m-%d")}

    def etat_lien(compte, l):
        """Un lien n'est utile que s'il porte l'état de ce qu'il désigne."""
        d = dict(l)
        d["nom"] = l["label"] or l["ref"]
        try:
            if l["kind"] == "tache":
                f = lecture("taches.fiche", id=int(l["ref"]))
                if f:
                    t = f["tache"]
                    d.update(nom=t["texte"], etat="fait" if t["statut"] == "fait" else (t["echeance"] or "")[:10], fait=1 if t["statut"] == "fait" else 0)
            elif l["kind"] == "projet":
                f = lecture("projets.equipe", id=int(l["ref"]))
                if f:
                    d.update(nom=f["projet"], etat=f.get("mon_role", ""))
            elif l["kind"] == "note":
                f = lecture("notes.fiche", ref=l["ref"], marquer=False)
                if f:
                    d.update(nom=f["titre"], etat=f.get("etat_n", ""))
            elif l["kind"] == "contact":
                f = lecture("contacts.voir", id=int(l["ref"]))
                if f:
                    d.update(nom=f.get("display_name") or f.get("nom") or d["nom"], detail=" · ".join(x for x in (f.get("company", ""), f.get("job_title", "")) if x))
        except (TypeError, ValueError):
            pass
        return d

    def evenement(c, id=0):
        compte = compte_agit()
        e = exiger(id, compte)
        liens = [etat_lien(compte, dict(r)) for r in db.lire("SELECT id, kind, ref, label FROM liens WHERE evenement_id=? ORDER BY kind", (e["id"],))]
        prep = [l for l in liens if l["kind"] == "tache"]
        proj = projet_lisible(e["projet_id"]) if e["projet_id"] else None
        occ = []
        if e["recurrence"]:
            occ = occurrences(e["recurrence"], e["debut"], e["journee"], datetime.now(), datetime.now() + timedelta(days=366), 6)[0]
        return {"evenement": e, "liens": liens, "prochaines": occ, "prep": {"total": len(prep), "faites": len([l for l in prep if l.get("fait")])},
                "projet": {"id": e["projet_id"], "nom": proj["projet"]} if proj else None,
                "journal": [{"texte": r["texte"], "acteur": r["acteur"], "ts": r["ts"]} for r in db.lire("SELECT texte, acteur, ts FROM journal WHERE evenement_id=? ORDER BY id DESC LIMIT 12", (e["id"],))]}

    # ------------------------------------------------------------------ liens
    def lien_ajouter(c, id=0, kind="", ref="", label=""):
        compte = compte_agit()
        e = exiger(id, compte)
        kind, ref = str(kind or "").strip().lower(), str(ref or "").strip()
        if kind not in LIENS:
            raise ValueError("type inconnu (%s)" % ", ".join(LIENS))
        if not ref:
            raise ValueError("référence requise")
        if kind == "domaine":
            ref = re.sub(r"^[a-z]+://", "", ref.lower()).split("/")[0]
            ref = ref[4:] if ref.startswith("www.") else ref
        existait = bool(db.lire("SELECT 1 FROM liens WHERE evenement_id=? AND kind=? AND ref=?", (e["id"], kind, ref)))
        if not existait:
            db.ecrire("INSERT INTO liens(evenement_id, kind, ref, label, cree) VALUES (?,?,?,?,?)", (e["id"], kind, ref, str(label or "")[:200], time.time()))
            if kind != "tache":                       # une préparation est journalisée par l'acte qui crée la tâche : deux lignes sinon
                noter(e["id"], "Rattaché — %s « %s »" % (kind, (label or ref)[:80]), qui_agit(compte))
        return {"id": e["id"], "compte": compte, "kind": kind, "ref": ref, "existait": existait}

    def prouver_lie(c, res):
        return bool(db.lire("SELECT 1 FROM liens WHERE evenement_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"])))

    def defaire_lie(c, res):
        if not res["existait"]:
            db.ecrire("DELETE FROM liens WHERE evenement_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"]))

    def lien_retirer(c, id=0, kind="", ref=""):
        compte = compte_agit()
        e = exiger(id, compte)
        kind, ref = str(kind or "").strip().lower(), str(ref or "").strip()
        avant = db.lire("SELECT * FROM liens WHERE evenement_id=? AND kind=? AND ref=?", (e["id"], kind, ref))
        if not avant:
            raise ValueError("lien introuvable")
        db.ecrire("DELETE FROM liens WHERE id=?", (avant[0]["id"],))
        return {"id": e["id"], "compte": compte, "kind": kind, "ref": ref, "avant": dict(avant[0])}

    def prouver_retire(c, res):
        return not db.lire("SELECT 1 FROM liens WHERE evenement_id=? AND kind=? AND ref=?", (res["id"], res["kind"], res["ref"]))

    def defaire_retire(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO liens(id, evenement_id, kind, ref, label, cree) VALUES (?,?,?,?,?,?)", (a["id"], a["evenement_id"], a["kind"], a["ref"], a["label"], a["cree"]))

    # ------------------------------------------------------------------ rappels
    def rappel_brut(rid, compte):
        try:
            r = db.lire("SELECT * FROM rappels WHERE id=? AND compte=?", (int(rid), compte))
        except (TypeError, ValueError):
            return None
        return dict(r[0]) if r else None

    def rappels(c, inclure_faits=True):
        compte = compte_agit()
        sql = "SELECT * FROM rappels WHERE compte=?" + ("" if inclure_faits else " AND statut<>'fait'") + " ORDER BY (statut='fait'), (echeance=''), echeance, id"
        return {"rappels": [dict(r) for r in db.lire(sql, (compte,))]}

    def rappel_enregistrer(c, id=0, texte=None, echeance=None, statut=None):
        compte = compte_agit()
        if statut is not None and str(statut) not in ETATS_RAPPEL:
            raise ValueError("statut : %s" % " | ".join(ETATS_RAPPEL))
        ech = None
        if echeance is not None:
            ech = lire_instant(echeance)[0]
            if ech and len(ech) == 10:
                ech += " 09:00"
        if id:
            r = rappel_brut(id, compte)
            if r is None:
                raise ValueError("rappel introuvable")
            maj = {"texte": propre(texte, 500) or r["texte"] if texte is not None else r["texte"], "echeance": r["echeance"] if ech is None else ech, "statut": r["statut"] if statut is None else str(statut)}
            db.ecrire("UPDATE rappels SET texte=?, echeance=?, statut=? WHERE id=?", (maj["texte"], maj["echeance"], maj["statut"], r["id"]))
            return {"id": r["id"], "compte": compte, "cree": False, "avant": r, "maj": maj}
        t = propre(texte, 500)
        if not t:
            raise ValueError("texte requis")
        maj = {"texte": t, "echeance": ech or "", "statut": str(statut or "attente")}
        rid = db.ecrire("INSERT INTO rappels(compte, texte, echeance, statut, cree) VALUES (?,?,?,?,?)", (compte, maj["texte"], maj["echeance"], maj["statut"], time.time()))
        ctx.emettre("rappel.cree", objet=("rappel", str(rid)), donnees={"id": rid, "echeance": maj["echeance"]})
        return {"id": rid, "compte": compte, "cree": True, "maj": maj}

    def prouver_rappel(c, res):
        r = rappel_brut(res["id"], res["compte"])
        return r is not None and all(r[k] == v for k, v in res["maj"].items())

    def defaire_rappel(c, res):
        if res["cree"]:
            db.ecrire("DELETE FROM rappels WHERE id=?", (res["id"],))
        else:
            a = res["avant"]
            db.ecrire("UPDATE rappels SET texte=?, echeance=?, statut=? WHERE id=?", (a["texte"], a["echeance"], a["statut"], a["id"]))

    def rappel_statut(c, id=0, statut=""):
        return rappel_enregistrer(c, id=id, statut=statut)

    def rappel_supprimer(c, id=0):
        compte = compte_agit()
        r = rappel_brut(id, compte)
        if r is None:
            raise ValueError("rappel introuvable")
        db.ecrire("DELETE FROM rappels WHERE id=?", (r["id"],))
        return {"id": r["id"], "compte": compte, "avant": r}

    def prouver_rappel_supprime(c, res):
        return rappel_brut(res["id"], res["compte"]) is None

    def defaire_rappel_supprime(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO rappels(id, compte, texte, echeance, statut, cree) VALUES (?,?,?,?,?,?)", (a["id"], a["compte"], a["texte"], a["echeance"], a["statut"], a["cree"]))

    # ------------------------------------------------------------------ CalDAV (lecture)
    def caldav_creds(compte):
        url = str(ctx.reglage("caldav_url", compte) or "").strip()
        return url, str(ctx.reglage("caldav_identifiant", compte) or "").strip(), str(ctx.reglage("caldav_mot_de_passe", compte) or "")

    def caldav_etat(c):
        compte = compte_agit()
        url, user, mdp = caldav_creds(compte)
        return {"configuree": bool(url), "url": url, "identifiant": user, "mot_de_passe_pose": bool(mdp)}

    def caldav_requete(compte, d0, d1):
        url, user, mdp = caldav_creds(compte)
        if not re.match(r"^https?://", url, re.I):
            raise ValueError("adresse CalDAV non réglée")
        fmt = "%Y%m%dT%H%M%SZ"
        xml = ('<?xml version="1.0" encoding="utf-8" ?><c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:prop><c:calendar-data/></d:prop>'
               '<c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"><c:time-range start="%s" end="%s"/></c:comp-filter></c:comp-filter></c:filter></c:calendar-query>'
               % (d0.strftime(fmt), d1.strftime(fmt)))
        req = urllib.request.Request(url, data=xml.encode("utf-8"), method="REPORT")
        if user:
            req.add_header("Authorization", "Basic " + base64.b64encode(("%s:%s" % (user, mdp)).encode("utf-8")).decode("ascii"))
        req.add_header("Depth", "1")
        req.add_header("Content-Type", "application/xml; charset=utf-8")
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read(MAX_ICS).decode("utf-8", errors="replace")

    def caldav_evenements(compte, d0, d1):
        brut = caldav_requete(compte, d0, d1)
        out = []
        for ev in ical_lire(brut.replace("&#13;", "").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")):
            starts = [ev["debut"]]
            if ev["rrule"]:
                s, motif = occurrences(ev["rrule"], ev["debut"], ev["journee"], d0, d1)
                starts = s if not motif else ([ev["debut"]] if d0.strftime("%Y-%m-%d") <= ev["debut"][:10] <= d1.strftime("%Y-%m-%d") else [])
            elif not (d0.strftime("%Y-%m-%d") <= ev["debut"][:10] <= d1.strftime("%Y-%m-%d")):
                starts = []
            for s in starts:
                out.append({"titre": ev["titre"], "debut": s, "fin": ev["fin"] if s == ev["debut"] else "", "lieu": ev["lieu"], "journee": ev["journee"], "origine": "caldav"})
        return out

    def agenda(c, jours=14):
        compte = compte_agit()
        jours = max(1, min(int(jours or 14), 366))
        d0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        d1 = (d0 + timedelta(days=jours)).replace(hour=23, minute=59, second=59)
        locaux = [dict(e, origine="local") for e in evenements_de(compte, d0, d1, 200)]
        url = caldav_creds(compte)[0]
        if not url:
            return {"evenements": locaux, "caldav": False, "note": "agenda local (CalDAV non configuré)"}
        try:
            distants = caldav_evenements(compte, d0, d1)
        except Exception as e:                      # CalDAV en panne ne doit PAS faire disparaître l'agenda local
            return {"evenements": locaux, "caldav": False, "note": "CalDAV injoignable (%s) — agenda local seul" % str(e)[:120]}
        return {"evenements": sorted(locaux + distants, key=lambda e: e["debut"])[:400], "caldav": True}

    # ------------------------------------------------------------------ la vue temporelle unique
    def calendrier(c, du="", au=""):
        """Ce qui tombe quand. Une tâche avec échéance EST un élément d'agenda ; la reléguer dans une autre vue obligeait à consulter deux écrans."""
        compte = compte_agit()
        d0, d1 = plage(du, au)
        a0, a1 = d0.strftime("%Y-%m-%d"), d1.strftime("%Y-%m-%d")
        auj = datetime.now().strftime("%Y-%m-%d")
        out = [dict(e, kind="event", quand=e["debut"], source="événement") for e in evenements_de(compte, d0, d1)]
        taches = (lecture("taches.lister", limite=1000) or {}).get("taches", [])
        for t in taches:
            if t["statut"] == "abandonnee":
                continue
            resp = (t.get("responsable") or "").lower()
            if resp and resp != compte.lower():
                continue                             # confiée à quelqu'un d'autre : à son agenda, pas au mien
            due = (t.get("echeance") or "")[:16]
            if not due:
                continue
            if t["statut"] != "fait" and due[:10] < auj and a0 <= auj <= a1:
                out.append({"kind": "task", "id": t["id"], "titre": "⚠ " + t["texte"], "quand": auj + " 00:00", "debut": auj + " 00:00", "journee": 1, "statut": t["statut"], "retard": due[:10],
                            "projet": t.get("projet", ""), "source": "tâche"})
                continue
            if a0 <= due[:10] <= a1:
                out.append({"kind": "task", "id": t["id"], "titre": t["texte"], "quand": due, "debut": due, "journee": 0, "statut": t["statut"], "projet": t.get("projet", ""), "source": "tâche"})
        for r in db.lire("SELECT * FROM rappels WHERE compte=? AND echeance<>''", (compte,)):
            if a0 <= r["echeance"][:10] <= a1:
                out.append({"kind": "reminder", "id": r["id"], "titre": r["texte"], "quand": r["echeance"][:16], "debut": r["echeance"][:16], "journee": 0, "statut": r["statut"], "source": "rappel"})
        for p in ((lecture("projets.lister") or {}).get("projets", []))[:50]:
            v = lecture("projets.voir", id=p["id"])
            for j in (v or {}).get("jalons", []):
                d = str(j.get("date") or "")[:10]
                if d and a0 <= d <= a1:
                    out.append({"kind": "etape", "id": p["id"], "titre": ("✓ " if j.get("etat") == "tenu" else "◆ ") + str(j.get("nom") or "Étape") + " — " + p["nom"], "quand": d + " 00:00", "debut": d + " 00:00",
                                "journee": 1, "statut": j.get("etat", ""), "projet": p["nom"], "source": "étape"})
        out.sort(key=lambda x: x.get("quand") or "")
        return {"elements": out, "du": a0, "au": a1}

    # ------------------------------------------------------------------ import / export iCalendar
    def ical_importer(c, texte="", etiquette="import"):
        compte = compte_agit()
        texte = str(texte or "")
        if len(texte.encode("utf-8")) > MAX_ICS:
            raise ValueError("fichier trop gros (5 Mo au plus)")
        evs = ical_lire(texte)
        if not evs:
            raise ValueError("aucun événement trouvé dans ce fichier")
        if len(evs) > MAX_EVENEMENTS_ICS:
            raise ValueError("%d événements — %d au plus par import" % (len(evs), MAX_EVENEMENTS_ICS))
        src = "ical:%s" % propre(etiquette or "import", 60)
        crees, maj, avertissements = [], [], []
        for ev in evs:
            uid = ev["uid"] or "gen-" + hashlib.sha1(("%s|%s" % (ev["titre"], ev["debut"])).encode("utf-8", "replace")).hexdigest()[:24]
            rec = ""
            if ev["rrule"]:
                r, motif = analyser_regle(ev["rrule"])
                if r is None:                        # perdre des occurrences en silence est le pire cas : l'événement de base est gardé, et on le dit
                    avertissements.append("« %s » : récurrence non développée (%s) — seule la première occurrence est importée" % (ev["titre"][:40], motif))
                else:
                    rec = ev["rrule"]
            debut = ev["debut"][:10] if ev["journee"] else ev["debut"]
            fin = ev["fin"] if ev["fin"] and (en_datetime(ev["fin"]) or datetime.min) >= (en_datetime(debut) or datetime.max) else ""
            url = ev["url"] if re.match(r"^https?://", ev["url"] or "", re.I) else ""
            ligne = (ev["titre"][:200], ev["description"][:8000], ev["lieu"][:300], debut, fin[:16], 1 if ev["journee"] else 0, src, rec, url[:400])
            ex = db.lire("SELECT * FROM evenements WHERE compte=? AND uid=?", (compte, uid))
            if ex:
                maj.append(dict(ex[0]))
                db.ecrire("UPDATE evenements SET titre=?, description=?, lieu=?, debut=?, fin=?, journee=?, source=?, recurrence=?, url=? WHERE id=?", ligne + (ex[0]["id"],))
            else:
                crees.append(db.ecrire("INSERT INTO evenements(titre, description, lieu, debut, fin, journee, source, recurrence, url, compte, uid, cree) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", ligne + (compte, uid, time.time())))
        return {"compte": compte, "crees": crees, "mises_a_jour": [e["id"] for e in maj], "avant": maj, "total": len(evs), "avertissements": avertissements[:10]}

    def prouver_importe(c, res):
        return all(evenement_brut(i, res["compte"]) for i in res["crees"] + res["mises_a_jour"])

    def defaire_importe(c, res):
        for i in res["crees"]:
            effacer_evenement(i)
        for e in res["avant"]:
            ks = list(e)
            db.ecrire("INSERT OR REPLACE INTO evenements(%s) VALUES (%s)" % (",".join(ks), ",".join("?" * len(ks))), [e[k] for k in ks])

    def exporter_ics(c, du="", au=""):
        compte = compte_agit()
        sql, args = "SELECT * FROM evenements WHERE compte=?", [compte]
        if du:
            sql += " AND (recurrence<>'' OR debut>=?)"
            args.append(jour_borne(du).strftime("%Y-%m-%d"))
        if au:
            sql += " AND debut<=?"
            args.append(jour_borne(au, True).strftime("%Y-%m-%d") + "~")
        lignes = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Cassandra//Agenda//FR", "CALSCALE:GREGORIAN"]
        n = 0
        for e in db.lire(sql + " ORDER BY debut", args):
            n += 1
            lignes += ["BEGIN:VEVENT", "UID:%s" % e["uid"], "DTSTAMP:%s" % datetime.fromtimestamp(e["cree"], timezone.utc).strftime("%Y%m%dT%H%M%SZ"), "SUMMARY:%s" % ical_escape(e["titre"])]
            for cle, val in (("DTSTART", e["debut"]), ("DTEND", e["fin"])):
                if not val:
                    continue
                d = en_datetime(val)
                lignes.append("%s;VALUE=DATE:%s" % (cle, d.strftime("%Y%m%d")) if e["journee"] else "%s:%s" % (cle, d.strftime("%Y%m%dT%H%M%S")))
            if e["description"]:
                lignes.append("DESCRIPTION:%s" % ical_escape(e["description"]))
            if e["lieu"]:
                lignes.append("LOCATION:%s" % ical_escape(e["lieu"]))
            if e["url"]:
                lignes.append("URL:%s" % e["url"])
            if e["recurrence"]:
                lignes.append("RRULE:%s" % e["recurrence"])
            lignes.append("END:VEVENT")
        lignes.append("END:VCALENDAR")
        return {"nom": "agenda-%s.ics" % time.strftime("%Y%m%d"), "mime": "text/calendar", "evenements": n, "contenu": "\r\n".join(plier(l) for l in lignes) + "\r\n"}

    # ------------------------------------------------------------------ détecteurs
    def det_rappels(c):
        maintenant = time.strftime("%Y-%m-%d %H:%M")
        return [{"objet": ("rappel", str(r["id"])), "compte": r["compte"], "titre": "Rappel : %s" % r["texte"][:80], "detail": "échu le %s" % r["echeance"][:16]}
                for r in db.lire("SELECT id, compte, texte, echeance FROM rappels WHERE statut<>'fait' AND echeance<>'' AND echeance<=?", (maintenant,))]

    def det_proches(c):
        """Un événement avec alarme est un constat de l'ouverture de l'alarme jusqu'à son début ; il se résout seul ensuite."""
        maintenant = datetime.now()
        out = []
        for e in db.lire("SELECT * FROM evenements WHERE alarme<>''"):
            avance = minutes_alarme(e["alarme"])
            if avance is None:
                continue
            for s in etendre(dict(e), maintenant, maintenant + timedelta(days=1, minutes=avance))[:20]:
                debut = en_datetime(s["debut"])
                if debut is not None and debut - timedelta(minutes=avance) <= maintenant < (debut if not e["journee"] else debut + timedelta(days=1)):
                    out.append({"objet": ("evenement", "%d:%s" % (e["id"], s["debut"])), "compte": e["compte"], "titre": "Bientôt : %s" % e["titre"][:80],
                                "detail": "à %s%s" % (s["debut"][:16], (" — %s" % e["lieu"]) if e["lieu"] else "")})
        return out

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.detecteur("rappel_echu", det_rappels)
    c.detecteur("evenement_proche", det_proches)
    def jours_de(quand):
        """Le nombre de jours entre aujourd'hui et une date « AAAA-MM-JJ… » (négatif : dépassée) ; None si elle est illisible."""
        s = str(quand or "")[:10]
        try:
            t = time.mktime(time.strptime(s, "%Y-%m-%d"))
        except Exception:
            return None
        return int(round((t - time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))) / 86400))

    def item_jour(bande, quoi, titre, detail="", nat="", ref="", poids=0, ou="", geste=("Ouvrir", "ouvrir")):
        return {"bande": bande, "quoi": quoi, "titre": str(titre or "")[:160], "detail": str(detail or "")[:200], "nat": nat, "ref": str(ref or ""), "poids": int(poids), "ou": ou,
                "geste": list(geste) if geste else None}

    def signal_rappels(c):
        out = []
        for r in rappels(c, inclure_faits=False)["rappels"]:
            if r.get("statut") == "fait":
                continue
            j = jours_de(r.get("echeance"))
            if j is None:
                continue
            if j < 0:
                out.append(item_jour("brule", "rappel", r["texte"], "En retard de %d jour(s)." % -j, "rappel", r["id"], 100 - j, "rem"))
            elif j == 0:
                out.append(item_jour("jour", "rappel", r["texte"], str(r.get("echeance") or "")[11:16] or "dans la journée", "rappel", r["id"], 40, "rem", geste=("Reporter", "reporter")))
        return {"items": out}

    def signal_agenda(c):
        auj = time.strftime("%Y-%m-%d")
        out = []
        for e in evenements(c, du=auj, au=auj, limite=60)["evenements"]:
            out.append(item_jour("jour", "event", e.get("titre") or "(sans titre)", "journée entière" if e.get("journee") else str(e.get("debut") or "")[11:16], "event", e["id"], 30, "cal", geste=("Voir", "ouvrir")))
        return {"items": out}

    for cid, f in (("evenements", evenements), ("signal_rappels", signal_rappels), ("signal_agenda", signal_agenda), ("evenement", evenement), ("calendrier", calendrier), ("agenda", agenda), ("caldav_etat", caldav_etat), ("rappels", rappels), ("exporter_ics", exporter_ics)):
        c.implementer(cid, f)
    c.implementer("evenement_enregistrer", evenement_enregistrer, prouver_enregistre, defaire_enregistre, simuler=lambda x, titre="", id=0, **_: "enregistrerait l'événement « %s »" % titre)
    c.implementer("evenement_supprimer", evenement_supprimer, prouver_supprime, defaire_supprime, simuler=lambda x, id="", **_: "supprimerait l'événement %s avec ses liens" % id)
    c.implementer("lien_ajouter", lien_ajouter, prouver_lie, defaire_lie, simuler=lambda x, id="", kind="", ref="", **_: "rattacherait l'événement %s à %s %s" % (id, kind, ref))
    c.implementer("lien_retirer", lien_retirer, prouver_retire, defaire_retire, simuler=lambda x, id="", kind="", ref="", **_: "détacherait l'événement %s de %s %s" % (id, kind, ref))
    c.implementer("rappel_enregistrer", rappel_enregistrer, prouver_rappel, defaire_rappel, simuler=lambda x, texte="", **_: "enregistrerait le rappel « %s »" % texte)
    c.implementer("rappel_statut", rappel_statut, prouver_rappel, defaire_rappel, simuler=lambda x, id="", statut="", **_: "passerait le rappel %s à « %s »" % (id, statut))
    c.implementer("rappel_supprimer", rappel_supprimer, prouver_rappel_supprime, defaire_rappel_supprime, simuler=lambda x, id="", **_: "supprimerait le rappel %s" % id)
    c.implementer("ical_importer", ical_importer, prouver_importe, defaire_importe, simuler=lambda x, **_: "importerait les événements du fichier .ics")
