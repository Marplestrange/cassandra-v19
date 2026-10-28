-- Les demandes de module d'une société secondaire : elle dit ce qu'il lui faut et pourquoi ; la société principale, propriétaire de l'instance, examine et installe
-- par la logithèque (examen, permissions montrées, consentement), puis attribue le module à la société demandeuse.
CREATE TABLE demandes_module(
  id INTEGER PRIMARY KEY AUTOINCREMENT, societe TEXT NOT NULL, demandeur TEXT NOT NULL DEFAULT '', ts REAL NOT NULL,
  nom TEXT NOT NULL, motif TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
  etat TEXT NOT NULL DEFAULT 'demandee', module TEXT NOT NULL DEFAULT '', decide_par TEXT NOT NULL DEFAULT '', decide_ts REAL NOT NULL DEFAULT 0, reponse TEXT NOT NULL DEFAULT ''
);
CREATE INDEX demandes_module_societe ON demandes_module(societe, etat);
