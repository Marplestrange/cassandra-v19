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

## Non porté (modules voisins)
- **Tâches** (`itare_tasks`, charge, avancement par tâches) : module des tâches ; un projet supprimé ne les emporte pas.
- **Itare dans le projet** : droits d'Itare par projet, propositions quotidiennes, cadrage assisté, fil, commentaires d'Itare, atelier (`pj_proposer`, `pj_cadrage_*`, `pj_fil*`, `pj_atelier_*`, `pj_com_itare`) : modules Itare.
- **Dossier du projet** (coffre/vault, `pj_dossier_*`, nature « livre » et ses mesures de texte), **courrier du projet** (`pj_courrier*`) : avec le coffre et le courrier.
- **Liens contacts/sites vers un projet** : ils pointent déjà ici par l'identifiant (`contacts.lier kind=project`).
