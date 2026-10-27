-- Les espaces du coffre : chacun voit les siens, jamais ceux des autres.
-- Un espace personnel (« u:<compte> ») existe sans ligne ; un espace de société (« s:<société> ») a ses membres.
ALTER TABLE vault_audit ADD COLUMN espace TEXT NOT NULL DEFAULT '';
CREATE TABLE vault_espaces(
  id TEXT PRIMARY KEY, genre TEXT NOT NULL, nom TEXT NOT NULL DEFAULT '',
  mode TEXT NOT NULL DEFAULT 'interne', url TEXT NOT NULL DEFAULT '',
  archive INTEGER NOT NULL DEFAULT 0, cree TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Qui a accès à quel espace, avec quel rôle (admin | membre | contrib | lecture), à quelles collections ('*' = toutes, '' = aucune), jusqu'à quand ('' = sans fin).
CREATE TABLE vault_membres(
  espace TEXT NOT NULL, compte TEXT NOT NULL, role TEXT NOT NULL, collections TEXT NOT NULL DEFAULT '*',
  expire TEXT NOT NULL DEFAULT '', accorde_par TEXT NOT NULL DEFAULT '', cree TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(espace, compte)
);
-- Ce qu'on sait de chaque secret SANS sa valeur : à qui il appartient, dans quelle collection. C'est ce qui permet le rôle « contributeur ».
CREATE TABLE vault_secrets(
  espace TEXT NOT NULL, nom TEXT NOT NULL, auteur TEXT NOT NULL DEFAULT '', collection TEXT NOT NULL DEFAULT '',
  cree TEXT NOT NULL DEFAULT (datetime('now')), maj TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY(espace, nom)
);
CREATE INDEX ix_vault_membres_compte ON vault_membres(compte);
