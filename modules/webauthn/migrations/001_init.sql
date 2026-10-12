-- Les clés de sécurité (WebAuthn) des comptes. La clé PUBLIQUE est gardée (COSE en JSON, les octets en base64url) ; elle ne sort jamais vers le navigateur.
CREATE TABLE cles(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, cred_id TEXT NOT NULL UNIQUE, cose TEXT NOT NULL,
  compteur INTEGER NOT NULL DEFAULT 0, libelle TEXT NOT NULL DEFAULT '', cree REAL NOT NULL, dernier REAL
);
CREATE INDEX cles_compte ON cles(compte);
-- Les codes de secours : seule l'empreinte salée est gardée, un code ne sert qu'une fois.
CREATE TABLE secours(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, empreinte TEXT NOT NULL, utilise REAL
);
CREATE INDEX secours_compte ON secours(compte);
-- La clé est-elle EXIGÉE pour entrer ? Enregistrer une clé n'exige rien : il faut pouvoir l'éprouver avant qu'elle devienne la condition d'entrée.
CREATE TABLE exigences(compte TEXT PRIMARY KEY, exigee INTEGER NOT NULL DEFAULT 0);
