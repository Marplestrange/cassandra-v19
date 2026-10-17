-- Les tâches sont à la PERSONNE, pas au projet : un projet supprimé ne les emporte pas, il les laisse libres.
CREATE TABLE taches(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, projet_id INTEGER,
  texte TEXT NOT NULL, statut TEXT NOT NULL DEFAULT 'todo', echeance TEXT NOT NULL DEFAULT '',
  cree REAL NOT NULL, fait_le REAL,
  source TEXT NOT NULL DEFAULT 'manuel', origine TEXT NOT NULL DEFAULT '',     -- d'où elle vient (une détection, un message...) : une tâche née d'une détection ne ressemble pas à une tâche saisie
  notes TEXT NOT NULL DEFAULT '', priorite INTEGER NOT NULL DEFAULT 1,           -- 0 basse, 1 normale, 2 haute, 3 urgente
  parent_id INTEGER, recurrence TEXT NOT NULL DEFAULT '', charge INTEGER NOT NULL DEFAULT 0, alarme TEXT NOT NULL DEFAULT '',
  avancement INTEGER NOT NULL DEFAULT 0, raison TEXT NOT NULL DEFAULT '', responsable TEXT NOT NULL DEFAULT '', etape_id INTEGER,
  reports INTEGER NOT NULL DEFAULT 0                                             -- combien de fois l'échéance a été repoussée
);
CREATE INDEX taches_compte ON taches(compte, statut);
CREATE INDEX taches_projet ON taches(projet_id, statut);
CREATE INDEX taches_parent ON taches(parent_id);
CREATE UNIQUE INDEX taches_origine ON taches(compte, source, origine) WHERE origine <> '' AND source <> 'manuel';
CREATE TABLE liens(id INTEGER PRIMARY KEY AUTOINCREMENT, tache_id INTEGER NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', cree REAL NOT NULL, UNIQUE(tache_id, kind, ref));
CREATE TABLE journal(id INTEGER PRIMARY KEY AUTOINCREMENT, tache_id INTEGER NOT NULL, texte TEXT NOT NULL, acteur TEXT NOT NULL DEFAULT '', ts REAL NOT NULL);
CREATE INDEX journal_tache ON journal(tache_id);
