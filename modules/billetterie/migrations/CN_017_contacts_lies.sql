-- Billetterie, lot 16 : les artistes et les revendeurs dans le répertoire du bureau (module Contacts).
-- On retient quelle fiche de la billetterie est devenue quel contact : la synchronisation ne crée jamais deux fois le même.
CREATE TABLE contacts_lies(
  fiche_type TEXT NOT NULL CHECK(fiche_type IN ('artiste','revendeur')), fiche_id INTEGER NOT NULL, contact_id INTEGER NOT NULL,
  cree_le TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY(fiche_type, fiche_id)
);
