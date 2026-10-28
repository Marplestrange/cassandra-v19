-- Billetterie, lot 14 : les artistes comme adhérents de Dolibarr (module Adhérents).
-- La liste des objets de la file passe de trois à quatre : SQLite ne modifie pas une contrainte, on reconstruit la table (les lignes existantes sont gardées).
ALTER TABLE artistes ADD COLUMN dolibarr_adherent_id INTEGER;

CREATE TABLE dolibarr_file_neuve(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cle TEXT NOT NULL UNIQUE,
  objet TEXT NOT NULL CHECK(objet IN ('facture','avoir','versement','adherent')),
  cible_id INTEGER NOT NULL,
  etat TEXT NOT NULL DEFAULT 'a_faire' CHECK(etat IN ('a_faire','fait','echec','ignore')),
  essais INTEGER NOT NULL DEFAULT 0, erreur TEXT NOT NULL DEFAULT '', prochain_essai REAL NOT NULL DEFAULT 0,
  resultat TEXT NOT NULL DEFAULT '', cree_le TEXT NOT NULL DEFAULT (datetime('now')), fait_le TEXT NOT NULL DEFAULT ''
);
INSERT INTO dolibarr_file_neuve(id, cle, objet, cible_id, etat, essais, erreur, prochain_essai, resultat, cree_le, fait_le)
  SELECT id, cle, objet, cible_id, etat, essais, erreur, prochain_essai, resultat, cree_le, fait_le FROM dolibarr_file;
DROP TABLE dolibarr_file;
ALTER TABLE dolibarr_file_neuve RENAME TO dolibarr_file;
CREATE INDEX idx_dolf_etat ON dolibarr_file(etat, id);
