-- Billetterie, lot 4c : la boutique publique (suivi d'une commande par jeton, limites contre l'abus, courriels à envoyer, événements des prestataires reçus).

ALTER TABLE commandes ADD COLUMN suivi TEXT NOT NULL DEFAULT '';                 -- le jeton donné à l'acheteur pour suivre SA commande (non devinable)
ALTER TABLE commandes ADD COLUMN ip TEXT NOT NULL DEFAULT '';
ALTER TABLE commandes ADD COLUMN session_prestataire TEXT NOT NULL DEFAULT '';   -- l'identifiant de la page de paiement chez le prestataire

-- Les limites : pas plus de N demandes d'une même origine par fenêtre de temps (une boutique publique qui retient des places se protège de qui voudrait les accaparer).
CREATE TABLE limites(cle TEXT NOT NULL, ts REAL NOT NULL);
CREATE INDEX idx_lim_cle ON limites(cle, ts);

-- Les courriels à envoyer : la billetterie les prépare, c'est le courrier qui les expédie (module distinct, branché plus tard) : un envoi qui échoue ne perd pas la commande.
CREATE TABLE courriels(
  id INTEGER PRIMARY KEY AUTOINCREMENT, a TEXT NOT NULL, objet TEXT NOT NULL, corps TEXT NOT NULL, commande_ref TEXT NOT NULL DEFAULT '',
  etat TEXT NOT NULL DEFAULT 'a_envoyer' CHECK(etat IN ('a_envoyer','envoye','echec')), erreur TEXT NOT NULL DEFAULT '',
  cree_le TEXT NOT NULL DEFAULT (datetime('now')), envoye_le TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_cou_etat ON courriels(etat, id);

-- Les événements reçus d'un prestataire de paiement : un même événement reçu deux fois n'agit qu'une fois.
CREATE TABLE evenements_paiement(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fournisseur TEXT NOT NULL, ident TEXT NOT NULL, type TEXT NOT NULL DEFAULT '', commande_ref TEXT NOT NULL DEFAULT '',
  issue TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', recu_le TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(fournisseur, ident)
);
