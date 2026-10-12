-- Les sites déclarés à la main qui ne sont pas gérés par le panneau.
-- Remplace le tableau `sites` du `users.json` de la V18.
CREATE TABLE sites_declares (
    domain TEXT NOT NULL,
    compte TEXT NOT NULL,
    ts REAL NOT NULL,
    par TEXT NOT NULL,
    PRIMARY KEY(domain, compte)
);

-- Historique de la disponibilité des sites (remplit la carte 'historique')
CREATE TABLE site_status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    domain TEXT NOT NULL,
    http_code INTEGER,
    response_ms INTEGER,
    up INTEGER,
    ssl_days INTEGER,
    backend TEXT,
    running INTEGER,
    error TEXT
);
CREATE INDEX idx_site_status_ts ON site_status(ts);
CREATE INDEX idx_site_status_dom ON site_status(domain, ts);

-- Transition d'état constatée (dehors vs en ligne)
CREATE TABLE site_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    domain TEXT NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT,
    duration_min INTEGER
);
CREATE INDEX idx_site_events_ts ON site_events(ts);

-- Le dernier état connu pour calculer les durées de panne
CREATE TABLE site_state_seen (
    domain TEXT PRIMARY KEY,
    up INTEGER,
    since REAL,
    ts REAL NOT NULL
);

-- Liens externes attachés au projet
CREATE TABLE site_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref TEXT NOT NULL,
    note TEXT,
    ts REAL NOT NULL,
    UNIQUE(domain, kind, ref)
);

-- Versions identifiées par le scanner de CMS
CREATE TABLE cms_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    domain TEXT NOT NULL,
    type TEXT NOT NULL,
    version TEXT NOT NULL,
    UNIQUE(domain)
);

-- Demandes d'adossement d'un site déclaré
CREATE TABLE site_demandes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    domain TEXT NOT NULL,
    compte TEXT NOT NULL,
    message TEXT,
    statut TEXT DEFAULT 'ouverte',
    reponse TEXT,
    traite_par TEXT,
    traite_ts REAL
);

-- Accords donnés par le propriétaire (ex: restauration de backup par admin)
CREATE TABLE site_accords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    domain TEXT NOT NULL,
    compte TEXT NOT NULL,
    geste TEXT NOT NULL,
    jusqu_a REAL NOT NULL,
    par TEXT NOT NULL
);

-- Mémorisation des rapports mensuels
CREATE TABLE site_rapports_envoyes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    domain TEXT NOT NULL,
    mois TEXT NOT NULL,
    compte TEXT NOT NULL
);
