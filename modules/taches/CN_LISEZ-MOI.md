<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Tâches -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : taches -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Tâches -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=53631b ▼▼▼ -->
# Tâches

Les tâches d'un compte : statut, échéance, priorité, sous-tâches, récurrence, avancement, responsable (soi, un membre du projet, ou Itare), liens, journal, provenance.

- Elles appartiennent à la personne : supprimer un projet ne les emporte pas.
- Dans un projet, il faut y pouvoir écrire (rôle auteur ou plus) ; les rôles sont lus via `projets.equipe`. Sans le module projets, seules les tâches personnelles existent.
- Terminer une tâche récurrente crée la suivante, à partir de l'échéance précédente (pas d'aujourd'hui) ; le retour retire cette occurrence.
- Abandonner exige une raison ; repousser une échéance compte un report.
- Une tâche née d'une détection (`source` + `origine`) ne se crée qu'une fois.
- Confier à Itare émet `tache.confiee`.
- Détecteur `en_retard` : un constat par compte.

## Non porté
Création automatique depuis un constat (selon palier), rappels, vue calendrier.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
