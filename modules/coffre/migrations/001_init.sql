-- L'audit du coffre : qui a lu ou touché quel secret, et quand. La valeur ne sort jamais d'ici.
CREATE TABLE vault_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL DEFAULT (datetime('now')),
  username TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '', secret_name TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_vault_audit_ts ON vault_audit(ts DESC);
