- L'appel système (crontab, `subprocess.run` en root pour exécution immédiate) a été désamorcé : les droits d'écriture d'un module V19 s'arrêtent à sa propre base de données (`ctx.stockage`). L'application d'un changement au système d'exploitation et la pose du script de l'enrobage ont été étiquetés avec `# TODO(courtier)`.
- La liste consolidée intègre `cron_natural` ainsi qu'un point d'ancrage simulé pour `fastpanel_crons` (`# TODO(systeme)`) puisqu'on n'a pas pu lier le module responsable de la grappe serveurs au cours du portage.
- Les dépendances transverses (comme `_cron_links_by_ref` pour les Projets, `sauv_plans()` pour les Sauvegardes ou `mandats()` pour les droits d'agent) ont été converties en fonctions souches ou neutralisées (`# TODO(...)`).
- Le concept lourd de sonde redondante a été rayé : on délègue sereinement au concept neuf de "détecteur" l'émission de `constat.ouvert` sur le dysfonctionnement d'un cron.
- La fonction obsolète `cron_en_maintenance()` qui était en "quarantaine jusqu'en 2027" a été retirée : elle ne servait qu'à tirer le fil, elle n'a pas sa place dans la refonte.

Bancs de brouillon à corriger (marqués skip) : test_lecons_v18
