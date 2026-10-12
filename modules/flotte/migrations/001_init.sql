-- Le registre des machines que l'administrateur déclare (SSH, ping, autre Cassandra). Les secrets (clé, mot de passe, jeton) sont chiffrés, jamais lus en clair par une lecture.
CREATE TABLE machines(
  nom TEXT PRIMARY KEY, type TEXT NOT NULL, actif INTEGER NOT NULL DEFAULT 1, hote TEXT NOT NULL DEFAULT '', port INTEGER NOT NULL DEFAULT 22,
  utilisateur TEXT NOT NULL DEFAULT 'root', auth TEXT NOT NULL DEFAULT 'tailscale', systeme TEXT NOT NULL DEFAULT '', url TEXT NOT NULL DEFAULT '',
  secrets TEXT NOT NULL DEFAULT '', cree REAL NOT NULL
);
-- L'engagement par machine, lu par tous : un statut (attendue, intermittente, retiree) et un niveau de contrôle déclaré.
CREATE TABLE engagements(nom TEXT PRIMARY KEY, statut TEXT NOT NULL DEFAULT 'attendue', niveau TEXT NOT NULL DEFAULT '');
-- Une ligne par machine et par passe : de quoi tracer la disponibilité. Une mesure absente est NULL, jamais zéro.
CREATE TABLE mesures(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, nom TEXT NOT NULL, type TEXT NOT NULL DEFAULT '', en_ligne INTEGER NOT NULL,
  cpu REAL, ram REAL, disque REAL, sante REAL, erreur TEXT NOT NULL DEFAULT ''
);
CREATE INDEX mesures_ts ON mesures(ts);
CREATE INDEX mesures_nom ON mesures(nom, ts);
-- Ce qui s'est passé : pertes, retours, découvertes, disparitions, contrôle obtenu ou perdu, actions, oublis.
CREATE TABLE evenements(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, nom TEXT NOT NULL, genre TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '', duree_min INTEGER);
CREATE INDEX evenements_ts ON evenements(ts);
-- Le dernier état vu, et depuis quand.
CREATE TABLE vus(nom TEXT PRIMARY KEY, en_ligne INTEGER NOT NULL, depuis TEXT NOT NULL, ts TEXT NOT NULL);
CREATE TABLE liens(id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL, genre TEXT NOT NULL, ref TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', ts TEXT NOT NULL, UNIQUE(nom, genre, ref));
-- Le dernier résultat de la sonde SSH sans clé (Tailscale SSH).
CREATE TABLE sonde_ssh(nom TEXT PRIMARY KEY, ok INTEGER NOT NULL, utilisateur TEXT NOT NULL DEFAULT '', ip TEXT NOT NULL DEFAULT '', detail TEXT NOT NULL DEFAULT '', ts TEXT NOT NULL);
-- Les relevés détaillés d'une machine (disques, mémoire, charge, redémarrage requis, services en échec…), datés.
CREATE TABLE releves(nom TEXT NOT NULL, cle TEXT NOT NULL, valeur TEXT NOT NULL, gravite TEXT NOT NULL DEFAULT 'info', ts TEXT NOT NULL, PRIMARY KEY(nom, cle));
