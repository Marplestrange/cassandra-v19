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
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼ -->
# Sociétés et coffre

Maquette de référence : `docs/CN_maquette-societe.html`. Écrans : `interface/CN_societes-ecran.js` (Paramètres › Société / Organisation) et `interface/CN_coffre-ecran.js` (Mon coffre-fort). Moteur : `noyau/CN_base.py`, `noyau/CN_droits.py`, `noyau/CN_identite.py`, `noyau/CN_executeur.py`, modules `societes`, `coffre`, `comptes`.

## Le socle (dans le noyau, toujours là)

- **Une société principale** (`1`) existe toujours et ne s'archive pas. Même avec une seule société, rien ne change pour l'utilisateur : mono-société = multi-société avec n = 1.
- **Tout compte appartient à une société** (colonne `comptes.societe`, jamais vide, comme dans Dolibarr). Créer un compte sans société valide est refusé ; un agent invité est de la société de son invitant. Seul le superadministrateur range un compte dans une autre société que la sienne (`comptes.creer`) ou le change de société (`comptes.transferer`, réversible : ses fonctions de l'ancienne société tombent).
- **Les répertoires d'un utilisateur vivent dans le grand répertoire de sa société** : `<sociétés>/<société>/utilisateurs/<compte>/<module>` (`ctx.espace_compte()`), et `<sociétés>/<société>/commun/<module>` pour ce que toute la société partage (`ctx.espace_societe()`). Racine : `$CASSANDRA_SOCIETES`, `/var/cassandra/societes` par défaut. Les sites hébergés restent sous `/var/www` (FastPanel).
- **La société active d'un acte** (`ctx.societe`) est par fil d'exécution, comme le compte : celle du compte, ou celle qu'il choisit (en-tête `X-Societe`) parmi les siennes. Un compte n'agit jamais dans une société qui n'est pas la sienne ; le superadministrateur les administre toutes.
- **Des droits avec portée** : un groupe peut être attaché à une société (`droit_groupe_portee`). Une « fonction » est un tel groupe : ses droits ne valent que dans sa société, jamais ailleurs (`Droits.raison(compte, droit, societe)`). Sans société, seuls comptent les groupes valables partout : aucun droit existant ne change de sens.
- **Seul le superadministrateur** crée, archive, rouvre et administre l'ensemble des sociétés. L'administrateur d'une société ne gère que la sienne. Une société qui a encore des comptes ne s'archive pas. Plus d'une société demande le réglage `societes.multi` (posé par le module Multi-sociétés de l'App Store, ou à la main par le superadministrateur).

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
- Un coffre peut être déclaré **externe** (adresse seulement) ; son branchement n'est pas encore disponible : tant qu'il ne l'est pas, rien n'y est lu ni écrit.

## À faire, si on le garde

Brancher les modules consommateurs sur `societes.carte` ; une valeur « société » sur les données de chaque module (Courrier, Agenda, Billetterie…) ; le branchement d'un coffre externe ; le départ d'un utilisateur dans le coffre (retirer ses accès à l'événement `compte.desactive`) ; le module Multi-sociétés de l'App Store (sélecteur dans chaque écran, héritage du groupe, vue consolidée, opérations entre sociétés) ; la gestion des utilisateurs par l'administrateur de société (aujourd'hui l'instance seule crée les comptes d'une société).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
