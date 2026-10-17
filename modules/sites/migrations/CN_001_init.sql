-- Les sites suivis par Cassandra. Une table appartient à ce module et à lui seul.
-- Un site déclaré ou attribué appartient à UN compte. S'y ajoutent, en lecture seule, les sites inscrits dans la fiche du compte (module comptes)
-- et ceux du panneau dont le propriétaire est le compte du panneau lié à ce compte (fiche du compte : fp_account).
CREATE TABLE sites(
  domaine TEXT PRIMARY KEY, compte TEXT NOT NULL, origine TEXT NOT NULL DEFAULT 'declare',   -- declare | attribue
  cree REAL NOT NULL, par TEXT NOT NULL DEFAULT ''
);
CREATE INDEX sites_compte ON sites(compte);
-- Les mesures de la sonde : le code seul ne suffit pas, un site qui répond 200 en huit secondes est en panne pour ses visiteurs.
CREATE TABLE mesures(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, domaine TEXT NOT NULL,
  code INTEGER, ms INTEGER, up INTEGER NOT NULL, ssl_jours INTEGER, erreur TEXT NOT NULL DEFAULT ''
);
CREATE INDEX mesures_dom ON mesures(domaine, ts);
CREATE INDEX mesures_ts ON mesures(ts);
CREATE TABLE evenements_site(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, domaine TEXT NOT NULL, genre TEXT NOT NULL,   -- decouverte | panne | retour
  detail TEXT NOT NULL DEFAULT '', duree_min INTEGER
);
CREATE INDEX evenements_site_dom ON evenements_site(domaine, ts);
CREATE TABLE etat_vu(domaine TEXT PRIMARY KEY, up INTEGER NOT NULL, depuis REAL NOT NULL, ts REAL NOT NULL);
CREATE TABLE liens(
  domaine TEXT NOT NULL, genre TEXT NOT NULL, ref TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', ts REAL NOT NULL,
  PRIMARY KEY(domaine, genre, ref)
);
CREATE TABLE demandes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, domaine TEXT NOT NULL, compte TEXT NOT NULL, message TEXT NOT NULL DEFAULT '',
  statut TEXT NOT NULL DEFAULT 'ouverte', reponse TEXT NOT NULL DEFAULT '', traite_par TEXT NOT NULL DEFAULT '', traite_ts REAL
);
CREATE UNIQUE INDEX demandes_ouverte ON demandes(domaine) WHERE statut = 'ouverte';
CREATE TABLE accords(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, domaine TEXT NOT NULL, compte TEXT NOT NULL, geste TEXT NOT NULL, jusqu_a REAL NOT NULL
);
CREATE INDEX accords_dom ON accords(domaine, geste);
-- Le journal des gestes sur les sites : qui a fait quoi sur quel site.
CREATE TABLE journal(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, acteur TEXT NOT NULL, verbe TEXT NOT NULL, domaine TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX journal_dom ON journal(domaine, ts);
