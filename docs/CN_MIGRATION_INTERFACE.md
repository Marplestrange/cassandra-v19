<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Remplacer l'ancienne interface (V18) par des écrans V19 -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Remplacer l'ancienne interface (V18) par des écrans V19 -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=2bb3b7 ▼▼▼ -->
# Remplacer l'ancienne interface (V18) par des écrans V19

Décision (26-10, Drisse, révisée) : **on ne refait pas les modules.** L'interface V18 reste le moteur des écrans de chaque module, avec toutes ses fonctions et ses pastilles ; la V19 apporte le cadre (disposition, menus, panneau de Cassandra, Logithèque, Mes applications) et surtout **un habillage universel** : un seul jeu de jetons (couleurs, rayons, ombres, verre dépoli, typographie, espacements) appliqué à tous les écrans, anciens compris.

Essai abandonné : refaire écran par écran (Historique, Journaux, Sensorium, Flotte, Sites, Hébergement, Automatismes) retirait des fonctions et des pastilles sans rien apporter. Les cinq commits ont été défaits (revert) ; le Panorama, resté en brouillon, est rangé dans le stash `panorama-v19-abandonne`. Le kit commun (`CN_kit.js`) reste pour les écrans neufs seulement.

## Ce qu'on fait à la place
1. **Habillage universel** : faire lire à la feuille V18 les jetons V19 (variables CSS) plutôt que ses propres valeurs ; retirer le CSS du menu V18 devenu inutile (la disposition V19 le remplace).
2. **Aucune suppression de panneau ni de code V18** sans validation de Drisse écran par écran.
3. Les écrans **neufs** (nouveaux modules) se bâtissent sur le kit commun.

## Ce qui reste hors du cadre
Rien n'est retiré : tout écran V18 garde ses scènes, ses pastilles et ses gestes.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
