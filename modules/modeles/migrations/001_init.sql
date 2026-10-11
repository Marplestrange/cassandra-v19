CREATE TABLE modeles_registre (
  id TEXT PRIMARY KEY,
  fournisseur TEXT NOT NULL,
  nom TEXT NOT NULL,
  base_url TEXT NOT NULL DEFAULT '',
  a_cle INTEGER NOT NULL DEFAULT 0,
  ts REAL NOT NULL,
  ajoute_par TEXT NOT NULL DEFAULT '',
  essai_ts REAL,
  essai_ok INTEGER,
  essai_s REAL,
  essai_msg TEXT NOT NULL DEFAULT ''
);

CREATE TABLE compte_choix (
  compte TEXT PRIMARY KEY,
  fournisseur TEXT NOT NULL,
  modele TEXT NOT NULL,
  maj REAL NOT NULL
);

CREATE TABLE modeles_roles (
  role TEXT PRIMARY KEY,
  modele_id TEXT NOT NULL
);
