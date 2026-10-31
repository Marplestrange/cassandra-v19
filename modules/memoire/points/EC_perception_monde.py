# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Memoire : la perception du monde (référence)
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : EC
# RUNTIME    : python
# VERSION CN : néant
# VERSION EC : EC0 (référence 0.3.0)  #7bad59
# HÔTE CN    : CN_module.py · perception_monde @1.0
# RÔLE       : choisit, parmi les relevés du Sensorium, ceux que la question appelle, et les dit avec leur âge, leur durée de validité, ou « je ne sais plus » quand ils sont périmés.
# MÉTHODE    : fonction pure : une passe sur les relevés, chacun retenu par son préfixe et par ce que la question cite ou évoque ; l'instant est une ENTRÉE, lue par la façade, pour que l'EC ne lise aucune horloge.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE EC point=perception_monde contrat=@1.0 version=EC0 empreinte=7bad59 ▼▼▼
from datetime import datetime, timezone
import re

PERCEPTION_TTL = {"service": 1800, "machine_hors_ligne": 900, "machine_en_ligne": 14400, "site": 7200, "disque": 86400, "ram": 300, "charge": 300, "certificat": 604800,
                  "config": 1800, "logiciel": 10800, "maj": 10800, "montage": 1800, "interface": 600, "stockage": 1800, "systeme": 1800, "port": 600, "machine_flotte": 2700}

# Les motifs de strptime pour « %Y-%m-%d %H:%M:%S » : strptime importe _strptime à son premier appel, import que le filtre des EC refuse.
_HORODATAGE = re.compile(r"(?P<Y>\d\d\d\d)-(?P<m>1[0-2]|0[1-9]|[1-9])-(?P<d>3[0-1]|[1-2]\d|0[1-9]|[1-9]| [1-9])\s+(?P<H>2[0-3]|[0-1]\d|\d):(?P<M>[0-5]\d|\d):(?P<S>6[0-1]|[0-5]\d|\d)")

def age(ts, instant):
    """Âge en secondes d'un horodatage « AAAA-MM-JJ HH:MM:SS » (UTC) ou d'une époque ; None si illisible. `instant` (époque) est une ENTRÉE : l'horloge se lit dans le nexus."""
    if ts in (None, ""):
        return None
    try:
        if isinstance(ts, (int, float)):
            return max(0.0, instant - float(ts))
        g = _HORODATAGE.fullmatch(str(ts).strip().replace("T", " ")[:19])
        if not g:
            raise ValueError(ts)
        d = datetime(int(g["Y"]), int(g["m"]), int(g["d"]), int(g["H"]), int(g["M"]), int(g["S"]), tzinfo=timezone.utc)
        return max(0.0, instant - d.timestamp())
    except ValueError:
        try:
            return max(0.0, instant - float(ts))
        except (TypeError, ValueError):
            return None

def duree_txt(s):
    if s is None:
        return "date inconnue"
    s = int(s)
    if s < 60:
        return "%d s" % s
    if s < 3600:
        return "%d min" % (s // 60)
    if s < 86400:
        return "%d h" % (s // 3600)
    return "%d j" % (s // 86400)

def perception_ligne(nom, etat, ts, ttl, instant):
    a = age(ts, instant)
    if a is None or a > ttl:
        return "· %s : je ne sais plus (dernier relevé %s, valable %s)" % (nom, ("il y a %s" % duree_txt(a)) if a is not None else "jamais", duree_txt(ttl))
    return "· %s : %s (relevé il y a %s, valable %s)" % (nom, etat, duree_txt(a), duree_txt(ttl))

_SYS = {"system.os": ("système", ("os ", "distribution", "debian", "ubuntu", "version du système")),
        "system.uptime": ("uptime", ("uptime", "depuis quand", "allumé depuis", "redémarré")),
        "system.redemarrage_requis": ("redémarrage requis", ("redémarr", "redemarr", "reboot")),
        "system.heure": ("heure système", ("heure", "ntp", "synchronis")),
        "system.temperature": ("température", ("températ", "chauffe", "chaud")),
        "system.batterie": ("batterie", ("batterie",)),
        "system.pare_feu": ("pare-feu", ("pare-feu", "firewall", "parefeu")),
        "system.protection_noyau": ("protection du noyau", ("apparmor", "selinux")),
        "system.tailscale": ("tailscale de cette machine", ("tailscale",)),
        "maj.paquets": ("mises à jour", ("mise à jour", "mises à jour", "mise a jour", "paquet", "apt ", "upgrade")),
        "systemd.failed_units": ("services en échec", ("échec", "echec", "failed", "planté"))}

_FAMILLES = {
    "courriel.": ("courriel", ("file d'attente", "mail bloqu", "mails bloqu", "courriel", "exim", "postfix", "gelé")),
    "ssh.": ("ssh", ("ssh", "intrusion", "connexion ratée", "connexions ratées", "brute")),
    "cle_ssh.": ("clé ssh", ("clé ssh", "cles ssh", "clés ssh", "authorized_keys", "qui peut se connecter")),
    "pare_feu.": ("pare-feu", ("pare-feu", "firewall", "iptables", "nftables")),
    "fail2ban.": ("fail2ban", ("fail2ban", "banni", "bannie")),
    "cron.": ("crons de", ("cron", "tâche planifiée", "tâches planifiées")),
    "fastpanel.": ("fastpanel", ("fastpanel", "compte ftp", "base de données", "bases de données", "boîte mail", "boîtes mail")),
    "erreurs.": ("erreurs de", ("erreur", "plantage", "journal", "journaux", "log")),
    "conteneur_ressources.": ("ressources du conteneur", ("conteneur", "docker", "consomme")),
    "certbot.": ("certbot", ("certbot", "renouvel", "let's encrypt", "letsencrypt")),
    "journaux.": ("journaux", ("journaux", "logs", "journald", "taille des log"))}

def perception_monde(rows, q, deja, instant, limite=12, stricte=False):
    """Les relevés du collecteur (le modèle du monde du sensorium), chacun avec son âge et sa validité. Une entité déjà dite (`deja`) n'est pas redite. En mode strict, seul un nom
    CITÉ compte : c'est le mode des questions qui ne sont pas des questions d'état."""
    q = (q or "").lower()
    out = []

    def cite(nom):
        nom = (nom or "").lower()
        if not nom:
            return False
        variantes = {nom, nom.replace("_", " "), nom.replace("-", " "), nom.replace(".", " ")}
        return any(re.search(r"(?<![\w.-])%s(?![\w-])" % re.escape(v), q) for v in variantes if len(v) >= 3)

    def mot(*mots):
        return (not stricte) and any(m in q for m in mots)

    def ajouter(libelle, etat, ts, ttl):
        if libelle in deja or len(out) >= limite:
            return
        deja.add(libelle)
        out.append(perception_ligne(libelle, etat, ts, ttl, instant))

    for r in rows:
        if not isinstance(r, dict):
            continue
        wk, cat, val, ts = str(r.get("wkey") or ""), str(r.get("category") or ""), str(r.get("value") or ""), r.get("observed_at")
        if r.get("acquit"):
            val += " (acceptée : %s)" % ((r["acquit"] or {}).get("raison") or "sans raison")
        sujet = wk.split(".")[1] if wk.startswith("machine.") and wk.count(".") >= 2 else (wk.split(".", 1)[1] if "." in wk else wk)
        if stricte and not cite(sujet):
            continue
        if wk.startswith("fleet.") and cat == "fleet":
            nom = wk[6:]
            if not q or cite(nom) or "machine" in q or "flotte" in q or "en ligne" in q:
                ajouter("machine %s" % nom, val, ts, PERCEPTION_TTL["machine_en_ligne"] if val.startswith("en ligne") else PERCEPTION_TTL["machine_hors_ligne"])
        elif wk.startswith("web."):
            if not q or cite(wk[4:]) or "site" in q:
                ajouter("site %s" % wk[4:], val, ts, PERCEPTION_TTL["site"])
        elif wk.startswith("ssl."):
            if "certificat" in q or "ssl" in q or "tls" in q or cite(wk[4:]):
                ajouter("certificat %s" % wk[4:], val.replace(" jours", " jours restants"), ts, PERCEPTION_TTL["certificat"])
        elif wk.startswith("service.") or wk.startswith("docker."):
            nom = wk.split(".", 1)[1]
            if cite(nom) or "service" in q or ("conteneur" in q and wk.startswith("docker.")) or ("docker" in q and wk.startswith("docker.")):
                ajouter(("conteneur %s" if wk.startswith("docker.") else "service %s") % nom, val, ts, PERCEPTION_TTL["service"])
        elif wk == "disk./.usage":
            if not q or any(w in q for w in ("disque", "espace", "disk", "libre", "plein")):
                ajouter("disque", val + " utilisé", ts, PERCEPTION_TTL["disque"])
        elif wk in ("ram.usage", "swap.usage"):
            if "ram" in q or "mémoire vive" in q or "memoire vive" in q or "swap" in q:
                ajouter("RAM" if wk == "ram.usage" else "swap", val + " utilisée", ts, PERCEPTION_TTL["ram"])
        elif wk in ("cpu.load", "load.1m"):
            if "charge" in q or "cpu" in q or "load" in q:
                ajouter("charge" if wk == "load.1m" else "processeur", ("load1 %s" % val) if wk == "load.1m" else val, ts, PERCEPTION_TTL["charge"])
        elif wk.startswith("config."):
            cle = wk[7:]
            if cite(cle) or (cle == "fichier" and mot("config.json", "configuration de cassandra", "fichier de config")):
                ajouter("réglage %s" % cle if cle != "fichier" else "fichier de config de Cassandra", val, ts, PERCEPTION_TTL["config"])
        elif wk.startswith("logiciel."):
            if cite(wk[9:]):
                ajouter("logiciel %s" % wk[9:], val, ts, PERCEPTION_TTL["logiciel"])
        elif wk.startswith("montage."):
            mp = wk[8:]
            if (mp != "/" and cite(mp)) or mot("montage", "monté", "partition", "inode", "systèmes de fichiers", "disques"):
                ajouter("système de fichiers %s" % mp, val, ts, PERCEPTION_TTL["montage"])
        elif wk.startswith("interface."):
            if cite(wk[10:]) or mot("interface", "réseau local", "adresse ip", "wifi", "wi-fi", "ethernet"):
                ajouter("interface %s" % wk[10:], val, ts, PERCEPTION_TTL["interface"])
        elif wk.startswith("stockage."):
            if cite(wk[9:]) or mot("raid", "zfs", "pool", "miroir", "mdadm"):
                ajouter("stockage %s" % wk[9:], val, ts, PERCEPTION_TTL["stockage"])
        elif wk.startswith("port."):
            if (cite(wk[5:]) and "port" in q) or mot("ports ouverts", "port ouvert", "écoute sur", "ports à l'écoute"):
                ajouter("port %s" % wk[5:], "à l'écoute (%s)" % val, ts, PERCEPTION_TTL["port"])
        elif wk.startswith("machine.") and wk.count(".") >= 2:
            m_, cle = wk.split(".", 2)[1], wk.split(".", 2)[2]
            if cite(m_):
                ajouter("%s · %s" % (m_, cle.replace("_", " ")), val, ts, PERCEPTION_TTL["machine_flotte"])
        elif any(wk.startswith(p_) for p_ in _FAMILLES):
            p_ = next(p_ for p_ in _FAMILLES if wk.startswith(p_))
            libelle, mots = _FAMILLES[p_]
            if cite(wk[len(p_):]) or mot(*mots):
                ajouter("%s %s" % (libelle, wk[len(p_):].replace("_", " ")), val, ts, PERCEPTION_TTL["systeme"])
        elif wk in _SYS:
            libelle, mots = _SYS[wk]
            if mot(*mots):
                ajouter(libelle, val, ts, PERCEPTION_TTL["systeme"])
    return out

def point_perception_monde(entree):
    """Le point d'évolution `perception_monde` (contrat 1.0) : les relevés du collecteur, la question, les libellés déjà dits et l'instant en entrée ; les lignes dites et les libellés dits en sortie."""
    deja = set(entree["deja"])
    lignes = perception_monde(entree["lignes"], entree["question"], deja, entree["maintenant"], entree["limite"], entree["stricte"])
    return {"lignes": lignes, "deja": sorted(deja)}

# ▲▲▲ FIN BORNE EC ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# EC : `point_perception_monde(entree)` est le point d'évolution. Les fonctions du fichier d'origine dont il dépend sont COPIÉES ici : une EC ne peut importer que la bibliothèque standard pure.
#      L'évolution peut en remplacer le corps ; elle ne peut changer ni la signature ni la forme de la sortie.
# CN : appelée par la façade de memoire (CN_module.py) par ctx.point, qui ne transmet que les champs utiles.
# LIEN : contrat dans contrats/CN_perception_monde.json ; corpus doré dans contrats/CN_perception_monde.corpus.json (sorties de l'ancien code, données synthétiques).
