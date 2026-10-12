-- Cache local des en-têtes et corps partiels pour alléger IMAP
CREATE TABLE mail_cache (
  account TEXT, folder TEXT, uid TEXT, msg_id TEXT DEFAULT '',
  thread_key TEXT DEFAULT '', from_addr TEXT DEFAULT '', from_name TEXT DEFAULT '',
  to_addr TEXT DEFAULT '', subject TEXT DEFAULT '', date_raw TEXT DEFAULT '',
  date_iso TEXT DEFAULT '', seen INTEGER DEFAULT 0, flagged INTEGER DEFAULT 0,
  answered INTEGER DEFAULT 0, has_attach INTEGER DEFAULT 0, size INTEGER DEFAULT 0,
  preview TEXT DEFAULT '', fetched_at TEXT DEFAULT (datetime('now')),
  texte TEXT DEFAULT '', texte_at TEXT DEFAULT '',
  corps TEXT DEFAULT '', corps_at TEXT DEFAULT '',
  PRIMARY KEY (account, folder, uid)
);
CREATE INDEX idx_mail_cache_date ON mail_cache(account, folder, date_iso DESC);
CREATE INDEX idx_mail_cache_thread ON mail_cache(account, thread_key);

-- Compteurs de dossiers
CREATE TABLE mail_dossiers (
  account TEXT, folder TEXT, role TEXT DEFAULT '', total INTEGER DEFAULT 0,
  non_lus INTEGER DEFAULT 0, maj TEXT DEFAULT '',
  PRIMARY KEY (account, folder)
);

-- Statistiques de passe en arrière-plan
CREATE TABLE mail_passes (
  account TEXT PRIMARY KEY, ts TEXT DEFAULT '', duree_ms INTEGER DEFAULT 0,
  nouveaux INTEGER DEFAULT 0, textes INTEGER DEFAULT 0, dossiers INTEGER DEFAULT 0,
  erreur TEXT DEFAULT ''
);

-- Pièces jointes et médias
CREATE TABLE mail_media (
  uid TEXT, folder TEXT, compte TEXT, md5 TEXT, name TEXT, content_type TEXT,
  size INTEGER, inline INTEGER, cid TEXT, idx INTEGER, text_indexed INTEGER DEFAULT 0,
  text_content TEXT DEFAULT '', url TEXT DEFAULT '', ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_mail_media_kind ON mail_media(compte, folder, uid);

CREATE TABLE mail_media_scanned (
  uid TEXT, folder TEXT, compte TEXT, ts TEXT DEFAULT (datetime('now'))
);

CREATE TABLE mail_seen_tech (
  uid TEXT, folder TEXT, compte TEXT, ts TEXT DEFAULT (datetime('now'))
);

-- Règles de classement de courrier
CREATE TABLE mail_rules (
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT, label TEXT, field TEXT,
  op TEXT, value TEXT, action TEXT, target TEXT, enabled INTEGER DEFAULT 1,
  sys INTEGER DEFAULT 0, ts TEXT DEFAULT (datetime('now'))
);

-- Carnet d'adresses et contacts
CREATE TABLE contacts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT, dossier_id TEXT, uid TEXT,
  rev TEXT, name TEXT, type TEXT DEFAULT 'person', notes TEXT DEFAULT '',
  data TEXT DEFAULT '{}', bimi_url TEXT DEFAULT '', bimi_status TEXT DEFAULT '',
  bimi_ts TEXT DEFAULT '', maj TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_contacts_compte ON contacts(compte);
CREATE INDEX idx_contacts_dossier ON contacts(dossier_id);

CREATE TABLE contact_emails (
  contact_id INTEGER, addr TEXT, role TEXT DEFAULT '',
  PRIMARY KEY (contact_id, addr)
);
CREATE INDEX idx_contact_emails_addr ON contact_emails(addr);

CREATE TABLE contact_dossiers (
  id TEXT PRIMARY KEY, compte TEXT, name TEXT, maj TEXT DEFAULT (datetime('now'))
);
CREATE INDEX idx_contact_dossiers_compte ON contact_dossiers(compte);

CREATE TABLE contact_pas_doublons (
  id1 INTEGER, id2 INTEGER, compte TEXT,
  PRIMARY KEY (id1, id2)
);

CREATE TABLE contact_links (
  contact_id INTEGER, kind TEXT, ref TEXT, label TEXT DEFAULT '',
  ts TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (contact_id, kind, ref)
);
CREATE INDEX idx_contact_links_ref ON contact_links(kind, ref);

-- Traçabilité des courriers envoyés
CREATE TABLE mail_sent (
  uid TEXT, compte TEXT, msg_id TEXT, date_iso TEXT, to_addr TEXT,
  subject TEXT, ts TEXT DEFAULT (datetime('now'))
);

-- Mandats de masse
CREATE TABLE mandats (
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT, nom TEXT, etat TEXT DEFAULT 'brouillon',
  expediteur TEXT DEFAULT '', repondre_a TEXT DEFAULT '', projet_id INTEGER DEFAULT 0,
  contexte TEXT DEFAULT '{}', total INTEGER DEFAULT 0, faits INTEGER DEFAULT 0,
  erreurs INTEGER DEFAULT 0, ts TEXT DEFAULT (datetime('now')), maj TEXT DEFAULT (datetime('now'))
);

CREATE TABLE mandat_envois (
  id INTEGER PRIMARY KEY AUTOINCREMENT, mandat_id INTEGER, cle TEXT, dest TEXT,
  vars TEXT DEFAULT '{}', etat TEXT DEFAULT 'attente', envoye_le TEXT DEFAULT '',
  erreur TEXT DEFAULT ''
);
CREATE UNIQUE INDEX idx_md_cle ON mandat_envois(cle);
CREATE INDEX idx_md_env ON mandat_envois(mandat_id, id DESC);
