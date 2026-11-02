-- Les alertes que l'administrateur a acceptées : « je sais, c'est normal », jusqu'à une échéance et tant que le chiffre ne monte pas.
CREATE TABLE sensorium_acceptations(
  wkey TEXT PRIMARY KEY, raison TEXT NOT NULL DEFAULT '', jusqua TEXT NOT NULL DEFAULT '', valeur TEXT NOT NULL DEFAULT '',
  par TEXT NOT NULL DEFAULT '', ts TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Les fenêtres de maintenance : pendant l'une d'elles, les mesures qu'elle couvre se taisent (les relevés continuent) ; elles reviennent à la fin si elles sont encore en alerte.
CREATE TABLE sensorium_fenetres(
  id INTEGER PRIMARY KEY AUTOINCREMENT, portee TEXT NOT NULL DEFAULT '*', debut TEXT NOT NULL, fin TEXT NOT NULL, motif TEXT NOT NULL DEFAULT '',
  redemarrer INTEGER NOT NULL DEFAULT 0, par TEXT NOT NULL DEFAULT '', cree TEXT NOT NULL DEFAULT (datetime('now')), annulee TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_sn_fenetres ON sensorium_fenetres(debut, fin);
-- Les redémarrages du démon : qui, pourquoi, combien de temps il s'est tu, comment il est revenu.
CREATE TABLE sensorium_redemarrages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL DEFAULT (datetime('now')), qui TEXT NOT NULL DEFAULT '', motif TEXT NOT NULL DEFAULT '',
  silence_s REAL, resultat TEXT NOT NULL DEFAULT ''
);
