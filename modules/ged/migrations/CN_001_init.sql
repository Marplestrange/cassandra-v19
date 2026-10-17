-- L'index des documents : une ligne par fichier, UNE (source, chemin, compte).
-- Le compte est sur la ligne : deux boîtes peuvent porter le même chemin relatif.
CREATE TABLE ged_fichiers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, chemin TEXT NOT NULL,
  nom TEXT NOT NULL DEFAULT '', taille INTEGER NOT NULL DEFAULT 0, kind TEXT NOT NULL DEFAULT 'autre',
  empreinte TEXT NOT NULL DEFAULT '', modifie TEXT NOT NULL DEFAULT '',
  etiquettes TEXT NOT NULL DEFAULT '', project_id INTEGER,
  prov_folder TEXT NOT NULL DEFAULT '', prov_uid TEXT NOT NULL DEFAULT '',
  prov_idx INTEGER, prov_from TEXT NOT NULL DEFAULT '', prov_sujet TEXT NOT NULL DEFAULT '',
  prov_date TEXT NOT NULL DEFAULT '',
  cree_le TEXT NOT NULL DEFAULT (datetime('now')),
  compte TEXT NOT NULL DEFAULT '',
  UNIQUE(source, chemin, compte)
);
CREATE INDEX idx_ged_emp ON ged_fichiers(empreinte);
CREATE INDEX idx_ged_src ON ged_fichiers(source, chemin);
-- Un document se rattache aux mêmes objets qu'Itare (projet, contact, tâche…).
CREATE TABLE ged_liens(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fichier_id INTEGER NOT NULL, kind TEXT NOT NULL,
  ref TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', cree_le TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(fichier_id, kind, ref)
);
-- Les règles de classement : une pièce qui correspond va dans `dest`, avec ses jetons.
CREATE TABLE ged_regles(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ordre INTEGER NOT NULL DEFAULT 100,
  actif INTEGER NOT NULL DEFAULT 1, libelle TEXT NOT NULL DEFAULT '',
  si_from TEXT NOT NULL DEFAULT '', si_nom TEXT NOT NULL DEFAULT '', si_sujet TEXT NOT NULL DEFAULT '',
  si_kind TEXT NOT NULL DEFAULT '', si_taille_min INTEGER NOT NULL DEFAULT 0,
  dest TEXT NOT NULL DEFAULT '', remote TEXT NOT NULL DEFAULT '',
  projet TEXT NOT NULL DEFAULT '', etiquette TEXT NOT NULL DEFAULT '',
  appliquee INTEGER NOT NULL DEFAULT 0
);
-- Remplacer un fichier n'écrase pas son passé : l'ancienne empreinte devient une version.
CREATE TABLE ged_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fichier_id INTEGER NOT NULL,
  empreinte TEXT NOT NULL DEFAULT '', taille INTEGER NOT NULL DEFAULT 0,
  chemin_copie TEXT NOT NULL DEFAULT '', ts TEXT NOT NULL DEFAULT (datetime('now'))
);
-- La configuration de la GED (racines, extraction, tailles) vit ici, pas dans un fichier de secrets.
CREATE TABLE ged_config(cle TEXT PRIMARY KEY, valeur TEXT NOT NULL DEFAULT '');
