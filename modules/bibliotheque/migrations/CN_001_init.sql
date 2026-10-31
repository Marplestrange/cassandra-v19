-- La bibliothèque d'Amizo : la CONNAISSANCE sourcée, dans SA base (donnees/modules/bibliotheque.db), à part de la Mémoire (un souvenir est une phrase
-- retenue ; une fiche est un document avec sa provenance). Rien ne se partage entre sociétés : toute ligne porte sa société, toute lecture la filtre.
CREATE TABLE meta(cle TEXT PRIMARY KEY, valeur TEXT NOT NULL);

-- Une source = un domaine (externe). « inconnue » par défaut ; « autorisee » monte la confiance ; « bloquee » ferme la porte (et bloque ses fiches).
CREATE TABLE sources(
  societe TEXT NOT NULL, domaine TEXT NOT NULL, statut TEXT NOT NULL DEFAULT 'inconnue' CHECK(statut IN ('inconnue','autorisee','bloquee')),
  confiance REAL NOT NULL DEFAULT 0.4, note TEXT NOT NULL DEFAULT '', maj REAL NOT NULL, par TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(societe, domaine));

-- Une fiche : un document. etagere interne = lu dans un espace partagé de la société (déjà de confiance) ; externe = lu sur le web (quarantaine d'abord).
-- L'état STOCKÉ est quarantaine | verifie | bloque ; « perime » se calcule à la lecture (lu_le trop ancien), il n'est jamais écrit.
CREATE TABLE fiches(
  id INTEGER PRIMARY KEY AUTOINCREMENT, societe TEXT NOT NULL,
  etagere TEXT NOT NULL CHECK(etagere IN ('interne','externe')),
  source TEXT NOT NULL, domaine TEXT NOT NULL DEFAULT '', titre TEXT NOT NULL, corps TEXT NOT NULL,
  empreinte TEXT NOT NULL, etat TEXT NOT NULL CHECK(etat IN ('quarantaine','verifie','bloque')),
  lu_le REAL NOT NULL, cree REAL NOT NULL, maj REAL NOT NULL, auteur TEXT NOT NULL DEFAULT '',
  verifie_par TEXT NOT NULL DEFAULT '', verifie_le REAL, motif TEXT NOT NULL DEFAULT '',
  version INTEGER NOT NULL DEFAULT 1, retire_le REAL);
-- Une adresse = une fiche vivante ; un contenu (empreinte) = une fiche vivante : le doublon n'entre pas, il s'ajoute aux attestations.
CREATE UNIQUE INDEX fiches_source ON fiches(societe, source) WHERE retire_le IS NULL;
CREATE UNIQUE INDEX fiches_empreinte ON fiches(societe, empreinte) WHERE retire_le IS NULL;
CREATE INDEX fiches_etat ON fiches(societe, etagere, etat);

-- Chaque adresse qui a porté EXACTEMENT ce contenu : deux domaines différents = deux sources concordantes.
CREATE TABLE attestations(
  fiche_id INTEGER NOT NULL, source TEXT NOT NULL, domaine TEXT NOT NULL DEFAULT '', lu_le REAL NOT NULL, PRIMARY KEY(fiche_id, source));

-- Le texte d'une fiche en passages, dans l'ordre (position gardée).
CREATE TABLE passages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fiche_id INTEGER NOT NULL, position INTEGER NOT NULL, titre TEXT NOT NULL DEFAULT '', texte TEXT NOT NULL,
  UNIQUE(fiche_id, position));

-- L'historique : la version d'AVANT, à chaque changement de contenu.
CREATE TABLE versions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fiche_id INTEGER NOT NULL, numero INTEGER NOT NULL, titre TEXT NOT NULL, corps TEXT NOT NULL,
  empreinte TEXT NOT NULL, lu_le REAL NOT NULL, auteur TEXT NOT NULL DEFAULT '', ts REAL NOT NULL);
CREATE INDEX versions_fiche ON versions(fiche_id, numero);

CREATE TABLE journal(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, societe TEXT NOT NULL, fiche_id INTEGER, quoi TEXT NOT NULL, par TEXT NOT NULL DEFAULT '', det TEXT NOT NULL DEFAULT '');

-- Recherche plein texte (index à contenu externe : la table passages). UN SEUL déclencheur par événement : deux AFTER UPDATE sur un même index externe ont
-- déjà corrompu un index sans erreur (le second « supprime » avec des valeurs que le premier a déjà changées). Le test de cohérence le vérifie.
CREATE VIRTUAL TABLE passages_fts USING fts5(titre, texte, content='passages', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
CREATE TRIGGER passages_ai AFTER INSERT ON passages BEGIN
  INSERT INTO passages_fts(rowid, titre, texte) VALUES (new.id, new.titre, new.texte);
END;
CREATE TRIGGER passages_ad AFTER DELETE ON passages BEGIN
  INSERT INTO passages_fts(passages_fts, rowid, titre, texte) VALUES ('delete', old.id, old.titre, old.texte);
  DELETE FROM vecteurs WHERE passage_id = old.id;
END;
CREATE TRIGGER passages_au AFTER UPDATE ON passages BEGIN
  INSERT INTO passages_fts(passages_fts, rowid, titre, texte) VALUES ('delete', old.id, old.titre, old.texte);
  INSERT INTO passages_fts(rowid, titre, texte) VALUES (new.id, new.titre, new.texte);
  DELETE FROM vecteurs WHERE passage_id = old.id;
END;

-- La recherche par le sens est PRÉVUE, pas active : le nom du modèle est écrit ici (meta), les vecteurs se calculent au premier usage, seulement quand le
-- modèle est prêt. Un seul modèle, partagé avec la Mémoire.
CREATE TABLE vecteurs(passage_id INTEGER PRIMARY KEY, modele TEXT NOT NULL, dim INTEGER NOT NULL, vecteur BLOB NOT NULL, ts REAL NOT NULL);
INSERT INTO meta(cle, valeur) VALUES('modele_vecteurs', 'intfloat/multilingual-e5-large');
INSERT INTO meta(cle, valeur) VALUES('recherche_sens', 'prevue');
