-- La fiche d'une société, rubrique par rubrique (JSON borné par le code), et son historique : qui a changé quoi, de quoi le défaire.
CREATE TABLE fiche(
  societe TEXT NOT NULL, rubrique TEXT NOT NULL, donnees TEXT NOT NULL DEFAULT '{}', maj REAL NOT NULL DEFAULT 0,
  PRIMARY KEY(societe, rubrique)
);
CREATE TABLE historique(
  id INTEGER PRIMARY KEY AUTOINCREMENT, societe TEXT NOT NULL, ts REAL NOT NULL, qui TEXT NOT NULL DEFAULT '', rubrique TEXT NOT NULL DEFAULT '',
  resume TEXT NOT NULL DEFAULT '', avant TEXT NOT NULL DEFAULT '', apres TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_historique_societe ON historique(societe, id DESC);
