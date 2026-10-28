-- Le profil d'une personne DANS une société : un utilisateur partagé entre deux sociétés signe, se présente et se joint différemment dans chacune.
CREATE TABLE profils(
  societe TEXT NOT NULL, compte TEXT NOT NULL, nom TEXT NOT NULL DEFAULT '', fonction TEXT NOT NULL DEFAULT '', tel TEXT NOT NULL DEFAULT '', email TEXT NOT NULL DEFAULT '',
  maj REAL NOT NULL DEFAULT 0, PRIMARY KEY(societe, compte)
);
