# Notes sur le portage du module sites

Ce qui a été fait et ce qui manque :

1. **Intégrations (TODO) :** Les appels au panneau (FastPanel), aux sauvegardes et à WordPress (`WP-CLI`) ont été isolés dans des `# TODO(...)` (ou à utiliser via `ctx.courtier()`). Le code V19 n'utilise plus de `subprocess` ni d'injections HTML dans le module.
2. **Leçons de la V18 portées (voir tests/commentaires) :** 
   - `_site_up` gère les redirections (3xx) pour ne pas classer en panne un site qui force HTTPS.
   - `_site_probe` chronomètre : une réponse HTTP en délai dépassé (ou > 8s) est une panne.
   - `actions modifiantes` : refaire le SSL ou le restart devra exiger un droit spécifique (quota 50 chez LE, qui n'est pas protégé par un `confirm()` JS volatil).
   - `CMS` : La distinction est établie entre répertoires parents (`_RACINES_WEB` pour Laravel/BookStack) et marqueurs d'API (`_SONDES_HTTP` pour Vaultwarden/Gitea) au niveau détection.
   - `Bases de données` : Ne pas deviner par ressemblance textuelle pour éviter de divulguer les bases d'autrui (leçon du `db.site_id` manquant).
   - `Certificats` : l'arrondi (plutôt que la troncature) et l'analyse de `expired_at` plutôt que `expires`.
3. **Architecture V19 :** La sonde n'est plus un `Thread` flottant mais un **moteur périodique** régulé par le noyau. L'historique d'alertes n'envoie plus d'email directement, un **détecteur** (`panne`) rend des `constats` que le Centre de notifications (module `notifications`) attrapera et affichera / notifiera.
4. **Schéma de base :** Les sites déclarés hors panneau ne vivent plus dans `users.json`, mais dans la table dédiée `sites_declares` (qui cloisonne par `compte`).

Bancs de brouillon à corriger (marqués skip) : test_attribuer_admin, test_lecon_site_probe_lenteur, test_lecon_site_up_redirections
