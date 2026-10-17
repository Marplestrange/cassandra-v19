<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : sites — les sites web suivis par Cassandra -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : sites -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.1  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : sites — les sites web suivis par Cassandra -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.1 empreinte=228665 ▼▼▼ -->
# sites — les sites web suivis par Cassandra

Porté de la V18 (`sites_vue`, `site_fiche`, `site_pass`, `site_history`, `site_availability`, demandes/accords, liens, journal), lu en entier.

## Ce que fait le module
- **Portée** : chaque compte voit ses sites (déclarés ici, attribués, inscrits dans sa fiche de compte, ou du panneau pour le compte du panneau lié à sa fiche). L'administrateur voit l'état de tous, jamais le contenu.
- **Sonde** (toutes les 5 min, budget 240 s, les moins récemment mesurés d'abord) : code, durée chronométrée, certificat lu sur le port 443 (au plus une fois par heure par site). Panne et retour jugés à la transition ; première observation = découverte.
- **Constats** : panne, lenteur (réglable), certificat court (réglable), adossement demandé.
- **Gestes avec preuve et retour** : déclarer, retirer, attribuer, transférer, demander l'adossement au panneau, y répondre, accorder un geste lourd au propriétaire pour un temps borné (7 jours au plus), lier projets/contacts/machines/notes.
- **Lectures** : vue (avec vigilances), fiche, historique, disponibilité sur N jours (un site non mesuré depuis 2 jours en sort), journal fondu (gestes + veille).

## Dépendances (facultatives, en lecture)
`comptes.lister` (sites et compte du panneau de chaque compte), `fastpanel.sites` (les sites du panneau). Absents, le module fonctionne avec ses propres sites ; un panneau muet est dit (`panneau_lu: false`), il ne passe pas pour un parc vide.

## Non porté (à venir)
- **Rapport mensuel par courriel** (`site_rapport*`) : attend le module courrier.
- **Captures d'écran / vignettes**, **détection du CMS** (`site_thumbnail`, `site_cms`) : à porter avec leur préalable (navigateur sans interface, lecture des fichiers du site).
- **Vigilances d'analyse antivirus et de sauvegarde par site** : attendent les scans du panneau (`fp_scan_*`) ; l'audit des sauvegardes existe déjà côté `fastpanel`.
- **Gestes sur le panneau depuis la fiche** (renouveler, redémarrer, restaurer) : ils passent par `fastpanel` ; la restauration exigera l'accord (`sites.accord`) quand elle sera portée.
- **Avis par courriel au propriétaire** (panne, attribution, transfert) : attend le module courrier ; les événements `site.*` sont émis.
- **Alertes ciblées aux propriétaires** : les constats vont aux administrateurs ; l'envoi au propriétaire se fera par le module notifications (destinataires par compte).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
