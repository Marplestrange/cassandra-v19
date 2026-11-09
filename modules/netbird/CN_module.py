# ══════════════════════════════════════════════════════════════════
# TITRE      : NetBird
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : netbird
# ZONE       : CN
# VERSION CN : 0.1.0  #c8b5b7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le réseau privé NetBird de la machine, piloté depuis l'interface : le client posé sur la machine, ou son conteneur Docker, que le module peut aussi installer.
# MÉTHODE    : `netbird status --json` pour l'état (jamais déduit) ; le client natif se parle sans root, tout le reste (Docker, installation) passe par le courtier, qui lance la commande root `piloter`.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c8b5b7 ▼▼▼
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
import subprocess
import threading
import time

DELAI = 15
NOM = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
CONTENEUR = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,62}$")
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


def _racine(verbe, args=(), entree=None, delai=30):
    """Le courtier : {ok, …} de la commande root `piloter`, ou {ok: False, erreur} (commande absente, délai, courtier arrêté)."""
    try:
        r = _RACINE_CTX("piloter", [verbe] + [str(x) for x in args], entree, delai)
    except Exception as e:                          # noqa: BLE001
        return {"ok": False, "erreur": str(e)[:200], "courtier": False}
    return _REPONSE(r)


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
        info = {"mode": "absent", "natif": False, "docker": False, "conteneur": "absent", "image": "", "courtier": True}
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
            base = {"mode": info["mode"], "docker": info["docker"], "natif": info["natif"], "conteneur": info["conteneur"], "image": info["image"], "courtier": info["courtier"], "nom_conteneur": conteneur()}
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

    def prouver_retire(c, res):
        return detecter(True)["conteneur"] == "absent"

    # ---- le journal : chaque geste qui écrit est noté (quand, qui, quoi, ce qu'il a rendu) pour pouvoir être défait depuis l'écran
    def noter(nom, args, res):
        """Ne fait JAMAIS échouer le geste : un journal qui casse ne doit pas défaire ce qui a marché."""
        try:
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

    DEFAIRE = {"connecter": defaire_connecter, "deconnecter": defaire_deconnecter, "installer_docker": defaire_installer}

    def libelle_geste(cap, args, res):
        if cap == "installer_docker":
            return "NetBird installé dans Docker (conteneur %s, image %s)" % (res.get("docker_conteneur", "?"), res.get("docker_tag", args.get("tag", "latest")))
        if cap == "retirer_docker":
            return "Conteneur NetBird retiré" + (" avec son volume (identité perdue)" if res.get("docker_purge") else "")
        return {"connecter": "Connexion à NetBird" + (" par clé" if args.get("avec_cle") else " (lien d'identification)"), "deconnecter": "NetBird coupé",
                "annuler": "Connexion en attente abandonnée"}.get(cap, cap)

    def journal(c, limite=20):
        limite = max(1, min(int(limite or 20), 100))
        gestes = []
        for g in db.lire("SELECT * FROM gestes ORDER BY id DESC LIMIT ?", (limite,)):
            try:
                args, res = json.loads(g["args"] or "{}"), json.loads(g["res"] or "{}")
            except ValueError:
                args, res = {}, {}
            gestes.append({"id": g["id"], "ts": g["ts"], "capacite": g["capacite"], "compte": g["compte"], "libelle": libelle_geste(g["capacite"], args, res), "defait": bool(g["defait"]),
                           "defait_ts": g["defait_ts"] or "", "defaisable": g["capacite"] in DEFAIRE and not g["defait"]})
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
    ctx.implementer("retirer_docker", journaliser("retirer_docker", retirer_docker), prouver_retire, lambda c, res: None, simuler=lambda x, purger=False, **_: "retirerait le conteneur NetBird" + (" et son volume" if purger else ""))
    ctx.implementer("defaire_geste", defaire_geste, prouver_defait, lambda c, res: None, simuler=lambda x, id=0, **_: "défairait le geste n°%s du journal" % id)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : la détection (natif ou Docker), l'état, les gestes, le journal
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : commandes/CN_piloter (la commande root du courtier), modules/tailscale (le module frère), interface/CN_netbird-ecran.js
