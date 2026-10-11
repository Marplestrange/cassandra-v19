Les fonctions internes de la V18 ont été conservées à l'identique avec toutes leurs leçons documentées en code, mais l'architecture a été adaptée au noyau V19.
1. `voix_prefs` et `voix_machine` : La V18 stockait cela dans le DB en mémoire monolithique `user_prefs` et le fichier global `config.json`. Le module a maintenant sa propre base de données via `ctx.stockage` et respecte le cloisonnement.
2. L'interface (`html`, `javascript`) n'a pas été migrée, conformément aux instructions de portage de la V19. L'API retourne dorénavant un payload strict (notamment en base64 pour les fichiers audio).
3. Le paramètre d'infrastructure `_VX_VOIX_DIR` dépend dorénavant des `[[reglages]]` gérés par le noyau via `ctx.reglage("dossier_voix")`.
4. L'implémentation Telegram (`tgc_dispo`) à la fin du fichier de la V18 a été ignorée intentionnellement car elle se rattache à un module différent (canaux ou messagerie).

Bancs de brouillon à corriger (marqués skip) : test_choisir_bascule_mode_ne_perd_pas_nom, test_est_echo
