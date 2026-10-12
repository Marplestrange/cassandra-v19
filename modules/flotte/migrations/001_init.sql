CREATE TABLE machines (
  nom TEXT PRIMARY KEY,
  type TEXT,
  os TEXT,
  ssh_host TEXT,
  ssh_port INTEGER,
  ssh_user TEXT,
  ssh_auth TEXT,
  ssh_key TEXT,
  ssh_key_date REAL,
  ssh_key_attente TEXT,
  ssh_pub_attente TEXT,
  ssh_pass TEXT,
  syn_host TEXT,
  syn_qc TEXT,
  url TEXT,
  enabled INTEGER DEFAULT 1
);

CREATE TABLE fleet_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')), name TEXT, type TEXT,
    online INTEGER, cpu REAL, ram REAL, disk REAL, health_score REAL,
    error TEXT
);
CREATE INDEX idx_fleet_status_ts ON fleet_status(ts);
CREATE INDEX idx_fleet_status_name ON fleet_status(name, ts);

CREATE TABLE fleet_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT DEFAULT (datetime('now')), name TEXT, kind TEXT,
    detail TEXT, duration_min INTEGER
);
CREATE INDEX idx_fleet_events_ts ON fleet_events(ts);

CREATE TABLE fleet_state_seen (
    name TEXT PRIMARY KEY, online INTEGER, since TEXT,
    ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE fleet_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, kind TEXT, ref TEXT, note TEXT,
    ts TEXT DEFAULT (datetime('now')),
    UNIQUE(name, kind, ref)
);

CREATE TABLE fleet_ssh_sonde (
    name TEXT PRIMARY KEY, ok INTEGER, user TEXT, ip TEXT,
    detail TEXT, ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE world_model (
    wkey TEXT PRIMARY KEY, category TEXT, value TEXT, detail TEXT,
    severity TEXT DEFAULT 'info', source TEXT DEFAULT 'observed',
    observed_at TEXT, updated_at TEXT
);

CREATE TABLE changelog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, entity_type TEXT, entity_name TEXT, change_type TEXT,
    old_value TEXT, new_value TEXT, severity TEXT
);

CREATE TABLE sensorium_acquits (
    wkey TEXT PRIMARY KEY, raison TEXT, jusqua TEXT, valeur TEXT,
    par TEXT, ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE sensorium_alertes (
    wkey TEXT PRIMARY KEY, depuis TEXT, ok_depuis TEXT,
    nid INTEGER DEFAULT 0, valeur TEXT
);
