# ══════════════════════════════════════════════════════════════════
# TITRE      : Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.5.0  #1e23fe
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le réseau privé Tailscale de la machine, piloté depuis l'interface.
# MÉTHODE    : le client `tailscale` local ; l'état se lit dans `status --json`, jamais déduit.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.5.0 empreinte=1e23fe ▼▼▼
"""Tailscale : voir où en est le réseau privé de la machine et le connecter depuis l'interface.

Deux façons de connecter, comme sur tailscale.com :
  - SANS clé : `tailscale up` s'ouvre, Tailscale répond par un LIEN ; la personne l'ouvre, s'identifie, et la machine rejoint son réseau. Le lien se lit dans
    `status --json` (AuthURL) ; `up` reste en attente en arrière-plan jusqu'à l'identification ou l'abandon ;
  - AVEC une clé d'authentification (tskey-…) : la machine se connecte seule. La clé vient du réglage SECRET `cle_auth` (jamais d'un argument de capacité, que le
    journal garderait) ; elle est donnée au client par un fichier à droits 0600 qui disparaît aussitôt, jamais en ligne de commande (visible dans /proc).

Rien ne se fait en root : l'installateur donne à l'utilisateur de Cassandra le droit d'opérateur du client. Un refus d'accès se dit en clair, avec la commande qui le règle.
Rien n'est inventé : un client absent, un tailscaled arrêté, une identification en attente sont des ÉTATS distincts, pas des « hors ligne » interchangeables."""
from __future__ import annotations

import datetime
import functools
import ipaddress
import json
import os
import re
import signal
import subprocess
import tempfile
import threading
import time

DELAI = 10
CLE = re.compile(r"^tskey-[A-Za-z0-9_-]{8,200}$")
NOM = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_EN_ATTENTE = {"proc": None, "err": None}          # le `tailscale up` sans clé, en attente d'identification ; `err` : le fichier où va sa sortie d'erreur (jamais un tube : personne ne le vide)
_PROC = "/proc"                                    # où chercher un `up` en attente d'avant un redémarrage de Cassandra (Linux ; ailleurs, rien à trouver)
_SOCKET = os.environ.get("CASSANDRA_TAILSCALE_SOCKET", "")   # un tailscaled qui n'écoute pas sur le socket par défaut (et le banc contre un vrai tailscaled)
_TTL = 2.0                                         # secondes pendant lesquelles `etat` réutilise la dernière lecture (statut + préférences) ; 0 : jamais
_CACHE = {"t": 0.0, "val": None}
_RESEAU = {"t": 0.0, "val": None}                  # le dernier netcheck (lent : quelques secondes de sondes) : réutilisé 60 s
SERVE_PORTS = (443, 8443, 10000)                   # les ports HTTPS que Tailscale Serve accepte
CIBLE_LOCALE = re.compile(r"^(?:https?://)?(?:127\.0\.0\.1|localhost|\[::1\])(?::(\d{1,5}))?(?:/[A-Za-z0-9._~/%-]*)?$")
CHEMIN_SERVE = re.compile(r"^/[A-Za-z0-9._~/-]{0,120}$")
_VERROU = threading.RLock()                        # un seul geste à la fois sur la connexion : deux `up` en même temps laisseraient un processus orphelin


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)
_REFERENCES = {}


def _appeler_point(point, entree):
    """Appelle le point d'évolution du module. Sans brancher() (un banc qui appelle la fonction seule), la RÉFÉRENCE du dépôt répond : points/EC_<point>.py, chargée par son chemin."""
    if _point is not None:
        return _point(point, entree)
    if point not in _REFERENCES:
        import importlib.util as _iu
        import pathlib as _pl
        chemin = _pl.Path(__file__).resolve().parent / "points" / ("EC_%s.py" % point)
        spec = _iu.spec_from_file_location("ec_ref_" + point, str(chemin))
        mod = _iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _REFERENCES[point] = getattr(mod, "point_" + point)
    return _REFERENCES[point](entree)


def _commande(args):
    return ["tailscale"] + (["--socket=" + _SOCKET] if _SOCKET else []) + list(args)


def _lancer(args, delai=DELAI):
    """(code, sortie) ; (None, raison) si le client est absent ou n'a pas répondu à temps."""
    try:
        r = subprocess.run(_commande(args), capture_output=True, text=True, timeout=delai, errors="replace")
        return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()
    except FileNotFoundError:
        return None, "absent"
    except subprocess.TimeoutExpired:
        return None, "pas de réponse de tailscaled"
    except Exception as e:                          # noqa: BLE001
        return None, str(e)[:200]


def _erreur(sortie, cle=''):
    """Une sortie du client, rendue lisible : sans la clé, avec la commande qui règle un refus d'accès. Le calcul est un POINT D'ÉVOLUTION : points/EC_erreur.py.
    La commande citée nomme le compte réellement en jeu (CASSANDRA_UTILISATEUR), pas toujours « cassandra »."""
    texte = _appeler_point("erreur", {"sortie": sortie, "cle": cle})["valeur"]
    return texte.replace("--operator=cassandra", "--operator=" + utilisateur())


def _json(sortie):
    """Le JSON d'une sortie du client, avertissements de stderr avant ou après compris (ValueError s'il n'y en a pas)."""
    i = str(sortie or "").find("{")
    obj = json.JSONDecoder().raw_decode(sortie[i:])[0] if i >= 0 else None
    if not isinstance(obj, dict):
        raise ValueError("pas d'objet JSON")
    return obj


def utilisateur():
    """Le compte sous lequel tourne le noyau : celui que l'installateur a fait opérateur du client."""
    try:
        import pwd
        return pwd.getpwuid(os.getuid()).pw_name
    except Exception:                               # noqa: BLE001
        return os.environ.get("CASSANDRA_UTILISATEUR", "cassandra")


def lire_statut():
    """(statut_json, None) ou (None, raison). `status --json` rend du JSON même quand il faut s'identifier."""
    code, sortie = _lancer(["status", "--json"])
    if code is None:
        return None, sortie
    try:
        return _json(sortie), None
    except ValueError:
        return None, _erreur(sortie)


def resume(d):
    """Le statut du client, aplati pour l'écran : état en clair, la machine, ses adresses, les autres machines du réseau. Le calcul est un POINT D'ÉVOLUTION : points/EC_resume.py."""
    return _appeler_point("resume", {"d": d})["valeur"]


def orphelins():
    """Les `tailscale up --timeout=15m` encore en attente d'identification et que ce processus ne suit plus (Cassandra a redémarré depuis : le `up` est parti dans sa propre
    session). Sans eux, l'écran dit « pas de connexion en attente » et un nouveau `up` s'ajoute à l'ancien. Rend la liste des pid ; vide hors Linux."""
    pids = []
    try:
        noms = os.listdir(_PROC)
    except OSError:
        return pids
    for n in noms:
        if not n.isdigit() or int(n) == os.getpid():
            continue
        try:
            with open(os.path.join(_PROC, n, "cmdline"), "rb") as f:
                a = [x.decode("utf-8", "replace") for x in f.read().split(b"\0") if x]
        except OSError:
            continue
        if len(a) < 2 or os.path.basename(a[0]) != "tailscale":
            continue
        sockets = [x for x in a[1:] if x.startswith("--socket=")]
        reste = [x for x in a[1:] if not x.startswith("--socket=")]
        # le même client que le nôtre : un `up` sur un autre socket est celui d'un autre tailscaled (jamais le sien à abandonner)
        if reste[:1] == ["up"] and "--timeout=15m" in a and sockets == (["--socket=" + _SOCKET] if _SOCKET else []):
            pids.append(int(n))
    return pids


def lire_prefs():
    """Les préférences du client (`debug prefs`) ou None : elles disent SSH (`RunSSH`) et qui est l'opérateur (`OperatorUser`), le statut non."""
    code, sortie = _lancer(["debug", "prefs"])
    if code != 0:
        return None
    try:
        return _json(sortie)
    except ValueError:
        return None


def lire_ssh():
    """SSH par Tailscale est-il activé ? Ce sont les préférences qui le disent (`RunSSH`), pas le statut."""
    p = lire_prefs()
    return None if p is None else bool(p.get("RunSSH"))


class Veilleur:
    """Le flux d'événements du client (`tailscale debug watch-ipn`) : chaque ligne réveille l'attente, qui relit alors l'état. L'ÉTAT reste lu par `status --json` (la source de vérité) ;
    le flux ne fait que cadencer, au lieu d'un sommeil fixe. Sans flux (client absent, ancien client), `attendre` dort comme avant : rien ne dépend de lui."""

    def __init__(self, commande=None):
        self.ev = threading.Event()
        self.proc = None
        try:
            self.proc = subprocess.Popen(commande or _commande(["debug", "watch-ipn"]), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
        except (OSError, ValueError):
            return
        threading.Thread(target=self._lire, daemon=True).start()

    def _lire(self):
        try:
            for _ in self.proc.stdout:
                self.ev.set()
        except (OSError, ValueError, AttributeError):
            pass

    def attendre(self, delai):
        """Rend après `delai` au plus, ou dès qu'un événement arrive. Sans flux : un simple sommeil."""
        if self.proc is None:
            time.sleep(delai)
            return False
        vu = self.ev.wait(delai)
        self.ev.clear()
        if vu:
            time.sleep(0.2)                         # le temps que le démon ait fini de changer d'état, et pas plus d'une relecture par instant
        return vu

    def fermer(self):
        p, self.proc = self.proc, None
        if p is not None:
            try:
                p.terminate()
                p.wait(2)
            except Exception:                       # noqa: BLE001
                try:
                    p.kill()
                except Exception:                   # noqa: BLE001
                    pass
            try:
                p.stdout.close()
            except (OSError, ValueError, AttributeError):
                pass


def brancher(ctx):
    global _point
    _point = ctx.point
    db = ctx.stockage                                # le journal des gestes de ce module (jamais un secret : ni clé, ni jeton)
    def _jours(iso):
        """Jours avant une date d'expiration (négatif : déjà expirée), ou None."""
        try:
            d = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
        if d.year < 2000:                            # « 0001-01-01 » : pas d'expiration
            return None
        return (d - datetime.datetime.now(datetime.timezone.utc)).days

    def expirations(d):
        """La clé de cette machine et celles des pairs qui expirent dans 14 jours (ou ont expiré) : sinon une machine tombe du réseau sans prévenir."""
        moi = d.get("Self") or {}
        j = _jours(moi.get("KeyExpiry"))
        out = {"expiration": None if j is None else {"date": str(moi.get("KeyExpiry"))[:10], "jours": j}, "expirent": []}
        for p in (d.get("Peer") or {}).values():
            jp = _jours(p.get("KeyExpiry"))
            if jp is not None and jp <= 14:
                out["expirent"].append({"nom": p.get("HostName") or str(p.get("DNSName") or "").split(".")[0], "jours": jp})
        out["expirent"].sort(key=lambda x: x["jours"])
        return out

    def reglages_de(prefs):
        """Les réglages que l'écran propose, lus dans les préférences (la source de vérité)."""
        routes = list(prefs.get("AdvertiseRoutes") or [])
        return {"accept_routes": bool(prefs.get("RouteAll")), "accept_dns": bool(prefs.get("CorpDNS")), "shields_up": bool(prefs.get("ShieldsUp")), "hostname": str(prefs.get("Hostname") or ""),
                "advertise_routes": sorted(x for x in routes if x not in ("0.0.0.0/0", "::/0")), "advertise_exit_node": "0.0.0.0/0" in routes, "exit_node": str(prefs.get("ExitNodeIP") or "")}

    def enrichir(r, d):
        """Ce que l'écran montre en plus par machine : étiquettes, routes annoncées, relais, échanges, date d'arrivée. Lu dans le statut brut ; la sortie du point `resume` ne change pas."""
        par_ip = {(p.get("TailscaleIPs") or [""])[0]: p for p in (d.get("Peer") or {}).values()}
        for q in r.get("pairs") or []:
            p = par_ip.get(q["ip"]) or {}
            q["tags"] = [str(x)[:40] for x in (p.get("Tags") or [])][:5]
            q["routes"] = [str(x)[:50] for x in (p.get("PrimaryRoutes") or [])][:8]
            q["relais"] = str(p.get("Relay") or "")
            q["direct"] = bool(p.get("CurAddr"))
            q["octets"] = int(p.get("RxBytes") or 0) + int(p.get("TxBytes") or 0)
            q["depuis"] = str(p.get("Created") or "")[:10]
            q["dns"] = str(p.get("DNSName") or "").split(".")[0]
        r["relais_maison"] = str((d.get("Self") or {}).get("Relay") or "")
        r["os"] = str((d.get("Self") or {}).get("OS") or "")
        cv = d.get("ClientVersion") or {}
        r["mise_a_jour"] = str(cv.get("LatestVersion") or "") if cv and cv.get("RunningLatest") is False else ""

    def _etat(c, frais):
        """`frais` : relire le client. Sinon la dernière lecture de moins de _TTL secondes sert (l'écran et `flotte` relisent souvent) ; tout geste qui écrit relit à neuf."""
        maintenant_t = time.time()
        if not frais and _TTL > 0 and _CACHE["val"] is not None and maintenant_t - _CACHE["t"] < _TTL:
            d, prefs = _CACHE["val"]
        else:
            d, raison = lire_statut()
            if d is None:
                _CACHE["val"] = None
                if raison == "absent":
                    return {"etat": "absent", "texte": "Tailscale n'est pas installé sur cette machine.", "en_attente": False}
                return {"etat": "arrete", "texte": raison or "tailscaled ne répond pas", "en_attente": False}
            prefs = lire_prefs()                     # une seule lecture : SSH, opérateur et réglages
            _CACHE.update(t=maintenant_t, val=(d, prefs))
        r = resume(d)
        r.update(expirations(d))
        enrichir(r, d)
        if prefs is not None:
            r["ssh"] = bool(prefs.get("RunSSH"))
            r["operateur"] = str(prefs.get("OperatorUser") or "")
            r["pilotable"] = r["operateur"] == utilisateur()      # faux : les gestes seraient refusés, l'écran le dit au lieu de proposer des boutons qui échouent
            r["reglages"] = reglages_de(prefs)
        else:
            r["ssh"], r["operateur"], r["pilotable"], r["reglages"] = None, "", None, None
        p = _EN_ATTENTE["proc"]
        r["en_attente"] = bool(p and p.poll() is None) or (r["etat"] == "a_identifier" and bool(orphelins()))
        r["cle_enregistree"] = bool(str(ctx.reglage("cle_auth", "") or "").strip())
        return r

    def etat(c):
        return _etat(c, False)

    def attendre(etats, delai, sauf_lien=""):
        """Relit l'état jusqu'à l'un des `etats`, au rythme des événements du client (ou d'un sommeil s'il n'a pas de flux). `sauf_lien` : un lien d'identification déjà là AVANT le geste
        est celui d'une tentative abandonnée ; le nouveau le remplace quelques secondes plus tard, et c'est lui que la personne doit ouvrir."""
        fin = time.time() + delai
        r = None
        veille = Veilleur()
        try:
            while time.time() < fin:
                d, _ = lire_statut()
                if d is not None:
                    r = resume(d)
                    if r["etat"] == "connecte" and "connecte" in etats:
                        return r
                    if r["etat"] == "a_identifier" and r["lien"] and r["lien"] != sauf_lien and "a_identifier" in etats:
                        return r
                    if r["etat"] == "a_approuver" and "a_approuver" in etats:      # identifiée : il ne reste que l'approbation de l'administrateur, inutile d'attendre davantage
                        return r
                veille.attendre(min(2.0, max(0.1, fin - time.time())) if veille.proc is not None else 0.7)
        finally:
            veille.fermer()
        return r

    def abandonner_attente():
        p, err = _EN_ATTENTE["proc"], _EN_ATTENTE["err"]
        _EN_ATTENTE["proc"] = _EN_ATTENTE["err"] = None
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(3)
            except Exception:                       # noqa: BLE001
                p.kill()
                try:
                    p.wait(3)
                except Exception:                   # noqa: BLE001
                    pass
        if err:
            try:
                err.close()
            except OSError:
                pass
        for pid in orphelins():                     # un `up` d'avant un redémarrage : même sort que celui qu'on suit
            try:
                os.kill(pid, signal.SIGTERM)
            except (OSError, AttributeError):
                pass

    def sortie_attente():
        """Ce que le `up` en attente a dit sur sa sortie d'erreur (il a fini : le fichier est complet)."""
        err = _EN_ATTENTE["err"]
        if not err:
            return ""
        try:
            err.flush()
            err.seek(0)
            return err.read().decode("utf-8", "replace")
        except (OSError, ValueError):
            return ""

    def regler_nom_ssh(nom, ssh):
        """Applique nom et SSH à une machine DÉJÀ enregistrée : `set` les change sans rien remettre à zéro (`up --reset` effacerait routes, nœud de sortie, DNS…)."""
        if nom:
            code, sortie = _lancer(["set", "--hostname=" + nom])
            if code != 0:
                raise ValueError(_erreur(sortie))
        if ssh:
            code, sortie = _lancer(["set", "--ssh=true"])
            if code != 0:
                raise ValueError(_erreur(sortie))

    def connecter(c, nom="", ssh=False, avec_cle=False):
        with _VERROU:
            return _connecter(c, nom, ssh, avec_cle)

    def _connecter(c, nom, ssh, avec_cle):
        d, raison = lire_statut()
        if d is None:
            raise ValueError("Tailscale n'est pas utilisable : %s" % (("le client est absent (CN_install.sh --module tailscale l'installe)") if raison == "absent" else raison))
        nom = str(nom or "").strip().lower()
        if nom and not NOM.match(nom):
            raise ValueError("Nom de machine invalide : lettres, chiffres et tirets seulement")
        cle = ""
        if avec_cle:                                  # refusée avant tout appel, même si la machine n'en aura pas besoin
            cle = str(ctx.reglage("cle_auth", "") or "").strip()
            if not CLE.match(cle):
                raise ValueError("La clé d'authentification doit ressembler à tskey-auth-… (créée sur login.tailscale.com › Settings › Keys)")
        etat_avant = resume(d)["etat"]
        if etat_avant == "connecte":
            regler_nom_ssh(nom, ssh)                         # déjà connectée : ce qu'on demande (nom, SSH) s'applique quand même, sans rien relancer
            return dict(_etat(c, True), avant="connecte")
        abandonner_attente()
        ancien_lien = resume(d)["lien"]
        if etat_avant == "deconnecte":
            # Machine déjà enregistrée, seulement coupée : `up` SANS AUCUN drapeau reprend sa configuration gardée (opérateur, routes, nœud de sortie, DNS). `--reset` les effacerait ;
            # et tout autre drapeau, même `--timeout`, fait refuser le `up` par le client dès qu'un réglage n'est pas celui par défaut (« requires mentioning all non-default flags »,
            # constaté sur argos). Le délai est donc celui du processus, pas du client.
            code, sortie = _lancer(["up"], 30)
            if code not in (0, None):
                raise ValueError(_erreur(sortie))
            r = attendre({"connecte", "a_approuver"}, 8) if code == 0 else None
            if r is not None and r["etat"] in ("connecte", "a_approuver"):
                if r["etat"] == "connecte":
                    regler_nom_ssh(nom, ssh)                 # nom et SSH demandés : par `set`, qui ne remet rien à zéro
                return dict(_etat(c, True), avant="deconnecte")
            # Pas reconnectée sans identification (clé expirée…) : elle repart comme une première connexion, ci-dessous.
        # Première connexion (ou après un retrait, ou identité à refaire) : rien à garder. --reset remet TOUT à zéro, l'opérateur compris : sans --operator, la connexion réussit
        # une fois puis Cassandra n'a plus le droit de rien piloter.
        args = ["up", "--reset", "--operator=" + utilisateur()]
        if nom:
            args.append("--hostname=" + nom)
        if ssh:
            args.append("--ssh")
        reglages_apres = ("", False)
        if avec_cle:
            fd, chemin = tempfile.mkstemp(prefix="ts-")                # mkstemp crée le fichier en 0600 : lisible par l'utilisateur de Cassandra seul
            try:
                try:
                    os.write(fd, cle.encode())
                finally:
                    os.close(fd)
                code, sortie = _lancer(args + ["--auth-key=file:" + chemin, "--timeout=45s"], delai=60)
            finally:
                try:
                    os.unlink(chemin)
                except OSError:
                    pass
            if code != 0:
                raise ValueError(_erreur(sortie, cle))
            r = attendre({"connecte", "a_approuver"}, 8)
            if r is not None and r["etat"] == "connecte":
                regler_nom_ssh(*reglages_apres)
            return dict(_etat(c, True), avant="deconnecte")
        err = tempfile.TemporaryFile()                                 # la sortie d'erreur du `up` en attente va dans un fichier : un tube que personne ne lit finirait par le bloquer
        try:
            _EN_ATTENTE["proc"] = subprocess.Popen(_commande(args + ["--timeout=15m"]), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
                                                   start_new_session=True)
            _EN_ATTENTE["err"] = err
        except FileNotFoundError:
            err.close()
            raise ValueError("Tailscale n'est pas installé")
        r = attendre({"connecte", "a_identifier", "a_approuver"}, 14, ancien_lien)
        p = _EN_ATTENTE["proc"]
        if (r is None or not r["lien"]) and (r is None or r["etat"] not in ("connecte", "a_approuver")) and p is not None and p.poll() not in (None, 0):
            erreur = _erreur(sortie_attente())
            abandonner_attente()
            raise ValueError(erreur)
        if r is None or (r["etat"] not in ("connecte", "a_approuver") and not r["lien"]):
            raise ValueError("Tailscale n'a pas donné de lien de connexion : réessaie dans un instant")
        if r["etat"] == "connecte":
            regler_nom_ssh(*reglages_apres)
        return dict(r, en_attente=r["etat"] == "a_identifier", avant="deconnecte")

    def maintenant():
        d, _ = lire_statut()
        return resume(d) if d is not None else None

    # Chaque geste qui écrit rend ce qu'il faut pour être PROUVÉ (relire l'état) et DÉFAIT (revenir à l'état d'avant).
    def prouver_connecter(c, res):
        """Connectée, un lien d'identification en attente, ou identifiée et seulement à approuver par l'administrateur (ce n'est pas un échec : la défaire couperait une connexion
        valable). Quelques lectures : le lien se renouvelle un instant quand une tentative en remplace une autre."""
        for _ in range(8):
            m = maintenant()
            if m and (m["etat"] in ("connecte", "a_approuver") or (m["etat"] == "a_identifier" and m["lien"])):
                return True
            time.sleep(0.8)
        return False

    def defaire_connecter(c, res):
        _CACHE["val"] = None
        with _VERROU:
            abandonner_attente()
            if res.get("avant") != "connecte":
                _lancer(["down"])

    def annuler(c):
        with _VERROU:
            m = maintenant()
            abandonner_attente()
            if m is not None and m["etat"] == "connecte":
                return dict(_etat(c, True), avant="connecte")        # rien à abandonner : `down` couperait une connexion qui marche (et peut-être la session qui pilote la machine)
            _lancer(["down"])
            return dict(_etat(c, True), avant="en_attente")

    def deconnecter(c):
        with _VERROU:
            avant = (maintenant() or {}).get("etat", "")
            abandonner_attente()
            code, sortie = _lancer(["down"])
            if code != 0:
                raise ValueError(_erreur(sortie))
            return dict(_etat(c, True), avant=avant)

    def defaire_deconnecter(c, res):
        if res.get("avant") == "connecte":
            code, sortie = _lancer(["up"], 30)             # sans option : reprend la configuration gardée, sans nouvelle identification
            if code != 0:
                raise ValueError(_erreur(sortie))

    def quitter(c):
        with _VERROU:
            avant = (maintenant() or {}).get("etat", "")
            abandonner_attente()
            code, sortie = _lancer(["logout"], 20)
            if code != 0:
                raise ValueError(_erreur(sortie))
            return dict(_etat(c, True), avant=avant)

    def ssh_regler(c, actif=True):
        avant = lire_ssh()
        code, sortie = _lancer(["set", "--ssh=" + ("true" if actif else "false")])
        if code != 0:
            raise ValueError(_erreur(sortie))
        return dict(_etat(c, True), ssh_avant=avant, ssh_demande=bool(actif))

    def prouver_pas_connecte(c, res):
        m = maintenant()
        return bool(m and m["etat"] != "connecte")

    def defaire_ssh(c, res):
        if res.get("ssh_avant") is not None:
            _lancer(["set", "--ssh=" + ("true" if res["ssh_avant"] else "false")])

    # --- les réglages du client, un geste pour tous : chaque réglage a sa validation, sa preuve (relire les préférences) et son retour (la valeur d'avant)
    BOOLEENS = {"accept_routes": "--accept-routes", "accept_dns": "--accept-dns", "shields_up": "--shields-up", "advertise_exit_node": "--advertise-exit-node"}
    CLES_REGLAGE = tuple(BOOLEENS) + ("hostname", "advertise_routes", "exit_node")

    def valider(cle, valeur, d):
        """La valeur demandée, mise en forme ; ValueError si elle n'a pas de sens ou serait dangereuse."""
        if cle in BOOLEENS:
            if isinstance(valeur, str):
                v = valeur.strip().lower()
                if v in ("1", "true", "oui", "vrai", "on"):
                    return True
                if v in ("0", "false", "non", "faux", "off"):
                    return False
                raise ValueError("Oui ou non attendu pour %s" % cle)
            return bool(valeur)
        if cle == "hostname":
            v = str(valeur or "").strip().lower()
            if v and not NOM.match(v):
                raise ValueError("Nom de machine invalide : lettres, chiffres et tirets seulement")
            return v                                 # vide : revient au nom du système
        if cle == "advertise_routes":
            items = valeur if isinstance(valeur, (list, tuple)) else str(valeur or "").split(",")
            sortie = set()
            for x in items:
                x = str(x).strip()
                if not x:
                    continue
                try:
                    reseau = ipaddress.ip_network(x, strict=False)
                except ValueError:
                    raise ValueError("Route invalide : %s (attendu : 192.168.1.0/24)" % x[:60]) from None
                if reseau.prefixlen == 0:
                    raise ValueError("0.0.0.0/0 et ::/0 s'annoncent par « advertise_exit_node », pas comme une route")
                sortie.add(str(reseau))
            if len(sortie) > 32:
                raise ValueError("32 routes au plus")
            return sorted(sortie)
        if cle == "exit_node":
            v = str(valeur or "").strip()
            if not v:
                return ""
            try:
                ipaddress.ip_address(v)
            except ValueError:
                raise ValueError("Une adresse Tailscale (100.x.y.z) attendue pour le nœud de sortie") from None
            if not any(p["ip"] == v and p["offre_sortie"] for p in resume(d)["pairs"]):
                raise ValueError("Cette machine n'offre pas de sortie Internet sur le réseau : elle doit l'annoncer et l'administrateur l'approuver")
            return v
        raise ValueError("Réglage inconnu : %s (parmi %s)" % (str(cle)[:40], ", ".join(CLES_REGLAGE)))

    def appliquer(cle, valeur, prefs):
        """`tailscale set` : change CE réglage sans toucher aux autres (`up --reset` remettrait tout à zéro)."""
        if cle in BOOLEENS:
            args = ["%s=%s" % (BOOLEENS[cle], "true" if valeur else "false")]
        elif cle == "hostname":
            args = ["--hostname=" + valeur]
        elif cle == "exit_node":
            args = ["--exit-node=" + valeur]
        else:                                        # advertise_routes : la sortie Internet annoncée est une route comme les autres pour le client ; on la garde telle quelle
            gardees = [x for x in (prefs or {}).get("AdvertiseRoutes") or [] if x in ("0.0.0.0/0", "::/0")]
            args = ["--advertise-routes=" + ",".join(list(valeur) + gardees)]
        code, sortie = _lancer(["set"] + args)
        if code != 0:
            raise ValueError(_erreur(sortie))

    def regler(c, cle="", valeur=None):
        with _VERROU:
            d, raison = lire_statut()
            if d is None:
                raise ValueError("Tailscale n'est pas utilisable : %s" % raison)
            prefs = lire_prefs()
            if prefs is None:
                raise ValueError("Les préférences du client sont illisibles : rien n'est changé")
            cle = str(cle or "").strip()
            demande = valider(cle, valeur, d)
            avant = reglages_de(prefs).get(cle)
            appliquer(cle, demande, prefs)
            return dict(_etat(c, True), reglage_cle=cle, reglage_avant=avant, reglage_demande=demande)

    def prouver_regler(c, res):
        p = lire_prefs()
        return p is not None and reglages_de(p).get(res.get("reglage_cle")) == res.get("reglage_demande")

    def defaire_regler(c, res):
        with _VERROU:
            _CACHE["val"] = None
            if res.get("reglage_cle") in CLES_REGLAGE and res.get("reglage_avant") is not None:
                appliquer(res["reglage_cle"], res["reglage_avant"], lire_prefs())

    def ping(c, machine=""):
        """Joindre une machine du réseau : par un chemin direct ou par un relais, et en combien de temps. La cible doit être une machine DU RÉSEAU (jamais un argument libre pour le client)."""
        d, raison = lire_statut()
        if d is None:
            raise ValueError("Tailscale n'est pas utilisable : %s" % raison)
        machine = str(machine or "").strip()
        cible = next((p for p in resume(d)["pairs"] if machine and machine in (p["nom"], p["ip"])), None)
        if cible is None or not cible["ip"]:
            raise ValueError("Machine inconnue du réseau Tailscale : %s" % machine[:60])
        code, sortie = _lancer(["ping", "-c", "3", "--timeout", "2s", cible["ip"]], 15)
        reponses = []
        for ligne in sortie.splitlines():
            m = re.search(r"pong from .*? via (\S+) in ([0-9.]+)\s*(µs|us|ms|s)\b", ligne)
            if m:
                ms = float(m.group(2)) * {"µs": 0.001, "us": 0.001, "ms": 1.0, "s": 1000.0}[m.group(3)]
                reponses.append({"chemin": "relais" if m.group(1).upper().startswith("DERP") else "direct", "via": m.group(1), "ms": round(ms, 1)})
        if not reponses:
            return {"machine": cible["nom"], "ip": cible["ip"], "ok": False, "reponses": 0, "detail": (sortie.splitlines() or ["pas de réponse"])[-1][:200]}
        return {"machine": cible["nom"], "ip": cible["ip"], "ok": True, "reponses": len(reponses), "chemin": reponses[-1]["chemin"], "via": reponses[-1]["via"],
                "ms": round(sum(x["ms"] for x in reponses) / len(reponses), 1)}

    # --- la santé du réseau (netcheck) : le chemin vers les relais, UDP, IPv6, NAT. Lent (quelques secondes) : à la demande, réutilisé 60 s.
    def reseau(c, force=False):
        if not force and _RESEAU["val"] is not None and time.time() - _RESEAU["t"] < 60:
            return _RESEAU["val"]
        code, sortie = _lancer(["netcheck", "--format=json"], 45)
        if "address family not supported" in sortie:
            raise ValueError("Le service Cassandra n'a pas le droit d'interroger les routes de la machine (AF_NETLINK) : CN_install.sh --module tailscale pose le complément systemd, "
                             "puis il faut redémarrer le noyau (systemctl restart cassandra-noyau)")
        if code != 0:
            raise ValueError(_erreur(sortie))
        try:
            d = _json(sortie)
        except ValueError:
            raise ValueError("netcheck n'a pas rendu de résultat lisible : %s" % (sortie.splitlines() or [""])[-1][:120]) from None
        noms = {}
        code2, sortie2 = _lancer(["debug", "derp-map"], 15)
        if code2 == 0:
            try:
                noms = {str(k): v for k, v in (_json(sortie2).get("Regions") or {}).items()}
            except ValueError:
                noms = {}
        regions = [{"id": int(k), "code": str((noms.get(str(k)) or {}).get("RegionCode") or ""), "nom": str((noms.get(str(k)) or {}).get("RegionName") or ""), "ms": round(float(ns) / 1e6, 1)}
                   for k, ns in (d.get("RegionLatency") or {}).items()]
        regions.sort(key=lambda x: x["ms"])
        pref = next((x for x in regions if x["id"] == d.get("PreferredDERP")), None)
        val = {"udp": bool(d.get("UDP")), "ipv4": bool(d.get("IPv4")), "ipv6": bool(d.get("IPv6")), "nat_varie": bool(d.get("MappingVariesByDestIP")), "portail_captif": bool(d.get("CaptivePortal")),
               "relais_prefere": pref, "regions": regions[:6], "mesure": datetime.datetime.now().strftime("%H:%M:%S")}
        _RESEAU.update(t=time.time(), val=val)
        return val

    # --- les services publiés dans le réseau (tailscale serve) : lus tels que le client les a ; publiés seulement vers un port LOCAL ; Funnel (Internet public) n'est jamais activé d'ici
    def lire_services():
        code, sortie = _lancer(["serve", "status", "--json"], 15)
        if code != 0:
            raise ValueError(_erreur(sortie))
        try:
            cfg = _json(sortie)
        except ValueError:
            cfg = {}                                 # « rien de publié » : pas de JSON
        public = cfg.get("AllowFunnel") or {}
        out = []
        for hote, web in (cfg.get("Web") or {}).items():
            for chemin, h in ((web or {}).get("Handlers") or {}).items():
                out.append({"hote": str(hote)[:120], "chemin": str(chemin)[:120], "cible": str(h.get("Proxy") or h.get("Path") or ("texte" if h.get("Text") else ""))[:200], "public": bool(public.get(hote))})
        for port, t in (cfg.get("TCP") or {}).items():
            if (t or {}).get("TCPForward"):
                out.append({"hote": ":" + str(port), "chemin": "", "cible": "tcp " + str(t["TCPForward"])[:100], "public": False})
        return out

    def services(c):
        return {"services": lire_services()}

    def serve_regler(c, port=443, cible="", chemin="/"):
        with _VERROU:
            try:
                port = int(port)
            except (TypeError, ValueError):
                port = 0
            if port not in SERVE_PORTS:
                raise ValueError("Port HTTPS : %s" % ", ".join(str(x) for x in SERVE_PORTS))
            cible = str(cible or "").strip()
            if cible.isdigit():
                cible = "127.0.0.1:" + cible
            m = CIBLE_LOCALE.match(cible)
            if not m or (m.group(1) and not 1 <= int(m.group(1)) <= 65535):
                raise ValueError("Cible : un port local (3000) ou 127.0.0.1:3000 : jamais une autre machine ni un fichier")
            chemin = "/" + str(chemin or "").strip().strip("/")
            if not CHEMIN_SERVE.match(chemin) or ".." in chemin.split("/"):
                raise ValueError("Chemin invalide (lettres, chiffres, tirets, points et barres)")
            avant = lire_services()
            args = ["serve", "--bg", "--yes", "--https=%d" % port] + (["--set-path", chemin] if chemin != "/" else []) + [cible]
            code, sortie = _lancer(args, 30)
            if code != 0:
                raise ValueError(_erreur(sortie))
            return dict(_etat(c, True), serve_port=port, serve_chemin=chemin, serve_cible=cible, serve_avant=avant, services=lire_services())

    def prouver_serve(c, res):
        return any(x["hote"].endswith(":%d" % res.get("serve_port", 0)) and x["chemin"] == res.get("serve_chemin") for x in lire_services())

    def defaire_serve(c, res):
        with _VERROU:
            if res.get("serve_avant"):
                raise ValueError("Il y avait déjà des services publiés : ils ne se rétablissent pas seuls. Retire celui-ci avec « Tout retirer » puis republie les autres.")
            code, sortie = _lancer(["serve", "reset"], 20)
            if code != 0:
                raise ValueError(_erreur(sortie))

    def serve_retirer(c):
        with _VERROU:
            avant = lire_services()
            code, sortie = _lancer(["serve", "reset"], 20)         # efface aussi ce que Funnel exposait à Internet
            if code != 0:
                raise ValueError(_erreur(sortie))
            return dict(_etat(c, True), serve_avant=avant, services=lire_services())

    # --- le journal : chaque geste qui écrit est noté (quand, qui, quoi, ce qu'il a rendu) pour pouvoir être défait depuis l'écran
    def horodate():
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

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

    DEFAIRE = {"serve_regler": defaire_serve, "connecter": defaire_connecter, "deconnecter": defaire_deconnecter, "ssh_regler": defaire_ssh, "regler": defaire_regler, "quitter": lambda c, res: connecter(c)}

    def afficher(v):
        if isinstance(v, bool):
            return "activé" if v else "coupé"
        if isinstance(v, (list, tuple)):
            return ", ".join(str(x) for x in v) or "aucune"
        return str(v) if v not in (None, "") else "(vide)"

    def libelle_geste(cap, args, res):
        if cap == "regler":
            return "Réglage « %s » : %s → %s" % (res.get("reglage_cle", args.get("cle", "?")), afficher(res.get("reglage_avant")), afficher(res.get("reglage_demande")))
        if cap == "ssh_regler":
            return "SSH par Tailscale %s" % ("activé" if args.get("actif", True) else "coupé")
        if cap == "serve_regler":
            return "Service publié : https :%s%s → %s" % (res.get("serve_port", args.get("port", 443)), res.get("serve_chemin", "/"), res.get("serve_cible", args.get("cible", "?")))
        if cap == "serve_retirer":
            return "Services publiés retirés (%d)" % len(res.get("serve_avant") or [])
        return {"connecter": "Connexion à Tailscale" + (" par clé" if args.get("avec_cle") else ""), "deconnecter": "Tailscale coupé", "quitter": "Machine retirée du réseau",
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
    ctx.implementer("ping", ping)
    ctx.implementer("journal", journal)
    ctx.implementer("reseau", reseau)
    ctx.implementer("services", services)
    ctx.implementer("serve_regler", journaliser("serve_regler", serve_regler), prouver_serve, defaire_serve, simuler=lambda x, port=443, cible="", **_: "publierait %s dans le réseau Tailscale (HTTPS %s)" % (cible, port))
    ctx.implementer("serve_retirer", journaliser("serve_retirer", serve_retirer), lambda c, res: not lire_services(), lambda c, res: None, simuler=lambda x, **_: "retirerait tous les services publiés par Tailscale Serve")
    ctx.implementer("defaire_geste", defaire_geste, prouver_defait, lambda c, res: None, simuler=lambda x, id=0, **_: "défairait le geste n°%s du journal" % id)
    ctx.implementer("connecter", journaliser("connecter", connecter), prouver_connecter, defaire_connecter, simuler=lambda x, nom="", ssh=False, avec_cle=False, **_: "connecterait la machine à Tailscale" + (" avec la clé enregistrée" if avec_cle else " (lien d'identification)"))
    ctx.implementer("annuler", journaliser("annuler", annuler), lambda c, res: not res.get("en_attente"), lambda c, res: None, simuler=lambda x, **_: "abandonnerait la connexion en attente")
    ctx.implementer("deconnecter", journaliser("deconnecter", deconnecter), prouver_pas_connecte, defaire_deconnecter, simuler=lambda x, **_: "couperait Tailscale sur cette machine")
    ctx.implementer("quitter", journaliser("quitter", quitter), prouver_pas_connecte, lambda c, res: connecter(c), simuler=lambda x, **_: "retirerait la machine du réseau Tailscale")
    ctx.implementer("regler", journaliser("regler", regler), prouver_regler, defaire_regler, simuler=lambda x, cle="", valeur=None, **_: "changerait le réglage Tailscale « %s »" % cle)
    ctx.implementer("ssh_regler", journaliser("ssh_regler", ssh_regler), lambda c, res: lire_ssh() == res.get("ssh_demande"), defaire_ssh, simuler=lambda x, actif=True, **_: "%s SSH par Tailscale" % ("activerait" if actif else "couperait"))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : lire_statut, resume, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/flotte (qui lit le même client pour la présence des machines)
