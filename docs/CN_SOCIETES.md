<!-- ═════════════════════════════════════════════════════════════════
<!-- TITRE      : Sociétés et coffre -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Le socle société : tout compte appartient à une société, les fonctions sont des groupes attachés, le coffre isole chaque espace. -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═════════════════════════════════════════════════════════════════
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=9329ba ▼▼▼ -->
# Sociétés et coffre

Maquette de référence : `docs/CN_maquette-societe.html`. Écrans : `interface/CN_societes-ecran.js` (Paramètres › Société / Organisation) et `interface/CN_coffre-ecran.js` (Mon coffre-fort). Moteur : `noyau/CN_base.py`, `noyau/CN_droits.py`, `noyau/CN_identite.py`, `noyau/CN_executeur.py`, modules `societes`, `coffre`, `comptes`.

## Le socle (dans le noyau, toujours là)

- **Une société principale** (`1`) existe toujours et ne s'archive pas. Même avec une seule société, rien ne change pour l'utilisateur : mono-société = multi-société avec n = 1.
- **Tout compte appartient à une société** (colonne `comptes.societe`, jamais vide). Créer un compte sans société valide est refusé ; un agent invité est de la société de son invitant. Seul le superadministrateur range un compte dans une autre société que la sienne (`comptes.creer`) ou le change de société (`comptes.transferer`, réversible : ses fonctions de l'ancienne société tombent).
- **Les répertoires d'un utilisateur vivent dans le grand répertoire de sa société** : `<sociétés>/<société>/utilisateurs/<compte>/<module>` (`ctx.espace_compte()`), et `<sociétés>/<société>/commun/<module>` pour ce que toute la société partage (`ctx.espace_societe()`). Racine : `$CASSANDRA_SOCIETES`, `/var/cassandra/societes` par défaut. Les sites hébergés restent sous `/var/www` (FastPanel).
- **La société active d'un acte** (`ctx.societe`) est par fil d'exécution, comme le compte : celle du compte, ou celle qu'il choisit (en-tête `X-Societe`) parmi les siennes. Un compte n'agit jamais dans une société qui n'est pas la sienne ; le superadministrateur les administre toutes.
- **Des droits avec portée** : un groupe peut être attaché à une société (`droit_groupe_portee`). Une « fonction » est un tel groupe : ses droits ne valent que dans sa société, jamais ailleurs (`Droits.raison(compte, droit, societe)`). Sans société, seuls comptent les groupes valables partout : aucun droit existant ne change de sens.
- **Seul le superadministrateur** crée, archive, rouvre et administre l'ensemble des sociétés. L'administrateur d'une société ne gère que la sienne. Une société qui a encore des comptes ne s'archive pas. Plus d'une société demande le réglage `societes.multi` (posé par le module Multi-sociétés de l'App Store, ou à la main par le superadministrateur).

## Chaque société a ses modules, ses réglages et son écran

- **Modules par société** : un module « vital » (comptes, droits, sociétés, coffre, menus…) est ouvert dans toutes les sociétés ; les autres le sont là où le superadministrateur les ouvre (table `societe_modules`). Sans choix, un module est ouvert dans la société principale seulement. Un module fermé disparaît des menus (`ctx.manifestes_actifs()` filtre par société) et refuse ses gestes (« le module X n'est pas ouvert dans la société Y »). Rubrique Société › Modules.
- **Le sélecteur de société** (à côté du menu avatar, visible seulement pour qui en a plusieurs) met TOUTE l'application dans la société choisie : chaque appel envoie `X-Societe` (`CASS.societe`, y compris les routes de l'ancienne interface), le serveur vérifie que c'est bien l'une des siennes, et un accès retiré remet l'écran dans sa propre société. Chacun ne voit que les sociétés qui lui sont attribuées ; le superadministrateur les voit toutes.
- **Un utilisateur dans plusieurs sociétés sans être administrateur** : sa société est celle où ses documents sont rangés ; une fonction dans une autre société lui en ouvre l'accès (onglet « Sociétés » de sa fiche), et il n'y voit que ce que cette fonction permet.
- **Gestion des utilisateurs par l'administrateur d'une société** : les fonctions « titulaire » et « administrateur » reçoivent `comptes.gerer`, valable dans leur société seulement. Le module des comptes borne chaque geste (liste, lecture, création, modification, désactivation, suppression, corbeille, lien de mot de passe) aux comptes de la société ; seul le superadministrateur range ou transfère un compte dans une autre. L'administrateur de société ne règle pas les droits fins (matrice, groupes) : il donne des fonctions.
- **Réglages par société** : un réglage peut être de portée `societe` (une valeur par société, repli sur celle de l'instance). Déjà : personas et rôles des agents, billetterie (identité du titulaire, règles de vente), vue des contacts, Dolibarr, mot du rôle Telegram. Rubrique Société › Réglages ; écrire pour une société demande d'en être l'administrateur.
- **Partages** : on n'invite (projets, salon) qu'un compte qui a accès à la société active (`ctx.dans_ma_societe`).

## Les partages entre sociétés

- **La société primaire est propriétaire de l'instance** : seule elle règle le comportement de l'application (réglages d'instance, Danger, réglages des agents structurels, sécurité, observabilité, sauvegardes, gestion des modules : les modules « d'instance »). Les sociétés secondaires ont le desk, le métier et le parc, leurs agents dédiés et les services des agents structurels, jamais leurs réglages. L'administrateur d'une société ouvre et ferme les modules de SA société parmi ceux qui ne sont pas la base.
- **Un partage** va d'une société (source) à une autre (destinataire) pour un type d'objet : aujourd'hui « utilisateurs », tous ou ceux qu'on a choisis (tables `societe_partages`, `societe_partage_elements`). Seul le superadministrateur décide d'un partage et le retire ; chaque geste s'inscrit à l'historique et se défait.
- **Ce que ça change** : l'administrateur d'une société ne range une personne d'une autre société dans une fonction que si elle est partagée avec la sienne (avant, `societes.affecter` acceptait n'importe quel compte de l'instance). `societes.partageables` liste ces personnes ; les agents et comptes système ne se partagent jamais. Page Société › Partages.
- **Trois types de partage** : « utilisateurs » (à ranger dans une fonction), « contacts » (le carnet de la société, en lecture seule, sans les notes : `contacts.societe_*`, droits `societe_lire` pour tous les membres et `societe_ecrire` pour titulaire, administrateur, gestionnaire), « modeles » (l'habillage et les préfixes de devis et facture, recopiés par `societes.modeles_recopier`, jamais la banque ; se défait).
- **Une société modèle** : `societes.creer(modeles_de=…)` reprend l'habillage et les préfixes d'une société existante, comme `modules_de` reprend ses modules.
- **Un profil par société** (`societes.profil_lire` / `profil_regler`) : nom d'affichage, fonction, téléphone et adresse propres à chaque société où l'on travaille ; chacun règle le sien, l'administrateur celui des membres. La signature du courrier (réglage `courrier.signature_societe`) le reprend, puis ajoute les mentions de la société.
- **Les demandes de module** : une société secondaire n'installe rien sur l'instance ; son administrateur dépose une demande (module, motif, source), la société principale examine et installe par la logithèque (permissions montrées, consentement) puis attribue le module à la société demandeuse (`societes.module_demande_decider`).
- **Le fuseau de la société** règle la lecture des heures d'un flux iCalendar dans l'agenda (sinon celui du serveur).
- **À venir** : les en-têtes des Documents et les mentions des Sites (ces modules n'ont pas encore de fonction qui lise l'identité), les Notifications par fuseau.

## Le module Sociétés

- **La fiche** : onze rubriques validées par le serveur (SIREN et IBAN contrôlés, adresses, horaires, établissements, pièces, banque, conformité, habillage, responsables). Chaque modification est inscrite à l'historique et se défait ; l'IBAN n'y est jamais en clair et son affichage est journalisé.
- **Droits par domaine et par niveau** : huit domaines (fiche, établissements, horaires, pièces, banque, conformité, habillage, fonctions) × trois niveaux (voir, modifier, gérer). La banque et les fonctions sont sensibles.
- **Sept fonctions de départ** pour toute société (titulaire, administrateur, gestionnaire, comptable, conformité, membre, invité). On en crée d'autres en partant d'une existante. Personne n'accorde plus que ce qu'il a ; un seul titulaire, jamais zéro ; une fonction par personne et par société.
- **L'identité publique** (`societes.carte`) : ce que les modules lisent pour nommer la société (en-têtes, signatures, mentions). Jamais la banque ni les responsables. Les modules à brancher : Courrier, Agenda, Billetterie, Documents, Sites, Notifications, Itare.
- Créer une société ouvre ses fonctions et, par l'événement `societe.creee`, son espace de coffre.

## Le coffre : un espace par compte, un par société

- **Un compte ne voit que ses espaces** : le sien, et ceux de société où on l'a fait entrer. Rien d'autre n'existe pour lui : ni le nom, ni le nombre de secrets. Ni l'administrateur de l'instance, ni Cassandra, ni l'administrateur d'une société ne lit un espace dont il n'est pas membre. Un refus ne dit jamais si l'espace existe.
- **Rôles** dans un espace de société : administrateur du coffre (gère les accès, ne lit que les collections qu'on lui ouvre), membre, contributeur (écrit, ne relit que SES secrets), lecture seule. Collections par accès, date de fin facultative. Le dernier administrateur ne part pas et ne change pas de rôle.
- **Chaque secret garde son auteur** (table `vault_secrets`) : c'est ce qui rend possible le rôle contributeur. Le serveur Vaultwarden n'a qu'une session : l'isolement est dans le module.
- **Le départ d'un utilisateur** : un compte désactivé ou supprimé perd à l'instant tout accès aux espaces de société (événements `compte.desactive` et `compte.supprime`) ; son coffre personnel reste le sien. Le dernier administrateur d'un espace ne part pas : le journal du coffre dit « départ bloqué » et il faut en nommer un autre.
- Un espace de société peut être **externe** : ses secrets vivent sur le serveur Vaultwarden de la société (un `bw serve` déverrouillé), à l'adresse que lui donne l'administrateur de l'instance (http ou https, sans identifiants ni paramètres, jamais une adresse de métadonnées). Les rôles, collections et l'auteur par secret sont les mêmes ; seul le serveur change. S'il est injoignable, rien n'est lu ni écrit et rien ne se replie sur le serveur de l'instance. `coffre.status(espace)` dit son état.

## À faire, si on le garde

Les données propres à une société dans les modules d'entreprise (la billetterie en premier : une base par société est la piste la plus sûre, sans retoucher le code du module) ; 
Brancher les modules consommateurs sur `societes.carte` ; une valeur « société » sur les données de chaque module (Courrier, Agenda, Billetterie…) ; le module Multi-sociétés de l'App Store (sélecteur dans chaque écran, héritage du groupe, vue consolidée, opérations entre sociétés) ; la gestion des utilisateurs par l'administrateur de société (aujourd'hui l'instance seule crée les comptes d'une société).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
