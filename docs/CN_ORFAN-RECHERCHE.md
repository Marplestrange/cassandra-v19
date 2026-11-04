<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Orfan, la recherche : comment en faire le meilleur moteur possible -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Orfan, la recherche : comment en faire le meilleur moteur possible -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=a6009a ▼▼▼ -->
# Orfan, la recherche : comment en faire le meilleur moteur possible

Statut : 04-11-2026. Dossier de recherche, **rien n'est construit**. Tu décides à la fin (§ 5) ce qu'on fait, ce qu'on mesure, ce qu'on jette.
Aucune ligne de code d'un autre projet n'est reprise : ce sont des IDÉES, à réécrire en bibliothèque standard. Cassandra est AGPL-3.0 ; Apache-2.0 et MIT sont compatibles à condition de garder les mentions si un jour on copie du code ; GPL-3.0 et les licences « maison » (Llama, AI Scientist) : idée seulement.

## 0. Comment lire la fiabilité

Chaque affirmation porte une étiquette :

- **LU** : la page, le README ou le résumé arXiv a été ouvert et lu (rarement le papier entier : je le dis quand je ne l'ai lu qu'en partie).
- **SURVOLÉ** : vu seulement dans un résultat de recherche ; je ne l'affirme pas.
- **ANNONCÉ** : un chiffre donné par les auteurs ou un résumé tiers (leurs propres bancs) ; je ne l'ai pas vérifié.
- **MESURÉ** : exécuté par nous, avec un petit script jetable (Python 3.14.7, Windows, micro-bancs ; sur 3.11-3.13 ou Linux les chiffres bougent).
- **VÉRIFIÉ** : étoiles, licence, dernier envoi de code, lus par l'API publique de GitHub le 04-11-2026 (pour l'axe 2 ; pour les axes 1 et 3 les pages GitHub lues n'affichent pas la date : « date non vérifiée »).

La recherche a été faite en parallèle par trois lecteurs (un par axe) ; j'ai relu leurs notes et refait moi-même les vérifications sur NOTRE code. Les notes brutes complètes sont dans le dossier partagé des sessions (`axe1-recettes.md`, `axe2-moteur-modele.md`, `axe3-hors-code.md`).

## 1. Résumé d'une page : les 10 idées les plus rentables

Classées par rapport gain / effort (la première est la plus rentable). « Axe » : 1 recettes gratuites, 2 moteur à modèle, 3 hors code.

| # | Idée | Ce qu'elle apporte, en une phrase | Effort | Axe |
|---|---|---|---|---|
| 1 | **Durcir les 5 recettes actuelles** et poser un petit « noyau d'analyse » commun (pureté, nom non redéfini, échappement, type connu) | Trois des cinq recettes d'aujourd'hui ne sont pas strictement équivalentes (prouvé § 2.1) : on corrige avant d'en ajouter | faible | 1 |
| 2 | **9 recettes à gros gain asymptotique** : mémoïsation, `x in liste` → ensemble, `sum(listes, [])`, `pop(0)` → deque, `.split()[0]`, `l = l + [x]`, `count()>0`, boucle `append` → `extend`, `any(==)` → `in` | Des gains de 5× à 170× MESURÉS, zéro jeton | moyen | 1 |
| 3 | **Montrer au modèle POURQUOI les essais ont échoué** (les tombes en clair, l'indice du juge : « sortie différente sur tel cas », « la ligne 42 domine ») | Aujourd'hui le prompt dit seulement « N variantes ont échoué » sans les montrer ; c'est le retour de GEPA / Effi-Learner, à coût nul | faible | 2 |
| 4 | **Ranger le prompt pour le cache** (partie stable d'abord, essais du tour à la fin) et faire remonter les jetons de cache dans le compteur de dépense | Lecture de cache à 0,1× (0,05× sur Sonnet 5.5) du prix d'entrée, sur une boucle de plusieurs tours | faible | 2 |
| 5 | **Évaluation en cascade** : compilation + 1 cas → mêmes résultats → mesure à froid seulement si un pré-test bon marché laisse espérer un gain | L'évaluation à froid est le poste cher ; EvoAlloc annonce −59 à −82 % d'évaluations complètes (ANNONCÉ) | moyen | 2 |
| 6 | **Boucle fermée pour les prompts et les politiques** avec TROIS jeux (entraînement, sélection, réserve scellée), arrêt précoce, plafond de longueur | Sans cela le moteur apprend le juge ; les études 2026 voient le pic de qualité vers les étapes 4 à 7, puis la chute (SURVOLÉ) | moyen | 3 |
| 7 | **Diff SEARCH/REPLACE par défaut**, fonction entière en repli | Beaucoup moins de jetons de sortie sur les fonctions longues ; AlphaEvolve et ShinkaEvolve mélangent les deux | moyen | 2 |
| 8 | **Bandit UCB sur les modèles**, récompense = gain relatif divisé par le coût | Le relais compte déjà la dépense : le choix du modèle devient une décision mesurée, pas un réglage à la main | faible | 2 |
| 9 | **Mémoire des gains rejouables** (idée ECO de Google) : chaque pièce validée devient un patron rejoué gratuitement avant tout appel de modèle ; plus tard, promotion en règle | Cassandra possède déjà son propre jeu de données de gains validés ; c'est un atout que personne d'autre n'a | moyen | 1+2 |
| 10 | **Détecteurs et tests d'attaque évolués sous un juge déterministe** (grille façon Rainbow Teaming ; règle de détection compilée, rappel mesuré, zéro faux positif sur corpus scellé, ne peut qu'alerter) | Place libre : l'état de l'art est « générer, valider, réparer », pas de vraie évolution ; et la sécurité ne dépend toujours pas d'un prompt | élevé | 3 |

**Ce qu'on ne fait PAS** (détail § 2.5, § 3.9) : RL au moment du test (GPU), modèle affiné maison, e-graphs / superoptimiseurs, dépendre de Ruff / DSPy / Hypothesis dans le chemin d'exécution, et toutes les recettes « jolies mais fausses » (`zip`, `try` sorti de la boucle, `sort(); reverse()`, `x**2` → `x*x` sur flottants…).

**Principe commun** : aucune de ces idées ne touche au juge du noyau ni au jeu réservé. Orfan propose, le juge dispose. Là où une idée demande de renforcer le juge (entrées « cruelles », comparaison des exceptions), c'est une décision à part, pour toi (§ 5).

## 2. Axe 1 — Plus de recettes gratuites (zéro jeton)

### 2.1 Ce que nos 5 recettes font aujourd'hui, et ce qui est FAUX

J'ai relu `orfan/CN_orfan.py` (`REGLES`) et exécuté les cas limites (MESURÉ, script jetable) :

| Recette actuelle | Cas où le résultat change | Preuve |
|---|---|---|
| `sorted(x)[-1]` → `max(x)` | Éléments égaux mais pas identiques : `sorted([1, 1.0])[-1]` rend `1.0`, `max([1, 1.0])` rend `1` (même chose avec `key=` : `sorted` stable rend le DERNIER des égaux, `max` le PREMIER). Avec NaN : `sorted([3, nan, 1])[0]` rend 3, `min` rend 1. Liste vide : `IndexError` devient `ValueError`. | MESURÉ |
| `any([f(v) for v in xs])` → `any(f(v) for v in xs)` | Si `f` lève plus loin que le premier vrai : la liste lève `ValueError`, le générateur rend `True`. Même chose pour un effet de bord. | MESURÉ |
| `len(x) == 0` → `not x` ; `dict()` → `{}` ; `list()` → `[]` | Faux si `x` n'est pas un conteneur standard (`__bool__` ≠ `__len__`) ou si `dict` / `list` est redéfini dans la portée. | lu dans le code, non exécuté |
| `list(générateur)` → compréhension | Équivalent pour une fonction pure (portée de classe mise à part). | lu |
| `sum([...])` → `sum(gen)` | Aucun gain en 3.14 (MESURÉ 3,06 µs des deux côtés) : mémoire seulement. | MESURÉ |

Le juge du noyau rattrape ces cas **seulement si le corpus les contient** (une liste vide, un NaN, deux égaux distincts : rare dans des exemples réels). La leçon : **une recette doit porter sa propre condition de sûreté sur l'arbre syntaxique**, le juge ne remplace pas cette condition. Et il faut **mesurer sur des données variées** : `sorted(x)[0]` → `min(x)` est PLUS LENT sur une liste déjà triée (MESURÉ 3,4 µs contre 6,8 µs).

### 2.2 Le noyau d'analyse commun (à écrire UNE fois, `ast` seul)

Presque toutes les recettes ci-dessous ne sont sûres que grâce à six questions, que l'on pose une fois pour toutes :

1. `est_pure(expr)` : seulement constantes, noms locaux, opérateurs, indexation, appels à une liste blanche de builtins non redéfinis ; ni `await`, `yield`, walrus, `del`.
2. `nom_libre(n)` : `min`, `list`, `sum`… ne sont ni affectés, ni paramètres, ni importés autrement.
3. `echappe(var)` : la variable est-elle rendue, passée en argument, stockée dans un attribut, capturée, aliasée ? Sinon on peut changer son type en sûreté.
4. `mute_dans(var, bloc)` : le bloc la mute-t-il ?
5. `type_connu(var)` : inférence minimale (littéral, `list(...)`, `range`, annotation, résultat d'une compréhension). Sans type connu, **on s'abstient**.
6. La version de Python cible (certaines recettes exigent 3.9 ou 3.10).

Règle d'or : **en cas de doute, ne pas réécrire**. Et ne tenter une recette que sur une ligne **chaude** (le profil existe déjà : `point_chaud`) : une ligne froide ne rapporte rien et le risque, lui, n'est pas nul. Un journal des échecs par recette (désactivation automatique d'une recette peu fiable) complète le dispositif.

### 2.3 Le catalogue : 46 recettes examinées, par ordre d'intérêt

Chaque ligne : avant → après · FAUX quand · condition vérifiable sur l'arbre · gain. « ast » = faisable avec la seule bibliothèque standard (c'est le cas de TOUTES ces recettes). Les gains sont MESURÉS par le lecteur de l'axe 1 (micro-bancs, 3 répétitions, minimum) ; ils dépendent de la taille et des données.

**A. À faire d'abord — gros gain asymptotique**

| Réf. | Avant → après | FAUX quand | Condition sur l'arbre | Gain |
|---|---|---|---|---|
| R01 | fonction pure auto-récursive → `@functools.cache` | arguments non hashables, fonction impure, résultat mutable partagé, méthode (le cache retient `self`), mémoire sans borne | au moins 2 appels récursifs (ou 1 dans une boucle) ; ni `global`/`nonlocal`, ni appel hors liste blanche ; retour immuable | `fib(18)` 300 µs → 0,03 µs (exponentiel → linéaire). **Le juge doit vider le cache entre mesures** |
| R02 | `x in L` en boucle (liste invariante) → `set` construit avant | éléments non hashables, `__eq__` sans `__hash__`, `L` modifiée, boucle trop courte | `L` locale, affectée une fois avant, jamais mutée ni aliasée ; éléments de type hashable connu | 30 → 2,5 µs (12×, 1000 éléments) |
| R03 | `sum(listes, [])` → `list(chain.from_iterable(x))` | éléments qui ne sont pas des listes (`TypeError` perdu) | second argument littéral `[]` (ou `()`) ; `sum` non redéfini | 59 → 7 µs (8×) |
| R04 | `q.pop(0)` / `q.insert(0, v)` → `collections.deque` | `q` indexée, découpée, triée, rendue | tous les usages de `q` dans {`append`, `pop(0)`, `extend`, `len`, itération, `in`} ; elle n'échappe pas | 67 → 28 µs, croît avec n |
| R05 | `s.split()[0]` → `s.split(None, 1)[0]` (et `[-1]` → `rsplit`) | indice autre que 0 / −1 ; `s` pas une `str` | sous-script constant 0 ou −1, `s` de type str connu | 78 → 0,5 µs (170×, chaîne de 25 000) |
| R40 | `l = l + [x]` → `l.append(x)` | `l` est un paramètre ou un alias (la mutation se verrait dehors) | `l` locale créée dans la fonction, non aliasée, non échappée | 12 → 1,9 µs (6×) |
| R07 | `x.count(v) > 0` → `v in x` | `x` pas list/tuple/str ; `count` avec bornes | un seul argument, type connu | 5,5 → 0,03 µs (court-circuit) |
| R10 | `for x in B: A.append(x)` → `A.extend(B)` | `B` est `A`, ou un générateur qui lit `A` | corps = exactement un `append(x)` | 1,8 → 0,17 µs (10×) |
| R08 | `any(v == c for v in L)` → `c in L` | **NaN** (`any(nan == v …)` est faux, `nan in [nan]` vrai) ; `__eq__` asymétrique | éléments int/str/bytes/bool/None, **jamais float** ; `c` pure | 23,8 → 5,6 µs (4×) |
| R06 | `[x for x in it if c][0]`, `list(filter(…))[0]` → `next(...)` | exception différente (`StopIteration`), condition non évaluée plus loin | `c` pure ; non-vacuité garantie par un `if lst:` juste avant | proportionnel au raccourci |

**B. Gain constant mais sûr (à faire ensuite)**

| Réf. | Avant → après | Piège principal | Gain |
|---|---|---|---|
| R11 | `r = []` + boucle `append(e)` (avec `if` éventuel) → compréhension | `r` aliasée, lue dans le corps, `x` relue après la boucle | 2,54 → 1,90 µs |
| R12 | `[x for x in it]` → `list(it)` ; `{k: v …}` → `dict(d)` | utiliser `dict(d)`, pas `d.copy()` (le sous-type change) | 1,49 → 0,29 µs |
| R13 | `list(map(lambda x: e, it))` → `[e for x in it]` | lambda à valeur par défaut ; sens inverse seulement avec un vrai builtin non redéfini | 4,4 → 1,8 µs |
| R14 | `[x for s in nested for x in s]` → `chain.from_iterable` | élément transformé ; `nested` à usage unique | 13 → 7,9 µs |
| R15 | `key=lambda p: p[1]` → `operator.itemgetter(1)` (et `attrgetter`) | `itemgetter(1, 2)` rend un tuple | 34 → 10,5 µs (3×) |
| R16 | comptage manuel `c[k] = c.get(k, 0) + 1` → `Counter` | le type change ; si `c` échappe, entourer de `dict(...)` | 39 → 21 µs |
| R18 | `bin(x).count('1')` → `x.bit_count()` | Python < 3.10 ; `x` pas un entier | 0,11 → 0,02 µs |
| R25 | `d[k] if k in d else v` → `d.get(k, v)` | `v` coûteux ou à effet de bord (évalué toujours) | 0,13 → 0,09 µs |
| R28 | `for k, _ in d.items()` → `for k in d` | la variable ignorée est lue | 10-30 % (non mesuré) |
| R29 | `for i in range(len(L)): v = L[i]` → `for v in L` | `L` mutée, `i` utilisé ailleurs | 10 % et plus |
| R26 | `if k not in d: d[k] = []` + `append` → `setdefault` | défaut partagé si ce n'est pas un littéral neuf | 1,5-2× (non mesuré) |
| R42 | `for k in d: r[k] = d[k]` → `r.update(d)` | `d` mutée dans la boucle | 3-5× (non mesuré) |
| R39 | `x = sorted(x)` → `x.sort()` ; `x = x[::-1]` → `x.reverse()` | `x` est un paramètre ou un alias | faible |
| R43 | déduplication avec `seen` liste → `seen` ensemble / `dict.fromkeys` | **jamais** `list(set(L))` (l'ordre est perdu) | quadratique → linéaire |
| R19 | `s.startswith(a) or s.startswith(b)` → `s.startswith((a, b))` | `a`, `b` non constants | 10-30 % |
| R35 | `s[len(p):] if s.startswith(p) else s` → `s.removeprefix(p)` | Python < 3.9 | modeste |

**C. Gain faible ou nul : à ne coder que si le juge le confirme**

R17 `x**2` → `x*x` (faux sur flottants : `1e200**2` lève `OverflowError`, `1e200*1e200` rend `inf` ; MESURÉ) ; R22 module → alias local (13 %, la spécialisation de 3.11+ réduit le gain) ; R23 regex précompilée (le cache de `re` fait déjà le travail) ; R24 constante de liste → `frozenset` (marginal) ; R27 `d.keys()` (lisibilité) ; R30 `len(x)==0` et R31 constructeurs vides (déjà dans Orfan, négligeables) ; R32 `s += w` → `join` (CPython optimise `s +=` sur une locale : MESURÉ 59 → 2,8 µs au niveau module seulement, **mesurer dans une fonction**) ; R33 f-strings (flynt est lui-même timide) ; R34 `lstrip().rstrip()` ; R20-R21 hisser un invariant hors de la boucle (faux si l'expression peut lever et que la boucle fait zéro tour : garder derrière un `if`).

**D. Négatives ou fausses : NE PAS coder** (prouvé)

- `min(a, b)` à la place du ternaire : plus lent (FURB136).
- `list(x)` / `x[:]` → `.copy()` : aucun gain (MESURÉ 1,17 contre 1,19 µs).
- `sum([comp])` → `sum(gen)` : aucun gain en 3.14 (garder seulement pour `any` / `all`, où le court-circuit paie).
- `''.join([comp])` → `join(gen)` : plus lent (`join` matérialise).
- `sorted(x)[-k:]` → `heapq.nlargest(k, x)` : beaucoup plus lent sur donnée triée (MESURÉ 3,85 contre 97,9 µs).
- `l.sort(); l.reverse()` → `l.sort(reverse=True)` : l'ordre des égaux change (MESURÉ).
- Boucle de somme → `sum()` sur des **flottants** : l'arrondi diffère (`sum([0.1]*10)` donne 1.0, la boucle `0.9999999999999999` ; MESURÉ, sommation compensée de 3.12+). Entiers seulement.
- `a[i] + b[i] for i in range(len(a))` → `zip` : si `b` est plus court, `IndexError` devient une troncature silencieuse.
- `try` sorti de la boucle (PERF203) : l'original continue après une exception ; sans coût depuis 3.11.

### 2.4 Fiches des projets et techniques

| Projet | Ce que c'est (2 phrases) | Licence · communauté · activité | À en retirer | Effort / risque / mesure |
|---|---|---|---|---|
| **Ruff** (astral-sh/ruff) — LU | Linter en Rust qui a absorbé perflint (PERF), refurb (FURB), flake8-comprehensions (C4), pyupgrade. Ses règles PERF101/102/203/401/402/403, RUF015/017, PLC0207, FURB192 sont des motifs prêts à lire. | MIT · 50,4 k étoiles · 17 929 commits ; date du dernier commit non vérifiée | La LISTE des motifs, et surtout ses correctifs marqués « unsafe » : une mine de cas risqués. Réécrire en `ast` ; ne pas en dépendre (binaire Rust). | Faible, 1-2 h par règle. Ce sont des règles de **lisibilité**, pas des garanties d'équivalence. Mesure : taux d'échec du juge par règle. |
| **perflint** (tonybaloney) — LU | Greffon pylint de performance : W8101, W8102, W8201 (invariant de boucle), W8202 (global en boucle), W8204 (`memoryview`), W8301 (liste → tuple), W8401-W8403. | MIT · 712 étoiles · 100 commits ; activité non vérifiée | Idées neuves : `memoryview` sur découpages répétés de `bytes`, liste jamais mutée → tuple. | Faible. W8301 change le type si la valeur échappe. |
| **refurb** (dosisod) — LU | Outil de « modernisation » (FURB100 à FURB192), dont 17 marqués [perf] ; s'appuie sur mypy. | **GPL-3.0** : idée seulement, rien à copier · 2,5 k étoiles | FURB129, 131, 140, 142, 190, 122, 182. | Idée seule ; dépend de mypy. |
| **pyupgrade / flynt** (asottile, ikamensh) — LU | Réécritures de syntaxe ; pyupgrade se dit lui-même « intentionally timid ». flynt refuse tout ce qui pourrait changer le comportement, sauf option. | MIT · 4,1 k et 732 étoiles | Une **politique de sûreté timide** comme modèle (ex. `%s` avec un tuple d'un élément). | Idée seule. |
| **Sourcery** — SURVOLÉ | Outil commercial (160 à 212 règles Python selon la page). | propriétaire (non vérifié) | rien de plus que Ruff | — |
| **ast-grep** (16,4 k étoiles, MIT) / **Semgrep** — LU / SURVOLÉ | Réécriture structurelle par motifs (`motif avant` + `motif après` + contraintes). SemOpt (arXiv 2510.16384, oct. 2025) fabrique des règles Semgrep depuis des commits de performance (surtout C/C++ ; ANNONCÉ). | MIT | Le **format** : une recette déclarative `(motif_avant, gabarit_après, prédicats_de_sûreté)`, avec un petit unificateur maison (~150 lignes) au lieu de 46 classes écrites à la main. | Moyen (1 jour pour le moteur de motifs, 15-30 min par recette). |
| **STOKE** (Stanford, 887 étoiles, Apache-2.0) / **Souper** (Google, 2,4 k étoiles, Apache-2.0, **archivé le 30-10-2025**) — LU | Superoptimiseurs (recherche aléatoire + preuve formelle) pour du binaire x86 et du LLVM IR. STOKE : « personne ne travaille activement » dessus. | Apache-2.0 | Seule l'idée : « chercher au hasard, prouver ensuite ». Rien d'utilisable pour Python. | Ne pas y consacrer de temps. |
| **egg / egglog** (egraphs-good, MIT, 1,9 k et 872 étoiles) — LU | Saturation d'égalités : garder TOUTES les formes équivalentes d'une expression et extraire la moins chère. `egglog-python` existe. | MIT | L'idée de ne pas choisir l'ordre d'application des règles. Pas d'optimiseur d'`ast` Python établi trouvé (SURVOLÉ). | Élevé, gain faible face aux recettes algorithmiques. **Priorité basse.** |
| **PIE** (CMU, madaan/pie-perf) / **Mercury** / **EffiBench-X** / **GSO** — LU (README) / SURVOLÉ | Jeux de paires « avant / après » de performance (PIE : plus de 77 000 paires C++, ANNONCÉ ; Mercury : 1 889 tâches Python, NeurIPS 2024). | Licence NON indiquée sur les pages lues (PIE, Mercury) · 101 et 87 étoiles · PIE inactif depuis 04-2024 | Mercury : un banc de mesure pour le juge. PIE : les auteurs avertissent que certains « gains » sont faux (constantes de tableaux réduites) — raison de plus de garder un juge externe. | Les fichiers téléchargés sont des données non fiables. |
| **ECO** (Google, arXiv 2503.15669, mars 2025) — SURVOLÉ | Fouille l'historique de commits pour bâtir un dictionnaire « anti-patron → correctif », appliqué ensuite par un modèle ; en production chez Google. **ANNONCÉ** : plus de 6 400 commits soumis, plus de 99,5 % de réussite, plus de 500 000 cœurs économisés par trimestre (chiffres de pages tierces). | — | L'idée forte : **les gains validés deviennent des patrons rejouables**. | Voir § 2.5 et § 4. |
| **LILO / DreamCoder** (LILO : MIT, 102 étoiles) — LU | Apprennent une bibliothèque de fonctions en compressant du code. Le dépôt officiel de DreamCoder lu est vide. | MIT | La « compression » repère les idiomes qui reviennent dans les solutions acceptées. | Élevé ; pas d'usage direct. |
| **Hypothesis** (9,1 k étoiles) / **CrossHair** (1,3 k) / **Z3** — LU (README) | Tests par propriétés ; exécution symbolique qui « trouve des différences de comportement entre deux fonctions » ; solveur SMT. Licences non lues (de mémoire MPL-2.0 pour Hypothesis : NON vérifié). | — | Hors du chemin d'exécution. Utiles **une fois par recette, en développement** : CrossHair compare « avant » et « après ». En production : un petit générateur maison d'entrées cruelles. | Moyen. |

### 2.5 Ce que l'axe 1 change pour Orfan

1. **Un moteur de recettes déclaratif** (motif avant, gabarit après, prédicats) à la place d'une classe par recette ; le catalogue passe de 5 à une quarantaine sans multiplier le code.
2. **Entrées « cruelles »** pour le pré-filtre `comparer_local` et pour le juge : liste vide, un seul élément, doublons, NaN, négatifs, déjà trié, très long ; **comparer aussi les exceptions** (type) ; vider les caches ; varier les formes de données. Côté Orfan (`comparer_local`) c'est faisable seul ; côté juge du noyau, c'est une décision pour toi.
3. **Un banc de test par recette** : chaque recette est livrée avec ses cas pièges (ceux de la colonne « FAUX quand ») ; c'est la barrière d'entrée.
4. **Fouille de nos propres pièces** : voir § 4 (précurseurs) : c'est le chemin « apprendre des règles » le plus réaliste pour nous.

## 3. Axe 2 — Un moteur à modèle plus intelligent et plus rapide

### 3.1 Ce que fait Orfan aujourd'hui (lu dans `orfan/CN_orfan.py`, `CN_frugal.py`, `CN_evolutif.py`)

`MoteurModele.proposer` : profil des lignes → (stratège optionnel) → un prompt → jusqu'à 3 appels **identiques** → les blocs de code extraits. Constats utiles :

- Le prompt ne dit au modèle que **« N variante(s) ont déjà échoué »** : il ne montre ni lesquelles ni pourquoi (`construire_prompt`). Les tombes sont donc inutilisées par le modèle.
- Les 3 appels reçoivent **le même prompt** : seule la température les distingue ; aucun retour du juge entre deux appels.
- Aucun tour de réparation dans `MoteurModele` ; Frugal 2 en a un (2 tours d'affinage).
- Le prompt mélange le stable (règles, source) et le variable (tombes, stratégie) sans souci du cache.
- La fonction entière est toujours réécrite, jamais un diff.
- Le modèle est choisi par le rôle, pas par la mesure.

Frugal 2 (`docs/CN_FRUGALEVO.md`) couvre déjà stratège fort / exécutant économe, plafonds d'appels, réparation. Évolutif (`docs/CN_OPENEVOLVE-LECTURE.md`, `docs/CN_EVOLUTIF-SEMANTIQUE.md`) couvre les niches, la mémoire des tombes par le sens (P0-P10). **Je ne les refais pas** : je les complète par ce qu'ils ne traitent pas (allocation du budget, cascade d'évaluation, format d'édition, cache, bandit).

### 3.2 Qui est responsable de quoi

| Sujet | Côté Cassandra (le moteur) | Côté fournisseur de modèle |
|---|---|---|
| Choix du modèle par essai (bandit) | OUI | — |
| Allocation du budget (cibles, branches, arrêt) | OUI | — |
| Format d'édition (diff / entier), analyseur tolérant | OUI | le modèle doit savoir suivre le format |
| Cascade d'évaluation, arrêt précoce, parallélisme | OUI (le juge est à nous) | — |
| Mémoire des échecs, déduplication | OUI | — |
| Réflexion sur les traces | OUI (construire le texte) | la qualité de la réflexion = le modèle |
| Cache de prompt | ordre du prompt, marqueurs `cache_control` | tarif, durée de vie, règles |
| Compression de contexte | quoi envoyer | (LLMLingua = modèle local, optionnel) |
| Plusieurs réponses, vote | nombre d'échantillons | prix par jeton, option `n`, lots |
| Routage, cascade de modèles | règle de bascule | disponibilité, limites de débit (le relais d'Orion) |
| Petit modèle affiné | seulement l'utiliser | l'entraînement est hors moteur |
| Qualité brute du code | — | OUI |

### 3.3 Fiches (étoiles, licences, dates VÉRIFIÉES par l'API GitHub le 04-11-2026)

| Projet | Ce que c'est | Statut · licence · communauté · activité | Ce qu'on en retire | Effort · risques · mesure |
|---|---|---|---|---|
| **ShinkaEvolve** (Sakana AI) — LU (papier arXiv 2509.19349, début ; README) | Boucle évolutive qui cherche avec très peu d'essais (circle packing en moins de 150 évaluations, selon le papier). Trois astuces : parent pondéré, rejet des doublons par similarité d'embeddings, **choix du modèle par bandit UCB1**. | Recherche, code utilisable (PyPI `shinka-evolve`) · Apache-2.0 · 1 496 étoiles · dernier envoi 05-10-2026 · v0.0.7 du 02-06-2026. Aucun usage de production tiers vérifié. | UCB1 (coefficient 1,0) ; récompense = amélioration relative sur le parent ; option `cost_aware_coef=0,5` (le coût est déjà dans la sélection) ; mutations 45 % diff / 45 % entier / 10 % croisement ; seuil de nouveauté 0,95 (papier) / 0,99 (README). Le papier ne décrit **pas** de cascade ni d'arrêt précoce. Le « débit 5-10× » du README est ANNONCÉ. | stdlib (`math.sqrt`, `math.log`). Risque : récompense bruitée si le gain est mesuré à froid sur peu de passes. Mesure : sur 10 cibles, 5 graines, appels / jetons / dépense pour atteindre le même gain validé, avec et sans bandit. |
| **AlphaEvolve** (DeepMind) — LU (arXiv 2506.13131, début) ; chiffres ANNONCÉS | Agent qui fait évoluer du code avec un mélange de modèles (un rapide, un fort), des évaluateurs automatiques et une base de programmes ; modifications en blocs SEARCH/REPLACE ; méta-prompt co-évolué. | Production interne chez Google. Service géré sur Google Cloud : les sources se contredisent (disponible en juillet 2026, ou aperçu restreint) — **je n'ai pas pu trancher**. Dépôts : alphaevolve_results (Apache-2.0, 305 étoiles), client Cloud (Apache-2.0, push 03-11-2026 ; exige une licence Gemini Enterprise, tarif non public). Clients cités (Klarna, FM Logistic…) : ANNONCÉ via la presse. | **La cascade d'évaluation** (tests de difficulté croissante, on avance si les étapes précédentes réussissent) ; le mélange rapide / fort ; un évaluateur « juge LLM » pour critères mous. | stdlib. Copier le service géré = dépendance à Google. Mesure : part des candidats éliminés à l'étage 1 ; coût total d'évaluation avant / après. |
| **FunSearch** (DeepMind) — SURVOLÉ | Ancêtre d'AlphaEvolve (une fonction, îles). | Apache-2.0 · 1 140 étoiles · **inactif depuis 05-02-2024** | rien de neuf | — |
| **CodeEvolve** (Inter&Co, science-codeevolve) — LU (README + résumé arXiv 2510.14150, révisé en mai 2026 : les chiffres ont changé entre versions) | Îles, croisement, méta-prompt évolué, exploitation en profondeur. Revendique d'égaler AlphaEvolve sur 5 des 9 problèmes et de battre OpenEvolve / ShinkaEvolve sur 6 (ANNONCÉ), avec Qwen3-Coder-30B à environ 10× moins cher (ANNONCÉ). | Apache-2.0 · 153 étoiles · push 29-10-2026 · v0.3.0 | Preuve qu'un modèle ouvert moyen suffit sur une tâche bornée → soutient « stratège fort / exécutant économe ». Son **mode MOCK** (faux modèle) pour tester la boucle sans coût : à copier pour nos bancs. | stdlib (idée). |
| **CodeEvolve Java/Apex** (arXiv 2605.04677, mai 2026) — LU (résumé seulement) | Les **profils d'exécution** choisissent QUOI optimiser ; recherche arborescente (MCTS) sur les éditions ; filtre « construction + tests + analyse statique + relecture ». ANNONCÉ : 15,22× de moyenne sur 7 fonctions chaudes d'un code d'entreprise. | Pas de dépôt trouvé | Choisir les cibles par coût mesuré (nous le faisons pour la ligne, pas pour la fonction) ; arbre d'essais avec visites. | Moyen. Gain annoncé sur le code d'une seule entreprise. |
| **GEPA / DSPy** — LU (README ; papier arXiv 2507.19457, ICLR 2026) | Optimise tout texte (prompts, mais aussi code) par **réflexion** : un modèle lit les traces (erreurs, sortie du profileur) et propose une version corrigée ; sélection sur un front de Pareto. ANNONCÉ : bat GRPO de 6 % avec jusqu'à 35× moins d'essais. | MIT · GEPA 7 261 étoiles, push 03-11-2026, v0.1.4 (15-07-2026) ; DSPy 38 910 étoiles. Adoption large (DSPy, MLflow, Google ADK) ; usages de production déclarés au README, non vérifiés. | **L'indice du juge en texte** (« Actionable Side Information ») qui alimente la réflexion suivante ; **Pareto par cas de test** (garder un candidat qui gagne sur un sous-ensemble). | stdlib (idée). La bibliothèque est lourde : non. Mesure : tours jusqu'au gain validé, avec / sans indices. |
| **AdaEvolve, BaSE, EvoAlloc, CostAda** (arXiv 2602.20133, 2605.29268, 2610.12086, 2607.26828 ; 2026) — LU (résumés), tout ANNONCÉ | Quatre papiers sur **l'allocation du budget** : où dépenser (quel parent, quelle branche, quel modèle), quand arrêter. EvoAlloc : −59 à −82 % d'évaluations complètes, −61 à −89 % de jetons (base : ShinkaEvolve). CostAda : tient compte du coût réel de chaque action et du budget restant. BaSE : +12,3 % de fitness (bandit entre trajectoires). | Recherche récente, non répliquée, **aucun code lu**. Lien d'AdaEvolve avec SkyDiscover (Apache-2.0, 733 étoiles, push 14-09-2026) : NON confirmé. | **La piste n° 1 de l'axe 2.** (1) bandit sur les branches (cibles) ; (2) évaluation complète seulement si un pré-test bon marché dépasse un seuil ; (3) le coût en euros dans la récompense (le relais le compte déjà) ; (4) arrêt d'une branche après N essais sans gain. | stdlib. Risque : mesuré sur des problèmes de type mathématique, pas sur du code de production fragile. Mesure : courbe « meilleur gain validé selon la dépense cumulée ». |
| **« Evolution or Illusion? »** (IBM, arXiv 2609.19799) — LU (résumé) | On ne classe pas des méthodes sur un seul budget et une graine ; parfois plusieurs graines courtes valent mieux qu'une longue. | — | Un **protocole de mesure honnête** : rapporter la frontière graines × itérations. | Aucun code ; de la discipline. |
| **TTT-Discover, ThetaEvolve, Guidance-TTT** — LU (résumés) | Apprentissage au moment du test : le modèle est entraîné pendant la résolution. | TTT-Discover (MIT, 653 étoiles) : « quelques centaines de dollars par problème » ; ThetaEvolve (Apache-2.0, 183 étoiles) : au moins 8 GPU de 80 Go ; Guidance-TTT (dans `reef`, Apache-2.0). | **Hors de portée** (GPU). Seule idée récupérable : séparer un petit « conseiller de stratégie » et un écrivain de code (nous l'avons déjà). | — |
| **PIE, Effi-Learner / SOAP, Afterburner, PerfCoder, Feng et al. AAAI 2026** — LU (résumés) / SURVOLÉ | Modèles affinés ou boucles « mesurer puis renvoyer le profil au modèle » pour la vitesse du code. ANNONCÉ : PerfCoder 2,50× avec un 7B ; Afterburner pass@1 47 → 62 % ; Effi-Learner −87 % de temps sur un cas. | PIE inactif depuis 04-2024, licence non déclarée ; Effi-Learner MIT, 15 étoiles | **Effi-Learner = ce que fait déjà notre profil des lignes.** Les modèles affinés : recherche, non livrés en produit. L'entraînement est hors moteur. | Mesurer sur NOS cibles avec NOTRE juge, jamais croire les chiffres sur PIE. |
| **EvoControl** (QuantaAlpha, arXiv 2601.07348) — LU (README) | Démarrer par plusieurs STRATÉGIES réellement différentes (DP, glouton…), mutation guidée par le retour (corriger la partie fautive, garder la bonne), mémoire de leçons locale et globale. ANNONCÉ : meilleur sur EffiBench-X (4 modèles). Le README dit « 7× » là où le calcul donne ≈ 9,4× : lire avec prudence. | Apache-2.0 · 134 étoiles · push 25-01-2026 | Plusieurs plans distincts au départ (Frugal 2 le fait) ; **mémoire de leçons réutilisable entre cibles** (fichier JSON). | stdlib. |
| **EoH, ReEvo, LLaMEA, LLM4AD** — SURVOLÉ (README) | Heuristiques (TSP, bin packing) par modèle. ReEvo : une **réflexion comparative** courte (« pourquoi A est meilleur que B ») avant de muter. LLaMEA : mode `diff` « économise des jetons ». | MIT / BSD · 133 à 802 étoiles · EoH push 06-08-2026, LLaMEA 29-10-2026 | La réflexion comparative, moins chère que relancer. | stdlib. Recherche académique, pas de production. |
| **Aider (formats d'édition)** — LU (doc) ; blog « AST Edits » 2026 SURVOLÉ | Les formats diff sont « beaucoup plus efficaces en jetons » ; `whole` est le plus simple pour un modèle faible. Un test indépendant de 2026 trouve que la fonction entière est souvent la plus fiable et que le diff unifié strict échoue souvent de format. | — | SEARCH/REPLACE par défaut sur les fonctions longues (> ~40 lignes), entière sur les courtes ou après un échec de diff ; **analyseur tolérant** (espaces, indentation). | Mesure : % de réponses applicables, jetons de sortie par tour, gain par jeton. |
| **Cache de prompt (Anthropic)** — LU (doc, première moitié) | Écriture 5 min = 1,25×, 1 h = 2× ; **lecture = 0,1×** (0,05× sur Sonnet 5.5 et Opus 5.5) ; minimum 512 jetons sur les modèles récents ; correspondance exacte du préfixe ; jusqu'à 4 points d'arrêt. | Tarifs du fournisseur | Ordre : règles → source → profil (point d'arrêt) → essais déjà faits → consigne du tour. Un horodatage ou un compteur dans la partie « stable » casse tout le cache SANS erreur. | stdlib. **À vérifier dans notre relais** : transmet-il `cache_control` et remonte-t-il `cache_read_input_tokens` dans le plafond de dépense ? Je ne l'ai pas lu. |
| **RouteLLM / FrugalGPT** — SURVOLÉ (FrugalGPT : texte non ouvert) | Routage appris ; cascade « petit modèle d'abord ». RouteLLM annonce jusqu'à 85 % de coût en moins (chat général, pas du code de performance). | RouteLLM : Apache-2.0, 5 672 étoiles, **inactif depuis 10-08-2024** | Un routeur appris n'a pas de sens ici (pas de données de préférence). La **cascade** (petit ou gratuit d'abord, fort si le juge rejette) existe déjà (OmniRoute, `CN_course`) ; le bandit la remplace par des mesures. | — |
| **LLMLingua** (Microsoft) — SURVOLÉ | Compression de prompt par un petit modèle. | MIT · 6 799 étoiles · push 10-09-2026 | Peu adapté au code exécutable (la syntaxe compte) ; dépendance lourde. Mieux : compression **déterministe** (la fonction ciblée, les signatures voisines, les lignes chaudes, une ligne par essai passé). | — |

### 3.4 Les idées de l'axe 2, classées

1. **Retour du juge en clair dans le prompt suivant** (tombes visibles avec leur raison) — gratuit, pas de dépendance.
2. **Cache** — ranger le prompt ; vérifier le relais.
3. **Cascade d'évaluation** — compilation + 1 cas, puis tout le corpus, puis la mesure à froid seulement pour un candidat prometteur. Le pré-test peut être le `comparer_local` qui existe déjà.
4. **Diff** avec repli.
5. **Bandit UCB** sur les modèles, coût dans le dénominateur.
6. **Allocation par cible** (le gros sujet des quatre papiers 2026) : arrêter une cible après N essais sans gain, donner plus à celle qui promet. Orfan traite une cible par appel ; c'est donc d'abord l'affaire de la **cascade / course** du noyau (`CN_course`), pas du moteur seul.
7. **Empreinte de nouveauté** sans e5 : arbre normalisé + n-grammes de jetons + Jaccard (voir `CN_EVOLUTIF-SEMANTIQUE.md`, P6, qui propose la même démarche « d'abord sans e5 »).
8. **Plusieurs réponses diversifiées** plutôt que 3 prompts identiques : une température ou une consigne de famille différente par appel (EvoControl).

**Ce que je n'ai pas couvert** (faute de lecture) : l'auto-consistance et les vérificateurs appris. Position raisonnée, non sourcée : quand on peut EXÉCUTER chaque candidat, un vote n'apporte rien ; un vérificateur appris ne se justifierait que comme pré-filtre bon marché, avec nos propres données.

**Retours de production** : je n'ai trouvé AUCUN billet d'une équipe tierce utilisant OpenEvolve ou ShinkaEvolve en production avec des chiffres de coût. Les seuls retours solides (ECO, AlphaEvolve) viennent de Google, qui donne lui-même ses chiffres. En novembre 2026 l'écosystème reste surtout académique.

## 4. Axe 3 — Orfan sur autre chose que du code

### 4.1 Ce qui existe chez nous (lu : `noyau/CN_juge_prompt.py`, `noyau/CN_genomes.py`)

- **Juge de prompts** : variables intactes, longueur, clauses d'interdiction conservées (`clauses_interdiction`), puis un cas ordinaire (schéma de réponse, pas de refus) et **cinq cas piégés à canari** (injection, exfiltration, droits, mandat, frein). Sans modèle : « indéterminé ». Les canaris sont des **chaînes fixes** du fichier.
- **`proposer_prompt`** : jusqu'à 4 réécritures dans un seul appel de la fonction ; seules les acceptées sont rendues ; les refusées reviennent avec la raison, et leur texte est redonné au modèle **dans cet appel seulement**.
- **Juge de politiques** : mêmes clés, nombres, intervalles, planchers, rejeu optionnel.
- **`proposer_politique`** : recherche locale, **sans modèle**, clé par clé : le seuil le plus haut qui garde toutes les alertes suivies d'une action et fait taire le plus de fausses alertes.

### 4.2 Ce qui manque pour que ce soit un vrai moteur

Liste établie en croisant les notes de l'axe 3 avec ce que le code fait réellement :

1. **Une boucle fermée.** Aujourd'hui une demande = une salve de réécritures ; rien ne repart des verdicts. Il faut : proposer → juger → garder → proposer à partir des raisons, avec un **budget** (appels, jetons, temps) et un **arrêt** (aucun gain après k tours).
2. **Une mémoire des échecs qui dure** entre deux demandes, rangée par **grille** (famille de piège × type de réécriture) pour garder de la diversité (Rainbow Teaming, DGM : garder les « mauvaises mais différentes » aide à long terme).
3. **Trois jeux de cas, pas un.** Les cinq pièges sont à la fois le jeu que le proposeur peut deviner et le jeu qui juge. Il faut : entraînement (visible du proposeur), sélection (choisit entre candidats), **réserve scellée** (jamais montrée, consultée à la promotion, renouvelée). Le proposeur ne voit que des verdicts agrégés, jamais le texte des cas réservés.
4. **Canaris tirés au hasard à chaque jugement** (aujourd'hui constants : un prompt évolué pourrait apprendre à ne pas répéter `CANARI-INJ-7F3A` sans résister à l'injection). C'est le plus important contre le Goodhart : variantes de formulation, canaux d'attaque, langues, ordre planté ailleurs que dans une seule variable.
5. **Statistique.** Le modèle est bruité : plusieurs répétitions par candidat, gain minimal exigé, attention aux comparaisons multiples (en testant beaucoup de candidats sur les mêmes cas, on en « gagne » un par hasard).
6. **Anti-Goodhart de politique.** `proposer_politique` optimise et évalue sur la **même** historique (pas de jeu mis de côté), prend la **plus petite mesure suivie** comme plafond (un seul point extrême fixe tout), n'a pas d'intervalle de confiance, et son jugement passe avec une tolérance de rejeu à 100 % (le rejeu ne bloque donc rien). Si le signal est « l'utilisateur a acquitté », la politique apprend à être peu gênante, pas utile.
7. **Hors-politique propre.** Pour estimer ce qu'un nouveau seuil aurait fait, il faut **journaliser la probabilité du choix passé** et exiger un support minimal dans la zone testée (sinon on ne peut rien dire d'une zone jamais explorée).
8. **Promotion encadrée.** Le meilleur candidat est une **PROPOSITION** pour un humain, jamais mise en service seule s'il touche à la sécurité ; retour arrière automatique ; traçabilité (version du juge, jeux utilisés).
9. **Juge immuable.** Orfan ne modifie ni le juge, ni les cas, ni les planchers (déjà la règle du noyau).
10. **Texte venu de l'extérieur = donnée hostile** quand il sert d'exemple d'entraînement (risque d'empoisonnement).
11. **Un plafond de longueur et un arrêt précoce** : les optimiseurs de prompts gonflent (jusqu'à 3× plus longs, SURVOLÉ) et sur-ajustent après quelques étapes.

### 4.3 Fiches — prompts

| Projet | Ce que c'est | Statut · licence · communauté · activité | Ce qu'on en retire | Effort · risques · mesure |
|---|---|---|---|---|
| **GEPA** — LU | Voir § 3.3. Pour les prompts : réflexion en langage naturel sur les échecs + front de Pareto + sélection sur un jeu de validation. | MIT · 7,3 k étoiles · 937 commits sur `main` | Le juge doit rendre un TEXTE riche (quel cas, pourquoi) ; un front de Pareto par famille de pièges ; fusion de deux bons prompts. | stdlib. Risques : sur-ajustement, gonflement, coût, variance. Mesure : score sur réserve scellée, longueur, écart entraînement / réserve. |
| **DSPy** (MIPROv2, SIMBA) — LU (page, partiellement) | « Signatures » de tâche ; l'optimiseur cherche instructions + exemples. MIPROv2 : bayésien. SIMBA : petits lots, cherche les cas à forte variance et ajoute des règles / démonstrations (ces deux noms sont ANNONCÉS : la page lue ne les listait pas). | MIT · 38,9 k étoiles | Évaluer par **mini-lots** pour économiser des appels ; cibler les cas où le prompt est instable (variance), ce qui colle aux pièges. | Dépendance lourde : non ; réimplémenter l'idée. |
| **TextGrad** — LU | Un « gradient » en texte (une critique) rétro-propagé dans une chaîne de variables ; publié dans Nature (19-03-2025 d'après le README). | MIT · 3,8 k étoiles · 140 commits | Une critique **par composant** du prompt, pour savoir quelle partie corriger. | Moyen. Critiques bavardes, dérive. |
| **Trace / OptoPrime** (Microsoft) — LU | Enregistre le graphe d'exécution et envoie un retour riche. | MIT · 764 étoiles · dernière date lisible : 07-02-2025 (peu récent) | Garder une **trace** (entrée, sortie, verdict) comme matière de la mémoire des échecs. | Idée seule. |
| **AdalFlow** — LU | Bibliothèque pour construire et auto-optimiser des applications. | MIT · 4,2 k étoiles | Séparer proprement évaluateur / optimiseur / données. | Idée seule. |
| **OPRO, PromptBreeder, EvoPrompt, ProTeGi** — ANNONCÉ (non relus ici) | OPRO : le modèle voit l'historique (prompt, score) trié et propose le suivant. PromptBreeder : évolue aussi les mutations. EvoPrompt : algorithme génétique. ProTeGi : « gradients textuels » + faisceau + bandit. | Articles de 2023 ; licences non vérifiées | OPRO = la boucle minimale pour démarrer ; ProTeGi = quels candidats évaluer plus. | stdlib. |
| **ACE** (Agentic Context Engineering, arXiv 2510.04618, ICLR 2026) — LU (résumé) | Le contexte est un « carnet de jeu » mis à jour par petites entrées (générer, réfléchir, trier), contre l'effondrement d'un contexte réécrit en bloc. ANNONCÉ : +10,6 % sur des agents, +8,6 % sur des bancs de domaine ; code à github.com/ace-agent/ace (non ouvert). | Recherche | **Mises à jour incrémentales avec validation** : modèle pour la mémoire d'Orfan (leçons, tombes). | stdlib. |
| **Nouveautés 2026** (MAGE arXiv 2607.11944, ESPO) — SURVOLÉ | Compromis stabilité / performance en optimisation multi-composants ; gonflement des prompts de GEPA. Préimpressions. | — | Ne pas citer leurs chiffres comme définitifs. | — |

### 4.4 Fiches — politiques et seuils

Je n'ai lu **aucune page** sur ce volet (le temps est allé aux prompts et à la sécurité) : tout ce qui suit est de la connaissance générale, **ANNONCÉ**, à vérifier avant de s'y fier.

- **Bandits** (Thompson, UCB, contextuels) : choisir entre quelques valeurs de seuil en explorant peu. stdlib : oui. Risque : usages qui changent → fenêtre glissante.
- **Optimisation bayésienne** (processus gaussiens, TPE) : pour 1 à 5 paramètres coûteux. Une recherche aléatoire suivie d'un raffinement local suffit en stdlib.
- **Évaluation hors-politique** (IPS, doublement robuste) : estimer un nouveau seuil à partir des décisions passées. **Open Bandit Pipeline** (st-tech/zr-obp, Apache-2.0 d'après PyPI et un fork ; non vérifié sur le dépôt d'origine) en est la bibliothèque de référence — SURVOLÉ. Notre rejeu en est la version déterministe, valable si TOUTES les décisions passées sont journalisées.
- **RL sûr** : retenir surtout des bornes de confiance sur le gain ET sur le risque, et ne déployer que si la borne basse dépasse l'existant.
- **Recherche locale sur acquittements** : petite variation d'un seuil à la fois, marge minimale, retour arrière automatique.
- **Mesure** : regret cumulé, intervalle du gain hors-politique, taux d'alertes ratées sur un corpus d'incidents scellé.

### 4.5 Fiches — sécurité

**Principe** (confirmé par CaMeL) : la sécurité d'une instance ne dépend jamais d'un prompt évolué. Évoluable = **un détecteur ou un test d'attaque**, sous un **juge déterministe**, sans pouvoir de déploiement automatique.

| Projet | Ce que c'est | Statut · licence · communauté | Ce qu'on en retire | Risques · mesure |
|---|---|---|---|---|
| **CaMeL** (« Defeating Prompt Injections by Design », arXiv 2503.18813, mars 2025) — SURVOLÉ | Un interpréteur Python restreint exécute le plan tiré de la requête de confiance ; chaque donnée porte des **capacités** (provenance, droits) ; des règles déterministes bloquent l'appel d'outil si une donnée non fiable y entre. ANNONCÉ : 77 % des tâches AgentDojo avec sécurité prouvable, contre 84 % sans défense (une autre source dit 67 %). | Recherche (DeepMind + ETH). Dépôt de code : je n'ai **pas pu l'ouvrir** (une adresse a répondu 404, l'autre n'a pas été vérifiée). | Le juge de sécurité ressemble à CaMeL : **règles de flux de données écrites à la main, pas apprises**. Orfan fait évoluer les TESTS d'attaque pour vérifier que ces règles tiennent. C'est déjà l'esprit de notre cage par provenance. | Ne garantit pas toute défense (de l'aveu même des commentaires). |
| **AgentDojo** (ETH, ethz-spylab) — LU | Banc d'attaques et de défenses pour agents. | MIT · 986 étoiles · NeurIPS 2024 · date récente non affichée | La structure : tâche utile + tâche d'attaque + **vérificateur d'état déterministe**. C'est l'état de l'environnement, pas un modèle, qui dit si l'attaque a réussi. | Modèle de test, pas une dépendance. |
| **Rainbow Teaming / RainbowPlus** (arXiv 2402.16822, NeurIPS 2024 ; 2504.15047) — SURVOLÉ | Archive « qualité-diversité » (MAP-Elites) d'attaques : une grille catégorie de risque × style ; on mute une attaque, on la garde si elle est meilleure dans sa case. RainbowPlus garde plusieurs attaques par case. | Recherche · code `knoveleng/rainbowplus` non ouvert | Une grille **canal (courriel, page, pièce jointe, outil) × technique** ; chaque case = un cas piégé. Le verdict « attaque réussie » reste déterministe (canari déclenché ou non). | stdlib faisable. Risque : générateur et juge de même famille de modèles = angles morts communs. |
| **Llama Guard / Prompt Guard / CyberSecEval** (PurpleLlama) / **NeMo Guardrails** (NVIDIA) — LU (pages) | Garde-fous probabilistes (un modèle juge un modèle). CyberSecEval v1-v3 : injection, abus d'interpréteur, injection visuelle. | PurpleLlama ~4,5 k étoiles (évaluations et Code Shield MIT ; **modèles sous licences Llama**, non libres) ; NeMo Guardrails Apache-2.0, ~7,4 k étoiles, v0.24.1 | Bons comme **alarme**, jamais comme seule barrière. CyberSecEval = idées de cas de test. | Ne pas dépendre du modèle Llama Guard (licence). |
| **RuleLLM** (arXiv 2504.17198), **ABLE** (arXiv 2605.21821, mai 2026), Sigma (USENIX Security 2026) — SURVOLÉ | Un modèle écrit des règles YARA / Semgrep / Sigma, les répare par les erreurs du compilateur, les valide dans un bac à sable. ANNONCÉ : RuleLLM 763 règles, précision 85,2 %, rappel 91,8 % (vus sur un site de résumé). | Préimpressions et articles | État de l'art = **« générer, valider, réparer »**, pas de vraie population évolutive : créneau libre pour Orfan. | Voir ci-dessous. |

**Détecteur évolué : le juge qu'il faudrait** (déterministe) : (a) la règle se compile ; (b) rappel mesuré sur un corpus d'attaques connues ; (c) **zéro faux positif** sur un corpus bénin scellé ; (d) coût borné (pas d'expression régulière catastrophique) ; (e) garde-fou de pouvoir : la règle ne peut qu'**alerter ou mettre en quarantaine**, jamais autoriser ni débloquer. Risques : règle trop étroite (sur-ajustement à un exemple), trop large (faux positifs), corpus empoisonné si les exemples viennent de contenu externe.

### 4.6 Fiches — raisonnement et agents

| Projet | Ce que c'est | Statut · licence · communauté | Ce qu'on en retire | Risques |
|---|---|---|---|---|
| **AFlow** (dans MetaGPT) — LU (annonce, ICLR 2025 oral) | Recherche de workflows d'agents par arbre de Monte-Carlo ; le workflow est du code composé d'opérateurs fixes. | MIT · MetaGPT 71,2 k étoiles | Chercher des « recettes » faites d'**opérateurs figés** (lire, résumer, vérifier), pas du code libre. | — |
| **ADAS** — LU | Un méta-agent programme de nouveaux agents. | Apache-2.0 · 1,7 k étoiles | L'idée de la recherche d'agents. | Exécute du code généré : bac à sable obligatoire. |
| **Darwin Gödel Machine** (Sakana / UBC) — LU | Archive d'agents qui modifient leur propre code, validés par des bancs. | Apache-2.0 · 2,5 k étoiles · 5 commits (code de référence) | **L'archive ouverte** (garder des pas de côté non optimaux). L'auto-modification du juge est exclue. | Le README avertit : code non fiable exécuté. |
| **AI Scientist** (Sakana) — LU rapide | Chercheur automatique. | **Licence propre** (dérivée Responsible AI) : incompatible avec une reprise de code · 14,9 k étoiles | rien | — |
| **MaAS, Self-Discover, distillation de traces** — ANNONCÉ, non lus | Architecture d'agents choisie selon la requête ; le modèle compose sa propre structure de raisonnement ; réutiliser de bonnes traces comme exemples. | — | À creuser si besoin. | — |

Pour le raisonnement, la condition d'AlphaEvolve vaut : **tout programme avec un évaluateur automatique fiable peut évoluer ; sans évaluateur fiable, rien ne tient.** C'est pourquoi le raisonnement est la dernière cible d'Orfan, après les prompts et les politiques.

## 5. Précurseurs — idées pas encore en production qui changeraient la donne

| # | Idée | Preuve qu'on en a | Ce que ça change pour Orfan |
|---|---|---|---|
| P1 | **Nos pièces validées deviennent des règles gratuites** : chaque gain prouvé par le juge est abstrait en un patron `(avant, après, condition)`, rejoué sans modèle, promu en recette après revue. | **Partielle.** ECO (Google, 2025) fait ceci à partir des commits, en production chez Google (chiffres ANNONCÉS, SURVOLÉS) ; LILO apprend des bibliothèques par compression (LU) ; la session voisine propose la même chose sous le nom « recettes promues » (`CN_EVOLUTIF-SEMANTIQUE.md`, P3, qu'elle juge « vraiment inédit »). Aucune de ces sources n'a de juge à jeu réservé comme le nôtre. | La bibliothèque de recettes grossit seule ; le coût en jetons baisse avec l'usage. Risque : un patron appris est plus étroit ou plus large que le gain d'origine → conditions de sûreté vérifiées sur l'arbre, revue humaine. |
| P2 | **Allocation du budget entre cibles** décidée par bandit avec le coût réel. | Quatre papiers 2026 (AdaEvolve, BaSE, EvoAlloc, CostAda), tous récents, **sans code lu**, chiffres ANNONCÉS. | Même dépense, plus de gains. Preuve faible : à mesurer chez nous avant d'y croire. |
| P3 | **Sécurité par construction, tests évolués** (CaMeL : règles de flux déterministes ; Orfan fait évoluer les attaques qui les éprouvent). | CaMeL et AgentDojo (papier, banc) ; pas de production grand public vérifiée. | On cesse de chercher « le bon prompt de défense » ; on durcit des règles par adversaire automatique. |
| P4 | **Mémoire en grille (qualité-diversité) des échecs et des attaques.** | Rainbow Teaming, DGM (auto-rapportés, recherche). | Les « mauvaises mais différentes » servent de tremplin ; un échec ne se reproduit pas. |
| P5 | **Mises à jour incrémentales du contexte avec validation** (ACE). | Papier ICLR 2026, gains annoncés par les auteurs. | Une mémoire d'Orfan qui ne s'effondre pas en se réécrivant. |
| P6 | **Détecteurs évolués avec bac à sable** (ABLE). | Préimpression de mai 2026, SURVOLÉE. | Un vrai moteur évolutif de règles de détection : créneau libre. |
| P7 | **Un optimiseur qui détecte son propre sur-ajustement** et s'arrête. | Préimpressions 2026 (pic vers les étapes 4-7 puis chute), tendance claire mais faible preuve. | Arrêt précoce sur réserve scellée : indispensable avant toute boucle de prompts. |

## 6. Feuille de route proposée (à accepter ou refuser, étape par étape)

Chaque étape a sa mesure et son critère d'abandon. **Aucune ne touche au juge du noyau, sauf l'étape 2b, qui est une décision à part.**

**Étape 0 — Banc de mesure (avant tout)**. Un jeu de 10 fonctions pures réelles (tirées des points d'évolution existants), 5 graines, la courbe « meilleur gain validé selon la dépense cumulée » ; un mode MOCK (faux modèle scripté) pour tester la boucle sans coût. *Mesure* : reproductibilité d'un même run. *Jeter si* : la variance entre graines est telle que rien ne se distingue (alors mesurer plus longtemps, pas conclure).

**Étape 1 — Durcir l'existant (jours)**. Noyau d'analyse (§ 2.2), correction des trois recettes fautives (§ 2.1), entrées cruelles et comparaison des exceptions dans `comparer_local`, banc de cas pièges par recette. *Mesure* : zéro régression de faux positif sur le banc ; le nombre de variantes que le juge rejette pour divergence tombe. *Jeter si* : le durcissement fait disparaître un gain réel (alors relâcher la condition cas par cas).

**Étape 2 — 9 recettes à gros gain (R01-R05, R07, R08, R10, R40)** puis, si elles tiennent, la famille B. *Mesure* : part des cibles résolues sans aucun jeton ; gain médian validé par le juge sur le jeu réservé ; taux de rejet par recette (désactiver automatiquement une recette qui dépasse un seuil). *Jeter* : toute recette dont le juge rejette plus d'une application sur cinq ; les recettes de la classe C si le gain mesuré à froid est sous le bruit.
**2b (décision de Drisse)** : renforcer le juge du noyau avec les entrées cruelles et la comparaison des exceptions.

**Étape 3 — Moteur à modèle, les gains sans dépendance (semaine)**. (a) tombes et indices du juge visibles dans le prompt ; (b) ordre du prompt pour le cache + vérification du relais ; (c) diff SEARCH/REPLACE avec repli ; (d) variantes réellement différentes plutôt que 3 prompts identiques. *Mesure* : tours et jetons jusqu'au gain validé ; part des jetons lus en cache ; taux de diff inapplicable ; dépense par run. *Jeter* : le diff si plus de 20 % des réponses sont inapplicables malgré l'analyseur tolérant.

**Étape 4 — Cascade et allocation (semaines)**. Pré-test bon marché avant la mesure à froid ; bandit UCB sur les modèles (récompense = gain relatif / coût) ; arrêt d'une cible après N essais sans gain (côté `CN_course`). *Mesure* : part des candidats éliminés avant l'étage cher ; dépense pour un gain donné, avec / sans bandit. *Jeter* : le bandit si la variance du gain à froid dépasse l'écart entre modèles (récompense bruitée).

**Étape 5 — Mémoire des gains rejouables (P1)**. Patron appris de chaque pièce validée, rejoué avant le modèle, promu en recette après revue humaine. *Mesure* : taux de cibles résolues sans appel de modèle sur un jeu de fonctions NON vues ; taux de rejet du juge. *Jeter* : tout patron dont la condition de sûreté ne s'exprime pas sur l'arbre.

**Étape 6 — Prompts et politiques en vrai moteur**. D'abord, **sans modèle** : trois jeux, réserve scellée, canaris aléatoires, arrêt précoce, plafond de longueur, journal des échecs (§ 4.2, points 1 à 11). Ensuite seulement : réflexion sur traces, Pareto, bandit ; politiques : jeu de validation séparé, hors-politique avec probabilité journalisée. *Mesure* : écart entraînement / réserve (doit rester petit) ; longueur du prompt ; taux d'acceptation de la réserve. *Jeter* : toute boucle dont l'écart entraînement / réserve grandit.

**Étape 7 — Sécurité : tests d'attaque évolués (grille façon Rainbow) puis détecteurs**, sous juge déterministe, sans pouvoir de déploiement, avec revue humaine de toute promotion. *Mesure* : nouvelles attaques trouvées qui font tomber une règle existante ; faux positifs sur corpus bénin scellé (doit rester à zéro). *Jeter* : tout générateur dont les attaques ne sont pas jugées par un vérificateur d'état déterministe.

**À écarter dès maintenant** : RL au moment du test, modèle affiné maison, e-graphs et superoptimiseurs, dépendance à Ruff / DSPy / Hypothesis / GEPA dans le chemin d'exécution, les recettes de la classe D.

### Décisions que tu dois prendre

1. Veux-tu **renforcer le juge du noyau** (entrées cruelles, comparaison des exceptions) ? Sans lui, le durcissement des recettes reste côté moteur seulement.
2. **Ordre** : on commence par l'étape 0-1-2 (gratuit, sûr) ou par l'étape 3 (jetons) ?
3. Acceptes-tu qu'une recette **apprise** (étape 5) soit promue **après revue humaine**, jamais seule ?
4. Pour les **prompts** : acceptes-tu des canaris **aléatoires** (changement du juge de prompts) et une **réserve scellée** ?
5. Pour la **sécurité** : confirmes-tu qu'Orfan ne produit jamais qu'une proposition, sans mise en service automatique ?
6. Veux-tu que je regarde d'abord **le relais de modèles** (cache, jetons de cache dans le plafond de dépense) ?

## 7. Ce que je n'ai PAS pu vérifier

- **Dates de dernier commit** des projets des axes 1 et 3 : les pages GitHub lues ne les affichent pas (axe 2 : dates lues par l'API, donc vérifiées). Les étoiles et licences viennent des pages lues le 04-11-2026.
- **Licences non lues** : Hypothesis, CrossHair (seule la mémoire dit MPL-2.0 pour Hypothesis), Z3, PIE, Mercury (aucune licence indiquée sur la page), Sourcery (propriétaire, non vérifié), Open Bandit Pipeline (lue sur PyPI et un fork, pas sur le dépôt d'origine).
- **Aucune des 46 recettes n'est implémentée ni testée une à une.** Seules les affirmations étiquetées MESURÉ ont été exécutées (par le lecteur de l'axe 1, et les trois cas limites de § 2.1 par moi). Les gains varient avec Python (3.11 à 3.14), le système et les données ; les spécialisations de 3.11+ réduisent plusieurs gains « local contre global ».
- **Tous les chiffres des papiers de 2026** (AdaEvolve, BaSE, EvoAlloc, CostAda, MAGE, ABLE, CodeEvolve Java/Apex, PerfCoder, Afterburner…) et ceux d'ECO, AlphaEvolve, CodeEvolve, GEPA, CaMeL, RuleLLM : **ANNONCÉS par leurs auteurs**, non reproduits, la plupart sans code lu.
- **Pas lus du tout ou seulement en résumé** : le texte complet d'ECO, de PIE, de Mercury, de FrugalGPT ; la page de limites de CrossHair ; les règles Semgrep Python ; les papiers complets (AlphaEvolve et ShinkaEvolve : début seulement).
- **Volet politiques / seuils** (bandits, optimisation bayésienne, hors-politique, RL sûr) : aucune page lue, tout est de connaissance générale.
- **CaMeL** : le dépôt de code n'a pas pu être ouvert ; deux chiffres (67 % et 77 %) circulent. **OPRO, PromptBreeder, EvoPrompt, ProTeGi, MaAS, Self-Discover** : non relus. **AI Scientist** : lu en diagonale.
- **AlphaEvolve Cloud** : les sources se contredisent (disponible en juillet 2026 ou aperçu restreint).
- **Auto-consistance et vérificateurs appris** pour la performance du code : non recherchés en détail.
- **Billets de production tiers** (OpenEvolve, ShinkaEvolve) : aucun trouvé. Cela ne prouve pas qu'il n'en existe pas.
- **Notre relais de modèles** : je n'ai PAS lu son code ; je ne sais pas s'il transmet `cache_control` ni s'il compte les jetons de cache.
- **`docs/CN_EVOLUTIF-SEMANTIQUE.md`** : je n'en ai lu que les titres ; mes renvois (P3, P6) s'appuient sur eux et non sur le détail.
- **Aucune expérience** n'a été faite sur Orfan lui-même (pas de modèle branché, pas de banc de 10 cibles) : tout gain annoncé pour Orfan est une hypothèse à mesurer à l'étape 0.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->
