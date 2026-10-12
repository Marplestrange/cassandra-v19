# contacts — le carnet d'adresses

Porté de la V18 (`contact_*`, `contacts_*`, vCard, CSV, doublons, fusion), lu en entier. Une nouveauté du noyau : `ctx.acteur` (qui agit), pour ne montrer à un modèle que ce que l'administrateur a choisi.

## Ce que fait le module
- Fiches par compte (cloisonnées : l'administrateur n'y a pas accès), adresses (une adresse = une fiche par compte), téléphones, société, notes, étiquettes, favori, photo (data URI ≤ 210 Ko, refusée plutôt que tronquée), anniversaire.
- Dossiers (un seul niveau), archive, corbeille de 30 jours (rien n'est effacé tant que la purge n'est pas demandée ; la purge garde de quoi défaire).
- Rattachements (projet, domaine, serveur, tâche, URL, rappel, note, événement) avec rôle ; une déduction (`auto`) ne remplace jamais un lien posé à la main.
- Doublons proposés par degré (adresse identique, jumelles d'import, probable, possible, piège) avec mémoire des paires « pas la même personne » ; fusion qui garde tout ; fusion en lot réservée au certain.
- Import/export vCard 3.0 (repli à 75 octets, `;` et `,` échappés), import CSV avec aperçu de l'appariement avant d'écrire (UTF-8 puis cp1252, séparateur compté sur l'en-tête).
- Vue pour un modèle : `contacts.vue_modele` (expurgée par défaut : « a une adresse » sans la valeur), `contacts.notes_au_modele`.
- Chaque geste a sa preuve et son retour (instantané de la fiche, des adresses et des liens).

## Défauts de la V18 corrigés au passage
- Un `;` échappé dans une société (« Acme\; Cie ») coupait le nom à l'import vCard.
- Un texte finissant par une espace perdait l'espace à l'import.
- Les initiales (« J. Danet ») ne sont reconnues que si un autre signal rapproche déjà les fiches.

## Non porté
- **CardDAV** (`carddav_*`) : client réseau avec secret, à porter avec le coffre.
- **Propositions d'Itare** (`contact_propositions`, signaux tirés du courrier, `contact_stale_pass`, `contacts_verser` depuis le courrier, autoliaison par domaine) : attendent les modules courrier et projets.
- **Portraits reçus par le courrier**, **messages d'un correspondant**, **documents liés** (GED) : idem.
- **Prévenir un contact pour un domaine** (`contact_for_domain`, `_contact_alert_line`) : la lecture `pour_cible` existe ; le repli sur le projet du domaine attend le module projets.
