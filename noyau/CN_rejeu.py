# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le corpus de rejeu : les appels réels d'un point d'évolution
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #90793d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : garde, par point d'évolution, les ENTRÉES réellement reçues (distinctes, comptées), avec une partition réservée que le générateur ne voit jamais.
# MÉTHODE    : une table SQLite ; l'entrée est identifiée par son empreinte ; la partition réservée se décide par l'empreinte (déterministe) ; borne par point, les cas dorés jamais évincés.
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=90793d ▼▼▼
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
import fnmatch
import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path

PART_RESERVEE = 5                  # un cas sur N est réservé
MAX_PAR_POINT = 2000               # entrées distinctes gardées par point (les cas dorés ne sont jamais évincés)
EXCLUS_PRIVES = ("courrier.*", "coffre.*", "memoire.*", "notes.*", "salon.*", "ged.*", "contacts.*", "agents.*", "agenda.*", "canvas.*")      # les points dont l'entrée EST le contenu privé d'un compte : par défaut, seule leur mesure est gardée
PURGE_TOUS_LES = 100               # on vérifie la borne tous les N enregistrements
MAX_ENTREE_OCTETS = 65536          # une entrée plus grosse n'est pas gardée : ce n'est pas un cas de test, c'est un fichier ou une pièce jointe (et c'est une donnée privée en clair)

SCHEMA = """CREATE TABLE IF NOT EXISTS appels(
  gid TEXT NOT NULL, h TEXT NOT NULL, entree TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 1, origine TEXT NOT NULL DEFAULT 'reel', reserve INTEGER NOT NULL,
  premier REAL NOT NULL, dernier REAL NOT NULL, ms_somme REAL NOT NULL DEFAULT 0, ms_n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(gid, h));
CREATE INDEX IF NOT EXISTS appels_gid ON appels(gid, reserve);
CREATE TABLE IF NOT EXISTS appels_comptes(gid TEXT NOT NULL, h TEXT NOT NULL, compte TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(gid, h, compte));
CREATE INDEX IF NOT EXISTS appels_comptes_c ON appels_comptes(compte);
CREATE TABLE IF NOT EXISTS mesures(gid TEXT PRIMARY KEY, appels INTEGER NOT NULL DEFAULT 0, ms_somme REAL NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS absorbes(source TEXT NOT NULL, gid TEXT NOT NULL, h TEXT NOT NULL, n INTEGER NOT NULL, ms_somme REAL NOT NULL, ms_n INTEGER NOT NULL, PRIMARY KEY(source, gid, h));"""


def empreinte(entree) -> str:
    """L'identité d'une entrée : le même contenu donne la même empreinte, quel que soit l'ordre des clés."""
    return hashlib.sha256(json.dumps(entree, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


def est_reserve(h: str) -> bool:
    return int(h[:8], 16) % PART_RESERVEE == 0


class Rejeu:
    def __init__(self, chemin, max_par_point: int = MAX_PAR_POINT, actif: bool = True, exclus=()):
        """`exclus` : des motifs de points (« courrier.* ») dont les entrées ne sont JAMAIS gardées (des données trop privées pour dormir en clair dans un corpus)."""
        self.chemin, self.max_par_point, self.actif = Path(chemin), int(max_par_point), bool(actif)
        self.exclus = tuple(str(x) for x in exclus)
        self._verrou = threading.Lock()
        self._compte = 0
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with self._con() as c:
            c.executescript(SCHEMA)
            try:
                c.execute("ALTER TABLE appels ADD COLUMN attribue INTEGER NOT NULL DEFAULT 0")      # une base d'avant les comptes
            except sqlite3.OperationalError:
                pass
        if os.name == "posix":
            try:
                os.chmod(self.chemin, 0o600)                       # des entrées réelles : lisibles du seul service
            except OSError:
                pass

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
    def enregistrer(self, gid: str, entree, sortie=None, duree_ms: float = 0.0, source: str = "reference", compte: str | None = None) -> None:
        """Compatible avec `enregistreur` de ServicePoints. La sortie n'est pas gardée (voir plus haut) ; la durée sert aux statistiques du trafic réel.
        `compte` : à qui appartient l'entrée (elle part avec lui à `purger_compte`). Un point EXCLU ne garde que sa mesure (combien d'appels, combien de temps) : jamais son contenu."""
        if not self.actif:
            return
        if any(fnmatch.fnmatchcase(gid, m) for m in self.exclus):
            with self._verrou, self._con() as c:
                c.execute("INSERT INTO mesures(gid,appels,ms_somme) VALUES(?,1,?) ON CONFLICT(gid) DO UPDATE SET appels=appels+1, ms_somme=ms_somme+excluded.ms_somme", (gid, float(duree_ms)))
            return
        h = empreinte(entree)
        t = time.time()
        corps = json.dumps(entree, ensure_ascii=False, sort_keys=True)
        if len(corps.encode("utf-8")) > MAX_ENTREE_OCTETS:
            return
        with self._verrou, self._con() as c:
            c.execute("INSERT INTO appels(gid,h,entree,reserve,premier,dernier,ms_somme,ms_n,attribue) VALUES(?,?,?,?,?,?,?,1,?) "
                      "ON CONFLICT(gid,h) DO UPDATE SET n=n+1, dernier=excluded.dernier, ms_somme=ms_somme+excluded.ms_somme, ms_n=ms_n+1, attribue=MAX(attribue, excluded.attribue)",
                      (gid, h, corps, 1 if est_reserve(h) else 0, t, t, float(duree_ms), 1 if compte else 0))
            if compte:
                c.execute("INSERT INTO appels_comptes(gid,h,compte,n) VALUES(?,?,?,1) ON CONFLICT(gid,h,compte) DO UPDATE SET n=n+1", (gid, h, str(compte)))
            self._compte += 1
            if self._compte % PURGE_TOUS_LES == 0:
                self._borner(c)

    def _borner(self, c) -> None:
        """Au-delà de la borne, on évince les entrées les moins fréquentes puis les plus anciennes, POUR CHAQUE point (pas seulement celui du dernier enregistrement). Un cas doré n'est jamais évincé."""
        for gid, n in c.execute("SELECT gid, COUNT(*) FROM appels GROUP BY gid HAVING COUNT(*) > ?", (self.max_par_point,)).fetchall():
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

    def purger_compte(self, compte: str) -> dict:
        """Le compte s'en va (suppression, demande d'effacement) : ses rattachements disparaissent, et toute entrée réelle qui n'appartenait QU'À lui avec. Une entrée partagée par un autre compte reste ; une entrée sans compte (trafic du noyau) aussi."""
        with self._verrou, self._con() as c:
            rattaches = c.execute("DELETE FROM appels_comptes WHERE compte=?", (str(compte),)).rowcount
            entrees = c.execute("DELETE FROM appels WHERE origine='reel' AND attribue=1 AND NOT EXISTS (SELECT 1 FROM appels_comptes k WHERE k.gid=appels.gid AND k.h=appels.h)").rowcount
        return {"rattachements": rattaches, "entrees": entrees}

    def comptes(self, gid: str | None = None) -> dict:
        """Combien d'entrées distinctes chaque compte a nourries (pour le dire à l'administrateur, jamais pour les lui montrer)."""
        with self._con() as c:
            q, a = "SELECT compte, COUNT(*) FROM appels_comptes", []
            if gid:
                q, a = q + " WHERE gid=?", [gid]
            return {r[0]: r[1] for r in c.execute(q + " GROUP BY compte", a)}

    def stats(self, gid: str) -> dict:
        with self._con() as c:
            m = c.execute("SELECT appels, ms_somme FROM mesures WHERE gid=?", (gid,)).fetchone()
            r = c.execute("SELECT COUNT(*) d, COALESCE(SUM(ms_n),0) a, COALESCE(SUM(reserve),0) r, COALESCE(SUM(origine='dore'),0) o, "
                          "COALESCE(SUM(ms_somme),0) ms, COALESCE(SUM(ms_n),0) mn FROM appels WHERE gid=?", (gid,)).fetchone()
        appels, ms, mn = r["a"] + (m["appels"] if m else 0), r["ms"] + (m["ms_somme"] if m else 0.0), r["mn"] + (m["appels"] if m else 0)      # un point exclu n'a que sa mesure
        return {"distincts": r["d"], "appels": appels, "reserve": r["r"], "visible": r["d"] - r["r"], "dores": r["o"], "duree_moyenne_ms": round(ms / mn, 3) if mn else None}

    def points(self) -> list:
        with self._con() as c:
            return [r[0] for r in c.execute("SELECT DISTINCT gid FROM appels ORDER BY gid")]
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Rejeu (stockage), empreinte, est_reserve. Aucune logique d'évolution ici : il garde la matière du banc d'essai.
# EC : néant. Jamais évolutif : le juge ne se réécrit pas (docs/CN_NEXUS.md §4).
# LIEN : noyau/CN_evaluateur.py (qui le lit), noyau/CN_points.py (qui l'alimente par `enregistreur`), docs/CN_EVOLUTION.md §2.
