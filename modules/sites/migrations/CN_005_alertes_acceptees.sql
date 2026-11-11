-- « Je sais, c'est normal » : une alerte de Sites acceptée se tait jusqu'à son échéance, et revient d'elle-même si son chiffre empire
-- (un certificat accepté à douze jours revient à onze). La clé dit l'alerte : « certificat:<site> », « nom:<zone> », « sauvegarde:<site> », « php:<site> ».
-- Les alertes du Sensorium ont leur propre acceptation, chez lui : celle-ci ne vaut que pour ce que Sites signale lui-même.
CREATE TABLE alertes_acceptees(
  cle TEXT PRIMARY KEY, domaine TEXT NOT NULL, titre TEXT NOT NULL DEFAULT '', jusqu_a REAL NOT NULL, valeur REAL, par TEXT NOT NULL DEFAULT '', ts REAL NOT NULL
);
