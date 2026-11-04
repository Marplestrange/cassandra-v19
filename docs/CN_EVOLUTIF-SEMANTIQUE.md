<!-- ═════════════════════════════════════════════════════════════════
<!-- TITRE      : Évolutif et le sens : propositions à débattre -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Propositions concrètes pour mettre le sens (multilingual-e5-large) au service du moteur Évolutif, classées, avec la façon de les mesurer et un plan en étapes. -->
<!-- MÉTHODE    : on part de ce que fait déjà OpenEvolve (docs/CN_OPENEVOLVE-LECTURE.md) et de ce que fait déjà notre code ; chaque idée dit ce qui est prouvé et ce qui est une hypothèse. -->
<!-- ═════════════════════════════════════════════════════════════════
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=7b67e5 ▼▼▼ -->
# Évolutif et le sens : propositions à débattre

Statut : 04-11-2026. **Rien n'est construit.** Ce document propose, Drisse tranche. Il s'appuie sur `docs/CN_OPENEVOLVE-LECTURE.md` (ce qu'OpenEvolve fait) et sur la lecture de notre code : `orfan/CN_evolutif.py`, `orfan/CN_orfan.py`, `orfan/CN_moteur_hote.py`, `noyau/CN_moteurs.py`, `noyau/CN_evolution.py`, `noyau/CN_encodage.py`, `modules/bibliotheque/CN_module.py`, `docs/CN_FRUGALEVO.md`.

## 0. Ce qui est prouvé, ce qui ne l'est pas

**Aucun chiffre mesuré avec e5-large n'est donné ici.** `sentence_transformers` n'est installé ni sur cette machine ni dans le Python système d'Orion. Il est installé dans le venv d'Orion (`/opt/cassandra/venv`, sentence-transformers 6.1.0, torch 2.14), mais les poids de `intfloat/multilingual-e5-large` (~2,2 Go) n'y sont pas, à ma portée, dans un cache lisible. Les télécharger est une décision de Drisse (2,2 Go, depuis huggingface.co, sur la machine de production) : je ne l'ai pas prise. Le script d'essai est en § 6, prêt à lancer. Toute phrase ci-dessous du genre « devrait » est une **hypothèse**.

Ce qui est **établi par la lecture du code** :

1. **Ce que le modèle reçoit des tombes aujourd'hui, c'est un nombre.** `noyau/CN_evolution.py` passe `contexte["tombes"]` = la liste des empreintes (des hachages) ; `orfan/CN_orfan.py:construire_prompt` n'en tire que « N variante(s) ont DÉJÀ échoué ». La table `tombes(gid, ast, raison, ts)` ne garde NI le texte de la variante NI l'idée (l'hypothèse). On ne peut donc, aujourd'hui, ni dire au modèle QUOI ne pas refaire, ni comparer une idée nouvelle à une idée morte. C'est le préalable de presque tout.
2. **Les tombes ne reconnaissent que l'identique** (`empreinte_ast` : l'arbre syntaxique brut). Renommer une variable change l'empreinte : la même idée repasse.
3. **Évolutif a 2 générations, 2 parents, un `budget` de 3 sorties** (`MoteurEvolutif.__init__`, `proposer`), une archive d'au plus quelques niches (`lignes // 4`). Le juge n'évalue au plus que `budget` candidats (`CN_evolution._juger`: `candidats[:budget]`). Les gains de calcul du juge sont donc bornés ; **la vraie dépense à réduire, ce sont les jetons du modèle** (relais, `CN_moteurs.MoteurProcessus`) et le temps de `comparer_local`.
4. **Le moteur tourne dans une cage sans réseau** et ne parle au serveur que par des lignes JSON (`CN_moteur_hote.py`, `{"op":"modele"}`). Rien n'y encode.
5. **Il n'y a que 52 points d'évolution** (`docs/CN_EVOLUTION.md` § 7 ter). Toute idée qui « apprend des résultats passés » démarre avec très peu de données : c'est le premier risque de chaque proposition d'apprentissage.
6. **e5 est un modèle de langue naturelle** (`CN_encodage._prefixe` : préfixes « query: » / « passage: »). Ses seuils mesurés dans la bibliothèque (bruit à 0,81, vrai rapport > 0,82) sont des seuils de PROSE FRANÇAISE. Pour du code, ils ne valent rien tant qu'on n'a pas mesuré : les cosinus de e5 sont tassés vers le haut, deux codes Python se ressemblent beaucoup quel que soit leur contenu (hypothèse forte, à vérifier par l'essai E1).

**Règle de tout le document : le sens n'est JAMAIS une preuve.** Le contrôleur du noyau reste le seul juge. Le sens sert à **ne pas dépenser** (jetons, évaluation) et à **mieux choisir où chercher**, jamais à déclarer qu'une variante est bonne ou fausse. Une proximité sémantique ne peut donc écarter qu'une variante dont l'écart est « sans gain », jamais « fausse » : une variante fausse mais très proche d'une bonne peut n'avoir qu'un caractère de trop.

## 1. Où se trouve le sens utile : trois étages

Un constat tiré de la lecture d'OpenEvolve (son filtre agit après l'évaluation, donc n'économise rien) et de notre cage :

- **Étage A, côté serveur, avant la cage.** Le noyau a le modèle. Il peut préparer le contexte : retrouver des idées mortes, des astuces réussies, et les mettre en texte dans `contexte` avant de lancer le moteur. **Aucun guichet d'encodage n'est nécessaire.** C'est le moins cher et le moins risqué.
- **Étage B, dans la cage, avec un « guichet de sens ».** Le moteur demande, en cours de recherche, « cette idée ressemble-t-elle à une idée morte ? ». Il lui faut un guichet.
- **Étage C, après la cage, côté serveur.** Choisir quelles sorties du moteur envoyer au juge (diversité des 3 sorties). Aucun guichet non plus.

### Le guichet de sens (étage B) : sa forme

Même esprit que le relais de modèles : le moteur n'a jamais le modèle ni les vecteurs ; il pose une question, le serveur répond, compte et plafonne.

```
moteur  -> serveur {"op":"sens","action":"proches","textes":["…idée ou code…"],"contre":"tombes","k":3}
serveur -> moteur  {"ok":true,"voisins":[[{"id":"t41","cos":0.93,"raison":"gain insuffisant…"}], …]}
              ou  {"ok":false,"erreur":"sens indisponible"}      (service pas prêt, plafond atteint)
```

- **Il rend des voisins (identifiant, cosinus, raison), jamais des vecteurs.** Les ensembles de comparaison (« tombes de CE point », « astuces ») restent côté serveur, cloisonnés ; le moteur ne peut ni les lire en entier ni exfiltrer un vecteur. Les vecteurs des tombes sont calculés une fois et gardés en base (1 024 réels = 4 Ko par ligne en float32).
- **Côté serveur** : dans `noyau/CN_moteurs.py`, la boucle de `MoteurProcessus.proposer` traite aujourd'hui `op == "modele"` ; on y ajoute `op == "sens"`, qui appelle `noyau.CN_encodage.service().encoder(textes, "query")` puis compare. **Côté cage** : `orfan/CN_moteur_hote.py` ajoute à `modele()` une fonction jumelle `sens()`, passée au moteur comme paramètre optionnel (`MoteurEvolutif(orfan, modele, sens=None)`).
- **Comptage et plafond**, comme le relais (`Registre.noter_relais`): par moteur et par jour, nombre d'appels, de textes, de signes encodés ; un plafond (`plafond_sens_jour`) ; au plafond ou si `service().pret()` est faux, réponse « indisponible ». **Le moteur doit toujours savoir se passer du guichet** (retour à l'empreinte d'arbre) : la bibliothèque n'est pas installée partout, le modèle pèse 2,4 Go.
- Taille bornée : 16 textes par appel, 2 000 signes par texte (e5 coupe de toute façon à 512 jetons).

## 2. Les propositions

Pour chacune : (a) quoi · (b) où dans le code · (c) comment e5 sert, ce qui est encodé · (d) gain et mesure · (e) coût · (f) risques · (g) expérience minimale.

### P0 — Préalable sans e5 : que les tombes gardent l'idée, et que le modèle la voie

(a) On grave dans chaque tombe le **texte** de la variante et son **hypothèse** (la phrase du modèle), et le prompt montre au modèle les 3 à 5 dernières idées mortes **en mots**, pas un nombre.
(b) `noyau/CN_evolution.py` : table `tombes` (colonnes `texte`, `hypothese`, créées par `ALTER TABLE ... ADD COLUMN`), `_tomber`, `tombes()` rend aussi le détail ; `_juger` donne dans `contexte` une liste `idees_mortes: [{hypothese, raison}]` en plus des empreintes. `orfan/CN_orfan.py:construire_prompt` (ligne `tombes`) et `orfan/CN_frugal.py` (même phrase) listent ces idées.
(c) Pas d'e5. C'est de la donnée.
(d) Gain attendu : le modèle cesse de reproposer ce que le prompt lui nomme. **Hypothèse** (c'est le comportement général des modèles quand on leur liste des échecs, pas une mesure chez nous). Mesure : sur N recherches, la part de sorties dont l'idée est dans une tombe (jugée à la main sur 50 cas) avant / après. Et dès aujourd'hui : **commencer à écrire le texte des tombes**, parce que sans cet historique aucune des idées de sens ne peut se tester sur le passé.
(e) Coût : quelques centaines de signes de prompt en plus ; base un peu plus grosse. Zéro mémoire.
(f) Risque : un prompt plus long qui pousse le modèle vers des idées trop différentes et inutiles ; une tombe « divergente » qui n'attendait qu'un petit correctif peut décourager une bonne idée (on étiquette donc la raison dans la liste : « fausse sur telle entrée » ≠ « sans gain »).
(g) Expérience : ajouter les deux colonnes et les écrire, sans changer le prompt, pendant quelques semaines ; puis comparer.

### P1 — Entonnoir de l'idée avant le code (la plus prometteuse pour les jetons)

(a) Avant que le modèle économe n'écrive du code, on compare l'**idée en prose** aux idées mortes et aux idées déjà retenues dans la recherche en cours ; une idée trop proche d'une idée « sans gain » ne passe pas à l'écriture.
(b) Pour Frugal 2 : entre « le modèle fort propose 2-3 plans » et « le modèle économe les implémente » (`orfan/CN_frugal.py`, là où `_appeler(prompt, "executant")` est lancé par plan). Pour Évolutif : la phrase d'hypothèse qui précède chaque bloc (`extraire_blocs`) existe déjà APRÈS le code, donc le filtre sert à ne pas **évaluer** (économie de `comparer_local`, pas de jetons) ; pour économiser des jetons il faudrait un appel de stratégie préalable, c'est-à-dire adopter la forme de Frugal 2.
(c) e5 est ici dans son élément : on encode une **phrase de langue naturelle** (« remplacer la recherche dans une liste par un ensemble »), jamais du code. Les idées mortes viennent de P0. Via le guichet (étage B), `contre: "tombes"`.
(d) Gain : jetons de l'exécutant non dépensés sur des idées déjà mortes. **Hypothèse** : dépend du taux de répétition d'idées chez nos modèles ; on ne l'a pas mesuré. Mesure : (1) rejouer sur l'historique P0 : pour chaque idée morte, dire si une idée plus ancienne du même point était à plus de `s` de cosinus ; compter les paires et vérifier à la main 30 paires (précision du filtre) ; (2) en ligne : jetons de l'exécutant par gain prouvé, avec et sans filtre, sur les mêmes points (les points se répartissent au hasard en deux bras).
(e) Coût : 1 à 5 phrases encodées par recherche (courtes) ; le modèle 2,4 Go doit être résident, déjà payé si la bibliothèque s'en sert. Latence : **non mesurée** (E3).
(f) Risques : deux idées proches en prose mais différentes en effet (« utiliser un ensemble » pour deux structures différentes) ; faux rejets d'une bonne idée. Garde-fous : (i) on ne rejette que sur des tombes de raison « gain insuffisant » ; une tombe « divergente » ne bloque pas, elle s'affiche comme contre-exemple ; (ii) seuil prudent ; (iii) 1 idée sur 5 laissée passer même si « proche » (tirage à graine fixe) pour mesurer le taux de faux rejets ; (iv) l'idée rejetée est journalisée avec sa voisine, lisible par Drisse.
(g) Expérience minimale : E2 (§ 6) : 40 phrases d'hypothèse réelles ou écrites à la main, regroupées à la main en familles ; vérifier que le cosinus sépare « même idée » de « autre idée » (aire sous la courbe ROC ≥ 0,9, sinon on abandonne).

### P2 — Bibliothèque d'astuces retrouvées par ressemblance (transfert d'une fonction à l'autre)

(a) Chaque gain **prouvé par le juge** devient une fiche : famille, phrase simple (« remplacer une liste par un ensemble pour tester l'appartenance »), l'avant/après en quelques lignes, le gain mesuré, le point d'origine. Face à une nouvelle fonction, on retrouve les 2 fiches les plus proches par le sens et le prompt les montre : « ailleurs dans la maison, cette astuce a donné ×1,8 ».
(b) Table nouvelle côté noyau (près des tombes, `noyau/CN_evolution.py`, écrite à l'écriture d'une pièce `_ecrire`). Récupération **côté serveur, à l'étage A** : `_juger` ajoute `contexte["astuces"]` avant de lancer le moteur. **Pas de guichet.** Le prompt (`construire_prompt`) gagne une section.
(c) On encode (1) la phrase simple de la fiche, (2) un petit descripteur du point : sa « ligne chaude » (`point_chaud`) et le début de la fonction, en texte. Requête : le même descripteur de la nouvelle fonction (`genre="query"`). Les deux côtés sont **du texte court**, et la phrase est de la langue naturelle (point fort d'e5).
(d) Gain : un modèle à qui l'on montre un exemple d'avant/après de la même famille réussit plus souvent (résultat général des invites par exemples, **hypothèse ici**). Mesure : taux de points qui reçoivent au moins un gain prouvé, avec et sans fiches, sur un tirage au hasard des 52 points ; et jetons par gain. **Démarrage à froid** : au début il y a 0 fiche. Remède honnête : écrire à la main un **manuel de 30 à 50 astuces Python** (compréhension plutôt que boucle, `str.join`, ensemble pour l'appartenance, `dict.get`, éviter de recalculer dans la boucle, `bisect`, etc.), chacune avec avant/après ; c'est du contenu, pas de l'IA, et il vaut déjà quelque chose sans e5 (on peut les montrer toutes, ou celles qui correspondent à des mots-clés).
(e) Coût : une fiche encodée = une fois ; recherche en mémoire (quelques centaines de fiches au plus, produit scalaire direct). Jetons : 300 à 600 signes par fiche montrée, donc le prompt grossit. Il faut que le gain en réussite le justifie.
(f) Risques : fiches trop locales à une fonction (l'astuce ne se transpose pas) ; biais (on ne propose que ce qu'on a déjà trouvé et on ferme l'exploration : à compenser en laissant toujours un essai sans fiche) ; fuite entre comptes (les fiches contiennent du code de la maison, pas des données ; le cloisonnement par compte doit être vérifié).
(g) Expérience minimale : écrire 30 fiches à la main ; prendre 10 points ; pour chacun, vérifier à la main si les 2 fiches les plus proches par e5 (E4) sont celles qu'on aurait choisies (rappel@2).

### P3 — Recettes promues : l'astuce répétée devient une règle gratuite  *(vraiment inédit)*

(a) Quand une même famille d'astuce a réussi sur au moins 3 points différents, le système propose d'en faire une **règle déterministe** de plus pour `REGLES` (`orfan/CN_orfan.py`: `_CompDansAgregat`, `_TriPourExtremum`…) : zéro jeton à l'avenir.
(b) Détection de répétition par la bibliothèque de P2 (regroupement des fiches de cosinus élevé et de même famille). L'écriture de la règle reste un travail d'ingénieur (ou d'un modèle fort, puis relu et éprouvé par le banc), **jamais automatique**; la règle suit le chemin normal de revue du dépôt.
(c) e5 sert uniquement à regrouper les phrases de fiches (langue naturelle).
(d) Gain : le moteur apprend, au fil des gains payés en jetons, des recettes gratuites. À long terme, c'est la seule idée qui **baisse le coût de façon cumulative**. Hypothèse : il faut assez de gains pour que 3 se ressemblent ; avec 52 points, il y en aura peu ; à voir sur le journal de P0/P2. Mesure : nombre de règles promues, et part des gains obtenus à zéro jeton avant / après.
(e) Coût : surtout humain (écrire/relire une règle).
(f) Risque : une règle fausse dans la bibliothèque des règles gratuites est pire qu'une mauvaise idée de modèle (elle s'applique partout) ; le juge du noyau la contrôle sur chaque point comme toute variante, mais il faut un banc de la règle seule.
(g) Expérience minimale : relire les gains réels déjà obtenus (`docs/CN_EVOLUTION.md` § 7 bis) et regarder à la main si deux d'entre eux relèvent de la même famille.

### P4 — Niches par famille d'idée, plutôt que par taille de code

(a) Aujourd'hui `MoteurEvolutif._niche` = nombre de lignes // 4. On proposerait : niche = **famille de l'hypothèse** (« éviter une liste intermédiaire », « sortie anticipée », « structure de données », « précalcul hors de la boucle », « fonction de la bibliothèque standard »…).
(b) `orfan/CN_evolutif.py:_niche` et la façon de choisir un parent d'une autre niche (`pool.append(rng.choice(sorted(autres)))`) : au lieu du hasard, prendre le parent **le plus éloigné** de ceux déjà retenus.
(c) Classification **sans entraînement** : une liste fixe de 8 à 12 phrases-types (les « prototypes »), écrites à la main, encodées une fois ; l'hypothèse de chaque enfant est rattachée au prototype le plus proche (guichet `action:"famille"`, ou, mieux, la classification se fait côté serveur et la cage ne reçoit que le nom). Les familles sont lisibles par un humain et servent aussi à P2 et à l'écran.
(d) Gain : à notre échelle (2 générations, 2 parents, 3 sorties) **le gain est faible**: il y aura rarement plus de 5 candidats ; la diversité de nos niches de taille est déjà suffisante pour 5 candidats. C'est une idée qui prend son sens si on augmente nettement les générations. **Hypothèse non prouvée.** Mesure : nombre de familles distinctes dans les 3 sorties finales, et part des gains qui viennent d'une famille différente du premier parent.
(e) Coût : 10 phrases encodées une fois ; une phrase par enfant.
(f) Risques : un jeu de prototypes arbitraire qui range tout dans « autre » ; l'hypothèse du modèle est parfois vide ou générique (« Voici le code »), car `extraire_blocs` prend la dernière ligne avant le bloc. Il faut donc exiger une ligne `Hypothèse :` dans le prompt (voir P7).
(g) Expérience minimale : E2 avec les prototypes : exactitude de rattachement sur 40 phrases étiquetées à la main.

### P5 — Niche par comportement d'exécution (sans modèle de sens)  *(une critique d'OpenEvolve, à comparer)*

(a) Au lieu de ranger les variantes d'après leur texte (taille ou sens du texte), on les range d'après **ce qu'elles font réellement** : un petit descripteur calculé en exécutant sur les entrées visibles : nombre de lignes exécutées par rapport à la référence (le `profil` existe déjà, `orfan/CN_orfan.py:profil`), pic de mémoire, rapport de temps arrondi. Deux variantes de même comportement sont dans la même niche, même si leur texte diffère ; deux variantes de texte voisin mais de comportement différent sont séparées.
(b) `MoteurEvolutif._niche` ; `profil` est déjà là ; `comparer_local` mesure déjà le temps.
(c) **e5 n'est pas utilisé.** Je le propose parce que, pour un problème de vitesse, la mesure réelle est plus fiable que le sens du texte : deux codes très ressemblants par le sens peuvent avoir des vitesses très différentes, et l'inverse.
(d) Gain : meilleures niches sans coût de modèle. À comparer à P4 sur les mêmes recherches. Hypothèse.
(e) Coût : un `profil` par candidat (déjà exécuté pour les points chauds).
(f) Risque : un descripteur bruité (le temps) mal arrondi crée de fausses niches ; préférer le **compte de lignes exécutées** (déterministe, sans horloge).
(g) Expérience : sur 10 points, comparer les niches P5 aux niches `lignes // 4` : combien de variantes sont mises dans la même case à tort, à la main.

### P6 — Déduplication sémantique : à faire d'abord SANS e5

(a) Avant d'évaluer, écarter les enfants qui sont « la même chose autrement écrite ».
(b) `MoteurEvolutif._cle` et `noyau/CN_evolution.empreinte_ast`.
(c) **Étage zéro, certain et gratuit** : une empreinte d'arbre **normalisée** (renommer les variables locales dans l'ordre d'apparition, ordonner les opérandes des opérations commutatives, replier les constantes, retirer les docstrings) attrape renommages et réécritures triviales avec certitude. Étage un, seulement si l'étage zéro ne suffit pas : cosinus e5 sur le code, avec un seuil mesuré (E1) ; il ne sert qu'à **ordonner** (ne pas évaluer en premier ce qui ressemble à un déjà-évalué), jamais à jeter sans autre raison.
(d) Gain : moins d'évaluations redondantes. Hypothèse : la part de doublons réels dans nos sorties n'a pas été mesurée. Mesure : compter, sur les journaux de P0, combien d'enfants différaient par l'arbre brut mais pas par l'arbre normalisé.
(e) Coût de l'étage zéro : négligeable.
(f) Risque : une normalisation qui fusionne deux choses différentes (opérandes non commutatifs : `a - b` ne se réordonne pas ; flottants : `a + b + c` n'est pas associatif). À limiter aux cas sûrs.
(g) Expérience : écrire la normalisation, la lancer sur les 52 points × leurs variantes connues et regarder les fusions à la main.

### P7 — Résumé en mots simples de ce qu'une amélioration a changé

(a) Pour chaque pièce gardée, une phrase que Drisse peut lire : « a remplacé une liste par un ensemble ; la fonction va 1,8 fois plus vite ».
(b) Pour les règles déterministes : déjà fait (`hypothese` de chaque règle). Pour les modèles : exiger dans `construire_prompt` une ligne `Hypothèse : …` fixe avant le bloc ; `extraire_blocs` la lit (aujourd'hui : la dernière ligne avant le bloc, souvent vide ou bavarde, tronquée à 300 signes).
(c) e5 : facultatif, pour rattacher la phrase à une **famille** (P4) et l'afficher. Sans e5, la phrase suffit.
(d) Gain : lisibilité et matière première de P0, P1, P2. C'est un gain de transparence, pas de coût. Mesure : part des pièces dont l'hypothèse est lisible (revue à la main sur 30).
(e) Coût : une ligne de prompt.
(f) Risque : le modèle écrit une explication qui ne correspond pas au code (il l'écrit avant le code). Elle reste une **hypothèse affichée comme telle**, jamais une preuve ; l'affichage dit « idée du modèle ».
(g) Expérience : modifier le prompt dans un banc et compter les réponses avec une ligne exploitable.

### P8 — Choisir les sorties à envoyer au juge (diversité des trois)

(a) Le moteur rend les `budget` meilleurs par rapport de temps ; ces trois peuvent être la même idée. On préfère « le meilleur, puis le meilleur parmi ceux qui diffèrent assez du premier » (MMR : pertinence moins redondance).
(b) `MoteurEvolutif.proposer`, dernière ligne (`classes[:budget]`).
(c) Distance = P5 (comportement) ou famille P4 ou cosinus e5 sur les hypothèses ; au choix, mesurer.
(d) Gain : plus de chances qu'une des 3 passe le juge si la première est une fausse bonne idée sur le corpus entier. Hypothèse. Mesure : taux de recherches où au moins une des sorties est retenue par le juge, avec et sans diversité.
(e) Coût : négligeable. (f) Risque : écarter la 2ᵉ meilleure vraie. (g) Rejouer sur l'historique des sorties.

### P9 — Classement des fonctions à chercher d'abord

(a) Dire quels points méritent qu'on y dépense, d'après ceux qui ont déjà bien réussi.
(b) `noyau/CN_course.py` / la liste des cibles (`Evolution.cibles`), non lus en détail.
(c) **D'abord sans sens** : part du temps réel que le point représente (appels × durée, venant du rejeu), proportion de point chaud (`point_chaud`) ; ces deux nombres sont des mesures. Le sens (voisins par e5 des points qui ont déjà réussi) n'a de sens que **quand il y aura ≥ 50 résultats** ; avec 52 points, un classement par voisinage serait du bruit.
(d)(e)(f) : gain honnête attendu faible à court terme. À reporter.

### P10 — Cartes de proximité entre fonctions de la maison

Même moteur que P2 : trouver des fonctions quasi dupliquées entre modules (un même assistant écrit trois fois). Une optimisation prouvée sur l'une est un **candidat à essayer** sur les autres (`comparer_local` en premier, zéro jeton, puis le juge). C'est le « transfert direct » de P2 poussé jusqu'à l'essai. Hypothèse : la maison contient de tels doublons ; non vérifié. Expérience : encoder les 52 points (code) et regarder les paires ≥ s (E1) à la main.

## 3. Ce qu'OpenEvolve fait et comment on fait mieux, à moindre coût

| OpenEvolve | Limite (cf. lecture § 4) | Notre réponse |
|---|---|---|
| Filtre de nouveauté par cosinus + juge LLM, à l'entrée de la base | Après l'évaluation : ne sauve ni jetons ni temps ; code brut ; un voisin ; seuil 0,99 | P1 : filtrer l'**idée** avant le code ; P6 : normalisation exacte d'abord |
| Pas de mémoire des échecs (traces écrites, non relues) | Les mêmes impasses reviennent | P0 : nos tombes gardent déjà les empreintes ; leur donner texte et idée |
| Diversité = taille + caractères | Pas de sens, pas de comportement | P5 (comportement), P4 (famille) |
| Inspirations = cases voisines de la grille de taille | Voisin = de même taille | P2 (par le sens de l'idée) |
| Pas de cache d'évaluation | Réévalue le même code | Nos tombes + P6 évitent déjà la réévaluation d'un arbre identique |
| Juge de nouveauté = un modèle de langage | Un appel de modèle par comparaison | Chez nous le juge est le **corpus + le jeu réservé** : un « nouveau » n'a pas à être jugé par un modèle, il est mesuré |

## 4. Classement

**Ce qui rapporte le plus pour le moins d'effort**
1. **P0** (tombes avec texte + idées dans le prompt) : une colonne et une phrase ; sans e5 ; condition de tout le reste.
2. **P7** (ligne `Hypothèse :` fixe) : une ligne de prompt.
3. **P6, étage zéro** (empreinte normalisée) : peu de code, certain.
4. **P1** (entonnoir de l'idée) : le meilleur rapport gain/risque *une fois P0 et E2 faits*.
5. **P2** (astuces par ressemblance, côté serveur, sans guichet).

**Ce qui serait vraiment inédit** : **P3** (le moteur gagne des recettes gratuites en apprenant des gains payés) et **P1** (un entonnoir par le sens, appliqué à l'idée en prose avant le code, que ni OpenEvolve ni FrugalEvo n'ont d'après leur code lu). P5 est une critique plus qu'une invention.

**À reporter** : P4 (à notre échelle), P9 (trop peu de points), P10 (à tester sur 52 points d'abord), P8 (petit gain).

## 5. Recommandation et plan en étapes

Je recommande **de commencer sans le modèle**, puis de n'ouvrir le guichet que si les mesures le justifient. Le modèle de sens est un outil pour *retrouver ce qui se ressemble* ; il n'a de valeur que si on a des choses à retrouver (idées mortes, astuces) et cela, on ne l'a pas encore gravé.

- **Étape 0 — accepter ou refuser** (rien d'e5) : P0 (écrire texte et idée dans les tombes ; les montrer au modèle), P7 (ligne `Hypothèse :`), P6 étage zéro. Effort : petit. Arrêt si la part de répétitions d'idées est basse.
- **Étape 1 — mesurer le sens** (accord de Drisse pour télécharger les poids, 2,2 Go, sur Orion, hors serveur de production) : E1, E2, E3, E4 du § 6. **Porte de sortie** : si le code ne se sépare pas du bruit (aire ROC < 0,9) → on n'encode que de la prose (P1, P2 sur phrases) ; si la prose ne se sépare pas non plus → on arrête les idées de sens.
- **Étape 2 — étage A seul** (sans guichet) : manuel de 30 à 50 astuces écrit à la main + P2 par le sens côté serveur. Mesure : gains prouvés et jetons par gain, par bras tiré au hasard.
- **Étape 3 — le guichet de sens** (§ 1) et P1 dans Frugal 2 / Évolutif, avec plafond et repli.
- **Étape 4 — P3** (recettes promues) quand le journal montre 3 astuces de la même famille.
- Ensuite seulement P4, P8, P9, P10.

Chaque étape se juge sur un chiffre simple : jetons du relais par gain prouvé (déjà compté par le registre) et taux de recherches avec au moins un gain retenu par le juge.

## 6. Expériences jetables (non faites ; script prêt)

À lancer sur Orion, hors du serveur Cassandra (processus à part, `nice`, 2 fils, dossier temporaire, rien commité), **après accord pour télécharger les poids** :

```bash
ssh marple@100.93.49.21
mkdir -p /tmp/e5essai && cd /tmp/e5essai
HF_HOME=/tmp/e5essai/hf nice -n 10 /opt/cassandra/venv/bin/python -I - <<'PY'
import time, itertools, statistics, torch
torch.set_num_threads(2)
from sentence_transformers import SentenceTransformer
t0=time.time(); m=SentenceTransformer("intfloat/multilingual-e5-large"); print("chargement s", round(time.time()-t0,1))
# E3 : latence d'un texte court (idée), d'un code de 15 lignes, d'un code de 60 lignes, lot de 8
# E1 : variantes d'une même fonction (renommage, mise en forme, règle d'optimisation) / fonctions différentes
# E2 : phrases d'hypothèse, même famille / autre famille
# Rendre : latence (médiane, p95), mémoire (resource.getrusage), distributions de cosinus, aire ROC
PY
```

- **E1** (code) : prendre ~20 fonctions des 52 points ; pour chacune : (i) la même, renommée ; (ii) reformatée ; (iii) une variante donnée par une règle d'`optimisations()` ; (iv) une variante réelle de modèle ; (v) 19 autres fonctions. Rendre les distributions de cosinus des quatre premiers groupes contre (v) et l'aire ROC « même fonction / autre fonction ». Dit si un seuil de tombe sur du code existe.
- **E2** (prose) : 40 phrases d'hypothèse en français, étiquetées à la main en 6 à 8 familles ; aire ROC même-famille / autre-famille, et exactitude du rattachement au prototype le plus proche.
- **E3** (coût) : temps d'un encodage (idée, 15 lignes, 60 lignes, lot de 8), mémoire résidente, temps de chargement à froid. Orion a 4 cœurs, 15 Go dont ~6 libres au moment où j'ai regardé ; le service partagé fixe `CASSANDRA_EMBED_THREADS` à 2.
- **E4** (récupération) : 30 fiches écrites à la main (P2) ; pour 10 points, rappel@2.

Aucun de ces chiffres n'existe encore.

## 7. Questions à trancher

1. D'accord pour **l'étape 0** (graver le texte et l'idée dans les tombes, la ligne `Hypothèse :`, l'empreinte normalisée) ?
2. D'accord pour **télécharger les poids d'e5-large (~2,2 Go) sur Orion** pour les essais E1-E4 (hors serveur) ? Sinon, sur quelle machine ?
3. Le modèle de sens peut-il rester **résident** (2,4 Go) en permanence pour Évolution, ou seulement chargé à la demande (premier appel lent) ?
4. Veut-on une **règle de prudence** : le sens ne rejette que des idées « sans gain », jamais des idées « fausses » (ma proposition) ?
5. Le **manuel d'astuces** (P2) : est-ce que tu veux le relire / le valider toi-même, ou je le prépare et tu l'approuves ?
6. Les promotions de **recettes gratuites** (P3) : toujours revues par un humain avant d'entrer dans `REGLES` (ma proposition) ?
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->
