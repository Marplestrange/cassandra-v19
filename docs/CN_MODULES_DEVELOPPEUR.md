<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Écrire, distribuer et installer un module -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Écrire, distribuer et installer un module : le manifeste (importance, dépendances versionnées, points d'extension), le cycle de vie, la page App Store, la santé, le mode sûr. -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=7b5a66 ▼▼▼ -->
# Écrire, distribuer et installer un module

## Créer
```
python CN_main.py module nouveau mon_module --nom "Mon module" --famille gestion --importance optionnel --dest donnees/extensions
```
Le squelette est valide, se charge, s'active et répond (`mon_module.etat`). `python CN_main.py paquet construire mon_module --cle editeur.pem` en fait une archive `.cmod` signée.

## Le manifeste, ce qui compte pour un module de magasin
- **`importance`** (`vital`, `important`, `optionnel`) et **`sans`** (une phrase : ce qui s'arrête quand on le désactive). Un module essentiel est vital. Ils se montrent sur la page Modules et dans l'examen d'une archive.
- **Dépendances versionnées** : `requiert = ["droits", "dns >=0.2, <1"]`. La version installée doit y répondre, sinon l'installation et l'activation le disent.
- **`conflits = ["autre"]`** : refusé à l'activation si l'autre est actif (dans les deux sens). **`suggere = [...]`** : sert mieux avec, sans l'exiger.
- **`fournit = ["courrier"]`** : un nom de service. Un autre module peut `requiert = ["courrier"]` sans savoir QUEL module le rend ; l'id exact d'un module l'emporte sur un fournisseur.
- **Points d'extension** (à la façon des hooks de Dolibarr) : un module offre `[[points_extension]] id = "colonne", libelle = "…", attend = ["titre"]` ; un autre y branche `[[contributions]] point = "hote:colonne", id = "prix", libelle = "…", donnees = { titre = "Prix" }`. Le module hôte lit ce qu'on branche chez lui par `modules.contributions` (les modules ACTIFS seulement) sans connaître les contributeurs. Une contribution vers un point inexistant, ou sans les clés attendues, est un défaut ; vers un module absent, elle dort.
- **`permissions`** : ce que le module DEMANDE (réseau, écritures, privilèges…).

## Le cycle de vie (noyau/CN_cycle.py, capacités du module `modules`)
1. **Examiner** (`modules.examiner`, ou téléversement `POST /api/televerser/modules.examiner`, 32 Mo au plus) : l'archive va en **quarantaine**, rien n'est posé. L'examen dit : nouveau, mise à jour ou version plus ancienne ; l'éditeur et la signature ; les permissions demandées, et celles demandées **en plus** de la version en place ; ce qui manque (dépendances, versions), les conflits avec un module actif, ce qu'elle casserait chez les autres.
2. **Installer** (`modules.installer`) : exige le **consentement aux permissions telles que montrées** (leur empreinte), re-vérifie l'archive, sauvegarde la version en place, dépose le dossier dans les extensions. Le module reste **inactif** jusqu'à son activation.
3. **Retour arrière** (`modules.retour_arriere`) : remet une version sauvegardée ; la version courante part elle-même en sauvegarde. **Désinstaller** (`modules.desinstaller`) : le dossier part en sauvegarde, les données restent (purge sur demande, elles partent alors aussi en sauvegarde). Ce qui est livré avec le noyau ne se remplace ni ne se désinstalle par archive.
4. **Politique** (réglage `modules.politique_confiance`) : `signes` (défaut) n'accepte que les paquets signés par une clé posée dans `config/cles/<éditeur>.pub` ; `tous` admet un paquet non signé, à ses risques.
5. **Registre** (réglage `modules.registre_url`) : l'index JSON d'un magasin ; une archive y est téléchargée chez l'hôte du registre et de lui seul, son empreinte est vérifiée contre l'index, puis elle est **examinée comme une archive déposée** : le registre n'a aucun passe-droit.

La page **App Store** (menu avatar) fait tout cela : déposer une archive, parcourir le registre, gérer les modules installés (versions, retour arrière, désinstallation).

## Santé et mode sûr
- `modules.sante` rassemble ce que le noyau mesure déjà (moteurs et leur disjoncteur, détecteurs coupés, activité des capacités sur 24 h) en un verdict : sain, à surveiller, en échec.
- `CASSANDRA_MODE_SUR=1` démarre la maison avec ses seuls modules livrés : un module installé qui bloque le démarrage ne peut plus le faire.

## Ce que ce système ne fait PAS (et qu'il faut savoir)
- **Les permissions sont déclaratives.** Un module installé tourne **dans le processus de Cassandra**, avec ses droits : seul l'espace utilisateur est appliqué. La politique « signés seulement » et le consentement à l'examen sont la protection ; le cloisonnement par processus est à venir. N'installez que ce que vous avez de bonnes raisons de croire.
- Pas de modules payants ni de clés de licence, pas de mise à jour automatique : une mise à jour est une archive qu'on examine et qu'on accepte.
- Pas encore de champs supplémentaires sur les objets (extrafields) ni de listes de valeurs configurables (dictionnaires) : les points d'extension sont le mécanisme général, à vous d'en offrir.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : le mode d'emploi du module store -->
<!-- EC : néant (aucun point d'évolution) -->
<!-- LIEN : noyau/CN_cycle.py, noyau/CN_manifeste.py, noyau/CN_nouveau.py, interface/CN_appstore.js, interface/CN_modules-page.js, tests/CN_test_cycle.py, tests/CN_test_installation.py -->
