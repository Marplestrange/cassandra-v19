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
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=a055b9 ▼▼▼ -->
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
| Saisir, valider un don ; éditer son reçu fiscal | `don_creer`, `don_valider`, `don_recu` | supprimer la promesse ; un don validé ne se défait pas par l'API ; supprimer le PDF |
| Enregistrer une cotisation | `cotisation` | supprimer cette cotisation |
| Virer d'un compte bancaire à un autre | `virement_interne` | le virement inverse |
| Ouvrir, clore un projet | `projet` | remettre le statut d'avant |
| Lire ou écrire n'importe où dans l'API | `lire_libre`, `ecrire_libre` | restaurer les champs d'avant (PUT), supprimer ce qui vient d'être créé (POST) |

Avant elles : `creer`, `modifier`, `creer_brouillon`, `supprimer` (avec corbeille), `restaurer`, `valider_facture`. L'écran est `interface/CN_dolibarr-ecran.js`.

## Le PDF d'une pièce

`piece_pdf` lit le PDF que Dolibarr a produit pour un devis, une facture ou un reçu de don (base64, 8 Mo au plus) ; l'écran l'affiche dans un cadre sur adresse locale (`blob:`), sans `sandbox`, comme le visionneur de la GED. Si la pièce n'en a pas, `produire_pdf` le fait produire (retour : supprimer ce PDF).

## Envoyer un projet ou un contact à Dolibarr

Par défaut une fiche de Cassandra reste « Cassandra seulement ». `envoyer_projet` et `envoyer_contact` la créent chez Dolibarr et posent un lien (objet `dolibarr_lien`, propre au compte). Une fois liée : **Dolibarr fait foi** pour ce qu'il porte (`modifier_lie` envoie la modification chez lui) ; les notes, l'équipe, les jalons et les tâches restent dans Cassandra. Un contact est toujours rattaché à un tiers choisi (`tiers`) ou créé pour l'occasion (`nouveau_tiers`) : il ne devient jamais un tiers. `detacher` rompt le lien et garde les deux copies. `liens` liste ce qu'on a envoyé. Les lectures de Cassandra passent par `[permissions] lectures` (`projets.voir`, `contacts.voir`).

## Une clé d'API par compte

- **Ma clé** : le réglage `dolibarr.cle_api` (secret, portée compte). Dolibarr agit sous le nom de l'utilisateur de cette clé, avec ses droits : l'Itare d'un compte fait ce que Dolibarr permet à cet utilisateur, rien de plus.
- **Un compte sans clé propre lit** (avec la clé de mandat) **mais n'écrit pas**. Il ne tombe jamais sur la clé d'un autre. Le réglage `dolibarr.mandat_pour_tous` (désactivé par défaut) en fait le choix de l'administrateur.
- **La clé de mandat** : `dolibarr.cle_mandat`, ou le fichier `config/dolibarr.key`. Elle sert les moteurs (billetterie, relevé) qui n'ont pas de compte. Un utilisateur Dolibarr aux droits limités vaut mieux qu'un administrateur.
- **La société attendue** : `dolibarr.societe_attendue`. Rempli, le pont vérifie avant chaque écriture que la clé voit cette société, sinon il refuse (une instance à plusieurs entités peut donner une clé qui écrit dans la mauvaise comptabilité).

## Les paliers

Chaque capacité a un palier, choix de l'administrateur : « raconter » (Cassandra ou Itare prépare, un humain approuve) ou « auto ». Aucun geste n'est interdit par le code. `valider_facture` reste réservée aux humains et à Cassandra : elle consomme un numéro légal.

## Ce qui n'est pas vérifié contre un vrai Dolibarr

Les chemins viennent du `swagger.json` de l'instance ; les bancs tournent contre un Dolibarr de poche (`tests/CN_test_dolibarr_gestion.py`). Pas encore essayés sur une vraie instance : le paiement partiel par `paymentsdistributed`, le reçu fiscal par `documents/builddoc`, le virement `bankaccounts/transfer`, la clôture d'un projet par PUT.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : la description du module -->
<!-- EC : néant (aucun point d'évolution) -->
<!-- LIEN : modules/dolibarr, interface/CN_dolibarr-ecran.js, tests/CN_test_dolibarr_gestion.py -->
