-- Le journal du module web : ce qui a été lu ou refusé (adresse sans sa requête, taille, empreinte). Jamais le contenu d'une page.
CREATE TABLE lectures(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, compte TEXT NOT NULL DEFAULT '', genre TEXT NOT NULL,
  url TEXT NOT NULL DEFAULT '', octets INTEGER NOT NULL DEFAULT 0, empreinte TEXT NOT NULL DEFAULT '', statut TEXT NOT NULL, motif TEXT NOT NULL DEFAULT ''
);
CREATE INDEX lectures_ts ON lectures(ts);
