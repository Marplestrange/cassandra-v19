-- Les tâches que Cassandra a créées, avec leur intention en clair. Celles du système (crontab, cron.d) se lisent par le courtier, elles n'ont pas de ligne ici.
CREATE TABLE naturelles(
  id INTEGER PRIMARY KEY AUTOINCREMENT, description TEXT NOT NULL, horaire TEXT NOT NULL, commande TEXT NOT NULL, utilisateur TEXT NOT NULL DEFAULT 'root',
  actif INTEGER NOT NULL DEFAULT 1, enrobee INTEGER NOT NULL DEFAULT 1, cree REAL NOT NULL
);
-- Les exécutions réelles (par l'enrobage, ou « exécuter maintenant »). Le journal du système prouve qu'un cron a été LANCÉ, jamais qu'il a RÉUSSI.
CREATE TABLE executions(id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL, debut TEXT NOT NULL, duree_ms INTEGER NOT NULL DEFAULT 0, code INTEGER, sortie TEXT NOT NULL DEFAULT '', declencheur TEXT NOT NULL DEFAULT 'cron');
CREATE INDEX executions_ref ON executions(ref, id);
-- Ce que l'administrateur a marqué critique (exempté du mode maintenance), par référence : les crons du système n'ont pas de ligne ailleurs.
CREATE TABLE critiques(ref TEXT PRIMARY KEY, libelle TEXT NOT NULL DEFAULT '');
-- Les rattachements d'une tâche à un projet.
CREATE TABLE liens(ref TEXT NOT NULL, projet_id INTEGER NOT NULL, libelle TEXT NOT NULL DEFAULT '', PRIMARY KEY(ref, projet_id));
-- Verrou, fenêtre, réessais, motif d'échec, enchaînement.
CREATE TABLE reglages_tache(
  ref TEXT PRIMARY KEY, fenetre_min INTEGER NOT NULL DEFAULT 0, verrou INTEGER NOT NULL DEFAULT 0, essais INTEGER NOT NULL DEFAULT 0, motif_echec TEXT NOT NULL DEFAULT '',
  apres_ref TEXT NOT NULL DEFAULT '', apres_si_ok INTEGER NOT NULL DEFAULT 1, nom TEXT NOT NULL DEFAULT ''
);
-- « Qu'est-ce qui a changé » est la première question quand une tâche se met à mal tourner.
CREATE TABLE modifs(id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL, ts REAL NOT NULL, acteur TEXT NOT NULL DEFAULT '', quoi TEXT NOT NULL);
CREATE INDEX modifs_ref ON modifs(ref, id);
-- Les silences déjà signalés, pour ne pas republier la même alerte à chaque passage.
CREATE TABLE signales(cle TEXT PRIMARY KEY, ts REAL NOT NULL);
-- La maintenance : une date de fin, jamais une intention.
CREATE TABLE maintenance(id INTEGER PRIMARY KEY CHECK(id=1), fin TEXT NOT NULL DEFAULT '');
INSERT INTO maintenance(id, fin) VALUES (1, '');
