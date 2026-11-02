-- Le journal des gestes de réparation faits depuis le Sensorium : qui, sur quelle mesure, quel geste, réussi ou non, ce que la commande root a répondu.
CREATE TABLE sensorium_gestes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL DEFAULT (datetime('now')), qui TEXT NOT NULL DEFAULT '', wkey TEXT NOT NULL DEFAULT '',
  geste TEXT NOT NULL DEFAULT '', op TEXT NOT NULL DEFAULT '', ok INTEGER NOT NULL DEFAULT 0, sortie TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_sn_gestes ON sensorium_gestes(id DESC);
