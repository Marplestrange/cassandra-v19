<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : La console d'un module -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : La console d'un module : ce que montre l'écran par défaut de tout module et comment il se comporte -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=0afffe ▼▼▼ -->
# La console d'un module

Fichier : `interface/CN_console-module.js` (`CASS.console(mid, hote)`). Tout module qui n'a pas d'écran sur mesure la reçoit d'office ; elle est tirée de ce qu'il déclare, jamais écrite à la main. Un module avec son écran (DNS, Évolution) peut aussi l'ouvrir (bouton « Console du module »).

- **En-tête** : nom, version, état, famille, confiance, description, auteur, licence, API ; les modules dont il dépend et ceux qui l'utilisent (cliquables) ; Activer / Désactiver (avec confirmation) quand l'instance gère les modules et que le module n'est pas essentiel.
- **Aperçu** : ce que le module compte (lectures, gestes, réglages, détecteurs, moteurs, objets, écrans, points d'évolution), ses gestes qui comptent (risque moyen ou élevé), et ce qu'il peut faire hors de lui (réseau, écritures, privilèges).
- **Lectures** : une carte par lecture, ses paramètres, un résultat lisible (grille clé-valeur, tableau triable en cliquant l'en-tête, ou JSON) avec sa durée et un bouton Copier ; un filtre au-delà de six lectures ; les deux premières lectures sans paramètre se lisent d'elles-mêmes.
- **Gestes** : le risque en couleur, le droit exigé, la portée, la preuve et le retour dits avant le geste ; un geste de risque moyen ou élevé demande une confirmation (second clic).
- **Réglages** : ceux du module (`reglages.lire` filtré par module), leur état (défaut ou posé), la remise à zéro (↺) et l'historique des changements (`reglages.historique`) ; chaque champ s'enregistre en le quittant.
- **Évolution** : les points d'évolution du module (`evolution.etat`), s'il en a.

Test : `tests-ui/console.spec.js` (module simulé : la console ne lance jamais un geste qui compte sans confirmation).

<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : la description de la console -->
<!-- EC : néant (aucun point d'évolution) -->
<!-- LIEN : interface/CN_console-module.js (la console), tests-ui/console.spec.js (le test) -->
