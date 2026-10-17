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
