# ══════════════════════════════════════════════════════════════════
# TITRE      : Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.1.5  #cadbb4
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le réseau privé Tailscale de la machine, piloté depuis l'interface.
# MÉTHODE    : le client `tailscale` local ; l'état se lit dans `status --json`, jamais déduit.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.5 empreinte=cadbb4 ▼▼▼
"""Tailscale : voir où en est le réseau privé de la machine et le connecter depuis l'interface.

Deux façons de connecter, comme sur tailscale.com :
  - SANS clé : `tailscale up` s'ouvre, Tailscale répond par un LIEN ; la personne l'ouvre, s'identifie, et la machine rejoint son réseau. Le lien se lit dans
    `status --json` (AuthURL) ; `up` reste en attente en arrière-plan jusqu'à l'identification ou l'abandon ;
  - AVEC une clé d'authentification (tskey-…) : la machine se connecte seule. La clé vient du réglage SECRET `cle_auth` (jamais d'un argument de capacité, que le
    journal garderait) ; elle est donnée au client par un fichier à droits 0600 qui disparaît aussitôt, jamais en ligne de commande (visible dans /proc).

Rien ne se fait en root : l'installateur donne à l'utilisateur de Cassandra le droit d'opérateur du client. Un refus d'accès se dit en clair, avec la commande qui le règle.
Rien n'est inventé : un client absent, un tailscaled arrêté, une identification en attente sont des ÉTATS distincts, pas des « hors ligne » interchangeables."""
from __future__ import annotations

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


def _lancer(args, delai=DELAI):
    """(code, sortie) ; (None, raison) si le client est absent ou n'a pas répondu à temps."""
    try:
        r = subprocess.run(["tailscale"] + list(args), capture_output=True, text=True, timeout=delai, errors="replace")
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
    """Le JSON d'une sortie du client. `_lancer` joint stdout et stderr : un avertissement du client (version différente de tailscaled…) avant ou après le JSON ne doit pas
    faire croire que tailscaled est arrêté. Lève ValueError s'il n'y a pas de JSON."""
    i = str(sortie or "").find("{")
    if i < 0:
        raise ValueError("pas de JSON")
    obj, _ = json.JSONDecoder().raw_decode(sortie[i:])
    if not isinstance(obj, dict):
        raise ValueError("pas un objet JSON")
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
        if len(a) >= 2 and os.path.basename(a[0]) == "tailscale" and a[1] == "up" and "--timeout=15m" in a:
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


def brancher(ctx):
    global _point
    _point = ctx.point
    def etat(c):
        d, raison = lire_statut()
        if d is None:
            if raison == "absent":
                return {"etat": "absent", "texte": "Tailscale n'est pas installé sur cette machine.", "en_attente": False}
            return {"etat": "arrete", "texte": raison or "tailscaled ne répond pas", "en_attente": False}
        r = resume(d)
        prefs = lire_prefs()                         # une seule lecture : SSH et opérateur
        if prefs is not None:
            r["ssh"] = bool(prefs.get("RunSSH"))
            r["operateur"] = str(prefs.get("OperatorUser") or "")
            r["pilotable"] = r["operateur"] == utilisateur()      # faux : les gestes seraient refusés, l'écran le dit au lieu de proposer des boutons qui échouent
        else:
            r["ssh"], r["operateur"], r["pilotable"] = None, "", None
        p = _EN_ATTENTE["proc"]
        r["en_attente"] = bool(p and p.poll() is None) or (r["etat"] == "a_identifier" and bool(orphelins()))
        r["cle_enregistree"] = bool(str(ctx.reglage("cle_auth", "") or "").strip())
        return r

    def attendre(etats, delai, sauf_lien=""):
        """Relit l'état jusqu'à l'un des `etats`. `sauf_lien` : un lien d'identification déjà là AVANT le geste est celui d'une tentative abandonnée ; le nouveau le remplace
        quelques secondes plus tard, et c'est lui que la personne doit ouvrir."""
        fin = time.time() + delai
        r = None
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
            time.sleep(0.7)
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

    def regler(nom, ssh):
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
            regler(nom, ssh)                         # déjà connectée : ce qu'on demande (nom, SSH) s'applique quand même, sans rien relancer
            return dict(etat(c), avant="connecte")
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
                    regler(nom, ssh)                 # nom et SSH demandés : par `set`, qui ne remet rien à zéro
                return dict(etat(c), avant="deconnecte")
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
                regler(*reglages_apres)
            return dict(etat(c), avant="deconnecte")
        err = tempfile.TemporaryFile()                                 # la sortie d'erreur du `up` en attente va dans un fichier : un tube que personne ne lit finirait par le bloquer
        try:
            _EN_ATTENTE["proc"] = subprocess.Popen(["tailscale"] + args + ["--timeout=15m"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=err,
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
            regler(*reglages_apres)
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
        with _VERROU:
            abandonner_attente()
            if res.get("avant") != "connecte":
                _lancer(["down"])

    def annuler(c):
        with _VERROU:
            m = maintenant()
            abandonner_attente()
            if m is not None and m["etat"] == "connecte":
                return dict(etat(c), avant="connecte")        # rien à abandonner : `down` couperait une connexion qui marche (et peut-être la session qui pilote la machine)
            _lancer(["down"])
            return dict(etat(c), avant="en_attente")

    def deconnecter(c):
        with _VERROU:
            avant = (maintenant() or {}).get("etat", "")
            abandonner_attente()
            code, sortie = _lancer(["down"])
            if code != 0:
                raise ValueError(_erreur(sortie))
            return dict(etat(c), avant=avant)

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
            return dict(etat(c), avant=avant)

    def ssh_regler(c, actif=True):
        avant = lire_ssh()
        code, sortie = _lancer(["set", "--ssh=" + ("true" if actif else "false")])
        if code != 0:
            raise ValueError(_erreur(sortie))
        return dict(etat(c), ssh_avant=avant, ssh_demande=bool(actif))

    def prouver_pas_connecte(c, res):
        m = maintenant()
        return bool(m and m["etat"] != "connecte")

    def defaire_ssh(c, res):
        if res.get("ssh_avant") is not None:
            _lancer(["set", "--ssh=" + ("true" if res["ssh_avant"] else "false")])

    ctx.implementer("etat", etat)
    ctx.implementer("connecter", connecter, prouver_connecter, defaire_connecter, simuler=lambda x, nom="", ssh=False, avec_cle=False, **_: "connecterait la machine à Tailscale" + (" avec la clé enregistrée" if avec_cle else " (lien d'identification)"))
    ctx.implementer("annuler", annuler, lambda c, res: not res.get("en_attente"), lambda c, res: None, simuler=lambda x, **_: "abandonnerait la connexion en attente")
    ctx.implementer("deconnecter", deconnecter, prouver_pas_connecte, defaire_deconnecter, simuler=lambda x, **_: "couperait Tailscale sur cette machine")
    ctx.implementer("quitter", quitter, prouver_pas_connecte, lambda c, res: connecter(c), simuler=lambda x, **_: "retirerait la machine du réseau Tailscale")
    ctx.implementer("ssh_regler", ssh_regler, lambda c, res: lire_ssh() == res.get("ssh_demande"), defaire_ssh, simuler=lambda x, actif=True, **_: "%s SSH par Tailscale" % ("activerait" if actif else "couperait"))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : lire_statut, resume, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : modules/flotte (qui lit le même client pour la présence des machines)
