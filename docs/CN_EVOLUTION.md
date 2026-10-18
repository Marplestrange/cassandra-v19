<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Évolution V19 — note de conception -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Évolution V19 — note de conception -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=aa1382 ▼▼▼ -->
# Évolution V19 — note de conception

Statut : conception (17-10-2026). Rien n'est construit. Ce document remplace le moteur V18 (diff d'un fichier unique `cassandra.py`), qui n'a plus d'objet.

## 1. Décisions

1. **Le noyau est hors périmètre.** Sa version est déterminée par ses mises à jour (déploiement normal : suite complète, retour arrière automatique). L'évaluateur, le routage pondéré, le mode ombre et le superviseur du déploiement vivent dans le noyau : la boucle ne les modifie jamais.
2. **Le périmètre évolutif = les modules et leurs moteurs** (fonctions pures : composer, analyse, parefeu, crise, images…), plus la création et le retrait de modules.
3. **Pas de validation humaine comme mécanisme de sécurité.** La sécurité est mécanique : évaluateur indépendant du générateur, jeu réservé, contrôles piégés, réversibilité, vérificateur indépendant pour l'irréversible. L'humain fixe l'objectif (fitness), le budget et garde l'arrêt d'urgence (crise). Le bulletin du lundi informe, il ne demande aucune décision.
4. **On intègre le moteur de recherche, on ne le réécrit pas.** OpenEvolve (Apache-2.0, API de bibliothèque, îlots, MAP-Elites, multi-objectifs) par défaut ; ShinkaEvolve (Apache-2.0, sobre en essais, modèles locaux) en alternative. DGM / HGM : idées seulement (archive d'ancêtres, potentiel des lignées).
5. **On construit ce qui n'existe nulle part** : le lien avec une production vivante.

## 2. Ce qu'on construit

- **Corpus de rejeu** par capacité : appels réels du journal (entrées, sorties, durée), anonymisés. C'est le contrat exécutable et la fonction de fitness.
- **Évaluateur déterministe** : rejeu + mesures déclarées (`[[mesures]]`). Jamais un modèle qui note son propre travail. Jeu réservé que le générateur ne voit pas ; variantes piégées volontairement mauvaises (si l'une passe, l'évaluateur est cassé et l'évolution s'arrête seule).
- **Mode ombre** : la variante tourne à côté de l'actuelle sur les appels réels ; seules les lectures sont exécutées, les écritures sont détournées vers un simulacre comparé.
- **Routage pondéré** (1 % → 10 % → 100 %) sur verdict calculé ; retour = repasser l'aiguillage.
- **Lignée et tombes** : chaque variante descend d'une autre, avec mesures et échecs gardés ; l'archive sert à choisir, pas seulement à afficher.
- **Budget par module** (essais, calcul) et fitness multiple déclarée dans le manifeste. Une mesure absente est dite muette, jamais lue comme zéro.
- **Autonomie gagnée** : le niveau de chaque module monte et descend seul, selon le taux de gains confirmés à J+30 sur le jeu réservé. Un module qui trompe son évaluateur redescend.
- **Frontière de l'irréversible** : suppression sans corbeille, envoi vers l'extérieur, secrets → vérificateur indépendant (autre famille de modèle, preuve sans le raisonnement de l'auteur) + délai avant effet.
- **Créer / élaguer / recomposer** : demandes sans réponse (501, « pas porté ») → module brouillon en ombre ; modules ou capacités inutilisés → retrait avec corbeille ; fusion/scission proposées.
- **Observations vers le noyau** : le moteur rend des constats (« 9 modules contournent la même limite ») qui alimentent la version suivante du noyau. Jamais des patchs.
- **Mise à jour du noyau** : le corpus est rejoué contre la nouvelle version ; une variante devenue incompatible est marquée, pas servie.
- **Export** : une variante validée devient un patch git sur le dépôt (le déployé ne dérive pas de `main`) et, à terme, un module signé du store, reçu par les autres instances en ombre avec leurs propres preuves.
- **Écran** : généalogie, variantes en ombre avec écart en direct, gains J+30, tombes, bulletin.

## 2 bis. Ce qui rend le système redoutable (17-10, après la maquette du cockpit)

1. **L'intention** : un objectif écrit en français est compilé en mesure + banc d'essai + budget ; l'humain valide l'objectif, rien d'autre.
2. **La nuit** : chaque nuit, la journée vécue (trafic réel de la veille) est rejouée en parallèle contre toutes les variantes, en cage, sans réseau.
3. **La guérison** : une erreur en service est reproduite depuis le journal en test rouge, une variante est cherchée contre tout le rejeu, passe en ombre puis en service ; le test reste pour toujours.
4. **Le cliquet** : les tests permanents ne font que croître (échecs, pièges, tombes). L'évaluateur ne peut que se durcir.
5. **La fossilisation** : une décision de modèle qui ne varie jamais devient une règle de code, rejouée contre toutes les décisions passées ; le modèle ne garde que l'exception. Le coût baisse avec l'usage.
6. **Le routage sur mesure** : des variantes spécialisées par contexte (taille de compte, pointe, panneau lent) et un aiguilleur qui apprend.
7. **Le comportement, pas seulement le code** : seuils du Sensorium (fitness = alertes acquittées sans action), prompts d'agents, règles de la Proactivité.
8. **La machine à remonter le temps** : variantes immuables et chaînées, restauration de l'organisme entier à un jour donné.
9. **Les autres instances** : variantes signées, rejouées chez le receveur sur son propre trafic.

Limites à tenir : la fossilisation ne vaut que pour des décisions déterministes en pratique ; le routage sur mesure exige assez de données par contexte ; le « 2,3× » et les autres chiffres de la maquette sont fictifs et doivent être mesurés par le pilote.

## 2 ter. Versionnement : version dépôt + version EC (17-10)

**Règle : tout artefact évolutif porte deux versions.**
- **Version dépôt** : celle du dépôt (semver, signée, personne ne la modifie). Ex. `fastpanel 1.9.0`.
- **Version EC** (*Evolution Cassandra*) : l'état de la ligne évoluée posée par-dessus. Ex. `EC21`.
- Écriture complète : `1.9.0+EC21.a3f9c2`, une version sémantique valide (métadonnée de build) : **l'EC ne passe jamais devant le dépôt**. Le suffixe est l'empreinte du contenu.
- Le numéro EC ne repart jamais à zéro : il identifie un état de la ligne évoluée. « EC21 » d'une instance et « EC21 » d'une autre ne sont la même version que si l'empreinte est la même.
- S'applique aux modules, aux prompts d'agents (`itare.prompt 1.2 · EC14`) et aux politiques (`sensorium.seuils 1.0 · EC6`). **Le noyau et Orfan** n'ont qu'une version dépôt, sans EC : ils sont hors évolution.
- Une EC ne peut changer ni le manifeste, ni les signatures de capacités, ni les permissions (contrôle à chaque promotion).
- **Version suivie**, par module : *Évolution* (la dernière EC prouvée), *Dépôt* (sans évolution) ou *Évolution éprouvée* (seulement une EC confirmée à J+30). Changer de version suivie, comme revenir à une EC ou au dépôt, est un aiguillage journalisé : rien n'est détruit.
- **Proposer au dépôt** : une EC devient un patch git ; une fois fusionnée, elle est « intégrée » à la version dépôt.
- **Sortie d'une nouvelle version dépôt** : les pièces EC sont rejouées sur la nouvelle base. Reportées (0 écart au rejeu), intégrées (déjà dans le dépôt), en conflit (renvoyées au moteur) ou retirées (le gain disparaît : tombe). Le résultat est une nouvelle EC sur la nouvelle base, qui passe par l'ombre.

## 2 quater. Nexus et couche EC : une EC n'est jamais annulée par le dépôt (17-10)

**Décision de Drisse : le dépôt améliore un module sans jamais qu'une EC d'un client cesse d'être compatible.** Chaque module est coupé en deux couches :

- **Nexus (version dépôt)** : écrit seulement par le dépôt, jamais touché par l'évolution. Il contient le manifeste, les signatures publiques des capacités, les permissions, les schémas de données et leurs migrations, et, pour chaque point d'évolution, une **façade de contrat** et une **implémentation de référence**.
- **Couche EC** : écrite seulement par l'évolution, rangée **à part** des fichiers du module (une mise à jour du dépôt ne l'écrit jamais). Elle ne remplace que des implémentations derrière un **point d'évolution déclaré** dans le manifeste (`[[points_evolution]]` : identifiant, contrat versionné, mesure, corpus de rejeu, invariants).

**Règles de compatibilité**
1. L'EC ne s'accroche qu'à des points déclarés et n'importe que l'**API publique stable** du nexus (versionnée, additive dans une version majeure). Le filtre avant évaluation d'Orfan le vérifie sur l'arbre syntaxique.
2. La **façade** traduit le modèle interne du nexus vers la forme stable du contrat, et inversement : un remaniement interne du dépôt n'atteint pas l'EC.
3. Un contrat n'évolue que **par ajout** (champs d'entrée optionnels, champs de sortie en plus) à l'intérieur d'une version majeure. Une rupture (version majeure) **livre une adaptation** de l'ancien contrat vers le nouveau ; l'EC continue de servir par elle pendant qu'une EC native est refaite en arrière-plan.
4. **Filet** : si une EC ne passe réellement plus, l'implémentation de référence du dépôt sert la capacité (correcte, pas encore optimisée). L'EC est **suspendue, conservée, refaite puis réintégrée**, jamais détruite.
5. **Mise à jour en deux temps** : le nouveau nexus est installé à côté, l'EC y est rejouée en ombre (point par point, sur le trafic réel) ; la bascule n'a lieu que si c'est compatible ; retour au nexus précédent en un clic.
6. **Les EC éprouvées des clients deviennent la suite de tests du dépôt** (exportées, anonymisées, avec consentement) : le dépôt ne peut pas publier une version qui casse une EC connue. Un vérificateur de contrats compare chaque version à la précédente (ajout seulement, sauf version majeure).
7. L'EC ne possède aucune donnée persistante : l'état reste au nexus (pas de migration côté EC) ; ses caches sont jetables.
8. Les artefacts d'Orfan sont stockés dans un format neutre (patch + contrat + preuve) : monter la version d'Orfan n'invalide aucune EC.

Ce qu'on promet, et ce qu'on ne promet pas : une EC reste **active** tant que le contrat n'évolue que par ajout. Si le dépôt change le sens d'un contrat, la garantie est qu'**aucune EC n'est perdue et qu'aucun service ne coupe** : l'EC est portée par l'adaptation, ou suspendue sous la référence, puis refaite.

## 2 quinquies. La règle « M. Martin » : une mise à jour ne fait jamais perdre ce que l'EC a gagné (17-10)

Cas d'école de Drisse : un client fait tourner depuis des mois une V20 avec des EC payées en jetons ; le dépôt publie une V22 ; le client ne doit pas se retrouver avec une version moins performante que sa V20 + EC.

**La discipline du dépôt ne suffit pas** (le dépôt ne connaît pas toutes les EC de tous les clients, et un humain se trompe). La garantie réelle est mécanique et se joue **chez le client**.

*Côté dépôt (empêcher de publier une version cassante)* : vérificateur de contrats bloquant en intégration continue (ajout seulement dans une version majeure, toute rupture livre son adaptation) ; la **banque d'EC éprouvées** (exportées, anonymisées, avec consentement) est rejouée contre chaque version candidate, et une EC qui perd du terrain bloque la publication ; les versions majeures passent d'abord par un **canal bêta** d'instances volontaires.

*Côté client (la garantie)* :
1. **Une mise à jour majeure n'est jamais automatique** : le client voit « V22 disponible » avec le résultat de la simulation ; rien ne s'installe sans son accord ou sa règle.
2. **Porte de non-régression de performance** : le nouveau nexus plus les EC portées est rejoué en ombre sur le trafic réel du client ; si la vitesse, les erreurs ou le coût sont moins bons que ce qui sert aujourd'hui, la bascule est **refusée** et la version actuelle continue de tourner, avec un message qui dit ce qu'on perdrait.
3. **Rattrapage** : l'évolution retravaille alors sur la nouvelle version, en arrière-plan ; dès qu'elle égale ou dépasse la version actuelle, la bascule se fait seule.
4. **L'ancienne version reste installée** pendant une durée réglable (retour en un clic, même après la bascule).
5. **Le stock d'EC est sauvegardé et exportable** : ce qui a coûté des jetons ne dépend pas d'un seul disque.
6. **Le capital d'EC est visible** : jetons dépensés, gain cumulé tenu à J+30, part protégée par la porte.

Limite assumée : refuser une mise à jour retarde aussi ses correctifs. La porte porte donc sur la performance ; un **correctif de sécurité** est signalé à part, avec sa propre voie (le client voit ce qu'il coûterait de ne pas l'appliquer).

## 2 sexies. Le système de compatibilité EC ↔ nexus (17-10)

Exigence de Drisse : un **système** qui garantisse qu'une EC reste compatible avec le code du nexus, pas seulement des règles. Six couches empilées ; chacune rattrape les trous de la précédente.

1. **Par construction : noyau fonctionnel / coquille impérative.** L'EC est une **fonction pure sur des données du contrat** ; le nexus (la coquille) fait toutes les entrées et sorties. L'EC n'importe rien du nexus (stdlib + `ec_api`, additive). La surface de compatibilité se réduit aux schémas de données.
2. **Registre de contrats en compatibilité complète et transitive** (au sens des registres de schémas d'Avro/Protobuf) : ajout seulement, avec valeurs par défaut ; lecteur tolérant (l'EC ignore les champs inconnus, le nexus accepte les champs de sortie manquants) ; renommage par alias ; rupture = **nouveau contrat** + **lentille** (traduction ancienne forme ↔ nouvelle) fournie et testée. L'intégration continue du dépôt **refuse** toute modification de contrat non classée (`AJOUT`, `ALIAS`, `DÉPRÉCIATION`, `RUPTURE` + lentille). Les lentilles se composent : une EC du contrat v1 tourne sur un nexus en v3.
3. **Diff de comportement de la référence.** À chaque version, l'implémentation de référence de chaque point est rejouée sur son **corpus doré** ; toute différence de sortie par rapport à la version précédente est un changement de sens : la publication exige de le classer « rupture » (avec lentille) ou de le justifier. Cela attrape ce que les schémas ne voient pas.
4. **Résolveur statique.** Chaque EC porte un manifeste (`contrat@`, `api_ec@`, empreinte des invariants et du corpus). `compatible(EC, nexus)` se calcule en quelques millisecondes, sans rien exécuter ; l'écran l'affiche par point d'évolution, et la mise à jour l'utilise comme première porte.
5. **Disjoncteur à l'exécution.** Une **garde de contrat** enveloppe chaque appel d'EC : sortie hors schéma, invariant violé, délai dépassé, exception → **la référence répond dans le même appel** ; trois violations en dix minutes suspendent l'EC (conservée) et notifient. Un échantillon d'appels est comparé à la référence pour déceler une dérive de sens. C'est ce qui rend l'incompatibilité **invisible** même si toutes les couches précédentes ont raté.
6. **Réparation.** Lentille d'abord ; puis re-évolution depuis l'EC suspendue (rattrapage de la §2 quinquies) ; l'EC revient, elle ne disparaît pas.

**Ce que le système garantit, honnêtement.** Les couches 1 à 4 rendent l'incompatibilité **impossible** pour toute évolution par ajout, et détectable **avant** publication pour les autres. La couche 5 rend toute incompatibilité résiduelle **invisible à l'utilisateur** (la réponse est toujours conforme) au prix d'une perte temporaire d'optimisation sur ce point. Limite : un changement de sens que ni les invariants ni le corpus doré ne détectent passerait la couche 3 ; la qualité des invariants et du corpus de chaque point d'évolution est donc la dépendance réelle du système, et fait partie de ce que le dépôt doit entretenir.

## 2 septies. EC dans d'autres langages (piste, 17-10)

Conséquence du contrat neutre : si l'EC est une fonction pure `entrée JSON → sortie JSON`, le langage est un détail d'implémentation, et le nexus verrouillé par la signature du dépôt laisse tout le reste en surcouche.

- **Ordre** : Python (v1) → **WebAssembly** (bac isolé sans disque ni réseau, déterministe ; produit par Rust, Go, C…) → Node et PHP en processus isolés seulement si un besoin réel apparaît.
- **Gain à mesurer** : l'évolution pourrait réécrire un point chaud en langage compilé (WASM) pour un gain de vitesse que le Python n'atteindra pas. Hypothèse, non mesurée.
- **Précautions dès maintenant** (sans rien construire de plus) : contrat en schéma JSON neutre ; interface d'appel `appeler(point, entrée) → sortie` ; champ `runtime` dans le manifeste d'EC (Python au départ) ; le chargement d'une EC vérifie que l'empreinte du nexus est signée par le dépôt.
- **Coûts** : surface de sécurité et d'évaluation par langage ; quelques ms de frontière de processus (ne vaut que pour les points assez lourds).
- **Horizon distinct, hors V19** : la même mécanique appliquée aux sites hébergés (le code du client = nexus à son commit, l'EC = couche d'optimisation). C'est un autre produit, au périmètre à part.
- Chantier d'**Orfan R&D**, après le Python.

## 3. Rôles (pas de nouvel agent)

Déclarés dans le registre de modèles et le module Agents IA, chacun avec profil, modèle et budget :

| Rôle | Qui | Note |
|---|---|---|
| Mutateur | un modèle du registre, appelé par l'outil intégré | propose les variantes |
| Évaluateur | code déterministe | rejeu + mesures |
| Vérificateur indépendant | modèle d'une autre famille (Itare possible) | gestes irréversibles |
| Décideur | Cassandra | promotion sur verdict calculé |

## 4. Intégration du moteur de recherche

Module `[[moteurs]]` enfichable, interface étroite : « une capacité, un contrat de rejeu, un budget → des variantes classées ». Le produit tiers est optionnel, tourne dans son propre processus avec ses dépendances, et ne rend que des candidats ; le déploiement et la promotion restent à notre étage. Changer de moteur de recherche ne coûte rien.

### Les moteurs (17-10)

**Décision de Drisse : le moteur de Cassandra est Orfan, natif et hybride, sans intégration externe.** Les moteurs tiers restent des adaptateurs facultatifs : pour comparer (course des moteurs) et pour la liberté de l'admin. Cela remplace la décision 4 ci-dessus (OpenEvolve par défaut).

| | Orfan | OpenEvolve | ShinkaEvolve | CodeEvolve | GEPA | FrugalEvo |
|---|---|---|---|---|---|---|
| Fait évoluer | code + prompts + politiques | code | code | code (+ méta-prompts) | prompts, politiques | code |
| Licence | celle de Cassandra | Apache-2.0 | Apache-2.0 | Apache-2.0 | MIT | inconnue |
| Python | celui du noyau | ≥ 3.10 | ≥ 3.10 | ≥ 3.13.5 (Amizo : 3.11, Debian 12) | 3.10 à 3.14 | — |
| Dernier push (17-10) | — | 13-10-2026 | 05-10-2026 | 08-04-2026 | 13-10-2026 | pas de dépôt trouvé |

Faits relevés : CodeEvolve (Inter&Co + WPI, 152 étoiles, v0.3.1) annonce dépasser OpenEvolve et ShinkaEvolve sur 6 problèmes sur 9 (ses propres chiffres), méta-prompts, CVT-MAP-Elites, diffs SEARCH/REPLACE ; réserves : Python ≥ 3.13.5, dépendances lourdes, six mois sans push. GEPA (MIT, 7 020 étoiles) évolue prompts et politiques d'agents par réflexion sur les traces et frontière de Pareto. GigaEvo (AIRI, 24 étoiles, ≥ 3.12, dernier push 11-2025) : écarté. FrugalEvo : article seul (stratège fort + exécutant économe), pas de dépôt trouvé.

**Orfan est un projet à part entière** (dépôt, banc et feuille de route propres, avec une vraie R&D). Cassandra ne le connaît que par le contrat d'adaptateur : « une capacité, un contrat de rejeu, un budget → des variantes classées ». Aucune intégration externe : bibliothèque standard seulement.

**Orfan v1 = le moteur de la V18, amélioré, pour les modules.** Livré avec Cassandra :
- pièce = diff + hypothèse (gain chiffré, équivalence prouvée) + test rouge-vert + empreinte + verdict calculé (jamais « neutre ») ;
- chaîne d'empreintes partagée, rupture = arrêt ; tombes et leçons ; retour arrière par pièce inverse après vérification ;
- périmètre par propriété, veto d'un vérificateur indépendant, bulletin, visite à J+30 ;
- **améliorations** : unité = le module (diff sur son dossier) ; cibles prises dans le trafic réel (la V18 avait 67 pièces sur 231 sur du code mort) ; équivalence prouvée par le **rejeu** en plus du test ; évaluation **par paliers** (5 %, 25 %, 100 %) et arrêt à la première divergence ; filtre avant évaluation (signature, imports, réseau) ; doublons écartés par empreinte d'arbre syntaxique, tombes comprises ; reprise sur incident ; mutateur pris dans le registre de modèles.

**Orfan R&D (hors v1, dans son projet)** : génome prompts (réflexion sur les traces, frontière de Pareto, esprit GEPA), génome politiques (seuils du Sensorium, règles de la Proactivité, recherche locale sans modèle), co-évolution prompt ↔ code, stratège fort + exécutant économe (idée FrugalEvo), archive dont les cases sont les contextes réels, fossilisation des décisions de modèle, mutations déterministes gratuites. Chaque chantier se juge par la course des moteurs ; rien n'est annoncé avant d'être mesuré.

## 5. Risques et limites

- Non vérifié : tenue des outils sur un petit serveur avec modèles gratuits ou locaux. Le pilote le mesure.
- Là où la capacité n'a pas de mesure nette, la sélection est faible : l'évaluateur est le vrai chantier.
- Une capacité qui appelle d'autres modules demande une isolation que nous fournissons.
- Coût : un essai = un appel modèle (quelques dizaines à centaines d'appels par capacité et par exécution, ordre de grandeur à mesurer) + le calcul du rejeu. D'où le budget par module.
- Un optimiseur capable cherche à tricher son évaluateur : jeu réservé et contrôles piégés sont obligatoires, pas optionnels.

## 6. Lots

1. **Pilote** : corpus de rejeu + évaluateur sur une capacité de lecture (ex. `fastpanel.sites` ou `vue`), adaptateur OpenEvolve, sans rien déployer.
2. **Mode ombre** en lecture seule, routage pondéré, retour instantané.
3. Archive/lignée/tombes, budget, autonomie gagnée.
4. Écritures simulées en ombre, vérificateur indépendant pour l'irréversible.
5. Créer / élaguer / recomposer ; observations vers le noyau.
6. Écran ; export git et store.
## 7. État de la construction (17-10-2026)

**Construit, testé, déployé sur Amizo (Linux, suite complète verte) :**

| Pièce | Fichier | Ce qu'elle fait |
|---|---|---|
| Points d'évolution | `noyau/CN_points.py` | contrat JSON, résolveur de compatibilité, hôtes d'exécution, disjoncteur (3 fautes en 10 min), **ombre**, **routage par part du trafic** (tranche stable), retour instantané, chargement du texte vérifié sans bytecode |
| Corpus de rejeu | `noyau/CN_rejeu.py` | les entrées réelles de chaque point, comptées ; **partition réservée** (1 cas sur 5) jamais montrée au générateur ; borne ; cas dorés jamais évincés |
| Évaluateur | `noyau/CN_evaluateur.py` | équivalence par paliers, gain mesuré à part sur le réservé, **bruit de mesure**, et **auto-test par mutations** (il dit si son corpus est trop faible) |
| Orchestrateur | `noyau/CN_evolution.py` | cibler (valeur = appels × durée, muet si non mesuré), proposer, écrire l'EC au format universel, ombre, paliers 10/50/100 %, visite à 30 jours, tombes, **chaîne d'empreintes** |
| Orfan v1 | `orfan/CN_orfan.py` | profil par lignes exécutées, 5 optimisations déterministes (zéro jeton), moteur à modèle (stratège / exécutant), composition ; **ne connaît pas le noyau** |
| Module Évolution | `modules/evolution/` | cibles, état, proposer, retour, visiter comme capacités (droits, preuve, retour), moteur périodique des paliers, 4 réglages |
| Pilote | `modules/vue/` | `verdict.composer` est un point d'évolution (référence EC0, façade, contrat, corpus doré de 49 cas) |
| Outils | `outils/CN_bornes.py`, `CN_entete.py`, `CN_renommer.py` | format universel, versions cohérentes, `--monter`, renommage `CN_` |

**Chiffres mesurés, pas annoncés**
- Le corpus doré de `vue` attrapait **70 %** des variantes fausses avec 15 cas, **92 %** avec 49 (l'évaluateur l'a dit, on l'a renforcé).
- Un gain n'est retenu que s'il dépasse 5 % **et** deux fois le bruit de mesure de la machine.
- Suite complète : 1 441 bancs sur Linux, 0 échec.

**Ce qui est vrai à ce jour, dit sans détour**
- **Aucune EC n'est en service nulle part.** Tout le mécanisme existe et est éprouvé sur des cas synthétiques et sur `vue`, mais aucun gain réel n'a encore été mesuré en production.
- Sur Amizo, le corpus de `vue` compte 49 cas dorés pour un minimum de 200 : l'évaluateur répondra « corpus trop étroit » tant que le trafic réel n'aura pas rempli le corpus. C'est voulu.
- Le moteur **à modèle** n'a été éprouvé qu'avec un faux modèle : il reste à le brancher sur un rôle réel du module Modèles et à mesurer son coût en jetons.
- Le module Évolution est déployé mais **non activé** sur Amizo : l'activer est un choix de l'administrateur.

**Reste à faire**
1. Extraire d'autres points (`securite.analyse`, `mesures.moteur`, `fastpanel`, `sensorium`) pour avoir plusieurs cibles réelles.
2. Activer l'évolution sur Amizo, laisser le corpus se remplir, lancer une vraie proposition.
3. L'écran Cockpit/Atelier (la maquette) branché sur les capacités du module.
4. Orfan R&D : génome prompts et politiques, co-évolution, archive par contextes.
5. EC dans un autre langage (WebAssembly d'abord).

### 7 bis. Premier gain réel mesuré (17-10-2026) : `contacts.signaux`

Une variante proposée à la main (comme un modèle l'aurait fait) pour le rapprochement des doublons, jugée par l'évaluateur sur 88 entrées (28 cas dorés + 60 carnets de 80 à 400 fiches) :

| Variante | Verdict | Gain | Bruit de mesure | Tient sur le jeu réservé |
|---|---|---|---|---|
| motifs précompilés **seulement** (sans cache, sans état) | équivalente sur 88/88 | **49 %** | 0,2 % | oui (49 % sur le réservé) |
| motifs précompilés **et** mémoïsation (`lru_cache`) | équivalente sur 88/88 | 93 % | 3 % | oui |

Ce que cette expérience a appris :
- **Un défaut de mon évaluateur trouvé en relisant ma méthode.** Il chronométrait chaque entrée trois fois de suite et gardait la meilleure : une variante qui mémorise serait « chaude » dès le deuxième essai et son gain serait gonflé. Le chronométrage se fait maintenant **en passes à froid** (la référence et le candidat sont rechargés à neuf à chaque passe, chaque entrée n'est jouée qu'une fois par instance). Le gain de 93 % a survécu à la correction, mais le chiffre honnête à retenir est le premier.
- **Le gain structurel (49 %) est devenu la référence du dépôt** (contacts 0.3.0) : il ne dépend d'aucun état ni d'aucun trafic, donc profite à toutes les installations. Son équivalence est prouvée par le corpus doré de 28 cas.
- **La mémoïsation reste une EC d'instance** : son gain dépend de la répétition des valeurs dans le trafic réel de chacun, et c'est la visite à 30 jours qui dira s'il est resté.
- Orfan déterministe n'a rien trouvé sur `vue.verdict.composer` ni sur `contacts.signaux` : le code était déjà propre pour ses cinq règles. C'est la réponse honnête, et la raison d'être du moteur à modèle.


<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->

### 7 ter. Les points d'évolution réels (17-10-2026)

Cinquante-deux points sont déclarés (les dix-neuf premiers sont listés ci-dessous ; les suivants viennent de la même méthode : courrier, mesures, fastpanel, mémoire, notes, dns, modeles, projets, planifie, sauvegardes, flotte, journal), chacun avec sa référence EC, son contrat, son corpus doré (sorties de l'ancien code, données synthétiques) et un plancher de score mesuré (`tests/CN_test_points_reels.py`) :

| Module | Points |
|---|---|
| contacts | `signaux`, `vcard_lire`, `vcard_ecrire`, `csv_apparier`, `csv_fiches` |
| vue | `verdict.composer` |
| notes | `lire_entete`, `md_vers_html` |
| dns | `analyser` (réponse DNS en base64 ; une réponse illisible est rendue en `erreur`) |
| agenda | `ical_lire` |
| memoire | `perception_monde`, `json_extraire` |
| planifie | `decrire`, `collisions` |
| flotte | `lire_sortie`, `lire_metriques` |
| ged | `media_kind` |
| courrier | `roles_uniques` |
| agents | `resume_resultat` |

**Règles apprises à l'extraction**

- Une EC ne lit jamais l'horloge : l'instant (ou le décalage horaire) est une entrée que la façade du nexus lit (`agenda.ical_lire`, `memoire.perception_monde`). Les attributs `now`, `today`, `random`… sont refusés par l'analyse de pureté, même sur un module admis (`datetime`, `ipaddress`, `shlex` le sont).
- Une fonction pure qui **décide ou filtre l'accès** reste nexus : verdicts de sécurité, filtrage des menus par droits, destinataires d'un message, validation d'un plan, détection d'un secret, et `planifie.cibles` (servie à la détection des commandes destructrices).
- Le collecteur du Sensorium est un démon séparé, sans service de points : il reste hors EC tant qu'il n'en a pas.
- Les fonctions qui mêlent entrées-sorties et calcul (`fastpanel.lire_*`, `courrier.corps`, `courrier.pieces_jointes`) se scindent d'abord (lire, puis calculer) ; l'extraction vient ensuite.
- Un point dont le corpus ne peut pas atteindre une partie du code (un prédicat renvoyé mais jamais lu) a un plancher de score bas, dit tel quel (`planifie.collisions`, 0,60) : le plancher n'est pas un souhait, c'est une mesure.
- L'évaluateur interrompt un candidat qui boucle sans fin (`appel_borne`, délai du contrat) : une mutation de condition d'arrêt figeait l'évaluation.

**Outil** : `outils/CN_extraire_point.py` (voir son en-tête) écrit la référence, le contrat, le corpus, la déclaration au manifeste, la façade et la ligne de test.


### 8. Ce qui n'est PAS encore construit : les points de politique et de prompt (17-10-2026)

Les cinquante-deux points actuels sont tous **à équivalence** : une variante est acceptée si elle rend les mêmes sorties que la référence, plus vite. C'est le seul critère que l'évaluateur sache juger.

Les prompts (`PROMPT_DISTILLATION`, `PROMPT_VETO`, `PROMPT_EPISODE`, `REGLES` des agents, `prompt_systeme`) et les politiques (seuils du Sensorium, `_etat` des sauvegardes, `FIN_SUPPORT_PHP`, seuils de la mesure) ne s'évaluent pas ainsi : une meilleure variante rend une sortie DIFFÉRENTE. Il faut un second protocole :

1. des signaux réels étiquetés (acquittements sans geste, corrections de l'utilisateur, relances) captés au fil de l'eau par le noyau, jamais par le module évolué ;
2. une mesure déclarée au manifeste (« part des alertes acquittées sans geste ») ;
3. un corpus d'entrées avec leur étiquette, partitionné comme le rejeu (un cinquième réservé) ;
4. une variante est meilleure si son score dépasse celui de la référence sur le jeu réservé ET qu'elle ne dégrade aucun cas protégé ;
5. une mise en service par ombre, où les deux sorties sont gardées et l'écart n'est plus une faute mais une mesure, jusqu'à ce que l'étiquette réelle arrive.

Rien de cela n'existe : ni la capture des signaux, ni le score étiqueté, ni l'ombre à écart toléré. Ces points ne sont donc pas déclarés, pour ne pas simuler un moteur qui n'existe pas.
