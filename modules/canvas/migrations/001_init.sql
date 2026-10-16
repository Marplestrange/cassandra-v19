-- Le plan d'une note : les cartes et les flèches, en JSON, à côté de la note.
CREATE TABLE cv_plans(
  ref TEXT PRIMARY KEY, plan TEXT NOT NULL DEFAULT '{"nodes":[],"edges":[]}',
  maj TEXT NOT NULL DEFAULT (datetime('now'))
);
