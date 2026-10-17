-- Les conversations d'un compte avec un agent. Une conversation est à la PERSONNE ; ses messages gardent les appels d'outils et leurs résultats, pour que le fil se relise tel qu'il a eu lieu.
CREATE TABLE conversations(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, agent TEXT NOT NULL DEFAULT 'cassandra', titre TEXT NOT NULL DEFAULT '',
  cree REAL NOT NULL, maj REAL NOT NULL, en_cours REAL,                      -- en_cours : le tour qui tourne (une conversation ne fait pas deux tours à la fois)
  supprime_at REAL
);
CREATE INDEX conversations_compte ON conversations(compte, supprime_at);
CREATE TABLE messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, conversation_id INTEGER NOT NULL,
  role TEXT NOT NULL,                                                         -- user | assistant | tool | panne (une panne n'est PAS une parole de l'agent : elle ne revient jamais dans le contexte)
  contenu TEXT NOT NULL DEFAULT '', appels TEXT NOT NULL DEFAULT '',        -- appels : les tool_calls du message assistant, en JSON
  tool_call_id TEXT NOT NULL DEFAULT '', nom TEXT NOT NULL DEFAULT '', statut TEXT NOT NULL DEFAULT '',
  tour INTEGER NOT NULL DEFAULT 0, ts REAL NOT NULL
);
CREATE INDEX messages_conversation ON messages(conversation_id, id);
CREATE TABLE arrets(conversation_id INTEGER PRIMARY KEY, ts REAL NOT NULL);   -- une demande d'arrêt, lue entre deux étapes du tour
