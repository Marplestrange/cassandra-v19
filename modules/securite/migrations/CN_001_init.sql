-- Le journal des gestes de sécurité : qui a fait quoi, avec le résultat et le retour arrière possible.
CREATE TABLE securite_journal(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL DEFAULT (datetime('now')),
  qui TEXT NOT NULL DEFAULT '', geste TEXT NOT NULL DEFAULT '', cible TEXT NOT NULL DEFAULT '',
  detail TEXT NOT NULL DEFAULT '', ok INTEGER NOT NULL DEFAULT 0,
  resultat TEXT NOT NULL DEFAULT '', defaire TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_sec_journal ON securite_journal(id DESC);
-- Les audits de sécurité : le rapport rédigé par le modèle, avec le modèle qui l'a produit.
CREATE TABLE securite_audits(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL DEFAULT (datetime('now')),
  modele TEXT NOT NULL DEFAULT '', titre TEXT NOT NULL DEFAULT '', corps TEXT NOT NULL DEFAULT ''
);
