-- Billetterie, lot 5b : la liste d'attente d'un billet épuisé.
--
-- Qui s'inscrit n'est PAS servi par hasard : le premier inscrit reçoit la première place qui se libère, dans l'ordre d'inscription.
-- Une offre retient VRAIMENT les places (une commande en cours, durée = réglage `offre_attente_heures`) : personne d'autre ne peut les acheter pendant ce temps.
-- Une offre non payée dans les temps passe à « expirée » et la place est proposée au suivant.

CREATE TABLE attente(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, evenement_id INTEGER NOT NULL, type_billet_id INTEGER,
  nom TEXT NOT NULL, mail TEXT NOT NULL, quantite INTEGER NOT NULL CHECK(quantite BETWEEN 1 AND 20),
  etat TEXT NOT NULL DEFAULT 'attente' CHECK(etat IN ('attente','offerte','convertie','expiree','retiree')),
  jeton TEXT NOT NULL UNIQUE,                       -- le jeton de suivi donné à la personne inscrite (non devinable)
  commande_id INTEGER, offre_jusqua REAL NOT NULL DEFAULT 0, ip TEXT NOT NULL DEFAULT '',
  cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_att_evt ON attente(evenement_id, etat, id);
