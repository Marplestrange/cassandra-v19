# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La flotte
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : flotte
# ZONE       : CN
# VERSION CN : 0.1.1  #1a8f97
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La flotte : les fonctions pures (noms, durées, lecture des sondes, fusion du parc, verdict) et l'accès au monde (Tailscale, SSH, TCP, HTTP).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=1a8f97 ▼▼▼
"""La flotte : les fonctions pures (noms, durées, lecture des sondes, fusion du parc, verdict) et l'accès au monde (Tailscale, SSH, TCP, HTTP).

Tout ce qui touche le réseau ou un binaire passe par la classe `Acces` : un banc la remplace, rien d'autre ne sort du module.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shlex
import socket
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

NIVEAUX = ("signal", "observation", "ssh", "agent")
STATUTS = ("attendue", "intermittente", "retiree")
TYPES = ("ssh", "ping", "cassandra")
OUBLI_JOURS = 30
LIENS = ("project", "contact", "domain", "note")
RE_SERVICE = re.compile(r"^[A-Za-z0-9@_.:-]{1,80}$")
SERVICES_VITAUX = {"ssh", "sshd", "network", "networking", "systemd-networkd", "NetworkManager", "systemd-journald"}

# Des commandes NOMMÉES, jamais un terminal libre : (gabarit, modifie, description)
ACTIONS = {
    "diagnostic": ("uptime; echo '---'; df -h; echo '---'; free -m; echo '---'; systemctl --failed --no-pager 2>/dev/null | head -20", False, "Charge, disques, mémoire et unités en échec."),
    "disques": ("df -h", False, "Occupation des systèmes de fichiers."),
    "memoire": ("free -m; echo '---'; ps aux --sort=-%mem | head -12", False, "Mémoire et les douze processus les plus gourmands."),
    "services": ("systemctl list-units --type=service --state=running --no-pager | head -40", False, "Services en cours d'exécution."),
    "journal": ("journalctl -n 120 --no-pager -o short-iso 2>/dev/null || tail -n 120 /var/log/syslog", False, "Dernières lignes du journal système."),
    "reseau": ("ip -brief addr 2>/dev/null || ifconfig; echo '---'; ss -tulpn 2>/dev/null | head -30", False, "Adresses et ports en écoute."),
    "svc_restart": ("systemctl restart %(service)s && systemctl status %(service)s --no-pager | head -20", True, "Redémarre un service."),
    "svc_start": ("systemctl start %(service)s && systemctl status %(service)s --no-pager | head -20", True, "Démarre un service."),
    "svc_stop": ("systemctl stop %(service)s && systemctl status %(service)s --no-pager | head -20", True, "Arrête un service."),
    "svc_status": ("systemctl status %(service)s --no-pager | head -30", False, "État détaillé d'un service."),
}

SONDE_SSH = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=5", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "IdentitiesOnly=yes",
             "-o", "IdentityFile=none", "-o", "PasswordAuthentication=no", "-o", "KbdInteractiveAuthentication=no", "-o", "LogLevel=ERROR"]

SONDE_LINUX = r"""
df -P -x tmpfs -x devtmpfs -x overlay -x squashfs 2>/dev/null | awk 'NR>1 && $6 !~ /^\/(snap|run|tmp|dev|boot\/efi)/ {print "DISK " $6 " " $5 " " int($4/1048576)}'
awk '/^MemTotal/{t=$2} /^MemAvailable/{a=$2} /^MemFree/{f=$2} /^Buffers/{b=$2} /^Cached/{c=$2} END{if(!a) a=f+b+c; if(t) printf "RAM %.0f\n", (t-a)/t*100}' /proc/meminfo 2>/dev/null
echo "UP $(cut -d. -f1 /proc/uptime 2>/dev/null)"
echo "LOAD $(cut -d' ' -f1 /proc/loadavg 2>/dev/null) $(nproc 2>/dev/null)"
[ -f /var/run/reboot-required ] && echo "REBOOT oui" || echo "REBOOT non"
command -v systemctl >/dev/null 2>&1 && { f=""; for u in $(systemctl list-units --state=failed --no-legend --plain 2>/dev/null | awk '{print $1}'); do f="$f $u"; done; echo "FAILED$f"; }
grep -h '^PRETTY_NAME=' /etc/os-release 2>/dev/null | cut -d= -f2 | tr -d '"' | sed 's/^/OS /'
grep -E '^md[0-9]+' -A1 /proc/mdstat 2>/dev/null | grep -o '\[[U_]*\]' | tr '\n' ' ' | sed 's/^/RAID /'; echo
for f in /sys/class/thermal/thermal_zone*/temp; do [ -r "$f" ] && cat "$f"; done 2>/dev/null | sort -n | tail -1 | sed 's/^/TEMP /'
"""
SONDE_WINDOWS = r"""
$ErrorActionPreference='SilentlyContinue'
Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object { if($_.Size){ 'DISK {0} {1}% {2}' -f $_.DeviceID, [math]::Round(100-100*$_.FreeSpace/$_.Size), [math]::Round($_.FreeSpace/1GB) } }
$os=Get-CimInstance Win32_OperatingSystem
'RAM {0}' -f [math]::Round(100*($os.TotalVisibleMemorySize-$os.FreePhysicalMemory)/$os.TotalVisibleMemorySize)
'UP {0}' -f [int]((Get-Date)-$os.LastBootUpTime).TotalSeconds
'OS {0} {1}' -f $os.Caption, $os.Version
$h = Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1
if($h.InstalledOn){ 'WU {0}' -f [int]((Get-Date)-$h.InstalledOn).TotalDays }
"""


def utc():
    return datetime.now(timezone.utc)


def horodate(d=None):
    return (d or utc()).strftime("%Y-%m-%d %H:%M:%S")


def nom(s):
    """Le nom canonique : minuscule, premier segment d'un nom DNS, sans espace."""
    s = str(s or "").strip().lower()
    return s.split(".")[0] if s else ""


def minutes_entre(a, b):
    try:
        return max(0, int((datetime.strptime(str(b)[:19], "%Y-%m-%d %H:%M:%S") - datetime.strptime(str(a)[:19], "%Y-%m-%d %H:%M:%S")).total_seconds() // 60))
    except Exception:
        return 0


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)


def duree(m):
    """duree. Le calcul est un POINT D'ÉVOLUTION : points/EC_duree.py."""
    return _point("duree", {"m": m})["valeur"]


def commande_sonde(windows):
    if windows:
        return "powershell -NoProfile -EncodedCommand " + base64.b64encode(SONDE_WINDOWS.encode("utf-16-le")).decode()
    return "sh -c " + shlex.quote(SONDE_LINUX)


def lire_sortie(sortie, appeler):
    """La sortie d'une sonde -> [(clé, valeur, gravité)] : disque.<point>, ram, uptime, charge, redemarrage_requis, services_en_echec, os, raid, temperature, mises_a_jour. Le calcul est un POINT D'ÉVOLUTION : points/EC_lire_sortie.py."""
    return appeler("lire_sortie", {"sortie": sortie})["valeur"]


def lire_metriques(sortie, appeler):
    """La sortie CPU:/RAM:/DISK:/HOST:/KERN:/UP: des machines du registre -> dict. Le calcul est un POINT D'ÉVOLUTION : points/EC_lire_metriques.py."""
    return appeler("lire_metriques", {"sortie": sortie})["valeur"]


COMMANDE_METRIQUES = (
    r"""printf 'CPU:%s\n' $(top -bn1 2>/dev/null | awk '/Cpu/{gsub(/[^0-9.]/," "); t+=$1+$2+$3; n++} END{printf "%.1f",t/n}'); """
    r"""printf 'RAM:%s\n' $(free 2>/dev/null | awk '/Mem/{printf "%.1f",$3/$2*100}'); """
    r"""printf 'DISK:%s\n' $(df / 2>/dev/null | awk 'NR==2{gsub(/%/,"");print $5}'); """
    r"""printf 'HOST:%s\n' $(hostname 2>/dev/null); printf 'KERN:%s\n' $(uname -r 2>/dev/null); printf 'UP:%s\n' $(uptime -p 2>/dev/null | head -c60)"""
)


def mesure(v):
    """Une mesure réellement rapportée, ou None : zéro n'est pas une mesure (un ping ne mesure pas de processeur)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


# ------------------------------------------------------------------ l'accès au monde
class Acces:
    """Tailscale, SSH, TCP, HTTP. Un banc remplace ces méthodes ; en service, ce sont des binaires et des sockets."""

    def __init__(self):
        self._cache = {"t": 0.0, "d": None}

    def tailscale_live(self):
        """`tailscale status --json`, 30 s de cache : nom -> {online, os, ip, last_seen, self}. Une absence de binaire rend {} : jamais un faux « en ligne »."""
        import time
        now = time.time()
        if self._cache["d"] is not None and now - self._cache["t"] < 30:
            return self._cache["d"]
        out = {}
        try:
            r = subprocess.run(["tailscale", "status", "--json"], capture_output=True, text=True, timeout=6)
            d = json.loads(r.stdout or "{}")
            me = d.get("Self") or {}
            if me:
                out[nom(me.get("HostName") or me.get("DNSName"))] = {"online": True, "os": me.get("OS", ""), "ip": (me.get("TailscaleIPs") or [""])[0], "last_seen": "", "self": True, "observe": horodate()}
            for p in (d.get("Peer") or {}).values():
                n = nom(p.get("DNSName") or p.get("HostName"))
                if not n:
                    continue
                ls = str(p.get("LastSeen") or "")
                out[n] = {"online": bool(p.get("Online")), "os": p.get("OS", ""), "ip": (p.get("TailscaleIPs") or [""])[0],
                          "last_seen": "" if ls.startswith("0001") else ls[:19].replace("T", " "), "self": False, "observe": horodate()}
            out["_sante"] = [str(x) for x in (d.get("Health") or [])][:4]
        except Exception:
            pass
        self._cache.update(t=now, d=out)
        return out

    def tailscale_ping(self, ip):
        r = subprocess.run(["tailscale", "ping", "-c", "3", "--timeout", "2s", ip], capture_output=True, text=True, timeout=9)
        return (r.stdout or "") + (r.stderr or "")

    def ssh_sonde(self, ip, user="root", timeout=12):
        """SANS CLÉ NI MOT DE PASSE : `ssh` en mode batch, aucune identité. Ne réussit que si l'autre bout authentifie autrement (Tailscale SSH signe par le nœud). -> (ok, détail)"""
        if not ip:
            return False, "adresse inconnue"
        try:
            r = subprocess.run(["ssh"] + SONDE_SSH + ["%s@%s" % (user, ip), "true"], capture_output=True, text=True, timeout=timeout)
        except FileNotFoundError:
            return False, "ssh absent de l'hôte"
        except subprocess.TimeoutExpired:
            return False, "sans réponse en %d s" % timeout
        if r.returncode == 0:
            return True, "Tailscale SSH · %s" % user
        return False, " ".join((r.stderr or "").split())[:160] or ("code %s" % r.returncode)

    def ssh_exec(self, m, cmd, timeout=30):
        """Une commande sur une machine : m = {hote, port, utilisateur, auth, cle, mot_de_passe}. -> (stdout, stderr, code)"""
        hote, port, user, auth = m.get("hote", ""), str(int(m.get("port") or 22)), m.get("utilisateur") or "root", m.get("auth") or "tailscale"
        cible = "%s@%s" % (user, hote)
        try:
            if auth == "tailscale":
                r = subprocess.run(["ssh"] + SONDE_SSH + ["-p", port, cible, cmd], capture_output=True, text=True, timeout=timeout)
                return r.stdout, r.stderr, r.returncode
            base = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=12", "-o", "ServerAliveInterval=10", "-p", port]
            if auth == "cle" and m.get("cle"):
                with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as kf:
                    kf.write(m["cle"])
                    chemin = kf.name
                os.chmod(chemin, 0o600)
                try:
                    r = subprocess.run(base + ["-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-i", chemin, cible, cmd], capture_output=True, text=True, timeout=timeout)
                finally:
                    try:
                        os.unlink(chemin)
                    except OSError:
                        pass
                return r.stdout, r.stderr, r.returncode
            if auth == "mot_de_passe" and m.get("mot_de_passe"):
                sshpass = subprocess.run(["which", "sshpass"], capture_output=True, text=True).stdout.strip()
                if not sshpass:
                    return "", "sshpass est absent de l'hôte : un mot de passe SSH ne peut pas être passé", 127
                env = dict(os.environ, SSHPASS=m["mot_de_passe"])           # par l'environnement, jamais dans la ligne de commande
                r = subprocess.run([sshpass, "-e"] + base + [cible, cmd], capture_output=True, text=True, timeout=timeout, env=env)
                return r.stdout, r.stderr, r.returncode
            r = subprocess.run(base + ["-o", "BatchMode=yes", cible, cmd], capture_output=True, text=True, timeout=timeout)
            return r.stdout, r.stderr, r.returncode
        except subprocess.TimeoutExpired:
            return "", "délai dépassé (%d s)" % timeout, 124
        except FileNotFoundError:
            return "", "ssh absent de l'hôte", 127

    def tcp(self, hote, port, timeout=4):
        try:
            with socket.create_connection((hote, int(port)), timeout=timeout):
                return True
        except OSError:
            return False

    def http_json(self, url, jeton="", timeout=6):
        try:
            req = urllib.request.Request(url, headers={"X-Session-Token": jeton, "User-Agent": "CASSANDRA-Flotte/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as ex:
            return {"_error": "HTTP %d" % ex.code}
        except Exception as ex:
            return {"_error": type(ex).__name__}


# ------------------------------------------------------------------ le verdict d'ouverture
def verdict(parc, pertes24):
    """CE QUE LE PARC DIT À L'OUVERTURE. Du plus grave au plus calme : une machine ATTENDUE qui ne répond plus ; une machine attendue sans aucun contrôle ;
    ce qui bouge (pertes répétées en 24 h, santé Tailscale). « Tout le parc répond » ne se dit que si la présence tourne — sinon on ne sait pas, et on le dit."""
    M = parc["machines"]
    presence = parc["presence"]
    lignes = []
    for m in M:
        if m["etat"] != "erreur":
            continue
        depuis = m.get("depuis") or m.get("dernier_contact") or ""
        lignes.append({"niveau": "panne", "machine": m["nom"], "titre": "%s est attendue et ne répond plus%s" % (m["nom"], (" depuis %s" % depuis[11:16]) if len(depuis) >= 16 else ""),
                       "detail": "Dernier contact %s · %s · la présence relève toutes les %d min." % ((m.get("dernier_contact") or "")[:16] or "inconnu", m.get("libelle") or "hors ligne", max(1, presence["periode_s"] // 60)),
                       "gestes": [{"lib": "Ouvrir la fiche", "f": "machine", "a": m["nom"]}, {"lib": "Éteindre l'alerte (absence volontaire)", "f": "intermittente", "a": m["nom"]}]})
    sans = [m for m in M if m["niveau"] == "signal" and m["statut"] == "attendue" and not m["hote"] and m["groupe"] not in ("Mobiles", "Retirées", "Disparues") and m["etat"] != "erreur" and not m["disparue"]]
    if sans:
        pluriel = "s" if len(sans) > 1 else ""
        lignes.append({"niveau": "regarder", "machine": sans[0]["nom"], "titre": "%s : aucune clé SSH dans le registre" % ", ".join(m["nom"] for m in sans),
                       "detail": "Attendue%s et vue%s par Tailscale, mais aucun geste possible : ni diagnostic, ni action sur un service. Une clé dans le registre, ou Tailscale SSH sur la machine si elle est sous Linux (la sonde le constate seule)." % (pluriel, pluriel),
                       "gestes": [{"lib": "Déclarer une clé SSH", "f": "declarer_ssh", "a": sans[0]["nom"]}]})
    for n, nb, t0, t1 in pertes24:
        m = next((x for x in M if x["nom"] == n), None)
        if m and m["etat"] == "erreur":
            continue
        statut = (m or {}).get("statut") or "attendue"
        lignes.append({"niveau": "regarder", "machine": n, "titre": "%s : %d pertes en 24 h, entre %s et %s" % (n, nb, str(t0)[11:16], str(t1)[11:16]),
                       "detail": "Intermittente : ni alerte ni malus, mais l'absence est datée." if statut == "intermittente" else "Attendue : chaque perte compte comme coupure.",
                       "gestes": [{"lib": "Voir la disponibilité", "f": "dispo", "a": n}, {"lib": "Ouvrir la fiche", "f": "machine", "a": n}]})
    for m in M:
        if m["disparue"]:
            lignes.append({"niveau": "regarder", "machine": m["nom"], "titre": "%s : disparue du tailnet%s" % (m["nom"], (" depuis le %s" % m["depuis"][:16]) if m.get("depuis") else ""),
                           "detail": "Tailscale ne la liste plus — renommée ou retirée. Ses traces (présence, relevés) s'oublient d'elles-mêmes après %d jours." % OUBLI_JOURS,
                           "gestes": [{"lib": "Oublier maintenant", "f": "oublier", "a": m["nom"]}, {"lib": "Ouvrir la fiche", "f": "machine", "a": m["nom"]}]})
    for s in (parc.get("tailscale_sante") or [])[:3]:
        lignes.append({"niveau": "regarder", "machine": "", "titre": "Tailscale sur l'hôte : %s" % str(s)[:120], "detail": "Health check de Tailscale.", "gestes": []})
    c = parc["compte"]
    n_panne = sum(1 for l in lignes if l["niveau"] == "panne")
    n_reg = sum(1 for l in lignes if l["niveau"] == "regarder")
    if not M:
        niveau, titre, sous = "inconnu", "Aucune machine connue.", "Ni le registre, ni Tailscale ne connaissent de machine. Déclare-en une, ou vérifie Tailscale sur l'hôte."
    elif n_panne:
        niveau = "panne"
        titre = lignes[0]["titre"] + ("." if n_panne == 1 else " — et %d autre%s." % (n_panne - 1, "s" if n_panne > 2 else ""))
        sous = "Le reste du parc répond. " + (("%d point%s à regarder ensuite." % (n_reg, "s" if n_reg > 1 else "")) if n_reg else "")
    elif not presence["active"]:
        niveau, titre = "inconnu", "Je ne peux pas dire que le parc répond."
        sous = "La présence est désactivée : personne ne relève les machines. Ce qui est affiché date du dernier relevé."
    elif n_reg:
        niveau, titre = "regarder", "Tout le parc répond, mais %d point%s à regarder." % (n_reg, "s" if n_reg > 1 else "")
        sous = "%d en ligne sur %d connues · contrôle SSH sur %d." % (c["en_ligne"], c["declarees"], c["ssh"])
    else:
        niveau, titre = "stable", "Tout le parc répond."
        sous = "%d en ligne sur %d connues · contrôle SSH sur %d · présence relevée toutes les %d min." % (c["en_ligne"], c["declarees"], c["ssh"], max(1, presence["periode_s"] // 60))
    return {"niveau": niveau, "titre": titre, "sous_titre": sous.strip(), "lignes": lignes, "compte": c, "presence": presence, "hote": parc.get("hote"), "lu_le": horodate()}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : utc, horodate, nom, minutes_entre, duree, commande_sonde, lire_sortie, lire_metriques …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
