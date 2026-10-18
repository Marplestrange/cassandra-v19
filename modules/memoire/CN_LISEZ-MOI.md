<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Mémoire -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : memoire -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.1  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Mémoire -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.1 empreinte=37604b ▼▼▼ -->
# Mémoire

Un souvenir est un fait daté, prouvé, propriétaire, corrigeable d'une phrase. Une seule porte d'écriture (`ecrire`), des versions liées, un veto, des doutes, des épisodes, des rappels conditionnés aux capteurs, un journal chaîné.

- **Propriétaires** : `compte:x`, `partage` (faits de machine appris au service d'un administrateur), `cassandra`, `itare`. La portée est dans la requête : hors portée = introuvable. L'administrateur ne voit pas les comptes.
- **La porte** : catégorie (vocabulaire fermé), nature exigée (`etat-courant` + sonde rejouable, ou `constat`), clé en mots-clés, anti-secret / anti-consigne / anti-données sensibles / sujet / note creuse, quotas, plafond de confiance par provenance. Un refus est un **résultat** journalisé, jamais une exception (le palier ne baisse pas).
- **Réconciliation** : plus fort ou égal remplace (l'ancienne reste lisible) ; plus faible entre contesté et ouvre un doute ; le même fait sous une autre clé est une version.
- **Veto** : une écriture critique d'un agent attend en quarantaine ; un moteur la fait relire par le rôle `second_avis` (module modèles), les gardes mécaniques servant de signal ; sans relecteur, elles décident.
- **Rappel** : noyau (épinglés, personne) puis plein texte FTS5 sur l'actif, seuil réglable ; chaque souvenir cité porte sa fraîcheur ; une question d'état lit les capteurs (`sensorium.monde`), jamais un souvenir.
- **Distillation** : `apres_echange` met l'échange en file seulement si un déclencheur a eu lieu ; un moteur appelle le rôle `principal` hors du chemin de la réponse. Les épisodes se résument de même.
- **Péremption** : un `etat-courant` est relu quand son artefact bouge. Sondes (vocabulaire fermé, lecture seule) : `capacite_existe`, `capacite_absente`, `module_actif`, `module_version`, `objet_present`, `objet_etat`.
- **Journal chaîné** (sha256 depuis une genèse) vérifié une fois par jour ; une rupture est un constat critique.

## Non porté
Les tables « vues » de la vigie V18 (flotte, sites, services) : la perception ne lit que le sensorium. Les sondes qui lisaient le code source du programme (sans objet en V19). La page « moteurs » de l'écran (elle viendra de l'interface). Le pied de réponse HTML (l'interface le fait avec `cites`).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
