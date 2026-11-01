<!-- ═══════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Dolibarr : la gestion complète -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Dolibarr, la gestion complète : ce que le module sait faire, la clé d'API par compte, le compte de mandat, les paliers -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═══════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=bb164d ▼▼▼ -->
# Dolibarr : la gestion complète

Le module `dolibarr` pilote une instance Dolibarr par son API REST. Il lit, il écrit, et tout geste a sa **preuve** (relire ce qui a été écrit) et son **retour arrière**.

## Ce qu'on peut faire

| Geste | Capacité | Retour arrière |
|---|---|---|
| Encaisser un règlement (partiel ou total) | `encaisser` | supprimer ce règlement (refusé par Dolibarr s'il est rapproché en banque) |
| Préparer un avoir en brouillon | `creer_avoir` | supprimer ce brouillon |
| Garder une relance dans l'agenda du tiers | `relancer` | supprimer l'évènement |
| Valider, signer, refuser un devis | `devis` | remettre le devis en brouillon |
| Facturer un devis signé (brouillon) | `facturer_devis` | supprimer ce brouillon |
| Saisir, valider un don | `don_creer`, `don_valider` | supprimer la promesse ; un don validé ne se défait pas par l'API |
| Enregistrer une cotisation | `cotisation` | supprimer cette cotisation |
| Virer d'un compte bancaire à un autre | `virement_interne` | le virement inverse |
| Ouvrir, clore un projet | `projet` | remettre le statut d'avant |
| Lire ou écrire n'importe où dans l'API | `lire_libre`, `ecrire_libre` | restaurer les champs d'avant (PUT), supprimer ce qui vient d'être créé (POST) |

Avant elles : `creer`, `modifier`, `creer_brouillon`, `supprimer` (avec corbeille), `restaurer`, `valider_facture`. L'écran est `interface/CN_dolibarr-ecran.js`.

## Les réglages propres au compte (plus stricts que le palier, jamais plus larges)

- `dolibarr.itare_ecrire` = `desactive` : l'Itare (ou Cassandra) de ce compte lit, mais n'écrit jamais dans Dolibarr quand il agit seul. Au palier « raconter » il ne fait que proposer, donc la garde ne joue que pour ce qui s'exécute sans accord.
- `dolibarr.itare_seuil` (euros, 0 = aucun) : au-dessus, un agent ne règle pas, ne vire pas, ne saisit pas de don ni de cotisation. Un humain n'y est jamais soumis.
- Le **palier** de chaque geste reste global : c'est le choix de l'administrateur. Un palier par compte demanderait un changement du noyau, non fait.

## Les pages de l'écran

À faire, Factures, Devis (fiche et PDF), Tiers, Contacts (la liste et la fiche de Dolibarr), Banque, Dons, Adhérents, Projets, Projets et Contacts de Cassandra (liens), Produits, Fournisseurs (`payer_fournisseur`), Itare (parle à `agents.converser`, avec la clé du compte), Capacités (`catalogue_api` et les deux réglages ci-dessus), Comptes (qui a une clé), Instance, Mon accès, Requête libre. Le rapprochement bancaire ligne à ligne et le virement SEPA groupé n'ont pas de point d'API dans Dolibarr : ils ne sont pas dans l'écran.

## Le PDF d'une pièce

`piece_pdf` lit le PDF que Dolibarr a produit pour un devis ou une facture (base64, 8 Mo au plus) ; l'écran l'affiche dans un cadre sur adresse locale (`blob:`), sans `sandbox`, comme le visionneur de la GED. Si la pièce n'en a pas, `produire_pdf` le fait produire. Le **reçu fiscal d'un don** ne passe pas par l'API de Dolibarr 24 (« Generation not available for this modulepart ») : il se produit dans Dolibarr. `produire_pdf` (retour : supprimer ce PDF).

## Envoyer un projet ou un contact à Dolibarr

Par défaut une fiche de Cassandra reste « Cassandra seulement ». `envoyer_projet` et `envoyer_contact` la créent chez Dolibarr et posent un lien (objet `dolibarr_lien`, propre au compte). Une fois liée : **Dolibarr fait foi** pour ce qu'il porte (`modifier_lie` envoie la modification chez lui) ; les notes, l'équipe, les jalons et les tâches restent dans Cassandra. Un contact est toujours rattaché à un tiers choisi (`tiers`) ou créé pour l'occasion (`nouveau_tiers`) : il ne devient jamais un tiers. `detacher` rompt le lien et garde les deux copies. `liens` liste ce qu'on a envoyé. Les lectures de Cassandra passent par `[permissions] lectures` (`projets.voir`, `contacts.voir`).

## Une clé d'API par compte

- **Ma clé** : le réglage `dolibarr.cle_api` (secret, portée compte). Dolibarr agit sous le nom de l'utilisateur de cette clé, avec ses droits : l'Itare d'un compte fait ce que Dolibarr permet à cet utilisateur, rien de plus.
- **Un compte sans clé propre lit** (avec la clé de mandat) **mais n'écrit pas**. Il ne tombe jamais sur la clé d'un autre. Le réglage `dolibarr.mandat_pour_tous` (désactivé par défaut) en fait le choix de l'administrateur.
- **La clé de mandat** : `dolibarr.cle_mandat`, ou le fichier `config/dolibarr.key`. Elle sert les moteurs (billetterie, relevé) qui n'ont pas de compte. Un utilisateur Dolibarr aux droits limités vaut mieux qu'un administrateur.
- **La société attendue** : `dolibarr.societe_attendue`. Rempli, le pont vérifie avant chaque écriture que la clé voit cette société, sinon il refuse (une instance à plusieurs entités peut donner une clé qui écrit dans la mauvaise comptabilité).

## Les droits par métier (Paramètres › Droits)

Tout le monde ne doit pas pouvoir tout faire dans Dolibarr. Le module déclare des droits que l'administrateur accorde (à un compte ou à un groupe) ; les administrateurs les ont tous. Chaque capacité demande l'un d'eux : **le serveur refuse le reste**, et l'écran grise les boutons que le compte ne peut pas utiliser (avec « il te manque le droit … » en infobulle).
| Droit | Ce qu'il ouvre | Par défaut |
|---|---|---|
| `consulter` | lire tiers, factures, devis, dons, adhérents, projets, banque, PDF ; l'écran lit par `lire_ecran`, borné à ce qu'il affiche (pas les utilisateurs ni la configuration de Dolibarr) | oui |
| `facturer` | brouillons de devis et factures, avoirs, relances, encaisser un règlement, produire un PDF | non |
| `valider` (sensible) | numéro légal d'une facture (irréversible), valider un don, valider ou clore un projet | non |
| `tiers` | créer, modifier, restaurer tiers, contacts, produits, projets ; les envoyer à Dolibarr ou les en détacher | non |
| `dons` | saisir un don, enregistrer une cotisation | non |
| `tresorerie` (sensible) | virements entre comptes, paiement des factures fournisseurs | non |
| `libre` (sensible) | requête libre sur l'API, en lecture (`lire_libre`, tous les domaines) comme en écriture | non |
| `administrer` (sensible) | supprimer, lire la base (en plus : superadministrateur), réglages, pont de la billetterie | non |

Les droits de Cassandra et ceux de la clé Dolibarr du compte s'ajoutent : il faut le droit ici ET que Dolibarr accepte la clé. Sans le droit `tiers`, la fiche d'un tiers ou d'un contact s'ouvre en lecture seule.

## Les paliers

Chaque capacité a un palier, choix de l'administrateur : « raconter » (Cassandra ou Itare prépare, un humain approuve) ou « auto ». Aucun geste n'est interdit par le code. `valider_facture` reste réservée aux humains et à Cassandra : elle consomme un numéro légal.

## Des fiches et des listes identiques à celles de Dolibarr 24

Compatibilité d'abord : ce qu'on saisit ici doit se retrouver dans Dolibarr sans perte, et ce qu'on lit doit se lire comme là-bas.
- **Fiches** (tiers, contact, facture, devis, produit, projet, don, cotisation, règlement client et fournisseur, virement entre comptes) : les champs de la fiche Dolibarr, sous leurs noms de propriété, dans son ordre et sous ses libellés ; les listes (pays, départements, formes juridiques, types de tiers, effectifs, devises, conditions et modes de règlement, comptes bancaires, taux de TVA, produits) sont lues dans l'instance. Une facture ou un devis porte plusieurs lignes (produit, désignation, TVA, quantité, prix, remise).
- **Règles** : celles de la fiche (nom ou libellé obligatoire, valeurs permises, courriel, adresse web, SIREN 9 et SIRET 14 chiffres pour un tiers français), dites dans le formulaire AVANT l'envoi et revérifiées par le module (point d'évolution `regles_dolibarr`). Le formulaire reste ouvert et affiche le message de Dolibarr quand il refuse.
- **Listes** : tiers, factures, devis, produits, adhérents, dons, projets et factures fournisseurs prennent les colonnes des listes de Dolibarr ; ce que Cassandra ajoute (factures et dû d'un tiers, actions) vient après.

## La lecture de la base de Dolibarr (superadministrateurs)

L'API de Dolibarr cache ou ne sait pas compter certaines choses : l'adresse d'un don (`unset($object->address)` dans son API), les totaux, la définition des champs personnalisés, l'état du journal inaltérable. Le module peut donc LIRE la base de Dolibarr, en plus de son API.
- **Réservé aux superadministrateurs** (`ctx.est_superadmin`) : un administrateur passe tous les contrôles de droits, donc ce n'est pas un droit. Un compte ordinaire, un moteur ou un agent sans compte de superadministrateur est refusé AVANT toute connexion. Les écritures restent dans l'API (ses règles, ses droits par utilisateur).
- **Lecture seule à deux niveaux** : un utilisateur SQL qui n'a que `SELECT` (la capacité `base_etat` dit s'il a plus, et lesquels), et une session ouverte en lecture seule. Rien d'autre que des **requêtes nommées** (`don_adresses`, `champs_perso`, `journal_etat`, `ca_par_mois`) : du SQL fixe, avec des paramètres contrôlés (nombres, dates, identifiants) ; aucun SQL libre.
- **Facultatif et générique** : réglages `base_hote`, `base_port`, `base_nom`, `base_utilisateur`, `base_motdepasse` (secret), `base_prefixe` (`llx_`), `base_client` (`mysql`). Vides : la lecture est coupée et le module marche comme avant. Le programme client `mysql` est appelé en ligne de commande (le mot de passe passe par l'environnement du processus, jamais par la ligne de commande).
- **Ce qui n'est jamais lu** : la table des réglages de Dolibarr (`llx_const`), où dorment la clé de signature du journal et le mot de passe d'envoi de courriels.
- **Ce que l'écran en tire** : l'adresse et le courriel dans la liste des dons ; sur la page Instance, l'accès et la version du serveur, le journal inaltérable, le chiffre d'affaires par mois, les champs personnalisés. Un compte qui n'a pas ce droit ne voit simplement pas ces cartes.
- **Créer l'utilisateur SQL** (une fois, sur le serveur de Dolibarr) : `CREATE USER 'cassandra_ro'@'localhost' IDENTIFIED BY '…'; GRANT SELECT ON dolibarr.* TO 'cassandra_ro'@'localhost';`

## Le pont de la billetterie (un seul client)

La billetterie n'a plus ni adresse ni clé de Dolibarr : sa file d'écritures (un moteur, donc sans compte) appelle les capacités `bil_tiers`, `bil_facture`, `bil_avoir`, `bil_versement`, `bil_adherent` (et `bil_tester`, en lecture) par `ctx.agir`, acteur « cassandra ». Un moteur agit sous le compte système `noyau` : c'est la clé de **mandat** qui écrit, dans la société de son tour, avec la garde de société, le palier et le journal de ce module. Chaque écriture est idempotente (recherche par `ref_ext` avant de créer). Le palier est le mandat de l'administrateur : « raconter » (défaut) fait attendre la file en le disant, « auto » la laisse écrire. Une panne de Dolibarr est rendue comme un report (`differe`), jamais comme un échec de la capacité : deux échecs de suite la rétrograderaient. Ces capacités ne sont proposées qu'à « cassandra » (ni à Itare, ni aux humains, sauf `bil_tester`).

## Ce qui a été vérifié contre un vrai Dolibarr 24.0.2

**L'épreuve des fiches (copie isolée de l'instance, `blockedlog` actif)** : chaque fiche (tiers, contact, produit, projet, facture, devis, don, cotisation, règlements, virement) est écrite avec la charge exacte de l'écran, puis RELUE dans Dolibarr champ par champ ; la facture va jusqu'à la validation (numéro légal, journal inaltérable), deux règlements, un avoir, puis chaque geste est défait. Ce qu'elle a appris :
- un **chèque exige son émetteur** (« Emetteur is mandatory when payment code is CHQ ») : le règlement demande l'émetteur et la banque du chèque quand le mode est « chèque » ;
- Skype, X, Facebook et LinkedIn vont dans **`socialnetworks`** (un objet), pas en propriétés plates : sans cela ils étaient perdus en silence ;
- Dolibarr garde les dates en secondes et **tronque les zéros de fin des codes comptables** (706000 devient 706) : la preuve relit comme Dolibarr garde, sinon une création réussie était annulée par erreur ;
- le champ « Devise » n'existe dans la fiche d'un tiers que si le module multidevise est actif : il n'est plus proposé ;
- l'adresse d'un don est bien gardée, mais l'API ne la rend pas à la relecture.

Sur une copie isolée de la base (31-10) : valider une facture, l'encaisser en deux fois (le règlement qui la solde se défait en la rouvrant d'abord, par `settounpaid`), son PDF, un avoir, un devis (valider, signer, facturer), un don validé, un virement entre comptes, le paiement d'une facture reçue. Ce que cette copie a appris, et que le code applique : `paymentsdistributed` refuse « amount » et « multicurrency_amount » ensemble ; un paiement fournisseur veut `payment_mode_id` ; le reçu fiscal d'un don n'a pas d'API ; la validation d'une facture échoue si le module `blockedlog` ne peut plus déchiffrer sa clé (`BLOCKEDLOG_HMAC_KEY`, après un changement de `dolibarr_main_instance_unique_id`).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : la description du module -->
<!-- EC : néant (aucun point d'évolution) -->
<!-- LIEN : modules/dolibarr, interface/CN_dolibarr-ecran.js, tests/CN_test_dolibarr_gestion.py -->
