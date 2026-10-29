# Sécurité

Cassandra administre des serveurs, des secrets et des données de travail : une faille y a des conséquences réelles. Merci de la signaler avec soin.

## Signaler une vulnérabilité

Écrivez à **marplestrange@cassandra.center**, avec pour objet « Sécurité — Cassandra V19 ». **Ne publiez pas la faille** (ticket public, forum, réseau social) avant
qu'elle soit corrigée : une divulgation coordonnée protège les installations existantes.

Pour qu'on puisse la reproduire, indiquez :

- la version (`V19`, ou `V18` pour le dépôt de production) et la manière dont Cassandra est installée (reverse proxy, tunnel SSH, port exposé) ;
- ce que vous avez observé et ce que vous attendiez ;
- les étapes pour la reproduire, et l'impact que vous lui voyez ;
- si vous souhaitez être nommé dans la correction (nous le faisons volontiers).

Le projet est porté par une association, sans équipe de sécurité dédiée : nous accusons réception, évaluons, corrigeons, puis publions ce qui doit l'être.

## Ce qui est couvert

La **V19** (ce dépôt) et la **V18** (dépôt `cassandra`). Les anciennes versions archivées (V3.2 à V14) ne reçoivent pas de correctif.

## Les garanties du noyau, et donc ce qui compterait comme une faille

La sûreté de la V19 ne repose pas sur une permission à demander mais sur des garanties que le **noyau** tient pour tous les modules (voir `docs/CN_NEXUS.md`). Les contourner est une faille :

- **Preuve et retour arrière.** Une capacité qui écrit déclare son périmètre, sa preuve et son retour, sinon le manifeste est refusé. Chaque geste est journalisé ; le journal est chaîné par empreintes.
- **Droits déclarés et vérifiés en un seul endroit.** Un module déclare ses droits ; le noyau les vérifie. Un module sans droit déclaré est refusé à l'installation.
- **Cloisonnement.** Un compte ne voit que ses propres données, y compris face à l'administrateur ; un module ne lit jamais plus que le compte au nom duquel il travaille. Entre sociétés, rien ne se voit sans un partage décidé par le superadministrateur ; le coffre d'un compte et celui d'une société sont isolés par espace.
- **Les secrets restent dans le coffre.** Ils ne vont ni dans la mémoire, ni dans le code, ni dans les journaux ; un module qui garde une clé la chiffre pour sa propre base.
- **Une donnée n'est jamais une consigne.** Ce qu'un agent lit sur le web ou dans un courriel ne lui donne aucun ordre ; après une lecture venue de l'extérieur, il ne peut ni envoyer ni agir sous mandat sans accord humain. L'adresse d'un envoi ne vient jamais de la demande.
- **Les agents ne se promeuvent pas.** Le palier d'autonomie est un réglage de l'administrateur ; des freins (gel, coupure des envois, arrêt d'urgence) le tiennent en échec.
- **Ce qui s'exécute en racine passe par un courtier** : le noyau ne dit jamais *quoi* exécuter, seulement *quelle commande nommée* d'un module, déclarée à l'avance.
- **Un module de tiers est examiné avant d'être installé** : archive en quarantaine, permissions montrées, consentement à leur empreinte, signature de l'éditeur par défaut. Il ne peut pas encore être confiné dans son propre processus : n'installez que des paquets d'éditeurs de confiance (`docs/CN_STORE.md`).
- **L'évolution ne touche jamais le nexus.** Une évolution automatique remplace seulement une fonction pure déclarée comme telle, après rejeu, ombre et paliers ; ni droits, ni secrets, ni envois, ni preuve.

## Si vous installez Cassandra

- Elle écoute sur `127.0.0.1:9000` par défaut. Pour y accéder à distance, utilisez un reverse proxy avec TLS ou un tunnel SSH ; n'exposez pas le port en direct sans TLS.
- Activez le second facteur (clé de sécurité) pour les comptes administrateurs et gardez le système à jour.
- Sauvegardez la base du noyau, celles des modules et le coffre ; vérifiez qu'une restauration fonctionne.
- Ne publiez jamais un fichier de configuration (clés d'API, mots de passe) : il est ignoré par git, ne le forcez pas.
