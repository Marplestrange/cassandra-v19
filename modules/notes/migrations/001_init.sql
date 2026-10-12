-- Les notes sont à la PERSONNE. Le numéro (N-0007) est l'identité : il ne change jamais et n'est jamais réattribué, corbeille et purge comprises
-- (un vieux renvoi ne tombera jamais sur une note qui n'a rien à voir). Le titre et le dossier se changent sans casser aucun renvoi.
CREATE TABLE notes(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, num INTEGER NOT NULL,
  titre TEXT NOT NULL, corps TEXT NOT NULL DEFAULT '',
  etiquettes TEXT NOT NULL DEFAULT '[]', projet TEXT NOT NULL DEFAULT '', dossier TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '', epinglee INTEGER NOT NULL DEFAULT 0,
  etat TEXT NOT NULL DEFAULT '', relire TEXT NOT NULL DEFAULT '', rattache TEXT NOT NULL DEFAULT '[]',
  cree REAL NOT NULL, modifie REAL NOT NULL, vues INTEGER NOT NULL DEFAULT 0, vu_at REAL,
  corbeille_at REAL, redirige INTEGER,                                          -- redirige : le numéro de la note qui a absorbé celle-ci (fusion)
  UNIQUE(compte, num)
);
CREATE INDEX notes_compte ON notes(compte, corbeille_at);
CREATE TABLE compteurs(compte TEXT PRIMARY KEY, dernier INTEGER NOT NULL);
CREATE TABLE dossiers(compte TEXT NOT NULL, chemin TEXT NOT NULL, PRIMARY KEY(compte, chemin));
-- Chaque écriture laisse la version d'AVANT (jamais d'après : après, l'ancien contenu n'existe déjà plus).
CREATE TABLE versions(id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER NOT NULL, ts REAL NOT NULL, auteur TEXT NOT NULL DEFAULT '', motif TEXT NOT NULL DEFAULT '', titre TEXT NOT NULL, corps TEXT NOT NULL);
CREATE INDEX versions_note ON versions(note_id, id);
-- Le reste de l'histoire : rangements, rattachements, changements d'état.
CREATE TABLE activite(id INTEGER PRIMARY KEY AUTOINCREMENT, note_id INTEGER NOT NULL, ts REAL NOT NULL, quoi TEXT NOT NULL, det TEXT NOT NULL DEFAULT '', qui TEXT NOT NULL DEFAULT '');
CREATE INDEX activite_note ON activite(note_id, id);
-- Une adresse qu'on envoie, qui sert la note sans session, expire et se retire. Le jeton ne porte JAMAIS un chemin.
CREATE TABLE partages(jeton TEXT PRIMARY KEY, compte TEXT NOT NULL, note_id INTEGER NOT NULL, titre TEXT NOT NULL DEFAULT '', format TEXT NOT NULL DEFAULT 'html', mdp TEXT NOT NULL DEFAULT '',
                      expire_le REAL, n_vues INTEGER NOT NULL DEFAULT 0, dernier REAL, cree REAL NOT NULL);
CREATE INDEX partages_compte ON partages(compte);
-- Une case à cocher peut être liée à une tâche (module taches) : la LIGNE est dans la clé, deux cases d'une même note peuvent porter le même texte.
CREATE TABLE cases(note_id INTEGER NOT NULL, ligne INTEGER NOT NULL, tache_id INTEGER NOT NULL, texte TEXT NOT NULL DEFAULT '', PRIMARY KEY(note_id, ligne));
