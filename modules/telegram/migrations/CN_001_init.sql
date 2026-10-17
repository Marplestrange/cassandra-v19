-- Le robot Telegram de chaque compte : il porte les notifications de CE compte vers SON téléphone, et ne lit rien de ce qu'on lui écrit.
-- Le jeton du robot est gardé tel quel (le coffre chiffré n'est pas encore porté) : le fichier de ce module est protégé comme les autres données du noyau.
CREATE TABLE liens(
  compte TEXT PRIMARY KEY, jeton TEXT NOT NULL, nom_robot TEXT NOT NULL DEFAULT '',
  secret_empreinte TEXT NOT NULL,                       -- sha256 du secret du webhook : le compte visé se retrouve par ce seul secret
  chat_id TEXT NOT NULL DEFAULT '',                     -- appris du premier message (« /start »)
  cible TEXT NOT NULL DEFAULT '',                       -- DÉCLARÉ par la personne, essayé pour de bon ; l'emporte sur chat_id
  actif INTEGER NOT NULL DEFAULT 1, cree REAL NOT NULL, dernier REAL
);
CREATE UNIQUE INDEX liens_secret ON liens(secret_empreinte);
CREATE TABLE messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, chat_id TEXT NOT NULL, sens TEXT NOT NULL,   -- recu | envoye
  corps TEXT NOT NULL DEFAULT '', expediteur TEXT NOT NULL DEFAULT '', message_id TEXT NOT NULL DEFAULT '', ts REAL NOT NULL
);
CREATE INDEX messages_compte ON messages(compte, id DESC);
