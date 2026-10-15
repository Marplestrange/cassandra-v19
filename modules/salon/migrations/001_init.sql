-- Un fil de travail : un titre, un but, un statut. Il appartient à un compte ; d'autres comptes y entrent par invitation. Les agents n'en sont pas membres : on les ADRESSE.
CREATE TABLE fils(
  id INTEGER PRIMARY KEY AUTOINCREMENT, titre TEXT NOT NULL DEFAULT '', but TEXT NOT NULL DEFAULT '', statut TEXT NOT NULL DEFAULT 'ouvert',
  proprietaire TEXT NOT NULL, cree REAL NOT NULL, dernier REAL NOT NULL, mode TEXT NOT NULL DEFAULT 'agir', terrain TEXT NOT NULL DEFAULT ''
);
CREATE INDEX fils_proprietaire ON fils(proprietaire, dernier);
CREATE TABLE membres(fil INTEGER NOT NULL, compte TEXT NOT NULL, invite_par TEXT NOT NULL DEFAULT '', ts REAL NOT NULL, PRIMARY KEY(fil, compte));
-- Un message : un auteur, des destinataires (un CHAMP — le corps n'est jamais lu pour router), un corps, des sources.
CREATE TABLE messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, fil INTEGER NOT NULL, ts REAL NOT NULL, auteur TEXT NOT NULL, destinataires TEXT NOT NULL DEFAULT '[]',
  corps TEXT NOT NULL DEFAULT '', sources TEXT NOT NULL DEFAULT '[]', humain INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX messages_fil ON messages(fil, id);
-- Jusqu'où chacun a lu (un humain, ou un agent résident).
CREATE TABLE vus(acteur TEXT NOT NULL, fil INTEGER NOT NULL, dernier INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(acteur, fil));
-- Qui a supprimé ou changé le statut de quoi : la trace avant le geste.
CREATE TABLE journal(id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, acteur TEXT NOT NULL DEFAULT '', geste TEXT NOT NULL, fil INTEGER NOT NULL, titre TEXT NOT NULL DEFAULT '', messages INTEGER NOT NULL DEFAULT 0, details TEXT NOT NULL DEFAULT '');
-- L'archivage est un RANGEMENT du compte, pas un statut du fil : le fil vit pour tous, chacun range sa liste.
CREATE TABLE rangements(compte TEXT NOT NULL, fil INTEGER NOT NULL, etat TEXT NOT NULL DEFAULT 'archive', PRIMARY KEY(compte, fil));
-- Le résumé roulant d'un fil long : jusqu'où il va, qui l'a rédigé.
CREATE TABLE resumes(fil INTEGER PRIMARY KEY, jusqu_a INTEGER NOT NULL DEFAULT 0, texte TEXT NOT NULL DEFAULT '', par TEXT NOT NULL DEFAULT '', ts REAL NOT NULL, tranches INTEGER NOT NULL DEFAULT 0);
-- La conversation de l'agent pour un fil et un compte (c'est le module des agents qui la tient).
CREATE TABLE convs(fil INTEGER NOT NULL, agent TEXT NOT NULL, compte TEXT NOT NULL, conversation_id INTEGER NOT NULL, PRIMARY KEY(fil, agent, compte));
-- Les tours d'un agent : « écrit… » tant que fin est vide, et la panne s'il y en a une.
CREATE TABLE tours(id INTEGER PRIMARY KEY AUTOINCREMENT, fil INTEGER NOT NULL, agent TEXT NOT NULL, debut REAL NOT NULL, fin REAL, erreur TEXT NOT NULL DEFAULT '');
CREATE INDEX tours_agent ON tours(agent, fin);
-- L'index plein texte des messages (contenu externe : rien n'est copié deux fois). UN déclencheur par événement : SQLite exécute plusieurs déclencheurs d'un même événement dans l'ordre INVERSE de leur création,
-- et deux déclencheurs (sortie, entrée) corrompaient un index en silence. Le corps ne change jamais en place.
CREATE VIRTUAL TABLE messages_fts USING fts5(corps, auteur, content='messages', content_rowid='id', tokenize='unicode61');
CREATE TRIGGER messages_fts_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, corps, auteur) VALUES (new.id, new.corps, new.auteur);
END;
CREATE TRIGGER messages_fts_ad AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, corps, auteur) VALUES ('delete', old.id, old.corps, old.auteur);
END;
