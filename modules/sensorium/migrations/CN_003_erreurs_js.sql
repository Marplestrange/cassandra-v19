-- Les erreurs JavaScript que les écrans des utilisateurs signalent : une ligne par erreur distincte (empreinte), son nombre de fois, quand, sur quelle page.
CREATE TABLE sensorium_erreurs_js(
  id INTEGER PRIMARY KEY AUTOINCREMENT, empreinte TEXT NOT NULL UNIQUE, message TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '', ligne INTEGER NOT NULL DEFAULT 0,
  page TEXT NOT NULL DEFAULT '', qui TEXT NOT NULL DEFAULT '', n INTEGER NOT NULL DEFAULT 1, premiere TEXT NOT NULL DEFAULT (datetime('now')), derniere TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_sn_erreurs_js ON sensorium_erreurs_js(derniere DESC);
