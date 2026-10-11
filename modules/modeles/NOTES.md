- L'appel au modèle (`_itare_agent_text`) n'est pas repris ici. Un `# TODO(agent)` marque l'endroit où le noyau V19 (ou un futur module d'agents) devra être appelé. `essayer` renvoie pour l'instant un succès factice.
- Tous les accès au coffre (Vault) pour sauvegarder les clés sont isolés derrière des `# TODO(coffre)` car un module ne peut interagir avec un autre qu'en déclarant l'événement ; les clés n'y sont pas inscrites pour le moment.
- Le thread asynchrone `ollama_pull` de la V18 (et son Lock global) a été supprimé au profit de l'architecture V19 : un *moteur sur événement* `modele.pull_demande` bloque en tâche de fond pour l'API `/api/pull` d'Ollama, libérant la capacité d'écriture de gérer l'asynchrone.
- L'historique d'Ollama `ollama_pull_status` est un TODO car l'état en temps réel sera émis par des événements V19 depuis le moteur dans l'avenir.
- Le déliement et l'effacement des anciens réglages de la configuration dans `role_set` se sont résolus de façon élégante en V19 avec la nouvelle table `modeles_roles`. Elle masque totalement les variables de réglages résiduelles : pas besoin de forcer une écriture dans le `config.json` via les réglages globaux du noyau. Le rôle lié a toujours la priorité absolue, suivant précisément la leçon de la V18.

Bancs de brouillon à corriger (marqués skip) : test_ajouter_et_lister, test_role_set_et_migrer
