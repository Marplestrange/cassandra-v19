-- La référence DNS d'une zone : des versions, jamais d'écrasement. La version courante est la plus récente non annulée.
CREATE TABLE reference(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, domaine TEXT NOT NULL, contenu TEXT NOT NULL, auteur TEXT NOT NULL DEFAULT '',
  annulee INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX reference_dom ON reference(domaine, id);
-- La dernière relève de chaque zone, et ce qu'elle dit.
CREATE TABLE releves(
  domaine TEXT PRIMARY KEY, ts REAL NOT NULL, contenu TEXT NOT NULL, serveur TEXT NOT NULL DEFAULT '', derives TEXT NOT NULL DEFAULT '[]'
);
-- Valeurs d'état du module (adresse publique de référence, expirations lues).
CREATE TABLE etat(cle TEXT PRIMARY KEY, valeur TEXT NOT NULL, ts REAL NOT NULL);
