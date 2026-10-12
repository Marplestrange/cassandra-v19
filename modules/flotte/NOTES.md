J'ai porté la logique de gestion de la flotte (machines, parc, ssh, actions, liens), du sensorium (constats, acquits, gestes) et de la présence (fleet_pass, fleet_availability).
Le registre des machines (anciennement lu via `multiserver.json` et `_ms_load`) a été transposé en une table `machines` pour être cohérent avec le stockage V19.
Les threads de fond (`_flotte_presence_boucle` et `_flotte_sensorium_boucle`) sont devenus des `moteurs` périodiques.
La boucle `_sensorium_alertes_boucle` a été convertie en un `detecteur` qui émet des constats (et délègue les notifications au noyau V19), s'appuyant sur la table locale `sensorium_alertes` pour garantir la temporisation (délai de 10 min et retour à la normale de 2 min) avant de lever ou clore un constat auprès du noyau.
Certains appels à des outils spécifiques ou à la CLI (Tailscale, exécution SSH `_ms_ssh_exec`, Docker, systemctl) sont laissés en `# TODO(...)` ou mocks explicites car le noyau V19 requiert de passer par l'API système ou le courtier.
Les V18 leçons sur l'engagement (ignorer les pannes volontaires, un collecteur muet ne ferme pas l'alerte, résolution avec transaction SQLite) sont respectées.

Bancs de brouillon à corriger (marqués skip) : test_engagement_modifier_et_defaire, test_parc_lecture, test_sensorium_detecteur_delai
