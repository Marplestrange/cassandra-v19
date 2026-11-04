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
<!-- RÔLE       : Propositions concrètes pour mettre le sens (multilingual-e5-large) au service du moteur Évolutif, éprouvées par des mesures réelles, classées, avec un plan en étapes. -->
<!-- MÉTHODE    : on part de ce que fait déjà OpenEvolve (docs/CN_OPENEVOLVE-LECTURE.md) et de ce que fait déjà notre code ; chaque idée dit ce qui est mesuré et ce qui reste une hypothèse. -->
<!-- ═════════════════════════════════════════════════════════════════
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=58633e ▼▼▼ -->
# Évolutif et le sens : propositions à débattre

Statut : 04-11-2026, après mesures. **Rien n'est construit dans le dépôt.** Ce document propose, Drisse tranche. Il s'appuie sur `docs/CN_OPENEVOLVE-LECTURE.md` et sur la lecture de notre code : `orfan/CN_evolutif.py`, `orfan/CN_orfan.py`, `orfan/CN_moteur_hote.py`, `noyau/CN_moteurs.py`, `noyau/CN_evolution.py`, `noyau/CN_evaluateur.py`, `noyau/CN_encodage.py`, `modules/bibliotheque/CN_module.py`, `docs/CN_FRUGALEVO.md`.

## Ce qu'il faut retenir en dix lignes

1. **Sur du code, e5-large est inutilisable pour décider.** Une variante **fausse** (une mutation d'un seul signe) est jugée plus proche de l'original (cosinus médian 0,995) qu'un simple **renommage de variables** qui, lui, est correct (0,979) : dans 96 cas sur 100. Le sens ne voit pas le comportement. Il ne peut ni dédupliquer ni filtrer du code. Un modèle spécialisé en code (UniXcoder) fait la même erreur (85 cas sur 100) : c'est le principe du texte, pas ce modèle-là.
2. **Sur des phrases décrivant une idée, e5-large sait reconnaître la même idée reformulée sur la même fonction** (cosinus 0,89–0,98 contre 0,83–0,91 pour des idées différentes), mais seulement sur un petit échantillon (12 textes réels) et avec un seuil étroit.
3. **Il ne sait pas classer des idées en familles** (exactitude 60 % sur 8 familles ; aire ROC 0,66).
4. **Il retrouve mal une astuce à partir d'un bout de code** : 34 % au premier rang (hasard : 7 %), alors qu'un détecteur d'arbre syntaxique est exact pour ces cas.
5. **Le vrai gisement est ailleurs : nos modèles se répètent, et le dire au modèle suffit à l'arrêter.** Sur 4 fonctions réelles, 3 échantillons chacun (même prompt) : 3 fonctions sur 4 ont rendu **la même idée trois fois** ; la 4ᵉ, deux fois sur trois (sur les 8 échantillons n° 2 et 3, 7 répétaient l'idée du premier). Quand on ajoute au prompt « idée déjà essayée : … », **les 8 échantillons suivants ont tous changé d'idée** (une seule avec un recouvrement partiel). Cela ne coûte aucun encodage.
6. **Le moteur Évolutif ignore les tombes** (il ne les sème pas dans son ensemble `vus`) : une variante déjà morte peut occuper l'un des 3 créneaux envoyés au juge. Et le prompt ne donne au modèle que le **nombre** de tombes, jamais leur contenu.
7. **Les 5 recettes gratuites ne s'appliquent à aucune des 98 références réelles** de la maison : la première étape de la cascade n'apporte rien sur le code actuel ; la dépense est tout entière dans le modèle.
8. **Coût mesuré** : une idée (une phrase) = 0,27 s ; un code de 15 lignes = 1,0 s ; 36 des 98 fichiers de référence dépassent les 512 jetons que le modèle lit (le reste est coupé). Le modèle, une fois chargé, occupe 2,7 à 2,9 Go.
9. **Ce que je recommande** : d'abord ce qui ne demande pas e5 (donner le contenu des tombes et des idées déjà tentées au modèle, semer les tombes dans `vus`, empreinte d'arbre normalisée), puis un **guichet d'idées** (phrases seulement, jamais le code), limité au même point. On abandonne l'encodage du code et les familles par prototypes.
10. Le sens n'est jamais une preuve : le contrôleur reste le seul juge.

## 0. Ce qui est mesuré, ce qui ne l'est pas

### 0.1 Conditions des mesures (04-11-2026)

- **Machine** : Orion (Debian 12, 4 cœurs, 15 Go, charge moyenne 2 à 3 pendant les essais : la production tournait). **2 fils de calcul** comme le service d'encodage (`CASSANDRA_EMBED_THREADS`=2), `nice 10`, processus séparé du serveur Cassandra, dans `/tmp/e5essai` (poids téléchargés là : `intfloat/multilingual-e5-large`, 2,2 Go, accord de Drisse). Venv `/opt/cassandra/venv` : sentence-transformers 6.1.0, torch 2.14 (CPU). **Rien n'a été chargé dans le serveur Cassandra, `CASSANDRA_EMBED_MODEL` n'a pas été touché.**
- **Corpus de code** : les **98 fichiers de référence réels** `modules/*/points/EC_*.py` (24 modules ; j'ai écarté les fichiers de moins de 300 ou de plus de 6 000 signes), entre 300 et 6 000 signes (médiane 1 040 signes, 382 jetons). Préfixe `passage: ` comme le service.
- **Variantes fabriquées à partir d'eux** (honnêtement : ce ne sont pas des variantes écrites par un modèle) : *renommage* des variables locales ; *reformatage* (`ast.unparse`) ; *sans docstring* ; *idée inverse* (99 variantes où l'on défait une recette d'Orfan : générateur → liste, `min(x)` → `sorted(x)[0]`, `not x` → `len(x)==0`, `[]` → `list()` : même fonction, une autre idée) ; *mutants* (389 variantes à un signe changé avec le mutateur de `noyau/CN_evaluateur.py`, donc **fausses** par construction ou presque).
- **Phrases** : 48 phrases d'hypothèse que **j'ai écrites** en 8 familles (6 par famille) ; 8 phrases-prototypes. Limite : ce sont mes phrases et mes étiquettes, pas des sorties réelles ; les familles se recouvrent un peu.
- **Hypothèses réelles de modèle** : 12 réponses d'un modèle économe (Claude Haiku, en sous-agent) au **vrai prompt** produit par `orfan.construire_prompt` (sans profil), 3 réponses indépendantes pour chacune des 4 fonctions `agents.coherents`, `courrier.roles_uniques`, `planifie.segments`, `bibliotheque.decouper`. **Je n'ai pas jugé ces réponses** (pas de corpus d'entrées pour les exécuter) : on ne sait pas si elles sont justes ni plus rapides.
- Scripts et résultats bruts : dossier temporaire de ma session, **non commités** (hors dépôt).

### 0.2 Résultats

**Coût (E3)** :

| Quoi | Mesure |
|---|---|
| Chargement du modèle (cache de fichiers chaud) | 3,2 s ; **non mesuré à froid** (disque non vidé) |
| Mémoire du processus | 0,77 Go avant, 1,15 Go juste après le chargement, **2,75 Go à la fin, pic 2,88 Go** |
| Une phrase d'idée (21 jetons) | 267 ms (p95 290 ms) |
| Huit phrases en lot | 903 ms |
| Code de 15 lignes (185 jetons) | 1,0 s |
| Code de 60 lignes (1 380 jetons, **coupé à 512**) | 2,5 s |
| Huit codes de 15 lignes en lot | 7,0 s |
| Les 98 fichiers de référence | 200 s (2 s chacun) |
| Fichiers de référence de plus de 512 jetons | 36 sur 98 (jetons : médiane 382, p95 1 330, max 2 149) |

**Code (E1)**, cosinus entre l'original et sa variante, et entre fonctions différentes :

| Paire | n | min | médiane | max |
|---|---|---|---|---|
| original / reformaté | 98 | 0,961 | 0,995 | 0,999 |
| original / renommé | 98 | 0,945 | **0,978** | 0,996 |
| original / sans docstring | 98 | 0,912 | 0,971 | 0,998 |
| original / « autre idée » (recette défaite) | 99 | 0,960 | 0,992 | 0,999 |
| original / **mutant (faux)** | 196 | 0,961 | **0,995** | 0,999 |
| deux fonctions différentes, même module | 570 | 0,813 | 0,871 | 1,000 |
| deux fonctions différentes, modules différents | 8 936 | 0,779 | 0,859 | 0,960 |

- Pour distinguer « une variante de la même fonction » de « une autre fonction », e5 est excellent (aire ROC 0,998 ; il retrouve l'original au premier rang 95 fois sur 98 pour un renommage ou un reformatage, 91 sur 98 sans docstring). **Mais ce n'est pas la question utile.**
- Question utile : **peut-il séparer le correct du faux, ou une idée d'une simple mise en forme ?** Non. Paires par fonction (50 premières) : le **mutant (faux) est plus proche de l'original que le renommage (correct) dans 96 cas sur 100**, et la variante « autre idée » dans 51 cas sur 52. **Plus un changement est petit dans le texte, plus le cosinus monte, quel que soit son effet.**
- Le maximum de 1,000 entre deux fonctions « différentes » vient de fichiers de référence identiques (du code copié d'un point à l'autre).
- Seuils : à 0,95, 0,4 % de fonctions différentes seraient fusionnées ; à 0,97 : 0,21 % ; mais à 0,97 un simple **renommage n'est reconnu que dans 76 % des cas** et une version sans docstring dans 50 %. Il n'existe pas de seuil qui reconnaisse le renommage sans fusionner aussi les mutants (qui sont à 97 % au-dessus de 0,97).

**Un modèle fait pour le code (E8)** : `microsoft/unixcoder-base` (125 M de paramètres, open source, 143 s pour les 50 premières fonctions et leurs variantes, mêmes variantes que E1). Il sépare bien mieux les fonctions différentes (cosinus médian 0,60 contre 0,86 pour e5) mais **a le même défaut** : le mutant faux est plus proche de l'original que le renommage correct dans **85 cas sur 100** (médianes 0,963 contre 0,918), la variante « autre idée » dans 49 sur 52. Un modèle de code lit toujours le texte, pas le comportement. Je n'ai pas testé d'autres modèles de code (ceux que j'ai vus demandent d'exécuter du code distant au chargement, je les ai laissés).

**Phrases d'idées (E2)**, 48 phrases, 8 familles :

- cosinus de deux phrases de la **même** famille : médiane 0,884 (0,836–0,944) ; de familles **différentes** : médiane 0,872 (0,814–0,943). Aire ROC **0,66** (0,67 avec le préfixe `query:`).
- rattachement de chaque phrase à son prototype le plus proche : **29 sur 48 (60 %)** (hasard 12,5 %).
- Tous les cosinus entre phrases techniques du même domaine sont dans la plage 0,81–0,94 : c'est le « bruit à 0,81 » de la bibliothèque, ici sans signal clair au-dessus.

**Vraies hypothèses de modèle (E5)**, 12 phrases, 4 fonctions × 3 échantillons :

- À la lecture, **les trois échantillons de `bibliotheque.decouper` disent la même chose** (« la recopie répétée du reste du paragraphe ; je passe à un index, je précompile la regex »), idem `agents.coherents` (« un ensemble pour les identifiants attendus »), idem `courrier.roles_uniques` (« remplacer le tri complet par un min »). Pour `planifie.segments`, deux échantillons sur trois proposent la même idée (« découper par regex les commandes simples, laisser shlex pour le reste »), le troisième une autre (« fusionner la lecture en une passe »).
- Cosinus des **10 paires « même idée, même fonction »** (jugées à la main) : 0,980 ; 0,964 ; 0,937 ; 0,933 ; 0,932 ; 0,919 ; 0,916 ; 0,913 ; 0,905 ; 0,888.
- Cosinus des **2 paires « idées différentes, même fonction »** : 0,889 et 0,884. Des **54 paires entre fonctions différentes** : 0,833 à 0,911 (médiane autour de 0,87).
- Donc, **sur cet échantillon**, un seuil à **0,915** donne 7 « même idée » reconnues sur 10 et **aucune fausse fusion** ; à **0,90**, 9 sur 10 mais 2 fausses fusions sur 56 paires de contrôle (les 2 paires d'idées différentes sur la même fonction et les 54 paires entre fonctions) (0,911 et 0,904). **Douze textes, quatre fonctions : ce sont des ordres de grandeur, pas une calibration.**

**Dire au modèle l'idée déjà essayée (E7)** : mêmes 4 fonctions, prompt identique **plus** une ligne « Idées DÉJÀ proposées dans cette recherche (ne les refais pas ; propose une idée d'une AUTRE nature) : <l'hypothèse de l'échantillon 1> », 2 nouveaux échantillons chacun (8 réponses).
- **Sans** cette ligne, parmi les 8 échantillons n° 2 et 3 des quatre fonctions, **7 répétaient l'idée de l'échantillon 1** (seul `planifie.segments` n° 2 avait changé).
- **Avec** cette ligne, **les 8 ont changé d'idée principale** : `agents.coherents` → contrôle rapide du cas déjà cohérent / parcours unique à état ; `bibliotheque.decouper` → précompiler la regex ou la sauter / court-circuiter les paragraphes courts (celle-ci garde aussi « ne joindre qu'une fois », un recouvrement partiel avec l'idée interdite) ; `courrier.roles_uniques` → compteurs sans liste par rôle / `Counter` ; `planifie.segments` → `lru_cache` / `itertools.groupby`.
- Limites : 8 réponses, un seul modèle, une seule idée interdite à la fois, des réponses **non jugées** (rien ne dit qu'elles sont justes ni plus rapides ; certaines sont risquées, par exemple un `lru_cache` qui rend un objet partagé), et le modèle a pu varier « pour obéir » sans trouver mieux.

**Retrouver une astuce (E4)**, 4 cartes d'astuces et 10 cartes-leurres, 99 variantes « idée inverse » à rapprocher de la bonne carte :

- avec **le code entier** comme requête : 7 bonnes sur 99 au premier rang, 16 au deuxième (**hasard : 7 et 14**) : c'est le hasard ;
- avec **seulement les lignes qui diffèrent** (la ligne chaude) : **34 au premier rang (34 %), 39 au deuxième** (hasard : 7 % et 14 %). Mieux que le hasard, mais pour ces quatre astuces **un détecteur sur l'arbre syntaxique est exact à 100 %** (c'est comme cela que les variantes ont été fabriquées).

**Sur le code de la maison (E6)** : les 5 recettes gratuites (`REGLES` d'`orfan/CN_orfan.py`) s'appliquent à **0 des 98** fichiers de référence. Le code actuel est déjà « propre » pour elles.

### 0.3 Ce qui n'a PAS été mesuré

- Le temps à froid (premier appel, disque), la latence quand la machine est plus chargée, ou avec 4 fils.
- Aucune variante **écrite par un modèle** n'a été jugée (ni exécutée) : pas de gain réel mesuré, pas de taux de variantes fausses.
- Le taux de répétition d'idées **entre tombes et nouvelles propositions** : les tombes n'ont jamais gardé leur texte (§ 1), donc l'historique n'existe pas. J'ai mesuré la répétition **entre échantillons d'un même prompt**, ce qui est un autre phénomène.
- Aucune idée de ce que donnerait e5 sur du code **écrit par un modèle** différent de mes variantes fabriquées ; mon résultat sur le code est cependant net sur les mutants (signe changé) et les renommages.
- Pas de test avec le modèle déjà résident du service partagé (autre charge, autre fil).
- Les variantes d'idées proviennent d'un seul modèle (Haiku) et de 4 fonctions ; E7 : 8 réponses seulement.
- La **justesse** et la **vitesse** de toutes ces réponses de modèle : non vérifiées.

## 1. Ce que la lecture du code établit

1. **Le modèle ne reçoit des tombes qu'un nombre.** `noyau/CN_evolution.py` (`_juger`) passe `contexte["tombes"]`, une liste d'empreintes ; `orfan/CN_orfan.py:construire_prompt` et `orfan/CN_frugal.py` n'en tirent que « N variante(s) ont DÉJÀ échoué ». La table `tombes(gid, ast, raison, ts)` ne garde ni le texte de la variante ni son idée.
2. **Évolutif ne sème pas les tombes** (`vus = {self._cle(source)}` seulement, `orfan/CN_evolutif.py`). Le juge les écarte ensuite (`deja_vue`), mais après que `candidats[:budget]` les a comptées parmi les 3 créneaux.
3. **Les tombes ne reconnaissent que l'identique** (`empreinte_ast`, l'arbre syntaxique brut).
4. Évolutif : 2 générations, 2 parents, 3 sorties, niches de `lignes // 4`. Le juge n'évalue que `budget` candidats : **la dépense à réduire, ce sont les jetons du modèle** (relais `CN_moteurs.MoteurProcessus`), pas le calcul du juge.
5. Le moteur tourne dans une cage sans réseau et parle au serveur par lignes JSON (`CN_moteur_hote.py`, `{"op":"modele"}`) ; rien n'y encode.
6. 52 points d'évolution seulement (`docs/CN_EVOLUTION.md` § 7 ter) : toute idée qui « apprend du passé » démarre avec très peu de données.
7. Décision de Drisse (04-11) : **e5-large est résident, chargé à l'installation de Cassandra, et sert aussi à la mémoire.** Le coût mémoire (2,7–2,9 Go) est donc déjà payé : seul le temps de calcul compte pour le guichet, sur une machine partagée avec la mémoire.

**Règle de tout le document : le sens n'est JAMAIS une preuve.** Le contrôleur du noyau reste le seul juge. Le sens sert à **ne pas dépenser** (jetons) et à **mieux choisir où chercher**. Il ne peut écarter qu'une idée « sans gain » ; une idée « fausse » peut n'avoir qu'un signe de trop (c'est exactement ce que les mutants ont montré).

## 2. Où se trouve le sens utile : deux étages

- **Étage A, côté serveur, avant la cage.** Le noyau prépare le contexte : idées mortes, idées déjà tentées, en texte. Aucun guichet.
- **Étage B, dans la cage, avec un « guichet d'idées ».** Le moteur demande en cours de recherche « cette idée ressemble-t-elle à une idée déjà tentée ? ». Il lui faut un guichet.
- (Un étage C, choisir les sorties avant le juge, se fait aussi côté serveur.)

### Le guichet d'idées : sa forme

Même esprit que le relais de modèles : le moteur n'a jamais le modèle ni les vecteurs ; il pose une question, le serveur répond, compte et plafonne.

```
moteur  -> serveur {"op":"sens","action":"proches","textes":["…phrase d'idée…"],"contre":"idees_du_point","k":3}
serveur -> moteur  {"ok":true,"voisins":[[{"id":"t41","cos":0.93,"etat":"morte|tentee","raison":"gain insuffisant…"}], …]}
              ou  {"ok":false,"erreur":"sens indisponible"}      (service pas prêt, plafond atteint)
```

- **Il ne prend que des phrases, pas du code** (mesure § 0.2 : le code ne sert à rien ici, et coûte 1 à 2,5 s). Une phrase = 0,27 s.
- **Il rend des voisins (identifiant, cosinus, état, raison), jamais des vecteurs.** L'ensemble de comparaison (les idées de CE point) reste côté serveur, cloisonné ; les vecteurs sont gardés en base (1 024 réels = 4 Ko par idée).
- **Côté serveur** : `noyau/CN_moteurs.py`, la boucle de `MoteurProcessus.proposer` traite `op == "modele"` ; on y ajoute `op == "sens"` (appel à `noyau.CN_encodage.service().encoder(textes, "query")`). **Côté cage** : `orfan/CN_moteur_hote.py` ajoute à `modele()` une fonction jumelle `sens()`, passée au moteur en paramètre optionnel (`MoteurEvolutif(orfan, modele, sens=None)`).
- **Comptage et plafond**, comme le relais (`Registre.noter_relais`) : par moteur et par jour, appels, textes, signes ; un plafond (`plafond_sens_jour`) ; au plafond ou si `service().pret()` est faux, réponse « indisponible ». **Le moteur doit toujours savoir se passer du guichet.**
- Bornes : 16 phrases par appel, 600 signes par phrase.
- **Le modèle est partagé avec la mémoire** : un plafond de temps de calcul pour que la recherche d'Évolution ne ralentisse pas la mémoire (à 2 fils, une phrase prend 0,27 s ; un lot de 8, 0,9 s).

## 3. Les propositions, après mesures

Pour chacune : (a) quoi · (b) où dans le code · (c) comment e5 sert · (d) gain et mesure · (e) coût · (f) risques · (g) expérience minimale · **verdict**.

### P0 — Que les tombes gardent l'idée, et que le modèle la voie  ·  *sans e5*  ·  **à faire**

(a) On grave dans chaque tombe le **texte** de la variante, son **hypothèse** et le type de raison ; le prompt montre au modèle les 3 à 5 dernières idées mortes **en mots**, pas un nombre. **Et** (P0b), à l'intérieur d'une même recherche, on dit au modèle de la génération suivante les idées déjà proposées dans cette recherche.
(b) `noyau/CN_evolution.py` : table `tombes` (colonnes `texte`, `hypothese` par `ALTER TABLE … ADD COLUMN`), `_tomber`, `tombes()` ; `_juger` ajoute `contexte["idees_mortes"]: [{hypothese, raison}]`. `orfan/CN_orfan.py:construire_prompt` et `orfan/CN_frugal.py` listent ces idées. `orfan/CN_evolutif.py:proposer` ajoute à `vus` les empreintes des tombes (corrige § 1.2) et passe les hypothèses des enfants déjà obtenus au prompt de la génération suivante.
(c) Pas d'e5.
(d) **Mesuré** (E5, E7) : sans la liste, 7 échantillons sur 8 répètent l'idée du premier ; avec la liste d'une idée déjà essayée, 8 sur 8 en changent. **Reste à mesurer** : que les nouvelles idées soient justes et plus rapides (il faut passer par le juge), et l'effet d'une liste plus longue (5 idées) sur la qualité.
(e) Quelques centaines de signes de prompt en plus. Zéro mémoire.
(f) Risque : un prompt qui pousse le modèle vers des idées absurdes « juste pour être différent » ; une tombe « divergente » peut décourager une idée presque bonne (on étiquette donc la raison : « fausse sur telle entrée » ≠ « sans gain »).
(g) Expérience : ci-dessus.

### P1 — Entonnoir de l'idée avant le code, **limité au même point**  ·  *e5 sur des phrases*  ·  **à tenter après P0**

(a) Avant que le modèle économe n'écrive du code, on compare l'**idée en prose** aux idées déjà tentées ou mortes **sur ce point** ; une idée qui reformule une idée déjà tentée (cosinus au-dessus d'un seuil étroit) ne passe pas à l'écriture.
(b) Pour Frugal 2 : entre « le modèle fort propose 2-3 plans » et « le modèle économe les implémente » (`orfan/CN_frugal.py`). Pour Évolutif : il faudrait ajouter une étape de stratégie (aujourd'hui l'hypothèse arrive avec le code), sinon le filtre n'économise que le temps de `comparer_local`.
(c) e5 reconnaît la reformulation d'une même idée sur la même fonction (mesuré : 0,89–0,98 contre ≤ 0,91 pour des idées différentes ; seuil 0,915 : 7 sur 10 reconnues, 0 fausse fusion sur 56 paires de contrôle). Il ne reconnaît **pas** des idées du même genre entre fonctions différentes (E2) : on compare donc **dans le point**, jamais d'un point à l'autre.
(d) Gain : jetons de l'exécutant non dépensés sur des répétitions. **Hypothèse chiffrée par la mesure E5** : dans 3 cas sur 4, 2 échantillons sur 3 étaient des répétitions de l'idée du premier ; un filtre parfait aurait épargné 2 appels sur 3. Mesure à faire : calibrer le seuil sur ≥ 100 paires d'idées **étiquetées à la main**, avec les journaux de P0 ; exiger ≥ 95 % de précision avant de rejeter quoi que ce soit.
(e) Coût : 1 à 5 phrases par recherche, 0,27 s chacune ; le modèle est déjà résident (décision de Drisse).
(f) Risques : seuil calibré sur 12 phrases seulement ; deux idées proches en prose mais différentes en effet ; faux rejet d'une bonne idée. Garde-fous : (i) on ne rejette que si la voisine est « sans gain » ; une voisine « fausse » ne bloque pas ; (ii) 1 idée sur 5 laissée passer même si « proche » (graine fixe) pour mesurer le taux de faux rejets ; (iii) chaque rejet est journalisé avec sa voisine, lisible par Drisse.
(g) Expérience minimale : 100 paires d'idées (réelles, via P0), étiquetage à la main, aire ROC et précision à 0,90/0,915/0,93.

### P2 — Astuces retrouvées pour une nouvelle fonction  ·  **repensée : détecteurs d'abord, e5 en second**

(a) Chaque gain prouvé par le juge devient une fiche (phrase simple, avant/après, gain, point). Face à une nouvelle fonction, on montre au modèle les fiches pertinentes.
(b) Table nouvelle côté noyau ; récupération côté serveur (étage A), `contexte["astuces"]`. **Pas de guichet.**
(c) **Mesuré** : retrouver une carte à partir du **code entier** est du hasard (7 %) ; à partir de la **seule ligne chaude** : 34 %. Un **détecteur sur l'arbre syntaxique** (« cette fonction contient `sorted(x)[0]` ») est exact pour les astuces syntaxiques. Donc : étape 1 = des détecteurs (une dizaine, comme les règles d'Orfan) qui rattachent une fonction à des fiches ; étape 2 (seulement pour les astuces floues, sans motif syntaxique) = e5 sur la **phrase** de la fiche contre la **description de la ligne chaude** par le modèle.
(d) Gain : **hypothèse** (un exemple avant/après de la même famille aide un modèle). Démarrage à froid : 0 fiche et 52 points. Remède : un manuel de 30 à 50 astuces Python écrit à la main. Mesure : taux de points qui reçoivent un gain prouvé, avec et sans fiches, tirage au hasard de bras.
(e) Faible. (f) Fiches trop locales ; fermeture de l'exploration (toujours laisser un essai sans fiche) ; code de la maison dans les fiches (cloisonnement à vérifier).
(g) Expérience : écrire 10 détecteurs + 30 fiches, vérifier à la main leur couverture sur les 98 références.
**Verdict : utile mais surtout par des détecteurs ; e5 y est secondaire.**

### P3 — Recettes promues : l'astuce répétée devient une règle gratuite  ·  **le plus inédit**

(a) Quand une même famille d'astuce a réussi sur au moins 3 points différents, on propose d'en faire une règle déterministe de plus dans `REGLES` (`orfan/CN_orfan.py`) : zéro jeton ensuite.
(b) Détection par les mêmes détecteurs que P2 (pas par e5). L'écriture de la règle reste revue par un humain.
(c) e5 n'est pas nécessaire (les familles viennent des détecteurs, pas des prototypes : E2 les a rejetés).
(d) Intérêt renforcé par la mesure E6 : les 5 recettes actuelles ne s'appliquent à **aucun** des 98 fichiers ; toute nouvelle recette qui s'applique réellement est un gain net. Hypothèse : assez de gains pour que 3 se ressemblent. Mesure : nombre de règles promues, part des gains à zéro jeton.
(f) Une règle fausse s'applique partout : banc propre à la règle, revue humaine.
**Verdict : à garder pour plus tard, sans e5.**

### P4 — Niches par famille d'idée avec prototypes  ·  **REJETÉE**

Exactitude 60 % sur 8 familles, aire ROC 0,66 (§ 0.2), à notre échelle (≤ 5 candidats) : pas de gain attendu. À reprendre seulement si le nombre de générations monte nettement **et** qu'un autre classeur (le modèle lui-même, qui nomme la famille dans sa réponse) est préféré.

### P5 — Niche par comportement d'exécution (sans e5)  ·  **à comparer**

(a) Ranger les variantes d'après ce qu'elles font : compte de lignes exécutées par rapport à la référence (`profil`, déjà là), mémoire. Deux variantes de même comportement sont dans la même niche, quel que soit leur texte.
(b) `MoteurEvolutif._niche` ; `profil` existe.
(c) Pas d'e5, et c'est la leçon de E1 : le texte (et son sens) ne voit pas le comportement ; un mutant faux a un cosinus de 0,995.
(d) Hypothèse. Mesure : sur 10 points, comparer les niches aux niches `lignes // 4` à la main.
(e)(f) : un descripteur bruité (le temps) crée de fausses niches ; préférer le compte de lignes.
**Verdict : meilleur candidat que P4 pour remplacer la niche de taille, à éprouver.**

### P6 — Déduplication de variantes : **empreinte normalisée seulement**  ·  *sans e5*  ·  **à faire**

(a) Écarter les enfants qui sont la même chose autrement écrite.
(b) `MoteurEvolutif._cle` et `noyau/CN_evolution.empreinte_ast`.
(c) **Les cosinus de code sont rejetés** (E1 : aucun seuil ne sépare renommage et mutant). Reste l'arbre normalisé : renommer les variables locales dans l'ordre d'apparition, retirer les docstrings, replier les constantes, ordonner les opérandes des opérations commutatives **sûres** (pas `a - b`, pas les flottants).
(d) Mesure : sur les 98 références, combien de variantes fabriquées (renommage, sans docstring) sont ramenées à la même empreinte (attendu : toutes) et combien de mutants sont à tort fusionnés (attendu : aucun).
(e) Négligeable. (f) Une normalisation qui fusionne deux choses différentes : se limiter aux cas sûrs.
**Verdict : à faire, c'est exact et gratuit.**

### P7 — Résumé en mots simples de ce qu'une amélioration a changé  ·  *sans e5*  ·  **à faire**

(a) Pour chaque pièce gardée, une phrase lisible.
(b) Règles déterministes : déjà faites. Modèles : **mesuré, le modèle économe a spontanément rendu une phrase d'hypothèse bien formée dans 12 réponses sur 12**, avec la cause supposée et le remède (« le temps part de … ; je remplace … »). La ligne `Hypothèse :` fixe dans le prompt reste utile pour que `extraire_blocs` la lise sans deviner (aujourd'hui : la dernière ligne avant le bloc, tronquée à 300 signes).
(d)(e)(f) : transparence, pas un gain de coût ; l'hypothèse reste « l'idée du modèle », jamais une preuve.

### P8 — Diversité des 3 sorties envoyées au juge  ·  *petit*

Choisir « le meilleur, puis le meilleur parmi ceux dont l'**idée** (cosinus des phrases d'hypothèse, seuil 0,915) diffère ». Gain faible à notre échelle, hypothèse ; coût négligeable. À reprendre avec P1 si le guichet existe.

### P9 — Classement des fonctions à chercher d'abord  ·  **reporté**

Avec 52 points et aucun historique, un classement « par ressemblance aux points réussis » serait du bruit (et E1/E4 montrent que le code se ressemble trop). D'abord sans sens : la part du temps réel (appels × durée du rejeu) et la présence d'un point chaud (`point_chaud`) ; **E6 ajoute** : tant que les recettes gratuites ne s'appliquent pas, les points à gros point chaud sont ceux où le modèle a une chance.

### P10 — Fonctions quasi dupliquées entre modules

**Mesuré** : il existe des fichiers de référence strictement identiques (cosinus 1,000) entre fonctions « différentes » ; une optimisation prouvée sur l'un vaut pour l'autre. Une détection **exacte** (empreinte d'arbre normalisée, P6) suffit à les repérer ; e5 n'est pas nécessaire. Piste à faible coût, pas encore explorée (je n'ai pas compté combien de paires).

## 4. Ce qu'OpenEvolve fait et comment on fait mieux, à moindre coût

| OpenEvolve | Limite (cf. lecture § 4) | Notre réponse |
|---|---|---|
| Filtre de nouveauté par cosinus du **code** + juge LLM, à l'entrée de la base | Après l'évaluation : ne sauve ni jetons ni temps ; **notre mesure montre en plus que le cosinus du code ne voit pas le comportement** (mutant faux : 0,995) ; seuil par défaut 0,99 | P1 : filtrer l'**idée en prose** avant le code, dans le point ; P6 : empreinte normalisée exacte |
| Pas de mémoire des échecs (traces écrites, non relues) | Les mêmes impasses reviennent | P0 : nos tombes ont déjà les empreintes ; leur donner texte et idée, et les montrer au modèle |
| Diversité = taille + caractères | Pas de sens, pas de comportement | P5 (comportement) |
| Inspirations = cases voisines de la grille de taille | Voisin = de même taille | P2 (par détecteur, puis par phrase) |
| Pas de cache d'évaluation | Réévalue le même code | Nos tombes + P6 |
| Juge de nouveauté = un modèle de langage | Un appel de modèle par comparaison | Chez nous le juge est le **corpus + le jeu réservé** : un « nouveau » est mesuré, pas jugé par un modèle |

## 5. Classement

**Ce qui rapporte le plus pour le moins d'effort** (tout est sans e5, sauf P1)
1. **P0 et P0b** : contenu des tombes et des idées déjà tentées dans le prompt, tombes semées dans `vus`. Une colonne, une liste, un bogue de moins.
2. **P6** : empreinte normalisée.
3. **P7** : ligne `Hypothèse :` fixe.
4. **P1** : l'entonnoir d'idées dans le point, avec le guichet, **après** avoir le journal d'idées de P0 pour calibrer.
5. **P2** par détecteurs.

**Ce qui serait vraiment inédit** : **P1** (un entonnoir par le sens, sur l'idée en prose avant le code, que ni OpenEvolve ni FrugalEvo n'ont d'après leur code lu) et **P3** (le moteur gagne des recettes gratuites en apprenant des gains payés). Et, côté conclusion : **montrer, mesures à l'appui, que le sens du code est la mauvaise piste** est déjà un résultat, qui coupe court à une direction coûteuse.

**Rejeté ou reporté** : encodage du code pour dédupliquer ou filtrer (E1), P4 (E2), P9, P10 (autre moyen), P8.

## 6. Recommandation et plan en étapes

Le modèle de sens ne vaut que sur des **phrases décrivant une idée**, dans **un même point**. Je recommande de **ne pas lui faire encoder du code**.

- **Étape 0 — sans e5** (petit) : P0 + P0b, semer les tombes dans `vus`, P6, P7. Résultat déjà obtenu (E7) : quand on lui nomme l'idée déjà prise, le modèle change d'idée (8 sur 8, petit échantillon). Porte de sortie restante : que ces idées nouvelles passent le juge au moins aussi souvent que les répétitions (à mesurer sur les vrais points avec leur corpus).
- **Étape 1 — journal** : pendant quelques semaines, écrire texte et hypothèse de chaque variante (jugée ou non). Sans cela, aucune calibration sérieuse.
- **Étape 2 — calibrer P1** sur ≥ 100 paires d'idées réelles étiquetées à la main (aire ROC et précision à 0,90 / 0,915 / 0,93). **Porte de sortie** : précision < 95 % → on n'ouvre pas le guichet.
- **Étape 3 — le guichet d'idées** (§ 2) et P1 dans Frugal 2 / Évolutif, avec plafond et repli.
- **Étape 4 — P2 par détecteurs** et le manuel d'astuces ; **P5** à comparer aux niches de taille.
- **Étape 5 — P3**, quand le journal montre trois gains de la même famille.

Chaque étape se juge sur un chiffre simple : jetons du relais par gain prouvé (déjà compté par le registre) et taux de recherches avec au moins un gain retenu par le juge.

## 7. Questions à trancher

1. D'accord pour **l'étape 0** (P0, P0b, semer les tombes dans `vus`, P6, P7) ? Elle ne demande pas e5 et corrige un défaut réel.
2. D'accord pour **abandonner l'encodage du code** et les familles par prototypes (P4), au vu des mesures ?
3. Pour calibrer P1 il faut ≥ 100 paires d'idées étiquetées : veux-tu les étiqueter toi-même (une dizaine de minutes), ou je les prépare et tu valides un échantillon ?
4. Règle de prudence : le sens ne rejette que des idées « sans gain », jamais des idées « fausses » (ma proposition) ?
5. Les promotions de recettes gratuites (P3) : toujours revues par un humain avant d'entrer dans `REGLES` ?
6. Un plafond de temps de calcul pour le guichet, partagé avec la mémoire (le modèle est résident et sert aux deux) : d'accord ?

## Mesures bout en bout du moteur (novembre 2026)

Banc jetable sur Orion : le vrai moteur dans la cage, le vrai juge du noyau, 17 fonctions synthétiques (dont 2 témoins déjà optimaux), un modèle gratuit fixé (Nemotron 3 Ultra), 2 passes par configuration. Une première série avait des entrées constantes par un défaut du banc : elle est écartée, les chiffres ci-dessous sont ceux de la série corrigée.

| Configuration | Fonctions avec gain | Appels | Jetons | Durée | Candidats faux |
|---|---|---|---|---|---|
| Règles seules | 3 / 17 | 0 | 0 | 10 s | 0 |
| Moteur à 2 générations | 11 | 70 | 86 700 | 61 min | 17 |
| + liste « déjà essayé » | 11 | 72 | 174 700 | 95 min | 24 |
| + 3 variantes par appel | 12 | 92 | 165 300 | 73 min | 72 |
| **1 génération** | **11** | **34** | **23 000** | **13 min** | 12 |

Ce qui en découle (et qui est codé) : une génération trouve les mêmes gains que deux ; la liste « déjà essayé » double les jetons sans gain ; les trois variantes ne gagnent qu'une fonction (`normaliser`) pour quatre fois plus de candidats faux. Le modèle varie d'un tirage à l'autre (`membre`, `inter` échouent une passe sur deux), d'où deux tirages par parent. Les deux témoins n'ont aucun faux gain, et aucun candidat faux n'a franchi le juge.

Limites : un seul modèle, des fonctions écrites pour le banc, deux passes, aucune donnée de production. Le rejeu refuse les entrées de plus de 64 Ko : les fonctions à grosses entrées restent « corpus trop étroit » (le plafond est maintenant un paramètre, son défaut reste à 64 Ko). `sommes_plage` n'aboutit dans aucune configuration.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->
