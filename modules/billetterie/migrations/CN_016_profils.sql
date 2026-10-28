-- Billetterie, lot 15 : le profil du revendeur et de l'artiste (IBAN chiffré, mode de facturation de la commission).
-- L'IBAN n'est JAMAIS gardé en clair : il est chiffré par le noyau ; le titulaire n'en voit que la fin, la personne le voit en entier chez elle.
ALTER TABLE revendeurs ADD COLUMN iban_chiffre TEXT NOT NULL DEFAULT '';
ALTER TABLE revendeurs ADD COLUMN mode_facturation TEXT NOT NULL DEFAULT 'mandat';        -- 'mandat' : le titulaire établit l'auto-facture en son nom ; 'propre' : il facture lui-même
ALTER TABLE artistes ADD COLUMN iban_chiffre TEXT NOT NULL DEFAULT '';
