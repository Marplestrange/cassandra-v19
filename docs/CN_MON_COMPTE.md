<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Mon compte (V19) -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Mon compte (V19) -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=38bdd1 ▼▼▼ -->
# Mon compte (V19)

L'écran personnel d'un compte : six pages, une fiche, un portrait. La maquette validée est `docs/CN_maquette-mon-compte.html` (sa page « Mise à niveau » dit pourquoi chaque choix).

## Où est quoi

| Quoi | Où |
|---|---|
| La fiche : champs, longueurs, conversions | `noyau/CN_fiche.py` |
| La table `comptes_fiche`, le portrait propre `comptes_portrait` | `noyau/CN_base.py` |
| Lire, écrire, migrer la fiche ; nom affiché unique | `noyau/CN_identite.py` (`fiche`, `fiche_ecrire`, `migrer_fiches`, `nom_affiche`) |
| Les capacités du compte (`moi`, `lire`, `modifier_moi`, `fiche_modifier`, `portrait*`, `mon_journal`) | `modules/comptes` |
| La fiche côté Dolibarr (liste blanche, lien, comparaison, envoi, photo) | `modules/dolibarr` (`fiche_*`, `portrait`) |
| L'avatar de FastPanel | `modules/fastpanel` (`avatar`) |
| Les six pages | `interface/CN_moncompte-ecran.js`, appelé par `interface/CN_comptes-ecran.js` pour les écrans `mc_*` |

## Les règles qui tiennent la fiche

- **Refuser, jamais couper.** Une valeur plus longue que la colonne de Dolibarr (nom et prénom 50, fonction 128, téléphones 30, code postal 25, adresse 255) est refusée avec le champ nommé.
- **Les anciens champs sont dérivés.** `display_name`, `role_label`, `contact_email`, `phone` et `lang` de la table `comptes` restent écrits, calculés depuis la fiche : ce qui les lit encore n'est pas cassé. Pour afficher un nom, passer par `Identite.nom_affiche`.
- **Un agent ou un compte système n'a pas de fiche.**
- **Les coordonnées privées** (courriel et mobile personnels, naissance, adresse) d'un autre compte ne se voient qu'avec le droit `comptes.fiche_voir_perso` ; chaque consultation de la fiche d'un autre s'inscrit au journal de son titulaire (`compte.fiche_vue`). Modifier la fiche d'un autre demande `comptes.fiche_modifier_autres`.
- **Dolibarr est facultatif.** Sans son module, l'écran n'en dit rien. Le lien est un objet du registre du module (`dolibarr_lien`, id `compte:utilisateur:moi`) ; il ne se pose que si l'utilisateur de Dolibarr porte l'adresse du compte. Seuls les champs de la liste blanche (`FICHE_BLANCHE`) passent ; mots de passe, clés, salaires, numéro de sécurité sociale, notes privées ne passent jamais.
- **Le portrait a un seul résolveur** (`comptes.portrait`) : la source choisie, puis le repli (image propre, Dolibarr, FastPanel), puis les initiales. Une image téléversée n'est jamais écrasée par une source externe.

## La sécurité de la session

Voir `CHANGELOG.md` : mot de passe qui ferme les autres sessions, dix sessions au plus, nouvel appareil, Origin, cookie `__Host-`, second facteur des administrateurs par défaut, et `confirmer = true` dans le manifeste d'une capacité pour redemander le mot de passe d'un geste sensible.

## Ce que la suite a ajouté

- **Qui voit ma fiche** : quatre groupes de champs (identité, professionnel, présentation, privé) et deux publics (collègues, administrateurs). Le privé demande l'ouverture par son titulaire ET le droit `comptes.fiche_voir_perso`. La journalisation des accès d'autrui se coupe.
- **Identités liées** : pseudo FastPanel et utilisateur système (bash). Seul un administrateur les pose ; le bash n'est lié qu'à un administrateur, jamais au superadministrateur (le sien se pose à sa création). Carte dans Branchements, champ dans Utilisateurs.
- **Dolibarr** : « qui l'emporte » par groupe (état civil, coordonnées, présentation) ; si les deux côtés ont changé depuis le dernier accord, on demande quel que soit le réglage. Le tiers (`socid`) et le contact (`contact_id`) liés se lisent. La carte de la clé de mandat (administrateur) pose l'adresse et la clé et les vérifie par de vrais appels.
- **Appareils** : « se souvenir de cet appareil » 30 jours (le mot de passe et le second facteur restent demandés) ; un appareil non revu depuis 30 jours et dont on ne s'est pas souvenu redevient « nouveau ». Réglage `comptes.admin_nouvel_appareil` : « alerter » (défaut) ou « bloquer » jusqu'à l'approbation d'une session déjà ouverte — jamais pour le superadministrateur.
- **À faire sur mon compte** : chaque module déclare ses attentes dans son manifeste (`[[attentes]]`, une lecture qui rend faux ou `{titre, texte}`) ; le noyau les rassemble (`comptes.mes_attentes`).
- **Portrait Telegram** : la photo de profil de l'interlocuteur du robot du compte (`telegram.portrait`).

## Ce qui n'est pas encore là

- L'essai contre un vrai Dolibarr (les bancs utilisent un faux serveur) ; le rattachement du `contact_id` à la fiche du module Contacts.
- Les cartes « Mes modèles », « Voix » et « Mon affichage » détaillées de la maquette : les modules qui déclarent des réglages de portée « compte » apparaissent déjà dans Branchements, mais pas ces trois cartes à gestes.
- Le nettoyage des 27 lignes de `interface/CN_app.js` qui servent encore l'ancienne rubrique « Mon compte » des Paramètres (les liens « Réglage agenda » et « Réglage Mail » s'y ouvrent toujours).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
