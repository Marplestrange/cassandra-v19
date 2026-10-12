-- Historique des audits du coffre (V18: vault_audit)
CREATE TABLE vault_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  username TEXT NOT NULL,
  action TEXT NOT NULL,
  secret_name TEXT NOT NULL
);
CREATE INDEX idx_vault_audit_ts ON vault_audit(ts);
CREATE INDEX idx_vault_audit_username ON vault_audit(username);

-- Versions des fichiers sauvegardés dans le coffre (V18: atelier_versions)
CREATE TABLE atelier_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pid INTEGER NOT NULL,
  chemin TEXT NOT NULL,
  n INTEGER NOT NULL,
  auteur TEXT NOT NULL DEFAULT '',
  ts REAL NOT NULL,
  empreinte TEXT NOT NULL,
  fichier TEXT NOT NULL,
  taille INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_coffre_versions ON atelier_versions(pid, chemin, n);

-- Stockage des accès inter-serveurs (V18: MULTISERVER_CONFIG_FILE)
CREATE TABLE multiserver_tokens(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nom TEXT NOT NULL,
  url TEXT NOT NULL,
  token_chiffre TEXT NOT NULL,
  maj REAL NOT NULL
);
CREATE UNIQUE INDEX ms_nom_unique ON multiserver_tokens(nom);
