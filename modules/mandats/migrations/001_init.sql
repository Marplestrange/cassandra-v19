-- Les mandats d'envoi : l'autorisation d'envoyer, avec ses bornes.
CREATE TABLE mandats(
  id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL DEFAULT '', actif INTEGER NOT NULL DEFAULT 1,
  declencheurs TEXT NOT NULL DEFAULT 'chat',
  dst_source TEXT NOT NULL DEFAULT 'document', dst_valeur TEXT NOT NULL DEFAULT '',
  objet TEXT NOT NULL DEFAULT '', corps TEXT NOT NULL DEFAULT '',
  variables TEXT NOT NULL DEFAULT '[]', libre INTEGER NOT NULL DEFAULT 0, libre_max INTEGER NOT NULL DEFAULT 400,
  pj_dossier TEXT NOT NULL DEFAULT '', pj_motif TEXT NOT NULL DEFAULT '',
  pj_types TEXT NOT NULL DEFAULT 'pdf', pj_max INTEGER NOT NULL DEFAULT 2097152,
  pj_obligatoire INTEGER NOT NULL DEFAULT 1,
  controle TEXT NOT NULL DEFAULT 'accord', differe_min INTEGER NOT NULL DEFAULT 10,
  quota_jour INTEGER NOT NULL DEFAULT 5, dst_max INTEGER NOT NULL DEFAULT 1,
  heure_debut TEXT NOT NULL DEFAULT '08:00', heure_fin TEXT NOT NULL DEFAULT '19:00',
  unique_par TEXT NOT NULL DEFAULT '', suspendre_incident INTEGER NOT NULL DEFAULT 1,
  suspendu TEXT NOT NULL DEFAULT '', cree_le TEXT NOT NULL DEFAULT (datetime('now'))
);
-- Les envois : le journal de ce qui est parti (ou n'est pas parti), et pourquoi.
CREATE TABLE mandat_envois(
  id INTEGER PRIMARY KEY AUTOINCREMENT, mandat_id INTEGER NOT NULL,
  ts TEXT NOT NULL DEFAULT (datetime('now')), etat TEXT NOT NULL DEFAULT 'attente',
  origine TEXT NOT NULL DEFAULT '', acteur TEXT NOT NULL DEFAULT '', teinte TEXT NOT NULL DEFAULT '',
  destinataire TEXT NOT NULL DEFAULT '', contact_id TEXT NOT NULL DEFAULT '',
  objet TEXT NOT NULL DEFAULT '', corps TEXT NOT NULL DEFAULT '',
  pj_chemin TEXT NOT NULL DEFAULT '', pj_nom TEXT NOT NULL DEFAULT '',
  pj_taille INTEGER NOT NULL DEFAULT 0, pj_empreinte TEXT NOT NULL DEFAULT '',
  variables TEXT NOT NULL DEFAULT '{}', cle TEXT NOT NULL DEFAULT '',
  verdict TEXT NOT NULL DEFAULT '', motif TEXT NOT NULL DEFAULT '',
  part_a TEXT NOT NULL DEFAULT '', message_id TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_md_env ON mandat_envois(mandat_id, id DESC);
CREATE UNIQUE INDEX idx_md_cle ON mandat_envois(cle) WHERE cle <> '' AND etat IN ('envoye','attente','differe');
