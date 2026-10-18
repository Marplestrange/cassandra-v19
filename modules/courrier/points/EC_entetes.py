# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Courrier : la lecture des en-têtes (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : courrier
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #a9005f
# HÔTE CN    : CN_module.py · entetes @1.0
# RÔLE       : transforme les en-têtes d'une réponse IMAP en lignes de cache (expéditeur, objet, date normalisée, fil, drapeaux, pièce jointe, taille) et en lignes d'écran (avec le motif technique et l'état à traiter).
# MÉTHODE    : fonctions pures : le nexus lit le serveur ; chaque en-tête est décodé, la date normalisée en UTC triable, le fil tiré des références ; un message technique reste technique même répondu.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=entetes contrat=@1.0 version=EC0 empreinte=a9005f ▼▼▼
import base64
from email.header import decode_header
import email
from email.utils import parseaddr, parsedate_to_datetime
import re
from datetime import timezone

def decoder_entete(s):
    if s is None:
        return ""
    try:
        sortie = ""
        for txt, enc in decode_header(str(s)):
            sortie += txt.decode(enc or "utf-8", errors="replace") if isinstance(txt, bytes) else txt
        return sortie
    except Exception:
        return str(s)

def date_iso(brut):
    """Date normalisée et TRIABLE : les en-têtes Date arrivent dans une dizaine de formats et de fuseaux, trier la chaîne brute mélangerait janvier et juillet."""
    if not brut:
        return ""
    try:
        d = parsedate_to_datetime(brut)
        if d is None:
            return ""
        if d.tzinfo is not None:
            d = d.astimezone(timezone.utc).replace(tzinfo=None)
        return d.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""

def adresse_parts(brut):
    """(nom affiché, adresse en minuscules) d'un en-tête From/To."""
    try:
        nom, adr = parseaddr(decoder_entete(brut))
        adr = (adr or "").strip().lower()
        return (nom or "").strip() or (adr.split("@")[0] if adr else ""), adr
    except Exception:
        return str(brut or ""), ""

def cle_de_fil(msg):
    """La racine des References, sinon In-Reply-To, sinon l'identifiant du message, sinon l'objet normalisé : l'objet seul regrouperait à tort tous les « Re: facture »."""
    refs = (msg.get("References") or "").split()
    if refs:
        return refs[0].strip()[:200]
    for entete in ("In-Reply-To", "Message-ID"):
        v = (msg.get(entete) or "").strip()
        if v:
            return v[:200]
    suj = re.sub(r"^\s*((re|fwd|tr|fw)\s*:\s*)+", "", decoder_entete(msg.get("Subject")), flags=re.I).strip().lower()
    return ("suj:" + suj)[:200] if suj else ""

TECH_EXP = re.compile(r"(certbot|let'?s\s*encrypt|cron|logwatch|monit|nagios|zabbix|netdata|fail2ban|backup|borg|restic|rsnapshot|mdadm|smartd|unattended-upgrades|postmaster|mailer-daemon|no-?reply@|root@|admin@)", re.I)

TECH_SUJ = re.compile(r"(cron\s*<|certificat|certificate|expir|renew|sauvegarde|backup|disk\s*(space|usage)|s\.m\.a\.r\.t|raid|degraded|failed|échec|erreur\s*serveur|security\s*update|reboot required|anacron|logwatch)", re.I)

def motif_technique(m):
    """Motif technique reconnu, ou ''. Un signal sur l'EXPÉDITEUR est exigé : « sauvegarde » dans l'objet d'un client parle d'un devis, pas d'un serveur."""
    exp, suj = m.get("from_addr") or m.get("from") or "", m.get("subject") or ""
    if TECH_EXP.search(exp):
        return "expéditeur technique"
    if TECH_SUJ.search(suj) and TECH_EXP.search(exp + " " + suj):
        return "objet et expéditeur techniques"
    return ""

def etat_du_message(m):
    """« tech », « attente » ou « traiter ». L'ORDRE COMPTE : un message technique auquel on a répondu reste technique, c'est sa nature qui décide."""
    if motif_technique(m):
        return "tech"
    return "attente" if m.get("answered") else "traiter"

def lignes_cache(items):
    """{uid: ligne de cache} d'après une réponse FETCH d'en-têtes : chaque item porte la méta de la réponse (texte) et les en-têtes bruts (base64)."""
    sortie = {}
    for item in items or []:
        meta = item["meta"]
        mu = re.search(r"UID (\d+)", meta)
        if not mu:
            continue
        msg = email.message_from_bytes(base64.b64decode(item["raw"]))
        nom, adr = adresse_parts(msg.get("From"))
        brut = decoder_entete(msg.get("Date"))
        sortie[mu.group(1)] = {
            "uid": mu.group(1), "msg_id": (msg.get("Message-ID") or "").strip()[:200], "fil": cle_de_fil(msg), "de_addr": adr, "de_nom": nom,
            "a_addr": (decoder_entete(msg.get("To")) or "")[:300], "objet": decoder_entete(msg.get("Subject")) or "(sans objet)", "date_brute": brut, "date_iso": date_iso(brut),
            "lu": 1 if "\\Seen" in meta else 0, "suivi": 1 if "\\Flagged" in meta else 0, "repondu": 1 if "\\Answered" in meta else 0,
            "pj": 1 if re.search(r'attachment|"name"|filename', meta, re.I) else 0, "taille": int((re.search(r"RFC822\.SIZE (\d+)", meta) or [0, 0])[1] or 0)}
    return sortie

def ligne_message(v):
    m = {"uid": v["uid"], "de": ("%s <%s>" % (v["de_nom"], v["de_addr"])).strip(), "de_nom": v["de_nom"], "de_addr": v["de_addr"], "objet": v["objet"], "date": v["date_brute"],
         "date_iso": v["date_iso"], "lu": bool(v["lu"]), "suivi": bool(v["suivi"]), "repondu": bool(v["repondu"]), "pj": bool(v["pj"]), "taille": v["taille"], "fil": v.get("fil", "")}
    m["technique"] = motif_technique({"from_addr": v["de_addr"], "subject": v["objet"]})
    m["etat"] = etat_du_message({"from_addr": v["de_addr"], "subject": v["objet"], "answered": v["repondu"]})
    return m

def point_entetes(entree):
    """Le point d'évolution `entetes` (contrat 1.0) : la lecture des en-têtes d'une boîte, en trois opérations. « cache » : les réponses FETCH (méta et en-têtes bruts en base64) en entrée, les lignes du cache en sortie.
    « ligne » : une ligne du cache en entrée, la ligne que lit l'écran en sortie. « etat » : un message en entrée, son état (tech, attente, traiter) en sortie."""
    op = entree["op"]
    if op == "cache":
        return {"valeur": lignes_cache(entree["items"])}
    if op == "ligne":
        return {"valeur": ligne_message(entree["v"])}
    if op == "etat":
        return {"valeur": etat_du_message(entree["m"])}
    raise ValueError("opération inconnue : %s" % op)

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_entetes(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de courrier (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_entetes.json ; corpus doré dans contrats/CN_entetes.corpus.json (sorties de l'ancien code, données synthétiques).
