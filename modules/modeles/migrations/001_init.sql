-- Un modèle se déclare UNE fois ; les rôles et les comptes y puisent. La clé est chiffrée (AES-256-GCM, étiquette « modele:<id> » liée au chiffré) et ne sort JAMAIS du module :
-- ni liste, ni journal, ni réponse. Les appels passent par `completer`.
CREATE TABLE modeles(
  id TEXT PRIMARY KEY, fournisseur TEXT NOT NULL, nom TEXT NOT NULL, base_url TEXT NOT NULL DEFAULT '',
  cle TEXT NOT NULL DEFAULT '',                 -- chiffrée ; vide = sans clé (serveur local ou ouvert)
  portee TEXT NOT NULL DEFAULT 'compte',        -- 'instance' (posé par un administrateur, sert les rôles) | 'compte' (le sien, avec sa propre clé)
  compte TEXT NOT NULL DEFAULT '', ajoute_par TEXT NOT NULL DEFAULT '', cree REAL NOT NULL,
  essai_ts REAL, essai_ok INTEGER, essai_s REAL, essai_msg TEXT NOT NULL DEFAULT ''
);
CREATE INDEX modeles_compte ON modeles(compte);
CREATE TABLE roles(role TEXT PRIMARY KEY, modele_id TEXT NOT NULL);
CREATE TABLE choix(compte TEXT PRIMARY KEY, modele_id TEXT NOT NULL);       -- le modèle que CE compte a choisi parmi les siens
CREATE TABLE usage(jour TEXT NOT NULL, role TEXT NOT NULL DEFAULT '', modele_id TEXT NOT NULL, appels INTEGER NOT NULL DEFAULT 0, echecs INTEGER NOT NULL DEFAULT 0,
                   entrees INTEGER NOT NULL DEFAULT 0, sorties INTEGER NOT NULL DEFAULT 0, secondes REAL NOT NULL DEFAULT 0, PRIMARY KEY(jour, role, modele_id));
CREATE TABLE pulls(id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL, etat TEXT NOT NULL DEFAULT 'attente', detail TEXT NOT NULL DEFAULT '', pourcent INTEGER NOT NULL DEFAULT 0, demande_par TEXT NOT NULL DEFAULT '', ts REAL NOT NULL);
