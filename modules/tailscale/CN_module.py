# ══════════════════════════════════════════════════════════════════
# TITRE      : Tailscale
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : tailscale
# ZONE       : CN
# VERSION CN : 0.1.0  #a171dd
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le réseau privé Tailscale de la machine, piloté depuis l'interface.
# MÉTHODE    : le client `tailscale` local ; l'état se lit dans `status --json`, jamais déduit.
# ══════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a171dd ▼▼▼
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


def _erreur(sortie, cle=""):
    """Une sortie du client, rendue lisible : sans la clé, avec la commande qui règle un refus d'accès."""
    t = str(sortie or "").strip()
    if cle:
        t = t.replace(cle, "tskey-…")
    t = re.sub(r"tskey-[A-Za-z0-9_-]+", "tskey-…", t)
    if re.search(r"access denied|profiles access denied|use 'sudo tailscale'|permission denied", t, re.I):
        return "Cassandra n'a pas le droit de piloter Tailscale : sur la machine, `sudo tailscale set --operator=cassandra` (l'installateur du module le fait)."
    if re.search(r"failed to connect to local tailscaled|tailscaled.*not running|connect: no such file", t, re.I):
        return "tailscaled ne tourne pas : `sudo systemctl enable --now tailscaled`."
    lignes = [x for x in t.splitlines() if x.strip()]
    return (lignes[-1] if lignes else "le client n'a rien répondu")[:300]


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
    """Le statut du client, aplati pour l'écran : état en clair, la machine, ses adresses, les autres machines du réseau."""
    moi = d.get("Self") or {}
    etat = ETATS.get(str(d.get("BackendState") or ""), "demarrage")
    reseau = d.get("CurrentTailnet") or {}
    pairs = []
    for p in (d.get("Peer") or {}).values():
        ls = str(p.get("LastSeen") or "")
        pairs.append({"nom": (p.get("HostName") or str(p.get("DNSName") or "").split(".")[0]), "ip": (p.get("TailscaleIPs") or [""])[0], "os": p.get("OS", ""),
                      "en_ligne": bool(p.get("Online")), "vu": "" if ls.startswith("0001") else ls[:16].replace("T", " "), "sortie": bool(p.get("ExitNode")),
                      "offre_sortie": bool(p.get("ExitNodeOption"))})
    pairs.sort(key=lambda x: (not x["en_ligne"], x["nom"].lower()))
    ips = [x for x in (d.get("TailscaleIPs") or []) if x]
    return {"etat": etat, "brut": d.get("BackendState") or "", "lien": d.get("AuthURL") or "", "nom": moi.get("HostName") or "", "dns": str(moi.get("DNSName") or "").rstrip("."),
            "ip4": next((x for x in ips if ":" not in x), ""), "ip6": next((x for x in ips if ":" in x), ""), "reseau": reseau.get("Name") or "", "suffixe": reseau.get("MagicDNSSuffix") or "",
            "version": d.get("Version") or "", "sante": [str(x)[:200] for x in (d.get("Health") or [])][:5], "pairs": pairs,
            "en_ligne": sum(1 for x in pairs if x["en_ligne"]), "ssh": bool(moi.get("sshHostKeys")) or "ssh" in str(moi.get("Capabilities") or "").lower()}


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

    def attendre(etats, delai):
        fin = time.time() + delai
        r = None
        while time.time() < fin:
            d, _ = lire_statut()
            if d is not None:
                r = resume(d)
                if r["etat"] in etats or (r["etat"] == "a_identifier" and r["lien"] and "a_identifier" in etats):
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
        args = ["up", "--reset"]
        if nom:
            args.append("--hostname=" + nom)
        if ssh:
            args.append("--ssh")
        abandonner_attente()
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
        r = attendre({"connecte", "a_identifier"}, 14)
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
        m = maintenant()
        return bool(m and (m["etat"] == "connecte" or (m["etat"] == "a_identifier" and m["lien"])))

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
