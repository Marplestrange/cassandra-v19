-- L'aperçu d'un site : ce que sa page d'accueil dit d'elle (titre, description, générateur, langue), son icône et, si elle en déclare une sur son propre nom,
-- son image de présentation. Les images sont gardées en « data: » : l'interface n'affiche aucune image venue d'ailleurs. Relu une fois par jour et par site.
CREATE TABLE apercus(
  domaine TEXT PRIMARY KEY, ts REAL NOT NULL, titre TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', generateur TEXT NOT NULL DEFAULT '',
  langue TEXT NOT NULL DEFAULT '', icone TEXT NOT NULL DEFAULT '', image TEXT NOT NULL DEFAULT '', erreur TEXT NOT NULL DEFAULT ''
);
