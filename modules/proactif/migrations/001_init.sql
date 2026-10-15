-- L'ombre : ce qu'elle AURAIT fait. Rien n'est exécuté ; c'est la façon honnête d'accorder de l'autonomie.
CREATE TABLE pf_ombre(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL DEFAULT (datetime('now')),
  fkey TEXT NOT NULL DEFAULT '', signature TEXT NOT NULL DEFAULT '', action_kind TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL DEFAULT '', titre TEXT NOT NULL DEFAULT '', motif TEXT NOT NULL DEFAULT '',
  verdict TEXT NOT NULL DEFAULT '', avis TEXT NOT NULL DEFAULT ''
);
-- Le savoir-faire : la confiance se mesure (réussites, échecs, état, réversibilité).
CREATE TABLE proactive_playbooks(
  signature TEXT PRIMARY KEY, action_kind TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '',
  successes INTEGER NOT NULL DEFAULT 0, failures INTEGER NOT NULL DEFAULT 0,
  last_used TEXT NOT NULL DEFAULT '', last_outcome TEXT NOT NULL DEFAULT '',
  etat TEXT NOT NULL DEFAULT 'proposition', echecs_suite INTEGER NOT NULL DEFAULT 0,
  reversible INTEGER NOT NULL DEFAULT 1, promu_le TEXT NOT NULL DEFAULT '', nom TEXT NOT NULL DEFAULT ''
);
-- Ce qu'elle a vu faire et propose d'écrire comme savoir-faire (trois fois le même geste).
CREATE TABLE pf_savoir_props(
  signature TEXT PRIMARY KEY, action_kind TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '',
  vu INTEGER NOT NULL DEFAULT 1, dernier TEXT NOT NULL DEFAULT (datetime('now')), etat TEXT NOT NULL DEFAULT 'propose'
);
-- L'incident : cinq anomalies, une histoire. Une cause, une chaîne, une fin prouvée.
CREATE TABLE pf_incidents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cle TEXT NOT NULL DEFAULT '',
  ouvert_le TEXT NOT NULL DEFAULT (datetime('now')), ferme_le TEXT NOT NULL DEFAULT '',
  titre TEXT NOT NULL DEFAULT '', cause TEXT NOT NULL DEFAULT '', gravite TEXT NOT NULL DEFAULT 'warning',
  statut TEXT NOT NULL DEFAULT 'ouvert', preuve TEXT NOT NULL DEFAULT '', duree_min INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX idx_pf_inc_cle ON pf_incidents(cle) WHERE statut = 'ouvert';
CREATE TABLE pf_incident_liens(
  incident_id INTEGER NOT NULL, fkey TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'effet',
  ts TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY (incident_id, fkey)
);
