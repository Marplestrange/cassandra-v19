# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La base du noyau
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #9495f5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La base du noyau : un fichier SQLite, des connexions courtes, des écritures qui réessaient.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9495f5 ▼▼▼
"""La base du noyau : un fichier SQLite, des connexions courtes, des écritures qui réessaient.

Leçon de la V18 : un verrou SQLite vient presque toujours d'une connexion laissée ouverte.
Ici AUCUNE connexion ne vit plus que l'opération qui l'a ouverte.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS evenements(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, type TEXT NOT NULL, source TEXT NOT NULL,
  acteur TEXT NOT NULL, objet_type TEXT NOT NULL DEFAULT '', objet_id TEXT NOT NULL DEFAULT '',
  compte TEXT NOT NULL DEFAULT '', cause INTEGER, donnees TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS ev_objet ON evenements(objet_type, objet_id, id);
CREATE INDEX IF NOT EXISTS ev_cause ON evenements(cause);
CREATE INDEX IF NOT EXISTS ev_type ON evenements(type, id);
CREATE TABLE IF NOT EXISTS objets(
  type TEXT NOT NULL, id TEXT NOT NULL, module TEXT NOT NULL, libelle TEXT NOT NULL, etat TEXT NOT NULL DEFAULT '',
  compte TEXT NOT NULL DEFAULT '', donnees TEXT NOT NULL DEFAULT '{}', maj REAL NOT NULL, PRIMARY KEY(type, id));
CREATE TABLE IF NOT EXISTS savoir(
  capacite TEXT PRIMARY KEY, palier TEXT NOT NULL, reussites INTEGER NOT NULL DEFAULT 0,
  echecs_de_suite INTEGER NOT NULL DEFAULT 0, maj REAL NOT NULL);
CREATE TABLE IF NOT EXISTS constats(
  cle TEXT PRIMARY KEY, module TEXT NOT NULL, detecteur TEXT NOT NULL, objet_type TEXT NOT NULL, objet_id TEXT NOT NULL,
  titre TEXT NOT NULL, etat TEXT NOT NULL, ouvert REAL NOT NULL, ferme REAL, evenement INTEGER);
CREATE TABLE IF NOT EXISTS etat_noyau(cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS modules_etat(
  id TEXT PRIMARY KEY, installe INTEGER NOT NULL DEFAULT 0, actif INTEGER NOT NULL DEFAULT 0,
  maj REAL NOT NULL, par TEXT NOT NULL DEFAULT '', raison TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS moteurs_etat(
  cle TEXT PRIMARY KEY, derniere REAL, duree REAL, executions INTEGER NOT NULL DEFAULT 0, echecs INTEGER NOT NULL DEFAULT 0,
  echecs_de_suite INTEGER NOT NULL DEFAULT 0, erreur TEXT NOT NULL DEFAULT '', figes INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS droit_admins(compte TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS droit_groupes(groupe TEXT PRIMARY KEY, libelle TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS droit_membres(compte TEXT NOT NULL, groupe TEXT NOT NULL, PRIMARY KEY(compte, groupe));
CREATE TABLE IF NOT EXISTS droit_accords(
  sujet_type TEXT NOT NULL, sujet TEXT NOT NULL, droit TEXT NOT NULL, accord INTEGER NOT NULL, PRIMARY KEY(sujet_type, sujet, droit));
CREATE TABLE IF NOT EXISTS comptes(
  compte TEXT PRIMARY KEY, hash TEXT NOT NULL, display_name TEXT NOT NULL DEFAULT '', role_label TEXT NOT NULL DEFAULT '',
  contact_email TEXT NOT NULL DEFAULT '', phone TEXT NOT NULL DEFAULT '', lang TEXT NOT NULL DEFAULT 'fr',
  fp_account TEXT NOT NULL DEFAULT '', sites TEXT NOT NULL DEFAULT '[]', cree REAL NOT NULL, maj REAL NOT NULL,
  unix_user TEXT NOT NULL DEFAULT '', superadmin INTEGER NOT NULL DEFAULT 0, type TEXT NOT NULL DEFAULT 'humain',
  invite_par TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS reglages(
  cle TEXT NOT NULL, compte TEXT NOT NULL DEFAULT '', valeur TEXT NOT NULL, maj REAL NOT NULL, par TEXT NOT NULL DEFAULT '', PRIMARY KEY(cle, compte));
CREATE TABLE IF NOT EXISTS reglages_historique(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cle TEXT NOT NULL, compte TEXT NOT NULL DEFAULT '', avant TEXT, apres TEXT, ts REAL NOT NULL, par TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS reglages_hist_cle ON reglages_historique(cle, id);
CREATE TABLE IF NOT EXISTS agents_jetons(
  id TEXT PRIMARY KEY, compte TEXT NOT NULL, cree REAL NOT NULL, dernier_vu REAL, actif INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS comptes_corbeille(id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, instantane TEXT NOT NULL, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  id TEXT PRIMARY KEY, compte TEXT NOT NULL, court TEXT NOT NULL, cree REAL NOT NULL, derniere REAL NOT NULL,
  ip TEXT NOT NULL DEFAULT '', agent TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS sessions_compte ON sessions(compte);
CREATE TABLE IF NOT EXISTS jetons_mdp(id TEXT PRIMARY KEY, compte TEXT NOT NULL, expire REAL NOT NULL, utilise INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS tentatives(cle TEXT NOT NULL, ts REAL NOT NULL);
CREATE INDEX IF NOT EXISTS tentatives_cle ON tentatives(cle, ts);
-- Les sociétés. Il y en a toujours au moins une : la principale (« 1 »), qui ne se supprime pas ; tout compte appartient à une société.
CREATE TABLE IF NOT EXISTS societes(
  id TEXT PRIMARY KEY, nom TEXT NOT NULL DEFAULT '', principale INTEGER NOT NULL DEFAULT 0,
  archivee INTEGER NOT NULL DEFAULT 0, cree REAL NOT NULL DEFAULT 0);
INSERT OR IGNORE INTO societes(id, nom, principale, cree) VALUES('1', 'Société principale', 1, 0);
-- Les modules de chaque société : un module « vital » est ouvert partout ; les autres le sont là où on les a ouverts. Sans ligne : ouvert dans la société principale seulement.
CREATE TABLE IF NOT EXISTS societe_modules(societe TEXT NOT NULL, module TEXT NOT NULL, actif INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(societe, module));
-- Ce qu'une société met à la disposition d'une autre (comme le partage de Multicompany) : un type d'objet (« utilisateurs »), tous ses éléments ou ceux qu'on a choisis.
CREATE TABLE IF NOT EXISTS societe_partages(source TEXT NOT NULL, destinataire TEXT NOT NULL, type TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'tous', actif INTEGER NOT NULL DEFAULT 1, cree REAL NOT NULL DEFAULT 0, par TEXT NOT NULL DEFAULT '', PRIMARY KEY(source, destinataire, type));
CREATE TABLE IF NOT EXISTS societe_partage_elements(source TEXT NOT NULL, destinataire TEXT NOT NULL, type TEXT NOT NULL, element TEXT NOT NULL, PRIMARY KEY(source, destinataire, type, element));
-- Un groupe de droits peut être attaché à UNE société : c'est une « fonction » (administrateur, comptable…) qui ne vaut que là.
CREATE TABLE IF NOT EXISTS droit_groupe_portee(groupe TEXT PRIMARY KEY, societe TEXT NOT NULL);
"""


class Base:
    def __init__(self, chemin, schema=None):
        """`schema` : None pour la base du noyau (son schéma et ses colonnes ajoutées après coup) ; un texte SQL pour le stockage d'un module."""
        self.chemin = str(chemin)
        noyau = schema is None
        if self.chemin != ":memory:":
            Path(self.chemin).parent.mkdir(parents=True, exist_ok=True)
        c = self._ouvrir()   # executescript valide d'office : il ne vit pas dans notre transaction
        try:
            c.executescript(SCHEMA if noyau else schema)
            for col, defn in (() if not noyau else (("unix_user", "TEXT NOT NULL DEFAULT ''"), ("superadmin", "INTEGER NOT NULL DEFAULT 0"), ("type", "TEXT NOT NULL DEFAULT 'humain'"), ("invite_par", "TEXT NOT NULL DEFAULT ''"), ("desactive", "INTEGER NOT NULL DEFAULT 0"), ("societe", "TEXT NOT NULL DEFAULT '1'"))):    # une base d'avant les colonnes
                if col not in [r[1] for r in c.execute("PRAGMA table_info(comptes)")]:
                    c.execute("ALTER TABLE comptes ADD COLUMN %s %s" % (col, defn))
            if noyau and "description" not in [r[1] for r in c.execute("PRAGMA table_info(droit_groupes)")]:
                c.execute("ALTER TABLE droit_groupes ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        finally:
            c.close()

    def _ouvrir(self) -> sqlite3.Connection:
        c = sqlite3.connect(self.chemin, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        return c

    def lire(self, sql: str, params=()) -> list:
        c = self._ouvrir()
        try:
            return [dict(r) for r in c.execute(sql, params).fetchall()]
        finally:
            c.close()

    @contextmanager
    def transaction(self):
        """BEGIN IMMEDIATE avec reprises : le verrou d'écriture se prend d'emblée, pas à mi-chemin."""
        c = self._ouvrir()
        try:
            for essai in range(6):
                try:
                    c.execute("BEGIN IMMEDIATE")
                    break
                except sqlite3.OperationalError as ex:
                    if "locked" not in str(ex).lower() or essai == 5:
                        raise
                    time.sleep(0.2 * (essai + 1))
            try:
                yield c
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise
        finally:
            c.close()

    def ecrire(self, sql: str, params=()) -> int:
        with self.transaction() as c:
            return c.execute(sql, params).lastrowid
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : Base
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
