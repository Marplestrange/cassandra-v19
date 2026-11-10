<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : sites — les sites web suivis par Cassandra -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : sites -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.4  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : sites — les sites web suivis par Cassandra -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.4 empreinte=9d2c66 ▼▼▼ -->
# sites — les sites web suivis par Cassandra

Porté de la V18 (`sites_vue`, `site_fiche`, `site_pass`, `site_history`, `site_availability`, demandes/accords, liens, journal), lu en entier.

## Ce que fait le module
- **Portée** : chaque compte voit ses sites (déclarés ici, attribués, inscrits dans sa fiche de compte, ou du panneau pour le compte du panneau lié à sa fiche). L'administrateur voit l'état de tous, jamais le contenu. Un sous-domaine d'un de ses sites est dans sa portée, sauf s'il est suivi à part pour quelqu'un d'autre.
- **Sonde** (toutes les 5 min, budget 240 s, les moins récemment mesurés d'abord) : code, durée chronométrée, certificat lu sur le port 443 (au plus une fois par heure par site, et lu même échu : les jours deviennent négatifs). Si le nom nu ne répond pas, `www.` est essayé. Les redirections ne sont suivies que vers le même site ; une adresse interne n'est jamais interrogée (réglage `sonde_interne`). Panne et retour jugés à la transition ; première observation = découverte ; il faut plusieurs mesures ratées de suite pour dire une panne (réglage `echecs_avant_panne`, 2 par défaut), et elle est datée du premier échec.
- **Ménage** : un site qu'on ne suit plus quitte le registre au tour suivant (plus de constat fantôme) ; le journal des gestes se garde un an au moins, les accords échus et les liens mis de côté trente jours.
- **Constats** : panne, lenteur (réglable), certificat court ou échu (réglable), adossement demandé.
- **Gestes avec preuve et retour** : déclarer, retirer, attribuer, transférer, demander l'adossement au panneau, y répondre (« fait » ou « refusee », rien d'autre), accorder un geste lourd au propriétaire pour un temps borné (7 jours au plus ; restaurer, supprimer, transferer, migrer), lier projets/contacts/machines/notes.
- **Ce qui ne suit pas un site qui change de mains** (retirer, transférer) : les liens de l'ancien compte sont mis de côté, ses accords tombent, sa demande ouverte se ferme. Défaire le geste les remet. Un accord ne vaut que tant que celui qui l'a donné a encore le site.
- **Ce qui ne se déclare pas** : un site du panneau, le site d'un autre, un nom partagé par beaucoup de sites (`github.io`, `gouv.fr`…), le parent du site d'un autre compte.
- **Lectures** : vue (avec vigilances), fiche, historique (sur N heures ou entre deux dates ; au-delà de 720 points ils sont regroupés en gardant le pire de chaque paquet), disponibilité sur N jours (un site non mesuré depuis 2 jours en sort ; une panne en cours compte), série (regroupée par tranches de temps sur une longue période), journal fondu (gestes + veille).

## Les certificats : au module Certificats
La veille des échéances, l'alerte, le seuil et le quota d'émission sont l'affaire du module Certificats (Sécurité). Quand il est là, Sites ne lit plus les certificats lui-même : sa sonde recopie les jours restants (`certificats.etat`) pour sa vue et sa courbe, son détecteur `certificat_court` se tait (c'est `certificats.expiration_proche` qui alerte), et le seuil affiché est celui de Certificats (`certificats.seuil`). En retour, la sonde de Certificats suit aussi les sites déclarés ici. Sans le module Certificats, Sites garde sa propre lecture, son détecteur et son réglage `ssl_court_j`.

## Dépendances (facultatives, en lecture)
`comptes.lister` (sites et compte du panneau de chaque compte), `comptes.moi` (la fiche du compte qui regarde), `fastpanel.sites` (les sites du panneau), `certificats.etat` et `certificats.seuil` (les certificats). Absents, le module fonctionne avec ses propres sites ; un panneau muet est dit (`panneau_lu: false`), il ne passe pas pour un parc vide.

**Le miroir.** `comptes.lister` demande le droit `comptes.gerer` et `fastpanel.sites` le droit `fastpanel.voir` : un compte ordinaire n'a ni l'un ni l'autre. La sonde, qui tourne sans compte, lit donc les deux à chaque tour et en garde un miroir réduit (table `miroir` : compte, sites, compte du panneau ; domaine, propriétaire, certificat, PHP). Un compte ordinaire lit ce miroir (frais d'une heure au plus), et sa propre fiche en direct. Tant que les comptes n'ont jamais été lus, rien ne se déclare : on ne peut pas vérifier que le site n'est à personne.

## Non porté (à venir)
- **Rapport mensuel par courriel** (`site_rapport*`) : attend le module courrier.
- **Captures d'écran / vignettes**, **détection du CMS** (`site_thumbnail`, `site_cms`) : à porter avec leur préalable (navigateur sans interface, lecture des fichiers du site).
- **Vigilances d'analyse antivirus et de sauvegarde par site** : attendent les scans du panneau (`fp_scan_*`) ; l'audit des sauvegardes existe déjà côté `fastpanel`.
- **Gestes sur le panneau depuis la fiche** : renouveler le certificat et restaurer une copie sont portés (`interface/routes/CN_sites.js`, par `fastpanel`) ; la restauration exige d'être le propriétaire ou d'avoir son accord (`sites.accord`), et ne prend qu'une copie de ce compte du panneau. Redémarrer, lancer une sauvegarde et lire les journaux demandent la racine du panneau : pas encore.
- **Avis par courriel au propriétaire** (panne, attribution, transfert) : attend le module courrier ; les événements `site.*` sont émis.
- **Alertes ciblées aux propriétaires** : les constats vont aux administrateurs ; l'envoi au propriétaire se fera par le module notifications (destinataires par compte).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
