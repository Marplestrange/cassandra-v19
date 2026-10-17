-- Les plans de sauvegarde : une portée décide du moteur (site/db -> FastPanel ; le reste -> rclone).
CREATE TABLE sauv_plans(
  id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL DEFAULT '', portee TEXT NOT NULL DEFAULT 'doc',
  source TEXT NOT NULL DEFAULT '', destination TEXT NOT NULL DEFAULT '', moteur TEXT NOT NULL DEFAULT 'rclone',
  rythme TEXT NOT NULL DEFAULT '', heure TEXT NOT NULL DEFAULT '03:30',
  garder INTEGER NOT NULL DEFAULT 7, date_dossier INTEGER NOT NULL DEFAULT 1,
  verifier INTEGER NOT NULL DEFAULT 1, fp_plan_id TEXT NOT NULL DEFAULT '',
  actif INTEGER NOT NULL DEFAULT 1, dernier TEXT NOT NULL DEFAULT '',
  dernier_res TEXT NOT NULL DEFAULT '', cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Les copies : le compte rendu de chaque exécution, réelle ou à blanc.
CREATE TABLE sauv_copies(
  id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL,
  ts TEXT NOT NULL DEFAULT (datetime('now')), resultat TEXT NOT NULL DEFAULT '',
  fichiers INTEGER NOT NULL DEFAULT 0, octets INTEGER NOT NULL DEFAULT 0,
  duree REAL NOT NULL DEFAULT 0, destination TEXT NOT NULL DEFAULT '',
  blanc INTEGER NOT NULL DEFAULT 0, verifie INTEGER NOT NULL DEFAULT 0,
  verif_detail TEXT NOT NULL DEFAULT '', sortie TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_sauv_copies ON sauv_copies(plan_id, id DESC);
