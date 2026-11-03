-- Les messages en cours de rédaction et ceux qui attendent leur heure. Un message est à une personne (le compte) : personne d'autre ne le voit.
-- États : brouillon -> programme (part seul à l'heure dite) -> envoi (le courrier le poste) -> envoye | echec.
CREATE TABLE messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL,
  a TEXT NOT NULL DEFAULT '', cc TEXT NOT NULL DEFAULT '', cci TEXT NOT NULL DEFAULT '',
  objet TEXT NOT NULL DEFAULT '', corps TEXT NOT NULL DEFAULT '', pieces TEXT NOT NULL DEFAULT '[]', liens TEXT NOT NULL DEFAULT '[]',
  suivi_jours INTEGER NOT NULL DEFAULT 0, reponse_a TEXT NOT NULL DEFAULT '', references_fil TEXT NOT NULL DEFAULT '', teinte TEXT NOT NULL DEFAULT '',
  etat TEXT NOT NULL DEFAULT 'brouillon', quand REAL, cree REAL NOT NULL, maj REAL NOT NULL,
  envoye_le REAL, message_id TEXT NOT NULL DEFAULT '', erreur TEXT NOT NULL DEFAULT ''
);
CREATE INDEX ix_messages_compte ON messages(compte, etat);
CREATE INDEX ix_messages_quand ON messages(etat, quand);
