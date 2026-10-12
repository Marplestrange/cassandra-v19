# telegram — le robot Telegram d'un compte

Porté de la V18 (`tg_*`, robot de notifications), lu en entier. La passerelle apprend deux choses pour cela : une capacité publique peut recevoir le **corps brut** d'un service extérieur (`corps_brut`) et **ses en-têtes** (`en_tetes`, sans cookie ni autorisation).

## Fonctionnement
- Régler `telegram.url_publique` (https obligatoire : Telegram l'exige). Le webhook est `<adresse>/api/public/telegram.recevoir`.
- Chaque compte colle le jeton de **son** robot (`brancher`) : vérifié par `getMe`, secret tiré, webhook posé (`drop_pending_updates`).
- Le compte visé par un appel entrant se retrouve par le SEUL secret (empreinte sha256) ; le contenu ne désigne jamais un destinataire ; un secret inconnu reçoit un 200 muet.
- Le robot ne lit pas ce qu'on lui écrit : le message est rangé, signalé (événement `telegram.message_recu`, que le module notifications pourra écouter), jamais exécuté. Le premier message apprend la conversation ; le mot du rôle n'est dit qu'une fois par heure.
- Destinataire = celui déclaré (`cible_poser`, essayé pour de bon, jamais un @pseudo) sinon celui appris.
- `envoyer` : un compte n'écrit que par son robot ; le système (Cassandra) écrit pour un compte. Retour = suppression du message chez Telegram (48 h).
- Un refus d'envoi ou un appel mal formé est un RÉSULTAT, pas une exception (l'apprentissage des paliers ne doit pas couper l'envoi de tous pour le robot bloqué d'un seul).

## À savoir
- Le **jeton du robot est gardé tel quel** dans le fichier du module : le coffre chiffré n'est pas encore porté. À migrer vers lui.
- `envoyer` démarre au palier « raconter » : l'administrateur le met à « auto » pour que Cassandra livre les notifications d'elle-même.

## Non porté
- **Le miroir du chatlab** (`tg_miroir*`, `ita_ecrire_a`) et le **compte Telegram d'Itare / d'une personne** (`tgc_*`, ~1 000 lignes, Telethon) : module suivant (`telegram_compte`).
- **Correspondants proposés / adopter une fiche** (`tg_proposes`, `tg_adopter`) : attend le module contacts.
- **Livraison des notifications** : le module notifications n'appelle pas encore `telegram.envoyer` (déclaratif des canaux à faire).
