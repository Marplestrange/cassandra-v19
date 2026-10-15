-- L'autonomie par domaine et par geste : un réglage par geste, sinon par domaine, sinon le palier global.
CREATE TABLE autonomie_reglages(
  cle TEXT PRIMARY KEY, reglages TEXT NOT NULL DEFAULT '{}',
  ts TEXT NOT NULL DEFAULT (datetime('now','localtime')), par TEXT NOT NULL DEFAULT ''
);
-- Le disjoncteur : un geste qui se déclenche ne fait plus rien seul, jusqu'à ce qu'on le débloque.
CREATE TABLE autonomie_disj(
  cle TEXT PRIMARY KEY, etat TEXT NOT NULL DEFAULT 'arme', raison TEXT NOT NULL DEFAULT '',
  depuis TEXT NOT NULL DEFAULT '', echecs_suite INTEGER NOT NULL DEFAULT 0
);
-- Le journal des actions autonomes (pour mesurer la boucle et les échecs).
CREATE TABLE autonomie_actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, cle TEXT NOT NULL,
  sujet TEXT NOT NULL DEFAULT '', ok INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_aut_act ON autonomie_actions(cle, sujet, ts);
