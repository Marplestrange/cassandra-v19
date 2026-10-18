# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le corpus de rejeu : les appels réels d'un point d'évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #3ef4c1
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : garde, par point d'évolution, les ENTRÉES réellement reçues (distinctes, comptées), avec une partition réservée que le générateur ne voit jamais.
# MÉTHODE    : une table SQLite ; l'entrée est identifiée par son empreinte ; la partition réservée se décide par l'empreinte (déterministe) ; borne par point, les cas dorés jamais évincés.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3ef4c1 ▼▼▼
"""Le corpus de rejeu (docs/CN_EVOLUTION.md §2) : la matière du banc d'essai de toute évolution.

On ne garde que les ENTRÉES : la sortie de référence est recalculée par la référence du dépôt à chaque évaluation, car c'est elle la spécification
(une sortie enregistrée pourrait venir d'une EC, donc d'un écart déjà passé). Chaque entrée distincte est comptée : un cas fréquent pèse plus.

La PARTITION RÉSERVÉE (un cas sur cinq, décidé par l'empreinte de l'entrée, donc stable d'un jour à l'autre) n'est jamais montrée à ce qui génère les variantes :
elle sert à vérifier qu'un gain tient hors de ce que le générateur a vu. Un évaluateur sans jeu réservé se laisse tromper par son propre candidat.

CONFIDENTIALITÉ : une entrée contient des données réelles (comptes, domaines). Ce stockage reste sur l'instance ; l'export d'un corpus (docs/CN_EVOLUTION.md §2 septies,
fédération) passera par une anonymisation, jamais par ce fichier tel quel. Seul l'administrateur de l'instance et le moteur d'évolution le lisent.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

PART_RESERVEE = 5                  # un cas sur N est réservé
MAX_PAR_POINT = 2000               # entrées distinctes gardées par point (les cas dorés ne sont jamais évincés)
PURGE_TOUS_LES = 100               # on vérifie la borne tous les N enregistrements

SCHEMA = """CREATE TABLE IF NOT EXISTS appels(
  gid TEXT NOT NULL, h TEXT NOT NULL, entree TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 1, origine TEXT NOT NULL DEFAULT 'reel', reserve INTEGER NOT NULL,
  premier REAL NOT NULL, dernier REAL NOT NULL, ms_somme REAL NOT NULL DEFAULT 0, ms_n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(gid, h));
CREATE INDEX IF NOT EXISTS appels_gid ON appels(gid, reserve);
CREATE TABLE IF NOT EXISTS absorbes(source TEXT NOT NULL, gid TEXT NOT NULL, h TEXT NOT NULL, n INTEGER NOT NULL, ms_somme REAL NOT NULL, ms_n INTEGER NOT NULL, PRIMARY KEY(source, gid, h));"""


def empreinte(entree) -> str:
    """L'identité d'une entrée : le même contenu donne la même empreinte, quel que soit l'ordre des clés."""
    return hashlib.sha256(json.dumps(entree, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


def est_reserve(h: str) -> bool:
    return int(h[:8], 16) % PART_RESERVEE == 0


class Rejeu:
    def __init__(self, chemin, max_par_point: int = MAX_PAR_POINT, actif: bool = True):
        self.chemin, self.max_par_point, self.actif = Path(chemin), int(max_par_point), bool(actif)
        self._verrou = threading.Lock()
        self._compte = 0
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as c:
            c.executescript(SCHEMA)

    @contextlib.contextmanager
    def _con(self):
        """Une connexion par opération, FERMÉE à la sortie (le « with » de sqlite3 valide mais ne ferme pas) ; validée si tout va bien, annulée sinon."""
        c = sqlite3.connect(str(self.chemin), timeout=10)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    # ── l'écriture ───────────────────────────────────────────────────────
    def enregistrer(self, gid: str, entree, sortie=None, duree_ms: float = 0.0, source: str = "reference") -> None:
        """Compatible avec `enregistreur` de ServicePoints. La sortie n'est pas gardée (voir plus haut) ; la durée sert aux statistiques du trafic réel."""
        if not self.actif:
            return
        h = empreinte(entree)
        t = time.time()
        corps = json.dumps(entree, ensure_ascii=False, sort_keys=True)
        with self._verrou, self._con() as c:
            c.execute("INSERT INTO appels(gid,h,entree,reserve,premier,dernier,ms_somme,ms_n) VALUES(?,?,?,?,?,?,?,1) "
                      "ON CONFLICT(gid,h) DO UPDATE SET n=n+1, dernier=excluded.dernier, ms_somme=ms_somme+excluded.ms_somme, ms_n=ms_n+1",
                      (gid, h, corps, 1 if est_reserve(h) else 0, t, t, float(duree_ms)))
            self._compte += 1
            if self._compte % PURGE_TOUS_LES == 0:
                self._borner(c, gid)

    def _borner(self, c, gid: str) -> None:
        """Au-delà de la borne, on évince les entrées les moins fréquentes puis les plus anciennes. Un cas doré n'est jamais évincé."""
        n = c.execute("SELECT COUNT(*) FROM appels WHERE gid=?", (gid,)).fetchone()[0]
        if n > self.max_par_point:
            c.execute("DELETE FROM appels WHERE rowid IN (SELECT rowid FROM appels WHERE gid=? AND origine!='dore' ORDER BY n ASC, dernier ASC LIMIT ?)",
                      (gid, n - self.max_par_point))

    def importer(self, gid: str, cas: list, origine: str = "dore") -> int:
        """Ajoute des cas connus (le corpus doré du dépôt) : jamais évincés. Rend le nombre d'entrées nouvelles."""
        nouveaux = 0
        t = time.time()
        with self._verrou, self._con() as c:
            for x in cas:
                entree = x["entree"] if isinstance(x, dict) and "entree" in x else x
                h = empreinte(entree)
                if c.execute("SELECT 1 FROM appels WHERE gid=? AND h=?", (gid, h)).fetchone():
                    c.execute("UPDATE appels SET origine=? WHERE gid=? AND h=? AND origine!='dore'", (origine, gid, h))
                    continue
                c.execute("INSERT INTO appels(gid,h,entree,n,origine,reserve,premier,dernier) VALUES(?,?,?,1,?,?,?,?)",
                          (gid, h, json.dumps(entree, ensure_ascii=False, sort_keys=True), origine, 1 if est_reserve(h) else 0, t, t))
                nouveaux += 1
        return nouveaux

    def absorber(self, chemin) -> int:
        """Prend les appels enregistrés par un AUTRE processus (le démon du Sensorium garde les siens dans son propre fichier) : seuls les DELTAS depuis la dernière absorption sont ajoutés,
        donc absorber deux fois de suite ne compte rien deux fois. Rend le nombre d'appels ajoutés. Un fichier absent ou illisible n'est pas une erreur : rien n'est ajouté."""
        autre = Path(chemin)
        if not autre.exists():
            return 0
        source = str(autre.resolve())
        try:
            lecture = sqlite3.connect(autre.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
            lecture.row_factory = sqlite3.Row
            try:
                lignes = lecture.execute("SELECT gid,h,entree,n,reserve,premier,dernier,ms_somme,ms_n FROM appels WHERE origine!='dore'").fetchall()
            finally:
                lecture.close()
        except sqlite3.Error:
            return 0
        ajoutes = 0
        with self._verrou, self._con() as c:
            for r in lignes:
                vu = c.execute("SELECT n, ms_somme, ms_n FROM absorbes WHERE source=? AND gid=? AND h=?", (source, r["gid"], r["h"])).fetchone()
                dn, dms, dmn = r["n"] - (vu["n"] if vu else 0), r["ms_somme"] - (vu["ms_somme"] if vu else 0.0), r["ms_n"] - (vu["ms_n"] if vu else 0)
                if dn <= 0:
                    continue
                c.execute("INSERT INTO appels(gid,h,entree,n,origine,reserve,premier,dernier,ms_somme,ms_n) VALUES(?,?,?,?, 'reel', ?,?,?,?,?) "
                          "ON CONFLICT(gid,h) DO UPDATE SET n=n+excluded.n, dernier=MAX(dernier, excluded.dernier), ms_somme=ms_somme+excluded.ms_somme, ms_n=ms_n+excluded.ms_n",
                          (r["gid"], r["h"], r["entree"], dn, 1 if est_reserve(r["h"]) else 0, r["premier"], r["dernier"], dms, dmn))
                c.execute("INSERT OR REPLACE INTO absorbes(source,gid,h,n,ms_somme,ms_n) VALUES(?,?,?,?,?,?)", (source, r["gid"], r["h"], r["n"], r["ms_somme"], r["ms_n"]))
                ajoutes += dn
        return ajoutes

    # ── la lecture ───────────────────────────────────────────────────────
    def corpus(self, gid: str, partition: str = "tout") -> list:
        """Les entrées d'un point, dans un ordre STABLE (par empreinte). `partition` : « visible » (ce que le générateur a le droit de voir), « reserve », « tout »."""
        cond = {"visible": " AND reserve=0", "reserve": " AND reserve=1", "tout": ""}[partition]
        with self._con() as c:
            lignes = c.execute("SELECT h, entree, n, origine, reserve FROM appels WHERE gid=?" + cond + " ORDER BY h", (gid,)).fetchall()
        return [{"h": r["h"], "entree": json.loads(r["entree"]), "n": r["n"], "origine": r["origine"], "reserve": bool(r["reserve"])} for r in lignes]

    def stats(self, gid: str) -> dict:
        with self._con() as c:
            r = c.execute("SELECT COUNT(*) d, COALESCE(SUM(ms_n),0) a, COALESCE(SUM(reserve),0) r, COALESCE(SUM(origine='dore'),0) o, "
                          "COALESCE(SUM(ms_somme),0) ms, COALESCE(SUM(ms_n),0) mn FROM appels WHERE gid=?", (gid,)).fetchone()
        return {"distincts": r["d"], "appels": r["a"], "reserve": r["r"], "visible": r["d"] - r["r"], "dores": r["o"], "duree_moyenne_ms": round(r["ms"] / r["mn"], 3) if r["mn"] else None}

    def points(self) -> list:
        with self._con() as c:
            return [r[0] for r in c.execute("SELECT DISTINCT gid FROM appels ORDER BY gid")]
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Rejeu (stockage), empreinte, est_reserve. Aucune logique d'évolution ici : il garde la matière du banc d'essai.
# EC : néant. Jamais évolutif : le juge ne se réécrit pas (docs/CN_NEXUS.md §4).
# LIEN : noyau/CN_evaluateur.py (qui le lit), noyau/CN_points.py (qui l'alimente par `enregistreur`), docs/CN_EVOLUTION.md §2.
