-- Billetterie, lot 1 : les bases (salles, artistes, revendeurs), les formules de rémunération, les événements et ce qui s'y rattache.
-- Tout l'argent est en CENTIMES entiers. Un identifiant (ref, code) n'est JAMAIS réutilisé : `sequences` compte, `retires` se souvient.

CREATE TABLE sequences(
  type TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE retires(
  type TEXT NOT NULL, ref TEXT NOT NULL, nom TEXT NOT NULL DEFAULT '', motif TEXT NOT NULL DEFAULT '',
  le TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY(type, ref)
);

CREATE TABLE salles(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, nom TEXT NOT NULL,
  adresse TEXT NOT NULL DEFAULT '', contact TEXT NOT NULL DEFAULT '',
  location INTEGER NOT NULL DEFAULT 0, acompte INTEGER NOT NULL DEFAULT 0, caution INTEGER NOT NULL DEFAULT 0,
  assis INTEGER NOT NULL DEFAULT 0, debout INTEGER NOT NULL DEFAULT 0, pmr INTEGER NOT NULL DEFAULT 1,
  erp TEXT NOT NULL DEFAULT '', heure_fin TEXT NOT NULL DEFAULT '', bruit TEXT NOT NULL DEFAULT '',
  alcool TEXT NOT NULL DEFAULT '', age TEXT NOT NULL DEFAULT '', equipements TEXT NOT NULL DEFAULT '',
  annulation TEXT NOT NULL DEFAULT '', assurance TEXT NOT NULL DEFAULT '',
  cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Les formules : DEUX groupes qui ne se mélangent jamais.
--   artiste     : l'artiste vend lui-même (forfait + commission par place)
--   cachet      : l'artiste ne vend pas (cachet fixe)
--   independant : le revendeur indépendant (commission par place, fixe par événement, palier)
CREATE TABLE formules(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, nom TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('artiste','cachet','independant')),
  forfait INTEGER NOT NULL DEFAULT 0, com INTEGER NOT NULL DEFAULT 0, fixe INTEGER NOT NULL DEFAULT 0,
  palier INTEGER NOT NULL DEFAULT 0, palier_n INTEGER NOT NULL DEFAULT 0, palier_com INTEGER NOT NULL DEFAULT 0,
  note TEXT NOT NULL DEFAULT '', cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE artistes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, scene TEXT NOT NULL,
  legal TEXT NOT NULL DEFAULT '', genre TEXT NOT NULL DEFAULT '',
  statut TEXT NOT NULL DEFAULT 'Particulier' CHECK(statut IN ('Particulier','Association','Société')),
  mail TEXT NOT NULL DEFAULT '', tel TEXT NOT NULL DEFAULT '', rider TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '',
  formule_id INTEGER, vend INTEGER NOT NULL DEFAULT 0, revendeur_id INTEGER,
  siret TEXT NOT NULL DEFAULT '', ape TEXT NOT NULL DEFAULT '', tva TEXT NOT NULL DEFAULT '',
  adresse TEXT NOT NULL DEFAULT '', code_postal TEXT NOT NULL DEFAULT '', ville TEXT NOT NULL DEFAULT '', pays TEXT NOT NULL DEFAULT 'FR',
  adhesion_fin TEXT NOT NULL DEFAULT '', compte TEXT NOT NULL DEFAULT '',
  cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE revendeurs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, code TEXT NOT NULL UNIQUE, nom TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'independant' CHECK(type IN ('independant','artiste')),
  statut TEXT NOT NULL DEFAULT 'Particulier' CHECK(statut IN ('Particulier','Association','Société')),
  mail TEXT NOT NULL DEFAULT '', tel TEXT NOT NULL DEFAULT '', artiste_id INTEGER, compte TEXT NOT NULL DEFAULT '',
  siret TEXT NOT NULL DEFAULT '', ape TEXT NOT NULL DEFAULT '', tva TEXT NOT NULL DEFAULT '',
  adresse TEXT NOT NULL DEFAULT '', code_postal TEXT NOT NULL DEFAULT '', ville TEXT NOT NULL DEFAULT '', pays TEXT NOT NULL DEFAULT 'FR',
  actif INTEGER NOT NULL DEFAULT 1, suspendu_motif TEXT NOT NULL DEFAULT '',
  cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE evenements(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, nom TEXT NOT NULL,
  date_iso TEXT NOT NULL DEFAULT '', salle_id INTEGER, conf TEXT NOT NULL DEFAULT 'debout' CHECK(conf IN ('assis','debout')),
  quota INTEGER NOT NULL DEFAULT 0, prix INTEGER NOT NULL DEFAULT 0,
  statut TEXT NOT NULL DEFAULT 'brouillon' CHECK(statut IN ('brouillon','en vente','complet','annulé','reporté','terminé')),
  publie INTEGER NOT NULL DEFAULT 0, type TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', accroche TEXT NOT NULL DEFAULT '',
  tags TEXT NOT NULL DEFAULT '', portes TEXT NOT NULL DEFAULT '19:30', debut TEXT NOT NULL DEFAULT '20:00', fin TEXT NOT NULL DEFAULT '23:00',
  age TEXT NOT NULL DEFAULT 'Tous publics', responsable TEXT NOT NULL DEFAULT '', projet_ref TEXT NOT NULL DEFAULT '',
  achat TEXT NOT NULL DEFAULT 'general' CHECK(achat IN ('general','obligatoire','libre')), frais_sans_compte INTEGER,
  pause INTEGER NOT NULL DEFAULT 10, reporte_au TEXT NOT NULL DEFAULT '', motif_annulation TEXT NOT NULL DEFAULT '',
  cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_evt_date ON evenements(date_iso);

CREATE TABLE types_billets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, evenement_id INTEGER NOT NULL,
  nom TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', prix INTEGER NOT NULL DEFAULT 0, quota INTEGER NOT NULL DEFAULT 0,
  entrees INTEGER NOT NULL DEFAULT 1, visible INTEGER NOT NULL DEFAULT 1, ouverture TEXT NOT NULL DEFAULT '', fermeture TEXT NOT NULL DEFAULT '',
  canaux TEXT NOT NULL DEFAULT 'boutique,caisse,revendeur', rang INTEGER NOT NULL DEFAULT 0,
  UNIQUE(evenement_id, nom)
);

CREATE TABLE passages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, evenement_id INTEGER NOT NULL, artiste_id INTEGER NOT NULL,
  ordre INTEGER NOT NULL DEFAULT 1, duree INTEGER NOT NULL DEFAULT 30, formule_id INTEGER
);
CREATE INDEX idx_pas_evt ON passages(evenement_id, ordre);

CREATE TABLE affectations(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, evenement_id INTEGER NOT NULL, revendeur_id INTEGER NOT NULL,
  formule_id INTEGER NOT NULL, quota INTEGER NOT NULL DEFAULT 0,
  UNIQUE(evenement_id, revendeur_id, formule_id)
);

CREATE TABLE invitations(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ref TEXT NOT NULL UNIQUE, evenement_id INTEGER NOT NULL, categorie TEXT NOT NULL,
  quota INTEGER NOT NULL DEFAULT 0, emises INTEGER NOT NULL DEFAULT 0, UNIQUE(evenement_id, categorie)
);

-- Les conditions d'une formule gelées pour un événement qui a déjà des ventes : modifier la formule ne les change pas.
CREATE TABLE formules_figees(
  evenement_id INTEGER NOT NULL, formule_id INTEGER NOT NULL, contenu TEXT NOT NULL, le TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(evenement_id, formule_id)
);
