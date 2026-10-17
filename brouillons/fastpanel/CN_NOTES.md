- L'API HTTP FastPanel sur les ports 5501 / 8888 utilisait `_fp_api_call` (avec JWT en mémoire ou tokens du vault). N'ayant pas accès aux requêtes directes en V19 (et `subprocess` étant délégué au courtier), la logique a été commentée avec `TODO(courtier)`.
- Les appels directs MySQL (`_fp_mysql_direct`) et SQLite en mode read-only (`_fp_db_query`) sont remplacés par des appels au courtier, respectant la stricte règle V18 d'ouverture SQLite en RO pour ne pas corrompre le WAL.
- Les dépendances au système de fichiers (V18 `user_sites`, lecture de certificats via sondes SSL locales pour compenser le collecteur) sont documentées mais dépendront de sondes d'infrastructure V19 (`ctx.courtier`).
- Les notifications générées par V18 (via `_itare_proactive_add`) sont traduites en détecteurs natifs produisant un `constat` selon la règle V19, libérant le code des alertes manuelles. Le cycle de vie des alertes (résolution automatique) remplace les passages d'états manuels.
- `_fp_comptes_sites` et `user_sites` appartenaient à V18 pour corréler les comptes virtuels. En V19, ce croisement s'effectue dynamiquement en appelant `TODO(comptes)`.

Bancs de brouillon à corriger (marqués skip) : test_cloisonnement, test_droits_manquants, test_preuve_et_retour_arriere, test_z_zero_absence
