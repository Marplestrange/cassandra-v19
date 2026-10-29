# Cassandra V19

Cassandra est une plateforme d'administration et de gestion où une IA autonome, Cassandra, travaille avec son second, Itare : elle surveille
les machines, les sites et les sauvegardes, tient la mémoire, le courrier, les projets et les contacts, vend des billets, et agit seule dans les
limites que l'administrateur fixe.

La V19 est une architecture **noyau + modules**. Le noyau est petit et ne connaît aucun métier. Tout le reste (billetterie, courrier, sauvegardes,
sécurité, sociétés, thèmes…) est un **module**, qui s'installe, s'active, se met à jour et se retire sans toucher au noyau, et qui se trouve dans
la **Logithèque**, le magasin d'applications de Cassandra.

> Principe de souveraineté : Cassandra n'attend jamais un humain. La sûreté vient de la **réversibilité** (preuve, retour arrière, journal), jamais
> d'une permission à demander. Un humain agit en voie parallèle, et le noyau le sait.

## Installer

Sur un serveur Linux neuf avec systemd (Debian ou Ubuntu de préférence), en root :

```bash
curl -fsSL https://raw.githubusercontent.com/Marplestrange/cassandra-v19/main/CN_amorcer.sh | sudo bash
```

Le script installe ce qui manque (git, python3, curl, `cryptography`, openssl, sudo, cron, iptables, ssh, sshpass, Tailscale ; apt, dnf, yum, zypper,
pacman ou apk), récupère les sources dans `/opt/cassandra-sources`, puis installe le noyau et **tous** les modules. Les bibliothèques de la voix
s'installent avec le module voix.

```bash
... | sudo bash -s -- --module billetterie        le noyau et ce module seulement
... | sudo bash -s -- --racine /srv/cassandra     un autre dossier racine
... | sudo TAILSCALE_AUTHKEY=tskey-... bash       la machine rejoint le réseau Tailscale seule
```

L'application écoute sur `127.0.0.1:9000` : ouvrez-la par un tunnel (`ssh -L 9000:127.0.0.1:9000 utilisateur@serveur`) ou derrière un proxy HTTPS.
**Le premier compte créé sur l'écran de connexion devient le superadministrateur** : créez-le tout de suite.

Mise à jour : relancer la même commande, ou `./CN_deploy.sh` dans `/opt/cassandra-sources`. Une nouvelle version se pose à côté de l'ancienne,
est prouvée, puis la bascule se fait d'un coup ; à la moindre preuve manquante, le retour arrière est automatique.

## Ce qu'il y a dedans

| Famille | Modules |
|---|---|
| **Socle** | `comptes`, `droits`, `societes`, `reglages`, `menus`, `modules` (la Logithèque), `affichage`, `themes`, `webauthn` |
| **Supervision** | `vue` (la vue d'ensemble), `jour`, `proactif`, `sensorium`, `mesures`, `journal`, `sauvegardes`, `planifie`, `flotte`, `evolution`, `notifications` |
| **Sécurité** | `securite`, `urgence`, `coffre`, `certificats` |
| **Hébergement** | `fastpanel`, `sites`, `dns` |
| **Travail** | `contacts`, `courrier`, `agenda`, `projets`, `taches`, `notes`, `canvas`, `ged`, `memoire` |
| **Échanges** | `salon`, `agents` (Cassandra et Itare), `mandats`, `telegram`, `canaux`, `voix`, `modeles` |
| **Métiers** | `billetterie`, `dolibarr` (le pont vers une instance Dolibarr) |

La **billetterie** va jusqu'au bout : événements, salles, tarifs, vente en ligne (Stripe, PayPal, HelloAsso), caisse hors ligne, contrôle par QR,
revendeurs et artistes avec leurs commissions et leur espace, liste d'attente, remboursements, comptes clients, courriels, boutique publique
(`docs/CN_BILLETTERIE.md`).

## La Logithèque : le magasin d'applications

Une page (menu de l'avatar) où se gèrent les modules, leurs sources, leur sécurité et l'autonomie de Cassandra sur eux. Pour un compte ordinaire :
**Mes applications**. Elle remplace l'ancienne page des modules (`docs/CN_LOGITHEQUE.md`).

- **Vue d'ensemble, Installés, Mises à jour, Boutique, Sources, Sécurité et confiance, Santé, Journal.** Un module montre ses dépendances, ses
  permissions, sa santé et ses versions avant tout geste.
- **Cassandra gère les modules seule** (`docs/CN_AUTONOMIE_MODULES.md`). La page lui laisse l'initiative et montre à l'utilisateur ce qu'elle a fait,
  avec le pourquoi. L'utilisateur peut tout **défaire**, la mettre en **pause**, **verrouiller** un module ou lui **demander** quelque chose.
  Les gestes directs sont derrière un Mode avancé, et leur impact se dit avant.
- **Le niveau d'autonomie est le choix de l'administrateur**, jamais un interdit codé.
- **Les modules viennent d'un registre** (le registre officiel, verrouillé et daté, ou un autre que l'administrateur ajoute) et se livrent en
  **paquets** `.cmod` : empreinte de chaque fichier, signature Ed25519 de l'éditeur, extraction sûre. L'administrateur déclare les éditeurs de
  confiance par leur clé publique (`config/cles/`) ; un paquet falsifié, d'un éditeur inconnu ou dangereux est refusé. Les **permissions** d'un module
  sont dites avant son installation. Le noyau ne se fie jamais au store : il revérifie tout (`docs/CN_STORE.md`).
- **Écrire un module** : `docs/CN_MODULES_DEVELOPPEUR.md` (le manifeste, `brancher(ctx)`, les capacités, les migrations, le paquet).

```
python CN_main.py module liste                        un module par ligne : famille, état, version
python CN_main.py module activer ID                   active d'abord ses dépendances
python CN_main.py module desactiver ID [--en-cascade]
python CN_main.py paquet construire DOSSIER --cle PRIVEE.pem     un paquet signé, reproductible
python CN_main.py paquet verifier ARCHIVE
```

Activer ou désactiver un module change le menu et les fonctions **à chaud**, sans redémarrer. Désactiver n'efface rien : objets, événements et
savoir-faire du module restent. Un module qui a des scripts d'installation ne s'active que s'il est installé (`CN_install.sh --module ID`), car le
noyau tourne sans privilège.

## Les quatre enjeux du moteur

| Enjeu | Ce que le moteur fait |
|---|---|
| **Modularité** | Manifeste validé (objets, événements, capacités, détecteurs, écrans, installation). Ordre d'installation par dépendances, cycles refusés. Un module n'en importe jamais un autre. |
| **Sécurité** | Une écriture déclare périmètre, preuve et retour arrière, sinon le manifeste est refusé. Acteurs autorisés par capacité, refus journalisés. En crise, seule la lecture passe. Cloisonnement par compte et par société. |
| **Évolution** | Les constats qui reviennent sont la matière du moteur d'évolution. Le palier d'une capacité monte (10 réussites) et redescend (2 échecs). Versions de manifeste et `noyau_min`. |
| **Résilience** | Connexions SQLite courtes, écritures qui réessaient. Le résultat d'une écriture est consigné avant sa preuve : au redémarrage, `reprendre()` prouve ou défait. Un détecteur en panne se voit toujours. |

## Les pièces du noyau

```
CN_main.py                  le moteur central : assemble le noyau et fait battre le cycle (percevoir, décider, agir, prouver, apprendre)
noyau/CN_manifeste.py       le contrat d'un module (lecture, validation, ordre d'installation)
noyau/CN_base.py            SQLite : connexions courtes, BEGIN IMMEDIATE avec reprises
noyau/CN_bus.py             le bus d'événements, la lignée, le cloisonnement par portée
noyau/CN_registre.py        le registre des objets, un propriétaire par type
noyau/CN_catalogue.py       le catalogue des capacités et le savoir-faire (paliers raconter / auto / maitre)
noyau/CN_executeur.py       la seule porte d'exécution : droits, palier, preuve, retour arrière, apprentissage
noyau/CN_contexte.py        ce qu'un module voit du noyau, et rien d'autre
noyau/CN_chargeur.py        découverte, isolation, branchement dans l'ordre des dépendances
modules/<id>/               CN_manifeste.toml, CN_module.py (def brancher(ctx)), migrations, scripts d'installation
interface/                  l'interface web, assemblée à partir de ce que les modules déclarent
tests/ , tests-ui/          les bancs (unittest) et les essais de l'interface (Playwright)
```

## Utiliser en développement

Python 3.11 ou plus, et la bibliothèque `cryptography`.

```
python CN_main.py verifier       manifestes, isolation, ordre d'installation, capacités à porter
python CN_main.py etat           résumé du noyau
python CN_main.py tick           une passe de détection
python CN_main.py demarrer       le cycle en continu (interface sur le port 9000)
python -m unittest discover -s tests -p "CN_test*.py" -v
```

Les données vont dans `donnees/` (ou `$CASSANDRA_DONNEES`).

## Les moteurs : le noyau les ordonnance

Une boucle ou une passe qui tourne seule se déclare au manifeste (`[[moteurs]]`) et s'inscrit par `ctx.moteur(id, fonction)`. Le module n'ouvre
jamais de thread : le noyau l'exécute dans un fil surveillé.

| Mode | Se réveille | Exemple |
|---|---|---|
| `periodique` (`toutes_les_s`, 10 s minimum) | à intervalle | mesurer le disque |
| `evenement` (`sur`, un type écouté par le module) | quand l'événement paraît, avec la lignée | réagir à un certificat renouvelé |
| `demande` | seulement si un humain ou un agent le lance | un export |

Pour chaque moteur, le noyau mesure la durée, empêche qu'il s'empile s'il dépasse `duree_max_s` (il est alors dit « figé »), compte les échecs, les
dit au bus et le suspend après cinq échecs de suite. `python CN_main.py moteurs` les liste avec leur état.

## Les droits : déclarés par les modules, vérifiés en un seul endroit

Un module **déclare** ses droits ; une capacité, une entrée de menu ou une tuile y renvoie par `droit = "..."`. Le module `droits` les attribue à des
**comptes** et à des **groupes** ; l'exécuteur les vérifie, et lui seul. Un module qui ne déclare pas ses droits est refusé à l'installation.

```toml
[[droits]]
id = "ecrire"
libelle = "Écrire en compta"
sensible = true            # signalé à celui qui l'attribue

[[capacites]]
id = "passer_ecriture"
droit = "ecrire"           # devient « compta.ecrire »
```

Résolution, du plus fort au plus faible : administrateur › accord ou refus propre au compte › refus d'un groupe › accord d'un groupe › défaut du
droit › non. Quand Itare ou Cassandra agissent **au nom d'un compte**, ils n'ont pas plus de droits que lui. Sans compte (infrastructure, agents
seuls), aucun droit n'est demandé : c'est le **palier** de la capacité, réglé par l'administrateur, qui les borne. Un refus est un événement
(`capacite.refusee`, avec le droit et la raison), et le menu se filtre par droits.

```
python CN_main.py agir droits.regler sujet=sandrine droit=compta.ecrire
python CN_main.py agir droits.groupe groupe=compta libelle=Comptables
python CN_main.py agir droits.membre compte=jules groupe=compta
python CN_main.py agir compta.passer_ecriture --compte sandrine        essayer comme elle : refusé, avec le droit manquant
```

Les comptes, les sociétés (tout compte appartient à une société), les fonctions et le coffre isolé par espace : `docs/CN_UTILISATEURS.md`,
`docs/CN_SOCIETES.md`.

## Les menus : un module déclare, le noyau assemble

```toml
[[menus]]
id = "domaines"          libelle = "Domaines"      ecran = "vue_domaine"
ordre = 10               role = "admin"            icone = "globe"
parent = ""              badge = "constats"
```

Le module `menus` (essentiel) assemble l'arbre : familles, entrées des modules actifs, enfants, filtré par rôle et par droits. Il se rebâtit dès
qu'un module est branché ou débranché. Masquer, renommer, réordonner ou déplacer une entrée se fait pour tous ou pour un compte, par la capacité
`menus.personnaliser_entree` (avec preuve et retour arrière). L'apparence (thèmes, tuiles, gabarits) s'assemble de la même façon
(`docs/CN_AFFICHAGE.md`).

## Les agents : Cassandra, Itare et le palier

Une capacité qui écrit a un **palier** : *raconter* (l'agent dit ce qu'il ferait), *auto* (il le fait, avec preuve et retour), *maître* (il décide
des suites). Le palier monte avec les réussites et redescend avec les échecs ; le plafond est le choix de l'administrateur.

```
python CN_main.py palier                              les capacités qui écrivent, leur palier, les paliers permis
python CN_main.py palier dolibarr.supprimer auto      Cassandra supprime seule (avec corbeille)
```

Les gestes d'urgence (`urgence`) gèlent l'autonomie des agents : ils observent, n'agissent plus.

## Greffer un module après coup

1. **Un module livré avec le noyau** : on ajoute `modules/<id>/` au dépôt ; `CN_deploy.sh` le pousse (inactif) ; `CN_install.sh --module <id>` l'installe.
2. **Une extension, à chaud** : `CN_install.sh --extension ./mon_module` (ou un paquet `.cmod`). Copiée dans `extensions/` (que `CN_deploy.sh`
   ne touche jamais), vérifiée, prouvée, puis **branchée sans redémarrer**. Exemple : `exemples/sentinelle/`.
3. **Un moteur de plus sur un module existant**, sans le modifier : une extension qui écoute ses événements.

Une extension qui porte l'identifiant d'un module livré **le remplace** ; le module livré est mis de côté, pas perdu, et reprend sa place si le
remplaçant est écarté. Seul l'administrateur peut décider de remplacer un module essentiel. Une extension illisible, qui importe un autre module ou
dont une dépendance manque est écartée et dite une fois au bus, sans jamais empêcher le noyau de démarrer.

Un module tourne aujourd'hui dans le processus du noyau : c'est un niveau de confiance « local ». Un module de tiers non fiable exigera une cage
par processus (à construire, voir `docs/CN_STORE.md`).

## Où vit Cassandra

```
/var/cassandra/                 UN seul dossier : on le sauvegarde, on le déplace d'un bloc (CASSANDRA_RACINE)
    releases/<horodatage>/      les versions du noyau ; l'ancienne reste à côté pour le retour arrière
    current -> releases/...     lien relatif
    extensions/                 les modules greffés (un déploiement n'y touche jamais)
    donnees/                    la base du noyau et ses sauvegardes
    config/                     la configuration, les clés publiques des éditeurs, l'unité systemd
    journal/

/var/www/<utilisateur>/data/    le dossier d'un utilisateur (compatible avec FastPanel)
    cassandra/                  son espace Cassandra
```

Le premier administrateur est `fastuser` (`--admin NOM` pour un autre nom). Un module demande l'espace d'un utilisateur par `ctx.espace(utilisateur)`
et ne sort jamais de `/var/www/<utilisateur>/data/cassandra/<module>`. La disposition est décrite une seule fois, dans `exploitation/CN_commun.sh`.

## Exploitation

```
./CN_install.sh                          le noyau seul : utilisateur, dossiers, version, service systemd
./CN_install.sh --tous                   + tous les modules du dépôt
./CN_install.sh --module certificats     + ce module et ses dépendances ; chacun s'installe par SON script,
                                         se prouve par SA vérification, se retire seul si la preuve manque
./CN_install.sh --retirer certificats
./CN_deploy.sh [--a-blanc]               mise à jour : nouvelle version à côté de l'ancienne, bancs, sauvegarde de la base,
                                         bascule atomique, preuve de chaque module actif qui a changé, retour arrière seul
outils/CN_pousser.sh <hote> install|deploy [options]    envoie l'arbre par SSH et lance le script là-bas
```

Le noyau tourne en service `Type=notify` : il annonce qu'il est prêt, puis donne signe de vie ; systemd tue et relance une boucle figée
(`WatchdogSec=120`). L'unité est durcie au plus étroit (utilisateur dédié, système en lecture seule, aucune capacité, appels système filtrés). Un
module qui a besoin de plus ouvre exactement ce qu'il lui faut dans un drop-in nommé, posé par son `CN_installer.sh` et retiré par son `CN_retirer.sh`.

## Pour aller plus loin

`CN_BILAN-V19.md` (où en est le portage), puis `docs/` : `CN_MODULES_DEVELOPPEUR.md`, `CN_LOGITHEQUE.md`, `CN_STORE.md`, `CN_AUTONOMIE_MODULES.md`,
`CN_BILLETTERIE.md`, `CN_SOCIETES.md`, `CN_UTILISATEURS.md`, `CN_EVOLUTION.md`, `CN_AFFICHAGE.md`, `CN_REGISTRE.md`, `CN_FORMAT.md`.

## Licence

AGPL-3.0. Auteur : Atek Drisse, github.com/Marplestrange.
