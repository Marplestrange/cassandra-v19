<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : La page des modules -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : La page des modules : cartes, tiroir de détail, importance déclarée et changements d'activation mis en attente avec leur impact -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=fab17a ▼▼▼ -->
# La page « Modules et applications »

Fichier : `interface/CN_modules-page.js` (`CASS.pageModules(el, famille, ctx)`), appelé par la page de `disposition.js` ; la maquette validée est `brouillons/maquette-modules.html`.

- **Importance déclarée par chaque module** : dans son manifeste, `[module] importance = "vital" | "important" | "optionnel"` et `sans = "une phrase"` (ce qui s'arrête quand il est désactivé, 300 caractères au plus). Un module essentiel est vital (le validateur le refuse sinon). `tests/CN_test_importance.py` exige les deux champs de tous les modules livrés. Le catalogue (`modules.lister`) et la fiche (`modules.fiche`) les rendent.
- **Une carte par module** : état, importance (pastille Vital / Important / Optionnel), interrupteur, engrenage vers l'onglet Réglages de sa console (grisé tant que le module est inactif). Filtres par état, par importance, recherche.
- **Instance de développement** : quand la gestion des modules est absente (`gere = false`), tout est chargé d'office ; la page l'affiche en une note et grise les interrupteurs ; réglages et consoles restent accessibles.
- **Tiroir de détail** : ce qui s'arrête sans lui (la phrase déclarée, plus les modules actifs qui s'appuient sur lui), ce qu'il compte, ses dépendances dans les deux sens (cliquables), ce qu'il peut faire hors de lui.
- **Changements en attente** : un interrupteur ne fait rien tout de suite ; il met le changement dans un plateau. « Voir l'impact » dit ce qui sera activé (demandé, ou tiré par une dépendance) et désactivé, signale un module déclaré vital, et bloque ce qui casserait un module actif (« Désactiver aussi ces modules » propose la cascade). « Appliquer » désactive d'abord (les dépendants avant leurs dépendances), puis active (`modules.activer` tire les dépendances).

Test : `tests-ui/modules.spec.js` (catalogue simulé : note de développement, blocage, cascade, ordre d'application, rien ne part avant l'accord).

<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : la description de la page -->
<!-- EC : néant (aucun point d'évolution) -->
<!-- LIEN : interface/CN_modules-page.js (la page), noyau/CN_manifeste.py (importance, sans), tests-ui/modules.spec.js (le test) -->
