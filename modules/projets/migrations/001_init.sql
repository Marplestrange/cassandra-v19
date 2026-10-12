-- Les projets. Un projet appartient à UN compte (son propriétaire) ; d'autres comptes y entrent par invitation, avec un rôle.
CREATE TABLE projets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL,
  nom TEXT NOT NULL, statut TEXT NOT NULL DEFAULT 'actif', genre TEXT NOT NULL DEFAULT 'perso', modele TEXT NOT NULL DEFAULT 'vide', priorite TEXT NOT NULL DEFAULT 'Normale',
  debut TEXT NOT NULL DEFAULT '', fin TEXT NOT NULL DEFAULT '', resume TEXT NOT NULL DEFAULT '', objectif TEXT NOT NULL DEFAULT '',
  perimetre_in TEXT NOT NULL DEFAULT '', perimetre_out TEXT NOT NULL DEFAULT '', reussite TEXT NOT NULL DEFAULT '',
  domaine TEXT NOT NULL DEFAULT '', serveur TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '',                 -- le journal : une ligne « [AAAA-MM-JJ HH:MM] texte » par mouvement
  ref_date TEXT NOT NULL DEFAULT '',              -- date où le plan de référence a été figé
  archive INTEGER NOT NULL DEFAULT 0,
  supprime_at REAL,                               -- à la corbeille depuis ; rien n'est effacé tant que la purge n'est pas demandée
  cree REAL NOT NULL, maj REAL NOT NULL
);
CREATE INDEX projets_compte ON projets(compte);
CREATE TABLE phases(
  id INTEGER PRIMARY KEY AUTOINCREMENT, projet_id INTEGER NOT NULL, nom TEXT NOT NULL, ordre INTEGER NOT NULL DEFAULT 0,
  debut TEXT NOT NULL DEFAULT '', fin TEXT NOT NULL DEFAULT '', ref_debut TEXT NOT NULL DEFAULT '', ref_fin TEXT NOT NULL DEFAULT '',
  etat TEXT NOT NULL DEFAULT 'À venir', charge INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX phases_projet ON phases(projet_id);
CREATE TABLE jalons(
  id INTEGER PRIMARY KEY AUTOINCREMENT, projet_id INTEGER NOT NULL, date TEXT NOT NULL DEFAULT '', nom TEXT NOT NULL,
  etat TEXT NOT NULL DEFAULT 'prevu', ref_date TEXT NOT NULL DEFAULT '', tenu_le TEXT NOT NULL DEFAULT ''
);
CREATE INDEX jalons_projet ON jalons(projet_id);
CREATE TABLE decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, projet_id INTEGER NOT NULL, question TEXT NOT NULL, reponse TEXT NOT NULL DEFAULT '', raison TEXT NOT NULL DEFAULT '',
  etat TEXT NOT NULL DEFAULT 'ouverte', seuil TEXT NOT NULL DEFAULT '', ferme TEXT NOT NULL DEFAULT '', auteur TEXT NOT NULL DEFAULT '', quand REAL NOT NULL
);
CREATE INDEX decisions_projet ON decisions(projet_id);
CREATE TABLE membres(
  projet_id INTEGER NOT NULL, compte TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'lecteur', etat TEXT NOT NULL DEFAULT 'invite', invite_par TEXT NOT NULL DEFAULT '', ts REAL NOT NULL,
  PRIMARY KEY(projet_id, compte)
);
CREATE INDEX membres_compte ON membres(compte, etat);
