-- Les réglages du Centre : ce que chaque personne a choisi pour elle (heures calmes, fuseau), les sourdines datées, la politique de canaux par gravité (la machine « * », puis la personne),
-- l'essai de chaque canal, et le webhook de la machine (son adresse est un secret : elle est chiffrée, jamais écrite en clair).
CREATE TABLE notif_prefs(
  compte TEXT PRIMARY KEY, fuseau TEXT NOT NULL DEFAULT '', calme_debut TEXT NOT NULL DEFAULT '22:00', calme_fin TEXT NOT NULL DEFAULT '08:00', calmes INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE notif_sourdines(
  compte TEXT NOT NULL, portee TEXT NOT NULL, cible TEXT NOT NULL, fin REAL NOT NULL,
  PRIMARY KEY(compte, portee, cible)
);
CREATE TABLE notif_politique(
  compte TEXT NOT NULL, niveau TEXT NOT NULL, canaux TEXT NOT NULL DEFAULT '["cloche"]',
  PRIMARY KEY(compte, niveau)
);
CREATE TABLE notif_essais(
  canal TEXT PRIMARY KEY, ts REAL NOT NULL, ok INTEGER NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT ''
);
CREATE TABLE notif_webhook(
  id INTEGER PRIMARY KEY CHECK (id = 1), actif INTEGER NOT NULL DEFAULT 0, url_chiffree TEXT NOT NULL DEFAULT '', modele TEXT NOT NULL DEFAULT ''
);
