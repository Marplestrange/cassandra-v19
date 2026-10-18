-- Billetterie, lot 5c : les reçus fiscaux de don (association éligible seulement, jamais pour un billet).
--
-- Un reçu est un document comptable : son numéro est CONTINU et ne se réutilise jamais, son contenu ne change pas une fois émis, et on ne l'efface pas.
-- Un reçu qui n'a plus lieu d'être (don remboursé) passe à « annulé » avec son motif : il garde son numéro, et le trou se voit et s'explique.
-- Le contenu est une COPIE de ce qui était vrai à l'émission (identité de l'organisme, du donateur, montant, date, mode de versement) : changer plus tard l'adresse
-- de l'organisme ne réécrit pas un reçu déjà donné.

CREATE TABLE recus_fiscaux(
  id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL UNIQUE,
  commande_id INTEGER NOT NULL, montant INTEGER NOT NULL CHECK(montant > 0),
  nom TEXT NOT NULL, adresse TEXT NOT NULL, mail TEXT NOT NULL DEFAULT '', date_don TEXT NOT NULL, mode TEXT NOT NULL,
  contenu TEXT NOT NULL,
  etat TEXT NOT NULL DEFAULT 'emis' CHECK(etat IN ('emis','annule')), motif TEXT NOT NULL DEFAULT '',
  emis_le TEXT NOT NULL DEFAULT (datetime('now')), annule_le TEXT NOT NULL DEFAULT '', par TEXT NOT NULL DEFAULT ''
);
-- un seul reçu EN VIGUEUR par commande (les annulés restent, avec leur numéro)
CREATE UNIQUE INDEX idx_recu_commande ON recus_fiscaux(commande_id) WHERE etat = 'emis';

CREATE TRIGGER recus_jamais_effaces BEFORE DELETE ON recus_fiscaux
BEGIN SELECT RAISE(ABORT, 'un reçu fiscal ne s''efface pas : on l''annule, il garde son numéro'); END;

CREATE TRIGGER recus_contenu_fige BEFORE UPDATE ON recus_fiscaux
WHEN NEW.numero <> OLD.numero OR NEW.commande_id <> OLD.commande_id OR NEW.montant <> OLD.montant OR NEW.nom <> OLD.nom OR NEW.adresse <> OLD.adresse
  OR NEW.date_don <> OLD.date_don OR NEW.mode <> OLD.mode OR NEW.contenu <> OLD.contenu OR NEW.emis_le <> OLD.emis_le
BEGIN SELECT RAISE(ABORT, 'le contenu d''un reçu fiscal ne change pas une fois émis : annulez-le et émettez-en un autre'); END;
