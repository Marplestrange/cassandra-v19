# Agents

Cassandra (la machine) et Itare (le bureau) en conversation. Un tour : mémoire → modèle → outils → réponse en clair.

- **Les outils dérivent du catalogue** (`ctx.outils`) : une capacité de plus = un outil de plus, avec son risque et son palier ; seuls ceux que l'acteur peut utiliser et que le compte a le droit d'utiliser. 60 présentés d'emblée selon la demande, tous joignables par nom, les autres par `outil_cherche` / `outil_appeler`.
- **Chaque outil traverse l'exécuteur** (`ctx.agir`, permission `agir`, acteur agent seulement) : droits du compte, palier, preuve, retour, journal. « Raconté » = rien n'a été fait ; l'agent le lit (avec ce que l'acte aurait été) et le dit.
- **Teinte** : une capacité marquée `externe` (lit de l'extérieur) pose la teinte du tour ; ensuite, ce qui est `sortant` (un envoi, un lien public) ou de risque moyen/élevé est retenu — la personne confirme au tour suivant.
- **Modèles** : Cassandra par le rôle `principal` ; Itare par le modèle choisi du compte, à défaut par le rôle `itare_citadelle`. Jamais la clé de la maison pour un compte sans modèle (Itare).
- **Mémoire** : `tour_commencer`, `rappeler`, `doutes_depuis_reponse` au début ; `apres_echange` à la fin (épisode, file de distillation).
- Une panne est gardée à part (rôle `panne`) et ne revient jamais dans le contexte ; un fil relu est remis en cohérence (chaque appel a sa réponse) ; « arrêter » est lu entre deux étapes ; un tour à la fois par conversation.

## Non porté
Le flux de jetons (le tour rend sa réponse entière : l'écran sondera la conversation), le salon multi-agents, les pièces jointes de conversation (« lab »), le mode plan, la compression de l'historique (les épisodes de la mémoire la remplacent), le comparateur solo.
