"""Les réglages : ce que la V18 gardait dans UN fichier config.json réécrit en entier à chaque sauvegarde (d'où la leçon : « relire avant d'écrire »,
sans quoi un réglage disparaissait). Ici chaque réglage est une LIGNE, écrite seule, avec son historique.

  - un module DÉCLARE ses réglages dans son manifeste ([[reglages]]) ; ils s'appellent « module.reglage » ;
  - un réglage a un type (texte, entier, booleen, choix, secret), un défaut, et une portée : global, ou propre à chaque compte ;
  - une valeur qui ne passe pas son type est refusée ; une valeur absente rend le défaut ;
  - chaque changement garde l'avant et l'après (de quoi défaire, et savoir qui l'a fait) ; un secret n'est jamais rendu en clair par une lecture
    d'administration : seul le module qui l'a déclaré le lit, par `ctx.reglage()`.
"""
from __future__ import annotations

import json
import threading
import time

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


class Reglages:
    def __init__(self, base):
        self.base = base
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

    def _brut(self, cle, compte):
        r = self.base.lire("SELECT valeur FROM reglages WHERE cle=? AND compte=?", (cle, compte))
        return (True, json.loads(r[0]["valeur"])) if r else (False, None)

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
        ok, avant = self._brut(cle, compte)
        now = time.time()
        with self.base.transaction() as c:
            c.execute("INSERT INTO reglages(cle, compte, valeur, maj, par) VALUES(?,?,?,?,?) "
                      "ON CONFLICT(cle, compte) DO UPDATE SET valeur=excluded.valeur, maj=excluded.maj, par=excluded.par",
                      (cle, compte, json.dumps(v), now, par))
            c.execute("INSERT INTO reglages_historique(cle, compte, avant, apres, ts, par) VALUES(?,?,?,?,?,?)",
                      (cle, compte, json.dumps(avant) if ok else None, json.dumps(v), now, par))
        return {"cle": cle, "compte": compte, "avant": avant, "avait": ok, "apres": v}

    def retirer(self, cle: str, compte: str = "", par: str = "") -> dict:
        """Rend la valeur au défaut (ou au global) : la ligne disparaît."""
        self._def(cle)
        ok, avant = self._brut(cle, compte)
        if not ok:
            return {"cle": cle, "compte": compte, "avait": False}
        now = time.time()
        with self.base.transaction() as c:
            c.execute("DELETE FROM reglages WHERE cle=? AND compte=?", (cle, compte))
            c.execute("INSERT INTO reglages_historique(cle, compte, avant, apres, ts, par) VALUES(?,?,?,NULL,?,?)",
                      (cle, compte, json.dumps(avant), now, par))
        return {"cle": cle, "compte": compte, "avant": avant, "avait": True}

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
