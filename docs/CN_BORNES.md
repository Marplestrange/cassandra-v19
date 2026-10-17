<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Bornes du code : nexus et points d'évolution -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Bornes du code : nexus et points d'évolution -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=9c504a ▼▼▼ -->
# Bornes du code : nexus et points d'évolution

Statut : conception (17-10-2026) + audit chiffré de l'existant. Rien n'est encore refactoré.
**À lire après `docs/CN_NEXUS.md` et `docs/CN_FORMAT.md`** (format universel : un fichier = une zone, CN ou EC, séparés ; il remplace les en-têtes `# BORNE:` et les régions dans un même fichier proposés ici) (ce qu'est le nexus et la liste des intouchables). Complète `docs/CN_EVOLUTION.md` (§2 ter à 2 sexies) : là-bas, le principe ; ici, **comment le code est découpé et borné fichier par fichier**.

## 1. Principe

Chaque module est coupé en deux zones physiquement distinctes, vérifiées par un outil :

- **Nexus** : la base rudimentaire, intouchable par l'évolution. Orchestration, entrées et sorties, schémas de données, migrations, permissions, façades de contrat, API publique. **Seul le dépôt l'écrit.**
- **Points d'évolution** : de petites fonctions pures déclarées, chacune avec son contrat. Le dépôt y écrit la **référence** ; l'évolution la remplace à l'exécution par une **EC** stockée à part. Le dépôt n'écrit jamais l'EC, l'évolution n'écrit jamais le nexus.

**Règle de mise à jour** : une mise à jour majeure de Cassandra ne touche que le nexus (et les références des points) **partout**. L'installateur écrit uniquement dans les zones « dépôt » et **refuse** d'écrire dans le stock d'EC. Le noyau et Orfan n'ont que la version dépôt.

## 2. Disposition par module

```
modules/<m>/
  manifeste.toml        nexus  (+ [[points_evolution]] : id, contrat, mesure, invariants, corpus)
  module.py             nexus  (coquille impérative : branche les capacités, fait les E/S)
  nexus/                nexus  (le reste de la logique d'orchestration, schémas, migrations)
  points/               zone des points : UNE fonction pure par point ; la référence du dépôt
  contrats/             nexus  (schéma d'entrée/sortie, invariants exécutables, corpus doré, lentilles)
  tests/                nexus
/var/cassandra/ec/<m>/  stock d'EC (hors du dossier du module, jamais écrit par une mise à jour)
```

**En-tête obligatoire de chaque fichier Python** (première ligne, lue par l'outil) :

- `# BORNE: nexus` ou `# BORNE: point <id> @<contrat>`

Pour l'existant pas encore découpé, une borne **dans** le fichier est tolérée en transition :

```
# ==== NEXUS ====
...
# ==== POINT sites.lecture @1.0 ====
def lire_sites(...): ...      # pure : aucune E/S, aucun ctx
# ==== FIN POINT ====
```

## 3. Ce que vérifie `outils/CN_bornes.py` (à écrire ; échec en intégration continue)

1. Tout fichier porte une borne, toute région est fermée.
2. Une zone **point** n'importe que la bibliothèque standard pure et `ec_api` : pas `os`, `subprocess`, `socket`, `sqlite3`, `urllib`, `time`, `random`, pas `ctx`, pas `self`, pas de `global`, pas d'accès disque.
3. Tout point déclaré dans le manifeste a son fichier, son contrat, ses invariants et son corpus doré ; tout fichier de point est déclaré.
4. Le nexus n'appelle un point que par la **façade de contrat** (jamais directement).
5. Aucune fonction pure de plus de 8 lignes ne reste dans le nexus **sans justification** (liste d'exceptions signée), pour que la zone d'évolution ne se vide pas en silence.
6. Empreintes d'arbre distinctes : `empreinte_nexus` et `empreinte_points` par module, publiées avec la version dépôt (elles alimentent `1.9.0+EC21.a3f9c2`).

## 4. Audit de l'existant (relevé sur le dépôt le 17-10-2026)

- **42 modules, 54 fichiers Python, 29 300 lignes** (noyau : 3 693 lignes, à part).
- Seulement **~10 %** des lignes (3 066) sont des **fonctions de tête pures** d'au moins 8 lignes, donc candidates immédiates à devenir des points : relevé strict, par analyse de l'arbre syntaxique.
- Elles se concentrent dans quelques modules : `sensorium` (26 fonctions, 534 l.), `securite` (19, 447 l.), `memoire` (13, 274 l.), `contacts` (11, 211 l.), `planifie` (11, 203 l.), `fastpanel` (15, 198 l.), `courrier` (14, 175 l.), `flotte` (4, 124 l.), `vue` (1, 97 l.), `menus`, `webauthn`, `notes`.
- **18 modules n'ont aucun candidat** : tout y est nexus (E/S, coordination). C'est normal : ils n'ont pas de point d'évolution tant qu'on n'en extrait pas.
- **35 modules tiennent en un seul `module.py`** qui mélange coquille et logique : la logique pure y est entremêlée avec les appels de `ctx`. C'est le gros du travail de bornage : **extraire un noyau fonctionnel** (fonction pure) et laisser une coquille mince.

Conséquence assumée : au départ, la zone d'évolution est une **minorité** du code (≈ 10 %, peut-être 25 à 30 % après extraction). C'est voulu : le nexus est la grande base stable ; l'évolution vise la logique pure et chaude, mesurable par rejeu.

## 5. Ordre de migration (module par module, suite de tests verte à chaque pas)

1. **Outil d'abord, en mode audit** : `bornes.py` classe tout sans rien faire échouer ; il publie la carte.
2. **Pilotes** : `vue.composer` (déjà pur, 97 l., très appelé), puis `fastpanel` (lecture des sites, services, audit), `securite.analyse`, `mesures.moteur`.
3. **Extraction guidée** des modules à logique entremêlée (`sensorium`, `memoire`, `contacts`, `planifie`, `courrier`) : on sort la fonction pure, on laisse la coquille, les bancs existants prouvent l'équivalence.
4. **Modules entièrement nexus** : marqués `nexus` d'un bloc, sans point d'évolution.
5. **Bascule à `échec`** en intégration continue une fois la carte complète.
6. **Installateur** : n'écrit plus que dans les zones « dépôt » ; refus explicite d'écrire dans `/var/cassandra/ec/`.

## 6. Risques

- Refactorer 42 modules est un chantier réel ; chaque extraction doit rester **équivalente à la ligne près** (les bancs de chaque module sont le filet).
- Une fonction « presque pure » (qui lit l'heure, tire un nombre au hasard) doit recevoir ses entrées en paramètres pour devenir un point : sinon le rejeu n'est pas reproductible.
- Un nexus trop mince fait perdre de la lisibilité ; un nexus trop gros stérilise l'évolution. Le critère est **mesurable** : une fonction est un point si elle est pure, chaude (appelée souvent) et lente ou coûteuse.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
