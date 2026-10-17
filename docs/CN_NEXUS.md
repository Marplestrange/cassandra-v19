<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Le Nexus : ce qu'il fait, et ce qui est intouchable -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Le Nexus : ce qu'il fait, et ce qui est intouchable -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=7ef9a2 ▼▼▼ -->
# Le Nexus : ce qu'il fait, et ce qui est intouchable

Statut : définition à valider (17-10-2026). **À lire avant `docs/CN_BORNES.md`** : on ne borne pas le code avant d'avoir dit ce qu'est le nexus.
Cadre : `docs/CN_EVOLUTION.md` (§2 ter à 2 septies).

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

Sinon : **nexus**. En particulier, une fonction **pure mais décisive** est nexus **par défaut** (vérification de signature, calcul d'empreinte, contrôle de droit, validation d'entrée de sécurité).

**Trois niveaux par fonction, réglables par l'admin** (décision de Drisse : le défaut est prudent, le choix reste à l'admin) :

| Niveau | Quoi | Condition |
|---|---|---|
| **Nexus** | jamais d'EC | défaut pour tout ce qui est décisif |
| **Point sous garde** | l'admin ouvre la fonction décisive à l'EC | invariants et corpus renforcés ; ombre plus longue ; vérificateur indépendant obligatoire ; **combinaison prudente (échec fermé)** : la référence et l'EC tournent toutes deux, et si l'une refuse ou signale un risque, le résultat est le refus |
| **Point** | ordinaire | les six conditions ci-dessus |

Seuls restent fixes les mécanismes qui sont des **juges** de l'évolution (garde de contrat, évaluateur, résolveur, vérification d'intégrité des EC) : on ne les fait pas évoluer par ce qu'ils jugent.

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

**Les modules régaliens (liste provisoire)** (100 % nexus par défaut) :
`droits`, `comptes`, `identite`/`webauthn`, `coffre`, `mandats`, `urgence`, `modules`, `reglages`, `journal`, `sauvegardes`.

**Le squelette de l'interface** : rendu, menus, routes, garde de sécurité de la page (politique CSP), jetons de session. Les **vues** (disposition, ordre, libellés, densité) ne sont **pas** nexus : ce sont des points d'évolution **déclaratifs** (voir §5 bis).

## 5. Ce que peut faire une EC (et rien d'autre)

- Remplacer l'implémentation d'**un point d'évolution déclaré**, par une fonction pure qui respecte son contrat.
- Importer la bibliothèque standard **pure** et `ec_api` : rien d'autre. Ni `os`, ni réseau, ni base, ni `ctx`, ni fichier, ni horloge, ni hasard.
- Avoir un temps et une mémoire plafonnés, **aucun état** entre deux appels.
- Être rangée **à part**, hors du dossier du module, dans `/var/cassandra/ec/<module>/`.

## 5 ter. Prompts d'agents et politiques : de l'EC, bornés par le nexus

Décision de Drisse (17-10) : **les prompts et les politiques sont de l'EC.** Ce sont des artefacts évolutifs de même rang que le code, avec leur version dépôt (le texte ou le réglage de référence) et leur version EC.

**Condition de sécurité : la sécurité ne dépend jamais d'un prompt.** Tout ce qui protège (droits, mandats, cloisonnement, plafonds d'autonomie, freins, confirmation d'un geste irréversible) est appliqué **par le code du nexus**, quoi que dise le prompt. Un prompt évolué qui « oublie » une consigne ne peut donc rien ouvrir : le nexus refuse de toute façon.

- **Prompt EC** : le nexus fixe le **contrat** du prompt : emplacements et variables obligatoires, longueur maximale, schéma de la réponse attendue (validée en code), liste de ce que le prompt ne peut pas déclarer (outils, droits). L'EC ne change que le texte à l'intérieur.
- **Politique EC** (seuils du Sensorium, règles de la Proactivité, fréquences) : le nexus déclare pour chaque paramètre un **intervalle autorisé** et des **planchers de sécurité** (ex. : un seuil critique ne peut pas dépasser une valeur donnée). L'EC règle à l'intérieur de l'intervalle, jamais en dehors.
- **Fitness** : signaux de vie réels : alertes acquittées sans action, réponses corrigées ou relancées, gestes annulés, coût par tâche.
- **Évaluation** : rejeu des conversations et des décisions passées, **jeu réservé**, et **cas piégés de sécurité** (le prompt évolué doit encore refuser ce que le nexus interdit, vérifié à chaque promotion).
- **Versions** : `itare.prompt 1.2 · EC14`, `sensorium.seuils 1.0 · EC6` ; mêmes règles de nexus, de façade, de référence et de retour qu'un module.

## 5 bis. L'interface en EC : des descriptions, jamais du JavaScript

Décision de Drisse : l'interface n'est pas nexus ; seuls le **squelette** et les **menus** le sont. Condition de sécurité : **l'EC d'interface est déclarative.** Le code d'une interface s'exécute dans le navigateur avec le jeton de session et sous la politique de sécurité de la page ; un script évolué que personne n'a relu y serait une porte ouverte.

- Le squelette nexus **interprète et valide** une description : `état → description d'écran` (structure, ordre, regroupements, libellés, densité, paramètres d'affichage), jamais de script.
- **Fitness** : l'usage mesuré (temps pour accomplir une tâche, clics, erreurs, recherches abouties), local à l'instance et respectueux du cloisonnement par compte.
- **Invariants du contrat** vérifiables automatiquement : accessibilité (contrastes, étiquettes, ordre du focus), respect des jetons de design, aucune information d'un autre compte.
- Les suggestions d'objectif du cockpit, l'ordre des onglets, la composition de la vue d'ensemble en sont les premières surfaces ; **`vue.composer`**, déjà pur, est le pilote.
- **Évolution au niveau de l'instance seulement** (décision de Drisse, 17-10) : pas d'évolution par compte, qui multiplierait variantes, corpus et mesures par le nombre de comptes (usine à gaz) et soulèverait la question de ce qu'on mesure chez chacun. La personnalisation d'un compte reste une **préférence d'affichage** dans les réglages, pas de l'évolution.

## 6. Comment l'intouchabilité est vérifiée (pas promise)

1. **Politique signée** : un fichier `INTOUCHABLES` du dépôt liste les chemins ci-dessus ; l'outil de bornes (`outils/CN_bornes.py`) échoue si un chemin intouchable porte une borne `point`.
2. **Orfan refuse** toute cible qui n'est pas un point déclaré dans un manifeste signé.
3. **Le chargeur** n'accepte une EC que pour un point déclaré, avec une empreinte de nexus signée par le dépôt ; tout fichier hors point dans le stock d'EC est rejeté.
4. **L'installateur** écrit seulement dans les zones du dépôt et **refuse** d'écrire dans `/var/cassandra/ec/`.
5. **Un banc « intouchables »** dans la suite : il essaie de passer une EC sur chaque intouchable et exige le refus.
6. **Le noyau et Orfan** n'ont que la version dépôt ; leur empreinte est vérifiée au démarrage.

## 6 bis. Classes de module (provisoire)

La classe de chaque module est un champ de son **manifeste** (`classe = "regalien" | "operationnel" | "mixte"`), signé par le dépôt et lu par l'outil de bornes : changer une classification est une ligne, pas un remaniement. La liste ci-dessous est **provisoire** (Drisse, 17-10 : « pas encore définitivement fixé »).

| Classe | Contenu | Points d'évolution |
|---|---|---|
| **Régalien** | identité, accès, secrets, urgence, gestion des modules, journal, sauvegardes | aucun, jamais |
| **Opérationnel** | `vue`, `mesures`, `fastpanel` (lecture), `sensorium` (agrégation), `contacts`, `courrier` (analyse), `planifie`, `notes`, `memoire`… | oui, sur leurs fonctions pures, chaudes et non décisives |
| **Mixte** | `securite`, `sensorium` (verdicts) | seulement les calculs **descriptifs** ; tout ce qui déclenche une crise, une alerte critique ou une écriture reste nexus |

## 7. Décisions

**Tranchées (17-10)**
1. L'interface n'est pas nexus : squelette et menus = nexus ; vues = EC **déclaratif** (§5 bis).
2. « Pure mais décisive » = nexus par défaut, **réglable** par l'admin, avec garde renforcée et combinaison prudente (§3).
3. La liste des régaliens **n'est pas figée** : la classe est un champ du manifeste.
4. **Les prompts d'agents et les politiques sont de l'EC** (§5 ter) : le nexus en garde le contrat et les bornes.
5. **L'interface évolue au niveau de l'instance seulement**, pas par compte (§5 bis).

**Ouvertes**
- Quels modules de la liste régalienne sont à revoir ? Candidats à discuter : `sauvegardes` (le calcul de rétention est pur), `modules` (la résolution des dépendances est pure et décisive), `reglages`, `journal`.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
