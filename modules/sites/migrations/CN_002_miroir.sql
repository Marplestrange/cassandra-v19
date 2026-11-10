-- Le miroir : ce que la sonde (qui tourne sans compte) a lu des comptes et du panneau, gardé pour les comptes ordinaires.
-- Un compte ordinaire n'a ni « comptes.gerer » ni « fastpanel.voir » : sans ce miroir il ne verrait ni les sites de sa fiche ni ceux du panneau,
-- et rien ne l'empêcherait de déclarer le site d'un autre. Le miroir ne garde que le nécessaire : compte, sites, compte du panneau ; domaine, propriétaire, certificat, PHP.
CREATE TABLE miroir(cle TEXT PRIMARY KEY, ts REAL NOT NULL, contenu TEXT NOT NULL);
-- Les liens d'un site retiré ou transféré : mis de côté (jamais montrés au nouveau propriétaire), remis si le geste est défait, purgés après trente jours.
CREATE TABLE liens_retires(
  lot REAL NOT NULL, domaine TEXT NOT NULL, genre TEXT NOT NULL, ref TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', ts REAL NOT NULL
);
CREATE INDEX liens_retires_lot ON liens_retires(domaine, lot);
