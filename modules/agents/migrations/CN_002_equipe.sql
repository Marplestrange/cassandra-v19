-- L'équipe d'agents : la définition (données, pas code), la configuration de chacun, ses paliers par outil, ses coûts par jour et les plafonds.
-- Un agent « d'instance » (Cassandra, Amizo, les services) a compte = '' ; Itare a une ligne PAR COMPTE (le bureau de chacun), plus la ligne d'instance (compte = '') qui sert de repli.
CREATE TABLE agents_def(
  id TEXT PRIMARY KEY, genre TEXT NOT NULL DEFAULT 'agent',                    -- agent | service
  nom TEXT NOT NULL, role TEXT NOT NULL DEFAULT '', portee TEXT NOT NULL DEFAULT 'instance',   -- instance | compte
  acteur_outils TEXT NOT NULL DEFAULT '',                                      -- l'acteur dont il emprunte les outils (cassandra | itare) ; vide : aucun outil
  niveau_defaut TEXT NOT NULL DEFAULT 'observer', modele_defaut TEXT NOT NULL DEFAULT '', ordre INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE agent_config(
  agent TEXT NOT NULL, compte TEXT NOT NULL DEFAULT '',
  nom_affiche TEXT, ton TEXT, modele TEXT, secours TEXT, niveau TEXT,           -- NULL : on hérite (ligne d'instance, puis définition)
  limites TEXT NOT NULL DEFAULT '{}', maj REAL NOT NULL,                        -- limites : JSON (max_tours, max_jetons, taille_fil, tarif_entree_cts, tarif_sortie_cts)
  PRIMARY KEY(agent, compte)
);
CREATE TABLE agent_paliers(
  agent TEXT NOT NULL, compte TEXT NOT NULL DEFAULT '', outil TEXT NOT NULL,   -- outil : « module.capacité »
  palier TEXT NOT NULL DEFAULT 'auto',                                         -- auto | raconter | retire  (« demander » n'est pas un palier : c'est `confirmer` posé sur auto)
  confirmer INTEGER NOT NULL DEFAULT 0, maj REAL NOT NULL,
  PRIMARY KEY(agent, compte, outil)
);
CREATE TABLE agent_couts(
  jour TEXT NOT NULL, agent TEXT NOT NULL, compte TEXT NOT NULL DEFAULT '',
  appels INTEGER NOT NULL DEFAULT 0, entrees INTEGER NOT NULL DEFAULT 0, sorties INTEGER NOT NULL DEFAULT 0, centimes REAL NOT NULL DEFAULT 0,
  PRIMARY KEY(jour, agent, compte)
);
CREATE TABLE agent_plafonds(
  portee TEXT PRIMARY KEY,                                                     -- 'global' ou l'identifiant d'un agent
  centimes INTEGER NOT NULL, action TEXT NOT NULL DEFAULT 'secours',          -- secours | arret | accord
  accord_jour TEXT NOT NULL DEFAULT '', maj REAL NOT NULL                      -- accord_jour : le jour où l'accord a été donné (une action « accord » laisse passer ce jour-là)
);
CREATE TABLE agent_attentes(                                                  -- ce qu'un agent retient et attend qu'on décide (lu par les propositions du lot suivant)
  id INTEGER PRIMARY KEY AUTOINCREMENT, agent TEXT NOT NULL, compte TEXT NOT NULL, genre TEXT NOT NULL,   -- genre : confirmer | plafond
  outil TEXT NOT NULL DEFAULT '', args TEXT NOT NULL DEFAULT '{}', ts REAL NOT NULL, etat TEXT NOT NULL DEFAULT 'attente'
);
CREATE INDEX agent_attentes_compte ON agent_attentes(compte, etat);
