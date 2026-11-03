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
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=70a816 ▼▼▼ -->
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

## Hébergement et système — 57 routes

Modules V19 proches : fastpanel, sites, sauvegardes, securite, mesures, flotte. Fonctions : panneau, bases, FTP, mail, DNS, sauvegardes (purger, restaurer, vérifier), analyses, redémarrages, journal des échecs, shell.

- `/api/crons` (1) : `/suggest`
- `/api/dashboard` (1) : ``
- `/api/docker` (1) : ``
- `/api/exec` (2) : ``, `/stream`
- `/api/fail2ban` (1) : ``
- `/api/failed` (2) : ``, `/reset`
- `/api/fp` (17) : `/act`, `/api/creds`, `/api/test`, `/db/delete`, `/db/users`, `/domain/attach`, `/domain/context`, `/scans/configure`, `/scans/report`, `/scans/reports`, `/scans/run`, `/scans/targets`, `/service/diagnose`, `/stats`, `/user/ssh`, `/users/link`, `/websocket/apply`
- `/api/multiserver` (2) : `/aggregate`, `/resolve_quickconnect`
- `/api/oom` (2) : ``, `/clear`
- `/api/pf` (3) : `/scan`, `/scan/note`, `/scans`
- `/api/ports` (1) : ``
- `/api/remotes` (1) : ``
- `/api/rollback` (1) : ``
- `/api/sauv` (2) : `/purger`, `/restaurer`
- `/api/securite` (3) : `/audit/rediger`, `/defaire`, `/direct`
- `/api/service` (2) : `/restart/agent`, `/restart/collector`
- `/api/session` (1) : `/kill`
- `/api/sessions` (1) : ``
- `/api/site` (6) : `/copies`, `/rapport`, `/restaurer`, `/sauvegarde`, `/scan`, `/thumb`
- `/api/sites` (1) : `/act`
- `/api/ssl` (1) : ``
- `/api/system` (3) : ``, `/geste`, `/wipe`
- `/api/tailscale` (1) : ``
- `/api/upload` (1) : ``

## Bureau d'Itare, messagerie et outils — 170 routes

Modules V19 proches : notes, canaux, telegram, canvas, coffre, notifications, journal, proactif, comptes. Fonctions : contacts (CardDAV, photos, documents), laboratoire, messages programmés, Telegram, Canva, carnet, préférences de notification, coffre personnel, agenda externe.

- `/api/autonomie` (1) : `/recit`
- `/api/canva` (6) : `/brancher`, `/creer`, `/debrancher`, `/designs`, `/etat`, `/reconcilier`
- `/api/canvas` (14) : `/amorcer`, `/ext/apercu`, `/ext/etat`, `/ext/lister`, `/geste`, `/importer`, `/itare`, `/portes`, `/registre`, `/relier`, `/sorties`, `/sortir`, `/vivante/poser`, `/vivante/rejouer`
- `/api/carnet` (15) : `/detacher`, `/etat`, `/fiche`, `/groupes`, `/lister`, `/migrer`, `/postit`, `/postit/reprendre`, `/ranger`, `/rattacher`, `/relire`, `/tache`, `/taches`, `/taches/projeter`, `/taches/reprendre`
- `/api/comptes` (2) : `/dossier/supprimer`, `/dossiers`
- `/api/conv` (1) : `/ecrire`
- `/api/iso` (1) : `/orphelines`
- `/api/ita` (7) : `/basculer`, `/commencer`, `/delier`, `/ident`, `/reconnaitre`, `/relancer`, `/valider`
- `/api/itare` (38) : `/bureau/suggestions`, `/contact/autolink`, `/contact/carddav`, `/contact/carddav/delier`, `/contact/carddav/importer`, `/contact/carddav/relier`, `/contact/documents`, `/contact/photos`, `/contact/privacy`, `/contact/propositions`, `/contact/site/apercu`, `/contact/site/importer`, `/contact/sites`, `/draft/compose`, `/event/prep`, `/mail/avatars`, `/mail/avatars/oublier`, `/mail/chercher`, `/mail/link`, `/mail/media`, `/mail/media/index`, `/mail/media/texte`, `/mail/piece/ged`, `/mail/projet/suggerer`, `/mail/relance`, `/mail/rule/delete`, `/mail/rule/save`, `/mail/rule/suggest`, `/mail/rules`, `/mail/rules/apply`, `/mail/schedule`, `/mail/summary`, `/mail/thread`, `/project/ask`, `/project/search`, `/project/suggest`, `/task/creneau`, `/task/from`
- `/api/journal` (5) : `/act`, `/anomalies`, `/postmortem`, `/postmortem/save`, `/purge`
- `/api/lab` (14) : `/assign`, `/chat`, `/contexte`, `/delete`, `/etabli`, `/modes`, `/piece`, `/piece/ged`, `/piece/oter`, `/pieces`, `/pull`, `/pull_status`, `/setmodel`, `/sources`
- `/api/liens` (2) : ``, `/graphe`
- `/api/mail` (3) : `/recap_now`, `/settings`, `/test`
- `/api/me` (9) : `/agenda/detach`, `/agenda/save`, `/deverrouiller`, `/history`, `/photo`, `/telegram/brancher`, `/telegram/cible`, `/telegram/detacher`, `/telegram/envoyer`
- `/api/modeles` (1) : `/migrer`
- `/api/msg` (8) : `/destinataires`, `/envoyer`, `/fait`, `/liste`, `/programmer`, `/reecrire`, `/relire`, `/save`
- `/api/notes` (2) : `/migration`, `/tache/rappel`
- `/api/notif` (6) : `/agir`, `/essai`, `/passe`, `/prefs`, `/sourdine`, `/webhook`
- `/api/proactive` (3) : `/act`, `/investigate`, `/snooze`
- `/api/ranger` (1) : ``
- `/api/rappel` (1) : `/comprendre`
- `/api/reglages` (1) : `/veille/set`
- `/api/settings` (5) : `/api-key`, `/password`, `/relecteur`, `/relecteur/essai`, `/vision`
- `/api/telegram` (2) : `/adopter`, `/proposes`
- `/api/tgc` (9) : `/commencer`, `/delier`, `/dire`, `/ident`, `/importer`, `/lire`, `/piece`, `/valider`, `/visage`
- `/api/vault` (13) : `/mine/audit`, `/mine/cle_api`, `/mine/creer`, `/mine/delete`, `/mine/get`, `/mine/historique`, `/mine/list`, `/mine/qr`, `/mine/status`, `/mine/totp`, `/mine/trace`, `/mine/update`, `/mine/url`

## Évolution et GED distante — 41 routes

Modules V19 proches : evolution, ged. Fonctions : pilotage de l'évolution (cadence, pièces, souhaits, retour arrière), distants de la GED, aperçus, extraction, dédoublonnage, montages.

- `/api/evolution` (20) : `/cadence`, `/comptes`, `/journal`, `/lecon`, `/mesures`, `/moteurs`, `/pause`, `/piece`, `/piece/appliquer`, `/piece/refuser`, `/pieces`, `/regime`, `/rollback`, `/run_now`, `/status`, `/toxique`, `/unfreeze`, `/wish`, `/wish/delete`, `/wishlist`
- `/api/ged` (21) : `/apercu`, `/apercu/texte`, `/corbeille/vider`, `/dedoublonner`, `/extraire`, `/montage/add`, `/montage/remove`, `/op`, `/piece/apercu`, `/piece/voir`, `/preparer`, `/recettes`, `/remote/coller`, `/remote/create`, `/remote/delete`, `/remote/oauth`, `/remote/oauth/finir`, `/remote/tester`, `/remote/types`, `/scanner`, `/texte`

<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
