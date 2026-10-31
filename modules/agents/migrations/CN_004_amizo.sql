-- Amizo, la connaissance : les passations (Itare ou Cassandra lui passent la main, jamais l'inverse). La demande est une question autonome, sans donnée personnelle.
CREATE TABLE passations(
  id INTEGER PRIMARY KEY AUTOINCREMENT, de TEXT NOT NULL, vers TEXT NOT NULL DEFAULT 'amizo', compte TEXT NOT NULL,   -- compte : celui chez qui la réponse sera déposée
  demande TEXT NOT NULL, pourquoi TEXT NOT NULL DEFAULT '', etat TEXT NOT NULL DEFAULT 'attend',                      -- attend | en_cours | repondue | echec
  cree REAL NOT NULL, traitee REAL, reponse_msg INTEGER, conversation_id INTEGER
);
CREATE INDEX passations_etat ON passations(etat, id);
CREATE INDEX passations_compte ON passations(compte, etat);
