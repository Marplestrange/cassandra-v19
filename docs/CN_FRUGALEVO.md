<!-- ═════════════════════════════════════════════════════════════════
<!-- TITRE      : FrugalEvo lu, et Frugal -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : FrugalEvo lu, et Frugal -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═════════════════════════════════════════════════════════════════
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=58f1fd ▼▼▼ -->
# FrugalEvo lu, et Frugal

Statut : 04-11-2026. Ce document dit ce que fait FrugalEvo, ce que Frugal (`orfan/CN_frugal.py`) en reprend, ce qu'il laisse, et pourquoi.

## 0. Source et licence

- Article : « FrugalEvo » (arXiv). Dépôt officiel : <https://github.com/chchenhui/frugalevo> (Apache-2.0 ; 14 étoiles ; créé le 02-10-2026). C'est un fork du cadre **SkyDiscover** auquel on a ajouté une recherche `frugalevo` (`skydiscover/search/frugalevo/` : `controller.py`, `database.py`, `strategy.py`, `evaluator_analysis.py`).
- **Aucune ligne de leur code n'est copiée dans Cassandra.** Frugal est une réécriture des IDÉES, dans notre vocabulaire, pour notre problème (une fonction Python pure, plus rapide à résultat identique). Aucune mention de licence tierce n'est donc due dans le code ; on cite la source ici par honnêteté. Si un jour du code est repris mot pour mot, il faudra garder la licence Apache-2.0 et la mention des auteurs.
- Ce qui a été lu : `controller.py` (3267 lignes), `database.py`, `strategy.py`, `evaluator_analysis.py`, `route.py`, le `frugalevo.yaml` du banc « circle_packing » (budget 1 $, modèle économe GLM-5.3-flash, modèle fort GLM-5.3). **Non lu** : `skydiscover/config.py` (donc les valeurs par défaut des paramètres non écrits dans le yaml), `skydiscover/prompt/`, `default_discovery_controller.py`, `base_database.py`, le README de la recherche. Le `controller.py` a été lu par un sous-agent qui m'a rendu un résumé avec numéros de ligne : je n'ai pas relu moi-même chacune de ses 3267 lignes.

## 1. Ce que fait FrugalEvo, en mots simples

**L'idée.** Dans une recherche évolutive de code, la plus grande partie du coût vient des nombreux appels de modèle qui échouent. FrugalEvo sépare le travail en deux :

1. Un modèle **fort** (cher, appelé rarement) ne code presque pas : il écrit des **stratégies**, c'est-à-dire des plans en prose (« remplace telle phase par telle construction, voilà pourquoi ça devrait mieux scorer »). Il peut aussi livrer un programme « de référence » qui applique la première stratégie.
2. Un modèle **économe** (bon marché, appelé souvent) **implémente** chaque stratégie en code, plusieurs fois (`implementations_per_strategy`, 3 dans le yaml).
3. Un **évaluateur** note chaque programme (`combined_score`). Les bons programmes entrent dans une base ; la recherche continue jusqu'à épuisement du **budget en dollars** (`budget_usd`, 1,0 dans le yaml).

**La boucle** (`FrugalEvoController.run_discovery`) :

- *Au départ* : une analyse unique de l'évaluateur (§ 5) ; une **cascade d'ouverture** : d'abord quelques essais économes sans stratégie (`opening_cheap_candidates`, 3), pour mesurer ce que vaut le modèle bon marché seul ; puis, si l'on veut, un essai direct du modèle fort ; puis les portefeuilles de stratégies.
- *À chaque tour* : le contrôleur calcule la **largeur admise** du tour d'après ce qui reste du budget (§ 4) ; il choisit un **parent** (§ 2) ; si une nouvelle stratégie est « due » (`strategy_when` : `stalled` dans le yaml, c'est-à-dire seulement quand la recherche cale ; sinon `always` ou `reuse_on_improvement`), il appelle le modèle fort pour 3 stratégies (`strategies_per_guide_call`) ; sinon il fait implémenter la stratégie courante par le modèle économe.
- *Course ordonnée* (`ordered_strategy_racing`, vrai dans le yaml) : un **pilote** économe par stratégie (même parent, en parallèle) ; on classe les stratégies sur le score du pilote ; on **exploite** la meilleure par lots, tant qu'elle améliore le meilleur global, puis on passe à la suivante. Option d'élagage des pilotes sans gain (`ordered_pilot_prune_nonpositive`).
- *Assurance* : si une stratégie productive cale, le modèle fort peut l'implémenter lui-même, une seule fois, avant qu'on l'abandonne ; et sur un long plateau, un essai « hedge » du fort sans stratégie.

**Les stratégies** (`strategy.py`). Chaque stratégie est un bloc `<STRATEGY_TITLE>[famille] titre</STRATEGY_TITLE><STRATEGY>…</STRATEGY>` avec quatre lignes obligatoires : *famille du mécanisme*, *portée du remplacement* (quelle fonction/phase on remplace), *budget de calcul* (bornes dures), *mécanisme du gain* (le degré de liberté nouveau). Il finit par une phrase de **vérification du gain attendu** (un score calculé, ou un seuil falsifiable). Le prompt interdit le code dans une stratégie, exige des stratégies vraiment différentes entre elles (une locale, une intermédiaire, une structurelle) et refuse les variantes de réglage (autre graine, autre tolérance).

**Le carnet des stratégies** (`StrategyLedger`). Chaque stratégie garde son résultat (meilleur score, gain, nombre d'implémentations utilisables, 3 dernières raisons d'échec). Le prompt suivant du modèle fort reçoit : l'historique résumé (« opérateurs de grande valeur » conservés + récents), les **familles de mécanismes épuisées** (« jamais amélioré »), les **mots qui reviennent** dans plusieurs familles sans succès (« ornières »), et, si les 6 dernières ont échoué, l'ordre de sortir de toute famille déjà essayée.

## 2. La sélection des parents (`database.py`)

La base est une **MAP-Elites à îlots** (5 îlots, population 40, archive 100) : chaque programme tombe dans une case selon des traits (taille du code, « diversité » mesurée sur des textes), une case ne garde que le meilleur ; tous les 10 tours, les meilleurs migrent entre îlots voisins (en anneau). Choix du parent : 20 % exploration (au hasard dans l'îlot), 70 % exploitation (dans les 10 % du haut de l'archive), le reste au hasard. Quand une stratégie est guidée, le parent est **ancré sur le meilleur global**, et après quelques tours stériles on échantillonne dans une « bande haute » en pénalisant les lignées trop usées. Le contexte donné aux modèles est borné (extraits de structure, quelques autres programmes).

## 3. Le suivi du coût et les critères d'arrêt

- Le coût est compté **en dollars** par palier : une moyenne par candidat économe, par appel de stratégie, par implémentation du fort. `_forecast_cost` prévoit le coût du tour ; `_plan_iteration` **réduit la largeur** du tour tant que la prévision dépasse le reste, et s'arrête si même la plus étroite dépasse. Piège : tant qu'un palier n'a pas d'historique, la prévision est vide et le tour est admis à l'aveugle (le premier tour sert à mesurer).
- La largeur peut être « en tête chargée » (`schedule`, large au début, étroite à la fin).
- Arrêts : budget épuisé ; score cible atteint (`target_score`, `stop_on_target`) ; arrêt extérieur. Un seuil de succès ne fait que poser un jalon.
- Stagnation : au bout de `stagnation_patience` tours sans gain, le taux d'exploration monte, et le modèle fort peut recevoir un effort de raisonnement plus élevé (avec un intervalle qui s'allonge).
- Une sauvegarde d'état (`frugalevo_state.json`) permet de reprendre.

## 4. Raffiner un échec

FrugalEvo ne relance pas bêtement un candidat. Il fait deux choses : (a) les implémentations d'une stratégie se font **l'une après l'autre** (`sequential_implementation_feedback`) : le résultat ou l'erreur de l'essai précédent, avec le programme fautif, est remis dans le prompt du suivant (« répare, ne change pas le mécanisme, ne change pas juste la graine »), avec arrêt au premier gain ou après trop d'échecs de suite ; (b) la raison d'échec (compacte, 400 signes) est conservée dans la stratégie et revient au modèle fort au prochain achat. Il sait aussi **récupérer un programme complet** depuis un diff inutilisable, sans nouvel appel.

## 5. L'analyse de l'évaluateur (`evaluator_analysis.py`)

Une seule fois, avant la recherche, le modèle fort lit le texte du problème, le code de l'évaluateur et la liste des paquets disponibles, et rend trois sections : **ce que le score récompense vraiment** (termes, poids, ce qui est presque au maximum, ce qui s'oppose), des exemples de pistes d'**exploration**, des exemples de **raffinement**. Ce texte est ajouté à chaque demande de stratégie. Utile quand l'évaluateur est opaque.

## 6. Ce qu'on garde, ce qu'on laisse

| Idée de FrugalEvo | Décision | Pourquoi |
|---|---|---|
| Fort = stratégies en prose, économe = code | **Gardé** (cœur de Frugal) | C'est l'idée qui fait baisser le coût : le fort écrit 2-3 plans courts, l'économe fait le travail volumineux. |
| Plusieurs stratégies, diversité exigée, quatre rubriques | **Gardé, allégé** | On demande 2-3 plans, chacun avec sa famille, sa portée et le gain attendu ; on dédoublonne les familles. |
| Carnet des stratégies, familles épuisées, raisons d'échec renvoyées | **Gardé (ajouté le 04-11, sur ta demande)** | Un moteur ne garde rien d'un appel à l'autre (il tourne en cage, sans fichier). Il rend donc ses « fiches » (famille, issue, raison, gain) au serveur, qui les nettoie et les garde SUR LE DISQUE (`moteurs.json`, 24 fiches par point, une par famille). À l'appel suivant, le modèle fort les reçoit : idées prouvées, idées ratées avec leur raison, et, après 6 échecs de suite, l'ordre de changer de famille. Une famille déjà ratée qu'il redirait quand même n'est pas réécrite (zéro appel). Les V18 sans mémoire tournaient en rond. |
| Réparation séquentielle avec retour d'erreur | **Gardé** | Si une version est fausse ou plus lente, on dit POURQUOI au modèle économe (sortie différente sur telle entrée, ou rapport de vitesse) pour qu'il l'affine, dans un budget de tours. |
| Budget borné, prévision du coût | **Gardé, en appels et en jetons** | Nous n'avons pas de dollars ici : le relais plafonne déjà les appels et les jetons, et Agents IA tient le plafond de coût de la maison. Frugal ajoute ses propres bornes (tours, appels). |
| Pilotes + course ordonnée entre stratégies | **Gardé en miniature** | Chaque stratégie reçoit un premier essai ; on affine d'abord la plus prometteuse (la plus rapide encore équivalente, sinon la moins fausse). |
| Évaluateur = juge dans la boucle | **Laissé** | Chez nous le moteur ne juge JAMAIS : il vérifie seulement « même sortie sur les entrées visibles ET plus rapide » ; le noyau juge sur tout le corpus et le jeu réservé. |
| Base MAP-Elites à îlots, migration, populations | **Laissé** | Il n'y a qu'une fonction, un seul parent (la référence), un seul appel : rien à peupler. Le moteur « Évolutif » fait déjà des générations. |
| Règles gratuites d'abord | **Nôtre, gardé** | FrugalEvo n'en a pas : c'est notre atout de coût zéro. |
| Analyse de l'évaluateur par un modèle | **Gardé, sans appel de modèle** | Le juge de la maison est connu : le contexte porte ses seuils (gain minimum, poids des objectifs). Frugal les écrit dans la demande au modèle fort (« le juge exige les mêmes valeurs, au moins X % de gain, un gain qui tient hors du vu »). Un appel de plus pour le deviner serait du gaspillage. |
| Cascade d'ouverture, hedge du fort, assurance | **Laissé** | Ils servent à une recherche longue sur un budget en dollars. Notre appel est court et borné. |
| Effort de raisonnement qui monte à la stagnation | **Laissé** | Notre relais n'expose pas ce réglage ; le rôle de modèle décide. |
| Rejets propres à un banc (mutations JAX, profil « txn_scheduling ») | **Laissé** | Spécifiques à leurs bancs. |

## 7. Frugal, en trois phrases

1. Il essaie d'abord les recettes gratuites ; si l'une est prouvée plus rapide, il la rend et ne dépense rien. Sans partie de la fonction qui travaille beaucoup, il ne dépense rien non plus.
2. Sinon un modèle fort propose 2 ou 3 idées en texte (sans code), un modèle économe écrit chaque idée en code, et Frugal vérifie chaque version lui-même : même résultat, et plus rapide.
3. Si une version est fausse ou plus lente, il dit au modèle économe pourquoi et lui laisse un ou deux essais pour la corriger ; il s'arrête dès que ses essais, ses appels ou ses jetons sont épuisés, et ne rend que ce qu'il a prouvé.

## 8. Limites honnêtes

- La comparaison de vitesse de Frugal se fait sur des entrées visibles, en un seul processus : le bruit de la machine existe. C'est un pré-filtre ; le noyau remesure.
- Le carnet apprend le verdict du JUGE du noyau (rappel facultatif `verdicts`, 04-11) : « retenue » ou « refusée » avec la raison. Si deux stratégies rendent le même code, une seule fiche reçoit le verdict (celle du meilleur rapport sur le vu).
- Le carnet est lié au point, pas au modèle : changer de modèle fort garde l'historique, ce qui est voulu mais peut surprendre.
- La qualité dépend des modèles liés aux rôles « strategie » et « executant » ; un modèle fort qui n'écrit pas les balises attendues donne zéro idée (Frugal se rabat alors sur un texte brut unique).
- Nous n'avons pas reproduit les chiffres de leur article ; aucune affirmation de gain de coût n'est faite ici.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->
