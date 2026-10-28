-- Billetterie, lot 10 : le pont facultatif vers Dolibarr (comptabilité).
--
-- Dolibarr n'est JAMAIS sur le chemin d'un paiement : l'acheteur paie, les billets sont émis, PUIS l'écriture comptable se fait en arrière-plan.
-- Chaque écriture à faire est une ligne de la FILE DE RATTRAPAGE (clé unique : une même écriture n'est jamais faite deux fois, même rejouée) ;
-- si Dolibarr est injoignable ou refuse, la ligne attend et se retente ; la vente, elle, n'est jamais touchée.
-- La billetterie ne garde de Dolibarr que des identifiants (tiers, facture, avoir) : taux, numérotation et comptes restent à Dolibarr.

ALTER TABLE clients ADD COLUMN dolibarr_id INTEGER;
ALTER TABLE revendeurs ADD COLUMN dolibarr_id INTEGER;
ALTER TABLE artistes ADD COLUMN dolibarr_id INTEGER;
ALTER TABLE commandes ADD COLUMN dolibarr_facture_id INTEGER;
ALTER TABLE commandes ADD COLUMN dolibarr_facture_ref TEXT NOT NULL DEFAULT '';
ALTER TABLE commandes ADD COLUMN dolibarr_avoir_id INTEGER;
ALTER TABLE commandes ADD COLUMN dolibarr_avoir_ref TEXT NOT NULL DEFAULT '';

CREATE TABLE dolibarr_file(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cle TEXT NOT NULL UNIQUE,
  objet TEXT NOT NULL CHECK(objet IN ('facture','avoir','versement')),
  cible_id INTEGER NOT NULL,                       -- la commande (facture, avoir) ou la demande de retrait (versement)
  etat TEXT NOT NULL DEFAULT 'a_faire' CHECK(etat IN ('a_faire','fait','echec','ignore')),
  essais INTEGER NOT NULL DEFAULT 0, erreur TEXT NOT NULL DEFAULT '', prochain_essai REAL NOT NULL DEFAULT 0,
  resultat TEXT NOT NULL DEFAULT '', cree_le TEXT NOT NULL DEFAULT (datetime('now')), fait_le TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_dolf_etat ON dolibarr_file(etat, id);

-- Les tiers « maison » créés une fois (clients divers pour les ventes sans fiche client).
CREATE TABLE dolibarr_cles(nom TEXT PRIMARY KEY, valeur TEXT NOT NULL);
