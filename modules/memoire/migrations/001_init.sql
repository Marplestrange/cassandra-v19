-- Un souvenir est un fait daté, prouvé, propriétaire, corrigeable d'une phrase. Rien ne s'y réécrit en place : toute évolution est une version nouvelle liée à l'ancienne.
-- Le propriétaire n'est jamais vide : « compte:x », « partage » (les faits de machine appris au service d'un administrateur), « cassandra » (ce qu'elle apprend seule), « itare ».
CREATE TABLE memoires(
  id INTEGER PRIMARY KEY AUTOINCREMENT, proprietaire TEXT NOT NULL, categorie TEXT NOT NULL, cle TEXT NOT NULL, valeur TEXT NOT NULL,
  provenance TEXT NOT NULL DEFAULT 'infere', confiance REAL NOT NULL DEFAULT 0.5, force REAL NOT NULL DEFAULT 0,
  statut TEXT NOT NULL DEFAULT 'actif',                                  -- actif | expire | conteste | quarantaine
  langue TEXT, piece_id INTEGER, valide_de TEXT, valide_a TEXT, remplace INTEGER, don_de INTEGER, version INTEGER NOT NULL DEFAULT 1,
  nb_rappels INTEGER NOT NULL DEFAULT 0, dernier_rappel TEXT, cree_le TEXT NOT NULL, maj_le TEXT NOT NULL,
  nature TEXT,                                                           -- etat-courant (porte une sonde rejouable) | constat (daté, jamais relu) | NULL (d'avant la péremption)
  sonde TEXT, sonde_args TEXT, sonde_valeur TEXT, artefact TEXT, artefact_empreinte TEXT
);
CREATE UNIQUE INDEX ux_memoires_actif ON memoires(proprietaire, cle) WHERE statut='actif';
CREATE INDEX ix_memoires_prop_statut ON memoires(proprietaire, statut);
CREATE INDEX ix_memoires_remplace ON memoires(remplace);
CREATE VIRTUAL TABLE memoires_fts USING fts5(valeur, cle, categorie, content='memoires', content_rowid='id', tokenize='unicode61');
CREATE TRIGGER memoires_fts_ai AFTER INSERT ON memoires WHEN new.statut='actif' BEGIN
  INSERT INTO memoires_fts(rowid, valeur, cle, categorie) VALUES (new.id, new.valeur, new.cle, new.categorie);
END;
-- UN SEUL déclencheur sur UPDATE : SQLite exécute plusieurs déclencheurs dans l'ordre INVERSE de leur création ; deux (sortie, entrée) réinséraient avant de supprimer et l'index
-- se corrompait au premier rappel. L'index ne bouge qu'au changement de statut : la valeur ne change jamais en place (sauf la purge d'un secret, qui passe par l'expiration).
CREATE TRIGGER memoires_fts_au AFTER UPDATE ON memoires WHEN old.statut <> new.statut BEGIN
  INSERT INTO memoires_fts(memoires_fts, rowid, valeur, cle, categorie) SELECT 'delete', old.id, old.valeur, old.cle, old.categorie WHERE old.statut='actif';
  INSERT INTO memoires_fts(rowid, valeur, cle, categorie) SELECT new.id, new.valeur, new.cle, new.categorie WHERE new.statut='actif';
END;
CREATE TRIGGER memoires_fts_ad AFTER DELETE ON memoires WHEN old.statut='actif' BEGIN
  INSERT INTO memoires_fts(memoires_fts, rowid, valeur, cle, categorie) VALUES ('delete', old.id, old.valeur, old.cle, old.categorie);
END;
CREATE TABLE pieces(id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, proprietaire TEXT NOT NULL, source TEXT, contenu TEXT, empreinte TEXT, date_piece TEXT, cree_le TEXT NOT NULL);
-- Le journal chaîné : chaque geste porte son empreinte et celle du précédent depuis une genèse constante. Une altération se voit au recalcul, elle ne s'empêche pas.
CREATE TABLE journal(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, acteur TEXT NOT NULL, verbe TEXT NOT NULL, memoire_id INTEGER, details TEXT, hash TEXT NOT NULL, previous_hash TEXT NOT NULL);
CREATE UNIQUE INDEX ux_journal_prev ON journal(previous_hash);
CREATE INDEX ix_journal_ts ON journal(ts);
CREATE INDEX ix_journal_verbe ON journal(verbe, ts);
-- Le cadran : ce qui se compte sans être un geste (un rappel vide, un bloc saturé). Une ligne chaînée par tour de chat n'était pas un journal, c'était du bruit signé.
CREATE TABLE cadran(cle TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0, dernier_ts TEXT, dernier TEXT);
CREATE TABLE doutes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, proprietaire TEXT NOT NULL, source TEXT NOT NULL, question TEXT NOT NULL, options TEXT,
  statut TEXT NOT NULL DEFAULT 'ouvert', priorite INTEGER NOT NULL DEFAULT 1, memoire_id INTEGER, memoire_id_2 INTEGER, piece_id INTEGER,
  echeance TEXT, dernier_pose TEXT, nb_poses INTEGER NOT NULL DEFAULT 0, differe INTEGER NOT NULL DEFAULT 0, resolution TEXT, resolu_le TEXT, resolu_par TEXT);
CREATE INDEX ix_doutes_statut ON doutes(statut, proprietaire);
CREATE TABLE episodes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, proprietaire TEXT NOT NULL, session_id TEXT, debut TEXT NOT NULL, fin TEXT NOT NULL, n_messages INTEGER NOT NULL DEFAULT 0,
  statut TEXT NOT NULL DEFAULT 'ouvert', resume TEXT, termes TEXT, cree_le TEXT NOT NULL);
CREATE INDEX ix_episodes_prop ON episodes(proprietaire, statut);
CREATE VIRTUAL TABLE episodes_fts USING fts5(resume, termes, content='episodes', content_rowid='id', tokenize='unicode61');
CREATE TRIGGER episodes_fts_au AFTER UPDATE ON episodes WHEN old.statut <> new.statut BEGIN
  INSERT INTO episodes_fts(episodes_fts, rowid, resume, termes) SELECT 'delete', old.id, old.resume, old.termes WHERE old.statut='ferme';
  INSERT INTO episodes_fts(rowid, resume, termes) SELECT new.id, new.resume, new.termes WHERE new.statut='ferme';
END;
-- Les échanges d'une session, gardés pour résumer l'épisode (le fil de chat appartiendra à un autre module ; la mémoire n'en garde que les derniers messages de l'épisode).
CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT, episode_id INTEGER NOT NULL, role TEXT NOT NULL, contenu TEXT NOT NULL, ts TEXT NOT NULL);
CREATE INDEX ix_messages_episode ON messages(episode_id);
-- La mémoire adressée : une condition mécanique sur une mesure, jamais évaluée par le modèle. Le rappel rappelle, il n'exécute rien.
CREATE TABLE rappels(
  id INTEGER PRIMARY KEY AUTOINCREMENT, proprietaire TEXT NOT NULL, cle TEXT NOT NULL, metrique TEXT NOT NULL, op TEXT NOT NULL, seuil REAL NOT NULL, message TEXT NOT NULL,
  actif INTEGER NOT NULL DEFAULT 1, dernier_declenche TEXT, nb_declenches INTEGER NOT NULL DEFAULT 0, acteur TEXT, cree_le TEXT NOT NULL);
-- Le tour en cours d'un compte : la question, son début, ce que l'outil « retenir » y a déjà écrit (la distillation ne repasse pas derrière lui).
CREATE TABLE tours(compte TEXT PRIMARY KEY, question TEXT NOT NULL DEFAULT '', debut TEXT NOT NULL, ecrits TEXT NOT NULL DEFAULT '[]', cites TEXT NOT NULL DEFAULT '[]');
-- La file de distillation : un fait naît d'un déclencheur de la liste fermée ; l'appel du modèle se fait HORS du chemin de la réponse, par un moteur (jamais un fil dans un module).
CREATE TABLE file(id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, acteur TEXT NOT NULL DEFAULT '', declencheur TEXT NOT NULL, question TEXT NOT NULL DEFAULT '', reponse TEXT NOT NULL DEFAULT '',
                  piece TEXT NOT NULL DEFAULT '', etat TEXT NOT NULL DEFAULT 'attente', resultat TEXT NOT NULL DEFAULT '', ts TEXT NOT NULL);
CREATE INDEX ix_file_etat ON file(etat, id);
