-- Billetterie, lot 3 : les clients, les codes promo, les commandes et leurs lignes, les billets, la clé qui les signe.
-- L'argent est en centimes entiers. Un billet n'existe que payé (ou offert, ou invité) ; une commande en cours ne fait que RETENIR des places, le temps du paiement.

CREATE TABLE clients(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, nom TEXT NOT NULL DEFAULT '',
  mail TEXT NOT NULL UNIQUE COLLATE NOCASE, tel TEXT NOT NULL DEFAULT '',
  compte INTEGER NOT NULL DEFAULT 0,                  -- 1 : a créé son compte (accès à son espace) ; 0 : a acheté sans compte
  professionnel INTEGER NOT NULL DEFAULT 0, organisation TEXT NOT NULL DEFAULT '', siret TEXT NOT NULL DEFAULT '', ape TEXT NOT NULL DEFAULT '', tva TEXT NOT NULL DEFAULT '',
  adresse TEXT NOT NULL DEFAULT '', code_postal TEXT NOT NULL DEFAULT '', ville TEXT NOT NULL DEFAULT '', pays TEXT NOT NULL DEFAULT 'FR',
  consentement INTEGER NOT NULL DEFAULT 0, cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE promos(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, code TEXT NOT NULL UNIQUE,
  type TEXT NOT NULL CHECK(type IN ('pct','eur')), valeur INTEGER NOT NULL CHECK(valeur > 0),
  evenement_id INTEGER, max_usages INTEGER NOT NULL DEFAULT 0, usages INTEGER NOT NULL DEFAULT 0,
  fin TEXT NOT NULL DEFAULT '', actif INTEGER NOT NULL DEFAULT 1, cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE commandes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, evenement_id INTEGER NOT NULL, client_id INTEGER, revendeur_id INTEGER,
  canal TEXT NOT NULL CHECK(canal IN ('boutique','caisse','revendeur','titulaire')),
  moyen TEXT NOT NULL DEFAULT '' CHECK(moyen IN ('','stripe','helloasso','paypal','virement','especes','carte_terminal','carte_declaree','offert')),
  etat TEXT NOT NULL DEFAULT 'retenue' CHECK(etat IN ('retenue','en_attente','payee','remboursee','annulee','expiree')),
  sous_total INTEGER NOT NULL DEFAULT 0, remise INTEGER NOT NULL DEFAULT 0, don INTEGER NOT NULL DEFAULT 0, frais INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0,
  promo_code TEXT NOT NULL DEFAULT '', nom TEXT NOT NULL DEFAULT '', mail TEXT NOT NULL DEFAULT '',
  attribution TEXT NOT NULL DEFAULT '',               -- pourquoi la vente est (ou n'est pas) attribuée à un revendeur
  formule_id INTEGER,                                 -- la formule qui rémunère le revendeur pour cette vente (figée à la commande)
  reference_externe TEXT UNIQUE,                      -- l'identifiant chez le prestataire : un même paiement ne se déclare qu'une fois
  expire_le REAL NOT NULL DEFAULT 0, cree_le TEXT NOT NULL DEFAULT (datetime('now')), payee_le TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '', par TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_cmd_evt ON commandes(evenement_id, etat);
CREATE INDEX idx_cmd_rev ON commandes(revendeur_id);

CREATE TABLE lignes_commande(
  id INTEGER PRIMARY KEY AUTOINCREMENT, commande_id INTEGER NOT NULL, type_billet_id INTEGER NOT NULL,
  nom TEXT NOT NULL, prix INTEGER NOT NULL, quantite INTEGER NOT NULL CHECK(quantite > 0), entrees INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_lig_cmd ON lignes_commande(commande_id);

CREATE TABLE billets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, numero TEXT NOT NULL UNIQUE,
  commande_id INTEGER, ligne_id INTEGER, evenement_id INTEGER NOT NULL, type_billet_id INTEGER, categorie_invite TEXT NOT NULL DEFAULT '',
  nom TEXT NOT NULL DEFAULT '', mail TEXT NOT NULL DEFAULT '', revendeur_id INTEGER,
  etat TEXT NOT NULL DEFAULT 'valide' CHECK(etat IN ('valide','annule')),
  entrees INTEGER NOT NULL DEFAULT 1, entrees_faites INTEGER NOT NULL DEFAULT 0, version INTEGER NOT NULL DEFAULT 0,
  cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_bil_evt ON billets(evenement_id, etat);
CREATE INDEX idx_bil_cmd ON billets(commande_id);

-- La clé qui signe les billets (créée au premier usage, chiffrée par le noyau : jamais en clair dans cette base).
CREATE TABLE cles(nom TEXT PRIMARY KEY, valeur TEXT NOT NULL);
