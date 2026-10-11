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
