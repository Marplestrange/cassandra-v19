-- Les fiches typées du coffre (identifiant, note, carte) : ce qu'on peut AFFICHER d'un secret sans l'ouvrir (genre, identifiant, adresse, favori, présence d'un code TOTP, date du mot de passe) — jamais une valeur.
ALTER TABLE vault_secrets ADD COLUMN fiche TEXT NOT NULL DEFAULT '';
-- Les mots de passe remplacés : chiffrés, datés, relus à la demande (et la lecture s'inscrit au journal).
CREATE TABLE vault_historique(
  id INTEGER PRIMARY KEY AUTOINCREMENT, espace TEXT NOT NULL, nom TEXT NOT NULL, ts TEXT NOT NULL DEFAULT (datetime('now')), valeur_chiffree TEXT NOT NULL
);
CREATE INDEX ix_vault_historique ON vault_historique(espace, nom);
