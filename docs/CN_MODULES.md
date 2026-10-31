<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Les modules -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Les modules -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=83c2dc ▼▼▼ -->
# Les modules

Ce catalogue est **généré** depuis les manifestes (`python outils/CN_catalogue_modules.py`) ; un banc vérifie qu'il est à jour. Chaque module est un dossier
indépendant de `modules/` : son manifeste déclare ses droits, ses capacités, ses menus et ses permissions.

- **vital** : ouvert dans toutes les sociétés, jamais désactivable ; **important** et **optionnel** : ouverts société par société.
- **instance** : n'existe que dans la société principale (sécurité, observabilité, sauvegardes, gestion des modules…).
- **base par société** : les données du module sont séparées société par société.

47 modules.

## Socle

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `affichage` — Affichage | vital | Assemble le thème et la mise en page que les modules actifs déclarent : tuiles, gabarits, touches de couleur, contraste vérifié, personnalisation par compte. |
| `menus` — Menus | vital | Assemble, à chaud, l'arbre de navigation que les modules actifs déclarent : familles, ordre, rôles, compteurs, personnalisation par compte. |
| `modules` — Modules | vital · instance | La gestion des modules : ce qui est installé, actif ou à installer, ce qui dépend de quoi, et le geste d'activer ou de désactiver. |
| `reglages` — Réglages | vital | Les réglages des modules : chacun déclare les siens (type, défaut, portée), ils s'écrivent un par un avec leur historique, les secrets ne sortent jamais en clair. |
| `societes` — Sociétés | vital | Les sociétés de l'instance et la fiche de chacune (identité, siège, horaires, établissements, pièces, banque, conformité, habillage, responsables). |
| `jour` — Aujourd'hui | important | Le bureau du jour : ce qui brûle, ce qui est à regarder, ce qui tombe aujourd'hui. |
| `themes` — Thèmes de la maison | optionnel | Deux thèmes complets pour l'interface, livrés comme n'importe quel module : Ardoise (sombre, bleu ardoise et cuivre) et Papier (clair chaud, encre indigo). |

## Sécurité

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `coffre` — Coffre fort | vital | Le coffre Vaultwarden : le magasin de secrets de Cassandra (statut, liste des noms sans jamais les valeurs, lecture, écriture réversible, retrait). |
| `comptes` — Comptes | vital | Les comptes et la preuve qu'on en est : identifiant (une adresse e-mail), mot de passe (règles de la V18, scrypt salé), sessions, jetons de mise en place du mot de passe. |
| `droits` — Droits | vital | Qui, parmi les comptes, peut utiliser quoi : les modules déclarent leurs droits, on les attribue à des comptes et à des groupes, l'exécuteur les vérifie. |
| `certificats` — Certificats | important | Surveille l'expiration des certificats TLS réellement servis (port 443), garde le registre des émissions Let's Encrypt (cinq par semaine et par domaine) et signale les… |
| `securite` — Sécurité | important · instance | La sécurité : les gestes (bannir une adresse, fermer un chemin, faire tourner une clé…), le journal de ce qui a été fait, et les audits. |
| `urgence` — Urgence | important · instance | Les gestes d'urgence : geler l'autonomie des agents (ils observent, n'agissent plus), couper les envois (rien ne sort plus de la maison), fermer les sessions des autres,… |
| `webauthn` — Clé de sécurité | important | Les clés de sécurité WebAuthn des comptes : enregistrer et retirer une clé, l'exiger pour entrer (second facteur, avec huit codes de secours), ou entrer sans mot de… |

## Supervision

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `proactif` — Proactivité | important · instance | La Proactivité : l'autonomie par palier (observer, proposer, maîtrise, raconter), le savoir-faire mesuré (un geste devient éprouvé à dix réussites, retombe à deux échecs… |
| `sauvegardes` — Sauvegardes | important · instance | Les plans de sauvegarde : une portée décide du moteur (un site ou une base passe par FastPanel, le reste par rclone), la rotation par dossiers datés, la vérification par… |
| `sensorium` — Sensorium | important · instance | Les sens de Cassandra. |
| `vue` — Vue d'ensemble | important | La vue d'ensemble : un verdict (rien ne demande un geste / à regarder / en panne), des compteurs, et ce qui demande un geste — composés à partir des modules de… |
| `journal` — Le Journal | optionnel · instance | Le journal des agents (les consultations entre les trois rôles — claude, itare, cassandra — inscrites avec la question et la réponse) et le lecteur unifié des journaux :… |
| `mesures` — Mesures | optionnel · instance | L'historique : chaque module déclare ses mesures ([[mesures]]) ; ce module en tire les courbes par période, l'habitude (ce qui est normal ce jour-là à cette heure), les… |

## Hébergement

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `fastpanel` — FastPanel | important | Le pont vers le panneau d'hébergement FastPanel. |
| `sites` — Sites | important | Les sites web que Cassandra suit : ceux d'un compte (déclarés, attribués, ou inscrits dans sa fiche de compte), ceux du panneau qui appartiennent au compte du panneau… |

## Réseau

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `flotte` — Flotte | important | Le parc de machines : le registre déclaré, Tailscale et les relevés SSH côte à côte, la présence mesurée, la disponibilité, le verdict d'ouverture, les commandes nommées… |
| `dns` — Zones DNS | optionnel | Relève les zones suivies auprès de leur serveur de noms faisant foi, garde une référence versionnée (rien n'est écrasé), signale la dérive, l'adresse publique qui a… |
| `web` — Web | optionnel | La porte du dehors : chercher sur le web (par un moteur compatible SearXNG que l'administrateur configure) et lire une page en texte seul. |

## Système

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `planifie` — Tâches planifiées | important | Tout ce qui tourne tout seul sur la machine, et est-ce que ça va : les tâches de Cassandra et celles du système (crontabs, cron.d) fusionnées, l'état de chacune (cassée,… |

## Agents

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `agents` — Agents | vital | Cassandra (la machine) et Itare (le bureau) en conversation : un tour lit la mémoire, raisonne par un modèle, appelle des OUTILS DÉRIVÉS DU CATALOGUE (rien à écrire à la… |
| `modeles` — Modèles | vital | Le registre des modèles de langage : un modèle se déclare une fois (fournisseur, nom, adresse, clé chiffrée), les rôles de la maison et les comptes y puisent. |
| `memoire` — Mémoire | important · instance | La mémoire de Cassandra : un souvenir est un fait daté, prouvé, propriétaire, corrigeable d'une phrase. |
| `bibliotheque` — Bibliothèque | optionnel | La connaissance d'Amizo : des fiches sourcées (adresse, date de lecture) découpées en passages, sur deux étagères (interne : espaces partagés de la société ; externe :… |

## Communication

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `notifications` — Notifications | vital | Le Centre de notifications : ce qui mérite l'attention de quelqu'un. |
| `courrier` — Courrier | important | La boîte mail de chaque compte, par IMAP : dossiers, messages (cache des en-têtes et du texte des trois derniers mois), lecture avec un HTML nettoyé par liste blanche… |

## Canaux

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `canaux` — Canaux | optionnel | Les canaux Telegram : l'état du client et le miroir (porter ses conversations sur Telegram, par compte). |
| `telegram` — Robot Telegram | optionnel | Le robot Telegram de chaque compte : il porte les notifications de CE compte vers SON téléphone, et ne lit rien de ce qu'on lui écrit (le premier message sert seulement… |

## Échanges

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `mandats` — Mandats | important | Les mandats d'envoi : l'autorisation d'envoyer, avec ses bornes (à qui, quand, combien, sous quel contrôle). |
| `salon` — Le Salon | optionnel | Des fils de travail où les personnes et les agents se parlent : un message a un auteur, des destinataires et un corps ; adresser un agent résident (Cassandra, Itare) le… |
| `voix` — Voix | optionnel | La voix : ce qui est installé (l'écoute par faster-whisper, la parole par piper), le catalogue des voix, et le choix par compte. |

## Gestion

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `agenda` — Agenda | important | L'agenda d'un compte : événements (récurrences, alarme, liens vers ce qu'ils concernent, journal, préparation), rappels, import et export iCalendar, lecture de son… |
| `canvas` — Canvas | optionnel | Le canvas de notes : les départs (des gabarits de note), les gestes de rédaction, et le plan (les cartes et les flèches d'une note). |
| `contacts` — Carnet d'adresses | optionnel · base par société | Le carnet de chaque compte : fiches (adresses, téléphones, société, notes, étiquettes, favori), dossiers, archive, corbeille de trente jours, rattachements aux projets,… |
| `ged` — Documents | optionnel | La GED : les documents d'un compte, classés par sources (locales, avec cloisonnement par propriétaire), un index, des règles de classement, le dépôt, la fiche, l'aperçu… |
| `notes` — Notes | optionnel | Le carnet de notes d'un compte : numéros stables (N-0007, jamais réattribués), renvois [[N-0007]] et [[nature:ref]] avec rétro-liens, dossiers à deux niveaux,… |
| `projets` — Projets | optionnel | Les projets d'un compte : fiche (objectif, périmètre, critères de réussite), phases, jalons, décisions, journal daté, plan de référence qui rend visible le glissement,… |
| `taches` — Tâches | optionnel | Les tâches d'un compte : statut, échéance, priorité, sous-tâches, récurrence (l'occurrence suivante repart de l'échéance précédente), avancement, responsable (soi-même,… |

## Finance

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `billetterie` — Billetterie | optionnel · base par société | La billetterie : événements, salles, artistes, revendeurs et formules de rémunération, billets, caisse, contrôle à l'entrée, boutique publique et portefeuille des… |
| `dolibarr` — Dolibarr | optionnel | Le pont vers une instance Dolibarr, par son API REST. |

## Évolution

| Module | Importance | Ce qu'il fait |
|---|---|---|
| `evolution` — Évolution | optionnel · instance | Le pilotage de l'évolution : quels points d'évolution méritent d'être optimisés (par ce qu'ils coûtent réellement), proposer une variante (Orfan ou un modèle) que le… |
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
