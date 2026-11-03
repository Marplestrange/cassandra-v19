<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Routes V18 sans équivalent branché en V19 -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Le relevé, par domaine, des routes V18 encore à porter en V19. -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=c15ab0 ▼▼▼ -->
# Routes V18 sans équivalent branché en V19

Relevé du 02-11-2026 : les écrans repris de la V18 (`interface/CN_app.js`) appellent des routes `/api/…` que la couche de compatibilité (`interface/CN_compat.js` + `interface/routes/CN_*.js`) ne branche pas encore ; elles répondent 501 « pas encore porté ».
Règle de la maison : la V19 est une évolution, pas une régression. Chaque route ci-dessous est une fonctionnalité de la V18 à retrouver — par une capacité d'un module (nouvelle si besoin), puis la route qui la branche.

Comment relever la liste : `python` sur `interface/CN_app.js` (toutes les chaînes `/api/…`) moins les chaînes présentes dans `interface/routes/*.js` et `CN_compat.js`.

## Projets (espace de travail) — 44 routes : toutes branchées (03-11-2026)

Aucune ne répond plus 501 : elles sont dans `interface/routes/CN_projets_pj.js`, sur les capacités du module `projets` (`CN_coffre.py`, `CN_fil.py`, migration `CN_002_atelier.sql`), de la GED, des notes et du courrier. Bancs : `tests/CN_test_projets_atelier.py`. Détail du module : `modules/projets/CN_LISEZ-MOI.md`.

Branchées en entier : atelier (fiche, importer, note, sources, verser), cadrage (proposer, appliquer), dossier de fichiers (lister, lire, écrire, versions, déplacer, retirer, remettre, index, fichier, état), commentaires, fil (publier, relire, trancher, avis), courrier rangé au projet (lister, ranger, pièce), présence, suites proposées, choix du dossier (parcourir, créer, corbeille, local).

Branchées avec une réserve, à reprendre :
- `/api/pj/dossier/*` et le dossier de fichiers : seuls les **dépôts de ce serveur** sont portés (`local:/nom`, dans l'espace du propriétaire). Les machines distantes de la V18 (`machine:/chemin` par SFTP sur la flotte) ne le sont pas : la flotte ne donne aucun canal de fichiers.
- `/api/pj/nav/aller`, `retour`, `fermer`, `clipper` : le navigateur partagé **lit** les pages (module web, texte) ; `/api/pj/nav/image`, `clic`, `defiler`, `texte` répondent `{ok:false}` avec la raison : la V18 pilotait un Chromium par tube derrière un relais anti-réseau privé, que la V19 n'a pas.
- @Itare dans le fil ou un commentaire : l'événement `projet.itare` est émis, mais le module des agents ne l'écoute pas encore (aucune réponse inventée). Les suites proposées (`/proposer`) sont calculées sur les faits du projet, sans modèle ; la relecture quotidienne d'Itare n'est pas reprise.
- Non repris, hors des 44 routes : le tableau propre à la nature « livre » (chapitres, mots), les droits d'Itare par projet.

## Hébergement et système — 57 routes : toutes branchées (03-11-2026)

Aucune ne répond plus 501 : elles sont dans `CN_systeme.js`, `CN_fastpanel.js`, `CN_sites.js`, `CN_sauvegardes.js`, `CN_securite.js`, `CN_flotte.js` et `CN_crons.js`. Le banc `tests/CN_test_hebergement_systeme.py` garde la table.

Branchées pour de bon, sur une capacité :
- les tableaux de la machine (`/api/ports`, `sessions`, `failed`, `oom`, `docker`, `ssl`, `tailscale`, `fail2ban`, `remotes`, `dashboard`, `system`) : le collecteur du Sensorium (`sensorium.entite`) ; un collecteur muet rend une liste vide, jamais des chiffres inventés ;
- les gestes de la machine, chacun avec sa preuve et son retour : `securite.oom_acquitter` (retour : retirer les signatures), `securite.unites_reinitialiser` et `securite.session_fermer` (sans retour, dit), `securite.systeme_geste` (recharger nginx après `nginx -t`, relancer Ollama ou le noyau, table fermée de trois services), `securite.journal_service` (lecture, table fermée), `sensorium.redemarrer` (le collecteur) ;
- `/api/fp/*` : `api/test`, `api/creds` (aux réglages, secrets), `domain/context`, `domain/attach` (un lien de la fiche du site), `db/users`, `db/delete` (`fastpanel.base_supprimer`, sans retour, dit), `user/ssh` (`fastpanel.utilisateur_cles`), `users/link` (`comptes.modifier`), `scans/targets` (`fastpanel.scans_cibles`) ;
- `/api/site/copies` et `restaurer` (`fastpanel.copies_du_plan`, `fastpanel.copie_restaurer` : le propriétaire, ou l'administrateur avec l'accord du propriétaire), `/api/site/rapport` (composé de l'historique de la sonde et des copies du compte), `/api/sites/act` (vérifier, renouveler le certificat) ;
- `/api/sauv/purger`, `verifier`, `restaurer` (`sauvegardes.purger`, `verifier`, `restaurer` : rclone par le courtier ; la rotation ne touche que les dossiers datés AAAA-MM-JJ, la restauration est à blanc et « à côté » par défaut) ;
- `/api/securite/direct`, `defaire`, `audit/rediger` (le modèle de l'administrateur rédige l'audit en arrière-plan) ; `/api/crons/suggest` ; `/api/multiserver/aggregate` et `resolve_quickconnect` (`flotte.quickconnect`) ; `/api/pf/scan`, `scans`, `scan/note` (la santé des modules relue à l'instant : les détecteurs de la V19 tournent en continu) ; `/api/upload` (texte et images ; le PDF et le bureautique attendent un extracteur).

Dites telles quelles (la route répond, avec la raison — jamais un 501) :
- `/api/exec`, `/api/exec/stream`, `/api/rollback` : la console de commandes libres n'existe plus en V19 (aucun shell libre ; chaque opération root est une commande nommée du courtier) ; sans commande libre, aucun instantané de fichier à restaurer ;
- `/api/system/wipe` : le reset total n'est pas un bouton en V19 ; le retrait propre est `CN_desinstaller.sh`, à la main ;
- `/api/fp/act`, `/api/fp/stats` : le catalogue d'actions libres (mogwai) est remplacé par un geste nommé chacun ; les statistiques du panneau par Historique ;
- `/api/fp/scans/run`, `configure`, `reports`, `report`, `/api/site/scan`, `/api/site/sauvegarde`, `/api/fp/websocket/apply`, `/api/fp/service/diagnose` (journal et vérification de configuration), `/api/site/thumb`, `/api/sites/act` (redémarrer, journaux) : ils demandent la commande `mogwai` ou des fichiers de root ; le courtier du module `fastpanel` n'a pas encore ces commandes. Reste à faire : une commande racine `mogwai` à table fermée (scan, backup run), puis ces routes.
- `/api/securite/direct` : bannir une adresse ou un pays, la liste blanche, fermer un chemin d'un site, freiner un robot — pas encore portés (pare-feu du noyau et nginx) ; débannir, arrêter un service et lancer un outil le sont.

## Bureau d'Itare, messagerie et outils — 127 routes

Modules V19 proches : notes, canaux, telegram, canvas, coffre, notifications, journal, proactif, comptes. Fonctions : contacts (CardDAV, photos, documents), laboratoire, messages programmés, Telegram, Canva, carnet, préférences de notification, coffre personnel, agenda externe.

**Porté dans cette section** (la V19 y répond autrement que par 501) : le carnet (`/api/carnet/*`, par le module notes), les réglages de la cloche (`/api/notif/*` : préférences, politique de canaux, sourdines, essai, webhook chiffré ; notifications 0.3.0),
Mon coffre-fort (`/api/vault/mine/*` ; coffre 0.2.0 : fiches typées, TOTP, historique chiffré), les messages en cours et programmés (`/api/msg/*` ; module messages 0.1.0, courrier 0.1.4 `envoyer_programme`),
les portraits, documents et vie privée d'une fiche du carnet (`/api/itare/contact/photos|documents|privacy` ; contacts 0.3.4, GED 0.1.2).
Honnêtement, **ce qui reste est ci-dessous**. Limites connues de ce qui est porté : les canaux de la cloche (courriel, Telegram, webhook) n'envoient pas encore (la politique est enregistrée pour eux, l'essai le dit) ; `/api/notif/agir` répond qu'aucune action n'est attachée à une notification ;
les fiches du coffre sont des documents JSON rangés dans la note sécurisée (l'application Bitwarden ne les voit pas comme des identifiants) et il n'y a plus de clé d'API personnelle ; `bcc` d'un message est enregistré mais le courrier ne le pose pas (comme en V18) ; `/api/msg/relire` et `/api/msg/fait` (relecture et faits relevés par un modèle) restent à porter.

- `/api/autonomie` (1) : `/recit`
- `/api/canva` (6) : `/brancher`, `/creer`, `/debrancher`, `/designs`, `/etat`, `/reconcilier`
- `/api/canvas` (14) : `/amorcer`, `/ext/apercu`, `/ext/etat`, `/ext/lister`, `/geste`, `/importer`, `/itare`, `/portes`, `/registre`, `/relier`, `/sorties`, `/sortir`, `/vivante/poser`, `/vivante/rejouer`
- `/api/comptes` (2) : `/dossier/supprimer`, `/dossiers`
- `/api/conv` (1) : `/ecrire`
- `/api/iso` (1) : `/orphelines`
- `/api/ita` (7) : `/basculer`, `/commencer`, `/delier`, `/ident`, `/reconnaitre`, `/relancer`, `/valider`
- `/api/itare` (35) : `/bureau/suggestions`, `/contact/autolink`, `/contact/carddav`, `/contact/carddav/delier`, `/contact/carddav/importer`, `/contact/carddav/relier`, `/contact/propositions`, `/contact/site/apercu`, `/contact/site/importer`, `/contact/sites`, `/draft/compose`, `/event/prep`, `/mail/avatars`, `/mail/avatars/oublier`, `/mail/chercher`, `/mail/link`, `/mail/media`, `/mail/media/index`, `/mail/media/texte`, `/mail/piece/ged`, `/mail/projet/suggerer`, `/mail/relance`, `/mail/rule/delete`, `/mail/rule/save`, `/mail/rule/suggest`, `/mail/rules`, `/mail/rules/apply`, `/mail/schedule`, `/mail/summary`, `/mail/thread`, `/project/ask`, `/project/search`, `/project/suggest`, `/task/creneau`, `/task/from`
- `/api/journal` (5) : `/act`, `/anomalies`, `/postmortem`, `/postmortem/save`, `/purge`
- `/api/lab` (14) : `/assign`, `/chat`, `/contexte`, `/delete`, `/etabli`, `/modes`, `/piece`, `/piece/ged`, `/piece/oter`, `/pieces`, `/pull`, `/pull_status`, `/setmodel`, `/sources`
- `/api/liens` (2) : ``, `/graphe`
- `/api/mail` (3) : `/recap_now`, `/settings`, `/test`
- `/api/me` (9) : `/agenda/detach`, `/agenda/save`, `/deverrouiller`, `/history`, `/photo`, `/telegram/brancher`, `/telegram/cible`, `/telegram/detacher`, `/telegram/envoyer`
- `/api/modeles` (1) : `/migrer`
- `/api/msg` (2) : `/fait`, `/relire`
- `/api/notes` (1) : `/tache/rappel`
- `/api/notif` (1) : `/agir`
- `/api/proactive` (3) : `/act`, `/investigate`, `/snooze`
- `/api/ranger` (1) : ``
- `/api/rappel` (1) : `/comprendre`
- `/api/reglages` (1) : `/veille/set`
- `/api/settings` (5) : `/api-key`, `/password`, `/relecteur`, `/relecteur/essai`, `/vision`
- `/api/telegram` (2) : `/adopter`, `/proposes`
- `/api/tgc` (9) : `/commencer`, `/delier`, `/dire`, `/ident`, `/importer`, `/lire`, `/piece`, `/valider`, `/visage`

## Évolution et GED distante — 41 routes

Modules V19 proches : evolution, ged. Fonctions : pilotage de l'évolution (cadence, pièces, souhaits, retour arrière), distants de la GED, aperçus, extraction, dédoublonnage, montages.

- `/api/evolution` (20) : `/cadence`, `/comptes`, `/journal`, `/lecon`, `/mesures`, `/moteurs`, `/pause`, `/piece`, `/piece/appliquer`, `/piece/refuser`, `/pieces`, `/regime`, `/rollback`, `/run_now`, `/status`, `/toxique`, `/unfreeze`, `/wish`, `/wish/delete`, `/wishlist`
- `/api/ged` (21) : `/apercu`, `/apercu/texte`, `/corbeille/vider`, `/dedoublonner`, `/extraire`, `/montage/add`, `/montage/remove`, `/op`, `/piece/apercu`, `/piece/voir`, `/preparer`, `/recettes`, `/remote/coller`, `/remote/create`, `/remote/delete`, `/remote/oauth`, `/remote/oauth/finir`, `/remote/tester`, `/remote/types`, `/scanner`, `/texte`

<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
