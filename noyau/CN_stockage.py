# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le stockage d'un module
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : noyau
# ZONE       : CN
# VERSION CN : 0.1.0  #800a73
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le stockage d'un module : SA base SQLite, à lui, avec ses migrations. C'est la réponse à « 169 tables et 88 lues par plusieurs modules » de la V18 : une table appartient à UN module, dans UN fichier (donnees/modules/<module>.db), et personn
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=800a73 ▼▼▼
"""Le stockage d'un module : SA base SQLite, à lui, avec ses migrations. C'est la réponse à « 169 tables et 88 lues par plusieurs modules » de la V18 :
une table appartient à UN module, dans UN fichier (donnees/modules/<module>.db), et personne d'autre n'y touche. Pour partager, on passe par une
capacité ou par un événement.

  - les migrations sont des fichiers `migrations/NNN_nom.sql` du dossier du module, appliqués dans l'ordre, une seule fois chacun ;
  - une migration déjà appliquée ne se modifie pas : son empreinte est gardée, un changement est refusé (on en écrit une nouvelle) ;
  - si une migration échoue, rien de ce fichier n'est gardé et le module ne se branche pas : on ne démarre pas sur un schéma à moitié fait ;
  - le module le demande dans son manifeste : [permissions] stockage = true.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path

from .CN_base import Base

_MIG = re.compile(r"^(?:CN_)?(\d{3})_[a-z0-9_]+\.sql$")


def identite(nom: str) -> str:
    """L'identité d'une migration : son nom SANS le préfixe de zone « CN_ » (docs/CN_FORMAT.md §3 quater). Renommer 001_init.sql en CN_001_init.sql
    ne la fait pas rejouer : l'instance qui l'a déjà appliquée la retrouve sous la même identité."""
    return nom[3:] if nom.startswith("CN_") else nom
SUIVI = """CREATE TABLE IF NOT EXISTS _migrations(version TEXT PRIMARY KEY, empreinte TEXT NOT NULL, ts REAL NOT NULL DEFAULT (strftime('%s','now')));"""


class MigrationRefusee(RuntimeError):
    pass


class StockageParSociete:
    """Se comporte comme le Stockage du module, mais chaque appel va à la base de la société de l'acte (`ctx.societe`, par fil ; vide = la société principale).
    Le module garde `db = ctx.stockage` tel quel : rien à changer dans son code."""

    def __init__(self, resoudre, societe_courante):
        object.__setattr__(self, "_resoudre", resoudre)
        object.__setattr__(self, "_courante", societe_courante)

    def _base(self):
        return self._resoudre(self._courante() or "1")

    def __getattr__(self, nom):
        return getattr(self._base(), nom)


class Stockage(Base):
    def __init__(self, chemin, dossier_migrations=None):
        super().__init__(chemin, schema=SUIVI)
        self.appliquees = []
        if dossier_migrations:
            self.migrer(dossier_migrations)

    def migrer(self, dossier) -> list:
        """Applique les migrations pas encore faites. Rend la liste de celles qu'elle vient d'appliquer."""
        d = Path(dossier)
        if not d.is_dir():
            return []
        fichiers = sorted((p for p in d.iterdir() if p.is_file() and p.suffix == ".sql"), key=lambda p: identite(p.name))
        for p in fichiers:
            if not _MIG.match(p.name):
                raise MigrationRefusee("%s : nom de migration invalide ([CN_]NNN_nom.sql, minuscules)" % p.name)
        vues = {}
        for p in fichiers:
            if identite(p.name) in vues:
                raise MigrationRefusee("%s et %s : la même migration deux fois (même identité)" % (vues[identite(p.name)], p.name))
            vues[identite(p.name)] = p.name
        faites = {r["version"]: r["empreinte"] for r in self.lire("SELECT version, empreinte FROM _migrations")}
        nouvelles = []
        for p in fichiers:
            texte = p.read_bytes().decode("utf-8").replace(chr(13) + chr(10), chr(10))      # CRLF ou LF : la même empreinte (un dépôt reclonné ne doit pas « modifier » une migration)
            emp = hashlib.sha256(texte.encode("utf-8")).hexdigest()
            ident = identite(p.name)
            if ident in faites:
                if faites[ident] != emp:
                    raise MigrationRefusee("%s : cette migration a déjà été appliquée puis modifiée (on en écrit une nouvelle, on ne retouche pas l'ancienne)" % p.name)
                continue
            c = self._ouvrir()
            try:
                c.execute("BEGIN")                     # chaque instruction DANS la transaction : un échec n'en laisse rien
                for instruction in _instructions(texte):
                    c.execute(instruction)
                c.execute("INSERT INTO _migrations(version, empreinte) VALUES(?,?)", (ident, emp))
                c.execute("COMMIT")
            except sqlite3.Error as ex:
                try:
                    c.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise MigrationRefusee("%s : %s" % (p.name, ex)) from ex
            finally:
                c.close()
            nouvelles.append(ident)
        self.appliquees = sorted(set(self.appliquees) | set(nouvelles))
        return nouvelles


def _instructions(texte: str) -> list:
    """Découpe un script SQL en instructions complètes (sqlite3.complete_statement : les « ; » dans une chaîne ou un déclencheur ne coupent pas)."""
    sortie, courant = [], ""
    for ligne in texte.splitlines(True):
        courant += ligne
        if sqlite3.complete_statement(courant):
            if courant.strip():
                sortie.append(courant.strip())
            courant = ""
    if courant.strip():
        sortie.append(courant.strip())
    return sortie
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : identite, MigrationRefusee, Stockage, _instructions
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
