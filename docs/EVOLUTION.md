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
- S'applique aux modules, aux prompts d'agents (`itare.prompt 1.2 · EC14`), aux politiques (`sensorium.seuils 1.0 · EC6`) et, plus tard, au moteur Orfan. **Le noyau** a une version dépôt et pas d'EC : il est hors évolution.
- Une EC ne peut changer ni le manifeste, ni les signatures de capacités, ni les permissions (contrôle à chaque promotion).
- **Version suivie**, par module : *Évolution* (la dernière EC prouvée), *Dépôt* (sans évolution) ou *Évolution éprouvée* (seulement une EC confirmée à J+30). Changer de version suivie, comme revenir à une EC ou au dépôt, est un aiguillage journalisé : rien n'est détruit.
- **Proposer au dépôt** : une EC devient un patch git ; une fois fusionnée, elle est « intégrée » à la version dépôt.
- **Sortie d'une nouvelle version dépôt** : les pièces EC sont rejouées sur la nouvelle base. Reportées (0 écart au rejeu), intégrées (déjà dans le dépôt), en conflit (renvoyées au moteur) ou retirées (le gain disparaît : tombe). Le résultat est une nouvelle EC sur la nouvelle base, qui passe par l'ombre.

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
