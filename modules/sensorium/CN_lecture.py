# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La lecture du Sensorium : dire une mesure en français, ranger le monde, appliquer ce qui est accepté
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sensorium
# ZONE       : CN
# VERSION CN : 0.1.12  #a08e08
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La lecture du Sensorium, sans contexte : le nom d'une mesure en français, son domaine et son objet, les alertes acceptées, les fenêtres de maintenance.
# MÉTHODE    : des fonctions pures sur des listes de lignes {wkey, value, severity…} : le module (CN_module.py) leur donne les lignes du collecteur et les lignes de sa base ; rien ici ne touche au disque, au réseau ni à l'horloge.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.12 empreinte=a08e08 ▼▼▼
"""La lecture du Sensorium : tout ce que l'écran dit d'une mesure vient d'ici, et rien ici n'a d'effet de bord.

Une ligne du collecteur est {wkey, value, severity, observed_at, detail}. Sa clé (« ssl.exemple.org », « service.nginx ») dit sa famille ; la famille dit son domaine ;
le reste de la clé dit l'objet dont elle parle (un site, une machine, un service) : c'est ce qui permet de regarder un objet plutôt qu'un capteur.
"""
import re

# La famille d'une mesure : (identifiant, libellé, préfixes de clé). L'ordre est celui de l'écran.
FAMILLES = (
    ("system", "Système", ("system.",)), ("ressources", "Ressources", ("cpu.", "ram.", "swap.", "load.", "disk.", "montage.")),
    ("service", "Services", ("service.", "systemd.")), ("docker", "Conteneurs", ("docker.", "conteneur_ressources.", "image.")),
    ("web", "Sites", ("web.",)), ("controle", "Contrôles de bout en bout", ("controle.",)), ("ssl", "Certificats", ("ssl.",)),
    ("sauvegarde", "Sauvegardes", ("sauvegarde.",)), ("prevision", "Ce qui va arriver", ("prevision.",)), ("flotte", "Flotte", ("fleet.", "machine.")),
    ("config", "Config de Cassandra", ("config.",)), ("logiciel", "Logiciels", ("logiciel.",)), ("reseau", "Réseau", ("interface.", "port.")),
    ("stockage", "Stockage", ("stockage.",)), ("securite", "Sécurité", ("security.",)), ("maj", "Mises à jour", ("maj.",)),
    ("courriel", "Courriel", ("courriel.", "domaine_courriel.")), ("acces", "Accès et pare-feu", ("ssh.", "cle_ssh.", "pare_feu.", "fail2ban.", "prison.")),
    ("cron", "Tâches planifiées", ("cron.",)), ("fastpanel", "FastPanel", ("fastpanel.",)), ("erreurs", "Erreurs des journaux", ("erreurs.", "journaux.")),
    ("certbot", "Renouvellement des certificats", ("certbot.",)), ("box", "La box", ("box.", "dns_local")), ("outils", "Outils de sécurité", ("outil_secu.",)),
    ("tailnet", "Tailnet", ("tailnet.",)), ("capteur", "Capteurs", ("capteur.",)), ("sante", "Santé", ("health.",)),
    ("noyau", "Noyau de Cassandra", ("noyau.", "module_noyau.", "cassandra.")), ("store", "Bases de Cassandra", ("store.",)),
    ("code", "Code scellé", ("code.",)), ("courtier", "Courtier racine", ("courtier.",)),
)
# Les domaines : ce que l'écran propose pour parcourir (six, au lieu de trente familles à plat).
DOMAINES = (
    ("machine", "Machine", ("system", "ressources", "stockage", "maj", "logiciel", "erreurs", "prevision")),
    ("services", "Services et sites", ("service", "docker", "web", "controle", "fastpanel", "cron")),
    ("securite", "Sécurité et accès", ("securite", "acces", "outils")),
    ("certificats", "Certificats et sauvegardes", ("ssl", "certbot", "sauvegarde")),
    ("reseau", "Réseau et flotte", ("reseau", "box", "tailnet", "flotte", "courriel")),
    ("cassandra", "Cassandra elle-même", ("config", "capteur", "sante", "noyau", "store", "code", "courtier")),
)


def famille_de(wkey) -> str:
    w = str(wkey or "")
    for fid, _, prefixes in FAMILLES:
        if any(w.startswith(p) for p in prefixes):
            return fid
    return "autre"


def libelle_famille(fid) -> str:
    return next((l for i, l, _ in FAMILLES if i == fid), str(fid))


def domaine_de(fid) -> str:
    return next((d for d, _, fs in DOMAINES if fid in fs), "autre")


# ---------- dire une mesure ----------
MOTS = {"wifi": "Wi-Fi", "socle": "socle (parc, Docker, réponses)", "partage": "partage et Funnel", "appareils": "appareils",
        "echecs au demarrage": "échecs au démarrage (avant l'horloge)", "acces distant": "accès distant à Freebox OS", "upnp": "UPnP", "dmz": "DMZ", "ftp": "FTP",
        "vpn": "VPN", "systeme": "système", "connexion": "connexion", "redirections": "redirections de ports", "en echec": "en échec", "mises a jour": "mises à jour",
        "hors machine": "hors machine", "redemarrage requis": "redémarrage requis", "protection noyau": "protection du noyau", "ipv4": "IPv4", "ipv6": "IPv6",
        "file attente": "file d'attente", "echecs": "échecs", "etat": "état", "paquets": "paquets", "usage": "occupation", "load": "charge", "score": "score",
        "fuseau": "fuseau horaire", "heure": "heure", "disque": "disque", "temperature": "température", "uptime": "allumée depuis", "os": "système"}
NOMS = {"service": "Service", "docker": "Conteneur", "web": "Site", "ssl": "Certificat", "machine": "Machine", "sauvegarde": "Sauvegarde", "montage": "Disque",
        "stockage": "Stockage", "controle": "Contrôle", "capteur": "Capteur", "prevision": "Prévision", "courriel": "Courriel", "ssh": "SSH", "erreurs": "Erreurs",
        "conteneur_ressources": "Conteneur", "system": "Système", "systemd": "Systemd", "maj": "Mises à jour", "pare_feu": "Pare-feu", "fleet": "Flotte",
        "trafic": "Trafic", "health": "Santé", "security": "Noyau", "ram": "Mémoire", "cpu": "Processeur", "swap": "Mémoire d'échange", "disk": "Disque", "load": "Charge",
        "port": "Port", "interface": "Interface", "logiciel": "Logiciel", "config": "Réglage", "cle_ssh": "Clé SSH", "fail2ban": "Fail2ban", "cron": "Tâche planifiée",
        "fastpanel": "FastPanel", "journaux": "Journaux", "mysql": "MySQL", "cassandra": "Cassandra", "certbot": "Certbot", "exposition": "Exposition",
        "disque_sante": "Santé du disque", "php_fpm": "PHP-FPM", "box": "Box", "tailnet": "Tailnet", "prison": "Prison fail2ban", "domaine_courriel": "Courriel du domaine",
        "image": "Image du conteneur", "dns_local": "DNS local de la maison", "noyau": "Noyau", "store": "Base", "code": "Code", "courtier": "Courtier"}


def mots(t: str) -> str:
    """Les mots d'une clé, accentués : une expression connue entière, sinon chaque expression de plusieurs mots."""
    if t in MOTS:
        return MOTS[t]
    for k, v in MOTS.items():
        if " " in k and k in t:
            t = t.replace(k, v)
    return t


def libelle(wkey) -> str:
    """Le nom d'une mesure en français : « Athena — services en échec », « Pare-feu IPv4 »."""
    wkey = str(wkey or "")
    fam, _, reste = wkey.partition(".")
    if not reste:
        return NOMS.get(fam, wkey)
    if fam == "machine":
        m, _, quoi = reste.partition(".")
        quoi = quoi.replace("_", " ")
        return "%s — %s" % (m.capitalize(), mots(quoi)) if quoi else m.capitalize()
    if fam == "tailnet" and reste.startswith("nouveau."):
        return "Tailnet — nouvel appareil %s" % reste.split(".", 1)[1]
    if fam == "outil_secu":
        return {"lynis": "Lynis — audit de durcissement", "trivy": "Trivy — failles des images Docker", "clamav": "ClamAV — antivirus",
                "crowdsec": "CrowdSec — attaquants bloqués"}.get(reste, "Outil de sécurité " + reste)
    if fam in ("prison", "domaine_courriel", "image"):
        return "%s %s" % (NOMS[fam], reste)
    if fam == "box" and reste.startswith("appareil."):
        return "Box — nouvel appareil sur le réseau"
    if fam == "box" and reste.startswith("redirection."):
        p = reste.split(".", 1)[1].split("_", 1)
        return "Box — redirection %s %s" % (p[0].upper(), p[1] if len(p) > 1 else "")
    if fam == "store" and reste.startswith("module."):
        return "Base du module %s" % reste.split(".", 1)[1]
    r = reste.replace("_", " ")
    return "%s %s" % (NOMS.get(fam, fam.capitalize()), mots(r))


# ---------- l'objet dont une mesure parle ----------
GENRES = ("Machines", "Sites", "Services", "Conteneurs", "Comptes et clés SSH", "Domaines de courriel", "Cassandra")
LOCALES = {"system", "ressources", "stockage", "maj", "logiciel", "erreurs", "reseau", "securite", "cron", "prevision"}      # ce qui parle de la machine qui porte le Sensorium


def objet_de(wkey, hote="") -> tuple:
    """(genre, nom) de l'objet dont parle une mesure, ou None : un site, une machine, un service, un conteneur, un compte, un domaine de courriel, Cassandra."""
    w = str(wkey or "")
    fam, _, reste = w.partition(".")
    if fam == "service" and reste:
        return ("Services", reste.replace(".service", ""))
    if fam in ("docker", "conteneur_ressources", "image") and reste:
        return ("Conteneurs", reste)
    if fam in ("web", "controle") and reste:
        return ("Sites", reste.split(".")[0] if fam == "controle" and "." not in reste else reste)
    if fam == "ssl" and reste:
        return ("Sites", reste[2:] if reste.startswith("*.") else reste)
    if fam == "machine" and reste:
        return ("Machines", reste.split(".", 1)[0])
    if fam == "fleet" and reste:
        return ("Machines", reste)
    if fam == "cle_ssh" and reste:
        return ("Comptes et clés SSH", reste.split(".", 1)[0])
    if fam == "domaine_courriel" and reste:
        return ("Domaines de courriel", reste)
    if fam in ("noyau", "module_noyau", "store", "code", "courtier", "cassandra"):
        return ("Cassandra", {"noyau": "le noyau", "module_noyau": "les modules", "store": "les bases", "code": "le code", "courtier": "le courtier", "cassandra": "le noyau"}[fam])
    if famille_de(w) in LOCALES and hote:
        return ("Machines", hote)
    return None


# ---------- ce qui est accepté ----------
def nombre(v):
    m = re.search(r"-?\d+(?:[.,]\d+)?", str(v or ""))
    return float(m.group(0).replace(",", ".")) if m else None


def acquis(row: dict, acq: dict) -> bool:
    """Acceptée, et pas pire qu'au moment où on l'a acceptée (un chiffre qui monte la fait revenir)."""
    if not acq:
        return False
    avant, maintenant = nombre(acq.get("valeur")), nombre(row.get("value"))
    if avant is not None and maintenant is not None:
        return maintenant <= avant
    return str(acq.get("valeur") or "") == str(row.get("value") or "")


def appliquer_acquits(rows: list, acquits: dict) -> list:
    """Une alerte acceptée se lit « acceptée : raison » et ne compte plus comme alerte ; les autres lignes passent telles quelles."""
    sortie = []
    for r in rows:
        if isinstance(r, dict) and r.get("severity") == "warning" and acquis(r, acquits.get(str(r.get("wkey") or ""))):
            a = acquits[str(r.get("wkey"))]
            r = dict(r, severity="info", acquit={"raison": a.get("raison") or "", "jusqua": a.get("jusqua") or "", "par": a.get("par") or ""})
        sortie.append(r)
    return sortie


# ---------- les fenêtres de maintenance ----------
def dans_fenetre(wkey, fenetres, maintenant: str, hote="") -> dict:
    """La fenêtre (dict) qui couvre cette mesure à cet instant, ou None. Une portée : « * » (tout), « famille:<id> », « machine:<nom> », « domaine:<id> ».
    Les instants sont des textes « AAAA-MM-JJ HH:MM:SS » comparables tels quels."""
    fam = famille_de(wkey)
    obj = objet_de(wkey, hote)
    for f in fenetres or []:
        if not (str(f.get("debut") or "") <= maintenant < str(f.get("fin") or "9999")):
            continue
        p = str(f.get("portee") or "")
        if p in ("*", "") or (p.startswith("famille:") and p[8:] == fam) or (p.startswith("domaine:") and p[8:] == domaine_de(fam)) \
                or (p.startswith("machine:") and obj and obj[0] == "Machines" and obj[1].lower() == p[8:].lower()):
            return f
    return None


def lignes_du_monde(brut) -> list:
    """Les lignes {wkey,…} d'une réponse GET_WORLD : une liste, ou un objet qui la porte."""
    if isinstance(brut, list):
        return [r for r in brut if isinstance(r, dict) and r.get("wkey")]
    if isinstance(brut, dict):
        for k in ("rows", "monde", "entites", "lignes"):
            if isinstance(brut.get(k), list):
                return lignes_du_monde(brut[k])
    return []
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : FAMILLES, DOMAINES, libelle, objet_de, acquis, dans_fenetre
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : CN_module.py (qui s'en sert), docs/maquettes/CN_maquette-sensorium.html (ce que l'écran en fait)
