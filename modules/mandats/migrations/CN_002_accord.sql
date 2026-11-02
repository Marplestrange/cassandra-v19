-- La file d'accord : à qui appartient un envoi (son serveur d'envoi, ses droits), d'où vient la pièce (la source du carnet de fichiers), et l'état « autorise » (accord donné, courrier en train de poster).
ALTER TABLE mandat_envois ADD COLUMN compte TEXT NOT NULL DEFAULT '';
ALTER TABLE mandat_envois ADD COLUMN pj_source TEXT NOT NULL DEFAULT '';
DROP INDEX idx_md_cle;
CREATE UNIQUE INDEX idx_md_cle ON mandat_envois(cle) WHERE cle <> '' AND etat IN ('envoye','attente','differe','autorise');
