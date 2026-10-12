CREATE TABLE memoires (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proprietaire TEXT NOT NULL,
    categorie TEXT NOT NULL,
    cle TEXT NOT NULL,
    valeur TEXT NOT NULL,
    provenance TEXT NOT NULL DEFAULT 'infere',
    confiance REAL DEFAULT 0.5,
    force REAL DEFAULT 0,
    statut TEXT NOT NULL DEFAULT 'actif',
    langue TEXT,
    piece_id INTEGER,
    valide_de TEXT, valide_a REAL,
    remplace INTEGER, don_de INTEGER,
    version INTEGER NOT NULL DEFAULT 1,
    nb_rappels INTEGER DEFAULT 0, dernier_rappel REAL,
    nature TEXT,
    sonde TEXT,
    sonde_args TEXT,
    sonde_valeur TEXT,
    artefact TEXT,
    artefact_empreinte TEXT,
    cree_le REAL NOT NULL, maj_le REAL NOT NULL
);
CREATE UNIQUE INDEX ux_memoires_actif ON memoires(proprietaire, cle) WHERE statut='actif';
CREATE INDEX ix_memoires_prop_statut ON memoires(proprietaire, statut);
CREATE INDEX ix_memoires_remplace ON memoires(remplace);

CREATE VIRTUAL TABLE memoires_fts USING fts5(valeur, cle, categorie, content='memoires', content_rowid='id', tokenize='unicode61');
CREATE TRIGGER memoires_fts_ai AFTER INSERT ON memoires WHEN new.statut='actif' BEGIN
    INSERT INTO memoires_fts(rowid, valeur, cle, categorie) VALUES (new.id, new.valeur, new.cle, new.categorie);
END;
CREATE TRIGGER memoires_fts_au AFTER UPDATE ON memoires WHEN old.statut <> new.statut BEGIN
    INSERT INTO memoires_fts(memoires_fts, rowid, valeur, cle, categorie) SELECT 'delete', old.id, old.valeur, old.cle, old.categorie WHERE old.statut='actif';
    INSERT INTO memoires_fts(rowid, valeur, cle, categorie) SELECT new.id, new.valeur, new.cle, new.categorie WHERE new.statut='actif';
END;
CREATE TRIGGER memoires_fts_ad AFTER DELETE ON memoires WHEN old.statut='actif' BEGIN
    INSERT INTO memoires_fts(memoires_fts, rowid, valeur, cle, categorie) VALUES ('delete', old.id, old.valeur, old.cle, old.categorie);
END;

CREATE TABLE memoire_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    acteur TEXT NOT NULL, verbe TEXT NOT NULL,
    memoire_id INTEGER, details TEXT,
    hash TEXT, previous_hash TEXT
);
CREATE INDEX ix_memoire_journal_ts ON memoire_journal(ts);
CREATE INDEX ix_memoire_journal_verbe ON memoire_journal(verbe, ts);

CREATE TABLE chaine (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    origine TEXT NOT NULL,
    ligne_id INTEGER,
    verbe TEXT,
    ts REAL,
    details TEXT,
    hash TEXT NOT NULL UNIQUE,
    previous_hash TEXT NOT NULL UNIQUE
);

CREATE TABLE memoire_cadran (
    cle TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0,
    dernier_ts REAL, dernier TEXT
);

CREATE TABLE memoire_doutes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    proprietaire TEXT NOT NULL,
    source TEXT NOT NULL,
    question TEXT NOT NULL,
    options TEXT,
    statut TEXT NOT NULL DEFAULT 'ouvert',
    priorite INTEGER NOT NULL DEFAULT 1,
    memoire_id INTEGER, memoire_id_2 INTEGER, piece_id INTEGER,
    echeance REAL, dernier_pose REAL, nb_poses INTEGER DEFAULT 0, differe INTEGER DEFAULT 0,
    resolution TEXT, resolu_le REAL, resolu_par TEXT
);
CREATE INDEX ix_memoire_doutes_statut ON memoire_doutes(statut, proprietaire);

CREATE TABLE memoire_episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proprietaire TEXT NOT NULL,
    session_id TEXT,
    debut REAL NOT NULL, fin REAL NOT NULL,
    n_messages INTEGER DEFAULT 0,
    statut TEXT NOT NULL DEFAULT 'ouvert',
    resume TEXT, termes TEXT,
    cree_le REAL NOT NULL
);
CREATE INDEX ix_memoire_episodes_prop ON memoire_episodes(proprietaire, statut);

CREATE VIRTUAL TABLE memoire_episodes_fts USING fts5(resume, termes, content='memoire_episodes', content_rowid='id', tokenize='unicode61');
CREATE TRIGGER memoire_episodes_fts_au AFTER UPDATE ON memoire_episodes WHEN old.statut <> new.statut BEGIN
    INSERT INTO memoire_episodes_fts(memoire_episodes_fts, rowid, resume, termes) SELECT 'delete', old.id, old.resume, old.termes WHERE old.statut='ferme';
    INSERT INTO memoire_episodes_fts(rowid, resume, termes) SELECT new.id, new.resume, new.termes WHERE new.statut='ferme';
END;

CREATE TABLE memoire_rappels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proprietaire TEXT NOT NULL,
    cle TEXT NOT NULL,
    metrique TEXT NOT NULL, op TEXT NOT NULL, seuil REAL NOT NULL,
    message TEXT NOT NULL,
    actif INTEGER NOT NULL DEFAULT 1,
    dernier_declenche REAL, nb_declenches INTEGER DEFAULT 0,
    acteur TEXT, cree_le REAL NOT NULL
);

CREATE TABLE postmortems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    title TEXT, summary TEXT,
    lessons TEXT, status TEXT DEFAULT 'open'
);
