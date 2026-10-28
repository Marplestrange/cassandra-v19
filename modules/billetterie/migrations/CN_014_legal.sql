-- Billetterie, lot 13 : les textes légaux de la boutique (conditions générales de vente, mentions légales, confidentialité).
--
-- Chaque texte a une VERSION qui monte à chaque changement ; une commande retient la version des conditions que l'acheteur a acceptées (preuve de ce qu'il a lu).
CREATE TABLE pages_legales(
  cle TEXT PRIMARY KEY CHECK(cle IN ('cgv','mentions','confidentialite')), titre TEXT NOT NULL, texte TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 0, maj_le TEXT NOT NULL DEFAULT (datetime('now'))
);
ALTER TABLE commandes ADD COLUMN cgv_version INTEGER NOT NULL DEFAULT 0;
