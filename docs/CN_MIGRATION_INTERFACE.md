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
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=9c23e7 ▼▼▼ -->
# Remplacer l'ancienne interface (V18) par des écrans V19

Décision (26-10, Drisse) : l'interface V18 avait été **extraite** et réemployée comme socle (voir `docs/CN_AFFICHAGE.md`). C'était une erreur de méthode : on se retrouve avec deux codes (l'ancien qui rend 34 des 37 entrées de menu, et le nouveau), un ancien écran qui se montre un instant au chargement, et des écrans qui n'ont pas l'esprit de la V19 (Cassandra d'abord, le récit, le défaire, le téléphone). **On remplace tout, écran par écran, et on supprime l'ancien code au fur et à mesure.**

## Où on en est (mesuré)
- `interface/CN_app.js` : 38 226 lignes (l'ancien JS), `CN_style.css` 7 631 lignes, `CN_index.html` 4 768 lignes dont **17 panneaux** (`tab-*`).
- 33 tables de routes (`interface/routes/`, 2 191 lignes) et `CN_compat.js` : la couche qui fait croire à l'ancien JS que ses 615 routes existent.
- Écrans V19 déjà là : Logithèque, Mes applications, Zones DNS, Certificats, Dolibarr, Évolution (écran), et les pages posées dans le panneau « bureau » (Aujourd'hui…).
- Entrées de menu qui ouvrent encore un panneau V18 : 34 (table `ENTREES` de `modules/affichage/points/EC_disposition.py`).

## La méthode (la même pour chaque écran)
1. Le module du domaine a déjà ses capacités (la V19 est portée côté serveur) : l'écran les appelle **directement**, sans passer par la couche de compatibilité.
2. Un fichier `interface/CN_<x>-ecran.js` (crochet `CASS.sceneSurMesure.<module>`), bâti sur le **kit commun** (`CN_kit.js`) : mêmes cartes, mêmes pastilles, même tiroir, même gabarit téléphone, même accessibilité que la Logithèque.
3. Le module déclare `[[ecrans]]` et `[[menus]]` dans son manifeste ; l'entrée disparaît de `ENTREES` (donc l'onglet V18 n'est plus joignable).
4. Un test d'interface (réponses simulées) et, côté serveur, le banc existant du module.
5. Quand plus aucune entrée ne mène à un panneau, le panneau (HTML) et ses routes de compatibilité sont **supprimés**. Le JS V18 qui ne sert plus à personne tombe avec la fin de `CN_app.js` (dernier lot).
6. On **tranche ce qu'on garde** : un écran V18 qui avait dix scènes n'en garde pas forcément dix ; ce qui est abandonné est dit dans cette page.

## Les lots, dans l'ordre
| # | Lot | Panneaux V18 (lignes de HTML) | Module(s) | Remarque |
|---|---|---|---|---|
| 0 | Kit commun | — | — | extrait de la Logithèque |
| 1 | Observatoire | history (25), sensorium (25), journal (33) | mesures, sensorium, journal | lectures, peu d'état : le plus sûr pour roder la méthode |
| 2 | Parc | overview (134), fleet (25), mysites (29), fastpanel (48), crons (150) | vue, flotte, sites, fastpanel, planifie | Panorama = le verdict de la maison |
| 3 | Sécurité | securite (321) | securite | pare-feu, outils, analyse |
| 4 | Autonomie | evolution (47), proactive (172), memory (51) | evolution, proactif, memoire | Évolution a déjà un écran V19 |
| 5 | Bureau | bureau (980) | courrier, agenda, taches, notes, contacts, ged, projets, jour | le plus gros : un écran par application |
| 6 | Salon | salon (114) | salon | vit déjà dans le panneau de conversation |
| 7 | Avatar | settings (1 936), vault (144) | reglages, coffre, comptes… | pages de l'avatar : à scinder en écrans par rubrique |
| 8 | Le cœur | — | — | connexion, cloche, thème, toasts, session : ce que `CN_app.js` fournit encore au shell ; puis **suppression de `CN_app.js`, `CN_style.css` (V18), `CN_compat.js` et `routes/`** |

## Ce qui est abandonné (au fil des lots)
- **Lot 1 — Observatoire** (Historique, Journaux, Sensorium : écrans V19 sur le kit, panneaux V18 plus joignables).
  - Sensorium : ne sont pas repris pour l'instant les gestes « Accepter… » (se taire jusqu'à l'échéance), les gestes de réparation par le catalogue, « Relever la flotte » et l'installation du témoin extérieur : aucune capacité V19 ne les porte encore ; ils reviendront avec leurs capacités (écriture, derrière le palier d'autonomie), pas par la couche de compatibilité.
  - Journaux : la timeline séparée du V18 est absorbée par le flux unifié.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
