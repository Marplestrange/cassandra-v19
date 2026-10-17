-- Le miroir Telegram, PAR COMPTE : éteint par défaut, délibérément.
CREATE TABLE canal_prefs(
  compte TEXT PRIMARY KEY, miroir INTEGER NOT NULL DEFAULT 0
);
