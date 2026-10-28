-- Billetterie, lot 7 : les comptes clients, par lien de connexion envoyé par courriel (pas de mot de passe à voler ni à oublier).
--
-- On ne garde JAMAIS un jeton en clair : seule son empreinte (SHA-256) est en base ; une fuite de la base ne donne accès à aucun compte.
-- Un lien ne sert qu'une fois et 15 minutes ; une session dure 30 jours.
-- La suppression d'un compte est DIFFÉRÉE (délai en réglage) : elle se défait tant qu'elle n'est pas exécutée ; à l'exécution, les données personnelles sont effacées
-- des clients, commandes, billets et listes d'attente ; les reçus fiscaux et les montants des commandes restent (obligations comptables et fiscales).

CREATE TABLE liens_connexion(
  id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL, empreinte TEXT NOT NULL UNIQUE,
  expire_le REAL NOT NULL, utilise INTEGER NOT NULL DEFAULT 0, cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE sessions_client(
  id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL, empreinte TEXT NOT NULL UNIQUE,
  expire_le REAL NOT NULL, cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_sescli ON sessions_client(client_id);

ALTER TABLE clients ADD COLUMN suppression_le REAL NOT NULL DEFAULT 0;      -- 0 : aucune demande ; sinon le moment où les données seront effacées
ALTER TABLE clients ADD COLUMN efface INTEGER NOT NULL DEFAULT 0;
