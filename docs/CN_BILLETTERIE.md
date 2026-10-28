<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Billetterie : vente par revendeurs, portefeuille de commissions -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Billetterie : vente par revendeurs, portefeuille de commissions -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=c2dd46 ▼▼▼ -->
<!-- TITRE : Module billetterie et réglage Titulaire de l'instance -->
<!-- LICENCE : AGPL-3.0 · AUTEUR : Atek Drisse · MODULE : docs -->

# Billetterie : vente par revendeurs, portefeuille de commissions

Statut : **conception à valider** (17-10-2026). Aucun code écrit. Maquette de l'écran revendeur : à faire après validation de cette note.

## 1. Le besoin

Le titulaire de l'instance organise des événements et vend des billets en ligne. Il confie la vente à des **revendeurs** : chacun a son lien, son code et son QR, vend à un prix fixé, et touche une **commission par billet**.

Exemple de référence : billet à 15 €, commission de 5 € ; un revendeur qui vend ses 20 billets a un portefeuille de 100 €, le titulaire encaisse 200 €. Chaque billet reste attribué au revendeur qui l'a vendu. Le revendeur suit en temps réel ses ventes et ses commissions, **par événement**.

## 2. Décisions prises

| Décision | Choix | Qui |
|---|---|---|
| Titulaire | **un seul par instance**. Un futur module « Multicompany » (app Store) pourra en ouvrir plusieurs ; le modèle ne l'interdit pas (voir §4) | Drisse |
| Revendeur | pas un organisateur : une personne ou une structure qui vend pour le titulaire | Drisse |
| Argent | **option A** : tout le paiement arrive chez le titulaire ; le portefeuille est un **registre de commissions dues**, Cassandra ne détient et ne transfère aucun fonds | proposé, à confirmer |
| Revendeur côté Cassandra | **compte dédié à rôle réduit** : billetterie (ses ventes, ses billets) et paiement (son portefeuille, ses retraits), rien d'autre dans Cassandra | Drisse |
| Disponibilité | commission **retirable 7 jours après l'événement** ; **seuil minimal de retrait : 20 €** (réglables par le titulaire, ces valeurs sont les défauts) | Drisse |
| Portefeuille | le revendeur **dispose** de son solde : il demande un retrait, le titulaire l'exécute (voir §5) | Drisse |

## 2 bis. Types de compte : du binaire aux rôles cumulables

**Constat (lu dans la V19).** Le module `droits` ne connaît aujourd'hui que **administrateur ou non**, plus des **groupes** et des accords ou refus par compte (modèle Dolibarr); le module `comptes` identifie par adresse électronique, mot de passe salé, sessions et invitations. Aucun rôle métier n'existe.

**Décision (Drisse).** On passe à des **rôles cumulables**: un compte peut être **artiste et/ou revendeur**, puis **client**. Il n'y a **qu'une identité par adresse électronique** (même mot de passe, même sessions, même clé de sécurité), et ce sont ses rôles qui disent où elle entre et ce qu'elle voit.

| Rôle | Accès | Création | Voit |
|---|---|---|---|
| Administrateur (le titulaire) | toute l'application | existant | tout, y compris les ventes de tous |
| Utilisateur | l'application, selon ses droits | invitation (existant) | selon ses droits |
| **Revendeur** | écran réduit: billetterie et paiement | **invitation** du titulaire | ses ventes, ses formules, son portefeuille |
| **Artiste** | écran réduit: son passage, ses billets d'invité, son cachet; **s'il a une formule d'artiste, il est aussi revendeur** | **invitation** (lien avec la fiche artiste) | sa fiche, ses événements, sa rémunération |
| **Client** | **la boutique seulement**, jamais l'application | **à l'achat** (courriel vérifié), ou à la demande | ses billets, ses factures, ses données |
| **Caisse** (caissier) | l'écran de caisse seulement (§4 octies) | **invitation** du titulaire | les ventes de la session ouverte, ses clôtures |
| **Contrôle** (ouvreur) | la page de contrôle des billets seulement (§4 nonies) | **invitation** du titulaire | les billets de l'événement et de la porte qui lui sont confiés |

**Réalisation, sans nouveau concept dans le noyau.**
- Un rôle est un **groupe** du module `droits`; les **droits** que la billetterie déclare (voir ses ventes, vendre, demander un retrait, gérer les formules, émettre une invitation, etc.) s'attribuent aux groupes, et un compte peut appartenir à **plusieurs groupes**. Les règles existantes de précédence restent (administrateur, puis accord ou refus du compte, puis refus de groupe, puis accord de groupe).
- Le **client** est un compte dont le seul groupe donne l'accès à la **boutique**. Il n'a **aucun droit** dans l'application et la page d'entrée de l'application le refuse: la porte de la boutique est un **domaine** et un processus à part (voir §5 quater).
- À la connexion, un compte qui a **plusieurs rôles** choisit où entrer (par exemple un revendeur qui est aussi client de la boutique).
- Les fiches métier (artiste, revendeur, client) **se lient au compte** par l'adresse électronique vérifiée, sans jamais en dépendre: une fiche existe sans compte (un artiste jamais invité), un compte peut être supprimé sans effacer l'historique des ventes.
- **Cloisonnement**: un revendeur ou un artiste ne lit que ses propres données; l'administrateur voit celles du titulaire, qui sont aussi les données de l'instance.
- Les identifiants du §4 quinquies (`REV-…`, `ART-…`, `CLI-…`) sont ceux des **fiches**; le compte garde le sien. Les trois restent distincts et ne se réutilisent jamais.

**Effets sur le noyau** (à ne toucher que par `comptes` et `droits`): groupes déclarés par le module billetterie à l'installation; invitation par rôle (le lien porte le rôle et la fiche à lier); inscription à l'achat pour le client; refus d'entrée dans l'application pour un compte sans droit d'application. Rien de tout cela ne casse les comptes existants: ils gardent leur état actuel.

## 3. Réglage de base : Titulaire de l'instance (noyau, module `reglages`)

Le titulaire est une donnée du **socle**, pas de la billetterie : facturation (`dolibarr`), mails, pages légales et RGPD s'en serviront aussi.

| Groupe | Champs |
|---|---|
| Identité légale | forme (particulier / association / société), raison sociale, SIRET ou RNA, adresse, TVA (numéro ou mention « non applicable ») |
| Contact public | courriel, téléphone, site |
| Versements | IBAN du titulaire, IBAN de versement des commissions si distinct |
| Paiement | prestataire choisi ; **clés dans le coffre**, jamais dans la configuration |
| Documents légaux | CGV, mentions légales, confidentialité, remboursement : affichés sur la page de vente, résumés sur le billet |
| Expéditeur | nom et adresse d'envoi des billets et reçus |

**Qui fait foi (Drisse) : Dolibarr.** Quand le module `dolibarr` est relié, l'**identité légale** (raison sociale, SIRET/RNA, adresse, TVA, forme) est **lue** depuis la société Dolibarr, en lecture seule dans Cassandra, avec un bouton « actualiser ». Le reste (contact public, versements, paiement, documents légaux, expéditeur) reste réglé dans Cassandra. **Sans Dolibarr**, les champs d'identité deviennent saisissables localement, et sont **proposés à l'import** le jour où Dolibarr est relié (jamais écrasés sans accord).

Règles : le titulaire est **vendeur au sens de la loi** et **responsable de traitement** RGPD des données des acheteurs ; Cassandra n'est jamais partie à la vente. Tant que le titulaire n'est pas renseigné, **le module ne peut pas ouvrir une vente**.

Le modèle stocke un `titulaire_id` partout où il compte (événement, billet, écriture) : aujourd'hui toujours le même, demain la porte du Multicompany sans migration.

## 4. Modèle de données

- **evenement** : titulaire_id, nom, lieu, date, ouverture/fermeture des ventes, état (brouillon, ouvert, clos).
- **type_billet** : événement, nom, prix en centimes, quota, fenêtre de vente.
- **revendeur** : compte (rôle réduit), code public, état (invité, actif, suspendu).
- **regle_commission** : revendeur × événement (ou type de billet) → montant fixe ou pourcentage. Défaut au niveau de l'événement, surcharge possible par revendeur.
- **commande** : acheteur (nom, courriel), revendeur_id (peut être vide : vente directe du titulaire), état (en attente, payée, remboursée, expirée), prestataire + identifiant de paiement (unique).
- **billet** : commande, type, **revendeur_id gravé à la création**, jeton signé (QR), état (valide, utilisé, annulé), scanné le / par qui.
- **ecriture** (le portefeuille) : registre **en écriture seule**. Types : `commission` (+), `annulation_commission` (−, remboursement), `versement` (− , commission payée au revendeur), `correction` (avec motif). Le solde est une **somme**, jamais un champ modifié.
- **reservation** : stock retenu 10 minutes pendant le paiement.
- **demande_retrait** : revendeur, montant, état (demandée, validée, payée, refusée), date, référence du versement.
- **coordonnees_versement** : par revendeur, IBAN et titulaire du compte ; stockées dans le coffre, jamais en clair dans la base.

Montants toujours en **entiers (centimes)**. Aucun flottant.

## 5. Parcours

**Vente** : l'acheteur ouvre le lien du revendeur → choisit ses billets → réservation du stock → paiement chez le prestataire → webhook signé → commande payée → billets créés (revendeur_id gravé) → écriture `commission` par billet → mail avec billets → notification temps réel au revendeur.

**Contrôle à l'entrée** : scan du QR, vérification de la signature, bascule atomique `valide → utilisé`. Second scan : refus avec l'heure du premier. Mode hors ligne : liste de jetons valides téléchargée avant l'événement (lot ultérieur).

**Remboursement** : billet annulé, écriture `annulation_commission`, le solde du revendeur baisse. Si le versement a déjà eu lieu, le solde peut devenir négatif et reste dû.

**Retrait (le revendeur dispose de son portefeuille)** : le revendeur voit son solde disponible et fait une `demande_retrait` (montant ≤ solde disponible, ses coordonnées de versement enregistrées dans le coffre). Le titulaire la voit, la valide, paie (virement, ou virement du prestataire), puis enregistre le `versement`, ce qui solde la demande. Le solde se découpe en **en attente** (événement pas encore passé ou passé depuis moins de 7 jours, donc encore remboursable) et **disponible** (événement passé + 7 jours, retrait possible dès que le disponible atteint 20 €). Cassandra tient le compte et produit le relevé ; elle ne déplace pas elle-même l'argent. Un retrait automatique (option B, partage Stripe Connect) reste un lot ultérieur.

**Vente en espèces** (le cas fréquent) : le revendeur déclare « vendu en main propre » ; le billet est créé « à encaisser ». Le revendeur **doit alors le prix net au titulaire** : écriture `a_reverser` (le portefeuille se compense : commission acquise moins prix encaissé). Le titulaire valide la remise d'argent, sinon le billet reste en attente et n'est pas scannable.

## 4 bis. Formules de rémunération et rentabilité (tirées de la maquette de rentabilité)

Source : l'artifact « Bilan formules billetterie » (salle de 120 places, place à 15 €, salle à 100 €, 5 artistes, 24 places par vendeur). Il montre que la **règle de commission du §4 ne suffit pas** : une rémunération peut combiner un **forfait fixe** et une **commission**, avec un **palier**. La `regle_commission` devient une **formule**, réutilisable et affectée à un revendeur par événement.

**Paramètres d'une formule**

| Paramètre | Exemple (A / B / C) |
|---|---|
| Pour qui | **fixé à la création, non modifiable** : les formules **A et B sont des formules d'artiste** (l'artiste vend lui-même), **seule la formule C est une formule de revendeur indépendant** ; un revendeur indépendant ne peut recevoir qu'une formule de ce type, un artiste qu'une formule d'artiste |
| Forfait de l'artiste | 80 € / 110 € / sans objet |
| Cachet fixe de l'artiste non vendeur | sans objet / sans objet / 100 € |
| Commission par place | 5 € / 3 € / 3 € |
| Palier (optionnel) | C : 3 € jusqu'à 12 places, puis 5 € |

**Paramètres d'un événement** : coût de la salle (100 €), prix de la place (15 €), nombre d'artistes (5), capacité (120), vente directe sans commission (oui).

**Décision avant l'événement** : date de décision (J-7), **seuil de rentabilité** calculé par formule (50 / 55 / 50 places), acompte de salle perdu au plus (100 €). Sous le seuil à la date de décision : annulation ou report, billets remboursés. Au-dessus : on maintient.

**Calculs** : bénéfice de la prod = places × prix − salle − rémunérations ; artiste vendeur = forfait + commission × places vendues ; revendeur indépendant avec palier = commission × min(n, palier) + commission haute × max(0, n − palier). Vérifié sur les chiffres de la maquette de rentabilité (60 places : 100 / 70 / 120 € ; salle pleine : 700 / 790 / 720 € avec palier ; seuils 50 / 55 / 50).

**Conséquences sur le modèle** : `formule` (forfait, cachet, commission, palier) remplace `regle_commission` ; `evenement` gagne coût de salle, nombre d'artistes, date de décision, acompte ; l'écran « Formules et rentabilité » est dans la maquette, onglet Titulaire. **Point de vigilance repris de l'artifact** : le revendeur indépendant est le maillon fragile de la formule C ; et un artiste laissé libre de choisir prend toujours la formule la plus chère pour la prod, donc la formule est **imposée à l'avance** par le titulaire.

## 4 ter. Événements, artistes, revendeurs, salles (bases du module)

Décision (Drisse) : quatre bases, chacune réutilisée d'un événement à l'autre. Maquette : onglets Titulaire › Événements, Artistes, Salles, Revendeurs.

**Salle** (`salle`) : nom, adresse, contact ; **prix de location**, acompte, caution, conditions d'annulation ; **capacité assise** et **capacité debout** (0 si la configuration n'existe pas) ; accessibilité PMR ; classement ERP et avis de la commission de sécurité ; heure limite de fin ; limite de bruit ; règles sur l'alcool et la buvette ; âge et public ; équipement ; assurance exigée ; documents (contrat de location, plan et jauge).

**Événement** (`evenement`) : nom, date, ouverture des portes, début, fin, description, public (tous publics, 18 ans et plus), état (brouillon, en vente, terminé, annulé) ; **une salle** et une **configuration** (assis ou debout), d'où la **capacité retenue** ; places mises en vente, prix ; **liste d'artistes** (artiste, ordre de passage, durée) ; **revendeurs indépendants assignés** (quota de places confiées à chacun) ; date de décision et seuil (§4 bis).
Règle : **les places en vente ne dépassent jamais la capacité retenue** (alerte rouge sinon). Changer de salle bascule la configuration si l'ancienne n'existe pas dans la nouvelle.

**Artiste** (`artiste`, base SQL) : nom de scène, nom légal ou structure, genre, statut juridique (association, auto-entrepreneur, société, particulier), contact, présentation, **fiche technique (rider)**, **formule par défaut** (A, B ou C). IBAN dans le coffre. Tiers fournisseur Dolibarr créé à la première facture de cachet. Un artiste de formule A ou B **est aussi un revendeur** : son compte revendeur lui est lié automatiquement ; un artiste de formule C ne vend pas.

**Revendeur** (`revendeur`, base SQL) : deux types, **artiste** (lié à une fiche artiste, formules A et B) et **indépendant** (invité, formule C). Nom, code, compte à rôle réduit (§2), coordonnées de versement (coffre), formule par événement, historique des ventes et du portefeuille.

**Liens** : `evenement` → 1 `salle` ; `evenement` ↔ n `artiste` (ordre, durée) ; `evenement` ↔ n `revendeur indépendant` (quota) ; `artiste` → 0..1 `revendeur` (si vendeur) ; `revendeur` / `artiste` → `formule` (§4 bis).

**Autres éléments à prévoir (à décider)**
- **Contrats et cachets** : contrat de cession ou convention par artiste et par événement, facture de cachet (Dolibarr), échéance de paiement.
- **Droits d'auteur** : déclaration des œuvres jouées (SACEM en France) par événement.
- **Sécurité et réglementation** : effectif du service de sécurité, déclaration de buvette et licence temporaire, secours, avis de la commission de sécurité selon la jauge.
- ~~Invitations et accréditations~~ : **retenues**, voir §4 quater.
- **Équipe et bénévoles** : planning, rôles à l'entrée.
- **Recettes annexes** : buvette, restauration (recettes et coûts dans le bilan de l'événement).
- **Promotions** : codes promotionnels, tarifs réduits, liste d'attente quand l'événement est complet.
- ~~Annulation et report~~ : **retenus**, procédure unique, voir §4 quater.
- **Bilan d'événement** : après coup, recettes, coûts, commissions, cachets, bénéfice réel comparé à la prévision.
- **Matériel et logistique** : sono, lumière, transport, hébergement des artistes.

## 4 quater. Invitations, base clients, autonomie de Dolibarr, annulation

**Invitations gratuites avec quota** (décision Drisse). Table `invitation` : événement, catégorie (artistes, presse, bénévoles, partenaires, autre), quota par catégorie, nombre émises, bénéficiaire, émetteur, état. Un billet d'invitation est un vrai billet (QR, nom) **sans recette, sans commission, sans facture**, marqué « invité » au contrôle d'entrée. Il **occupe une place de la salle** : la règle de jauge devient **places en vente + invitations réservées ≤ capacité retenue** (alerte rouge sinon). Les places en vente restent la base du calcul de rentabilité (§4 bis). Un quota ne peut pas descendre sous le nombre déjà émis. Chaque émission est tracée au journal.

**Bases SQL.** Cinq tables propres à Cassandra, qui vivent **dans la base de la billetterie, jamais dans Dolibarr** : `salle`, `artiste`, `revendeur`, `client`, `evenement`. Dolibarr n'en est qu'un **miroir facultatif** : chaque fiche porte un champ `dolibarr_id` (vide sans pont). La **base clients** est alimentée à chaque achat et retrouvée par courriel vérifié ; le compte client (§5 quater) est facultatif ; export et anonymisation à la demande.

**Fonctionnement indépendant de Dolibarr** (décision Drisse). La billetterie doit marcher **seule**, et se brancher sur Dolibarr si elle existe :

| Domaine | Sans pont (mode autonome) | Avec pont |
|---|---|---|
| Identité du titulaire | saisie dans le réglage Titulaire | lue depuis la société Dolibarr, en lecture seule |
| Clients | base clients locale | un tiers Dolibarr par client |
| Artistes, revendeurs | suivi par portefeuille, relevé exportable | tiers fournisseurs |
| Ventes | **reçu PDF simple** (pas une facture légale), export CSV | facture validée, PDF Dolibarr, avoir au remboursement |
| Paiements | état de la commande | règlement sur le compte bancaire Dolibarr |
| Commissions | relevé par revendeur | facture fournisseur par revendeur |
| Dons | **aucun reçu fiscal proposé** | don et Cerfa dans Dolibarr (§5 quater) |

**Réglages du pont** (écran Titulaire › Réglages, section « Pont Dolibarr ») : un interrupteur **relié / autonome** ; adresse de l'API, **clé dans le coffre** ; **un interrupteur par domaine** (identité, clients, fournisseurs, factures, paiements, commissions) pour relier à la carte ; « Tester la connexion » ; « Rapprocher les fiches existantes ». Débrancher le pont ne supprime rien : les écritures attendent dans la file de rattrapage ou repassent en mode autonome. Brancher le pont **rapproche** les fiches par courriel et SIRET **avant** d'en créer (aucun doublon). Les écrans changent de vocabulaire selon le mode (« Facture PDF » ou « Reçu PDF », pas de don sans pont).

**Procédure d'annulation et de report unique** (décision Drisse). Une seule procédure pour tous les événements, déclenchée depuis la fiche de l'événement ou depuis le seuil de décision (§4 bis). Choix : **annuler** ou **reporter** (nouvelle date), avec un motif envoyé aux acheteurs. Étapes, annoncées avec leurs chiffres avant confirmation :
1. fermer la vente ;
2. prévenir les acheteurs par courriel ;
3. **annulation** : rembourser les billets (par chaque prestataire, virements à la main) ; **report** : les billets restent valables, remboursement sur demande ;
4. **annulation** : écritures inverses des commissions ; **report** : conservées ;
5. invitations annulées (annulation) ou conservées (report) ;
6. prévenir artistes et revendeurs ;
7. comptabilité : avoirs Dolibarr si le pont est relié, sinon écritures inverses exportables ;
8. salle : rappeler ses conditions d'annulation et l'**acompte à risque** ; en cas de report, vérifier sa disponibilité à la nouvelle date.
Le bouton n'est actif qu'après confirmation (et une date pour un report). L'état devient « annulé » ou la date change, et chaque étape est tracée au journal.

## 4 quinquies. Formules gérables, affectations multiples, identifiants uniques, interopérabilité Dolibarr

**Formules: ajouter, modifier, dupliquer, supprimer** (décision Drisse). Une formule est une fiche à part entière: nom, description, type (artiste ou revendeur indépendant, définitif), forfait ou cachet, commission, palier. Tout ce qui s'y réfère la désigne **par son identifiant** (jamais par son nom), donc renommer ou modifier une formule se répercute **partout**: fiches artistes, passages dans les événements, affectations des revendeurs, écran du revendeur, tableaux de rentabilité (une colonne par formule).
- **Événements déjà vendus ou terminés**: ils gardent les conditions d'origine. Au premier changement d'une formule, une **copie figée** est prise pour chaque événement concerné (pastille « figée »). Les événements sans vente suivent la formule en direct.
- **Suppression définitive**: une fenêtre montre l'impact (artistes, passages, affectations, événements dont figés), propose de **remplacer partout** par une autre formule du même type ou de **retirer** les affectations, et demande une confirmation. L'identifiant `FOR-…` est inscrit au registre des identifiants retirés.

**Plusieurs formules par revendeur, retirables par événement.** Table `affectation` (événement, revendeur, formule, quota, périmètre) où un revendeur peut avoir **plusieurs lignes**, ou aucune. Périmètre: tous les billets ou un type de billet. **Ordre d'application**: de haut en bas, la première affectation qui a encore du quota. Un artiste a aussi **sa formule par événement** (par défaut celle de sa fiche). **Retirer toutes les affectations** d'un revendeur ferme sa vente pour cet événement (lien désactivé côté revendeur, la boutique passe en « vente directe »), **sans effacer ses ventes passées**. Le revendeur voit ses formules et leurs conditions dans son écran.

**Identifiants uniques, jamais réutilisés.** Chaque fiche reçoit à la création un identifiant immuable issu d'un **compteur qui ne recule jamais**: `REV-000001` (revendeurs), `ART-…` (artistes), `CLI-…` (clients), `SAL-…` (salles), `EVT-…` (événements), `FOR-…` (formules), et de même pour commandes, billets, factures. S'y ajoute le **code de vente** du revendeur (dans son lien), unique lui aussi. **On archive, on ne supprime jamais une fiche** (le code et l'identifiant restent réservés); seule une formule se supprime vraiment, et son identifiant va au **registre des identifiants retirés**. Garanties en base: index unique, compteur persistant, table des identifiants retirés.

**Association à Dolibarr.** Quand le pont est relié, **l'identifiant Cassandra est écrit dans le champ `ref_ext`** de la fiche Dolibarr; le **code que Dolibarr génère** (code client ou fournisseur, numéro d'adhérent) est **relu et rangé à côté**. Les deux s'affichent partout. On associe, on n'identifie pas: les codes Dolibarr sont produits par sa numérotation, que Cassandra ne pilote pas. À la mise en relation, les fiches existantes sont **rapprochées** (courriel, SIRET) avant toute création.

| Cassandra | Objet Dolibarr | Champ qui porte l'identifiant |
|---|---|---|
| client (`CLI-…`) | tiers client | `ref_ext`; `code_client` relu |
| revendeur (`REV-…`) | tiers fournisseur | `ref_ext`; `code_fournisseur` relu |
| artiste (`ART-…`) | **adhérent** (module Adhérents) | `ref_ext`; numéro d'adhérent relu; `fk_soc` vers le tiers fournisseur |

**Compte client compatible tiers Dolibarr.** Champs vérifiés sur l'instance (lecture seule). Dolibarr n'exige que le **nom**; le reste rend la facture complète.

| Champ Cassandra | Champ Dolibarr | Obligatoire |
|---|---|---|
| nom (particulier: prénom + nom; pro: raison sociale) | `name` | **oui** |
| type (particulier, entreprise, association) | `typent_code` (TE_PRIVATE ou TE_SMALL) | non |
| courriel | `email` | recommandé |
| téléphone | `phone` | non |
| adresse, code postal, ville | `address`, `zip`, `town` | recommandé pour une facture |
| pays | `country_code` | recommandé |
| SIRET, n° de TVA | `idprof1`, `tva_intra` | pour un professionnel |
| langue | `default_lang` | non |
| accepte les courriels | `no_email` | non |
| identifiant | `ref_ext` | oui (côté Cassandra) |
| (drapeau client, code) | `client` = 1, `code_client` = `auto` | généré par Dolibarr |
À l'achat, la boutique demande **nom et courriel** (obligatoires), puis adresse, pays et, pour une entreprise ou une association, raison sociale, SIRET, TVA. L'écran Titulaire › Clients montre pour chaque fiche si elle est **complète pour Dolibarr** et ce que le pont enverrait (`Voir ce qui part vers Dolibarr`).

**Compte artiste compatible adhérent Dolibarr** (décision Drisse). Champs d'un adhérent confirmés sur l'instance: `login`, `morphy` (`phy` personne, `mor` association ou société), `typeid`, `firstname`, `lastname`, `societe`, `email`, `phone`, `address`, `zip`, `town`, `country_code`, `datefin` (fin d'adhésion), `statut`, `public`, `fk_soc`, `ref_ext`. La fiche artiste porte ces champs: prénom, nom, adresse, code postal, ville, pays, adhésion valable jusqu'au; le statut juridique donne le `morphy` (association ou société = `mor`, sinon `phy`); le `login` est dérivé de l'identifiant. **Point d'attention**: les types de membre de l'instance sont aujourd'hui « Utilisateur » et « Administrateur », **le type « Artiste » n'existe pas**: il est créé à la première association (route des types de membre disponible). `fk_soc` relie l'adhérent au **tiers fournisseur** qui reçoit les cachets; un artiste qui vend a en plus son compte revendeur (`REV-…`) associé au même tiers. Le pont a un interrupteur propre « Artistes → adhérents ».

## 4 sexies. Compte artiste, provisions, remboursement unique, fiche événement et projet Dolibarr, verrou des formules

**Compte artiste** (décision Drisse). Un artiste a **toujours une fiche** (dates de passage, ordre, durée, fixe, invitations, portefeuille). Une case **« vend lui-même des billets »** (fiche artiste, côté Titulaire, et à la création) décide du reste:
- **cochée**: sa fiche s'**additionne à un compte revendeur** (identifiant `REV-…` et code de vente créés, formule de **type artiste** imposée); il voit en plus l'onglet « Mes ventes » (lien, code, commissions);
- **décochée**: **fiche artiste seule**, avec **cachet fixe** (formule de type revendeur indépendant, qui porte le cachet).
Le compte artiste se compose de: Mes passages, Mon portefeuille, (Mes ventes si vendeur), Ma fiche. Décocher ne supprime rien: l'identifiant et le code du revendeur restent réservés (§4 quinquies).

**Provisions** (décision Drisse). La prod **provisionne**, compte par compte et par événement: les **fixes des artistes** (forfait ou cachet, avant l'événement) et les **commissions des revendeurs** (au fil des ventes encaissées). Chaque provision est une écriture du registre (type `provision`). **Disponible au retrait = le plus petit du montant acquis et échu et du montant provisionné**, moins ce qui a déjà été versé. L'écran Titulaire › Provisions liste, par événement, ce qui est dû, provisionné, restant, avec « Provisionner » (montant, mode) et « Tout provisionner ». Le revendeur et l'artiste voient leur part provisionnée dans leur portefeuille.

**Remboursement unique** (décision Drisse; l'annulation d'événement, §4 quater, en est le cas en série). Une seule procédure, appelée par: la **demande du client** (« Demander un remboursement » dans son compte), la **décision du titulaire** (Titulaire › Commandes › Rembourser) ou l'**annulation d'un événement** (commande par commande). Effets, **automatiques**:
1. **la commission du vendeur est retirée** (écriture `annulation_commission`; pour un revendeur à palier, la commission est recalculée sur ses formules); si elle était déjà versée ou échue, le solde baisse et peut devenir négatif (à régulariser);
2. le billet est invalidé (QR refusé);
3. le paiement est rendu par le prestataire (carte, PayPal, HelloAsso), ou par virement manuel pour un virement;
4. avoir dans Dolibarr si le pont est relié (sinon écriture inverse exportable); le reçu de don est annulé si le don est remboursé;
5. courriel au client; ligne négative dans les « ventes en direct » du vendeur.
On peut rembourser **tout** ou **les billets seulement** (en gardant le don). Une vente directe n'a pas de commission à retirer. Le titulaire peut **refuser** une demande de remboursement.

**Fiche événement étoffée, compatible projet Dolibarr** (décision Drisse). Champs ajoutés: type, responsable, date exacte, mots-clés, début du montage, sécurité, secours, buvette, lien public; **budget prévisionnel** (recettes, salle, rémunérations, autres coûts, résultat prévu); **tâches** avec échéance, responsable, avancement et retard (modèle de tâches: contrat de salle, assurance, buvette, SACEM, sécurité, bénévoles, communication, solde). Correspondances vérifiées sur l'instance (module Projets actif):

| Cassandra | Projet Dolibarr |
|---|---|
| identifiant `EVT-…` | `ref_ext` (retrouvable par `/projects/ref_ext/…`); `ref` généré puis relu |
| nom | `title` |
| description | `description` |
| date | `date_start`, `date_end` |
| état (brouillon, en vente, terminé ou annulé) | `status` (0, 1, 2) |
| coût total du budget prévisionnel | `budget_amount` |
| (toujours) | `usage_task` = 1 |
| tâche | tâche du projet (`label`, `fk_project`, `date_start`, `date_end`, `progress`) |
Le pont a un interrupteur « Événements → projets ». Sans Dolibarr, la fiche événement garde tout en local.

**Verrou des formules d'artiste** (décision Drisse, importante). Une formule déclarée **de type artiste est réservée aux artistes**: elle **ne peut jamais être affectée à un revendeur indépendant**, ni comme formule par défaut, ni par événement. Le verrou est **dans l'interface** (ces formules ne sont pas proposées, la carte porte « Réservée aux artistes ») **et dans la règle** (une tentative forcée est refusée avec un message). Le type d'une formule est définitif; la formule de revendeur indépendant, elle, porte aussi le cachet de l'artiste qui ne vend pas.

## 4 septies. Profil du revendeur, compatible fournisseur Dolibarr

**Profil du revendeur** (décision Drisse). L'écran du revendeur a un onglet **« Mon profil »**, à côté de ses événements. Il contient: identité et coordonnées, fiscalité et règlement, identifiants, compatibilité Dolibarr, sécurité du compte. Le titulaire en voit un **résumé** dans la fiche du revendeur (complète ou « manque: … »).

**Champs et correspondances** (vérifiés sur l'instance, tiers fournisseurs en lecture seule):

| Champ du profil | Champ fournisseur Dolibarr | Obligatoire |
|---|---|---|
| statut (particulier, auto-entrepreneur, entreprise, association) | `typent_code` (TE_PRIVATE ou TE_SMALL) | non |
| nom, ou raison sociale pour un professionnel | `name` | **oui** |
| courriel, téléphone | `email`, `phone` | recommandé |
| adresse, code postal, ville, pays | `address`, `zip`, `town`, `country_code` | pour être payé |
| SIRET | `idprof1` | pour un professionnel |
| assujetti à la TVA, n° de TVA | `tva_assuj`, `tva_intra` | si assujetti |
| conditions de règlement (à réception, 30 jours, 30 jours fin de mois, 60 jours) | `cond_reglement_supplier_id` | non |
| mode de règlement (virement, PayPal, chèque) | `mode_reglement_supplier_id` | non |
| IBAN, BIC | compte bancaire du tiers, envoyé **séparément** par `/thirdparties/{id}/bankaccounts`, **lu dans le coffre** | pour être payé |
| identifiant `REV-…` | `ref_ext` | oui (côté Cassandra) |
| (drapeau fournisseur, code) | `fournisseur` = 1, `code_fournisseur` = `auto` | généré par Dolibarr |

**Facturation de la commission.** Le revendeur choisit: **« le titulaire établit une auto-facture en mon nom »** (mandat de facturation, la facture fournisseur est créée dans Dolibarr au nom du revendeur) ou **« je facture moi-même »**. À valider avec l'expert-comptable selon le statut du titulaire.

**Règles.** Un revendeur **sans IBAN ne peut pas demander de retrait**. Un revendeur professionnel (hors particulier) doit avoir un SIRET, et un revendeur assujetti à la TVA un numéro de TVA, pour que sa fiche soit « complète ». Un artiste qui vend a son profil dans sa **fiche artiste** (adhérent, §4 quinquies); son compte revendeur lié produit le tiers fournisseur à partir de cette fiche. Une invitation crée un **profil vide**, à compléter par le revendeur. Le nom du compte ne change pas quand on modifie l'identité légale (les ventes et affectations restent rattachées au compte).

## 4 octies. La caisse (billetterie sur place)

**Compte caisse du titulaire** (décision Drisse). Un écran « Caisse » pour vendre des billets à l'entrée, avec **espèces** et **carte** (terminal **Stripe**, terminal **SumUp**, ou **déclaration manuelle** d'un paiement fait sur un terminal autonome). Il s'ouvre au titulaire et à ses **caissiers** (rôle « caisse » du §2 bis, droits: ouvrir la caisse, encaisser, rembourser, clôturer; le remboursement est un droit sensible).

**Session de caisse.** On **ouvre** avec un fond de caisse, un caissier et un événement; on **clôture** en comptant les espèces. Identifiant de session `CAI-…`, jamais réutilisé.

**Encaisser**
- **Espèces**: montant reçu, puces (appoint, 20, 50, 100 €), **rendu de monnaie** calculé; un montant insuffisant est refusé.
- **Carte, terminal Stripe ou SumUp** (automatique): le montant est **envoyé au lecteur**, le résultat **revient tout seul**; une carte refusée laisse le client réessayer ou payer autrement. La référence de transaction est conservée.
- **Carte déclarée** (manuel): le caissier déclare un paiement **déjà accepté** sur un terminal autonome (n° d'autorisation, 4 derniers chiffres, confirmation obligatoire). La vente est marquée **« à rapprocher »** avec le relevé bancaire.
Chaque mode se **désactive** dans les réglages. Une vente de caisse est une **commande en vente directe** (aucune commission), elle décompte les places, et elle apparaît dans Titulaire › Commandes.

**Remboursement en caisse.** Le même **remboursement unique** (§4 sexies): espèces rendues par le caissier ou carte rendue par le prestataire, aucune commission à retirer, avoir si Dolibarr est relié. La vente sort des totaux de la session.

**Clôture (ticket Z).** Total des ventes par mode (espèces, Stripe, SumUp, déclarées), fond de caisse, **espèces attendues** (fond + ventes en espèces − remboursées), espèces comptées, **écart** (toléré jusqu'à un seuil réglable). La clôture est **numérotée en continu** (`Z-000001`…), **archivée et non modifiable**, et se revoit à tout moment.

**Réglages** (Titulaire › Réglages › Caisse): espèces, Stripe, SumUp, déclaration manuelle; nom des lecteurs; fond de caisse par défaut; écart toléré; rappel réglementaire.

**Dolibarr.** Interrupteur « Ventes en caisse → factures et règlements »: facture par vente, règlement sur un **compte « caisse »** (espèces) ou sur le compte du prestataire (carte). Sans Dolibarr: reçus de caisse et clôtures exportables.

**Point réglementaire à valider.** En France, les **logiciels de caisse** des assujettis à la TVA doivent être **certifiés NF 525** (ou attestés). Le titulaire est ici une association non assujettie, donc l'obligation ne s'applique en principe pas; l'écran de réglage le rappelle et l'indique en rouge si le titulaire devient assujetti. À confirmer avec l'expert-comptable avant la mise en service. Les principes de la loi sont déjà tenus: numérotation continue, registre en écriture seule, clôtures inaltérables.

## 4 nonies. Le contrôle des billets (l'ouvreur)

**Page de contrôle** (décision Drisse), pour l'**ouvreur** (rôle « contrôle » du §2 bis, créé par invitation, droit unique: contrôler les billets de l'événement et de la porte qui lui sont confiés). C'est une page web pensée pour un téléphone, qui sert aussi sur une tablette ou un ordinateur.

**Comment lire un QR code**
1. **Caméra du téléphone**: la page utilise l'API `BarcodeDetector` quand le navigateur l'a (Chrome sur Android), sinon une bibliothèque de lecture de QR code embarquée (jsQR); caméra arrière, lecture en continu. *Dans la maquette la caméra est simulée.*
2. **Lecteur USB ou Bluetooth**: il se comporte comme un clavier, tape le code puis Entrée; le champ du lecteur reste actif en permanence. *Fonctionne déjà dans la maquette.*
3. **Saisie du numéro** ou **recherche par nom** quand le QR est illisible; la validation à la main est **tracée** (« validé à la main »).

**Contenu du QR code**: `CASS1.<numéro du billet>.<signature>`, où la signature est calculée avec une **clé secrète conservée dans le coffre**. Un QR recopié ou modifié a une mauvaise signature et est **refusé comme falsifié**; un numéro inconnu est refusé comme **invalide**.

**Résultats**, avec couleur et détail
- **Vert « Entrée autorisée »**: nom, type de billet, « entrée 1 sur 2 » pour un pack duo, mention **invité (catégorie)** pour une invitation.
- **Rouge « Déjà utilisé »**: heure, porte et ouvreur du premier passage.
- **Rouge « Billet annulé »**: la commande a été **remboursée** (le billet est invalidé automatiquement par le remboursement unique, §4 sexies).
- **Rouge « Paiement en attente »**: virement non reçu, ou **vente en espèces d'un revendeur dont la remise n'est pas validée**. Le titulaire les débloque dans Commandes › Paiements en attente (« Virement reçu », « Valider la remise »).
- **Rouge « Billet invalide »**: inconnu ou falsifié.
- **Orange « Autre événement »**: le billet est pour un autre événement.
Un **pack duo** compte deux entrées sur le même QR. L'ouvreur peut **annuler une entrée** qu'il vient de valider (droit sensible, tracé).

**Compteurs en direct**: entrées sur billets valides, restants, invités entrés, refusés. Un **registre des passages** (heure, billet, porteur, résultat) est conservé, **non modifiable**.

**Mode hors ligne** (décision de principe): avant l'ouverture, la page **télécharge la liste des billets valides** (leur signature suffit à les vérifier sans réseau); les entrées s'enregistrent localement puis se **synchronisent**. Limite assumée: **un même billet scanné à deux portes en même temps hors ligne** ne se détecte qu'à la synchronisation, où le conflit est signalé.

**Liens avec le reste**: les billets viennent des **ventes en ligne, des ventes de caisse, des ventes en espèces des revendeurs et des invitations**; le **remboursement** et l'**annulation d'événement** invalident les billets; la **caisse** (§4 octies) crée des billets scannables à la vente.

## 4 decies. Boutique (calendrier, page d'événement, QR), numéro de contrôle, gestion des billets

**Boutique: calendrier d'abord** (décision Drisse). La page d'accueil de la boutique est un **calendrier des événements** (grille mensuelle avec navigation, événements passés en grisé) suivi de la **liste des prochains événements** (date, lieu, accroche, tarif de départ, places restantes ou « dernières places », « complet », « terminé »). Les événements **masqués** (case « Publiée sur la boutique » de la fiche) ou en brouillon n'apparaissent pas.

**Page d'un événement, construite à partir de sa fiche.** Nom, date et horaires (portes, début, fin), lieu, description, mots-clés, **programme** (artistes dans l'ordre, heures de passage calculées avec dix minutes entre deux passages), informations pratiques (salle, adresse, configuration et jauge, public, accessibilité, buvette, équipement), tarifs de l'événement et places restantes, organisateur et conditions d'annulation. Modifier la fiche modifie la page. Un champ **accroche** (texte court du calendrier) et la case de publication sont dans la fiche, section « Page publique et QR code ».

**QR code direct vers la page de l'événement.** Chaque événement a une page à l'adresse `…/<événement>`; son **QR code** (téléchargeable en affiche A4 depuis la fiche) ouvre cette page. Un **code d'événement** (`EVT-000001`) est imprimé sous le QR et peut être saisi dans la boutique pour ouvrir la page sans lecteur. Le lien d'un **revendeur** ajoute son code de vente: la vente lui est attribuée seulement quand on arrive par son lien (ou qu'on saisit son code); sans lien, c'est une **vente directe**, sans commission.

**Numéro de contrôle intégré à chaque billet** (décision Drisse). Sous chaque QR code de billet est imprimé un **numéro de contrôle**: le numéro du billet suivi de **6 caractères de contrôle** (ex. `A-0430-7K3Q9X`), calculés avec la même clé secrète que la signature du QR. Il permet le **contrôle à la main** quand le titulaire n'a **aucun lecteur**: l'ouvreur saisit le numéro complet; une **faute de frappe ou un numéro inventé est refusé** (« numéro de contrôle incorrect »), et un **numéro incomplet** (sans les 6 caractères) **ne fait jamais entrer** quelqu'un, parce que les numéros de billets se suivent et seraient devinables. La saisie tolère majuscules, minuscules et espaces. La **recherche par nom** reste possible, avec validation à la main tracée. En dernier recours, une **liste de secours** (numéros de contrôle complets, nom, type, statut, case à cocher) est imprimable par le titulaire ou l'ouvreur; **chaque impression est enregistrée** et le document est confidentiel. Le billet affiche aussi ce numéro dans le compte du client et dans son PDF. Un billet **réémis** a un **nouveau numéro et un nouveau QR**; l'ancien est refusé.

**Gestion des billets dans l'événement** (décision Drisse). Nouvel onglet Titulaire › **Billets**, avec deux parties:
- **Types de billets par événement**: nom, description, **prix**, **quota propre** (0 = sans limite), **nombre d'entrées** (1, ou 2 pour un pack duo), **fenêtre de vente** (début, fin), **canaux** (boutique, caisse, revendeurs), proposé ou non. Exemples: prévente à quota et date limite, billet « sur place » réservé à la caisse, tarif réduit. Supprimer un type **sans vente** le supprime; un type **déjà vendu** est seulement **retiré de la vente** (conservé pour l'historique). Les quotas par type sont comparés aux places en vente. **La boutique, la caisse et les ventes des revendeurs** proposent les types de leur canal, grisent un type épuisé ou hors fenêtre, refusent d'ajouter au-delà du quota, et décomptent le stock à la vente.
- **Billets émis**: liste filtrable (nom, numéro, type; valides, utilisés, en attente ou bloqués, annulés) avec le **canal** d'origine (boutique, caisse, revendeur, invitation, offert) et, pour chaque billet: voir le **QR et le numéro de contrôle**, **renvoyer** par courriel, **modifier le porteur**, **réémettre** (nouveau QR, ancien refusé), **bloquer ou débloquer**, **annuler** (le remboursement, qui retire aussi la commission, reste dans Commandes). On peut aussi **émettre un billet offert** (hors vente, sans recette ni commission, tracé), **exporter en CSV** et ouvrir la **liste de secours**.
Un billet dont le paiement n'est pas reçu ou la remise d'espèces non validée est **bloqué à l'entrée**; l'annulation, le blocage et la réémission sont visibles immédiatement dans la page de contrôle.

## 4 sexies bis. Deux groupes de formules, étanches (remplace le détail du verrou ci-dessus)

Décision (Drisse): les formules forment **deux groupes qui ne se voient pas**.
- **Formules d'artistes**, de deux types: **artiste vendeur** (forfait + commission par place) et **artiste à cachet fixe** (ne vend pas). Elles ne sont **jamais proposées à un revendeur**.
- **Formules de revendeurs indépendants**: commission par place, avec **palier** facultatif; **aucun cachet**. Elles ne sont **jamais proposées à un artiste**.
Un artiste ne peut donc **jamais** recevoir une formule de revendeur, ni un revendeur une formule d'artiste: les menus ne les proposent pas, et une tentative forcée est refusée avec un message. Le groupe d'une formule est définitif. À la suppression, le remplacement ne se fait que **dans le même groupe**. Le cachet de l'artiste qui ne vend pas vit dans sa **formule d'artiste à cachet fixe** (ex. « Cachet fixe », 100 €), plus dans une formule de revendeur. Dans la comparaison de rentabilité, une formule à cachet fixe est **associée** à la formule de revendeur choisie dans un réglage (« formule de revendeur associée »); seules les formules d'artistes forment les colonnes.

## 4 undecies. Programme, fiche en onglets, compte client, Mon compte

**Programme par événement** (décision Drisse). Dans l'onglet **Programme** de l'événement, le titulaire fixe, pour chaque artiste: l'**ordre de passage** (flèches monter et descendre), le **nombre de passages** (un artiste peut jouer plusieurs fois dans la soirée: « ＋ passage ») et la **durée** de chaque passage. Une **pause entre deux passages** est réglable par événement. Les **heures** de passage se calculent à partir du début de la soirée; une alerte signale un programme qui finit **après la fin prévue** ou **après l'heure limite de la salle**. Le **fixe de l'artiste** (forfait ou cachet) n'est compté **qu'une fois** (au premier passage; retirer le premier passage le reporte sur le suivant); sa **commission** non plus. La page publique affiche « passage 1/2 »; le compte de l'artiste liste tous ses passages.

**Fiche événement en onglets, billets réglés par événement** (décision Drisse). L'onglet global « Billets » est supprimé: chaque événement a ses onglets **Fiche**, **Programme**, **Billets** (types, billets émis, règle de compte client), **Revendeurs et invitations**, **Budget et tâches** (avec le projet Dolibarr), **Annulation**. Choisir un autre événement garde l'onglet ouvert.

**Compte client: obligatoire, ou achat sans compte avec frais** (décision Drisse). Réglage général (Titulaire › Réglages › Comptes clients et achats):
- **compte client obligatoire**: le client crée son compte à l'achat (lien d'activation par courriel), **sans frais**; ou
- **achat sans compte autorisé**, avec des **frais de service** (montant réglable, **par commande** ou **par billet**). Le client choisit à la boutique: créer son compte (gratuit) ou continuer sans compte (+ frais, ajoutés au total et détaillés).
Chaque **événement peut avoir sa propre règle** et ses propres frais (onglet Billets de l'événement); sinon le réglage général s'applique. La page de l'événement rappelle la règle. Dans Titulaire › Clients, une colonne distingue **compte** et **sans compte**. Les frais de service ne sont **pas une ligne de billet**: ils ne créent pas de billet, et le remboursement « billets seulement » ne les rend pas.

**Mon compte Cassandra, pour chaque type de compte** (décision Drisse). L'artiste, le revendeur et le client ont un onglet **Mon compte**, repris de la gestion de compte Cassandra: **mot de passe** (règle: 12 caractères au moins, confirmation), **clés de sécurité WebAuthn** (ajouter, retirer), **sessions ouvertes** (fermer une session, fermer toutes les autres), **mes rôles** (avec « Entrer » pour passer d'un rôle à l'autre), **notifications** (ventes et commissions, retraits, rappels d'événement, remboursements; canal courriel, Telegram ou SMS), **export et suppression de mes données**. Les trois profils métier (revendeur, artiste, client) renvoient vers cet onglet pour la sécurité.

**Profil de l'artiste renforcé** (même niveau que le revendeur). Statut juridique, SIRET pour un professionnel, assujettissement à la TVA, conditions et mode de règlement, **IBAN dans le coffre** (un artiste sans IBAN ne peut pas demander de retrait), identifiants (artiste et, s'il vend, revendeur et code de vente), **compatibilité adhérent Dolibarr** avec la liste de ce qui manque et l'aperçu de ce qui part vers Dolibarr.

## 5 bis. Prestataires de paiement (plusieurs, au choix du titulaire)

Décision (Drisse) : **Stripe, HelloAsso, PayPal et virement bancaire**, activables ensemble ; le titulaire coche ceux qu'il propose, l'acheteur choisit au paiement.

Le module définit **une interface de prestataire** (créer un paiement, vérifier le webhook, rembourser, lire l'état) et chaque prestataire est un **sous-module** qui l'implémente. Ajouter un prestataire plus tard n'ouvre aucun autre fichier. La commande ne connaît que l'interface.

| Prestataire | Mode | Particularités |
|---|---|---|
| Stripe | paiement hébergé (Checkout) + webhook signé | remboursement par API ; partage automatique possible plus tard (Connect, option B) |
| HelloAsso | paiement hébergé + notification | réservé aux associations (sans frais, dons facultatifs) ; vérifier que l'usage billetterie est couvert par leurs conditions |
| PayPal | Orders API v2 + webhook | capture explicite avant de créer les billets ; remboursement par API |
| Virement | **manuel** | voir ci-dessous |

**Virement bancaire.** La commande passe `en attente de virement` avec une **référence unique** (ex. `EVT12-7K3Q`) que l'acheteur met en libellé. Le stock est réservé plus longtemps (défaut 3 jours, réglable) puis libéré. Le titulaire marque le virement reçu (lot 4), ou plus tard importe son relevé (CSV/CAMT) et Cassandra rapproche par référence et montant. Les billets sont émis à la réception. Pas de remboursement automatique : écriture `annulation_commission` et remboursement fait à la main par le titulaire.

Règles communes : chaque prestataire pose son identifiant de transaction dans `commande`, **unique par prestataire** ; les clés de chacun sont dans le coffre ; un prestataire sans clés valides est grisé côté titulaire et absent côté acheteur.

## 5 ter. Fiscalité et comptabilité : Dolibarr fait foi

Décision (Drisse) : **la fiscalité n'est pas réinventée dans Cassandra, elle est déléguée à Dolibarr**, qui la gère déjà (TVA, numérotation légale des factures, comptabilité, avoirs). Le module billetterie **requiert** le module `dolibarr` (champ `requiert` du manifeste) et lui parle par son API ; il ne réécrit rien de ce que Dolibarr sait faire.

**Ce que le module `dolibarr` sait déjà** (v0.3.0, lu dans le code) : créer des tiers et produits, créer des brouillons de factures avec lignes, les valider, avec preuve et retour arrière, et signaler une instance injoignable.
**Ce qui lui manque** et que la billetterie exige, à ajouter **dans le module `dolibarr`** (pas dans la billetterie) :
- enregistrer un **paiement** sur une facture (et choisir le compte bancaire de Dolibarr) ;
- créer un **avoir** (remboursement) ;
- lire les **taux de TVA**, la **société** et le compte bancaire par défaut ; les comptes du plan comptable **se règlent dans Dolibarr** (aucune route de lecture, voir la vérification ci-dessous) ;
- une **sonde de santé** exploitable par la billetterie (elle existe : événements `dolibarr.injoignable` / `dolibarr.reprise`).

**Correspondances**

| Billetterie | Dolibarr |
|---|---|
| Titulaire de l'instance (§3) | la société Dolibarr : **Dolibarr fait foi** pour l'identité légale, Cassandra la lit (§3) |
| Acheteur | tiers (client) créé ou retrouvé par courriel |
| Type de billet | produit, avec son taux de TVA |
| Commande payée | facture validée + paiement enregistré sur le compte du prestataire |
| Remboursement | avoir lié à la facture |
| Commission d'un revendeur | **achat / charge** côté Dolibarr : le revendeur est un tiers fournisseur, la commission une facture fournisseur, le versement son règlement |
| Export comptable (lot 7) | ce que Dolibarr produit déjà ; la billetterie n'exporte qu'un relevé de ses écritures |

**Règles**
- **Dolibarr n'est jamais sur le chemin du paiement.** L'acheteur paie, les billets sont émis, **puis** l'écriture dans Dolibarr se fait en arrière-plan. Si Dolibarr est injoignable, les écritures attendent dans une **file de rattrapage** (idempotente, par identifiant de commande) et sont rejouées à la reprise (`dolibarr.reprise`). Une vente ne doit jamais échouer parce que la comptabilité est en panne.
- **Dolibarr optionnel.** Sans lui, la billetterie fonctionne (billets, registre, retraits) ; elle affiche « comptabilité non reliée » et conserve la file. La mention de TVA du billet vient alors du réglage Titulaire.
- **Aucune donnée fiscale dupliquée** : taux et numérotation viennent de Dolibarr, la billetterie ne stocke que l'identifiant de la facture.
- L'autonomie du module `dolibarr` (plafond choisi par l'administrateur) s'applique : une écriture comptable automatique de billetterie est un **mandat explicite** et non un choix de l'agent.

**Lot ajouté** : *lot 3 bis, extension du module `dolibarr`* (paiement, avoir, TVA, compte bancaire, facture fournisseur), avec tests contre une instance Dolibarr de recette, avant le lot 4. À vérifier d'abord que l'API REST de l'instance expose ces routes (versions de Dolibarr).

*Vérification du 17-10-2026* (lecture seule, clé de `Documents\Cassandra\dolibarr.key`, instance Athena `:8081`, **Dolibarr 23.0.2**, 341 routes) :

| Besoin | Route | État |
|---|---|---|
| Paiement d'une facture client | `POST /invoices/{id}/payments` | **présente** |
| Valider une facture | `POST /invoices/{id}/validate` | présente (déjà utilisée par le module) |
| Facture fournisseur (commission) | `POST /supplierinvoices`, `/validate`, `/payments`, `/settopaid` | **présentes** |
| Société du titulaire | `GET /setup/company` | **présente** : nom, pays, SIRET (idprof), TVA intra, assujettissement TVA, capital, langue, logo ; lue avec succès |
| Taux de TVA | `GET /setup/dictionary/vat` | présente (5 taux) |
| Comptes bancaires | `GET /bankaccounts` (+ `/lines`, `/balance`) | présente (5 comptes) |
| Modes de paiement | `GET /setup/dictionary/payment_types` | présente |
| Avoir (remboursement) | pas de route dédiée « créer un avoir » | **par `POST /invoices` avec `type = 2` et `fk_facture_source`** (à tester en recette) |
| Plan comptable | **aucune route** pour le lire | **manque** : seul `GET /accountancy/exportdata` existe (export) |

Conséquences : (1) le lot 3 bis tient avec l'API telle quelle, sauf le plan comptable ; (2) **le compte comptable ne se choisit pas par l'API** : il se règle dans Dolibarr (comptes par défaut du produit « billet » et du tiers fournisseur « revendeur »), et la billetterie crée les objets avec la bonne fiche produit sans jamais manipuler de numéro de compte ; la correction de §5 ter ci-dessus « lire le plan comptable » devient « s'appuyer sur les comptes par défaut réglés dans Dolibarr ». (3) Une première écriture de recette (facture + paiement + avoir) sera faite sur une **entité ou un tiers de test**, jamais sur la comptabilité réelle. (4) L'instance est issue d'une fusion multi-entités : vérifier que la clé API agit bien sur l'**entité du titulaire**.

**Maquettes** : `docs/CN_maquette-billetterie.html` réunit les quatre vues (Titulaire, Revendeur, Boutique, Compte client) et les relie : une demande de retrait côté revendeur apparaît côté titulaire, une commande en boutique alimente les ventes du revendeur. L'ancienne `docs/CN_maquette-revendeur.html` (écran revendeur seul) est conservée. Clair, sombre et téléphone vérifiés au navigateur. **Tous les boutons sont actifs** (48 fenêtres, 52 actions de formulaire, fiche ou aperçu, vérifiées une à une, dont la gestion des formules, les affectations multiples, le registre des identifiants et ce qui part vers Dolibarr) : nouvel événement, artiste, salle, invitation d'un revendeur, fiche et suspension d'un revendeur, ajout d'un artiste, d'un revendeur ou d'une catégorie d'invitations à un événement, vente en espèces, demande de retrait, refus avec motif, paiement par chacun des quatre prestataires, aperçu du billet PDF, transfert de billet, aperçu de la facture ou du reçu, aperçu du Cerfa, export, anonymisation et suppression du compte client, document de salle.

## 5 quater. Plateforme de vente publique et compte client

Décision (Drisse) : le module fournit **la boutique où les clients paient eux-mêmes leur billet**, avec un **compte client** : historique d'achats, factures téléchargeables automatiques, et, si le titulaire est une association, un **reçu pour les dons**.

**Trois identités, étanches** : le titulaire (administrateur de l'instance), le **revendeur** (compte réduit, §2) et le **client** (nouveau). Le client n'est **pas un utilisateur de Cassandra** : il n'a aucun accès à l'application, seulement à sa boutique. Sa table, sa session et ses cookies sont à part.

**Boutique publique**
- Pages : liste des événements, page d'un événement (types de billets, quotas restants), panier, paiement, confirmation.
- **Achat sans compte possible** (courriel seul, lien magique pour retrouver ses billets), création de compte proposée à la fin ; le compte se rattache aux achats déjà faits avec le même courriel vérifié.
- Un lien de revendeur (`?r=CODE`) grave le revendeur sur la commande ; sans lien, vente directe du titulaire.
- Le paiement se fait chez le prestataire (§5 bis) : aucune donnée de carte ne passe par Cassandra.
- Domaine et exposition : la boutique est publique, l'interface d'administration ne l'est pas. Elle tourne dans un **processus séparé**, avec sa propre liste blanche de routes, sa CSP, une limitation de débit et un piège anti-robots, et n'a **aucun accès au coffre** hors de la clé du prestataire (via le courtier de la cage).

**Compte client (espace « Mes billets »)**
- **Historique** des commandes, par événement, avec l'état de chaque billet.
- **Billets** : QR à l'écran, PDF téléchargeable, envoi à un tiers (transfert de billet à un autre nom), renvoi par courriel.
- **Factures** : générées **automatiquement** après paiement. Voie normale : la facture est créée, validée et payée dans Dolibarr (§5 ter), le PDF est produit par Dolibarr (`PUT /documents/builddoc`), puis le client le télécharge **à travers Cassandra** (`GET /documents/download` côté serveur) : le client n'a jamais d'accès à Dolibarr. Sans Dolibarr, le module émet un **reçu PDF simple** (pas une facture légale) et le dit.
- **Données personnelles** : export et suppression à la demande (RGPD) ; les factures déjà émises sont conservées pour la durée légale, le reste est anonymisé.
- Connexion : courriel + lien magique, mot de passe facultatif ; la clé de sécurité (WebAuthn) du noyau pourra s'y ajouter plus tard.

**Association : déduction fiscale, ce qu'il faut savoir**
- **Un billet n'ouvre pas droit à réduction d'impôt.** C'est l'achat d'une prestation, pas un don. Aucune promesse de déduction ne figure donc sur un billet.
- Ce qui peut être déductible, c'est un **don** : une ligne **« don facultatif »** ajoutée au paiement, sans contrepartie. Le **reçu fiscal** ne peut être émis que si le titulaire est un **organisme éligible** (intérêt général, reconnu par l'administration) : le réglage Titulaire porte un indicateur « éligible aux reçus de dons » **renseigné par le titulaire, avec la mention de sa base légale**, et sans lui aucun reçu n'est proposé.
- **Dolibarr gère les dons et émet le Cerfa** (module « Dons », reçu fiscal Cerfa 11580) : c'est lui qui fait foi, comme pour le reste (Drisse). Constat sur l'instance (17-10-2026) : le **module Dons n'y est pas activé** (54 modules actifs, dont « adhérents », aucun don), et l'API REST n'expose aujourd'hui **aucune route de dons** ; comme l'API ne charge que les modules actifs, on ne peut pas conclure avant de l'avoir activé.
- Marche à suivre : (1) activer le module Dons dans Dolibarr et configurer le Cerfa (identité de l'association, article du code général des impôts), (2) relire `swagger.json` pour voir si des routes de dons apparaissent, (3) sinon, ajouter à Dolibarr une **petite classe d'API dans un module maison** (Dolibarr accepte les classes `api_*.class.php` de modules personnalisés) pour créer un don et construire le reçu, plutôt qu'écrire en base à la main. Dans tous les cas, **le module billetterie ne fabrique pas de reçu fiscal lui-même**. Le don est créé dans Dolibarr à la validation du paiement, et le reçu PDF est téléchargé comme une facture.

**Dépendances ajoutées** : `courrier` (liens magiques, billets, factures), `dolibarr` (facture, PDF), `coffre` (clés prestataires), cage par provenance (isolement du processus public).

## 6. Garde-fous

- **Webhooks idempotents** : l'identifiant de paiement est unique ; un double appel ne crée pas deux commandes.
- **Pas de survente** : décrémenter le stock et réserver dans **une seule transaction**.
- **Cloisonnement** : un revendeur ne lit que ses billets et ses écritures (règle de `droits`/`comptes`), jamais les acheteurs d'un autre. Le titulaire voit tout.
- **Données acheteurs** minimales : nom, courriel. Conservation limitée et purge après l'événement + délai légal.
- **Routes publiques** (page de vente, webhook, billet) : déclarées explicitement dans la liste blanche, avec leur CSP.
- **Clés de paiement** dans le coffre uniquement.
- **Journal** : toute écriture du registre et tout scan est tracé.

## 7. Où ça s'accroche dans la V19

| Besoin | Brique existante |
|---|---|
| Titulaire | `reglages` (nouveau groupe), lu par `dolibarr`, `courrier` |
| Revendeurs | `comptes` + `droits` (rôle réduit) |
| Temps réel | `bus` / SSE du noyau |
| Mails de billets | `courrier`, expéditeur du Titulaire |
| Clés de paiement | `coffre` |
| Factures / reçus | `dolibarr` (à vérifier : ce qu'il sait déjà faire) |
| Alertes (stock bas, refus de paiement) | `notifications`, `proactif` |
| Capacités déclarées | `mandats`, manifeste du module |

Le module `billetterie` serait un module ordinaire (manifeste, contrats, corpus) : il ne touche pas au noyau, hors le groupe Titulaire dans `reglages`.

## 8. Découpage en lots

0. **Rôles de compte** (noyau, modules `comptes` et `droits`): groupes artiste, revendeur, client; invitation par rôle; inscription du client à l'achat; refus d'entrée dans l'application sans droit d'application (§2 bis).
1. **Titulaire** (noyau) : champs, écran de réglage, lecture par les modules.
2. **Événements, types de billets, revendeurs, règles de commission.**
3. **Registre (portefeuille)** et son relevé, avec tests de somme.
3 bis. **Extension du module `dolibarr`** : paiement, avoir, TVA, compte bancaire, facture fournisseur (§5 ter), puis file de rattrapage.
4. **Vente publique + les quatre prestataires + webhook + vente en espèces** (déclaration par le revendeur, validation de la remise par le titulaire).
4 bis. **Boutique publique et compte client** (§5 quater) : processus public isolé, achat sans compte, comptes clients, historique, billets téléchargeables, factures automatiques (PDF Dolibarr), export et suppression RGPD.
5. **Billets, mails, QR, contrôle à l'entrée.**
6. **Écran revendeur temps réel** (ventes, commissions, par événement) et écran titulaire.
7. **Remboursements, versements, export comptable.**
7 bis. **Dons et reçus fiscaux** (association éligible seulement) : activer le module Dons de Dolibarr, vérifier ou ajouter la route d'API, créer le don et télécharger le Cerfa depuis l'espace client ; transfert de billet entre clients.
8. Hors ligne du contrôle ; prestataire en mode partage automatique (option B).

## 9. À trancher

1. ~~Prestataire~~ : tranché (Stripe, HelloAsso, PayPal, virement ; voir §5 bis). Livraison (Drisse) : **les quatre au lot 4, d'un coup**. Le lot est donc le plus lourd (quatre sous-modules, quatre jeux de tests de webhook, rapprochement du virement) ; l'interface de prestataire est écrite et testée en premier, avec un faux prestataire, avant les quatre vrais.
2. ~~Rôle du revendeur~~ : tranché (compte dédié réduit billetterie + paiement). Délai (7 jours après l'événement) et seuil (20 €) : tranchés, voir §2.
3. ~~Commission~~ : tranché, **montant fixe ou pourcentage, au choix par règle**. Le pourcentage s'arrondit au centime inférieur, calculé sur le prix du billet hors frais du prestataire.
4. ~~Espèces~~ : tranché, **dès le premier lot de vente (lot 4)**.
5. ~~Fiscalité et statut des commissions~~ : tranché, **entièrement délégués à Dolibarr** (§5 ter). Il gère l'attribution fiscale par le **plan comptable** et le **statut légal du titulaire** ; la billetterie ne porte aucune règle fiscale. Chaque commission est associée à un **compte du plan comptable** (charge de commissions) choisi dans Dolibarr, et sa TVA suit le statut du titulaire tel que Dolibarr le connaît. Le réglage Titulaire de Cassandra ne stocke que l'identifiant de la facture fournisseur créée.
6. ~~Identité légale~~ : tranché, **Dolibarr fait foi**, Cassandra la lit (§3). Le module `dolibarr` doit donc aussi savoir **lire la société** (route des informations de l'entreprise) : ajouté au lot 3 bis, et le lot 1 (Titulaire) livre d'abord la saisie locale, puis la lecture Dolibarr au lot 3 bis.

## 10. Enveloppe d'interface : la V19, pas la V18

La maquette reprend l'interface de la **V19** (`interface/CN_index.html`, `CN_shell.css`) : en-tête (☰, flèches retour/suivant, marque, point d'état, badge 19.0, heure de session), cloche, thème, menu du compte en haut à droite (identité, « Cette session », apparence, écran allégé, Paramètres généraux, raccourcis, verrouiller, se déconnecter) et colonne latérale à groupes repliables.

- **Une vue par rôle.** Titulaire : Billetterie, Bases, Réglages (dont « Module Billetterie »). Revendeur, artiste, caisse, contrôle : menus réduits, sans les entrées de Cassandra. Boutique et compte client : enveloppe publique, sans colonne ni menu de Cassandra.
- Le sélecteur de vues du menu du compte est **propre à la maquette** (en vrai, la vue découle du compte).
- Les premiers niveaux d'onglets de page sont remplacés par la colonne latérale.

## 11. Réglages du module (Paramètres généraux › Modules › Billetterie)

Dans les réglages du module, pas dans l'onglet Billetterie : **adresse de l'interface boutique** (domaine, https, page d'accueil par défaut, mise en ligne/hors ligne, test), **chemins** (événement, compte, revendeur, retour des fournisseurs), **description complète des fonctionnalités**, **guide de paramétrage** (liste qui se coche d'après l'état), **avec ou sans Dolibarr**, **réglementation française** (avertissement : informatif, à valider), **découpage CN/EC**. Les liens et QR de toute la billetterie se construisent avec ce domaine ; le QR d'un billet contient un identifiant, pas une adresse.

## 12. Prérequis réels de Dolibarr (lus sur l'instance, 18-10)

| Objet | Obligatoire |
|---|---|
| Tiers | nom ; professionnel en France : SIRET (idprof2, 14 chiffres), SIREN (idprof1, déduit), APE (idprof3) ; SIREN/SIRET uniques → un tiers par société |
| Adhérent (artiste) | courriel valide, identifiant, type de membre « Artiste » (à créer), lien `fk_soc` |
| Projet (événement) | titre ; référence automatique ; tiers facultatif |

**Contexte (précisé par Drisse)** : l'instance actuelle est multi-société ; la société lue est en France et assujettie à la TVA, mais **Maison Bohème est une association non assujettie**. Dolibarr sera refait sur FastPanel, en **société unique** (Maison Bohème, association). Conséquences : (1) le module ne code pas ces règles en dur, il les **relit par l'API à chaque liaison** (champs obligatoires, unicité, société, statut TVA) ; (2) l'hypothèse « non assujettie » de la maquette est la bonne, la caisse NF 525 ne s'applique pas tant que le statut ne change pas ; (3) le tableau ci-dessus décrit l'instance actuelle, à relire après la refonte (les règles SIRET/APE pourront différer).

## 13. Découpage CN / EC

- **CN_ (nexus)** : paiement et webhooks (signatures), émission et contrôle des billets, soldes, retraits, droits, écritures Dolibarr, journal. Une fonction pure mais décisive reste CN.
- **EC_ (évolutif)** : pur, déterministe, borné, mesurable, sans donnée persistante, sans décision. Points d'évolution : `EC_formules` (commissions), `EC_rentabilite`, `EC_tarifs` (propose seulement), `EC_billet` (mise en page ; QR et numéro viennent du nexus), `EC_textes`. Chacun a un contrat : schéma JSON + corpus de cas.

## 14. Liaison avec le bureau de Cassandra et Itare Citadelle

- Le module s'appuie sur **projets, tâches, répertoire et agenda** du bureau : un événement est un projet (même identifiant), ses tâches sont des tâches du bureau, artistes/revendeurs/clients/salles sont des fiches du répertoire (une fiche, deux usages). Réglable par domaine ; délié, le domaine reste local (mode autonome) et se rapproche plus tard par identifiant.
- La **vue d'ensemble du titulaire** porte une fenêtre de conversation avec **Itare Citadelle** (états des ventes, retraits à traiter, préparation de tâches). Itare propose, ne décide pas : aucune écriture ni aucun virement sans confirmation du titulaire.

## 15. Terrain : vendre et contrôler depuis un téléphone

La caisse et le contrôle se font debout, à l'entrée, sur un téléphone. Sous 700 px de large, ces deux vues se réduisent à l'essentiel ; sur iPad et ordinateur, tout redevient normal.

- **Commun** : ni colonne latérale, ni ☰, ni cloche, ni heure, ni flèches ; en-tête réduit à la marque et au compte ; explications masquées ; fenêtres en feuille qui monte du bas ; champs à 18 px (pas de zoom iOS) ; boutons d'au moins 48 px.
- **Caisse** : un seul chiffre (ventes de la session) ; les billets en lignes à gros boutons − / + ; **barre de paiement fixée en bas** (total, Espèces, Carte) toujours sous le pouce ; terminaux et clôtures précédentes masqués (on clôture depuis « Dernières ventes »).
- **Contrôle** : deux chiffres (entrées, restants) ; **le résultat du scan passe au-dessus de tout** (vert/rouge/orange, grand) ; caméra en 4/3 ; saisie du numéro de contrôle en grand ; recherche par nom ; mode hors ligne et liste de secours conservés plus bas.
- À valider sur appareils réels : lecture du QR par la caméra, retour sonore/vibration, luminosité au soleil.

## 16. Points tranchés après l'audit de complétude (18-10)

Tous portés en maquette (Réglages Titulaire, Promotions, Entrées, boutique, caisse, contrôle).

1. **Reçu fiscal en mode autonome : oui.** Sans Dolibarr, la billetterie produit un reçu au modèle du Cerfa 11580 (numéro continu, conservé 10 ans), uniquement pour la part « don » et pour un organisme éligible ; jamais pour un billet. Avec Dolibarr relié, le Cerfa de Dolibarr fait foi. Réglage : « Reçu fiscal sans Dolibarr ».
2. **Liste d'attente.** Quand un type de billet est épuisé ou l'événement complet, le client laisse son courriel ; le titulaire propose les places (lien d'achat valable 24 h, réglable). En service l'offre part seule à la libération d'une place ; dans la maquette elle se déclenche à la main.
3. **Codes promo.** Pourcentage ou euros par billet, par événement ou global, plafond d'utilisations, date de fin. Un code n'est **jamais réutilisé**, même supprimé. Réglage de l'effet sur la commission d'un revendeur (commission fixe inchangée / tout sur le prix catalogue) : **affiché mais pas encore calculé**, à brancher avec le moteur de commissions.
4. **Billets Apple Wallet et Google Wallet.** Même QR et même numéro de contrôle que le PDF ; mise à jour automatique si la date change. Il faut un certificat Apple (Pass Type ID) et un compte émetteur Google Wallet, rangés dans le coffre. Réglable séparément.
5. **Caisse sans réseau : réserve de numéros.** Chaque caisse reçoit avant l'ouverture un bloc de numéros consécutifs (50 par défaut). Sans réseau elle ne vend qu'avec son bloc : aucun doublon. Un numéro non utilisé n'est **jamais réattribué**. Hors ligne : espèces et carte déclarée seulement (les terminaux demandent le réseau) ; la clôture exige la resynchronisation.
6. **Places retenues pendant le paiement.** Carte, HelloAsso et PayPal retiennent les places 10 minutes (réglable) avec compte à rebours ; passé ce délai elles sont remises en vente ; si d'autres paiements retiennent déjà les places demandées, la commande est refusée avec le nombre restant. Le virement garde ses 3 jours.
7. **Contrôle hors ligne, deux portes.** Trois règles au choix du titulaire : **une catégorie par porte** (recommandée, aucun conflit possible), **signaler les conflits** (un billet peut entrer deux fois ; signalement à la synchronisation, arbitrage « accepter » ou « bloquer le billet » par le titulaire), **pas de contrôle hors ligne** (liste papier). Écran « Entrées » côté titulaire.

**Limites assumées** : le calcul réel de la commission sous promo, l'envoi automatique des offres de la liste d'attente, et l'émission réelle des passes Wallet relèvent du code du module, pas de la maquette.

## 17. Formules : trois retouches (18-10)

1. **Fenêtre « Nouvelle formule » : les champs qui ne concernent pas le type sont grisés.** Artiste revendeur : forfait + commission (fixe et palier grisés). Artiste à cachet fixe : forfait seul. Revendeur indépendant : commission, fixe et palier (forfait grisé). Le grisage suit le choix du menu ; un champ grisé n'est jamais enregistré.
2. **Fixe du revendeur indépendant** (€ par événement, versé dès la première place vendue), en plus de la commission par place et du palier. Il entre dans tout calcul de commission (provisions, rémunération estimée, simulateur de rentabilité) et s'affiche dans les conditions de la formule.
3. **Bouton « Modifier »** sur chaque formule : même fenêtre que la création, le type ne change pas ; la modification se répercute partout où la formule sert ; les événements qui ont déjà des ventes gardent leurs conditions d'origine (instantané).

Intitulés du menu : **Artiste revendeur** / **Artiste à cachet fixe (ne vend pas)** / **Revendeur indépendant** (remplacent « Formule artiste : l'artiste vend lui-même » et « Formule revendeur indépendant »).

## 18. Guide de paramétrage : les dix guides rédigés

Dans Module Billetterie › Guide de paramétrage, chacune des dix étapes se déplie en un guide complet : **à quoi ça sert, où le faire, les gestes dans l'ordre, comment vérifier, le piège à éviter**, avec un bouton « Ouvrir » qui mène à l'écran concerné et une pastille « fait / à faire » qui se coche d'après les réglages. Les dix : 1 domaine et DNS, 2 https, 3 organisateur, 4 paiement et adresse de retour, 5 salle et premier événement, 6 formules de commission, 7 Dolibarr (facultatif), 8 bureau de Cassandra, 9 publication et billet de test, 10 essai de la caisse et du contrôle (réseau coupé compris). Bouton « Tout déplier / Tout replier ».

## 19. Vue d'ensemble du titulaire repensée, et Itare qui règle tout le module

### Vue d'ensemble (refonte)
Ordre : **À traiter** (retraits, remboursements, paiements en attente, conflits d'entrée, liste d'attente, tâches en retard, écritures Dolibarr en file, chacun avec son bouton) à côté d'**Itare Citadelle** ; puis le **prochain événement** (jours restants, ventes, recettes, coûts estimés, seuil de rentabilité atteint ou non, places retenues, prochaines tâches, accès à la fiche) ; puis trois chiffres (chiffre d'affaires, billets, commissions dues) ; puis la liste des événements et les ventes en direct. Les interrupteurs du bureau de Cassandra quittent cet écran (c'est du réglage) pour **Module Billetterie › Bureau de Cassandra** ; une ligne d'état reste en bas.

### Itare règle le module à la demande du titulaire (super administrateur)
- **Principe d'architecture** : tout réglage et tout geste du module est une **action déclarée** (nom, schéma des champs, droits, contrôles). L'écran et Itare appellent **les mêmes actions** : Itare n'a aucun accès privilégié, donc aucune règle contournée (code promo jamais réutilisé, champs obligatoires, règles Dolibarr). Elle n'agit que sur demande du titulaire.
- **Palier d'autonomie, choix de l'administrateur** (pas un interdit codé) : « elle propose, je confirme » (défaut) ou « elle exécute, journalise, et je peux annuler ». Un second réglage, **Gestes financiers**, peut imposer la confirmation même au palier « exécute » (défaut : toujours confirmés). Valider un retrait n'envoie pas le virement.
- **Jamais** : lire ou écrire un secret. Les clés des prestataires et de Dolibarr restent dans le coffre, Itare ne les voit pas.
- **Journal** de toutes ses actions (heure, action, état) avec **Annuler** ; un code promo annulé reste interdit à la réutilisation, une formule annulée est retirée au registre.
- **Dans la maquette** : elle reconnaît par mots-clés des demandes réelles (code promo, formule revendeur, événement, seuil et délai de retrait, durée de réservation des places, durée d'offre de la liste d'attente, règle de contrôle hors ligne, domaine, Apple/Google Wallet, relier ou délier Dolibarr, valider les retraits, ouvrir un écran). En service, Itare comprend des demandes libres et appelle les mêmes actions. Module Billetterie › Itare liste ce qu'elle peut régler, permet d'essayer, et montre le journal.

### Défaut corrigé pendant ces essais
Un événement, un artiste ou une salle créé depuis un écran n'avait pas d'identifiant (`ref`) : la fiche plantait. Les identifiants manquants sont maintenant attribués à la création, jamais réutilisés.

## 20. Le chat d'Itare Citadelle, refait

- **Un tiroir de conversation partout** pour le titulaire (bouton flottant « Itare », ouvert/fermé à volonté, Échap pour fermer) : on lui parle depuis n'importe quel écran, sans perdre ce qu'on regarde. Sur ordinateur le contenu se décale ; sur téléphone le tiroir prend tout l'écran. La vue d'ensemble garde une carte de lancement.
- **Réponses riches** : cartes avec barres (ventes par événement, classement des revendeurs), listes avec boutons « Traiter » (ce qui est urgent, retraits, tâches, conflits, codes promo, liste d'attente), rentabilité du prochain événement, places restantes, commissions dues, état de Dolibarr.
- **Elle pose les questions qui manquent** (« Quel code, et quelle remise ? ») avec des réponses en un clic, et se souvient de la demande en cours.
- **Plans en plusieurs étapes** : « crée un code promo ETE15 de 15 % et mets la réservation à 15 minutes » devient un plan numéroté, confirmé d'un clic (« Tout confirmer ») ou refusé.
- **Avant → après** sur chaque changement, bouton **Annuler** sur chaque action faite, bouton **Voir dans…** vers l'écran concerné ; palier « Je confirme / Elle exécute » commutable dans l'en-tête du tiroir ; gestes financiers toujours confirmés si le réglage le demande.
- Confort : indicateur « Itare écrit », horodatage, suggestions selon l'écran affiché, Entrée envoie / Maj+Entrée saute une ligne, flèche haut rappelle le dernier message, effacer la conversation.
- Dans la maquette la compréhension passe par des mots-clés ; en service Itare comprend des demandes libres et appelle les mêmes actions.

### Défauts mobiles trouvés et corrigés
L'en-tête du titulaire débordait sur téléphone (flèches, badge, thème, avatar) et plusieurs écrans (clients, artistes, salles, événements) étaient élargis par leurs tableaux. Correctifs : en-tête compact sous 700 px, enfants de grille réductibles, tableaux défilants. Mesure refaite à 375 px fixes sur les 43 vues.
## 21. Ce qui est construit, ce qui ne l'est pas (28-10-2026)

**Construit et testé** (module `modules/billetterie`, ~130 capacités, 14 migrations, une trentaine de fichiers de bancs, six specs Playwright) :
- les bases (salles, formules, artistes, revendeurs, événements, types de billets, programme, affectations, invitations) avec leurs règles et leurs identifiants jamais réutilisés ;
- le registre des mouvements en écriture seule (centimes), les retraits (demande, validation, versement, refus) et la commission d'un revendeur calculée par le point d'évolution `commission` ;
- les ventes (stock et places retenues, prix toujours lu en base, codes promo, billets signés, remboursement, transfert, réémission), la caisse (réserve de numéros signés, vente hors ligne, clôture avec écart), le contrôle (portes, hors ligne, conflits) ;
- la boutique publique (page statique `boutique.html`, route dans le fragment) : programmation, panier chiffré, commande, suivi avec QR, impression, agenda, liste d'attente, reçu de don, textes légaux avec acceptation des conditions de vente ;
- les comptes clients par lien de connexion (sans mot de passe), l'export et la suppression différée des données ; les espaces revendeur et artiste, cloisonnés par compte ;
- les paiements : Stripe, PayPal et HelloAsso en pages hébergées, vérifiées chez le prestataire au retour (montant exact, ordre de CETTE commande), virement ;
- l'annulation et le report d'un événement (chiffres annoncés avant, remboursements en masse, commissions reprises), la liste d'attente (offres qui retiennent les places), les reçus fiscaux de don (association éligible, numéro continu, contenu figé), la rentabilité et la date de décision ;
- l'envoi réel des courriels (SMTP réglé, réessais, jamais sans activation) avec les billets en PDF joints ; le billet en PDF et son QR vectoriel (même dessin que l'écran, vérifié contre la bibliothèque de référence) ;
- le pont Dolibarr facultatif (file de rattrapage idempotente : tiers, facture validée, règlement, avoir, versement de commission, artiste comme adhérent avec son type de membre « Artiste »), le projet de l'événement dans le bureau (Projets, Tâches) ;
- l'interface V19 : dix menus, l'écran du titulaire, la caisse et le contrôle pour téléphone (avec file hors ligne), « Mon espace » du revendeur et de l'artiste.

**Écarts avec ce qui était prévu plus haut**
- Le pont Dolibarr vit dans la billetterie (son propre client d'API et ses réglages), pas dans le module `dolibarr` : une écriture comptable automatique part d'un moteur, qui n'a pas de compte et ne peut donc pas passer par les capacités d'un autre module. Le module `dolibarr` n'a pas été modifié.
- Les courriels partent d'un moteur, hors de l'exécuteur : le frein « envois » du noyau est consulté par `ctx.frein_actif`.
- Le profil du revendeur et de l'artiste (coordonnées, SIRET, IBAN vérifié par sa clé de contrôle et chiffré par le noyau, mode de facturation de la commission) vit dans la billetterie, pas dans le coffre ; sans IBAN, pas de retrait ; le titulaire ne voit que la fin de l'IBAN. L'auto-facture « par mandat » n'est qu'un choix enregistré : la facture fournisseur écrite dans Dolibarr au versement est la même dans les deux cas.
- Un compte client n'a pas d'historique de dons ni de factures PDF téléchargeables (le reçu fiscal et les billets le sont).

**Jamais éprouvé contre un service réel** (à essayer en bac à sable ou sur une entité de recette avant de s'y fier) : Stripe, PayPal, HelloAsso (le code suit leurs documentations publiques, les bancs utilisent des doublures), Dolibarr (en particulier l'avoir, et le mode de paiement par code), un vrai serveur SMTP, la lecture d'un QR par la caméra d'un vrai téléphone.

**Pas construit**
- Apple Wallet et Google Wallet (les réglages existent, les passes ne sont pas générés : signature avec un certificat ou une clé de service à fournir) ;
- le don dans Dolibarr (le module Dons n'a pas de route d'API : le reçu fiscal de la billetterie reste la voie) ;
- le lien de l'événement avec l'agenda et le répertoire du bureau (le projet et ses tâches le sont) ;
- les pages publiques de la boutique n'ont pas de sélecteur de langue ni de thème propre à l'organisateur (couleurs de la marque).

**À savoir en exploitation** : rien ne part par courriel tant que `courriels_actifs` n'est pas coché et le serveur réglé ; le pont Dolibarr ne fait rien tant que `dolibarr_actif`, l'adresse, la clé et les comptes bancaires ne sont pas réglés (l'onglet Argent › Comptabilité dit ce qui manque) ; les textes légaux sont des squelettes à faire relire.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
