-- Billetterie, lot 4a : le contrôle à l'entrée. Chaque présentation d'un billet est consignée (acceptée ou refusée), un même billet vu à deux portes pendant
-- une coupure réseau devient un conflit que le titulaire arbitre. La porte d'un type de billet sert à la règle « une catégorie par porte ».

ALTER TABLE types_billets ADD COLUMN porte TEXT NOT NULL DEFAULT 'Entrée principale';
ALTER TABLE invitations ADD COLUMN porte TEXT NOT NULL DEFAULT 'Backstage';

CREATE TABLE controles(
  id INTEGER PRIMARY KEY AUTOINCREMENT, evenement_id INTEGER NOT NULL, billet_id INTEGER, numero TEXT NOT NULL DEFAULT '',
  porte TEXT NOT NULL DEFAULT '', ouvreur TEXT NOT NULL DEFAULT '',
  niveau TEXT NOT NULL CHECK(niveau IN ('ok','ko','warn')), titre TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
  manuel INTEGER NOT NULL DEFAULT 0, hors_ligne INTEGER NOT NULL DEFAULT 0,
  heure_appareil TEXT NOT NULL DEFAULT '',                  -- l'heure de l'appareil de l'ouvreur (ISO) : c'est elle qui dit qui est entré le premier après une coupure
  annule INTEGER NOT NULL DEFAULT 0, le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_ctl_evt ON controles(evenement_id, id);
CREATE INDEX idx_ctl_bil ON controles(billet_id);

CREATE TABLE conflits(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, evenement_id INTEGER NOT NULL, billet_id INTEGER NOT NULL, numero TEXT NOT NULL,
  porte1 TEXT NOT NULL DEFAULT '', heure1 TEXT NOT NULL DEFAULT '', porte2 TEXT NOT NULL DEFAULT '', heure2 TEXT NOT NULL DEFAULT '',
  etat TEXT NOT NULL DEFAULT 'a_arbitrer' CHECK(etat IN ('a_arbitrer','accepte','bloque')),
  decide_par TEXT NOT NULL DEFAULT '', decide_le TEXT NOT NULL DEFAULT '', cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_cfl_evt ON conflits(evenement_id, etat);
