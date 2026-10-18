-- Billetterie, lot 2 : le registre des mouvements (le « portefeuille » des revendeurs et des artistes) et les demandes de retrait.
--
-- Le registre est en ÉCRITURE SEULE : une ligne écrite ne se modifie ni ne s'efface (des déclencheurs le refusent). Une erreur se corrige par une ligne contraire.
-- Cassandra ne détient aucun fonds : le portefeuille est ce que l'organisateur DOIT au porteur ; le versement lui-même se fait hors de Cassandra (virement), puis s'enregistre.
-- Les montants sont en centimes signés : positif = dû au porteur, négatif = pris sur ce qui lui est dû (retrait, reprise après remboursement).

CREATE TABLE mouvements(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE,
  porteur TEXT NOT NULL CHECK(porteur IN ('revendeur','artiste')), porteur_id INTEGER NOT NULL,
  evenement_id INTEGER,
  nature TEXT NOT NULL CHECK(nature IN ('commission','fixe','forfait','retrait','reprise','ajustement')),
  montant INTEGER NOT NULL CHECK(montant <> 0),
  disponible_le TEXT NOT NULL DEFAULT '',          -- date AAAA-MM-JJ à partir de laquelle ce montant compte comme retirable ('' = tout de suite)
  origine TEXT NOT NULL DEFAULT '',                -- ce qui l'a causé : une commande, un retrait, une main
  cle TEXT UNIQUE,                                 -- idempotence : écrire deux fois le même fait n'écrit qu'une ligne
  note TEXT NOT NULL DEFAULT '', par TEXT NOT NULL DEFAULT '',
  cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_mou_porteur ON mouvements(porteur, porteur_id, id);
CREATE INDEX idx_mou_evt ON mouvements(evenement_id);

CREATE TRIGGER mouvements_jamais_modifies BEFORE UPDATE ON mouvements
BEGIN SELECT RAISE(ABORT, 'le registre est en écriture seule : une ligne ne se modifie pas, on en écrit une contraire'); END;

CREATE TRIGGER mouvements_jamais_effaces BEFORE DELETE ON mouvements
BEGIN SELECT RAISE(ABORT, 'le registre est en écriture seule : une ligne ne s''efface pas, on en écrit une contraire'); END;

-- Une demande de retrait : la seule chose mutable ici (son état avance), le registre garde la trace de l'argent.
CREATE TABLE retraits(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE,
  porteur TEXT NOT NULL CHECK(porteur IN ('revendeur','artiste')), porteur_id INTEGER NOT NULL,
  montant INTEGER NOT NULL CHECK(montant > 0),
  etat TEXT NOT NULL DEFAULT 'demandee' CHECK(etat IN ('demandee','validee','payee','refusee')),
  motif TEXT NOT NULL DEFAULT '', reference_virement TEXT NOT NULL DEFAULT '',
  demande_le TEXT NOT NULL DEFAULT (datetime('now')), traite_le TEXT NOT NULL DEFAULT '', par TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_ret_porteur ON retraits(porteur, porteur_id, id);
