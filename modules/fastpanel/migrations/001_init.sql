-- Les tables d'état pour les détecteurs, autrefois dans MEMORY_DB_PATH

CREATE TABLE service_state_seen (
  name TEXT PRIMARY KEY, 
  active TEXT, 
  enabled TEXT, 
  ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE scan_state_seen (
  domain TEXT PRIMARY KEY, 
  status TEXT, 
  report TEXT, 
  scanned_at TEXT, 
  ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE user_sites_seen (
  email TEXT PRIMARY KEY, 
  fp_account TEXT, 
  domains TEXT, 
  ts TEXT DEFAULT (datetime('now'))
);
