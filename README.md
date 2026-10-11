# Cassandra V19

Le noyau de Cassandra et d'Itare. `cassandra.py` (V18, plus de 150 000 lignes) est découpé en **modules** qui se
branchent sur ce noyau par un **manifeste**. Rien ici ne dépend de la V18 : on **porte** la logique module par
module, on ne la réécrit pas.

> Principe de souveraineté : Cassandra n'attend jamais un humain. La sûreté vient de la **réversibilité**
> (preuve, retour arrière, journal), jamais d'une permission. Un humain agit en voie parallèle, et le noyau le sait.

## Les quatre enjeux du moteur

| Enjeu | Ce que le moteur fait déjà | Ce qui reste à construire |
|---|---|---|
| **Modularité** | Manifeste validé (objets, événements, capacités, détecteurs, écrans, installation). Ordre d'installation par dépendances, cycles refusés. Un module n'en importe jamais un autre (vérifié par analyse du code). Un type d'objet a un seul propriétaire ; un module n'émet que ce qu'il a déclaré. | Écrans (couche C4). Compatibilité de versions entre modules. Retrait propre d'un module. Kit de test de contrat par module. |
| **Sécurité** | Une écriture déclare périmètre, preuve et retour arrière, sinon le manifeste est refusé. Acteurs autorisés par capacité, refus journalisés. Crise : seule la lecture passe. **Cloisonnement par compte : toute lecture exige une portée explicite**, l'oubli est une erreur. | **Le périmètre est déclaré, pas encore appliqué** : les modules tournent dans le même processus, un module hostile contournerait `ctx`. Un module tiers exige une cage (processus séparé, systemd). Provenance (contenus non fiables), second avis, intégrité du bus par chaîne de hachage, authentification des comptes. |
| **Évolution** | `recurrences()` : les constats qui reviennent sont la matière du moteur d'évolution. Le palier d'une capacité monte (10 réussites) et redescend (2 échecs). Versions de manifeste et `noyau_min`. | Le moteur d'évolution lui-même, module par module, avec quarantaine et retrait à J+90. Brancher `recurrences()` dessus. |
| **Résilience** | Connexions SQLite courtes, écritures qui réessaient. Le résultat d'une écriture est consigné avant sa preuve : `reprendre()` prouve ou défait au redémarrage. Un détecteur en panne se voit toujours et un disjoncteur le suspend après 5 pannes. Un abonné en échec ne fait pas taire les autres. Preuve manquante : retour arrière seul. | Surveillance de la boucle elle-même (watchdog extérieur), migrations de schéma versionnées, sauvegarde de la base du noyau, budget de ressources par module. |

## Les pièces

```
main.py                  le moteur central : assemble le noyau et fait battre le cycle (percevoir, décider, agir, prouver, apprendre)
noyau/manifeste.py       le contrat d'un module (lecture, validation, ordre d'installation)
noyau/base.py            SQLite : connexions courtes, BEGIN IMMEDIATE avec reprises
noyau/bus.py             le bus d'événements, la lignée, le cloisonnement par portée
noyau/registre.py        le registre des objets, un propriétaire par type
noyau/catalogue.py       le catalogue des capacités et le savoir-faire (paliers raconter / auto / maitre)
noyau/executeur.py       la seule porte d'exécution : palier, preuve, retour arrière, apprentissage
noyau/contexte.py        ce qu'un module voit du noyau, et rien d'autre
noyau/chargeur.py        découverte, isolation, branchement dans l'ordre des dépendances
modules/<id>/            manifeste.toml, module.py (def brancher(ctx)), scripts d'installation
tests/                   bancs, stdlib seule
```

## Utiliser

Python 3.11 ou plus, bibliothèque standard seule.

```
python main.py verifier       manifestes, isolation, ordre d'installation, capacités à porter
python main.py etat           résumé du noyau
python main.py tick           une passe de détection
python main.py demarrer       le cycle en continu
python -m unittest discover -s tests -v
```

Les données vont dans `donnees/` (ou `$CASSANDRA_DONNEES`).

## Les moteurs : le noyau les ordonnance

Une boucle ou une passe qui tourne seule se déclare au manifeste (`[[moteurs]]`) et s'inscrit par `ctx.moteur(id, fonction)`.
Le module n'ouvre jamais de thread : le noyau l'exécute dans un fil surveillé.

| Mode | Se réveille | Exemple |
|---|---|---|
| `periodique` (`toutes_les_s`, 10 s minimum) | à intervalle | mesurer le disque |
| `evenement` (`sur`, un type écouté par le module) | quand l'événement paraît, avec la lignée | réagir à un certificat renouvelé |
| `demande` | seulement si un humain ou un agent le lance (`lancer`) | un export |

Pour chaque moteur le noyau mesure la durée, empêche qu'il s'empile s'il dépasse `duree_max_s` (il est alors dit « figé »),
compte les échecs, dit chaque échec au bus et le suspend après cinq échecs de suite (`lancer` le réarme : voie humaine).
`python main.py moteurs` les liste avec leur état.

## Le pont Dolibarr : Cassandra pilote une instance, elle ne la remplace pas

Dolibarr garde son PHP et sa base ; `modules/dolibarr/` le pilote par son API REST. Il **lit** (santé, version, modules actifs, comptes, factures impayées,
objets aux champs bornés) et il **agit**, par des capacités qui ont toutes leur périmètre, leur preuve (relire ce qui a été écrit) et leur retour arrière :

| Capacité | Risque | Retour arrière |
|---|---|---|
| `creer`, `modifier` (tiers, contacts, produits, projets) | moyen | supprimer ce que l'acte vient de créer / remettre les valeurs d'avant |
| `creer_brouillon` (facture, devis, commande) | moyen | supprimer le brouillon, tant qu'il en est un |
| `supprimer` | élevé | une **corbeille** : copie entière de l'objet avant suppression ; on le recrée (seul l'identifiant change) |
| `restaurer` | moyen | supprimer l'objet recréé, la copie restant en corbeille |
| `valider_facture` | élevé | repasser en brouillon (impossible si payée ou comptabilisée) |

**Le plafond d'autonomie est un choix de l'administrateur**, jamais un interdit codé : le manifeste fixe le maximum permis, par défaut Cassandra *raconte*
ce qu'elle ferait (un humain agit en voie parallèle), et l'administrateur monte le palier quand il le décide :

```
python main.py palier                              les capacités qui écrivent, leur palier, les paliers permis
python main.py palier dolibarr.supprimer auto      Cassandra supprime seule (avec corbeille) ; l'événement savoir.regle le journalise
```

Réglage : `config/dolibarr.conf` (`url`, `hote`, `fichier_cle`, `delai` ; voir `dolibarr.conf.exemple`) et la clé dans `config/dolibarr.key` (0640, groupe du noyau).
La clé ne figure dans aucun événement, aucun objet, aucun message d'erreur. En production, Dolibarr se joint par le réseau privé, sans passer par Cloudflare (qui
bloque les machines de datacenter). **La clé donne les droits de son utilisateur Dolibarr : en créer un dédié, aux droits limités.**

## Le Sensorium : le collecteur de la V18, gardé entier

`cassandra_knowledge_collector.py` (6 560 lignes) devient `modules/sensorium/sensorium.py` : **renommé, jamais découpé**. Il reste un service à part,
qui tourne en root pour tout voir et ne peut écrire que dans son dossier (`donnees/sensorium/`, 0700) et son socket (`/run/sensorium/`). Seules
**six lignes** diffèrent de la V18 : des chemins devenus réglables par variable d'environnement (`SENSORIUM_DB`, `SENSORIUM_SOCKET`...), avec les mêmes
valeurs par défaut, pour qu'il tienne dans le dossier unique de Cassandra.

Le module qui l'entoure le relie au noyau, sans rien mesurer lui-même :

- un moteur relève la santé et les ressources (toutes les 30 s) et en fait un objet `machine` du registre ; un changement de santé est un événement ;
- un **collecteur muet est un constat**, jamais un silence ; des unités systemd en échec aussi ;
- des lectures (`sante`, `metriques`, `monde`, `entite`, `historique`, `changements`) aux arguments validés avant de toucher le socket ;
- un menu, un écran, et deux tuiles (santé sur l'accueil, ressources).

`install.sh --module sensorium` installe le service (son unité vit dans `config/`, liée dans systemd), l'ouvre au groupe du noyau pour ce seul socket, et ne
valide l'installation que si le collecteur répond **à root et au noyau**. `deploy.sh` rejoue l'installation d'un module à scripts quand il change.

## Les menus : un module déclare, le noyau assemble

Un module ne touche jamais à l'interface pour s'y inscrire. Il déclare ses entrées dans son manifeste :

```toml
[[menus]]
id = "domaines"          libelle = "Domaines"      ecran = "vue_domaine"      # un écran du même module
ordre = 10               role = "admin"            icone = "globe"
parent = ""              badge = "constats"        # un menu du module, ou « autre:menu » ; compteur affiché
```

Le module `menus` (essentiel, avec ses trois moteurs) assemble l'arbre : familles dans l'ordre du noyau, puis entrées du module, puis leurs enfants,
filtré par rôle ; une entrée sans page ni enfant visible disparaît ; un parent dont le module est inactif fait remonter l'enfant au premier niveau. Il
se rebâtit dès qu'un module est branché ou débranché (et toutes les cinq minutes par filet), et tient les compteurs à jour. Activer ou désactiver un
module change le menu **à chaud**, sans redémarrer ni retoucher l'interface.

Personnalisation : masquer, renommer, réordonner, déplacer une entrée, pour tous ou pour un compte (celui du compte l'emporte, et ne touche
personne d'autre), par la capacité `menus.personnaliser_entree` (preuve et retour arrière comme toute écriture).

```
python main.py agir menus.lire_menu role=admin                                  l'arbre, en JSON
python main.py agir menus.personnaliser_entree entree=dns:domaines masque=true  masquer une entrée
```

## Les droits : le modèle de Dolibarr, appliqué en un seul endroit

Un module **déclare** ses droits, comme les `rights` d'un module Dolibarr ; une capacité, une entrée de menu ou une tuile y renvoie par `droit = "..."`.
Le module essentiel `droits` les attribue à des **comptes** et à des **groupes** ; l'exécuteur les vérifie, et lui seul.

```toml
[[droits]]
id = "ecrire"
libelle = "Écrire en compta"
sensible = true            # signalé à celui qui l'attribue
# defaut = true            # accordé d'office à tout compte

[[capacites]]
id = "passer_ecriture"
droit = "ecrire"           # devient « compta.ecrire »
```

Résolution, du plus fort au plus faible : **administrateur** › accord ou refus propre au compte › refus d'un groupe › accord d'un groupe › défaut du droit › non.
Le premier administrateur est `fastuser`, posé une seule fois (`[droits] admin_initial` pour en choisir un autre) ; s'il est retiré ensuite, il ne revient pas.

Ce que cela règle : quand Itare ou Cassandra agissent **au nom d'un compte**, ils n'ont pas plus de droits que lui. Sans compte (infrastructure, agents seuls)
aucun droit n'est demandé : les agents sont souverains, et c'est le **palier** de la capacité, réglé par l'administrateur, qui les borne.
Un refus est un événement (`capacite.refusee`, avec le droit et la raison). Le menu se filtre par droits : un compte ne voit pas ce qu'il ne peut pas ouvrir.

```
python main.py agir droits.regler sujet=sandrine droit=compta.ecrire             accorder (valeur=refuse | herite)
python main.py agir droits.groupe groupe=compta libelle=Comptables               créer un groupe (supprimer=true)
python main.py agir droits.membre compte=jules groupe=compta                     l'y mettre (present=false : l'en retirer)
python main.py agir droits.mes_droits compte=sandrine                            ce qu'elle détient
python main.py agir compta.passer_ecriture --compte sandrine                     essayer comme elle : refusé, avec le droit manquant
```

Tout est réversible (l'état d'avant est gardé), et nommer un administrateur est un droit à part (`droits.nommer_admin`).
Pas encore fait : filtrer les tuiles (le champ `droit` est déjà dans le contrat), l'authentification (mots de passe, WebAuthn) qui dira *quel* compte agit.

## Activer et désactiver un module (le menu des modules)

Chaque module a un état, qui vit dans la base du noyau : **disponible** (le manifeste est là), **installé** (ses scripts ont posé et prouvé ce
qu'il faut sur la machine), **actif** (le noyau l'a branché). Désactiver n'efface rien : les objets, les événements et le savoir-faire du module
restent, comme dans Dolibarr ; réactiver retrouve tout.

```
python main.py module liste                     un module par ligne : famille, état, version
python main.py module activer ID [--sans-dependances]
python main.py module desactiver ID [--en-cascade] [--forcer]
```

Le noyau en marche voit le changement et **branche ou débranche à chaud**, sans redémarrer : moteurs arrêtés, détecteurs et capacités qui ne
répondent plus, abonnements retirés, constats ouverts suspendus. Les règles :

- activer un module active d'abord ses dépendances (`requiert`) ; désactiver un module requis par un module actif est refusé, sauf `--en-cascade`
  (les dépendants d'abord) ;
- un module `essentiel = true` ne se désactive pas (sauf `--forcer`) ;
- un module qui a des scripts d'installation ne s'active que s'il est installé : cela demande l'administrateur système (`install.sh --module ID`) ;
  le noyau tourne sans privilège et ne s'installe jamais lui-même ;
- chaque changement est un événement (`module.active`, `module.desactive`) avec son auteur : un humain, un agent, Cassandra elle-même. Elle sait.

Pour l'interface : `Noyau.catalogue_modules()` rend, par module, tout ce qu'un menu affiche (état, famille, dépendances et dépendants, nombre de
moteurs, détecteurs et capacités, et pour chaque action si elle est possible et pourquoi pas), et `activer` / `desactiver` en sont les boutons.

## Un module store à terme : le contrat est prêt

Le noyau est pensé pour qu'un jour des modules viennent d'ailleurs (voir `docs/STORE.md`). Déjà en place :

- le manifeste dit tout ce qu'une vitrine affiche (`auteur`, `licence`, `site`, `famille`, `version`) et ce que le module **demande**
  (`[permissions]`) avant qu'il soit installé ; `api` fixe la version majeure du contrat visée (`API_NOYAU`) ;
- un module est livré en **paquet** (`.cmod`) : empreinte de chaque fichier, signature Ed25519 de l'éditeur, extraction sûre ;
- l'administrateur déclare les éditeurs de confiance par leur clé publique dans `config/cles/` ; un paquet falsifié, d'un éditeur inconnu ou
  dangereux est refusé (`install.sh --extension mod.cmod`, `--non-signe` pour le choisir en connaissance de cause).

```
python main.py paquet construire DOSSIER --cle PRIVEE.pem        un paquet signé, reproductible
python main.py paquet verifier ARCHIVE                           intégrité et signature (code de sortie 3 : intègre mais non signé)
python main.py paquet extraire ARCHIVE DEST [--non-signe]
```

## Greffer un module après coup

Trois voies, un seul contrat (le manifeste) :

1. **Un module livré avec le noyau** : on ajoute `modules/<id>/` au dépôt, `deploy.sh` le pousse (inactif), `install.sh --module <id>` l'installe et l'active.
2. **Une extension, à chaud** : `install.sh --extension ./mon_module`. Elle est copiée dans `custom/` (hors des versions : `deploy.sh`
   n'y touche jamais), vérifiée, prouvée par son `verifier.sh`, ajoutée aux modules actifs, et **le noyau la branche sans redémarrer**.
   Exemple complet : `exemples/sentinelle/` (un moteur, un détecteur, un type d'objet, des événements).
3. **Un moteur de plus sur un module existant, sans le modifier** : une extension qui écoute ses événements (`evenements.ecoute`) et
   déclare son moteur `sur` l'un d'eux. Le module d'origine n'est jamais retouché.

Garde-fous de la greffe : une extension ne peut pas se dire « interne » ni prendre l'id d'un module livré ; une extension illisible, qui
importe un autre module ou dont une dépendance manque est **écartée et dite une fois au bus** (`noyau.greffe_refusee`), sans jamais
empêcher le noyau de démarrer ni ce qui tourne déjà. Le code d'une extension tourne dans le processus du noyau, sous l'utilisateur
dédié et l'unité durcie : c'est un niveau de confiance « local ». Un module de tiers non fiable exigera une cage par processus.

## Où vit Cassandra : un dossier, comme Dolibarr

```
/var/cassandra/                 UN seul dossier : on le sauvegarde, on le déplace d'un bloc (CASSANDRA_RACINE)
    releases/<horodatage>/      les versions du noyau ; l'ancienne reste à côté pour le retour arrière
    current -> releases/...     lien RELATIF : la racine peut changer de place sans rien casser
    custom/                     les modules greffés après coup (un déploiement n'y touche jamais)
    donnees/                    la base du noyau et ses sauvegardes
    config/                     la configuration et l'unité systemd (/etc/systemd/system n'en garde qu'un lien)
    journal/

/var/www/<utilisateur>/data/    le dossier d'un utilisateur, à la manière de FastPanel
    cassandra/                  son espace Cassandra, accessible au noyau par groupe (setgid), nulle part ailleurs
```

Les dossiers des utilisateurs suivent la convention de FastPanel (`/var/www/<utilisateur>/`, le « home » dans `data/`) et le premier
administrateur est, comme chez lui, `fastuser`. Ainsi un FastPanel installé **après** Cassandra retrouve les utilisateurs et leurs
dossiers déjà là. Le dossier de Cassandra reste hors de `/var/www` : un utilisateur FastPanel nommé « cassandra » prendrait
`/var/www/cassandra`. Un module demande l'espace d'un utilisateur par `ctx.espace(utilisateur)` et ne sort jamais de
`/var/www/<utilisateur>/data/cassandra/<module>`.

`install.sh` migre seul une ancienne disposition (`/opt/cassandra`, `/var/lib/cassandra`, `/etc/cassandra`, `/var/log/cassandra`) et
crée `fastuser` s'il n'existe pas (`--admin NOM` pour un autre nom, `--racine DIR` pour un autre dossier). La disposition est décrite
une seule fois, dans `exploitation/commun.sh`, que `install.sh` et `deploy.sh` partagent.

## Exploitation

```
./install.sh                          le noyau seul : utilisateur, dossiers, version, service systemd
./install.sh --module certificats     + ce module et ses dépendances ; chacun s'installe par SON script,
                                      se prouve par SA vérification, se retire seul si la preuve manque
./install.sh --retirer certificats
./deploy.sh [--a-blanc]               mise à jour : nouvelle version à côté de l'ancienne, manifestes, bancs,
                                      sauvegarde de la base, bascule atomique, preuve de chaque module actif
                                      qui a changé, retour arrière seul à la moindre preuve manquante
outils/pousser.sh <hote> install|deploy [options]    envoie l'arbre par SSH et lance le script là-bas
```

Le noyau tourne en service `Type=notify` : il annonce qu'il est prêt, puis donne signe de vie ; systemd tue et relance
une boucle figée (`WatchdogSec=120`). L'unité est durcie au plus étroit (utilisateur dédié, système en lecture seule,
aucune capacité, appels système filtrés ; exposition mesurée par `systemd-analyze security` : 1,4 OK). Un module qui
a besoin de plus ouvre exactement ce qu'il lui faut dans un drop-in nommé, posé par son `installer.sh` et retiré par
son `retirer.sh`. Modules actifs : `/etc/cassandra/modules.actifs`.

## Couches

C0 noyau · C1 services communs (authentification, coffre, notifications, mémoire, modèles) · C2 moteurs
(proactif, autonomie, évolution, Itare) · C3 domaines (certificats, sauvegardes, DNS, sites, flotte, courrier…)
· C4 interface. On construit de bas en haut ; chaque couche est prouvée sur une machine vierge avant la suivante.

## Premier module

`modules/certificats` (avec `modules/dns` dont il dépend) : leurs manifestes sont écrits, leur code est à porter
depuis la V18. Le noyau est « terminé » quand ce module tourne de bout en bout sur une machine vierge : installation,
détection, renouvellement, preuve, retour arrière, lignée et un écran.

## Licence

AGPL-3.0, comme la V18.
