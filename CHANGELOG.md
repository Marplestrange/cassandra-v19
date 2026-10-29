# Journal des changements

Aucune version n'a encore été étiquetée : la V19 est en développement, et la V18 reste la version de production (dépôt `cassandra`). Ce journal rassemble ce qui compte pour
quelqu'un qui découvre le projet ; le détail est dans l'historique git, dont chaque message dit le *pourquoi*.

## Non publié

### Ajouté
- **Plusieurs sociétés dans une instance** : tout compte appartient à une société ; la société principale est propriétaire de l'instance ; fonctions par société (aucun, voir, modifier, gérer) ;
  modules ouverts société par société ; demandes de module (la société secondaire demande, la principale examine, installe et attribue) ; sélecteur de société ; vue consolidée.
- **Partages entre sociétés**, décidés par le superadministrateur : utilisateurs, carnet de contacts (lecture seule), modèles (habillage, préfixes de devis et de facture).
- **Une base de données par société** pour un module qui le déclare (`stockage_par_societe`), sans changer son code ; ses moteurs tournent société par société.
- **Le coffre** : un espace par compte et par société, des rôles, l'auteur de chaque secret, le départ d'un utilisateur, et un **coffre externe** sur le Vaultwarden propre à une société.
- **Un profil par société** pour une personne (signature du courrier), la signature de la société dans le courrier, le fuseau de la société dans l'agenda.
- **La billetterie** : l'interface V19 (vue d'ensemble, événements, ventes, revendeurs, caisse, contrôle, espaces du revendeur et de l'artiste), la boutique publique, les comptes clients.
- **Sécurité** : ses pages sont des sous-menus de la colonne de gauche.
- **Documentation** : README refait (aperçu, nexus CN et évolution EC, sociétés, coffre), `SECURITY.md`, `CONTRIBUTING.md`, résumé en anglais, catalogue des modules généré.
- `ctx.frein_actif(nom)` : lecture seule des freins d'urgence, pour les moteurs (qui n'ont pas de compte).

### Corrigé
- La liste de sélection d'un partage ne propose plus que des personnes (ni les agents, ni le noyau).
- Un essai d'interface (« Aujourd'hui ») ne dépend plus de l'heure.

### Retiré
- Les squelettes de `brouillons/` (tous les modules sont portés ; les maquettes rejoignent `docs/maquettes/`).
