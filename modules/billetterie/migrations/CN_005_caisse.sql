-- Billetterie, lot 4b : la caisse (vente sur place) et sa réserve de numéros de billets pour vendre sans réseau.
--
-- Une caisse est une SESSION (un caissier, un appareil, un fond, un événement) qui s'ouvre et se clôture avec un comptage des espèces.
-- Sans réseau, l'appareil ne peut pas demander un numéro : il reçoit AVANT un bloc de numéros de billets déjà signés. Un numéro réservé n'est jamais réattribué,
-- qu'il serve ou non (ceux qui n'ont pas servi à la clôture sont retirés). À la reconnexion, les ventes arrivent avec les numéros qu'elles ont utilisés.

CREATE TABLE caisses(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, evenement_id INTEGER NOT NULL,
  caissier TEXT NOT NULL DEFAULT '', appareil TEXT NOT NULL DEFAULT 'K1', fond INTEGER NOT NULL DEFAULT 0,
  etat TEXT NOT NULL DEFAULT 'ouverte' CHECK(etat IN ('ouverte','fermee')),
  ouverte_le TEXT NOT NULL DEFAULT (datetime('now')), fermee_le TEXT NOT NULL DEFAULT '',
  compte_especes INTEGER, attendu_especes INTEGER, ecart INTEGER, z TEXT UNIQUE, par TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_cai_evt ON caisses(evenement_id, etat);

CREATE TABLE reserves(
  id INTEGER PRIMARY KEY AUTOINCREMENT, caisse_id INTEGER NOT NULL, numero TEXT NOT NULL UNIQUE,
  etat TEXT NOT NULL DEFAULT 'libre' CHECK(etat IN ('libre','vendu','retire')), commande_id INTEGER
);
CREATE INDEX idx_res_cai ON reserves(caisse_id, etat);

ALTER TABLE commandes ADD COLUMN caisse_id INTEGER;
ALTER TABLE commandes ADD COLUMN recu INTEGER NOT NULL DEFAULT 0;
ALTER TABLE commandes ADD COLUMN rendu INTEGER NOT NULL DEFAULT 0;
ALTER TABLE commandes ADD COLUMN hors_ligne INTEGER NOT NULL DEFAULT 0;
CREATE INDEX idx_cmd_cai ON commandes(caisse_id);
