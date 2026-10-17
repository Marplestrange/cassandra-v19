-- L'agenda est à la PERSONNE : ses événements, ses rappels, ses liens. Un identifiant deviné ne rend rien de l'agenda d'un autre.
CREATE TABLE evenements(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, uid TEXT NOT NULL,         -- uid : un réimport du même fichier met à jour au lieu de dupliquer
  titre TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', lieu TEXT NOT NULL DEFAULT '',
  debut TEXT NOT NULL, fin TEXT NOT NULL DEFAULT '', journee INTEGER NOT NULL DEFAULT 0,  -- dates naïves « AAAA-MM-JJ HH:MM » (ou « AAAA-MM-JJ » pour une journée)
  source TEXT NOT NULL DEFAULT 'manuel', projet_id INTEGER,
  recurrence TEXT NOT NULL DEFAULT '', alarme TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
  cree REAL NOT NULL, UNIQUE(compte, uid)
);
CREATE INDEX evenements_debut ON evenements(compte, debut);
CREATE TABLE liens(id INTEGER PRIMARY KEY AUTOINCREMENT, evenement_id INTEGER NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, label TEXT NOT NULL DEFAULT '', cree REAL NOT NULL, UNIQUE(evenement_id, kind, ref));
CREATE TABLE journal(id INTEGER PRIMARY KEY AUTOINCREMENT, evenement_id INTEGER NOT NULL, texte TEXT NOT NULL, acteur TEXT NOT NULL DEFAULT '', ts REAL NOT NULL);
CREATE INDEX journal_evenement ON journal(evenement_id);
CREATE TABLE rappels(id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, texte TEXT NOT NULL, echeance TEXT NOT NULL DEFAULT '', statut TEXT NOT NULL DEFAULT 'attente', cree REAL NOT NULL);
CREATE INDEX rappels_compte ON rappels(compte, statut);
