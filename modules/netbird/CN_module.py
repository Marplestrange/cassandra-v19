# ══════════════════════════════════════════════════════════════════
# TITRE      : NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : netbird
# ZONE       : CN
# VERSION CN : 0.1.0  #fb275f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le réseau privé NetBird de la machine, piloté depuis l'interface : le client posé sur la machine, ou son conteneur Docker, que le module peut aussi installer.
# MÉTHODE    : `netbird status --json` pour l'état (jamais déduit) ; le client natif se parle sans root, tout le reste (Docker, installation) passe par le courtier, qui lance la commande root `piloter`.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=fb275f ▼▼▼
"""NetBird : voir où en est le réseau privé de la machine, le connecter, l'installer au besoin dans Docker.

Deux façons d'avoir le client : NATIF (le paquet `netbird`, un service sur la machine) ou DOCKER (le conteneur officiel netbirdio/netbird). Le module trouve seul laquelle existe
(réglage `mode` : auto, natif, docker) ; il sait aussi INSTALLER le conteneur (`installer_docker`) et le retirer.

Deux façons de connecter, comme dans NetBird :
  - SANS clé : `netbird up --no-browser` attend l'identification en arrière-plan et rend un LIEN que la personne ouvre ;
  - AVEC une clé d'installation (setup key) : la machine se connecte seule. La clé vient du réglage SECRET `cle_install` (jamais d'un argument de capacité, que le journal garderait) ;
    elle voyage par l'entrée standard jusqu'au client, jamais en ligne de commande (visible dans /proc et dans `docker ps`).

Le noyau n'est pas root et ne parle pas à Docker : tout ce qui demande plus passe par le COURTIER, qui ne lance que la commande `piloter` posée en root par l'installateur du module :
une table fermée de verbes, des arguments vérifiés un à un, et jamais le conteneur d'un autre service.
Rien n'est inventé : un client absent, un démon arrêté, un conteneur arrêté, une identification en attente sont des ÉTATS distincts."""
from __future__ import annotations

import datetime
import functools
import json
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request

DELAI = 15
NOM = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
CONTENEUR = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")
VERSION_NUM = re.compile(r"v?(\d{1,3})\.(\d{1,3})\.(\d{1,3})")
URL_VERSIONS = "https://api.github.com/repos/netbirdio/netbird/releases/latest"
ID_SAUVEGARDE = re.compile(r"^\d{8}-\d{6}$")
TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
URL = re.compile(r"^https?://[A-Za-z0-9.-]{1,253}(:\d{1,5})?(/[A-Za-z0-9._~/-]{0,100})?$")
CLE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
ETATS = {"Connected": "connecte", "Connecting": "demarrage", "Idle": "deconnecte", "NeedsLogin": "a_identifier", "LoginFailed": "echec_connexion", "SessionExpired": "session_expiree"}
_RACINE_CTX = None                                 # posé par brancher() : ctx.racine (le courtier)
_REPONSE = None                                    # posé par brancher() : lit ce que le courtier rend
_MODE = {"t": 0.0, "val": None}                    # ce qui existe sur la machine, relu toutes les 30 s
_SSO = {"lien": "", "t": 0.0}                      # le dernier lien d'identification rendu par le courtier
_TTL = 2.0                                         # secondes pendant lesquelles `etat` réutilise sa dernière lecture ; 0 : jamais
_CACHE = {"t": 0.0, "val": None}
_VERROU = threading.RLock()
# Les ports d'un serveur NetBird auto-hébergé, tels que NetBird les documente (docs.netbird.io/selfhosted/selfhosted-quickstart et /selfhosted/external-reverse-proxy).
PORTS = [
    {"port": 80, "proto": "tcp", "public": True, "modes": ["traefik"], "usage": "HTTP : certificats Let's Encrypt et redirection vers HTTPS"},
    {"port": 443, "proto": "tcp", "public": True, "modes": ["traefik", "nginx", "caddy"], "usage": "HTTPS : tableau de bord, API, gRPC et relais (publié par traefik, ou par ton proxy nginx ou caddy)"},
    {"port": 3478, "proto": "udp", "public": True, "modes": ["traefik", "nginx", "caddy"], "usage": "STUN/TURN : publié directement, il ne passe jamais par un proxy"},
    {"port": 8080, "proto": "tcp", "public": False, "modes": ["nginx", "caddy"], "usage": "Tableau de bord, sur cette machine seulement : ton proxy y envoie tout sauf les chemins du serveur"},
    {"port": 8081, "proto": "tcp", "public": False, "modes": ["nginx", "caddy"], "usage": "Serveur NetBird (gestion, signal, relais), sur cette machine seulement : /api, /oauth2, /relay, /ws-proxy, gRPC (pile v0.65.0 et après)"},
    {"port": 8083, "proto": "tcp", "public": False, "modes": ["nginx", "caddy"], "ancien": True, "usage": "Signal en WebSocket : /ws-proxy/signal (ancienne pile, avant v0.65.0)"},
    {"port": 8084, "proto": "tcp", "public": False, "modes": ["nginx", "caddy"], "ancien": True, "usage": "Relais : /relay (ancienne pile, avant v0.65.0)"},
    {"port": 10000, "proto": "tcp", "public": False, "modes": ["nginx", "caddy"], "ancien": True, "usage": "Signal en gRPC : /signalexchange.SignalExchange (ancienne pile, avant v0.65.0)"},
]
_SERVEUR = {"meta": None}
_VERSIONS = {"t": 0.0, "val": ""}
_resoudre = lambda nom: socket.getaddrinfo(nom, None, socket.AF_INET)         # remplaçable : les bancs n'ont pas de DNS                          # ce que la commande root `serveur` a dit du serveur NetBird posé (domaine, version…), pour savoir où est son API
ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NOM_API = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,62}$")
VERSION_SERVEUR = re.compile(r"^v\d{1,3}\.\d{1,3}\.\d{1,3}$")
DOMAINE = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,63}|xn--[a-z0-9-]{1,59})$")
EMAIL = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
JETON = re.compile(r"^[A-Za-z0-9_.-]{16,300}$")
URL_API = re.compile(r"^(https://[A-Za-z0-9.-]{1,253}(:\d{1,5})?|http://(127\.0\.0\.1|localhost)(:\d{1,5})?)$", re.I)


def _direct(args, delai=DELAI):
    """(code, sortie) du client NATIF lancé sans root ; (None, raison) s'il est absent ou muet."""
    try:
        r = subprocess.run(["netbird"] + list(args), capture_output=True, text=True, timeout=delai, errors="replace")
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except FileNotFoundError:
        return None, "absent"
    except subprocess.TimeoutExpired:
        return None, "pas de réponse du démon NetBird"
    except Exception as e:                          # noqa: BLE001
        return None, str(e)[:200]


def _borner(delai):
    """Le courtier refuse un délai hors de 1 à 300 secondes : un geste long demandait plus et échouait avant de commencer (« délai entre 1 et 300 secondes »)."""
    try:
        return max(1, min(int(delai), 300))
    except (TypeError, ValueError):
        return 30


def _racine(verbe, args=(), entree=None, delai=30, commande="piloter"):
    """Le courtier : {ok, …} de la commande root `piloter` (le client) ou `serveur` (le serveur), ou {ok: False, erreur} (commande absente, délai, courtier arrêté)."""
    try:
        r = _RACINE_CTX(commande, [verbe] + [str(x) for x in args], entree, _borner(delai))
    except Exception as e:                          # noqa: BLE001
        return {"ok": False, "erreur": str(e)[:200], "courtier": False}
    return _REPONSE(r)


class _SansRedirection(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):          # le jeton d'accès ne suit JAMAIS une redirection (vers un autre hôte, il serait donné)
        return None


def _http(methode, url, jeton, corps=None, delai=15):
    """(code, JSON ou texte) d'une requête à l'API NetBird ; (None, raison) si le serveur ne répond pas."""
    en_tetes = {"Accept": "application/json", "Content-Type": "application/json"}
    if jeton:
        en_tetes["Authorization"] = "Token " + jeton
    req = urllib.request.Request(url, data=None if corps is None else json.dumps(corps).encode(), method=methode, headers=en_tetes)
    try:
        with urllib.request.build_opener(_SansRedirection).open(req, timeout=delai) as r:
            code, brut = r.status, r.read(2000001)
    except urllib.error.HTTPError as e:
        code, brut = e.code, e.read(20000)
    except (urllib.error.URLError, OSError, ValueError) as e:
        return None, str(getattr(e, "reason", e))[:200]
    texte = brut.decode("utf-8", "replace")
    try:
        return code, json.loads(texte or "null")
    except ValueError:
        return code, texte[:300]


def _json(sortie):
    """Le JSON d'une sortie du client, avertissements avant ou après compris (ValueError s'il n'y en a pas)."""
    i = str(sortie or "").find("{")
    obj = json.JSONDecoder().raw_decode(sortie[i:])[0] if i >= 0 else None
    if not isinstance(obj, dict):
        raise ValueError("pas d'objet JSON")
    return obj


def brancher(ctx):
    global _RACINE_CTX, _REPONSE
    _RACINE_CTX = ctx.racine

    def repondre(r):
        """Ce que le courtier rend ({ok, code, sortie, erreur}) : la ligne de JSON que la commande `piloter` a écrite, ou la raison pour laquelle il n'y en a pas."""
        try:
            d = json.loads((r.get("sortie") or "").strip().splitlines()[-1])
            return d if isinstance(d, dict) else {"ok": False, "erreur": "réponse illisible"}
        except (ValueError, IndexError):
            return {"ok": False, "erreur": (r.get("erreur") or r.get("sortie") or "pas de réponse du courtier")[:200], "courtier": "absente" not in str(r.get("erreur") or "")}
    _REPONSE = repondre
    db = ctx.stockage                                # le journal des gestes (jamais un secret)

    def conteneur():
        c = str(ctx.reglage("conteneur", "netbird") or "netbird").strip()
        return c if CONTENEUR.match(c) else "netbird"

    def horodate():
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def erreur(sortie, cle=""):
        """Une sortie du client, rendue lisible : sans la clé, avec le remède des refus connus."""
        t = str(sortie or "").strip()
        t = t.replace(cle, "…") if cle else t
        if re.search(r"permission denied", t, re.I):
            return "Cassandra n'a pas le droit de parler au démon NetBird : la commande root du module est posée par CN_install.sh --module netbird."
        if re.search(r"failed to connect to daemon|no such file|connection refused|daemon.*not running", t, re.I):
            return "Le démon NetBird ne tourne pas : `sudo netbird service start` (ou démarrer le conteneur)."
        lignes = [x for x in t.splitlines() if x.strip()]
        return (lignes[-1] if lignes else "le client n'a rien répondu")[:300]

    # ---- ce qui existe sur la machine : le client natif (direct, ou par le courtier), le conteneur Docker, ou rien
    def detecter(frais=False):
        if not frais and _MODE["val"] is not None and time.time() - _MODE["t"] < 30:
            return _MODE["val"]
        forcer = str(ctx.reglage("mode", "auto") or "auto")
        info = {"mode": "absent", "natif": False, "docker": False, "conteneur": "absent", "image": "", "courtier": True, "conflit": False}
        code, sortie = _direct(["version"], 8)
        natif_direct = code == 0
        if code is not None and code != 0 and re.search(r"permission denied", sortie, re.I):
            natif_direct = False
            info["natif"] = True                      # il existe, mais le noyau n'a pas le droit de lui parler : par le courtier
        e = _racine("etat", [conteneur()])
        if e.get("ok"):
            info.update(natif=info["natif"] or bool(e.get("natif")), docker=bool(e.get("docker")), conteneur=e.get("conteneur", "absent"), image=e.get("image", ""))
        else:
            info["courtier"] = e.get("courtier", True) is not False
        if natif_direct:
            info.update(natif=True, mode="natif_direct")
        if forcer != "docker" and info["mode"] == "absent" and info["natif"]:
            info["mode"] = "natif_racine"
        if forcer != "natif" and info["conteneur"] in ("en_marche", "arrete") and (forcer == "docker" or info["mode"] == "absent"):
            info["mode"] = "docker"
        info["conflit"] = info["natif"] and info["conteneur"] in ("en_marche", "arrete")      # deux clients sur la machine : ils se disputent wt0 et le port 51820
        _MODE.update(t=time.time(), val=info)
        return info

    def via(args, delai=DELAI, entree=None):
        """(code, sortie) du client NetBird par la voie qui existe : natif direct, natif par le courtier, ou dans le conteneur."""
        mode = detecter()["mode"]
        if mode == "natif_direct" and entree is None:
            return _direct(args, delai)
        if mode in ("natif_direct", "natif_racine"):
            r = _racine("cli", ["natif", conteneur(), "--"] + list(args), entree, max(delai, 20))
        elif mode == "docker":
            r = _racine("cli", ["docker", conteneur(), "--"] + list(args), entree, max(delai, 20))
        else:
            return None, "absent"
        if "code" in r:
            return r["code"], r.get("sortie", "")
        return None, r.get("erreur", "le courtier n'a pas répondu")

    def lire_statut(frais=False):
        """(statut_json, None) ou (None, raison). `status --json` rend du JSON même quand il faut s'identifier."""
        code, sortie = via(["status", "--json"], 20)
        if code is None:
            return None, sortie
        try:
            return _json(sortie), None
        except ValueError:
            return None, erreur(sortie)

    def jours(iso):
        try:
            d = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        return None if d.year < 2000 else (d - datetime.datetime.now(datetime.timezone.utc)).days

    def aplatir(d):
        """Le statut du client, aplati pour l'écran : état en clair, la machine, ses adresses, les autres machines du réseau."""
        pairs = []
        for p in ((d.get("peers") or {}).get("details") or []):
            lat = p.get("latency") or 0
            pairs.append({"nom": str(p.get("fqdn") or "").split(".")[0], "fqdn": str(p.get("fqdn") or ""), "ip": str(p.get("netbirdIp") or "").split("/")[0], "en_ligne": p.get("status") == "Connected",
                          "chemin": {"P2P": "direct", "Relayed": "relais"}.get(str(p.get("connectionType") or ""), ""), "relais": str(p.get("relayAddress") or ""),
                          "ms": round(lat / 1e6, 1) if isinstance(lat, (int, float)) and lat > 0 else None, "octets": int(p.get("transferReceived") or 0) + int(p.get("transferSent") or 0),
                          "vu": str(p.get("lastStatusUpdate") or "")[:16].replace("T", " ") if not str(p.get("lastStatusUpdate") or "").startswith("0001") else "",
                          "reseaux": [str(x)[:50] for x in (p.get("networks") or [])][:6], "pq": bool(p.get("quantumResistance"))})
        pairs.sort(key=lambda x: (not x["en_ligne"], x["nom"].lower()))
        gest, sig, rel = d.get("management") or {}, d.get("signal") or {}, d.get("relays") or {}
        brut = str(d.get("daemonStatus") or "")
        exp = jours(d.get("sessionExpiresAt"))
        return {"etat": ETATS.get(brut, "inconnu" if brut else "demarrage"), "brut": brut, "nom": str(d.get("fqdn") or "").split(".")[0], "fqdn": str(d.get("fqdn") or ""),
                "ip": str(d.get("netbirdIp") or "").split("/")[0], "ip6": str(d.get("netbirdIpv6") or "").split("/")[0], "version": str(d.get("daemonVersion") or ""), "cli": str(d.get("cliVersion") or ""),
                "profil": str(d.get("profileName") or ""), "noyau": bool(d.get("usesKernelInterface")), "pq": bool(d.get("quantumResistance")),
                "gestion": {"url": str(gest.get("url") or ""), "connecte": bool(gest.get("connected")), "erreur": str(gest.get("error") or "")[:200]},
                "signal": {"connecte": bool(sig.get("connected")), "erreur": str(sig.get("error") or "")[:200]},
                "relais_total": int(rel.get("total") or 0), "relais_dispo": int(rel.get("available") or 0), "reseaux": [str(x)[:60] for x in (d.get("networks") or [])][:30],
                "dns": [{"serveurs": [str(s)[:60] for s in (g.get("servers") or [])][:4], "actif": bool(g.get("enabled")), "erreur": str(g.get("error") or "")[:100]} for g in (d.get("dnsServers") or [])][:6],
                "ssh": bool((d.get("sshServer") or {}).get("enabled")), "session_jours": exp, "pairs": pairs, "en_ligne": sum(1 for x in pairs if x["en_ligne"])}

    def _etat(c, frais):
        maintenant_t = time.time()
        if not frais and _TTL > 0 and _CACHE["val"] is not None and maintenant_t - _CACHE["t"] < _TTL:
            r = dict(_CACHE["val"])
        else:
            info = detecter(frais)
            base = {"mode": info["mode"], "docker": info["docker"], "natif": info["natif"], "conteneur": info["conteneur"], "image": info["image"], "courtier": info["courtier"], "conflit": info["conflit"], "nom_conteneur": conteneur()}
            if info["mode"] == "absent":
                texte = ("Aucun client NetBird sur cette machine. Docker est là : le module peut installer le client dans un conteneur." if info["docker"]
                         else "NetBird n'est pas installé sur cette machine, et Docker non plus.")
                if info["conteneur"] == "autre":
                    texte = "Le conteneur « %s » existe mais n'est pas un conteneur NetBird : il n'est pas touché. Change le réglage « conteneur »." % conteneur()
                r = dict(base, etat="a_installer" if info["docker"] and info["conteneur"] != "autre" else "absent", texte=texte, en_attente=False, pairs=[], reseaux=[])
            else:
                d, raison = lire_statut(frais)
                r = dict(base, etat="arrete", texte=raison or "le démon NetBird ne répond pas", en_attente=False, pairs=[], reseaux=[]) if d is None else dict(base, **aplatir(d))
            _CACHE.update(t=maintenant_t, val=r)
        r["lien"] = _SSO["lien"] if r["etat"] in ("a_identifier", "demarrage", "session_expiree", "echec_connexion", "deconnecte") and time.time() - _SSO["t"] < 900 else ""
        r["en_attente"] = bool(r["lien"])
        r["cle_enregistree"] = bool(str(ctx.reglage("cle_install", "") or "").strip())
        return r

    def etat(c):
        return _etat(c, False)

    def options(nom, url):
        nom = str(nom or "").strip().lower()
        if nom and not NOM.match(nom):
            raise ValueError("Nom de machine invalide : lettres, chiffres et tirets seulement")
        url = str(url or ctx.reglage("url_gestion", "") or "").strip()
        if url and not URL.match(url):
            raise ValueError("Adresse de gestion invalide : https://netbird.exemple.fr:443")
        return (["--hostname=" + nom] if nom else []) + (["--management-url=" + url] if url else [])

    # ---- les gestes
    def connecter(c, nom="", avec_cle=False, url=""):
        with _VERROU:
            avant = _etat(c, True)
            if avant["etat"] in ("absent", "a_installer"):
                raise ValueError("NetBird n'est pas utilisable : %s" % avant.get("texte", "client absent"))
            if avant["etat"] == "connecte":
                return dict(avant, avant="connecte")
            opts = options(nom, url)
            if avec_cle:
                cle = str(ctx.reglage("cle_install", "") or "").strip()
                if not CLE.match(cle):
                    raise ValueError("La clé d'installation doit ressembler à XXXXXXXX-XXXX-… (créée dans le tableau de bord NetBird › Setup Keys)")
                code, sortie = via(["up"] + opts, 120, entree=cle)
                if code != 0:
                    raise ValueError(erreur(sortie, cle))
                _SSO.update(lien="", t=0.0)
                return dict(_etat(c, True), avant="deconnecte")
            mode = detecter()["mode"]
            r = _racine("sso", ["docker" if mode == "docker" else "natif", conteneur()] + opts, None, 60)
            if not r.get("ok"):
                raise ValueError(erreur(r.get("erreur") or r.get("sortie")))
            _SSO.update(lien=str(r.get("lien") or ""), t=time.time())
            return dict(_etat(c, True), avant="deconnecte")

    def prouver_connecter(c, res):
        for _ in range(8):
            r = _etat(c, True)
            if r["etat"] == "connecte" or (r["etat"] in ("a_identifier", "demarrage") and r["lien"]):
                return True
            time.sleep(0.8)
        return False

    def annuler_attente():
        mode = detecter()["mode"]
        _SSO.update(lien="", t=0.0)
        if mode != "absent":
            _racine("sso_annuler", ["docker" if mode == "docker" else "natif", conteneur()], None, 60)

    def defaire_connecter(c, res):
        with _VERROU:
            _CACHE["val"] = None
            if res.get("avant") != "connecte":
                annuler_attente()

    def annuler(c):
        with _VERROU:
            if _etat(c, True)["etat"] == "connecte":
                return dict(_etat(c, True), avant="connecte")          # rien à abandonner : `down` couperait une connexion qui marche
            annuler_attente()
            return dict(_etat(c, True), avant="en_attente")

    def deconnecter(c):
        with _VERROU:
            avant = _etat(c, True)["etat"]
            _SSO.update(lien="", t=0.0)
            code, sortie = via(["down"], 30)
            if code != 0:
                raise ValueError(erreur(sortie))
            return dict(_etat(c, True), avant=avant)

    def prouver_pas_connecte(c, res):
        return _etat(c, True)["etat"] != "connecte"

    def defaire_deconnecter(c, res):
        with _VERROU:
            _CACHE["val"] = None
            if res.get("avant") == "connecte":
                code, sortie = via(["up"], 60)                          # sans option : reprend la configuration gardée, sans nouvelle identification
                if code != 0:
                    raise ValueError(erreur(sortie))

    def installer_docker(c, tag="latest", avec_cle=False, url="", nom=""):
        with _VERROU:
            tag = str(tag or "latest").strip()
            if not TAG.match(tag):
                raise ValueError("Étiquette d'image invalide (latest, 0.30.0…)")
            opts = options(nom, url)
            cle = ""
            if avec_cle:
                cle = str(ctx.reglage("cle_install", "") or "").strip()
                if not CLE.match(cle):
                    raise ValueError("La clé d'installation doit ressembler à XXXXXXXX-XXXX-… (tableau de bord NetBird › Setup Keys)")
            info = detecter(True)
            if info["natif"]:
                raise ValueError("Un client NetBird est déjà installé sur cette machine : un seul client par machine (deux se disputeraient l'interface wt0 et le port 51820). Utilise celui-là, ou désinstalle-le d'abord.")
            if not info["docker"]:
                raise ValueError("Docker n'est pas installé sur cette machine (ou le courtier ne répond pas) : %s" % ("la commande root du module est absente : CN_install.sh --module netbird" if not info["courtier"] else "installer Docker d'abord"))
            r = _racine("docker_installer", [conteneur(), tag] + opts, cle or None, 280)
            if not r.get("ok"):
                raise ValueError(erreur(r.get("erreur") or r.get("sortie"), cle))
            _MODE["val"] = None
            return dict(_etat(c, True), docker_conteneur=conteneur(), docker_tag=tag)

    def prouver_installe(c, res):
        for _ in range(10):
            if detecter(True)["conteneur"] == "en_marche":
                return True
            time.sleep(1.0)
        return False

    def retirer_docker_effet(purger):
        r = _racine("docker_retirer", [conteneur()] + (["purger"] if purger else []), None, 90)
        if not r.get("ok"):
            raise ValueError(erreur(r.get("erreur") or r.get("sortie")))
        _MODE["val"] = None
        _CACHE["val"] = None

    def defaire_installer(c, res):
        with _VERROU:
            retirer_docker_effet(False)

    def retirer_docker(c, purger=False):
        with _VERROU:
            if detecter(True)["conteneur"] not in ("en_marche", "arrete"):
                raise ValueError("Il n'y a pas de conteneur NetBird « %s » à retirer" % conteneur())
            retirer_docker_effet(bool(purger))
            return dict(_etat(c, True), docker_purge=bool(purger))

    def mettre_a_jour_client(c, tag=""):
        with _VERROU:
            tag = str(tag or "").strip()
            if tag and not TAG.match(tag):
                raise ValueError("Étiquette d'image invalide (latest, 0.30.0…)")
            info = detecter(True)
            avant_version = str((_etat(c, True)).get("version") or "")
            if info["conteneur"] not in ("en_marche", "arrete"):
                if not info["natif"]:
                    raise ValueError("Il n'y a pas de client NetBird à mettre à jour : ni conteneur « %s », ni paquet" % conteneur())
                r = _racine("natif_maj", [], None, 380)                           # le paquet : par le gestionnaire de paquets, sans tag
                if not r.get("ok"):
                    raise ValueError(erreur(r.get("erreur") or r.get("sortie")))
                _MODE["val"] = None
                _CACHE["val"] = None
                avant, apres = str(r.get("avant") or avant_version), str(r.get("apres") or "")
                return dict(_etat(c, True), maj_change=bool(r.get("change")), maj_mode="natif", version_avant=avant, version_apres=apres, revenir={"mode": "natif", "version": avant} if r.get("change") and avant else {})
            r = _racine("docker_maj", [conteneur()] + ([tag] if tag else []), None, 480)
            if not r.get("ok"):
                raise ValueError(erreur(r.get("erreur") or r.get("sortie")))
            _MODE["val"] = None
            _CACHE["val"] = None
            apres = dict(_etat(c, True), maj_change=bool(r.get("change")), maj_mode="docker", version_avant=avant_version)
            apres["version_apres"] = str(apres.get("version") or "")
            apres["revenir"] = {"mode": "docker", "avant": r["avant"]} if r.get("change") and r.get("avant") else {}
            return apres

    def defaire_maj_client(c, res):
        with _VERROU:
            v = res.get("revenir") or {}
            r = _racine("docker_revenir", [conteneur(), v.get("avant", "")], None, 180) if v.get("mode") == "docker" else _racine("natif_revenir", [v.get("version", "")], None, 300)
            if not r.get("ok"):
                raise ValueError(erreur(r.get("erreur") or r.get("sortie")))
            _MODE["val"] = None
            _CACHE["val"] = None

    def installer_natif(c):
        with _VERROU:
            info = detecter(True)
            if info["natif"]:
                raise ValueError("Un client NetBird est déjà installé sur cette machine : un seul client par machine.")
            if info["conteneur"] in ("en_marche", "arrete", "autre"):
                raise ValueError("Un conteneur « %s » existe déjà : un seul client par machine (deux se disputeraient l'interface wt0 et le port 51820). Retire-le d'abord." % conteneur())
            if not info["courtier"]:
                raise ValueError("Le courtier ne répond pas ou la commande root du module est absente : CN_install.sh --module netbird")
            r = _racine("natif_installer", [], None, 420)
            if not r.get("ok"):
                raise ValueError(erreur(r.get("erreur") or r.get("sortie")))
            _MODE["val"] = None
            _CACHE["val"] = None
            return dict(_etat(c, True), natif_version=str(r.get("version") or ""), famille=str(r.get("famille") or ""))

    def prouver_natif_installe(c, res):
        return bool(detecter(True)["natif"])

    def prouver_maj_client(c, res):
        return prouver_natif_installe(c, res) if res.get("maj_mode") == "natif" else prouver_installe(c, res)

    def retirer_natif_effet():
        r = _racine("natif_retirer", [], None, 240)
        if not r.get("ok"):
            raise ValueError(erreur(r.get("erreur") or r.get("sortie")))
        _MODE["val"] = None
        _CACHE["val"] = None

    def defaire_installer_natif(c, res):
        with _VERROU:
            retirer_natif_effet()

    def retirer_natif(c):
        with _VERROU:
            if not detecter(True)["natif"]:
                raise ValueError("Il n'y a pas de client natif à désinstaller")
            retirer_natif_effet()
            return _etat(c, True)

    def prouver_natif_retire(c, res):
        return not detecter(True)["natif"]


    def prouver_retire(c, res):
        return detecter(True)["conteneur"] == "absent"

    # ---- les versions : ce qui est installé, et la dernière publiée par NetBird (GitHub, une demande par heure au plus)
    def nombres(v):
        m = VERSION_NUM.search(str(v or ""))
        return tuple(int(x) for x in m.groups()) if m else None

    def plus_recente(installee, derniere):
        """True : la dernière est plus récente ; False : non ; None : on ne sait pas (une des deux versions est illisible)."""
        a, b = nombres(installee), nombres(derniere)
        return None if a is None or b is None else b > a

    def derniere_version():
        """(tag de la dernière publication de NetBird, raison de l'échec). Une réponse récente est gardée ; si GitHub ne répond pas, la dernière connue est rendue."""
        if _VERSIONS["val"] and time.time() - _VERSIONS["t"] < 3600:
            return _VERSIONS["val"], ""
        code, d = _http("GET", URL_VERSIONS, None, None, 10)
        tag = str(d.get("tag_name") or "") if code == 200 and isinstance(d, dict) else ""
        if VERSION_SERVEUR.match(tag):
            _VERSIONS.update(t=time.time(), val=tag)
            return tag, ""
        return _VERSIONS["val"], "GitHub ne répond pas (%s)" % (code if code else str(d)[:80])

    def versions(c):
        derniere, erreur_v = derniere_version()
        client = str(_etat(c, False).get("version") or "")
        e = srv("etat")
        serveur = str(((e.get("meta") or {}) if e.get("ok") and e.get("installe") else {}).get("version") or "")
        return {"derniere": derniere, "client": client, "client_a_jour": None if not client else (None if plus_recente(client, derniere) is None else not plus_recente(client, derniere)),
                "serveur": serveur, "serveur_a_jour": None if not serveur else (None if plus_recente(serveur, derniere) is None else not plus_recente(serveur, derniere)),
                "erreur": erreur_v, "source": "github.com/netbirdio/netbird/releases"}

    # ---- le SERVEUR NetBird : posé et tenu par la commande root `serveur` (courtier) ; ADMINISTRÉ par l'API du serveur, sans root
    def srv(verbe, args=(), entree=None, delai=60):
        return _racine(verbe, args, entree, delai, "serveur")

    def srv_ok(r):
        if not r.get("ok"):
            raise ValueError(erreur(r.get("erreur") or r.get("sortie") or "la commande root `serveur` ne répond pas : CN_install.sh --module netbird"))
        return {k: v for k, v in r.items() if k != "ok"}

    def serveur_etat(c):
        r = srv("etat")
        if not r.get("ok"):
            return {"disponible": False, "erreur": str(r.get("erreur") or "la commande root `serveur` ne répond pas")[:200]}
        d = dict(r, disponible=True)
        _SERVEUR["meta"] = d.get("meta") or {}
        if d["installe"] and d["meta"].get("domaine"):
            code, i = _http("GET", "https://%s/api/instance" % d["meta"]["domaine"], None, None, 8)
            ok = code == 200 and isinstance(i, dict) and "setup_required" in i                       # la vraie API de NetBird : la 404 du tableau de bord (proxy incomplet) n'en est pas une
            d["api_joignable"] = ok
            d["setup_requis"] = bool(ok and i.get("setup_required"))                                   # le premier compte reste à créer (page /setup)
        return d

    # Le domaine du serveur NetBird doit être un nom que Cassandra ADMINISTRE : un site du panneau d'hébergement, ou un nom de la zone DNS qu'il héberge.
    def lire_panneau(cap):
        try:
            r = ctx.executer_lecture(cap)
        except Exception:
            return None
        return r if isinstance(r, list) else None                     # None : le panneau ne répond pas (≠ aucun site)

    def domaines_administres():
        sites, dns = lire_panneau("fastpanel.sites"), lire_panneau("fastpanel.dns")
        nets = lambda xs, cle: sorted({str(x.get(cle) or "").strip().lower().rstrip(".") for x in (xs or []) if isinstance(x, dict)} - {""})
        return {"disponible": sites is not None, "sites": nets(sites, "domaine"), "zones": nets(dns, "zone")}

    def verdict_domaine(domaine):
        d, adm = str(domaine or "").strip().lower().rstrip("."), domaines_administres()
        zone = next((z for z in sorted(adm["zones"], key=len, reverse=True) if d == z or d.endswith("." + z)), "")
        if d in adm["sites"]:
            return dict(adm, domaine=d, administre=True, par="site du panneau", raison="")
        if zone:
            return dict(adm, domaine=d, administre=True, par="zone DNS « %s » hébergée par le panneau" % zone, raison="")
        raison = ("Le panneau d'hébergement ne répond pas : Cassandra ne peut pas savoir si « %s » est un domaine qu'elle administre" % d) if not adm["disponible"] else             "« %s » n'est ni un site ni un nom d'une zone DNS que Cassandra administre : ajoute-le d'abord au panneau d'hébergement" % d
        return dict(adm, domaine=d, administre=False, par="", raison=raison)

    def serveur_domaines(c, domaine=""):
        v = verdict_domaine(domaine)
        propositions = list(v["sites"]) + ["netbird." + z for z in v["zones"] if ("netbird." + z) not in v["sites"]]
        return {"disponible": v["disponible"], "sites": v["sites"], "zones": v["zones"], "propositions": propositions,
                "domaine": v["domaine"], "administre": v["administre"] if domaine else None, "par": v["par"], "raison": v["raison"] if domaine else "", "libre": bool(ctx.reglage("domaine_libre", False))}

    def serveur_ports(c, proxy=""):
        if proxy and proxy not in ("traefik", "nginx", "caddy"):
            raise ValueError("Proxy : traefik, nginx ou caddy")
        e = serveur_etat(c)
        mode = proxy or str((e.get("meta") or {}).get("proxy") or "")
        pris = set(e.get("occupes") or []) if e.get("occupes") is not None else None
        ports = []
        for p in PORTS:
            if mode and mode not in p["modes"]:
                continue
            cle = "%s/%d" % (p["proto"], p["port"])
            etat = "inconnu" if pris is None else "libre" if cle not in pris else "pris_par_proxy" if (p["port"] in (80, 443) and mode in ("nginx", "caddy")) else "occupe"
            ports.append(dict(p, etat=etat))
        reels = [{"service": x.get("service", ""), "ports": x.get("ports", [])} for x in (e.get("conteneurs") or []) if x.get("ports")]
        return {"proxy": mode, "installe": bool(e.get("installe")), "disponible": bool(e.get("disponible")), "ports": ports, "reels": reels}

    def serveur_telecharger(c, version=""):
        version = str(version or "").strip()
        if not VERSION_SERVEUR.match(version):
            raise ValueError("Version explicite attendue (v0.40.0) : jamais « latest »")
        return srv_ok(srv("telecharger", [version], None, 60))

    def serveur_installer(c, version="", sha256="", domaine="", email="", proxy="nginx", hors_cassandra=False):
        with _VERROU:
            version, sha256, domaine, email = str(version or "").strip(), str(sha256 or "").strip().lower(), str(domaine or "").strip().lower(), str(email or "").strip()
            if not VERSION_SERVEUR.match(version) or not SHA.match(sha256):
                raise ValueError("Version (v0.40.0) et empreinte SHA-256 du script, telles que `serveur_telecharger` les a rendues, attendues")
            if not DOMAINE.match(domaine):
                raise ValueError("Domaine invalide : le nom (netbird.exemple.fr) qui pointe vers cette machine")
            if not EMAIL.match(email):
                raise ValueError("Adresse e-mail invalide (sert aux certificats Let's Encrypt)")
            v = verdict_domaine(domaine)
            if not v["administre"] and not hors_cassandra and not ctx.reglage("domaine_libre", False):
                raise ValueError(v["raison"] + " (ou coche « domaine que Cassandra n'administre pas » : son DNS et son certificat sont alors à ta charge)")
            if proxy not in ("traefik", "nginx", "caddy"):
                raise ValueError("Proxy : traefik (TLS intégré, ports 80 et 443 libres), nginx ou caddy (le proxy existant publie le serveur)")
            r = srv_ok(srv("installer", [version, sha256, domaine, email, proxy], None, 295))
            _SERVEUR["meta"] = None
            return dict(serveur_etat(c), installation=r.get("sortie", "")[-600:], domaine_hors_cassandra=bool(hors_cassandra and not v["administre"]))

    def prouver_serveur_installe(c, res):
        for _ in range(15):
            e = serveur_etat(c)
            if e.get("installe") and any(x.get("etat") == "running" for x in e.get("conteneurs") or []):
                return True
            time.sleep(2.0)
        return False

    def serveur_mettre_a_jour(c, sauvegarde=True):
        with _VERROU:
            avant = str(((serveur_etat(c).get("meta")) or {}).get("version") or "")
            sauv = srv_ok(srv("sauvegarder", ["avant_maj"], None, 400)).get("id", "") if sauvegarde else ""       # sans copie, la mise à jour ne se défait pas
            derniere, _ = derniere_version()
            r = srv_ok(srv("mettre_a_jour", [derniere] if derniere and plus_recente(avant, derniere) else [], None, 295))
            e = serveur_etat(c)
            return dict(e, mise_a_jour=r.get("sortie", "")[-600:], sauvegarde=sauv, version_avant=avant, version_apres=str((e.get("meta") or {}).get("version") or ""))

    def defaire_serveur_maj(c, res):
        with _VERROU:
            srv_ok(srv("restaurer", [res.get("sauvegarde", ""), "images"], None, 450))                # les données, la config ET les images d'avant
            _SERVEUR["meta"] = None

    def serveur_sauvegarder(c):
        with _VERROU:
            return srv_ok(srv("sauvegarder", ["manuelle"], None, 400))

    def serveur_sauvegardes(c):
        return srv_ok(srv("sauvegardes"))

    def serveur_restaurer(c, id="", images=False):
        with _VERROU:
            ident = str(id or "").strip()
            if not ID_SAUVEGARDE.match(ident):
                raise ValueError("Identifiant de sauvegarde attendu, tel que la liste le donne (20261109-143200)")
            r = srv_ok(srv("restaurer", [ident] + (["images"] if images else []), None, 450))
            _SERVEUR["meta"] = None
            return dict(serveur_etat(c), restauree=ident, securite=str(r.get("securite") or ""), images_remises=int(r.get("images_remises") or 0))

    def prouver_restauration(c, res):
        for _ in range(15):
            if any(x.get("etat") == "running" for x in serveur_etat(c).get("conteneurs") or []):
                return True
            time.sleep(2.0)
        return False

    def defaire_restauration(c, res):
        with _VERROU:
            srv_ok(srv("restaurer", [res.get("securite", "")], None, 450))                              # remet ce qui était là avant la restauration
            _SERVEUR["meta"] = None

    # ---- le pare-feu : les ports publics de NetBird, ouverts et refermés par la commande root
    def proxy_du_serveur(proxy=""):
        p = str(proxy or (_SERVEUR.get("meta") or {}).get("proxy") or "nginx")
        return p if p in ("traefik", "nginx", "caddy") else "nginx"

    def pare_feu_etat(c, proxy=""):
        p = proxy_du_serveur(proxy)
        r = srv_ok(srv("pare_feu"))
        return dict(r, proxy=p, publics=(["80/tcp"] if p == "traefik" else []) + ["443/tcp", "3478/udp"])

    def pare_feu_ouvrir(c, proxy=""):
        with _VERROU:
            p = proxy_du_serveur(proxy)
            r = srv_ok(srv("pare_feu_ouvrir", [p]))
            return dict(r, proxy=p)

    def prouver_pare_feu(c, res):
        e = srv_ok(srv("pare_feu"))
        return all(p in e.get("ouverts", []) for p in (res.get("ouverts_par_nous") or []) + (res.get("deja_ouverts") or []))

    def defaire_pare_feu(c, res):
        with _VERROU:
            ports = [p for p in (res.get("ouverts_par_nous") or []) if p in ("80/tcp", "443/tcp", "3478/udp")]       # seulement ce que ce geste a ouvert : le reste était déjà là
            if ports:
                srv_ok(srv("pare_feu_fermer", ports))

    def serveur_installer_jq(c):
        with _VERROU:
            r = srv_ok(srv("installer_jq", [], None, 300))
            return dict(serveur_etat(c), jq_installe=True, installation=str(r.get("sortie", ""))[-300:])

    def serveur_installer_compose(c):
        with _VERROU:
            r = srv_ok(srv("installer_compose", [], None, 360))
            return dict(serveur_etat(c), compose_installe=True, commande=str(r.get("commande") or ""))

    def prouver_compose(c, res):
        return bool(serveur_etat(c).get("compose"))

    def prouver_jq(c, res):
        return bool(serveur_etat(c).get("jq"))

    # ---- le proxy : le domaine du serveur doit envoyer /api, /oauth2, /relay et le gRPC au serveur NetBird, pas tout au tableau de bord
    def serveur_proxy_etat(c, domaine=""):
        d = str(domaine or (_SERVEUR.get("meta") or {}).get("domaine") or "").strip().lower()
        if not DOMAINE.match(d):
            raise ValueError("Domaine invalide : le nom (netbird.exemple.fr) du serveur")
        r = srv("proxy_etat", [d])
        etat = {k: v for k, v in r.items() if k != "ok"} if r.get("ok") else {"fastpanel": False, "include": "", "deja": False, "nginx": "", "http2": False, "erreur_root": str(r.get("erreur") or "")[:200]}
        code, i = _http("GET", "https://%s/api/instance" % d, None, None, 8)
        code2, o = _http("GET", "https://%s/oauth2/.well-known/openid-configuration" % d, None, None, 8)
        api = code == 200 and isinstance(i, dict) and "setup_required" in i
        oauth = code2 == 200 and isinstance(o, dict) and bool(o.get("issuer"))
        return dict(etat, domaine=d, https=code is not None, api_ok=api, oauth_ok=oauth, routes_ok=api and oauth, setup_requis=bool(api and i.get("setup_required")))

    def serveur_proxy_publier(c, domaine=""):
        with _VERROU:
            d = str(domaine or (_SERVEUR.get("meta") or {}).get("domaine") or "").strip().lower()
            if not DOMAINE.match(d):
                raise ValueError("Domaine invalide : le nom (netbird.exemple.fr) du serveur")
            r = srv_ok(srv("proxy_publier", [d], None, 120))
            return dict(serveur_proxy_etat(c, d), publie=True, include=r.get("include", ""))

    def prouver_proxy(c, res):
        for _ in range(8):
            if serveur_proxy_etat(c, res.get("domaine", "")).get("routes_ok"):
                return True
            time.sleep(1.5)
        return False

    def defaire_proxy(c, res):
        with _VERROU:
            srv_ok(srv("proxy_retirer", [res.get("domaine", "")], None, 120))

    def serveur_ip(c):
        return srv_ok(srv("ip"))

    def serveur_dns_verifier(c, domaine="", ip=""):
        d, attendue = str(domaine or "").strip().lower(), str(ip or "").strip()
        if not DOMAINE.match(d):
            raise ValueError("Domaine invalide : le nom (netbird.exemple.fr) du serveur")
        try:
            adresses = sorted({x[4][0] for x in _resoudre(d)})
        except OSError:
            adresses = []
        return {"domaine": d, "adresses": adresses, "attendue": attendue, "resolu": bool(adresses), "correspond": (attendue in adresses) if attendue else bool(adresses)}

    def serveur_redemarrer(c):
        with _VERROU:
            srv_ok(srv("commande", ["restart"], None, 130))
            return serveur_etat(c)

    def serveur_journaux(c):
        return {"journaux": srv_ok(srv("commande", ["logs"], None, 130)).get("sortie", "")}

    def serveur_nginx(c):
        return srv_ok(srv("nginx"))

    def serveur_retirer(c, purger=False):
        with _VERROU:
            avant = serveur_etat(c)
            if not avant.get("installe"):
                raise ValueError("Aucun serveur NetBird posé par Cassandra")
            sauv = ""
            if purger and not avant.get("partiel"):
                sauv = srv_ok(srv("sauvegarder", ["avant_retrait"], None, 400)).get("id", "")          # les données vont partir : on les copie d'abord, et sans copie on ne purge pas
            r = srv_ok(srv("retirer", ["purger"] if purger else [], None, 130))
            _SERVEUR["meta"] = None
            # `purge` : ce que la commande root a vraiment fait (une installation inachevée, sans pile, part toujours en entier) ; `avertissement` : un dossier qui a résisté.
            return dict(serveur_etat(c), purge=bool(r.get("purge", purger)), avertissement=str(r.get("avertissement") or ""), sauvegarde=sauv, domaine_retire=(avant.get("meta") or {}).get("domaine", ""))

    def prouver_serveur_retire(c, res):
        return not serveur_etat(c).get("conteneurs")

    # ---- l'API de gestion du serveur (jeton d'accès personnel, secret `jeton_api`) : machines, clés d'installation, groupes, politiques
    def base_api():
        u = str(ctx.reglage("url_api", "") or "").strip().rstrip("/")
        if not u:
            meta = _SERVEUR["meta"] if _SERVEUR["meta"] is not None else (serveur_etat(None).get("meta") or {})
            u = "https://" + meta["domaine"] if meta.get("domaine") else ""
        if not URL_API.match(u):
            raise ValueError("L'adresse de l'API NetBird n'est pas renseignée : réglage « url_api » (https://netbird.exemple.fr), ou installe le serveur depuis Cassandra")
        return u

    def api(methode, chemin, corps=None):
        jeton = str(ctx.reglage("jeton_api", "") or "").strip()
        if not JETON.match(jeton):
            raise ValueError("Le jeton d'accès NetBird n'est pas enregistré : tableau de bord NetBird › Settings › Personal Access Tokens, puis le réglage « jeton_api »")
        code, d = _http(methode, base_api() + "/api" + chemin, jeton, corps, 20)
        if code is None:
            raise ValueError("Le serveur NetBird ne répond pas : %s" % d)
        if code in (401, 403):
            raise ValueError("Le serveur NetBird refuse le jeton d'accès (HTTP %d) : expiré, révoqué, ou sans droit d'administrateur" % code)
        if code >= 400:
            raise ValueError("NetBird : %s (HTTP %d)" % ((d.get("message") if isinstance(d, dict) else str(d)) or "refus", code))
        return d

    def ident(v, quoi="identifiant"):
        v = str(v or "").strip()
        if not ID.match(v):
            raise ValueError("%s illisible" % quoi.capitalize())
        return v

    def liste(chemin):
        d = api("GET", chemin)
        return d if isinstance(d, list) else []

    def noms(x):
        return [str(g.get("name") or g.get("id") or "")[:60] if isinstance(g, dict) else str(g)[:60] for g in (x or [])]

    def api_verifier(c):
        return {"ok": True, "adresse": base_api(), "machines": len(liste("/peers"))}

    def api_machines(c):
        return {"machines": [{"id": str(p.get("id") or ""), "nom": str(p.get("name") or ""), "ip": str(p.get("ip") or ""), "connecte": bool(p.get("connected")), "os": str(p.get("os") or "")[:60],
                              "version": str(p.get("version") or ""), "groupes": noms(p.get("groups")), "vu": str(p.get("last_seen") or "")[:16].replace("T", " "), "ssh": bool(p.get("ssh_enabled")),
                              "expiree": bool(p.get("login_expired")), "expiration": bool(p.get("login_expiration_enabled")), "inactivite": bool(p.get("inactivity_expiration_enabled")),
                              "approbation": bool(p.get("approval_required"))} for p in liste("/peers")]}

    def api_cles(c):
        return {"cles": [{"id": str(k.get("id") or ""), "nom": str(k.get("name") or ""), "type": str(k.get("type") or ""), "valide": bool(k.get("valid")), "revoquee": bool(k.get("revoked")),
                          "utilisations": int(k.get("used_times") or 0), "limite": int(k.get("usage_limit") or 0), "expire": str(k.get("expires") or "")[:10], "etat": str(k.get("state") or ""),
                          "groupes": [str(x) for x in (k.get("auto_groups") or [])][:20], "ephemere": bool(k.get("ephemeral"))} for k in liste("/setup-keys")]}

    def api_groupes(c):
        return {"groupes": [{"id": str(g.get("id") or ""), "nom": str(g.get("name") or ""), "machines": int(g.get("peers_count") or 0), "emis": str(g.get("issued") or "")} for g in liste("/groups")]}

    def api_politiques(c):
        return {"politiques": [{"id": str(p.get("id") or ""), "nom": str(p.get("name") or ""), "actif": bool(p.get("enabled")),
                                "regles": [{"nom": str(r.get("name") or ""), "actif": bool(r.get("enabled")), "action": str(r.get("action") or ""), "bidirectionnel": bool(r.get("bidirectional")),
                                            "protocole": str(r.get("protocol") or ""), "sources": noms(r.get("sources")), "destinations": noms(r.get("destinations"))} for r in (p.get("rules") or [])]}
                               for p in liste("/policies")]}

    def trouver(chemin, i):
        return next((x for x in liste(chemin) if str(x.get("id")) == i), None)

    def corps_machine(p, nom=None, ssh=None, expiration=None):
        return {"name": nom if nom else p.get("name"), "ssh_enabled": bool(p.get("ssh_enabled")) if ssh is None else bool(ssh),
                "login_expiration_enabled": bool(p.get("login_expiration_enabled")) if expiration is None else bool(expiration), "inactivity_expiration_enabled": bool(p.get("inactivity_expiration_enabled"))}

    def machine_modifier(c, id="", nom="", ssh=None, expiration=None):
        i = ident(id, "identifiant de machine")
        nom = str(nom or "").strip()
        if nom and not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$", nom):
            raise ValueError("Nom de machine invalide : lettres, chiffres, points et tirets")
        p = api("GET", "/peers/" + i)
        avant = corps_machine(p)
        api("PUT", "/peers/" + i, corps_machine(p, nom, ssh, expiration))
        return {"id": i, "avant": avant, "apres": corps_machine(api("GET", "/peers/" + i))}

    def prouver_machine(c, res):
        return corps_machine(api("GET", "/peers/" + res["id"])) == res["apres"]

    def defaire_machine(c, res):
        api("PUT", "/peers/" + res["id"], res["avant"])

    def machine_supprimer(c, id=""):
        i = ident(id, "identifiant de machine")
        p = api("GET", "/peers/" + i)
        api("DELETE", "/peers/" + i)
        return {"id": i, "nom": str(p.get("name") or ""), "ip": str(p.get("ip") or "")}

    def absent(chemin):
        try:
            api("GET", chemin)
            return False
        except ValueError as e:
            return "HTTP 404" in str(e)

    def cle_creer(c, nom="", type="reusable", jours=30, groupes=None, limite=0, ephemere=False):
        nom = str(nom or "").strip()
        if not NOM_API.match(nom):
            raise ValueError("Nom de clé invalide : lettres, chiffres, espaces, points et tirets")
        if type not in ("one-off", "reusable"):
            raise ValueError("Type de clé : one-off (un seul usage) ou reusable")
        try:
            jours, limite = int(jours), int(limite)
        except (TypeError, ValueError):
            raise ValueError("Durée (jours) et limite d'usage : des nombres") from None
        if not 1 <= jours <= 365 or not 0 <= limite <= 10000:
            raise ValueError("Durée de 1 à 365 jours ; limite d'usage de 0 (illimitée) à 10000")
        ids = [ident(g, "identifiant de groupe") for g in (groupes if isinstance(groupes, (list, tuple)) else [x for x in str(groupes or "").split(",") if x.strip()])][:20]
        d = api("POST", "/setup-keys", {"name": nom, "type": type, "expires_in": jours * 86400, "auto_groups": ids, "usage_limit": limite, "ephemeral": bool(ephemere)})
        # La clé complète n'est rendue qu'ici, une seule fois : elle va à l'écran (`cle_secrete`, champ masqué du journal du noyau) et ne se relit jamais ensuite.
        return {"id": str((d or {}).get("id") or ""), "nom": nom, "type": type, "expire": str((d or {}).get("expires") or "")[:10], "groupes": ids, "cle_secrete": str((d or {}).get("key") or "")}

    def prouver_cle(c, res):
        return trouver("/setup-keys", res["id"]) is not None

    def defaire_cle(c, res):
        api("DELETE", "/setup-keys/" + res["id"])

    def cle_revoquer(c, id="", revoquer=True):
        i = ident(id, "identifiant de clé")
        k = trouver("/setup-keys", i)
        if k is None:
            raise ValueError("Clé inconnue")
        avant = bool(k.get("revoked"))
        api("PUT", "/setup-keys/" + i, {"revoked": bool(revoquer), "auto_groups": [str(x) for x in (k.get("auto_groups") or [])]})
        return {"id": i, "nom": str(k.get("name") or ""), "revoquee": bool(revoquer), "avant": avant}

    def prouver_revocation(c, res):
        k = trouver("/setup-keys", res["id"])
        return k is not None and bool(k.get("revoked")) == res["revoquee"]

    def defaire_revocation(c, res):
        cle_revoquer(c, res["id"], res["avant"])

    def cle_supprimer(c, id=""):
        i = ident(id, "identifiant de clé")
        k = trouver("/setup-keys", i)
        if k is None:
            raise ValueError("Clé inconnue")
        api("DELETE", "/setup-keys/" + i)
        return {"id": i, "nom": str(k.get("name") or "")}

    def groupe_creer(c, nom=""):
        nom = str(nom or "").strip()
        if not NOM_API.match(nom):
            raise ValueError("Nom de groupe invalide : lettres, chiffres, espaces, points et tirets")
        d = api("POST", "/groups", {"name": nom})
        return {"id": str((d or {}).get("id") or ""), "nom": nom}

    def prouver_groupe(c, res):
        return trouver("/groups", res["id"]) is not None

    def defaire_groupe(c, res):
        api("DELETE", "/groups/" + res["id"])

    def groupe_supprimer(c, id=""):
        i = ident(id, "identifiant de groupe")
        g = trouver("/groups", i)
        if g is None:
            raise ValueError("Groupe inconnu")
        api("DELETE", "/groups/" + i)
        return {"id": i, "nom": str(g.get("name") or "")}

    def politique_creer(c, nom="", sources=None, destinations=None, bidirectionnel=True, protocole="all", action="accept"):
        nom = str(nom or "").strip()
        if not NOM_API.match(nom):
            raise ValueError("Nom de politique invalide : lettres, chiffres, espaces, points et tirets")
        if protocole not in ("all", "tcp", "udp", "icmp") or action not in ("accept", "drop"):
            raise ValueError("Protocole : all, tcp, udp ou icmp ; action : accept ou drop")
        src = [ident(g, "identifiant de groupe") for g in (sources if isinstance(sources, (list, tuple)) else [x for x in str(sources or "").split(",") if x.strip()])][:20]
        dst = [ident(g, "identifiant de groupe") for g in (destinations if isinstance(destinations, (list, tuple)) else [x for x in str(destinations or "").split(",") if x.strip()])][:20]
        if not src or not dst:
            raise ValueError("Au moins un groupe source et un groupe destination")
        d = api("POST", "/policies", {"name": nom, "description": "créée depuis Cassandra", "enabled": True, "rules": [
            {"name": nom, "description": "", "enabled": True, "action": action, "bidirectional": bool(bidirectionnel), "protocol": protocole, "sources": src, "destinations": dst}]})
        return {"id": str((d or {}).get("id") or ""), "nom": nom, "sources": src, "destinations": dst}

    def prouver_politique(c, res):
        return trouver("/policies", res["id"]) is not None

    def defaire_politique(c, res):
        api("DELETE", "/policies/" + res["id"])

    def politique_activer(c, id="", actif=True):
        i = ident(id, "identifiant de politique")
        p = trouver("/policies", i)
        if p is None:
            raise ValueError("Politique inconnue")
        avant, regles = bool(p.get("enabled")), []
        for r in (p.get("rules") or []):
            regles.append({k: v for k, v in dict(r, sources=[g.get("id") if isinstance(g, dict) else g for g in (r.get("sources") or [])],
                                                 destinations=[g.get("id") if isinstance(g, dict) else g for g in (r.get("destinations") or [])]).items() if k in
                           ("id", "name", "description", "enabled", "action", "bidirectional", "protocol", "ports", "port_ranges", "sources", "destinations")})
        api("PUT", "/policies/" + i, {"name": p.get("name"), "description": p.get("description") or "", "enabled": bool(actif), "source_posture_checks": p.get("source_posture_checks") or [], "rules": regles})
        return {"id": i, "nom": str(p.get("name") or ""), "actif": bool(actif), "avant": avant}

    def prouver_activation(c, res):
        p = trouver("/policies", res["id"])
        return p is not None and bool(p.get("enabled")) == res["actif"]

    def defaire_activation(c, res):
        politique_activer(c, res["id"], res["avant"])

    def politique_supprimer(c, id=""):
        i = ident(id, "identifiant de politique")
        p = trouver("/policies", i)
        if p is None:
            raise ValueError("Politique inconnue")
        api("DELETE", "/policies/" + i)
        return {"id": i, "nom": str(p.get("name") or "")}

    # ---- le journal : chaque geste qui écrit est noté (quand, qui, quoi, ce qu'il a rendu) pour pouvoir être défait depuis l'écran
    def noter(nom, args, res):
        """Ne fait JAMAIS échouer le geste : un journal qui casse ne doit pas défaire ce qui a marché."""
        try:
            res = {k: v for k, v in res.items() if k != "cle_secrete"} if isinstance(res, dict) else res        # une clé d'installation créée ne va JAMAIS au journal
            db.ecrire("INSERT INTO gestes(ts, capacite, compte, args, res) VALUES (?,?,?,?,?)", (horodate(), nom, str(ctx.compte or ""), json.dumps(args, default=str)[:2000], json.dumps(res, default=str)[:20000]))
            db.ecrire("DELETE FROM gestes WHERE id NOT IN (SELECT id FROM gestes ORDER BY id DESC LIMIT 200)")
        except Exception:                           # noqa: BLE001
            pass

    def journaliser(nom, faire):
        @functools.wraps(faire)
        def enveloppe(c, *a, **kw):
            res = faire(c, *a, **kw)
            noter(nom, kw, res)
            return res
        return enveloppe

    DEFAIRE = {"connecter": defaire_connecter, "deconnecter": defaire_deconnecter, "installer_docker": defaire_installer, "machine_modifier": defaire_machine, "cle_creer": defaire_cle, "cle_revoquer": defaire_revocation,
               "groupe_creer": defaire_groupe, "politique_creer": defaire_politique, "politique_activer": defaire_activation,
               "serveur_mettre_a_jour": defaire_serveur_maj, "serveur_proxy_publier": defaire_proxy, "mettre_a_jour_client": defaire_maj_client, "serveur_restaurer": defaire_restauration, "pare_feu_ouvrir": defaire_pare_feu,
               "installer_natif": defaire_installer_natif}
    PEUT_DEFAIRE = {"serveur_mettre_a_jour": lambda r: bool(r.get("sauvegarde")), "mettre_a_jour_client": lambda r: bool(r.get("revenir")), "serveur_restaurer": lambda r: bool(r.get("securite")),
                    "pare_feu_ouvrir": lambda r: bool(r.get("ouverts_par_nous"))}

    def libelle_geste(cap, args, res):
        if cap == "installer_docker":
            return "NetBird installé dans Docker (conteneur %s, image %s)" % (res.get("docker_conteneur", "?"), res.get("docker_tag", args.get("tag", "latest")))
        if cap == "retirer_docker":
            return "Conteneur NetBird retiré" + (" avec son volume (identité perdue)" if res.get("docker_purge") else "")
        n = res.get("nom") or args.get("nom") or res.get("id") or ""
        if cap == "mettre_a_jour_client":
            if not res.get("maj_change"):
                return "Client NetBird déjà à jour"
            de = " : %s → %s" % (res.get("version_avant") or "?", res.get("version_apres") or "?") if res.get("version_avant") != res.get("version_apres") else ""
            return "Client NetBird mis à jour%s (%s)" % (de, "paquet" if res.get("maj_mode") == "natif" else "conteneur recréé, identité gardée")
        if cap == "serveur_mettre_a_jour":
            de = " : %s → %s" % (res.get("version_avant") or "?", res.get("version_apres") or "?") if res.get("version_avant") != res.get("version_apres") else ""
            return "Serveur NetBird mis à jour%s%s" % (de, " (sauvegarde %s)" % res["sauvegarde"] if res.get("sauvegarde") else " (sans sauvegarde)")
        if cap == "serveur_sauvegarder":
            return "Sauvegarde du serveur NetBird faite (%s)" % res.get("id", "?")
        if cap == "serveur_restaurer":
            return "Serveur NetBird restauré depuis la sauvegarde %s" % res.get("restauree", "?")
        if cap == "pare_feu_ouvrir":
            return "Ports NetBird ouverts dans le pare-feu (%s)" % (", ".join(res.get("ouverts_par_nous") or []) or "déjà tous ouverts")
        if cap == "serveur_proxy_publier":
            return "Routes NetBird posées dans le site FASTPANEL %s (nginx rechargé)" % res.get("domaine", "?")
        if cap == "serveur_installer_compose":
            return "Docker Compose installé (%s) : exigé par le script d'installation du serveur NetBird" % (res.get("commande") or "paquet de la distribution")
        if cap == "serveur_installer_jq":
            return "jq installé (exigé par le script d'installation du serveur NetBird)"
        if cap == "installer_natif":
            return "Client NetBird natif installé (paquet officiel%s)" % (", version %s" % res["natif_version"] if res.get("natif_version") else "")
        if cap == "retirer_natif":
            return "Client NetBird natif désinstallé"
        return {"connecter": "Connexion à NetBird" + (" par clé" if args.get("avec_cle") else " (lien d'identification)"), "deconnecter": "NetBird coupé",
                "annuler": "Connexion en attente abandonnée", "serveur_telecharger": "Script du serveur téléchargé (%s)" % res.get("version", args.get("version", "?")),
                "serveur_installer": "Serveur NetBird installé (%s, %s)%s" % ((res.get("meta") or {}).get("domaine", args.get("domaine", "?")), args.get("proxy", "nginx"), " : domaine hors Cassandra" if res.get("domaine_hors_cassandra") else ""), "serveur_mettre_a_jour": "Serveur NetBird mis à jour",
                "serveur_redemarrer": "Serveur NetBird redémarré", "serveur_retirer": "Serveur NetBird retiré" + (" avec ses données (comptes et machines perdus%s)" % (" ; sauvegarde " + res["sauvegarde"] if res.get("sauvegarde") else "") if res.get("purge") else ""),
                "machine_modifier": "Machine « %s » modifiée" % n, "machine_supprimer": "Machine « %s » supprimée du réseau" % n, "cle_creer": "Clé d'installation « %s » créée" % n,
                "cle_revoquer": "Clé d'installation « %s » %s" % (n, "révoquée" if res.get("revoquee", True) else "rétablie"), "cle_supprimer": "Clé d'installation « %s » supprimée" % n,
                "groupe_creer": "Groupe « %s » créé" % n, "groupe_supprimer": "Groupe « %s » supprimé" % n, "politique_creer": "Politique d'accès « %s » créée" % n,
                "politique_activer": "Politique d'accès « %s » %s" % (n, "activée" if res.get("actif", True) else "désactivée"), "politique_supprimer": "Politique d'accès « %s » supprimée" % n}.get(cap, cap)

    def journal(c, limite=20):
        limite = max(1, min(int(limite or 20), 100))
        gestes = []
        for g in db.lire("SELECT * FROM gestes ORDER BY id DESC LIMIT ?", (limite,)):
            try:
                args, res = json.loads(g["args"] or "{}"), json.loads(g["res"] or "{}")
            except ValueError:
                args, res = {}, {}
            gestes.append({"id": g["id"], "ts": g["ts"], "capacite": g["capacite"], "compte": g["compte"], "libelle": libelle_geste(g["capacite"], args, res), "defait": bool(g["defait"]),
                           "defait_ts": g["defait_ts"] or "", "defaisable": g["capacite"] in DEFAIRE and not g["defait"] and PEUT_DEFAIRE.get(g["capacite"], lambda r: True)(res)})
        return {"gestes": gestes}

    def defaire_geste(c, id=0):
        with _VERROU:
            lignes = db.lire("SELECT * FROM gestes WHERE id=?", (int(id or 0),))
            if not lignes:
                raise ValueError("Geste inconnu")
            g = lignes[0]
            if g["defait"]:
                raise ValueError("Ce geste est déjà défait")
            if g["capacite"] not in DEFAIRE:
                raise ValueError("Ce geste ne se défait pas (rien à remettre)")
            try:
                res = json.loads(g["res"] or "{}")
            except ValueError:
                raise ValueError("Le résultat noté de ce geste est illisible : il ne peut pas être défait") from None
            if not PEUT_DEFAIRE.get(g["capacite"], lambda r: True)(res):
                raise ValueError("Ce geste ne se défait pas : rien n'a été gardé pour revenir en arrière (pas de sauvegarde, pas d'ancienne version)")
            DEFAIRE[g["capacite"]](c, res)
            db.ecrire("UPDATE gestes SET defait=1, defait_ts=? WHERE id=?", (horodate(), int(g["id"])))
            return dict(_etat(c, True), geste_defait=int(g["id"]))

    def prouver_defait(c, res):
        lignes = db.lire("SELECT defait FROM gestes WHERE id=?", (res.get("geste_defait"),))
        return bool(lignes and lignes[0]["defait"])

    ctx.implementer("etat", etat)
    ctx.implementer("journal", journal)
    ctx.implementer("connecter", journaliser("connecter", connecter), prouver_connecter, defaire_connecter,
                    simuler=lambda x, nom="", avec_cle=False, **_: "connecterait la machine à NetBird" + (" avec la clé enregistrée" if avec_cle else " (lien d'identification)"))
    ctx.implementer("annuler", journaliser("annuler", annuler), lambda c, res: not res.get("en_attente"), lambda c, res: None, simuler=lambda x, **_: "abandonnerait la connexion en attente")
    ctx.implementer("deconnecter", journaliser("deconnecter", deconnecter), prouver_pas_connecte, defaire_deconnecter, simuler=lambda x, **_: "couperait NetBird sur cette machine")
    ctx.implementer("installer_docker", journaliser("installer_docker", installer_docker), prouver_installe, defaire_installer,
                    simuler=lambda x, tag="latest", **_: "installerait le client NetBird dans un conteneur Docker (netbirdio/netbird:%s)" % tag)
    ctx.implementer("mettre_a_jour_client", journaliser("mettre_a_jour_client", mettre_a_jour_client), prouver_maj_client, lambda c, res: None,
                    simuler=lambda x, tag="", **_: "mettrait à jour le client NetBird (image netbirdio/netbird" + (":" + tag if tag else ", même étiquette") + ", conteneur recréé, volume gardé)")
    ctx.implementer("installer_natif", journaliser("installer_natif", installer_natif), prouver_natif_installe, defaire_installer_natif, simuler=lambda x, **_: "installerait le client NetBird natif (paquet officiel, apt ou dnf)")
    ctx.implementer("retirer_natif", journaliser("retirer_natif", retirer_natif), prouver_natif_retire, lambda c, res: None, simuler=lambda x, **_: "désinstallerait le client NetBird natif")
    ctx.implementer("versions", versions)
    ctx.implementer("retirer_docker", journaliser("retirer_docker", retirer_docker), prouver_retire, lambda c, res: None, simuler=lambda x, purger=False, **_: "retirerait le conteneur NetBird" + (" et son volume" if purger else ""))
    ctx.implementer("serveur_etat", serveur_etat)
    ctx.implementer("serveur_journaux", serveur_journaux)
    ctx.implementer("serveur_nginx", serveur_nginx)
    ctx.implementer("serveur_domaines", serveur_domaines)
    ctx.implementer("serveur_ports", serveur_ports)
    ctx.implementer("serveur_telecharger", journaliser("serveur_telecharger", serveur_telecharger), lambda c, res: bool(SHA.match(str(res.get("sha256", "")))), lambda c, res: None,
                    simuler=lambda x, version="", **_: "téléchargerait le script d'installation du serveur NetBird %s et en donnerait l'empreinte" % version)
    ctx.implementer("serveur_installer", journaliser("serveur_installer", serveur_installer), prouver_serveur_installe, lambda c, res: None,
                    simuler=lambda x, domaine="", proxy="nginx", **_: "installerait un serveur NetBird auto-hébergé pour %s (proxy %s)" % (domaine, proxy))
    ctx.implementer("serveur_mettre_a_jour", journaliser("serveur_mettre_a_jour", serveur_mettre_a_jour), lambda c, res: True, defaire_serveur_maj, simuler=lambda x, **_: "mettrait à jour les images du serveur NetBird")
    ctx.implementer("serveur_sauvegarder", journaliser("serveur_sauvegarder", serveur_sauvegarder), lambda c, res: bool(ID_SAUVEGARDE.match(str(res.get("id", "")))), lambda c, res: None, simuler=lambda x, **_: "sauvegarderait le serveur NetBird (volumes et dossier, serveur arrêté le temps de la copie)")
    ctx.implementer("serveur_sauvegardes", serveur_sauvegardes)
    ctx.implementer("serveur_restaurer", journaliser("serveur_restaurer", serveur_restaurer), prouver_restauration, defaire_restauration, simuler=lambda x, id="", **_: "restaurerait la sauvegarde %s du serveur NetBird (après une sauvegarde de sécurité)" % id)
    ctx.implementer("pare_feu_etat", pare_feu_etat)
    ctx.implementer("pare_feu_ouvrir", journaliser("pare_feu_ouvrir", pare_feu_ouvrir), prouver_pare_feu, defaire_pare_feu, simuler=lambda x, proxy="", **_: "ouvrirait dans le pare-feu les ports publics de NetBird (proxy %s)" % (proxy or "du serveur"))
    ctx.implementer("serveur_proxy_etat", serveur_proxy_etat)
    ctx.implementer("serveur_proxy_publier", journaliser("serveur_proxy_publier", serveur_proxy_publier), prouver_proxy, defaire_proxy, simuler=lambda x, domaine="", **_: "poserait les routes NetBird (/api, /oauth2, /relay, gRPC) dans le fichier d'inclusion du site FASTPANEL %s, puis rechargerait nginx" % (domaine or "du serveur"))
    ctx.implementer("serveur_installer_compose", journaliser("serveur_installer_compose", serveur_installer_compose), prouver_compose, lambda c, res: None, simuler=lambda x, **_: "installerait Docker Compose (paquet de la distribution) pour le script du serveur NetBird")
    ctx.implementer("serveur_installer_jq", journaliser("serveur_installer_jq", serveur_installer_jq), prouver_jq, lambda c, res: None, simuler=lambda x, **_: "installerait jq (paquet de la distribution) pour le script du serveur NetBird")
    ctx.implementer("serveur_ip", serveur_ip)
    ctx.implementer("serveur_dns_verifier", serveur_dns_verifier)
    ctx.implementer("serveur_redemarrer", journaliser("serveur_redemarrer", serveur_redemarrer), lambda c, res: True, lambda c, res: None, simuler=lambda x, **_: "redémarrerait le serveur NetBird")
    ctx.implementer("serveur_retirer", journaliser("serveur_retirer", serveur_retirer), prouver_serveur_retire, lambda c, res: None, simuler=lambda x, purger=False, **_: "retirerait le serveur NetBird" + (" et ses données" if purger else ""))
    ctx.implementer("api_verifier", api_verifier)
    ctx.implementer("api_machines", api_machines)
    ctx.implementer("api_cles", api_cles)
    ctx.implementer("api_groupes", api_groupes)
    ctx.implementer("api_politiques", api_politiques)
    ctx.implementer("machine_modifier", journaliser("machine_modifier", machine_modifier), prouver_machine, defaire_machine, simuler=lambda x, id="", **_: "modifierait la machine %s du réseau NetBird" % id)
    ctx.implementer("machine_supprimer", journaliser("machine_supprimer", machine_supprimer), lambda c, res: absent("/peers/" + res["id"]), lambda c, res: None, simuler=lambda x, id="", **_: "supprimerait la machine %s du réseau NetBird" % id)
    ctx.implementer("cle_creer", journaliser("cle_creer", cle_creer), prouver_cle, defaire_cle, simuler=lambda x, nom="", **_: "créerait la clé d'installation « %s »" % nom)
    ctx.implementer("cle_revoquer", journaliser("cle_revoquer", cle_revoquer), prouver_revocation, defaire_revocation, simuler=lambda x, id="", **_: "révoquerait la clé d'installation %s" % id)
    ctx.implementer("cle_supprimer", journaliser("cle_supprimer", cle_supprimer), lambda c, res: trouver("/setup-keys", res["id"]) is None, lambda c, res: None, simuler=lambda x, id="", **_: "supprimerait la clé d'installation %s" % id)
    ctx.implementer("groupe_creer", journaliser("groupe_creer", groupe_creer), prouver_groupe, defaire_groupe, simuler=lambda x, nom="", **_: "créerait le groupe « %s »" % nom)
    ctx.implementer("groupe_supprimer", journaliser("groupe_supprimer", groupe_supprimer), lambda c, res: trouver("/groups", res["id"]) is None, lambda c, res: None, simuler=lambda x, id="", **_: "supprimerait le groupe %s" % id)
    ctx.implementer("politique_creer", journaliser("politique_creer", politique_creer), prouver_politique, defaire_politique, simuler=lambda x, nom="", **_: "créerait la politique d'accès « %s »" % nom)
    ctx.implementer("politique_activer", journaliser("politique_activer", politique_activer), prouver_activation, defaire_activation, simuler=lambda x, id="", actif=True, **_: "%s la politique d'accès %s" % ("activerait" if actif else "désactiverait", id))
    ctx.implementer("politique_supprimer", journaliser("politique_supprimer", politique_supprimer), lambda c, res: trouver("/policies", res["id"]) is None, lambda c, res: None, simuler=lambda x, id="", **_: "supprimerait la politique d'accès %s" % id)
    ctx.implementer("defaire_geste", defaire_geste, prouver_defait, lambda c, res: None, simuler=lambda x, id=0, **_: "défairait le geste n°%s du journal" % id)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : la détection (natif ou Docker), l'état, les gestes, le journal
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : commandes/CN_piloter (la commande root du courtier), modules/tailscale (le module frère), interface/CN_netbird-ecran.js
