-- Le cache du courrier : le serveur IMAP reste la référence, ceci n'est qu'une mémoire (en-têtes, texte des trois derniers mois).
CREATE TABLE messages(
  compte TEXT NOT NULL, dossier TEXT NOT NULL, uid TEXT NOT NULL,
  msg_id TEXT NOT NULL DEFAULT '', fil TEXT NOT NULL DEFAULT '', de_addr TEXT NOT NULL DEFAULT '', de_nom TEXT NOT NULL DEFAULT '', a_addr TEXT NOT NULL DEFAULT '',
  objet TEXT NOT NULL DEFAULT '', date_brute TEXT NOT NULL DEFAULT '', date_iso TEXT NOT NULL DEFAULT '',
  lu INTEGER NOT NULL DEFAULT 0, suivi INTEGER NOT NULL DEFAULT 0, repondu INTEGER NOT NULL DEFAULT 0, pj INTEGER NOT NULL DEFAULT 0, taille INTEGER NOT NULL DEFAULT 0,
  texte TEXT NOT NULL DEFAULT '', texte_le REAL, vu_le REAL NOT NULL DEFAULT 0,
  PRIMARY KEY(compte, dossier, uid)
);
CREATE INDEX messages_date ON messages(compte, dossier, date_iso DESC);
CREATE INDEX messages_fil ON messages(compte, fil);
CREATE TABLE dossiers(compte TEXT NOT NULL, nom TEXT NOT NULL, role TEXT NOT NULL DEFAULT '', total INTEGER NOT NULL DEFAULT 0, non_lus INTEGER NOT NULL DEFAULT 0, maj REAL NOT NULL DEFAULT 0, PRIMARY KEY(compte, nom));
CREATE TABLE passes(compte TEXT PRIMARY KEY, ts REAL NOT NULL, duree_ms INTEGER NOT NULL DEFAULT 0, nouveaux INTEGER NOT NULL DEFAULT 0, textes INTEGER NOT NULL DEFAULT 0, dossiers INTEGER NOT NULL DEFAULT 0, erreur TEXT NOT NULL DEFAULT '');
-- Le journal des envois : un message parti au mauvais destinataire doit laisser une trace consultable (destinataire, objet, extrait ; pas le corps entier).
CREATE TABLE envoyes(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, compte TEXT NOT NULL, a TEXT NOT NULL, cc TEXT NOT NULL DEFAULT '', objet TEXT NOT NULL DEFAULT '', extrait TEXT NOT NULL DEFAULT '', ok INTEGER NOT NULL DEFAULT 1, raison TEXT NOT NULL DEFAULT '');
CREATE INDEX envoyes_compte ON envoyes(compte, id DESC);
