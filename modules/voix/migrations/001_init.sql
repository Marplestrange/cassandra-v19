-- Les préférences de voix, PAR COMPTE : le ton et le modèle d'Itare le sont déjà, sa voix ne fait pas exception.
CREATE TABLE voix_prefs(
  compte TEXT PRIMARY KEY, voix_nom TEXT NOT NULL DEFAULT '', voix_locuteur TEXT NOT NULL DEFAULT '',
  voix_auto INTEGER NOT NULL DEFAULT 1, voix_debit TEXT NOT NULL DEFAULT '', voix_mode INTEGER NOT NULL DEFAULT 0
);
