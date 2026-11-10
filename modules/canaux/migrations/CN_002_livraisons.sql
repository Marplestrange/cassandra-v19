-- La file des livraisons : ce que le moteur doit porter hors de la cloche, ce qui attend (et pourquoi), ce qui est parti, ce qui a échoué.
-- Une ligne sans compte est une notification à DÉVELOPPER (on ne sait pas encore qui la reçoit : c'est notifications qui le dit).
-- L'unicité est la garantie qu'on ne sonne pas deux fois : une notification part une fois par niveau atteint, par destinataire et par canal.
CREATE TABLE canal_livraisons(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  notif INTEGER NOT NULL, niveau TEXT NOT NULL DEFAULT '', compte TEXT NOT NULL DEFAULT '', canal TEXT NOT NULL DEFAULT '',
  est_essai INTEGER NOT NULL DEFAULT 0, etat TEXT NOT NULL DEFAULT 'attente', motif TEXT NOT NULL DEFAULT '',
  tentatives INTEGER NOT NULL DEFAULT 0, pas_avant REAL NOT NULL DEFAULT 0, cree REAL NOT NULL, maj REAL NOT NULL,
  UNIQUE(notif, niveau, compte, canal)
);
CREATE INDEX canal_livraisons_dues ON canal_livraisons(etat, pas_avant);
