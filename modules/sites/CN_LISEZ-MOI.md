<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : sites — les sites web suivis par Cassandra -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : sites -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.2.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : sites — les sites web suivis par Cassandra -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.2.0 empreinte=8f3056 ▼▼▼ -->
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

## Les incidents : une panne est un objet
Une panne confirmée ouvre un **incident** (tables `incidents`, `incident_faits`) : un diagnostic tiré de la dernière mesure (où chercher d'abord), une chronologie (qui a su, qui a fait quoi), quelqu'un qui s'en occupe, une cause. États : `ouvert` → `depannage` (quelqu'un l'a pris) → `retabli` (le site répond, la cause reste à noter) → `resolu`. Si personne n'y a touché, l'incident se clôt seul au retour du site (« revenu seul ») et sa cause se note après coup ; si quelqu'un s'en occupait, il attend sa cause. Gestes, tous avec preuve et retour : `incident_prendre`, `incident_noter`, `incident_connu` (la panne est connue : son constat se tait de 1 heure à 7 jours, l'incident reste ouvert, les mesures continuent), `incident_clore`. `relever` mesure un site tout de suite — la même mesure que la sonde, au plus toutes les trente secondes. Un site déjà en panne à l'arrivée des incidents en reçoit un, daté du début de sa panne ; un site qu'on ne suit plus perd le sien. Un incident résolu se garde un an.

## Le calendrier et l'objectif
`calendrier(domaine, mois)` rend, jour par jour, l'état du site (sans coupure, coupure courte — 98 % et plus —, coupure longue, pas de mesure), ses incidents, ses retours, les gestes faits dessus, puis le mois en chiffres face à son **objectif** de disponibilité (réglage `objectif_pct`, 99,9 % par défaut ; `objectif(domaine, pct)` en pose un propre au site). L'écran passe les débuts de journée tels qu'il les voit (son fuseau) ; un agent passe `mois` « AAAA-MM », lu à l'heure du serveur. Un mois sans mesure le dit : il n'emprunte pas les chiffres d'un autre.

## Les sociétés
Trois étendues : un compte voit **ses** sites ; l'administrateur d'une société, ceux de **sa** société ; le superadministrateur, ceux de toutes. La société d'un site est celle qu'on lui a **attribuée** (table `societes_site`, geste `attribuer_societe`, réservé au superadministrateur) ; à défaut celle de son compte ; à défaut aucune — et seuls les superadministrateurs le voient. L'administrateur d'une société ne lit, ne retire, ne transfère et n'attribue que dans sa société ; les demandes, le journal et les incidents des autres n'existent pas pour lui. Une instance à une seule société ne cloisonne rien.

## La preuve de propriété (sans le panneau)
Le panneau dit à qui est un site ; hors de lui, rien ne le dit. Un compte qui déclare un site (réglage `preuve_exigee`, vrai par défaut) reçoit un **jeton** et doit le rendre visible, au choix : un enregistrement DNS `TXT _cassandra.<site>` valant `cassandra-site=<jeton>`, ou un fichier `https://<site>/.well-known/cassandra-site.txt` qui le contient. Tant que la preuve manque, le site n'est à personne : il n'est pas dans la table `sites`, pas mesuré, ne donne aucune portée, et un autre compte peut encore le réclamer. `prouver(domaine)` vérifie ; trouvée, le site est au compte et les autres déclarations de ce nom tombent. Une déclaration non prouvée tombe en sept jours. L'administrateur déclare sans preuve, et peut attester à la place d'un compte (il attribue). Les sites déclarés avant cette version restent à leur compte.

## Qui est concerné
`concerne()` dit si un compte a quelque chose à voir ici (un site, une déclaration à prouver, ou il administre). Le module Affichage s'en sert : le menu ne montre « Sites » qu'à ceux-là.

## Les certificats : au module Certificats
La veille des échéances, l'alerte, le seuil et le quota d'émission sont l'affaire du module Certificats (Sécurité). Quand il est là, Sites ne lit plus les certificats lui-même : sa sonde recopie les jours restants (`certificats.etat`) pour sa vue et sa courbe, son détecteur `certificat_court` se tait (c'est `certificats.expiration_proche` qui alerte), et le seuil affiché est celui de Certificats (`certificats.seuil`). En retour, la sonde de Certificats suit aussi les sites déclarés ici. Sans le module Certificats, Sites garde sa propre lecture, son détecteur et son réglage `ssl_court_j`.

## Dépendances (facultatives, en lecture)
`comptes.lister` (sites et compte du panneau de chaque compte), `comptes.moi` (la fiche du compte qui regarde), `fastpanel.sites` (les sites du panneau), `certificats.etat` et `certificats.seuil` (les certificats). Absents, le module fonctionne avec ses propres sites ; un panneau muet est dit (`panneau_lu: false`), il ne passe pas pour un parc vide.

**Le miroir.** `comptes.lister` demande le droit `comptes.gerer` et `fastpanel.sites` le droit `fastpanel.voir` : un compte ordinaire n'a ni l'un ni l'autre. La sonde, qui tourne sans compte, lit donc les deux à chaque tour et en garde un miroir réduit (table `miroir` : compte, sites, compte du panneau ; domaine, propriétaire, certificat, PHP). Un compte ordinaire lit ce miroir (frais d'une heure au plus), et sa propre fiche en direct. Tant que les comptes n'ont jamais été lus, rien ne se déclare : on ne peut pas vérifier que le site n'est à personne.

## Limites connues
- Les seuils de portée société (`echecs_avant_panne`, `lent_ms`…) sont lus par la sonde et les détecteurs, qui tournent hors de toute société : c'est la valeur globale qui s'applique à la mesure.
- La preuve par le DNS interroge les serveurs de noms de la machine (`/etc/resolv.conf`) ; sans eux, seule la preuve par fichier est lisible.

## Non porté (à venir)
- **Dépannage par Cassandra** : l'écran écrit la demande dans la conversation (elle lit `sites.incident`, propose un plan, attend l'accord) ; les gestes de réparation eux-mêmes (relancer PHP, recharger nginx) restent ceux du Sensorium et de Sécurité.
- **Fenêtres de maintenance et alertes acceptées du Sensorium**, **avis au propriétaire** (constat adressé à son compte) : lot suivant.
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
