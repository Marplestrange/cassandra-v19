# ══════════════════════════════════════════════════════════════════
# TITRE      : Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.1.1  #dba004
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le réseau privé Tailscale de la machine, piloté depuis l'interface.
# MÉTHODE    : le client `tailscale` local ; l'état se lit dans `status --json`, jamais déduit.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=dba004 ▼▼▼
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
import subprocess
import tempfile
import time

DELAI = 10
CLE = re.compile(r"^tskey-[A-Za-z0-9_-]{8,200}$")
NOM = re.compile(r"^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")
_EN_ATTENTE = {"proc": None}                       # le `tailscale up` sans clé, en attente d'identification


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
    """Une sortie du client, rendue lisible : sans la clé, avec la commande qui règle un refus d'accès. Le calcul est un POINT D'ÉVOLUTION : points/EC_erreur.py."""
    return _appeler_point("erreur", {"sortie": sortie, "cle": cle})["valeur"]


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
        return json.loads(sortie), None
    except ValueError:
        return None, _erreur(sortie)


ETATS = {"Running": "connecte", "NeedsLogin": "a_identifier", "NeedsMachineAuth": "a_approuver", "Stopped": "deconnecte", "Starting": "demarrage", "NoState": "demarrage"}


def resume(d):
    """Le statut du client, aplati pour l'écran : état en clair, la machine, ses adresses, les autres machines du réseau. Le calcul est un POINT D'ÉVOLUTION : points/EC_resume.py."""
    return _appeler_point("resume", {"d": d})["valeur"]


def lire_ssh():
    """SSH par Tailscale est-il activé ? Ce sont les préférences qui le disent (`RunSSH`), pas le statut."""
    code, sortie = _lancer(["debug", "prefs"])
    if code != 0:
        return None
    try:
        return bool(json.loads(sortie).get("RunSSH"))
    except ValueError:
        return None


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
        r["ssh"] = lire_ssh()
        p = _EN_ATTENTE["proc"]
        r["en_attente"] = bool(p and p.poll() is None)
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
            time.sleep(0.7)
        return r

    def abandonner_attente():
        p = _EN_ATTENTE["proc"]
        _EN_ATTENTE["proc"] = None
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(3)
            except Exception:                       # noqa: BLE001
                p.kill()

    def connecter(c, nom="", ssh=False, avec_cle=False):
        d, raison = lire_statut()
        if d is None:
            raise ValueError("Tailscale n'est pas utilisable : %s" % (("le client est absent (CN_install.sh --module tailscale l'installe)") if raison == "absent" else raison))
        if resume(d)["etat"] == "connecte":
            return dict(etat(c), avant="connecte")
        nom = str(nom or "").strip().lower()
        if nom and not NOM.match(nom):
            raise ValueError("Nom de machine invalide : lettres, chiffres et tirets seulement")
        # --reset remet TOUT à zéro, l'opérateur compris : sans --operator, la connexion réussit une fois puis Cassandra n'a plus le droit de rien piloter
        args = ["up", "--reset", "--operator=" + utilisateur()]
        if nom:
            args.append("--hostname=" + nom)
        if ssh:
            args.append("--ssh")
        abandonner_attente()
        ancien_lien = resume(d)["lien"]
        if avec_cle:
            cle = str(ctx.reglage("cle_auth", "") or "").strip()
            if not CLE.match(cle):
                raise ValueError("La clé d'authentification doit ressembler à tskey-auth-… (créée sur login.tailscale.com › Settings › Keys)")
            fd, chemin = tempfile.mkstemp(prefix="ts-")                # mkstemp crée le fichier en 0600 : lisible par l'utilisateur de Cassandra seul
            try:
                os.write(fd, cle.encode())
                os.close(fd)
                code, sortie = _lancer(args + ["--auth-key=file:" + chemin, "--timeout=45s"], delai=60)
            finally:
                try:
                    os.unlink(chemin)
                except OSError:
                    pass
            if code != 0:
                raise ValueError(_erreur(sortie, cle))
            return dict(attendre({"connecte"}, 8) or etat(c), avant="deconnecte")
        try:
            _EN_ATTENTE["proc"] = subprocess.Popen(["tailscale"] + args + ["--timeout=15m"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                                   start_new_session=True)
        except FileNotFoundError:
            raise ValueError("Tailscale n'est pas installé")
        r = attendre({"connecte", "a_identifier"}, 14, ancien_lien)
        p = _EN_ATTENTE["proc"]
        if (r is None or not r["lien"]) and (r is None or r["etat"] != "connecte") and p is not None and p.poll() not in (None, 0):
            erreur = _erreur((p.stderr.read() or b"").decode("utf-8", "replace") if p.stderr else "")
            _EN_ATTENTE["proc"] = None
            raise ValueError(erreur)
        if r is None or (r["etat"] != "connecte" and not r["lien"]):
            raise ValueError("Tailscale n'a pas donné de lien de connexion : réessaie dans un instant")
        return dict(r, en_attente=True, avant="deconnecte")

    def maintenant():
        d, _ = lire_statut()
        return resume(d) if d is not None else None

    # Chaque geste qui écrit rend ce qu'il faut pour être PROUVÉ (relire l'état) et DÉFAIT (revenir à l'état d'avant).
    def prouver_connecter(c, res):
        """Connectée, ou un lien d'identification en attente. Quelques lectures : le lien se renouvelle un instant quand une tentative en remplace une autre."""
        for _ in range(8):
            m = maintenant()
            if m and (m["etat"] == "connecte" or (m["etat"] == "a_identifier" and m["lien"])):
                return True
            time.sleep(0.8)
        return False

    def defaire_connecter(c, res):
        abandonner_attente()
        if res.get("avant") != "connecte":
            _lancer(["down"])

    def annuler(c):
        abandonner_attente()
        _lancer(["down"])
        return dict(etat(c), avant="en_attente")

    def deconnecter(c):
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
