-- Les règles communes à tous les agents (réglées par l'administrateur) et les tâches récurrentes que l'on confie à un agent.
CREATE TABLE agents_regles(cle TEXT PRIMARY KEY, valeur TEXT NOT NULL, maj REAL NOT NULL);
CREATE TABLE taches_agents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, compte TEXT NOT NULL, consigne TEXT NOT NULL,
  frequence TEXT NOT NULL,                                                      -- horaire | quotidien | hebdomadaire
  heure TEXT NOT NULL DEFAULT '08:00', jour INTEGER NOT NULL DEFAULT 0,         -- heure HH:MM (quotidien, hebdomadaire) ; jour 0 = lundi (hebdomadaire)
  active INTEGER NOT NULL DEFAULT 1, cree REAL NOT NULL, derniere REAL, conversation_id INTEGER
);
CREATE INDEX taches_agents_compte ON taches_agents(compte, active);
