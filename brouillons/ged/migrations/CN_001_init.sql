-- V18 : LES PIÈCES JOINTES SONT PAR COMPTE (18-09) : deux boîtes peuvent porter le
-- même chemin relatif et les mêmes numéros de message. L'unicité porte donc le compte.
CREATE TABLE ged_fichiers (
  id INTEGER PRIMARY KEY AUTOINCREMENT, 
  source TEXT NOT NULL, 
  chemin TEXT NOT NULL, 
  nom TEXT NOT NULL, 
  taille INTEGER DEFAULT 0, 
  kind TEXT DEFAULT 'autre', 
  empreinte TEXT DEFAULT '', 
  modifie TEXT DEFAULT '', 
  etiquettes TEXT DEFAULT '', 
  project_id INTEGER, 
  prov_folder TEXT DEFAULT '', 
  prov_uid TEXT DEFAULT '', 
  prov_idx INTEGER, 
  prov_from TEXT DEFAULT '', 
  prov_sujet TEXT DEFAULT '', 
  prov_date TEXT DEFAULT '', 
  cree_le REAL NOT NULL, 
  compte TEXT DEFAULT '', 
  UNIQUE(source, chemin, compte)
);
CREATE INDEX idx_ged_emp ON ged_fichiers(empreinte);
-- V18 : Garde en BASE : une pièce jointe ne peut être extraite qu'une fois PAR COMPTE.
CREATE UNIQUE INDEX idx_ged_prov ON ged_fichiers(compte, prov_folder, prov_uid, prov_idx) WHERE source='courrier' AND prov_uid <> '';
CREATE INDEX idx_ged_src ON ged_fichiers(source, chemin);

-- Jumelle de itare_event_links : un document se rattache aux mêmes objets.
CREATE TABLE ged_liens (
  id INTEGER PRIMARY KEY AUTOINCREMENT, 
  fichier_id INTEGER NOT NULL, 
  kind TEXT NOT NULL, 
  ref TEXT NOT NULL, 
  label TEXT DEFAULT '', 
  cree_le REAL NOT NULL, 
  UNIQUE(fichier_id, kind, ref)
);

CREATE TABLE ged_regles (
  id INTEGER PRIMARY KEY AUTOINCREMENT, 
  ordre INTEGER DEFAULT 100, 
  actif INTEGER DEFAULT 1, 
  libelle TEXT DEFAULT '', 
  si_from TEXT DEFAULT '', 
  si_nom TEXT DEFAULT '', 
  si_sujet TEXT DEFAULT '', 
  si_kind TEXT DEFAULT '', 
  si_taille_min INTEGER DEFAULT 0, 
  dest TEXT DEFAULT '', 
  remote TEXT DEFAULT '', 
  projet TEXT DEFAULT '', 
  etiquette TEXT DEFAULT '', 
  appliquee INTEGER DEFAULT 0
);

CREATE TABLE ged_sync (
  id INTEGER PRIMARY KEY AUTOINCREMENT, 
  src TEXT NOT NULL, 
  dst TEXT NOT NULL, 
  mode TEXT DEFAULT 'copy', 
  planif TEXT DEFAULT '', 
  actif INTEGER DEFAULT 1, 
  dernier TEXT DEFAULT '', 
  dernier_res TEXT DEFAULT '', 
  blanc_ok TEXT DEFAULT ''
);

CREATE TABLE ged_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, 
  fichier_id INTEGER NOT NULL, 
  empreinte TEXT DEFAULT '', 
  taille INTEGER DEFAULT 0, 
  chemin_copie TEXT DEFAULT '', 
  ts REAL NOT NULL
);

-- V18 : Ce que la configuration dit DÉJÀ : c'est elle qui fait foi pour la propriété, 
-- pas ce que le client renvoie.
CREATE TABLE ged_racines (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  label TEXT NOT NULL,
  ro INTEGER DEFAULT 0,
  compte TEXT DEFAULT '',
  forme TEXT DEFAULT 'documents',
  sentinelle TEXT DEFAULT ''
);

-- Clé = empreinte du fichier : la vignette se régénère quand le contenu change, et JAMAIS autrement.
CREATE TABLE ged_apercus (
  empreinte TEXT PRIMARY KEY, 
  mime TEXT NOT NULL, 
  data TEXT NOT NULL, 
  ts REAL NOT NULL
);
