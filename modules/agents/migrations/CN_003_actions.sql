-- Les actions de l'équipe : propositions (« À valider »), actes tracés pour « Pourquoi ? », outils vus (période d'essai), épreuves de sûreté, sentinelle anti-fuite et relectures.
-- Rien n'est COPIÉ ici : un acte garde des RÉFÉRENCES (événement du journal du noyau, conversation, souvenirs [M:id]) que « Pourquoi ? » relit à la demande.
CREATE TABLE propositions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, compte TEXT NOT NULL,         -- compte : celui au nom duquel l'agent travaillait
  capacite TEXT NOT NULL, args TEXT NOT NULL DEFAULT '{}',                                  -- arguments MASQUÉS pour les secrets (« *** ») : une proposition à argument secret n'est jamais exécutable
  empreinte TEXT NOT NULL DEFAULT '',                                                       -- agent + compte + capacité + arguments : une même demande ne se propose pas deux fois
  titre TEXT NOT NULL DEFAULT '', resume TEXT NOT NULL DEFAULT '', risque TEXT NOT NULL DEFAULT '', pourquoi TEXT NOT NULL DEFAULT '', impact TEXT NOT NULL DEFAULT '',
  origine TEXT NOT NULL DEFAULT '',                                                         -- confirmer | racontee | retenue
  etat TEXT NOT NULL DEFAULT 'attend',                                                      -- attend | acceptee | refusee | reportee | perimee
  cree REAL NOT NULL, decidee REAL NOT NULL DEFAULT 0, par TEXT NOT NULL DEFAULT '', reporte_jusqua REAL NOT NULL DEFAULT 0,
  conversation_id INTEGER NOT NULL DEFAULT 0, tour INTEGER NOT NULL DEFAULT 0, attente INTEGER NOT NULL DEFAULT 0,
  mandat_id INTEGER NOT NULL DEFAULT 0, mandat TEXT NOT NULL DEFAULT '{}',                  -- le mandat d'envoi (de, à, objet, validité) : jamais une adresse tirée de la demande
  blocage TEXT NOT NULL DEFAULT '', resultat TEXT NOT NULL DEFAULT '', acte INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX propositions_compte ON propositions(compte, etat);
CREATE INDEX propositions_empreinte ON propositions(empreinte, etat);
CREATE TABLE agent_actes(                                                                   -- un acte d'agent, vu du côté de la conversation
  evenement INTEGER PRIMARY KEY, compte TEXT NOT NULL, agent TEXT NOT NULL, capacite TEXT NOT NULL,
  conversation_id INTEGER NOT NULL DEFAULT 0, tour INTEGER NOT NULL DEFAULT 0, declencheur TEXT NOT NULL DEFAULT '',   -- tour | proposition
  memoires TEXT NOT NULL DEFAULT '[]', palier TEXT NOT NULL DEFAULT '', niveau TEXT NOT NULL DEFAULT '', confirmer INTEGER NOT NULL DEFAULT 0,
  proposition_id INTEGER NOT NULL DEFAULT 0, ts REAL NOT NULL
);
CREATE INDEX agent_actes_compte ON agent_actes(compte, ts);
CREATE TABLE agent_outils_vus(                                                              -- période d'essai : un outil neuf reste raconté 7 jours avant qu'on propose « auto »
  agent TEXT NOT NULL, compte TEXT NOT NULL DEFAULT '', outil TEXT NOT NULL, vu_le REAL NOT NULL,
  PRIMARY KEY(agent, compte, outil)
);
CREATE TABLE epreuves_runs(
  id INTEGER PRIMARY KEY AUTOINCREMENT, modele TEXT NOT NULL, ts REAL NOT NULL, par TEXT NOT NULL DEFAULT '',
  reussies INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0, ok INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE epreuves_cas(
  run_id INTEGER NOT NULL, cas TEXT NOT NULL, reussi INTEGER NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT '',
  PRIMARY KEY(run_id, cas)
);
CREATE INDEX epreuves_runs_modele ON epreuves_runs(modele, id);
CREATE TABLE sentinelle(                                                                    -- les secrets connus : leur EMPREINTE (HMAC) seulement, jamais la valeur
  etiquette TEXT PRIMARY KEY, empreinte TEXT NOT NULL, longueur INTEGER NOT NULL, ajoutee REAL NOT NULL
);
CREATE TABLE sentinelle_cle(id INTEGER PRIMARY KEY CHECK(id = 1), cle TEXT NOT NULL);       -- la clé du HMAC (propre à l'instance, tirée au premier usage)
CREATE TABLE relectures(                                                                    -- ce que le Relecteur a retenu : les MOTIFS seulement, jamais le texte
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, compte TEXT NOT NULL, conversation_id INTEGER NOT NULL DEFAULT 0, tour INTEGER NOT NULL DEFAULT 0,
  verdict TEXT NOT NULL, motifs TEXT NOT NULL DEFAULT '[]', ts REAL NOT NULL
);
