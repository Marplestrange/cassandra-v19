-- Le cycle de vie : ce que la veille ne savait pas dire (qui, pourquoi, quelle source), les demandes et le journal d'audit.
-- Les échecs d'émission s'inscrivent aussi (ok=0, avec leur motif) : Let's Encrypt limite aussi les validations ratées.
ALTER TABLE emissions ADD COLUMN motif TEXT NOT NULL DEFAULT '';
-- Ce qu'on sait d'un hôte au-delà de ce que dit le certificat servi : sa source, son propriétaire, un état posé à la main (révoqué, archivé).
CREATE TABLE cert_meta(
  hote TEXT PRIMARY KEY, source TEXT NOT NULL DEFAULT '', etat_force TEXT NOT NULL DEFAULT '', auto INTEGER NOT NULL DEFAULT 0,
  site TEXT NOT NULL DEFAULT '', proprietaire TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '', maj REAL NOT NULL DEFAULT 0
);
-- Une demande de certificat : brouillon -> a_valider -> validee -> emise ; refusee ; echec.
CREATE TABLE demande(
  id INTEGER PRIMARY KEY AUTOINCREMENT, hote TEXT NOT NULL, sans TEXT NOT NULL DEFAULT '', modele TEXT NOT NULL, site TEXT NOT NULL DEFAULT '',
  demandeur TEXT NOT NULL DEFAULT '', etat TEXT NOT NULL, valideur TEXT NOT NULL DEFAULT '', motif TEXT NOT NULL DEFAULT '',
  justification TEXT NOT NULL DEFAULT '', cree REAL NOT NULL, maj REAL NOT NULL
);
CREATE INDEX demande_etat ON demande(etat);
-- Le journal d'audit : écriture seule (jamais de UPDATE ni de DELETE), refus de permission compris.
CREATE TABLE audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL NOT NULL, acteur TEXT NOT NULL DEFAULT '', type_acteur TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL, objet TEXT NOT NULL DEFAULT '', resultat TEXT NOT NULL DEFAULT 'ok', note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX audit_ts ON audit(ts);
