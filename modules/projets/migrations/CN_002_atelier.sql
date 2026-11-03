-- L'atelier du projet : le dossier de fichiers, ses versions, ce qui s'y passe (activité, fil, commentaires), le courrier rangé, les suites proposées.
ALTER TABLE projets ADD COLUMN dossier TEXT NOT NULL DEFAULT '';
CREATE TABLE pj_versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, projet_id INTEGER NOT NULL, chemin TEXT NOT NULL, n INTEGER NOT NULL,
  auteur TEXT NOT NULL DEFAULT '', empreinte TEXT NOT NULL, taille INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '', ts REAL NOT NULL, contenu BLOB NOT NULL,
  UNIQUE(projet_id, chemin, n)
);
CREATE INDEX pj_versions_fichier ON pj_versions(projet_id, chemin);
CREATE TABLE pj_activite(
  id INTEGER PRIMARY KEY AUTOINCREMENT, projet_id INTEGER NOT NULL, ts REAL NOT NULL, chemin TEXT NOT NULL DEFAULT '', geste TEXT NOT NULL DEFAULT '', auteur TEXT NOT NULL DEFAULT '', de TEXT NOT NULL DEFAULT ''
);
CREATE INDEX pj_activite_projet ON pj_activite(projet_id, ts);
CREATE TABLE pj_fil(
  id INTEGER PRIMARY KEY AUTOINCREMENT, projet_id INTEGER NOT NULL, ts REAL NOT NULL, auteur TEXT NOT NULL DEFAULT '', genre TEXT NOT NULL, texte TEXT NOT NULL DEFAULT '',
  ref TEXT NOT NULL DEFAULT '', parent INTEGER NOT NULL DEFAULT 0, etat TEXT NOT NULL DEFAULT '', meta TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX pj_fil_projet ON pj_fil(projet_id, ts);
CREATE TABLE pj_commentaires(
  id INTEGER PRIMARY KEY AUTOINCREMENT, projet_id INTEGER NOT NULL, chemin TEXT NOT NULL DEFAULT '', citation TEXT NOT NULL DEFAULT '', auteur TEXT NOT NULL DEFAULT '',
  texte TEXT NOT NULL DEFAULT '', ts REAL NOT NULL, parent INTEGER NOT NULL DEFAULT 0, resolu TEXT NOT NULL DEFAULT '', etat TEXT NOT NULL DEFAULT ''
);
CREATE INDEX pj_commentaires_fichier ON pj_commentaires(projet_id, chemin);
CREATE TABLE pj_courriers(
  projet_id INTEGER NOT NULL, compte TEXT NOT NULL, cle TEXT NOT NULL, mode TEXT NOT NULL, ts REAL NOT NULL,
  PRIMARY KEY(projet_id, compte, cle)
);
CREATE TABLE pj_propositions(
  projet_id INTEGER PRIMARY KEY, jour TEXT NOT NULL, quand TEXT NOT NULL, items TEXT NOT NULL DEFAULT '[]'
);
