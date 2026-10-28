-- Billetterie, lot 8 : l'envoi réel des courriels. Un envoi qui échoue est retenté plus tard : on compte les essais et on retient le moment du prochain.
ALTER TABLE courriels ADD COLUMN essais INTEGER NOT NULL DEFAULT 0;
ALTER TABLE courriels ADD COLUMN prochain_essai REAL NOT NULL DEFAULT 0;
