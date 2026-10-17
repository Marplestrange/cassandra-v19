"""Le registre des objets : tout ce que Cassandra connaît, avec UN propriétaire par type.

Un site, un certificat, un conteneur, un domaine : même table, même fiche. Seul le module qui déclare
un type (section [[objets]] de son manifeste) peut en écrire les objets. Les autres lisent, dans leur
portée (voir CN_bus.py : toute lecture exige une portée explicite).
"""
from __future__ import annotations

import json
import time

from .CN_bus import filtre_portee, visible


class Registre:
    def __init__(self, base, bus):
        self.base = base
        self.bus = bus
        self.proprietaires = {}   # type d'objet -> module

    def declarer(self, module: str, type: str) -> None:
        self.proprietaires[type] = module

    def poser(self, module: str, type: str, id: str, libelle: str, etat: str = "", donnees=None, cause=None, compte: str = "") -> bool:
        """Crée ou met à jour. Rend True si quelque chose a changé (et alors un événement est écrit)."""
        if self.proprietaires.get(type) != module:
            raise PermissionError("le module « %s » ne possède pas le type d'objet « %s »" % (module, type))
        id = str(id)
        avant = self._lire(type, id)
        d = json.dumps(donnees or {}, ensure_ascii=False, default=str)
        if avant and avant["libelle"] == libelle and avant["etat"] == etat and avant["compte"] == (compte or "") \
                and json.dumps(avant["donnees"], ensure_ascii=False, default=str) == d:
            return False
        self.base.ecrire(
            "INSERT INTO objets(type,id,module,libelle,etat,compte,donnees,maj) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(type,id) DO UPDATE SET libelle=excluded.libelle, etat=excluded.etat, compte=excluded.compte, donnees=excluded.donnees, maj=excluded.maj",
            (type, id, module, libelle, etat, compte or "", d, time.time()))
        self.bus.emettre("objet.pose" if not avant else "objet.change", source=module, acteur="module", objet=(type, id), cause=cause, compte=compte,
                         donnees={"libelle": libelle, "etat_avant": avant["etat"] if avant else None, "etat": etat})
        return True

    def retirer(self, module: str, type: str, id: str, cause=None) -> bool:
        if self.proprietaires.get(type) != module:
            raise PermissionError("le module « %s » ne possède pas le type d'objet « %s »" % (module, type))
        avant = self._lire(type, id)
        if not avant:
            return False
        self.base.ecrire("DELETE FROM objets WHERE type=? AND id=?", (type, str(id)))
        self.bus.emettre("objet.retire", source=module, acteur="module", objet=(type, str(id)), cause=cause, compte=avant["compte"])
        return True

    @staticmethod
    def _ligne(r: dict) -> dict:
        r = dict(r)
        r["donnees"] = json.loads(r.get("donnees") or "{}")
        return r

    def _lire(self, type: str, id: str):
        r = self.base.lire("SELECT * FROM objets WHERE type=? AND id=?", (type, str(id)))
        return self._ligne(r[0]) if r else None

    def lire(self, type: str, id: str, *, portee):
        filtre_portee(portee)
        o = self._lire(type, id)
        return o if o and visible(o, portee) else None

    def lister(self, *, portee, type: str = "", etat: str = "") -> list:
        frag, p = filtre_portee(portee)
        sql, params = "SELECT * FROM objets WHERE 1=1" + frag, list(p)
        if type:
            sql += " AND type=?"; params.append(type)
        if etat:
            sql += " AND etat=?"; params.append(etat)
        return [self._ligne(r) for r in self.base.lire(sql + " ORDER BY type, id", tuple(params))]

    def compter(self, *, portee) -> dict:
        frag, p = filtre_portee(portee)
        return {r["type"]: r["n"] for r in self.base.lire("SELECT type, COUNT(*) AS n FROM objets WHERE 1=1" + frag + " GROUP BY type", p)}
