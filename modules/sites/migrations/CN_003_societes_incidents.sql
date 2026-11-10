-- La société d'un site. Un site du panneau appartient à un compte, qui appartient à une société : le site lui-même n'était attribué à rien.
-- Ici la société qu'on lui a ATTRIBUÉE ; sans ligne, il suit celle de son compte ; sans compte non plus, seuls les superadministrateurs le voient.
CREATE TABLE societes_site(domaine TEXT PRIMARY KEY, societe TEXT NOT NULL, par TEXT NOT NULL DEFAULT '', ts REAL NOT NULL);
-- Une panne est un objet : un diagnostic, quelqu'un qui s'en occupe, une chronologie, une cause. Un incident s'ouvre quand la panne est confirmée
-- et se clôt quand le site répond de nouveau (seul si personne n'y a touché ; sinon il attend sa cause).
CREATE TABLE incidents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, domaine TEXT NOT NULL, debut REAL NOT NULL, fin REAL,
  etat TEXT NOT NULL DEFAULT 'ouvert',                                   -- ouvert | depannage | retabli | resolu
  diagnostic TEXT NOT NULL DEFAULT '', code INTEGER, erreur TEXT NOT NULL DEFAULT '',
  pris_par TEXT NOT NULL DEFAULT '', connu_jusqu REAL, cause TEXT NOT NULL DEFAULT '', clos_par TEXT NOT NULL DEFAULT ''
);
CREATE INDEX incidents_dom ON incidents(domaine, debut);
CREATE UNIQUE INDEX incidents_ouvert ON incidents(domaine) WHERE etat IN ('ouvert', 'depannage');
-- La chronologie d'un incident : qui a su, qui a fait quoi.
CREATE TABLE incident_faits(
  id INTEGER PRIMARY KEY AUTOINCREMENT, incident INTEGER NOT NULL, ts REAL NOT NULL, acteur TEXT NOT NULL, genre TEXT NOT NULL, texte TEXT NOT NULL DEFAULT ''
);
CREATE INDEX incident_faits_i ON incident_faits(incident, ts);
-- L'objectif de disponibilité d'un site (sans ligne : celui du réglage « objectif_pct »).
CREATE TABLE objectifs(domaine TEXT PRIMARY KEY, pct REAL NOT NULL, par TEXT NOT NULL DEFAULT '', ts REAL NOT NULL);
-- La preuve de propriété. Le panneau dit à qui est un site ; sans lui, c'est la preuve qui le dit : un enregistrement DNS ou un fichier portant ce jeton.
-- Tant qu'elle manque, le site n'est à personne : il n'est pas dans la table sites, pas mesuré, et un autre compte peut encore le réclamer.
CREATE TABLE preuves(
  domaine TEXT NOT NULL, compte TEXT NOT NULL, jeton TEXT NOT NULL, cree REAL NOT NULL, essais INTEGER NOT NULL DEFAULT 0, dernier REAL,
  PRIMARY KEY(domaine, compte)
);
