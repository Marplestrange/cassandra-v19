-- Le journal des agents : une consultation inscrite avec SA question ET SA réponse.
-- La question est toujours celle qu'on oublie de garder : une réponse sans le dossier
-- qui l'a produite ne veut rien dire. Trois rôles (claude, itare, cassandra), pas trois personnes.
CREATE TABLE journal_agents(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  qui TEXT NOT NULL DEFAULT '',
  modele TEXT NOT NULL DEFAULT '',
  etiquette TEXT NOT NULL DEFAULT '',
  consigne TEXT NOT NULL DEFAULT '',
  dossier TEXT NOT NULL DEFAULT '',
  reponse TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_journal_agents_ts ON journal_agents(ts DESC);
-- Les signatures d'anomalies : une erreur déjà vue est du bruit, une jamais vue mérite d'être lue.
CREATE TABLE journal_signatures(
  sig TEXT PRIMARY KEY, source TEXT NOT NULL DEFAULT '', sample TEXT NOT NULL DEFAULT '',
  n INTEGER NOT NULL DEFAULT 1, first_seen TEXT NOT NULL DEFAULT (datetime('now')),
  last_seen TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Les veilles sur motif : un motif cherché dans les journaux, avec son étiquette.
CREATE TABLE journal_watch(
  id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL DEFAULT '', pattern TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT '', enabled INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
