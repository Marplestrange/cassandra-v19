-- Le journal des gestes que Cassandra a faits sur Tailscale (200 derniers) : de quoi les montrer et les défaire. Jamais un secret : ni clé d'authentification, ni jeton.
CREATE TABLE gestes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, capacite TEXT NOT NULL, compte TEXT NOT NULL DEFAULT '', args TEXT NOT NULL DEFAULT '{}', res TEXT NOT NULL DEFAULT '{}',
  defait INTEGER NOT NULL DEFAULT 0, defait_ts TEXT NOT NULL DEFAULT ''
);
