-- Les mesures de première classe : capteurs enfichables, dernière lecture et état, historique plafonné, clés suivies, visibilité, relations, compteurs d'auto-observation.
-- Instance entière (jamais par société) : l'infrastructure est de l'instance ; la visibilité décide ce qu'une société en voit.
CREATE TABLE sensorium_espaces(
  espace TEXT PRIMARY KEY, proprietaire TEXT NOT NULL, cree_le REAL NOT NULL
);
CREATE TABLE sensorium_capteurs(
  cle TEXT PRIMARY KEY, espace TEXT NOT NULL, proprietaire TEXT NOT NULL, libelle TEXT NOT NULL DEFAULT '', unite TEXT NOT NULL DEFAULT '',
  fraicheur_s INTEGER NOT NULL DEFAULT 300, alerte REAL, critique REAL, pire TEXT NOT NULL DEFAULT 'haut', confiance_min REAL NOT NULL DEFAULT 0, cree_le REAL NOT NULL
);
CREATE INDEX idx_sn_capteurs_espace ON sensorium_capteurs(espace);
CREATE TABLE sensorium_lectures(
  cle TEXT PRIMARY KEY, valeur_num REAL, valeur_txt TEXT NOT NULL DEFAULT '', gravite TEXT NOT NULL DEFAULT 'ok', observe_a REAL, recu_a REAL NOT NULL, confiance REAL NOT NULL DEFAULT 1,
  decalage_s REAL, detail TEXT NOT NULL DEFAULT '', etat TEXT NOT NULL DEFAULT 'inconnu', raison TEXT NOT NULL DEFAULT '', depuis REAL NOT NULL, annonce TEXT NOT NULL DEFAULT '', annonce_a REAL
);
CREATE TABLE sensorium_historique(
  id INTEGER PRIMARY KEY AUTOINCREMENT, cle TEXT NOT NULL, t REAL NOT NULL, valeur REAL, etat TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_sn_histo ON sensorium_historique(cle, t);
CREATE TABLE sensorium_suivies(
  cle TEXT NOT NULL, suiveur TEXT NOT NULL, motif TEXT NOT NULL DEFAULT '', cree_le REAL NOT NULL, PRIMARY KEY(cle, suiveur)
);
CREATE TABLE sensorium_visibilites(
  cle TEXT PRIMARY KEY, visibilite TEXT NOT NULL DEFAULT 'instance', libelle TEXT NOT NULL DEFAULT '', par TEXT NOT NULL DEFAULT '', maj REAL NOT NULL
);
CREATE TABLE sensorium_liens(
  de TEXT NOT NULL, relation TEXT NOT NULL, vers TEXT NOT NULL, par TEXT NOT NULL DEFAULT '', cree_le REAL NOT NULL, PRIMARY KEY(de, relation, vers)
);
CREATE INDEX idx_sn_liens_vers ON sensorium_liens(vers);
CREATE TABLE sensorium_compteurs(
  nom TEXT PRIMARY KEY, n INTEGER NOT NULL DEFAULT 0, maj REAL
);
