CREATE TABLE cron_natural (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  description TEXT,
  cron_expr TEXT,
  command TEXT,
  created_at TEXT DEFAULT (datetime('now')),
  active INTEGER DEFAULT 1,
  wrapped INTEGER DEFAULT 1
);

CREATE TABLE cron_critical (
  ref TEXT PRIMARY KEY,
  label TEXT,
  ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE cron_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref TEXT,
  started_at TEXT,
  duration_ms INTEGER,
  exit_code INTEGER,
  output TEXT,
  trigger TEXT
);
CREATE INDEX idx_cron_runs_ref ON cron_runs(ref, started_at);

CREATE TABLE cron_reglages (
  ref TEXT PRIMARY KEY,
  fenetre_min INTEGER DEFAULT 0,
  verrou INTEGER DEFAULT 0,
  essais INTEGER DEFAULT 0,
  motif_echec TEXT DEFAULT '',
  apres_ref TEXT DEFAULT '',
  apres_si_ok INTEGER DEFAULT 1,
  nom TEXT DEFAULT '',
  maj TEXT DEFAULT (datetime('now'))
);

CREATE TABLE cron_modifs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ref TEXT,
  ts TEXT DEFAULT (datetime('now')),
  acteur TEXT DEFAULT '',
  quoi TEXT DEFAULT ''
);
CREATE INDEX idx_cron_modifs ON cron_modifs(ref, id DESC);
