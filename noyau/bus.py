"""Le bus d'événements : la mémoire commune de tout ce qui se passe.

Un seul format pour tout (quand, quoi, qui l'a fait, sur quel objet, pour quel compte, à cause de quoi).
Les seize journaux de la V18 deviennent des vues de cette table. Le champ `cause` fabrique la LIGNÉE :
de n'importe quel événement on remonte à la perception qui l'a provoqué et on descend vers ses suites.

CLOISONNEMENT : toute lecture publique exige une `portee`, sans valeur par défaut. `TOUT` est la portée
des agents ; une adresse de compte ne voit que ses événements et le commun (compte vide). La V18 a
fui des données d'un compte à l'autre parce que « aucun compte » valait « tout voir » : ici l'oubli
est une erreur, jamais un accès.
"""
from __future__ import annotations

import json
import logging
import threading
import time

log = logging.getLogger("noyau.bus")
PROFONDEUR_MAX = 8   # un abonné qui émet un événement qui réveille un abonné qui émet... est coupé net
TOUT = "*"           # portée des agents


def filtre_portee(portee) -> tuple:
    """(fragment SQL, paramètres) qui borne une requête à la portée. Refuse une portée absente."""
    if portee == TOUT:
        return "", ()
    if not isinstance(portee, str) or not portee:
        raise ValueError("portée obligatoire : TOUT, ou l'adresse d'un compte")
    return " AND (compte='' OR compte=?)", (portee,)


def visible(ligne: dict, portee) -> bool:
    return portee == TOUT or ligne.get("compte", "") in ("", portee)


class Bus:
    def __init__(self, base):
        self.base = base
        self._abonnes = []          # (type, fonction, module)
        self._pile = threading.local()

    def emettre(self, type: str, source: str, acteur: str = "noyau", objet=None, cause=None, donnees=None, compte: str = "") -> int:
        ot, oi = (objet if objet else ("", ""))
        eid = self.base.ecrire(
            "INSERT INTO evenements(ts, type, source, acteur, objet_type, objet_id, compte, cause, donnees) VALUES (?,?,?,?,?,?,?,?,?)",
            (time.time(), type, source, acteur, str(ot), str(oi), compte or "", cause,
             json.dumps(donnees or {}, ensure_ascii=False, default=str)))
        self._distribuer(self._lire(eid))
        return eid

    def ecouter(self, type: str, fonction, module: str) -> None:
        self._abonnes.append((type, fonction, module))

    def _distribuer(self, ev: dict) -> None:
        profondeur = getattr(self._pile, "n", 0)
        if profondeur >= PROFONDEUR_MAX:
            log.warning("distribution coupée à la profondeur %d (%s)", profondeur, ev["type"])
            return
        self._pile.n = profondeur + 1
        try:
            for motif, fn, module in list(self._abonnes):
                if motif != ev["type"]:
                    continue
                try:
                    fn(ev)
                except Exception as ex:   # un abonné en panne ne fait pas taire les autres, mais se voit
                    log.exception("abonné en échec (%s)", module)
                    if ev["type"] != "noyau.abonne_en_echec":
                        self.emettre("noyau.abonne_en_echec", source=module, acteur="noyau", cause=ev["id"], compte=ev["compte"],
                                     donnees={"evenement": ev["type"], "erreur": str(ex)[:300]})
        finally:
            self._pile.n = profondeur

    @staticmethod
    def _ligne(r: dict) -> dict:
        r = dict(r)
        r["donnees"] = json.loads(r.get("donnees") or "{}")
        return r

    def _lire(self, eid: int):
        """Interne, SANS portée : réservé au noyau (distribution, lignée)."""
        r = self.base.lire("SELECT * FROM evenements WHERE id=?", (eid,))
        return self._ligne(r[0]) if r else None

    def lire(self, eid: int, *, portee):
        filtre_portee(portee)
        ev = self._lire(eid)
        return ev if ev and visible(ev, portee) else None

    def chronologie(self, objet_type: str, objet_id: str, *, portee, limite: int = 100) -> list:
        """Tout ce qui est arrivé à un objet, tous moteurs confondus, du plus ancien au plus récent."""
        frag, p = filtre_portee(portee)
        rows = self.base.lire("SELECT * FROM evenements WHERE objet_type=? AND objet_id=?" + frag + " ORDER BY id DESC LIMIT ?",
                              (objet_type, str(objet_id)) + p + (int(limite),))
        return [self._ligne(r) for r in reversed(rows)]

    def recents(self, *, portee, limite: int = 50, type_prefixe: str = "") -> list:
        frag, p = filtre_portee(portee)
        if type_prefixe:
            rows = self.base.lire("SELECT * FROM evenements WHERE type LIKE ?" + frag + " ORDER BY id DESC LIMIT ?", (type_prefixe + "%",) + p + (int(limite),))
        else:
            rows = self.base.lire("SELECT * FROM evenements WHERE 1=1" + frag + " ORDER BY id DESC LIMIT ?", p + (int(limite),))
        return [self._ligne(r) for r in reversed(rows)]

    def lignee(self, eid: int, *, portee) -> dict:
        """{'causes': [de la racine jusqu'à l'événement], 'suites': [tous les descendants]}, bornée à la portée."""
        filtre_portee(portee)
        causes, vu, courant = [], set(), self._lire(eid)
        if courant is None or not visible(courant, portee):
            return {"causes": [], "suites": []}
        while courant and courant["id"] not in vu:
            vu.add(courant["id"])
            causes.append(courant)
            courant = self._lire(courant["cause"]) if courant["cause"] else None
        causes.reverse()
        suites, front = [], [eid]
        while front:
            rows = self.base.lire("SELECT * FROM evenements WHERE cause IN (%s) ORDER BY id" % ",".join("?" * len(front)), tuple(front))
            front = [r["id"] for r in rows if r["id"] not in vu]
            suites += [self._ligne(r) for r in rows]
            vu.update(front)
        return {"causes": [c for c in causes if visible(c, portee)], "suites": [s for s in suites if visible(s, portee)]}
