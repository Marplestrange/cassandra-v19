# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Agenda : lecture d'un flux iCalendar (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : agenda
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #a61307
# HÔTE CN    : CN_module.py · ical_lire @1.0
# RÔLE       : lit un flux iCalendar (RFC 5545) et rend ses événements : titre, lieu, début, fin, journée entière, récurrence ; une heure UTC est ramenée à l'heure locale par le décalage reçu.
# MÉTHODE    : fonction pure : dépliage des lignes, un bloc par VEVENT, le premier exemplaire d'un champ gagne ; le décalage local (minutes) est une ENTRÉE, lue par la façade, pour que l'EC ne lise aucune horloge.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=ical_lire contrat=@1.0 version=EC0 empreinte=a61307 ▼▼▼
from datetime import datetime, timedelta, timezone
import re

def ical_unescape(v):
    return (v or "").replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")

_JOUR = r"(?P<Y>\d\d\d\d)(?P<m>1[0-2]|0[1-9]|[1-9])(?P<d>3[0-1]|[1-2]\d|0[1-9]|[1-9]| [1-9])"
_HEURE = r"T(?P<H>2[0-3]|[0-1]\d|\d)(?P<M>[0-5]\d|\d)(?P<S>6[0-1]|[0-5]\d|\d)"

def _date_heure(v, avec_heure):
    """AAAAMMJJ ou AAAAMMJJTHHMMSS -> datetime ; ValueError si la forme ou la valeur est fausse. Mêmes motifs que strptime, qui n'est pas appelé : il importe _strptime à son premier appel, import que le filtre des EC refuse (strftime importe `time` pareil, d'où isoformat plus bas)."""
    g = re.fullmatch(_JOUR + (_HEURE if avec_heure else ""), v)
    if not g:
        raise ValueError(v)
    return datetime(int(g["Y"]), int(g["m"]), int(g["d"]), *((int(g["H"]), int(g["M"]), int(g["S"])) if avec_heure else ()))

def ical_instant(brut, params, decalage_min):
    """(valeur normalisée, journée entière). VALUE=DATE, UTC suffixé Z (ramené à l'heure locale), heures locales avec TZID : chaînes naïves comme partout ailleurs."""
    brut = (brut or "").strip()
    p = (params or "").upper()
    journee = "VALUE=DATE" in p and "DATE-TIME" not in p
    try:
        if journee or (len(brut) == 8 and brut.isdigit()):
            return _date_heure(brut[:8], False).date().isoformat(), 1
        if brut.endswith("Z"):
            d = _date_heure(brut[:15], True)
            d = d + timedelta(minutes=decalage_min)
            return d.isoformat(" ", "minutes"), 0
        return _date_heure(brut[:15], True).isoformat(" ", "minutes"), 0
    except ValueError:
        return brut, 0

def ical_lire(texte, decalage_min):
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
                ev["debut"], ev["journee"] = ical_instant(val, params, decalage_min)
            elif cle == "DTEND" and not ev["fin"]:
                ev["fin"], _ = ical_instant(val, params, decalage_min)
            elif cle == "RRULE" and not ev["rrule"]:
                ev["rrule"] = val
        if ev["debut"] and ev["titre"]:
            out.append(ev)
    return out

def point_ical_lire(entree):
    """Le point d'évolution `ical_lire` (contrat 1.0)."""
    return {"evenements": ical_lire(entree["texte"], entree["decalage_min"])}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_ical_lire(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de agenda (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_ical_lire.json ; corpus doré dans contrats/CN_ical_lire.corpus.json (sorties de l'ancien code, données synthétiques).
