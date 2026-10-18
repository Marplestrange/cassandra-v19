-- Billetterie, lot 5a : annuler ou reporter un événement.
--
-- Un report change la date : la date d'origine est gardée, et les commissions déjà écrites au registre (qui est en écriture seule) ne deviennent pas retirables
-- avant la NOUVELLE date + le délai : `dispo_min` est le plancher de disponibilité que le registre applique à toutes les lignes de l'événement.

ALTER TABLE evenements ADD COLUMN ancienne_date TEXT NOT NULL DEFAULT '';
ALTER TABLE evenements ADD COLUMN motif_report TEXT NOT NULL DEFAULT '';
ALTER TABLE evenements ADD COLUMN dispo_min TEXT NOT NULL DEFAULT '';
