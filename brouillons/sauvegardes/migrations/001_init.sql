-- Plans de sauvegarde. L'état d'activation et la configuration.
CREATE TABLE sauv_plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nom TEXT NOT NULL,
  portee TEXT DEFAULT 'doc',
  source TEXT NOT NULL,
  destination TEXT NOT NULL,
  moteur TEXT DEFAULT 'rclone',
  rythme TEXT DEFAULT '',
  heure TEXT DEFAULT '03:30',
  garder INTEGER DEFAULT 7,
  date_dossier INTEGER DEFAULT 1,
  verifier INTEGER DEFAULT 1,
  fp_plan_id TEXT DEFAULT '',
  actif INTEGER DEFAULT 1,
  dernier REAL,
  dernier_res TEXT DEFAULT '',
  cree_le REAL NOT NULL,
  origine TEXT DEFAULT '',
  supprime INTEGER NOT NULL DEFAULT 0
);

-- Les exécutions de sauvegarde (historique, durée, résultat).
CREATE TABLE sauv_copies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  plan_id INTEGER NOT NULL,
  ts REAL NOT NULL,
  resultat TEXT DEFAULT '',
  fichiers INTEGER DEFAULT 0,
  octets INTEGER DEFAULT 0,
  duree REAL DEFAULT 0,
  destination TEXT DEFAULT '',
  blanc INTEGER DEFAULT 0,
  verifie INTEGER DEFAULT 0,
  verif_detail TEXT DEFAULT '',
  sortie TEXT DEFAULT ''
);

CREATE INDEX idx_sauv_copies ON sauv_copies(plan_id, id DESC);

-- Le suivi des preuves (échantillon aléatoire et restauration à blanc).
CREATE TABLE sauv_preuves (
  cle TEXT PRIMARY KEY,
  ts REAL NOT NULL
);
