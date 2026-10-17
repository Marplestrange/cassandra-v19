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
# VERSION EC : EC0 (référence 0.3.0)  #4c252b
# HÔTE CN    : CN_module.py · ical_lire @1.0
# RÔLE       : lit un flux iCalendar (RFC 5545) et rend ses événements : titre, lieu, début, fin, journée entière, récurrence ; une heure UTC est ramenée à l'heure locale par le décalage reçu.
# MÉTHODE    : fonction pure : dépliage des lignes, un bloc par VEVENT, le premier exemplaire d'un champ gagne ; le décalage local (minutes) est une ENTRÉE, lue par la façade, pour que l'EC ne lise aucune horloge.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=ical_lire contrat=@1.0 version=EC0 empreinte=4c252b ▼▼▼
from datetime import datetime, timedelta, timezone
import re

def ical_unescape(v):
    return (v or "").replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")

def ical_instant(brut, params, decalage_min):
    """(valeur normalisée, journée entière). VALUE=DATE, UTC suffixé Z (ramené à l'heure locale), heures locales avec TZID : chaînes naïves comme partout ailleurs."""
    brut = (brut or "").strip()
    p = (params or "").upper()
    journee = "VALUE=DATE" in p and "DATE-TIME" not in p
    try:
        if journee or (len(brut) == 8 and brut.isdigit()):
            return datetime.strptime(brut[:8], "%Y%m%d").strftime("%Y-%m-%d"), 1
        if brut.endswith("Z"):
            d = datetime.strptime(brut[:15], "%Y%m%dT%H%M%S")
            d = d + timedelta(minutes=decalage_min)
            return d.strftime("%Y-%m-%d %H:%M"), 0
        return datetime.strptime(brut[:15], "%Y%m%dT%H%M%S").strftime("%Y-%m-%d %H:%M"), 0
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
