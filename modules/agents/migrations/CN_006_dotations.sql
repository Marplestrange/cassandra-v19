-- Les familles prêtées : l'administrateur confie à un agent les outils d'un module, d'une tuile du menu ou de la famille d'un autre agent.
-- Un outil du module dont l'agent est propriétaire (manifeste) ne passe jamais par cette table : il est à lui, quoi qu'il arrive. Ici ne vit que ce qui est prêté, et qui se reprend.
CREATE TABLE agent_dotations(
  agent TEXT NOT NULL,                                                          -- l'agent doté : cassandra | itare
  portee TEXT NOT NULL,                                                         -- module | tuile | agent (la famille d'un autre agent, à mesure que ses modules s'ajoutent)
  cible TEXT NOT NULL,                                                          -- l'identifiant du module, de la tuile (desk, parc…) ou de l'agent propriétaire
  par TEXT NOT NULL DEFAULT '',                                                 -- le compte qui l'a confiée
  le REAL NOT NULL,
  PRIMARY KEY (agent, portee, cible)
);
