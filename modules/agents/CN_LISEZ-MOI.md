<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Agents -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : agents -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.3.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Agents -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.3.0 empreinte=2486d7 ▼▼▼ -->
# Agents

Cassandra (la machine) et Itare (le bureau) en conversation. Un tour : mémoire → modèle → outils → réponse en clair.

- **Les outils dérivent du catalogue** (`ctx.outils`) : une capacité de plus = un outil de plus, avec son risque et son palier ; seuls ceux que l'acteur peut utiliser et que le compte a le droit d'utiliser. 60 présentés d'emblée selon la demande, tous joignables par nom, les autres par `outil_cherche` / `outil_appeler`.
- **Chaque outil traverse l'exécuteur** (`ctx.agir`, permission `agir`, acteur agent seulement) : droits du compte, palier, preuve, retour, journal. « Raconté » = rien n'a été fait ; l'agent le lit (avec ce que l'acte aurait été) et le dit.
- **Teinte** : une capacité marquée `externe` (lit de l'extérieur) pose la teinte du tour ; ensuite, ce qui est `sortant` (un envoi, un lien public) ou de risque moyen/élevé est retenu — la personne confirme au tour suivant.
- **Modèles** : Cassandra par le rôle `principal` ; Itare par le modèle choisi du compte, à défaut par le rôle `itare_citadelle`. Jamais la clé de la maison pour un compte sans modèle (Itare).
- **Mémoire** : `tour_commencer`, `rappeler`, `doutes_depuis_reponse` au début ; `apres_echange` à la fin (épisode, file de distillation).
- Une panne est gardée à part (rôle `panne`) et ne revient jamais dans le contexte ; un fil relu est remis en cohérence (chaque appel a sa réponse) ; « arrêter » est lu entre deux étapes ; un tour à la fois par conversation.

## L'équipe (lot 1 du portage de l'onglet « Agents IA »)
- **Trois agents et des services, déclarés comme DONNÉES** (`CN_equipe.json`, semés dans `agents_def`) : Cassandra (l'infrastructure seulement), Itare (le bureau de chaque compte), Amizo (la connaissance, n'agit jamais) ; services Relecteur et Vision. Le nom affiché, le ton, le modèle principal et de secours et les limites se règlent par agent (`agent_regler`).
- **Paliers par agent et par outil** (`palier_regler`) : `auto`, `raconter`, `retire` ; « demander » est l'indicateur `confirmer` posé sur `auto` (l'action est retenue dans `agent_attentes`). Niveau d'autonomie par agent (`niveau_regler`) : `observer` raconte toute écriture.
- **Coûts et plafonds** : chaque réponse du modèle est comptée par jour et par agent ; plafond par agent et global, le plus bas atteint donne l'action (`secours`, `arret` sauf Cassandra, `accord`).
- **Cloisonnement** : un compte ordinaire n'agit que sur SON Itare ; l'administrateur règle Cassandra, Amizo et les services, et ne lit jamais le bureau d'un autre compte. Les réglages sont refusés à tout agent. Aucun outil `coffre__*` pour un autre agent que Cassandra.
- Contrat des capacités : `equipe`, `agent`, `couts`, `paliers` (lecture), `agent_regler`, `palier_regler`, `niveau_regler`, `plafond_regler` (écriture, avec preuve et retour).

## Non porté
Le flux de jetons (le tour rend sa réponse entière : l'écran sondera la conversation), le salon multi-agents, les pièces jointes de conversation (« lab »), le mode plan, la compression de l'historique (les épisodes de la mémoire la remplacent), le comparateur solo.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
