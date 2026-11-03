<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : projets — les projets d'un compte -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : projets -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.2.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : projets — les projets d'un compte -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.2.0 empreinte=b7b131 ▼▼▼ -->
# projets — les projets d'un compte

Porté de la V18 (`pj_*`, `projet_*` : en-tête, rôles, phases, jalons, décisions, journal, plan de référence, corbeille, avancement), lu en entier pour ce cœur.

## Ce que fait le module
- **Fiche** (objectif, périmètre, réussite, domaine, serveur, priorité, statut), créée depuis un modèle qui pose ses phases (sans lien qui subsiste). **Journal** daté, une ligne par mouvement.
- **Rôles** : propriétaire > co-propriétaire > auteur > lecteur. Chaque porte vérifie le rôle ; un projet d'autrui répond « introuvable » (même à l'administrateur : administrer n'est pas voir). Un projet **archivé** n'accepte plus d'écriture mais reste modifiable (pour le rouvrir).
- **Plan de référence** : on le fige explicitement, l'ancien part au journal ; le glissement (phases, jalons) se lit ensuite en jours. Les phases se refigent à chaque fois, un jalon garde sa date d'origine (« ne peut pas bouger »).
- **Avancement** pondéré par la charge des phases. **Jalons dépassés** : constat visible du propriétaire.
- **Équipe** : invitation avec rôle, réponse, retrait (ou départ de soi-même) ; événements `projet.invitation` / `projet.reponse` adressés au compte concerné.
- **Corbeille** : supprimer ne détruit rien (lignes et équipe restent), restaurer rend le projet sous son numéro, purger (propriétaire) garde de quoi défaire.
- Tout geste a sa preuve et son retour.

## L'Atelier du projet (`/api/pj/*`)
Porté de la V18 (`pj_atelier_*`, `atelier_*`, `pj_fil*`, `pj_com*`, `pj_courrier*`, `pj_cadrage_*`, `pj_dossier_*`, `nav_*`) dans `CN_coffre.py` et `CN_fil.py` ; les routes sont dans `interface/routes/CN_projets_pj.js`.
- **Dossier de fichiers** : un dépôt de CE serveur, dans l'espace du propriétaire (`<espace du compte>/projets/depots/<nom>`), rattaché au projet (`projets.dossier = local:/nom`). Rien ne sort du dossier (`..` et liens refusés) ; l'état trouvé est TOUJOURS rangé en version avant d'être remplacé, déplacé ou retiré ; une écriture porte l'empreinte lue et ne piétine jamais un fichier changé ailleurs (le conflit est rendu) ; renommer ou déplacer réécrit les `[[liens]]` comme Obsidian ; un dossier retiré va à la corbeille des dépôts. Ce qu'écrit Itare entre dans la file « à relire » du fil.
- **Fil, commentaires, présence** : un fil daté (messages avec @mentions, décisions avec avis et arbitrage, journal, activité du dossier regroupée, courrier, file « à relire »), des commentaires accrochés à une citation, une présence en mémoire (une minute de vie).
- **Courrier rangé** : lu dans le cache de la boîte du compte qui regarde (jamais IMAP, jamais la boîte d'un autre). **Cadrage** : un diff, rien n'est écrit avant l'accord. **Suites proposées** : au plus trois, tirées des faits (jalons dépassés, décisions ouvertes, écritures à relire, tâches en retard).
- **Navigateur partagé** : ouvre une page publique par le module web (texte), revient, ferme, et range la page en note Markdown dans le dossier.
- Les gestes qui touchent deux modules (importer un document, verser une note du Carnet, prendre une pièce jointe) passent par la porte `projets.garde` puis par les capacités de la GED, des notes et du courrier.

## Non porté — et pourquoi
- **Machines distantes** (`machine:/chemin` par SFTP, le sélecteur de dossier sur la flotte) : la flotte ne donne pas de canal de fichiers ; seuls les dépôts de ce serveur sont portés.
- **Réponse d'Itare** à une @mention du fil ou d'un commentaire, et **relecture quotidienne d'Itare** : l'événement `projet.itare` est émis, mais le module des agents ne l'écoute pas encore ; aucune réponse n'est inventée. Les suites proposées sont calculées sur les faits, sans modèle.
- **Image, clic, défilement et frappe** du navigateur (Chromium piloté par tube et son relais anti-réseau privé) : la V19 lit les pages en texte.
- **Nature « livre » et ses mesures de texte** (`pj_tableau`, `pj_inventaire`), **droits d'Itare par projet** : non repris.
- **Tâches** (`itare_tasks`) : module des tâches ; un projet supprimé ne les emporte pas. **Liens contacts/sites vers un projet** : ils pointent déjà ici par l'identifiant.
- Purger un projet efface ses lignes d'atelier (fil, versions, commentaires) mais **pas** ses fichiers, qui restent dans le dépôt ; le retour de la purge ne les rend donc pas.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
