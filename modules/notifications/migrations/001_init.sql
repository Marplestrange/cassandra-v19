-- Le Centre de notifications. Une ligne par notification ; l'état « lu / pris en compte » est PAR PERSONNE (notif_dest),
-- jamais sur la notification elle-même : en V18, écrire « vu » sur la ligne cachait à un nouvel administrateur ce qu'un ancien avait lu.
CREATE TABLE notifs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL, maj REAL NOT NULL,
  source TEXT NOT NULL, niveau TEXT NOT NULL, titre TEXT NOT NULL, corps TEXT NOT NULL DEFAULT '',
  cle TEXT NOT NULL DEFAULT '', n INTEGER NOT NULL DEFAULT 1,
  sujet TEXT NOT NULL DEFAULT '', nature TEXT NOT NULL DEFAULT 'evenement',
  destinataires TEXT NOT NULL DEFAULT '["admins"]',
  resolue INTEGER NOT NULL DEFAULT 0, resolue_le REAL, resolue_par TEXT NOT NULL DEFAULT '',
  supprimee INTEGER NOT NULL DEFAULT 0,
  expire_le REAL, auteur TEXT NOT NULL DEFAULT '', provenance TEXT NOT NULL DEFAULT ''
);
-- Une seule notification OUVERTE par clé : la même panne qui se répète incrémente `n`, elle ne s'empile pas.
CREATE UNIQUE INDEX notifs_cle_ouverte ON notifs(cle) WHERE cle <> '' AND resolue = 0 AND supprimee = 0;
CREATE INDEX notifs_ts ON notifs(ts);
CREATE TABLE notif_dest(
  notif INTEGER NOT NULL, compte TEXT NOT NULL, vu_le REAL, acquitte_le REAL,
  PRIMARY KEY(notif, compte)
);
