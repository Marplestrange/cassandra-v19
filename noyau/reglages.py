"""Les réglages : ce que la V18 gardait dans UN fichier config.json réécrit en entier à chaque sauvegarde (d'où la leçon : « relire avant d'écrire »,
sans quoi un réglage disparaissait). Ici chaque réglage est une LIGNE, écrite seule, avec son historique.

  - un module DÉCLARE ses réglages dans son manifeste ([[reglages]]) ; ils s'appellent « module.reglage » ;
  - un réglage a un type (texte, entier, booleen, choix, secret), un défaut, et une portée : global, ou propre à chaque compte ;
  - une valeur qui ne passe pas son type est refusée ; une valeur absente rend le défaut ;
  - chaque changement garde l'avant et l'après (de quoi défaire, et savoir qui l'a fait) ; un secret n'est jamais rendu en clair par une lecture
    d'administration : seul le module qui l'a déclaré le lit, par `ctx.reglage()`.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import secrets as _secrets
import threading
import time

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:                      # sans la bibliothèque, un secret ne s'écrit pas : on ne le garde jamais en clair
    AESGCM = None

log = logging.getLogger("noyau.reglages")
PREFIXE = "enc1:"

TYPES = ("texte", "entier", "booleen", "choix", "secret")
PORTEES = ("global", "compte")


def valider(r, valeur):
    """(valeur normalisée, erreur). `r` est un Reglage déclaré."""
    t = r.type
    if t in ("texte", "secret"):
        if not isinstance(valeur, str):
            return None, "un texte est attendu"
        if len(valeur) > 4000:
            return None, "texte trop long (4000 caractères au plus)"
        return valeur, ""
    if t == "entier":
        if isinstance(valeur, bool) or not isinstance(valeur, int):
            return None, "un entier est attendu"
        if r.minimum is not None and valeur < r.minimum:
            return None, "au moins %s" % r.minimum
        if r.maximum is not None and valeur > r.maximum:
            return None, "au plus %s" % r.maximum
        return valeur, ""
    if t == "booleen":
        if not isinstance(valeur, bool):
            return None, "vrai ou faux est attendu"
        return valeur, ""
    if t == "choix":
        if valeur not in r.choix:
            return None, "parmi : %s" % ", ".join(str(c) for c in r.choix)
        return valeur, ""
    return None, "type inconnu"


class SecretIllisible(RuntimeError):
    pass


class Reglages:
    """Les secrets sont CHIFFRÉS au repos (AES-256-GCM) avec une clé gardée à part, dans un fichier lisible de son seul propriétaire. Cela protège les
    sauvegardes et les copies de la base ; cela ne protège pas d'un accès au serveur lui-même (qui lit aussi la clé). Chaque valeur est liée à son
    réglage et à son compte (données associées) : recopier un secret chiffré d'une ligne à l'autre ne donne rien."""

    def __init__(self, base, fichier_cle=None):
        self.base = base
        self._fichier_cle = fichier_cle
        self._cle = None
        self.connus = {}                 # « module.reglage » -> (module, Reglage)
        self._verrou = threading.Lock()

    def declarer(self, manifeste) -> None:
        with self._verrou:
            for r in manifeste.reglages:
                self.connus["%s.%s" % (manifeste.id, r.id)] = (manifeste.id, r)

    def oublier(self, module: str) -> None:
        """Un module débranché n'offre plus ses réglages ; les valeurs posées sont gardées (il peut revenir)."""
        with self._verrou:
            for cle in [k for k, (m, _) in self.connus.items() if m == module]:
                del self.connus[cle]

    def _def(self, cle):
        c = self.connus.get(cle)
        if c is None:
            raise KeyError("réglage inconnu (aucun module actif ne le déclare) : %s" % cle)
        return c[1]

    # ---- le chiffrement des secrets ----
    def _cle_secrets(self):
        if AESGCM is None:
            raise SecretIllisible("la bibliothèque « cryptography » manque : un secret ne s'écrit pas en clair, il n'est donc pas écrit")
        if self._cle is None:
            if self._fichier_cle is None:
                self._cle = _secrets.token_bytes(32)                      # sans fichier (essais) : une clé de la durée du processus
                log.warning("réglages : pas de fichier de clé, les secrets ne survivront pas au redémarrage")
            else:
                chemin = str(self._fichier_cle)
                if os.path.exists(chemin):
                    with open(chemin, "rb") as f:
                        self._cle = f.read()
                    if len(self._cle) != 32:
                        raise SecretIllisible("le fichier de clé des secrets est invalide : %s" % chemin)
                else:
                    os.makedirs(os.path.dirname(chemin) or ".", exist_ok=True)
                    cle = _secrets.token_bytes(32)
                    fd = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)       # lisible de son seul propriétaire
                    with os.fdopen(fd, "wb") as f:
                        f.write(cle)
                    self._cle = cle
        return self._cle

    def chiffrer(self, valeur, cle, compte):
        nonce = _secrets.token_bytes(12)
        ct = AESGCM(self._cle_secrets()).encrypt(nonce, str(valeur).encode("utf-8"), ("%s|%s" % (cle, compte)).encode("utf-8")) if AESGCM else None
        if ct is None:
            raise SecretIllisible("chiffrement indisponible")
        return PREFIXE + base64.b64encode(nonce + ct).decode("ascii")

    def dechiffrer(self, chiffre, cle, compte):
        try:
            brut = base64.b64decode(chiffre[len(PREFIXE):])
            return AESGCM(self._cle_secrets()).decrypt(brut[:12], brut[12:], ("%s|%s" % (cle, compte)).encode("utf-8")).decode("utf-8")
        except SecretIllisible:
            raise
        except Exception:
            raise SecretIllisible("le secret de « %s » est illisible (clé changée ou valeur altérée)" % cle)

    def _brut(self, cle, compte):
        """(posé ?, valeur). Un secret est rendu EN CLAIR, déchiffré ; un secret resté en clair d'avant le chiffrement est chiffré au passage."""
        r = self.base.lire("SELECT valeur FROM reglages WHERE cle=? AND compte=?", (cle, compte))
        if not r:
            return False, None
        v = json.loads(r[0]["valeur"])
        c = self.connus.get(cle)
        if c is not None and c[1].type == "secret" and isinstance(v, str):
            if v.startswith(PREFIXE):
                return True, self.dechiffrer(v, cle, compte)
            if v:
                try:
                    self.base.ecrire("UPDATE reglages SET valeur=? WHERE cle=? AND compte=?", (json.dumps(self.chiffrer(v, cle, compte)), cle, compte))
                except SecretIllisible:
                    pass
        return True, v

    def brut_chiffre(self, cle, compte):
        """La valeur CHIFFRÉE telle qu'elle est rangée (pour un retour arrière : on la remet sans jamais la déchiffrer), ou None."""
        r = self.base.lire("SELECT valeur FROM reglages WHERE cle=? AND compte=?", (cle, compte))
        v = json.loads(r[0]["valeur"]) if r else None
        if isinstance(v, str) and v and not v.startswith(PREFIXE):
            v = self.chiffrer(v, cle, compte)
        return v

    def poser_chiffre(self, cle, compte, chiffre, par=""):
        """Remet une valeur chiffrée d'avant (retour arrière)."""
        self._def(cle)
        now = time.time()
        with self.base.transaction() as c:
            c.execute("INSERT INTO reglages(cle, compte, valeur, maj, par) VALUES(?,?,?,?,?) ON CONFLICT(cle, compte) DO UPDATE SET valeur=excluded.valeur, maj=excluded.maj, par=excluded.par",
                      (cle, compte, json.dumps(chiffre), now, par))
            c.execute("INSERT INTO reglages_historique(cle, compte, avant, apres, ts, par) VALUES(?,?,?,?,?,?)", (cle, compte, None, json.dumps("***"), now, par))

    def valeur(self, cle: str, compte: str = ""):
        """La valeur EFFECTIVE : celle du compte si le réglage est de portée compte et qu'il l'a posée, sinon la globale, sinon le défaut."""
        d = self._def(cle)
        if d.portee == "compte" and compte:
            ok, v = self._brut(cle, compte)
            if ok:
                return v
        ok, v = self._brut(cle, "")
        return v if ok else d.defaut

    def poser(self, cle: str, valeur, compte: str = "", par: str = "") -> dict:
        """Écrit UN réglage (jamais un fichier entier). `compte` : la valeur propre à ce compte (portée compte) ; vide : la valeur globale."""
        d = self._def(cle)
        if compte and d.portee != "compte":
            raise ValueError("« %s » est un réglage global : il n'a pas de valeur par compte" % cle)
        v, err = valider(d, valeur)
        if err:
            raise ValueError("%s : %s" % (cle, err))
        secret = d.type == "secret"
        ok, avant = self._brut(cle, compte)
        avant_chiffre = self.brut_chiffre(cle, compte) if (secret and ok) else None
        stocke = self.chiffrer(v, cle, compte) if (secret and v != "") else v
        now = time.time()
        with self.base.transaction() as c:
            c.execute("INSERT INTO reglages(cle, compte, valeur, maj, par) VALUES(?,?,?,?,?) "
                      "ON CONFLICT(cle, compte) DO UPDATE SET valeur=excluded.valeur, maj=excluded.maj, par=excluded.par",
                      (cle, compte, json.dumps(stocke), now, par))
            c.execute("INSERT INTO reglages_historique(cle, compte, avant, apres, ts, par) VALUES(?,?,?,?,?,?)",
                      (cle, compte, (json.dumps("***") if (secret and ok) else (json.dumps(avant) if ok else None)), json.dumps("***" if secret else v), now, par))
        if secret:
            return {"cle": cle, "compte": compte, "avant": "***" if ok else None, "avait": ok, "apres": "***", "avant_chiffre": avant_chiffre}
        return {"cle": cle, "compte": compte, "avant": avant, "avait": ok, "apres": v}

    def retirer(self, cle: str, compte: str = "", par: str = "") -> dict:
        """Rend la valeur au défaut (ou au global) : la ligne disparaît."""
        self._def(cle)
        ok, avant = self._brut(cle, compte)
        if not ok:
            return {"cle": cle, "compte": compte, "avait": False}
        secret = self._def(cle).type == "secret"
        avant_chiffre = self.brut_chiffre(cle, compte) if secret else None
        now = time.time()
        with self.base.transaction() as c:
            c.execute("DELETE FROM reglages WHERE cle=? AND compte=?", (cle, compte))
            c.execute("INSERT INTO reglages_historique(cle, compte, avant, apres, ts, par) VALUES(?,?,?,NULL,?,?)",
                      (cle, compte, json.dumps("***" if secret else avant), now, par))
        return {"cle": cle, "compte": compte, "avant": "***" if secret else avant, "avait": True, "avant_chiffre": avant_chiffre}

    def historique(self, cle: str, compte: str = "", limite: int = 20) -> list:
        d = self._def(cle)
        sql = "SELECT ts, par, avant, apres, compte FROM reglages_historique WHERE cle=?" + ("" if compte == "*" else " AND compte=?")
        rows = self.base.lire(sql + " ORDER BY id DESC LIMIT ?", (cle,) + (() if compte == "*" else (compte,)) + (int(limite),))
        masque = d.type == "secret"
        return [{"ts": r["ts"], "par": r["par"], "compte": r["compte"],
                 "avant": ("***" if masque and r["avant"] is not None else (json.loads(r["avant"]) if r["avant"] is not None else None)),
                 "apres": ("***" if masque and r["apres"] is not None else (json.loads(r["apres"]) if r["apres"] is not None else None))} for r in rows]

    def liste(self, module: str = "", compte: str = "", global_visible: bool = True) -> list:
        """Les réglages déclarés, leurs valeurs effectives, les secrets MASQUÉS (« *** » s'ils ont une valeur, vide sinon)."""
        out = []
        with self._verrou:
            items = sorted(self.connus.items())
        for cle, (mod, d) in items:
            if module and mod != module:
                continue
            if d.portee == "global" and not global_visible:
                continue
            v = self.valeur(cle, compte)
            pose = self._brut(cle, compte if d.portee == "compte" and compte else "")[0]
            if d.type == "secret":
                v = "***" if (v not in (None, "")) else ""
            out.append({"cle": cle, "module": mod, "libelle": d.libelle, "type": d.type, "portee": d.portee, "valeur": v,
                        "defaut": ("***" if d.type == "secret" and d.defaut else d.defaut), "pose": pose, "choix": list(d.choix), "aide": d.aide})
        return out
