-- Le journal du coffre note aussi QUI a agi (cassandra, humain, compte...), pas seulement pour quel compte.
ALTER TABLE vault_audit ADD COLUMN acteur TEXT NOT NULL DEFAULT '';
