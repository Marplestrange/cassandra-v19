<!-- ═════════════════════════════════════════════════════════════════
<!-- TITRE      : OpenEvolve lu : notes de lecture -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Notes de lecture du code d'OpenEvolve, en mots simples, avec renvois fichier:fonction, pour préparer le débat sur la sémantique d'Sedal. -->
<!-- MÉTHODE    : lecture du dépôt (clone en lecture seule, hors du dépôt Cassandra) ; ce qui est lu en détail et ce qui est seulement survolé sont séparés. -->
<!-- ═════════════════════════════════════════════════════════════════
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=373a47 ▼▼▼ -->
# OpenEvolve lu : notes de lecture

Statut : 04-11-2026. Lecture seule : rien de ce dépôt n'a été installé ni exécuté dans le serveur Cassandra. Le texte de ce document est de moi ; aucune ligne d'OpenEvolve n'est copiée.

## 0. Ce qui a été lu, et comment

Source : le dépôt `algorithmicsuperintelligence/openevolve` (Apache-2.0), branche `main`, clone superficiel de 594 fichiers, lu dans un dossier temporaire. Le paquet `openevolve/` fait ~14 000 lignes. Je n'ai PAS comparé avec la 0.4.1 d'Orion (`/tmp/oe-try/v/…`) : les numéros de ligne ci-dessous sont ceux de `main` ; une différence avec la 0.4.1 est possible.

**Lu en détail (ligne à ligne)**

| Fichier | Ce qui a été lu |
|---|---|
| `embedding.py` (115 l.) | en entier |
| `novelty_judge.py` (43 l.) | en entier |
| `selection.py`, `population.py` | en entier (ce sont des « crochets » : des types de décision) |
| `database.py` (2910 l.) | `__init__`, `_add`, `sample`, `sample_from_island`, tous les `_sample_*`, `_sample_inspirations`, `_calculate_feature_coords`, `_calculate_complexity_bin`, `_calculate_diversity_bin`, `_cosine_similarity`, `_llm_judge_novelty`, `_is_novel`, `_is_better`, migration (`should_migrate`, `migrate_programs`, `_migrate_one`), diversité (`_calculate_island_diversity`, `_code_shape`, `_fast_code_diversity`, `_get_cached_diversity`, `_update_diversity_reference_set`), config de la base |
| `process_parallel.py` | `_run_iteration` en entier (la boucle d'un tour : prompt, appel du modèle, lecture des diffs, évaluation, création de l'enfant) ; début de `run_evolution` |
| `evaluator.py` | `evaluate_program`, début de `_cascade_evaluate`, `_passes_threshold`, `evaluate_multiple` |
| `prompt/sampler.py` | `build_prompt`, `_identify_improvement_areas`, début de `_format_evolution_history`, `_format_inspirations_section`, `_determine_program_type`, `_extract_unique_features` |
| `config.py` | `DatabaseConfig` en entier ; les champs d'évaluateur et d'évolution (cascade, seuils, `max_code_length`, arrêt anticipé) |
| `evolution_trace.py` | `log_failure` |
| `prompts/defaults/diff_user.txt`, `docs/how-it-works.md` | en entier / début |

**Lu en détail dans un second temps (04-11, même jour)** : `process_parallel.py` : `_choose_evolution_mode`, `_create_database_snapshot`, `_select_island`, `_checkpoint_if_due` et la boucle de traitement d'un résultat dans `run_evolution` (erreur → journal d'échec ; enfant → `database.add`, génération d'îlot, migration, meilleur, arrêt sur score) ; `llm/ensemble.py` (tirage pondéré d'un modèle, graine par itération) ; `prompt/sampler.py` : `_format_evolution_history` presque en entier (3 derniers essais, meilleurs programmes, programmes « divers » tirés au hasard parmi le reste) ; `coevolution.py` : en-tête et docstring de `run_coevolution` ; `utils/code_utils.py` : liste des fonctions seulement (lecture des diffs SEARCH/REPLACE, blocs EVOLVE, `calculate_edit_distance`, importée par `database.py` mais dont je n'ai pas lu le corps).

**Seulement survolé (noms de fonctions, signatures ou quelques lignes ; je ne les affirme pas)** : `controller.py` (liste des fonctions seulement : `run`, `_save_checkpoint`, `_load_checkpoint`…), `api.py`, `cli.py`, la suite de `coevolution.py`, `llm/openai.py` et les autres clients, `utils/trace_export_utils.py`, `compat/alphaevolve*`, `config.py` hors les champs cités, `_update_archive`, `_enforce_population_limit`, `_update_best_program`, `_reconstruct_islands`, la sauvegarde et le chargement des points de reprise, les exemples (`examples/`, non ouverts), `tests/`. Ils ne touchent pas à la sémantique d'après leurs noms, mais c'est une inférence.

**Non lu du tout** : les 590 fichiers d'exemples et de résultats, `scripts/`, `Dockerfile`, le visualiseur.

## 1. Comment OpenEvolve travaille, en mots simples

Une boucle : on choisit un programme **parent** et quelques programmes **inspirations** dans une base ; on écrit un prompt avec leur code, leurs scores et un résumé de l'histoire ; un modèle répond avec des modifications (au format « cherche ce bloc / remplace par celui-là ») ; on applique les modifications, on **évalue** le programme enfant (une fonction d'évaluation écrite par l'utilisateur), et on le range dans la base si c'est utile.

**Où se joue chaque étape**

- Un tour = `process_parallel._run_iteration` (dans un processus de travail ; la base est copiée en « instantané » pour chaque tour, d'après le nom `ProcessParallelController._create_database_snapshot`, non lue).
- Choix d'îlot : `_select_island` (non lue ; d'après `run_evolution`, une rotation simple ou une fonction de l'utilisateur, `selection.IslandSelector`).
- Mode du tour : diff ou réécriture complète, `_choose_evolution_mode` (non lue ; probabilité réglable d'après la config).
- Rejets avant évaluation : réponse sans diff valide, diff qui ne change rien, code plus long que `max_code_length` (10 000 signes par défaut), modifications hors du bloc autorisé. Chaque rejet est une erreur nommée (`_reject`).
- Évaluation : `evaluator.evaluate_program` (un fichier temporaire, des reprises en cas d'exception, un délai ; **aucun cache**, voir § 4).
- Entrée dans la base : `database.add` → `_add`.

## 2. La base : MAP-Elites, îlots, archive

**La grille MAP-Elites** (`database._add`, `_calculate_feature_coords`). Chaque programme reçoit des coordonnées dans une grille ; une case ne garde qu'un programme, le meilleur (`_is_better` : le score de fitness, hors dimensions de la grille). Par défaut deux dimensions (`DatabaseConfig.feature_dimensions`) : `complexity` et `diversity`, 10 cases chacune. Une dimension peut être n'importe quelle mesure rendue par l'évaluateur (valeur continue, mise à l'échelle par `_scale_feature_value`, min-max par défaut).

**Comment la « diversité » est mesurée (point capital).** Ce n'est PAS un calcul de sens. `_fast_code_diversity` (database.py) additionne : 0,1 × la différence de longueur du texte + 10 × la différence du nombre de lignes + 0,5 × le nombre de caractères présents dans un code et pas dans l'autre. Elle est moyennée contre un petit ensemble de référence de 20 programmes (`diversity_reference_size`, choisi gloutonnement par `_update_diversity_reference_set`). Le docstring dit lui-même « fast approximation ». Et la « complexité » est la **longueur du texte** (`len(program.code)`). Donc leur grille de qualité-diversité par défaut est : taille × une approximation de taille. C'est ce que fait déjà Sedal (une niche par taille de code), en moins fin.

**Les îlots** (`num_islands`, 5 par défaut). Des sous-populations séparées. Un enfant reste dans l'îlot de son parent (`_add`). Les parents et les inspirations sont tirés dans l'îlot (`sample_from_island`, `_sample_inspirations`). **Migration** (`migrate_programs`, `_migrate_one`) : tous les `migration_interval` générations (50 par défaut), les 10 % meilleurs de chaque îlot sont copiés dans les deux îlots voisins (anneau) ; une copie n'est faite que si aucun programme de l'îlot cible n'a exactement le même code (`p.code == migrant.code`, égalité de texte) ; les copies ne migrent jamais à nouveau.

**L'archive** (`archive_size` 100, `_update_archive`, non lue en détail) : un ensemble de programmes d'élite, entretenu en même temps que les cases (on y voit un remplacement quand une case change de propriétaire, `_add`).

**Limite de taille** (`population_size`, 1000 ; `_enforce_population_limit`, non lue en détail) : au-delà, des programmes sont retirés ; je n'ai pas lu selon quelle règle.

## 3. Comment les parents et les inspirations sont choisis

Parent (`sample_from_island`) : un tirage au sort selon trois parts réglables : `exploration_ratio` 0,2 (au hasard dans l'îlot), `exploitation_ratio` 0,7 (dans l'archive, de préférence de l'îlot), le reste (0,1) tiré avec un poids égal à la fitness (`_sample_from_island_weighted`, plancher 0,001).

Inspirations (`_sample_inspirations`, 5 par défaut) : (1) le meilleur de l'îlot ; (2) les meilleurs de l'îlot (10 % des places, `elite_selection_ratio`) ; (3) pour le reste, des programmes dans des cases **voisines dans la grille** (on perturbe les coordonnées du parent de ±2 par dimension, jusqu'à 3 essais par place) ; (4) enfin, au hasard dans l'îlot. Donc « voisin » veut dire « voisin en taille/approximation de taille », jamais « voisin par le sens ».

## 4. Ce qu'OpenEvolve fait DÉJÀ de sémantique

C'est peu, et c'est **éteint par défaut**.

**`embedding.py` + `database._is_novel`.** Si `embedding_model` est réglé (défaut : `None` ⇒ rien), chaque programme qui veut entrer dans la base est encodé par un modèle distant d'API (OpenAI `text-embedding-3-*`, Gemini, ou toute API compatible) par `EmbeddingClient.get_embedding` ; le code entier est envoyé comme texte. Puis `_is_novel` le compare (cosinus, `_cosine_similarity`) à tous les programmes **de son îlot** qui ont un vecteur, et retient le plus proche si sa similarité dépasse `similarity_threshold` (**0,99** par défaut, donc très haut : « presque identique »). S'il y en a un, on demande à un modèle de langage (`novelty_llm`) : « ces deux codes sont-ils vraiment différents ? » (`_llm_judge_novelty`, prompt dans `novelty_judge.py` : on ignore les noms de variables, la mise en page, les commentaires ; on compte les différences d'algorithme, de structure, d'optimisation, d'hyperparamètres). La réponse « NOT_NOVEL » fait refuser l'entrée dans la base. Cas d'erreur : réponse vide, illisible ou exception ⇒ « nouveau » (on laisse entrer).

Ce que ce filtre **fait** : il évite que la base se remplisse de quasi-copies. Ce qu'il **ne fait pas** :

1. Il ne s'applique qu'à l'**entrée dans la base**, donc **après** l'appel au modèle générateur ET **après l'évaluation** (l'évaluation se fait dans le travailleur, `_run_iteration` ; puis `run_evolution` appelle `database.add`, et un refus lève `_CandidateRejected` après coup : relu à ces deux endroits). Il n'économise ni jetons de génération ni temps d'évaluation, seulement de la place dans la base et, de façon indirecte, de la diversité des futurs parents.
2. Il ne regarde qu'**un seul voisin** (le plus proche) et ne juge que s'il dépasse le seuil.
3. Il ne sert **ni** à choisir les parents, **ni** les inspirations, **ni** à définir les cases de la grille, **ni** à guider le prompt.
4. Il encode du **code brut**, jamais la description de l'idée (l'hypothèse du modèle n'est pas encodée).
5. Il n'a **aucune mémoire des échecs** : un programme rejeté ou en erreur ne laisse aucune trace dans la base ; rien n'empêche de reproposer la même idée demain.
6. Chaque programme est ré-encodé à chaque tentative d'entrée (un appel d'API par candidat, sur tout le texte).

**Les « autres » mécanismes proches du sens :**

- `_extract_unique_features` (sampler.py) : pour décrire une inspiration au modèle, du **texte fixe** selon des mots présents dans le code (« class », « numpy », « for » et « while » tous deux présents, code court/long). Aucun calcul sémantique : de la recherche de sous-chaînes.
- `_determine_program_type` : étiquette « performant / alternatif / expérimental / exploratoire » d'après le **score** seulement.
- `programs_as_changes_description` (option) : on garde, pour chaque programme, une **description en prose** de ce qu'il fait (le modèle la met à jour à chaque tour comme une partie du diff, `process_parallel._run_iteration`), et on montre cette prose plutôt que le code aux inspirations. C'est le plus proche d'une « mémoire d'idées », mais sans comparaison de sens.
- `evolution_trace.py` (`log_failure`) : journal des tours **sans enfant** (erreur de diff, de longueur, délai…). Écrit sur disque (option `include_failures`), pour l'analyse ou l'entraînement. **Il n'est pas relu par la boucle** : ces échecs ne reviennent jamais dans le prompt.

## 5. Le prompt et l'historique

`PromptSampler.build_prompt` : le modèle reçoit le programme parent, sa fitness, ses coordonnées de grille, des « zones d'amélioration » (`_identify_improvement_areas` : fitness en hausse/baisse par rapport au dernier, longueur du code), l'historique des 3 derniers « essais précédents » parmi les meilleurs de l'îlot (leur description des changements et leurs métriques), quelques meilleurs programmes, les inspirations, et les « artefacts » du parent (sortie d'erreur, trace, texte libre rendus par l'évaluateur : un canal de retour). Le message du modèle demande des modifications au format SEARCH/REPLACE. Les échecs d'un **autre** tour ne sont pas dans ce prompt ; seul ce que l'évaluateur a laissé en « artefacts » sur le parent y est.

## 6. Évaluation en cascade, cache

**Cascade** (`evaluator._cascade_evaluate`, `cascade_thresholds` = 0,5 / 0,75 / 0,9) : si le module d'évaluation définit `evaluate_stage1`, `evaluate_stage2`… on exécute l'étape 1 (rapide), et on ne passe à l'étape 2 que si le score de l'étape 1 atteint le seuil (`_passes_threshold`, qui prend `combined_score` ou la moyenne des mesures numériques). C'est un entonnoir de **coût**: écarter tôt ce qui est mauvais. Sa décision est numérique, jamais sémantique.

**Cache d'évaluation** : je n'en ai trouvé aucun (recherche du mot « cache » dans `evaluator.py`, `controller.py`, `process_parallel.py` : seulement le cache de clients asynchrones des travailleurs). Le même code évalué deux fois est réévalué deux fois, sauf si le rejet « le diff n'a rien changé » (`child_code == parent.code`) l'a arrêté avant. Le seul garde-fou de doublons au sens strict est l'égalité de texte à la migration.

## 7. Autres points utiles à Cassandra

- **`PopulationStrategy`** (population.py) : des crochets (`admit`, `replace_cell`, `archive`, `evict`, `migration_due`, `migrate`) pour que l'utilisateur remplace les règles de la base, sans pouvoir contourner le filtre de nouveauté. Un signe que la structure est pensée pour qu'on y branche autre chose que ses règles par défaut.
- **Rejeu et graine** : tout est ensemencé (`random_seed` 42, `reseed(iteration)` du modèle). Même idée que notre « graine fixe par point ».
- **Mode diff contre réécriture** : le diff est un coût en jetons plus bas, mais il échoue si le bloc cherché ne correspond pas exactement (`apply_diff_blocks`, « None of the N SEARCH block(s) matched »).
- **Coût** : `max_code_length`, `early_stopping_patience`, plafond de jetons : surtout des limites de taille. Pas de budget en dollars (c'est FrugalEvo qui en a un, voir `docs/CN_FRUGALEVO.md`).

## 8. Ce qu'il faut retenir pour le débat

1. La partie « sémantique » d'OpenEvolve est **une seule fonction de filtre à l'entrée de la base**, éteinte par défaut, qui encode du code avec un modèle distant. Tout le reste (diversité, voisins, types d'inspirations) est de la taille du texte et des mots-clés.
2. Elle n'économise **aucun jeton ni aucun temps de calcul**, parce qu'elle vient après l'évaluation. Une version qui agit AVANT (sur l'idée, avant d'écrire le code ; ou sur la variante, avant de la juger) serait plus utile et n'existe pas chez eux.
3. Ils n'ont **ni mémoire des échecs ni cache d'évaluation**. Chez nous, les tombes existent déjà (par empreinte exacte de l'arbre syntaxique) : on est devant eux sur ce point, et il s'agit surtout de les rendre plus intelligentes.
4. Leur grille « qualité-diversité » est grossière. Il y a de la place pour mieux, sans forcément un modèle de sens : une mesure de **comportement à l'exécution** serait plus honnête pour notre problème (voir `docs/CN_SEDAL-SEMANTIQUE.md`).
5. Le sens n'est jamais une preuve, chez eux non plus : l'évaluateur reste le juge ; le filtre de nouveauté ne fait que refuser une entrée.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->
