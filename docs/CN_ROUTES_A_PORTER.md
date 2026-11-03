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
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=5c3173 ▼▼▼ -->
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

## Bureau d'Itare, messagerie et outils — 102 routes
Modules V19 proches : notes, canaux, telegram, canvas, coffre, notifications, journal, proactif, comptes. Fonctions : contacts (CardDAV, photos, documents), laboratoire, messages programmés, Telegram, Canva, carnet, préférences de notification, coffre personnel, agenda externe.

**Porté dans cette section** (la V19 y répond autrement que par 501) : le carnet (`/api/carnet/*`, par le module notes), les réglages de la cloche (`/api/notif/*` : préférences, politique de canaux, sourdines, essai, webhook chiffré ; notifications 0.3.0),
Mon coffre-fort (`/api/vault/mine/*` ; coffre 0.2.0 : fiches typées, TOTP, historique chiffré), les messages en cours et programmés (`/api/msg/*` ; module messages 0.1.0, courrier 0.1.4 `envoyer_programme`),
les portraits, documents et vie privée d'une fiche du carnet (`/api/itare/contact/photos|documents|privacy` ; contacts 0.3.4, GED 0.1.2).
Honnêtement, **ce qui reste est ci-dessous**. Limites connues de ce qui est porté : les canaux de la cloche (courriel, Telegram, webhook) n'envoient pas encore (la politique est enregistrée pour eux, l'essai le dit) ; `/api/notif/agir` répond qu'aucune action n'est attachée à une notification ;
les fiches du coffre sont des documents JSON rangés dans la note sécurisée (l'application Bitwarden ne les voit pas comme des identifiants) et il n'y a plus de clé d'API personnelle ; `bcc` d'un message est enregistré mais le courrier ne le pose pas (comme en V18) ; `/api/msg/relire` et `/api/msg/fait` (relecture et faits relevés par un modèle) restent à porter.

**Greffe du 03-11 (deuxième passe).** Avant de coder, chaque route restante a été rapprochée des capacités qui existent déjà. Sont maintenant servies, sans toucher à un module : le robot Telegram du compte (`/api/me/telegram/*`, `/api/telegram/proposes|adopter`), le rappel lié à une case, les liens et leur graphe (renvois des notes seulement : la table générique de liens de la V18 n'est pas portée), le récit de l'autonomie (politique de la machine), les anomalies du journal (silences seulement : les pics dans les lignes ne sont pas relevés), le post-mortem (ligne du temps + modèle, enregistré comme note), le portrait (poser, retirer), le verrou d'écran, l'agenda distant (enregistrer, détacher), `/api/conv/ecrire` (l'adresse est lue sur la fiche, jamais sur la requête), `/api/itare/task/from` et `/api/msg/relire` (relecture mécanique, plus le fil si le courrier et un modèle répondent), `/api/rappel/comprendre` (le moment lu dans une phrase, calculé à l'écran : fonction pure) et `/api/mail/test` (l'essai part à l'adresse du compte, jamais à une adresse de la requête). Les dossiers de comptes et les lignes sans propriétaire sont des notions de la V18 (dossiers sur disque, lignes sans compte) : la V19 répond « rien à inventorier » plutôt que d'inventer.

Ce qui reste (102 routes) : **38 à compléter** () et **64 à créer** (aucune capacité ne couvre). Le classement vient des manifestes et des noms de routes ; chaque ligne se relit dans la V18 avant d'être codée.

| Route | Reste | Ce qui existe, ou ce qu'il faut |
|---|---|---|
| `/api/canva/brancher` | À créer | intégration Canva (OAuth + jeton à ranger comme secret) : aucun module ne la porte |
| `/api/canva/creer` | À créer | intégration Canva (OAuth + jeton à ranger comme secret) : aucun module ne la porte |
| `/api/canva/debrancher` | À créer | intégration Canva (OAuth + jeton à ranger comme secret) : aucun module ne la porte |
| `/api/canva/designs` | À créer | intégration Canva (OAuth + jeton à ranger comme secret) : aucun module ne la porte |
| `/api/canva/etat` | À créer | intégration Canva (OAuth + jeton à ranger comme secret) : aucun module ne la porte |
| `/api/canva/reconcilier` | À créer | intégration Canva (OAuth + jeton à ranger comme secret) : aucun module ne la porte |
| `/api/canvas/amorcer` | À compléter | canvas.departs + modeles.completer : le départ choisi, les sources lues, le modèle propose, la personne décide |
| `/api/canvas/ext/apercu` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/ext/etat` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/ext/lister` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/geste` | À compléter | canvas.gestes + modeles.completer : reformuler, resserrer, développer… sur un passage |
| `/api/canvas/importer` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/itare` | À compléter | même chaîne que geste, avec la persona d'Itare |
| `/api/canvas/portes` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/registre` | À compléter | canvas.departs et canvas.gestes en un seul inventaire |
| `/api/canvas/relier` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/sorties` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/sortir` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/vivante/poser` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/canvas/vivante/rejouer` | À créer | section vivante, sorties, portes, liaison, import et sources externes du canvas : différés par le manifeste de canvas |
| `/api/ita/basculer` | À créer | client MTProto d'Itare (Telethon) : canaux l'a différé ; la session ne doit vivre que dans le coffre |
| `/api/ita/commencer` | À créer | client MTProto d'Itare (Telethon) : canaux l'a différé ; la session ne doit vivre que dans le coffre |
| `/api/ita/delier` | À créer | client MTProto d'Itare (Telethon) : canaux l'a différé ; la session ne doit vivre que dans le coffre |
| `/api/ita/ident` | À créer | client MTProto d'Itare (Telethon) : canaux l'a différé ; la session ne doit vivre que dans le coffre |
| `/api/ita/reconnaitre` | À créer | client MTProto d'Itare (Telethon) : canaux l'a différé ; la session ne doit vivre que dans le coffre |
| `/api/ita/relancer` | À créer | client MTProto d'Itare (Telethon) : canaux l'a différé ; la session ne doit vivre que dans le coffre |
| `/api/ita/valider` | À créer | client MTProto d'Itare (Telethon) : canaux l'a différé ; la session ne doit vivre que dans le coffre |
| `/api/itare/bureau/suggestions` | À compléter | agents.propositions + taches.lister : ce que le bureau propose d'abord |
| `/api/itare/contact/autolink` | À compléter | contacts.lier + projets.courrier : rapprochement adresse → projet |
| `/api/itare/contact/carddav` | À créer | client CardDAV : réseau + secret (contacts n'a pas encore `[permissions] secrets`) |
| `/api/itare/contact/carddav/delier` | À créer | idem |
| `/api/itare/contact/carddav/importer` | À créer | idem |
| `/api/itare/contact/carddav/relier` | À créer | idem |
| `/api/itare/contact/propositions` | À compléter | contacts.lister + courrier.lister : les expéditeurs sans fiche |
| `/api/itare/contact/site/apercu` | À compléter | sites.fiche + contacts.voir |
| `/api/itare/contact/site/importer` | À compléter | sites.fiche + contacts.creer |
| `/api/itare/contact/sites` | À compléter | sites.liens + contacts.pour_cible |
| `/api/itare/draft/compose` | À compléter | modeles.completer + messages.save : un brouillon rédigé, enregistré dans messages |
| `/api/itare/event/prep` | À compléter | agenda.evenement + modeles.completer : la préparation d'un rendez-vous |
| `/api/itare/mail/avatars` | À compléter | contacts.photos + courrier : vignettes des correspondants |
| `/api/itare/mail/avatars/oublier` | À compléter | idem |
| `/api/itare/mail/chercher` | À compléter | courrier.lister avec un terme (argument facultatif à ajouter) |
| `/api/itare/mail/link` | À compléter | courrier + ged_liens : lier un message à une fiche ou à un projet |
| `/api/itare/mail/media` | À créer | index des pièces jointes (texte extrait, vignettes) : ged propose l'extraction, pas l'index du courrier |
| `/api/itare/mail/media/index` | À créer | idem |
| `/api/itare/mail/media/texte` | À créer | idem |
| `/api/itare/mail/piece/ged` | À compléter | courrier.piece + ged.deposer : composition |
| `/api/itare/mail/projet/suggerer` | À compléter | projets.courrier + projets.trouver |
| `/api/itare/mail/relance` | À compléter | taches.creer + courrier.lire : relance d'un message sans réponse |
| `/api/itare/mail/rule/delete` | À créer | règles de tri du courrier : aucune capacité |
| `/api/itare/mail/rule/save` | À créer | idem |
| `/api/itare/mail/rule/suggest` | À créer | idem |
| `/api/itare/mail/rules` | À créer | idem |
| `/api/itare/mail/rules/apply` | À créer | idem |
| `/api/itare/mail/schedule` | À compléter | courrier.lire + modeles.completer + agenda.evenement_enregistrer : un message devient un rendez-vous |
| `/api/itare/mail/summary` | À compléter | courrier.lire + modeles.completer |
| `/api/itare/mail/thread` | À compléter | courrier.lire : le fil n'est pas rendu par la capacité (clé de fil à ajouter, en argument facultatif) |
| `/api/itare/project/ask` | À compléter | projets.contexte + modeles.completer |
| `/api/itare/project/search` | À compléter | projets.trouver + notes.lister |
| `/api/itare/project/suggest` | À compléter | projets.cadrage_proposer |
| `/api/itare/task/creneau` | À compléter | taches.fiche + agenda.agenda : un créneau libre pour une tâche |
| `/api/journal/act` | À créer | actions sur un relevé (relancer un service…) : elles passent par le courtier, pas par le journal |
| `/api/journal/purge` | À créer | purge irréversible : refusée tant qu'elle n'a pas de retour (defaire) |
| `/api/lab/assign` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/chat` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/contexte` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/delete` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/etabli` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/modes` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/piece` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/piece/ged` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/piece/oter` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/pieces` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/pull` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/pull_status` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/setmodel` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/lab/sources` | À créer | laboratoire de modèles (conversations d'essai, sources, pièces, tirage de modèles) : aucun module ; modeles couvre les moteurs, pas le banc |
| `/api/mail/recap_now` | À compléter | notifications + journal.resume : le récapitulatif hebdomadaire envoyé à la demande |
| `/api/mail/settings` | À compléter | réglages courrier : adresse publique, jour et heure du récapitulatif (à déclarer) |
| `/api/me/history` | À compléter | sans appelant dans l'écran V19 (la carte d'activité lit /api/me/activity) : à rendre vide ou à retirer |
| `/api/modeles/migrer` | À compléter | modeles.role_lier : migration d'un rôle vers un autre moteur |
| `/api/msg/fait` | À compléter | modeles.completer + faits des modules certificats, sauvegardes, dns |
| `/api/notif/agir` | À créer | une action attachée à une notification : la notification n'en porte pas encore |
| `/api/proactive/act` | À compléter | proactif.incidents : l'incident V19 a une cause et une fin prouvée, pas d'action à la demande |
| `/api/proactive/investigate` | À compléter | proactif.incidents + journal.timeline |
| `/api/proactive/snooze` | À créer | mettre une alerte en sommeil : pas de capacité (la sourdine des notifications est à relier) |
| `/api/ranger` | À compléter | classement du carnet (notes.menage) : comportement V18 à relire avant |
| `/api/reglages/veille/set` | À créer | interrupteurs de surveillance : portés par les détecteurs de chaque module, sans réglage commun |
| `/api/settings/api-key` | À créer | clé d'API de l'administrateur : plus de clé personnelle en V19 |
| `/api/settings/password` | À compléter | comptes.changer_mon_mot_de_passe (déjà servi par /api/me/password) |
| `/api/settings/relecteur` | À compléter | modeles.role_lier (rôle relecteur) |
| `/api/settings/relecteur/essai` | À compléter | modeles.essayer |
| `/api/settings/vision` | À compléter | modeles.role_lier (rôle vision) |
| `/api/tgc/commencer` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |
| `/api/tgc/delier` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |
| `/api/tgc/dire` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |
| `/api/tgc/ident` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |
| `/api/tgc/importer` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |
| `/api/tgc/lire` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |
| `/api/tgc/piece` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |
| `/api/tgc/valider` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |
| `/api/tgc/visage` | À créer | client MTProto du compte (Telethon) : canaux l'a différé ; lire, écrire, importer exigent la session au coffre |

## Évolution et GED distante — 41 routes

Modules V19 proches : evolution, ged. Fonctions : pilotage de l'évolution (cadence, pièces, souhaits, retour arrière), distants de la GED, aperçus, extraction, dédoublonnage, montages.

- `/api/evolution` (20) : `/cadence`, `/comptes`, `/journal`, `/lecon`, `/mesures`, `/moteurs`, `/pause`, `/piece`, `/piece/appliquer`, `/piece/refuser`, `/pieces`, `/regime`, `/rollback`, `/run_now`, `/status`, `/toxique`, `/unfreeze`, `/wish`, `/wish/delete`, `/wishlist`
- `/api/ged` (21) : `/apercu`, `/apercu/texte`, `/corbeille/vider`, `/dedoublonner`, `/extraire`, `/montage/add`, `/montage/remove`, `/op`, `/piece/apercu`, `/piece/voir`, `/preparer`, `/recettes`, `/remote/coller`, `/remote/create`, `/remote/delete`, `/remote/oauth`, `/remote/oauth/finir`, `/remote/tester`, `/remote/types`, `/scanner`, `/texte`

<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
