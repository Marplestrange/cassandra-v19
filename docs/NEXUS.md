# Le Nexus : ce qu'il fait, et ce qui est intouchable

Statut : définition à valider (17-10-2026). **À lire avant `docs/BORNES.md`** : on ne borne pas le code avant d'avoir dit ce qu'est le nexus.
Cadre : `docs/EVOLUTION.md` (§2 ter à 2 septies).

## 1. Définition

> Le **nexus** est ce qui doit rester vrai même si tout ce qui est optimisé se trompe.

C'est la partie de Cassandra qui répond de **l'identité, de l'accès, des effets sur le monde, des données, de la preuve et de l'exploitation**. Elle est écrite et signée par le dépôt. Aucune évolution, aucun moteur, aucun agent ne l'écrit.

L'**EC** (Evolution Cassandra) est ce qui peut changer sans que rien de vrai ne change : le *comment* d'un calcul pur, jamais le *quoi* ni le *qui a le droit* ni le *quel effet*.

## 2. Ce que fait le nexus (neuf responsabilités)

1. **Déclarer** : manifestes, capacités (risque, droit, périmètre, preuve, retour, paliers), objets, événements, mesures, **points d'évolution** et leurs contrats.
2. **Garder l'accès** : identité, authentification (mots de passe, second facteur, clés d'accès), droits, **cloisonnement par compte**, mandats, secrets et coffre.
3. **Faire les effets** : toute entrée et sortie (disque, réseau, base, processus, programmes racine par le courtier, horloge, hasard). C'est la coquille impérative.
4. **Posséder les données** : schémas, migrations, stockage, sauvegardes. **L'EC ne possède aucune donnée persistante.**
5. **Orchestrer** : brancher les capacités, enchaîner les modules, appeler les points d'évolution par leur façade, ordonnancer.
6. **Tenir la preuve** : journal, chaîne d'empreintes, versions (dépôt + EC), empreintes signées du nexus et des points.
7. **Garantir le contrat** : façades, schémas, invariants, lentilles, **références**, garde de contrat (disjoncteur), résolveur de compatibilité.
8. **Mesurer** : produire les mesures déclarées et le journal d'appels (la matière du rejeu). **L'EC ne mesure jamais sa propre performance.**
9. **Exploiter** : installer, vérifier, retirer, migrer, déployer, revenir en arrière, arrêt d'urgence, gel, frein des envois.

Le nexus **décide**, **autorise**, **agit** et **prouve**. L'EC **calcule**.

## 3. Le test « nexus ou point d'évolution ? »

Une fonction n'est un **point d'évolution** que si **les six** conditions sont vraies :

1. **Pure** : aucune entrée/sortie, pas de `ctx`, pas d'état, pas d'accès global.
2. **Déterministe** : l'heure, le hasard et les données arrivent **en paramètres**.
3. **Bornée** : durée et mémoire plafonnées.
4. **Mesurable** : elle a une mesure déclarée et un corpus de rejeu.
5. **Non décisive** : elle ne décide d'aucun droit, secret, suppression, envoi, confinement, écriture de pare-feu, ni d'aucune vérification de preuve.
6. **Contractuelle** : son entrée et sa sortie sont décrites par un contrat neutre (schéma JSON) avec invariants et corpus doré.

Sinon : **nexus**. En particulier, une fonction **pure mais décisive** reste nexus (vérification de signature, calcul d'empreinte, contrôle de droit, validation d'entrée de sécurité). Elle ne peut être déclassée en point que par décision signée du dépôt, avec invariants et corpus renforcés.

## 4. Les intouchables absolus (jamais d'EC, jamais de point)

**Dans le dépôt**
- `noyau/` **en entier** : exécuteur, droits, identité, passerelle, courtier racine, registre, stockage, chargeur, manifeste, paquets, systemd, bus, contexte, base, catalogue, chemins, modules, réglages.
- `main.py`, `install.sh`, `deploy.sh`, `outils/pousser.sh`, et tout `exploitation/` (unités et configuration système).
- **Tous les `manifeste.toml`.**
- **Tout ce qui s'exécute en racine ou installe** : `modules/*/commandes/`, `installer.sh`, `verifier.sh`, `retirer.sh`, `migrations/`.
- Les **contrats**, **façades**, **lentilles**, **références**, **corpus dorés** et **tests**.
- Les **données** et secrets (`donnees/`, `/var/cassandra`).

**Les mécanismes de l'évolution elle-même** (ils ne s'évoluent pas, sinon le juge se réécrit)
- **Orfan** (le moteur) et tout adaptateur de moteur, l'**évaluateur**, le **routage** et la **garde de contrat**, le **résolveur**, le **superviseur de déploiement**, le stock d'empreintes et la chaîne.

**Les modules régaliens** (100 % nexus, aucun point d'évolution possible) :
`droits`, `comptes`, `identite`/`webauthn`, `coffre`, `mandats`, `urgence`, `modules`, `reglages`, `journal`, `sauvegardes`.

**L'interface** (`interface/`) est nexus en v1.

## 5. Ce que peut faire une EC (et rien d'autre)

- Remplacer l'implémentation d'**un point d'évolution déclaré**, par une fonction pure qui respecte son contrat.
- Importer la bibliothèque standard **pure** et `ec_api` : rien d'autre. Ni `os`, ni réseau, ni base, ni `ctx`, ni fichier, ni horloge, ni hasard.
- Avoir un temps et une mémoire plafonnés, **aucun état** entre deux appels.
- Être rangée **à part**, hors du dossier du module, dans `/var/cassandra/ec/<module>/`.

## 6. Comment l'intouchabilité est vérifiée (pas promise)

1. **Politique signée** : un fichier `INTOUCHABLES` du dépôt liste les chemins ci-dessus ; l'outil de bornes (`outils/bornes.py`) échoue si un chemin intouchable porte une borne `point`.
2. **Orfan refuse** toute cible qui n'est pas un point déclaré dans un manifeste signé.
3. **Le chargeur** n'accepte une EC que pour un point déclaré, avec une empreinte de nexus signée par le dépôt ; tout fichier hors point dans le stock d'EC est rejeté.
4. **L'installateur** écrit seulement dans les zones du dépôt et **refuse** d'écrire dans `/var/cassandra/ec/`.
5. **Un banc « intouchables »** dans la suite : il essaie de passer une EC sur chaque intouchable et exige le refus.
6. **Le noyau et Orfan** n'ont que la version dépôt ; leur empreinte est vérifiée au démarrage.

## 6 bis. Classes de module

| Classe | Contenu | Points d'évolution |
|---|---|---|
| **Régalien** | identité, accès, secrets, urgence, gestion des modules, journal, sauvegardes | aucun, jamais |
| **Opérationnel** | `vue`, `mesures`, `fastpanel` (lecture), `sensorium` (agrégation), `contacts`, `courrier` (analyse), `planifie`, `notes`, `memoire`… | oui, sur leurs fonctions pures, chaudes et non décisives |
| **Mixte** | `securite`, `sensorium` (verdicts) | seulement les calculs **descriptifs** ; tout ce qui déclenche une crise, une alerte critique ou une écriture reste nexus |

## 7. Décisions à confirmer par Drisse

1. **L'interface reste-t-elle nexus** pour toujours, ou ouvre-t-on plus tard une zone de présentation évolutive (disposition, textes) ?
2. **« Pure mais décisive = nexus par défaut »** : d'accord ? (Cela retire des candidats comme `webauthn.verifier_signature` et certains verdicts de sécurité.)
3. **La liste des régaliens** ci-dessus est-elle complète ?
4. **Les prompts d'agents et les politiques** (seuils, règles) : ils sont des artefacts évolutifs d'un autre type. Ils suivent le même principe (un nexus qui garde le contrat, une couche EC par-dessus) mais leur frontière sera définie à part.
