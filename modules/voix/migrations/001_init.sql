-- Préférences de voix cloisonnées par compte. L'état global passe dans voix_machine.
CREATE TABLE voix_prefs (
    compte TEXT PRIMARY KEY,
    voix_nom TEXT DEFAULT '',
    voix_locuteur TEXT DEFAULT '',
    voix_debit TEXT DEFAULT '1.0',
    voix_mode INTEGER DEFAULT 0,
    voix_auto INTEGER DEFAULT 1
);

-- Le modèle d'écoute et son lexique étaient stockés dans config.json.
CREATE TABLE voix_machine (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    modele TEXT NOT NULL DEFAULT 'small',
    lexique TEXT NOT NULL DEFAULT ''
);

INSERT INTO voix_machine (id, modele, lexique) VALUES (1, 'small', 'Conversation avec Itare, l''agent d''administration système. Vocabulaire : serveur, Cassandra, Itare, panneau, nginx, SSL, certificat, cron, sauvegarde, Telegram, coffre-fort, base de données, redémarrer, journal, domaine, vhost.');
