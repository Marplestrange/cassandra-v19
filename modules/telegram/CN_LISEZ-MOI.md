<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : telegram — le robot Telegram d'un compte -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : telegram -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.2.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : telegram — le robot Telegram d'un compte -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.2.0 empreinte=2db668 ▼▼▼ -->
# telegram — le robot Telegram d'un compte

Porté de la V18 (`tg_*`, robot de notifications), lu en entier. La passerelle apprend deux choses pour cela : une capacité publique peut recevoir le **corps brut** d'un service extérieur (`corps_brut`) et **ses en-têtes** (`en_tetes`, sans cookie ni autorisation).

## Fonctionnement
- Régler `telegram.url_publique` (https obligatoire : Telegram l'exige). Le webhook est `<adresse>/api/public/telegram.recevoir`.
- Chaque compte colle le jeton de **son** robot (`brancher`) : vérifié par `getMe`, secret tiré, webhook posé (`drop_pending_updates`).
- Le compte visé par un appel entrant se retrouve par le SEUL secret (empreinte sha256) ; le contenu ne désigne jamais un destinataire ; un secret inconnu reçoit un 200 muet.
- Le robot ne lit pas ce qu'on lui écrit : le message est rangé, signalé (événement `telegram.message_recu`, que le module notifications pourra écouter), jamais exécuté. Le premier message apprend la conversation ; le mot du rôle n'est dit qu'une fois par heure.
- Destinataire = celui déclaré (`cible_poser`, essayé pour de bon, jamais un @pseudo) sinon celui appris.
- `envoyer` : un compte n'écrit que par son robot ; le système (Cassandra) écrit pour un compte. Retour = suppression du message chez Telegram (48 h).
- `prevenir` : la porte des notifications. Le moteur du module `canaux` (sous le compte « noyau », reconnu par `ctx.appelant`) y porte ce que la politique du destinataire demande, par le robot de ce destinataire et jamais un autre. Tout autre appel rend `{ok: false, cause: "reserve"}`.
- Un refus d'envoi ou un appel mal formé est un RÉSULTAT, pas une exception (l'apprentissage des paliers ne doit pas couper l'envoi de tous pour le robot bloqué d'un seul).

## À savoir
- Le **jeton du robot** est un réglage secret par compte (`telegram.jeton`), chiffré au repos ; il n’est jamais copié dans la base du module.
- `envoyer` démarre au palier « raconter » et y reste tant que l'administrateur ne l'a pas choisi : Cassandra et Itare racontent avant d'écrire sur Telegram.
- `prevenir` n'a que le palier « auto » : la personne a déjà décidé, dans sa politique de notifications, de recevoir ses alertes ici. C'est pour ne pas ouvrir `envoyer` aux agents que les notifications ont leur propre porte.

## Non porté
- **Le miroir du chatlab** (`tg_miroir*`, `ita_ecrire_a`) et le **compte Telegram d'Itare / d'une personne** (`tgc_*`, ~1 000 lignes, Telethon) : module suivant (`telegram_compte`).
- **Correspondants proposés / adopter une fiche** (`tg_proposes`, `tg_adopter`) : attend le module contacts.
- **Le courriel et le webhook des notifications** : seul Telegram livre (module `canaux`).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
