-- Le carnet d'adresses. Chaque fiche appartient à UN compte ; l'administrateur n'y a pas accès (administrer n'est pas voir).
CREATE TABLE contacts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL,
  display_name TEXT NOT NULL DEFAULT '', company TEXT NOT NULL DEFAULT '', job_title TEXT NOT NULL DEFAULT '',
  phone TEXT NOT NULL DEFAULT '', mobile TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', website TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '', favorite INTEGER NOT NULL DEFAULT 0, source TEXT NOT NULL DEFAULT 'manuel',
  photo TEXT NOT NULL DEFAULT '', vault_ref TEXT NOT NULL DEFAULT '', dossier_id INTEGER NOT NULL DEFAULT 0, anniversaire TEXT NOT NULL DEFAULT '',
  archive INTEGER NOT NULL DEFAULT 0,
  supprime_at REAL,                         -- à la corbeille depuis ; rien n'est effacé tant que la purge n'est pas demandée
  fusion_vers INTEGER NOT NULL DEFAULT 0,   -- absorbée par cette fiche (fusion)
  created_at REAL NOT NULL, updated_at REAL NOT NULL
);
CREATE INDEX contacts_compte ON contacts(compte);
CREATE INDEX contacts_dossier ON contacts(compte, dossier_id);
-- Une adresse appartient à UNE fiche par compte : on la refuse plutôt que de la voler en silence.
CREATE TABLE emails(
  contact_id INTEGER NOT NULL, compte TEXT NOT NULL, addr TEXT NOT NULL, is_primary INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(contact_id, addr), UNIQUE(compte, addr)
);
CREATE TABLE dossiers(
  id INTEGER PRIMARY KEY AUTOINCREMENT, compte TEXT NOT NULL, nom TEXT NOT NULL, parent_id INTEGER NOT NULL DEFAULT 0, cree REAL NOT NULL
);
CREATE INDEX dossiers_compte ON dossiers(compte);
-- Les rattachements d'une fiche à ce qu'elle concerne (projet, domaine, serveur...). `auto` : une déduction, qui ne remplace jamais un lien posé à la main.
CREATE TABLE liens(
  contact_id INTEGER NOT NULL, kind TEXT NOT NULL, ref TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'autre', label TEXT NOT NULL DEFAULT '',
  auto INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL, PRIMARY KEY(contact_id, kind, ref)
);
CREATE INDEX liens_ref ON liens(kind, ref);
-- Les paires déclarées « pas la même personne » : sans cette mémoire les faux doublons remontent chaque semaine et on cesse de regarder.
CREATE TABLE pas_doublons(compte TEXT NOT NULL, a INTEGER NOT NULL, b INTEGER NOT NULL, ts REAL NOT NULL, PRIMARY KEY(compte, a, b));
