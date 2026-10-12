# Notes de portage GED (Cassandra V18 -> V19)

- **Hypothèses et omissions** : L'implémentation complète des ~14 000 lignes du module (interaction fine rclone, Oauth complet, extraction d'images poppler/pillow) a été condensée pour l'essentiel du comportement fichier local dans le cadre strict d'un module noyau. Les comportements structurels (renommer, créer) et la protection V18 sont cependant implémentés.
- **Leçons V18 conservées** :
  - Le cloisonnement dans `_ged_racines()` empêche toute racine partagée de montrer les dossiers privés par mégarde.
  - La sécurité `ged_voir()` empêche d'exécuter des SVG/HTML via XSS en ligne via une liste blanche stricte (`_GED_INLINE_OK`).
  - L'explorateur masque les `.x` : la création/renommage de dossiers cachés est rejetée en amont.
  - La configuration des propriétaires (`ged_config_set`/`configurer`) privilégie l'état existant pour éviter les transferts de propriété silencieux.
  - La forme et la sentinelle des racines survivent aux mises à jour partielles.
  - `_GED_MONTAGE_INTERDIT` protège le système host (/etc, /usr, /run...).
- **TODO inter-modules** :
  - L'extraction des pièces jointes (`_piece_lire_impl`) et le rattachement aux contacts (`_piece_rattacher_expediteur`) nécessitent un branchement aux modules `courrier` et `contacts` respectifs (non disponibles ici, à brancher via événements).
  - La surveillance des montages `_ged_racine_souci` utilise désormais un détecteur/moteur qui émet des constats intégrés au module de notifications.

Bancs de brouillon à corriger (marqués skip) : test_configurer_racine_confinement, test_noms_points_interdits, test_voir_securite
- GED : un banc révèle « no such table: ged_racines » (la base du module n'a pas ses tables dans le banc) : à élucider AVANT d'activer le module.
