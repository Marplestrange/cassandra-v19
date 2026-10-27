<!-- ═════════════════════════════════════════════════════════════════
<!-- TITRE      : Utilisateurs et groupes -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Utilisateurs et groupes : ce que l'écran fait, ce que le moteur garantit, ce qui reste à faire. -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═════════════════════════════════════════════════════════════════
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=000000 ▼▼▼ -->
# Utilisateurs et groupes

Maquette de référence : `docs/CN_maquette-utilisateurs.html`. Écran : `interface/CN_comptes-ecran.js`. Moteur : `noyau/CN_droits.py`, `noyau/CN_identite.py`, modules `droits` et `comptes`.

## Les pages (menu Paramètres › Institutionnel)

Utilisateurs : Nouvel utilisateur, Liste des utilisateurs. Groupes : Nouveau groupe, Liste des groupes, Matrice des droits, Qui peut… ?, Journal des droits.

## Ce que le moteur garantit

- **Tout utilisateur appartient à une société** (comme dans Dolibarr) : la liste montre sa société, le formulaire la demande (la sienne par défaut ; seul le superadministrateur en choisit une autre), un administrateur de société ne voit et n'administre que les comptes de la sienne. Voir `docs/CN_SOCIETES.md`.

- **Tout module déclare ses droits** (`[[droits]]`, au moins un) : le manifeste est refusé sinon, le module n'est pas installé. Les modules du dépôt déclarent `utiliser` (accordé à tous par défaut) et `administrer` (sensible) ; leurs capacités ordinaires portent `droit = "utiliser"`, donc refuser « utiliser » à un compte ou à un groupe coupe le module pour eux.
- **Ordre de décision** : administrateur → réglage du compte → agent invité (les droits de son invitant) → groupes (un refus l'emporte sur un octroi) → défaut → non. `droits.decisions` rend chaque droit avec son pourquoi ; `Droits.decisions_de` le calcule en quatre lectures et un test l'égale à `raison` droit par droit.
- **Appliquer d'un coup** (`droits.appliquer`) : accordé / refusé / hérité pour un compte ou un groupe, plus le statut d'administrateur ; un événement `droit.change`, de quoi défaire.
- **Anti-verrouillage** : le dernier administrateur humain actif ne perd pas son statut, n'est ni désactivé ni supprimé ; se retirer à soi-même le droit de gérer les droits demande `confirme`. Nommer un administrateur demande `droits.nommer_admin`.
- **Départ d'un utilisateur** (`comptes.desactiver`) : sessions fermées, mot de passe gardé, sites transférés au compte choisi, agents invités révoqués ou réattribués ; `comptes.reactiver` le rend. L'événement `compte.desactive` prévient les modules qui gardent des données par compte.
- **Voir comme** (`droits.voir_comme`) : la structure seulement (modules ouverts, nombre de droits), jamais un contenu : administrer un compte, ce n'est pas le lire.
- **Journal** (`droits.journal`) : qui a fait le changement, un utilisateur ou un agent (Cassandra, Itare). `prevenir` ouvre une notification pour la personne concernée.

## À faire, si on le garde

Groupes emboîtés, droits à durée limitée, second facteur exigé pour les droits sensibles, modèles de droits enregistrables, import et export en tableur. Transférer aussi les automatismes et les données d'un compte qui part : chaque module doit écouter `compte.desactive`.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
