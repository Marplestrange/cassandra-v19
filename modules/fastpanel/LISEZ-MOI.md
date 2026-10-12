# fastpanel — le pont vers FastPanel

Porté de la V18 (`hebergement` : `get_fp_*`, `fp_api_*`, `fp_*_watch`/`_audit`), lu en entier, avec ses leçons.

## Ce que fait le module
- **Lit** le parc dans la base SQLite du panneau, ouverte en lecture seule : comptes, sites (avec l'état du certificat en quatre états), bases, FTP, courrier, DNS, copies de sauvegarde.
- **Lit par l'API** : services, plans et stockages de sauvegarde.
- **Agit par l'API**, avec preuve et retour : relancer/arrêter un service, renouveler un certificat, créer une base, déclarer un stockage local, créer un plan.
- **Surveille** (une relève chaque minute, les audits chaque quart d'heure) : panneau injoignable ou refus d'accès, service actif tombé sans action de Cassandra, certificat échu ou proche, sauvegarde absente ou périmée, PHP en fin de support.

## Réglages
`url` (vide : le panneau local, 8888), `utilisateur`, `mot_de_passe` (secret), `jeton` (secret, remplace le compte), `base_panneau`, `delai`, `sauvegarde_age_max_j`, `ssl_alerte_j`.

## Droits
`fastpanel.voir` pour les lectures, `fastpanel.piloter` pour les actions (les deux sensibles). Aucun interdit codé : l'arrêt d'un service est de risque élevé, plafonné au palier « auto », réservé à l'humain et à Cassandra ; le plafond réel est le choix de l'administrateur.

## Non porté (volontairement ou pas encore)
- **Suppression d'une base** : sans retour arrière sûr. À faire avec un dump vérifié et une restauration (comme la corbeille de Dolibarr), pas avant.
- **Restauration d'une copie** (`fp_backup_restaurer`) : elle écrase des sites ; à porter avec sa preuve.
- **Activer/désactiver un service** : le champ « activé » de l'API n'est pas prouvé ; sans preuve, pas d'acte.
- **Crons du panneau, utilisateurs SSH, avatars, scans (`fp_scan_*`), santé SSL par sonde en cache, statistiques CPU/mémoire/disque** : les statistiques machine relèvent du module `sensorium`. Les scans et les crons sont à porter.
- **Cloisonnement par compte** (un compte ordinaire ne voit que ses sites : `fp_comptes_sites`, `set_user_fp_account`) : arrive avec le module `sites`, qui sait rattacher un compte à ses sites.
- **Rattachement d'un domaine à un projet** (`fp_domain_attach`) : relève du module des projets.
- **Retour du plan de sauvegarde** (`DELETE /api/v2/backup/plans/{id}`) : le point d'entrée n'a pas été éprouvé sur un panneau réel ; le banc ne le prouve que contre un faux panneau. À vérifier sur Amizo avant de s'y fier.
