-- Les OOM acquittés : un événement de mémoire saturée, vu et accepté, cesse d'être compté (signature = date + processus tué).
CREATE TABLE securite_oom_acquits(
  sig TEXT PRIMARY KEY, ts TEXT NOT NULL DEFAULT (datetime('now')), qui TEXT NOT NULL DEFAULT ''
);
