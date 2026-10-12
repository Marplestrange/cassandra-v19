-- Le registre des émissions : Let's Encrypt limite à cinq certificats par semaine et par domaine enregistré ; cinq échecs de suite bloquent un domaine mal réglé.
CREATE TABLE emissions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, domaine TEXT NOT NULL, ok INTEGER NOT NULL DEFAULT 1, acteur TEXT NOT NULL DEFAULT ''
);
CREATE INDEX emissions_dom ON emissions(domaine, ts);
-- Jusqu'où le journal du bus a été lu : un événement ne compte qu'une fois.
CREATE TABLE curseur(cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);
