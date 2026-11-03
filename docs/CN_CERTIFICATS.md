<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Module Certificats V19 — audit, cartographie et spécifications -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Module Certificats V19 — audit, cartographie et spécifications -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=4dbaf0 ▼▼▼ -->
# Module Certificats V19 — audit, cartographie et spécifications

Maquette cliquable : [`maquettes/CN_maquette-certificats.html`](maquettes/CN_maquette-certificats.html) (ouvrir dans un navigateur ; le panneau « Outil de maquette » en bas à gauche change le rôle et l'état de l'écran, il ne fait pas partie de la V19).
Date de l'audit : 02-11-2026. Sources lues : `modules/certificats`, `modules/fastpanel`, `modules/sensorium`, `modules/proactif`, `modules/affichage`, `modules/agenda`, `modules/journal`, `.porte/*/NOTES.md`, `docs/CN_AFFICHAGE.md`, `docs/maquettes/CN_maquette-menus.html`, `interface/CN_habillage.css`, et côté V18 les fonctions `fp_ssl_*`, `ssl_quota_state`, `_site_ssl_renew_impl`.

> **Ce que ce document ne prétend pas.** L'audit est ciblé (les endroits où le mot certificat, SSL, TLS, ACME ou Let's Encrypt apparaît dans la V19 et dans les fonctions SSL de la V18), pas une lecture ligne à ligne de tout Cassandra : la V18 compte plus de mille occurrences. Les zones **non lues** sont listées au §10. Les constats marqués *à confirmer* demandent un essai avant correction.

---

## 1. Où l'on part, et ce que la demande change

La V19 a déjà un module `certificats` (v0.2.0) : c'est une **veille**, pas un cycle de vie.

| Ce qui existe | Ce qui manque pour la demande |
|---|---|
| Sonde horaire du certificat réellement servi (port 443) pour les hôtes du panneau et `certificats.hotes` | Un **registre** des certificats (aujourd'hui : un état par hôte, sans propriétaire, source ni historique) |
| États `valide`, `proche`, `echu`, `inconnu` | `révoqué`, `archivé`, et les états d'une **demande** |
| Registre des émissions Let's Encrypt (quota 5/semaine/domaine) | Demande, validation, émission initiale, révocation, archivage |
| Détecteur d'expiration, signal pour le bureau « Aujourd'hui », constats avec quota restant | Autorités, modèles, clés (métadonnées), workflows, rapports, journal consultable |
| Renouvellement **via FastPanel** (`fastpanel.ssl_renouveler`, avec preuve par la date d'émission) | Un écran de gestes (aujourd'hui aucun écran n'existe : le manifeste déclare `vue_certificats`, gabarit `tableau`) |

**Décision de cadrage proposée** : ne pas inventer un module PKI complet d'un bloc. Chaque certificat porte une **source** (FastPanel, importé, autorité interne, sondé seulement) et les gestes offerts en découlent. Un certificat seulement observé reste en lecture seule. Tout ce qui dépasse ce que FastPanel prouve faire aujourd'hui est marqué **hypothèse** (§8) ou **phase 2** (§9).

## 2. Périmètre : trois blocs distincts

| Bloc | Contenu | Où ça vit |
|---|---|---|
| **A. Module Certificats V19** | registre, demandes, validation, autorités, modèles, clés (métadonnées), rapports, audit, réglages, écrans | `modules/certificats` (étendu) |
| **B. Intégration FastPanel** | lecture `GET /api/certificates`, renouvellement `PUT …/renew/external`, preuve, relève, écarts, erreurs | `modules/fastpanel` (existant) + contrat avec A |
| **C. Impacts sur le reste de Cassandra** | seuils dupliqués, agenda, Sensorium, Proactivité, Sites, DNS, droits, cloisonnement, cloche, bureau | autres modules (§9) |

## 3. Audit : constats

Gravité : **P0** bloquant ou faux en production · **P1** nécessaire pour la demande · **P2** utile · **P3** confort. *Confiance* : lu dans le code (L), déduit (D), à confirmer par essai (C).

### 3.1 Dans le module Certificats
| # | Constat | Gravité | Confiance |
|---|---|---|---|
| A1 | **L'état « échu » est probablement inatteignable par la sonde.** `lire_certificat` utilise `ssl.create_default_context()` : un certificat expiré fait échouer la poignée de main (`certificate has expired`), l'erreur est capturée et l'hôte passe en `inconnu`. Le détecteur et le signal du jour ne voient alors un échu que par la voie FastPanel. Correction : sonder sans vérification de chaîne **puis** juger séparément la validité (V18 `_tls_verifie` distinguait « refusé » de « absent »). Test : `expired.badssl.com`. | **P0** | D, à confirmer (C) |
| A2 | Les échecs d'émission ne sont jamais enregistrés : `emission()` n'insère que `ok=1` (événement `certificat_renouvele`), alors que la migration et la V18 prévoient `ok=0` et que le quota réel de Let's Encrypt compte aussi des **échecs de validation** (limite par heure/hôte). On ne peut pas dire « cinq échecs de suite bloquent ce domaine ». | P1 | L |
| A3 | `domaine_enregistre` est une heuristique maison (suffixes `co/com/org/net/gov/ac` sous un ccTLD), pas la *Public Suffix List*. Le quota est mal attribué pour certains suffixes (ex. `x.gouv.fr`, `asso.fr`). | P2 | L |
| A4 | Aucun cloisonnement par compte : `c.lister(portee=c.TOUT)` partout, `signal_jour` réservé à l'administrateur, menu `role = "admin"`. Un titulaire de site ne voit pas ses certificats ; la règle « l'admin ne voit pas les autres » de Cassandra n'est pas respectée dans l'autre sens. | P1 | L |
| A5 | Un seul droit utile (`utiliser`, défaut vrai) et `administrer` : ni `demander`, `valider`, `renouveler`, `revoquer`. Le manifeste n'a **aucune capacité d'écriture** (toutes `risque = lecture`). | P1 | L |
| A6 | La sonde ne lit que le port 443. Messagerie (IMAP 993, SMTP 465/587), Vaultwarden, Authentik, Dolibarr, OmniRoute, SearXNG derrière nginx : à suivre via `hotes` à la main, et les ports non 443 ne sont pas lisibles. | P2 | L/D |
| A7 | Aucune comparaison nom ↔ SAN : un certificat valide mais pour un autre nom n'est pas détecté. Pas de test de chaîne complète, ni d'algorithme faible. | P2 | L |
| A8 | Le calendrier des échéances n'est **pas porté** (`_ssl_calendar_items`, noté « avec le module agenda »), et l'agenda déclare déjà `certificat` dans `LIENS` sans rien en afficher. | P1 | L |
| A9 | Aucune table pour les certificats, demandes, autorités, modèles, journal : seulement `emissions` et `curseur` (migration 001). | P1 | L |

### 3.2 Seuils et vérités multiples
| # | Constat | Gravité |
|---|---|---|
| B1 | **Cinq seuils** : `certificats.seuil_jours` (21), Sensorium `certificat_jours` (21), FastPanel `ssl_alerte_j` (obsolète, repris à la volée), règle Proactivité « Renouveler un certificat » (30), V18 auto-renouvellement (15). Le manifeste dit que Certificats est le propriétaire unique, mais Sensorium garde son propre seuil. | P1 |
| B2 | **Trois sources de vérité** pour une échéance : sonde 443 (Certificats), base du panneau (`certificate` via FastPanel, dont le champ `expires` est une *durée* de 90 jours, pas une date), collecteur Sensorium (`openssl` sur fichiers). Règle déjà posée : **le certificat servi fait foi**. À rendre visible à l'écran (écarts, §7). | P1 |
| B3 | Doublons de détection : `certificats.expiration_proche`, `fastpanel.certificat_proche`, Sensorium `certificat.<dom>`, Proactivité. Risque de quatre constats pour un même certificat. | P1 |

### 3.3 FastPanel
| # | Constat | Gravité |
|---|---|---|
| C1 | Seuls deux appels sont **prouvés dans le code** : `GET /api/certificates` et `PUT /api/certificates/{id}/renew/external`. Émission initiale, téléversement d'un certificat personnalisé, suppression/révocation : **non prouvés** (le catalogue de 400 points d'entrée est à relire, mémoire « api-fastpanel-carte »). | P1 |
| C2 | Rattachement par nom (`common_name`/`alternative_name`), pas par identifiant : correct, car l'identifiant peut changer à la réémission. À conserver. | — |
| C3 | La preuve d'un renouvellement attend 60 s (`ATTENTE_SSL_S`) ; le geste n'est pas défaisable (`defaire_ssl` rend `None`) : l'écran doit le dire avant, pas après. | P2 |
| C4 | Le droit unique `fastpanel.piloter` couvre « services, certificats, bases, sauvegardes » : trop large pour séparer renouveler / révoquer / émettre. | P1 |
| C5 | `.porte/sites/NOTES.md` : « refaire le SSL devra exiger un droit spécifique (quota LE) ». Pas réalisé. | P1 |

### 3.4 Reste de Cassandra
| # | Zone | Lien avec les certificats |
|---|---|---|
| D1 | **affichage** | `relire_cert` → capacité `certificats.relire_expiration` (admin). Les menus : groupe `secu` « Sécurité », entrée Certificats ; l'ancienne maquette des menus dit « Sécurisation » (écart de libellé, §6). |
| D2 | **agenda** | `LIENS` contient `certificat` ; aucune échéance poussée (A8). |
| D3 | **proactif** | Règle « Hébergement › Renouveler un certificat » (seuil 30 j, disjoncteur). Doit lire le seuil unique et le quota. |
| D4 | **sensorium** | Familles `ssl.*` et `certbot.*`, seuil propre, `ssl_certificates` (openssl). Doublon avec la sonde 443. |
| D5 | **journal** | Source `letsencrypt` (`/var/log/letsencrypt/letsencrypt.log`) : lien « pourquoi un certificat n'a pas été renouvelé ». |
| D6 | **sites** | `TODO(certificats)` dans le portage ; un site doit afficher son certificat et renvoyer ici. |
| D7 | **dns** | Validation DNS-01 (wildcard) et enregistrements CAA ; le manifeste déclare `requiert = ["dns"]`. |
| D8 | **courrier** | IMAP/SMTP chiffrés ; le certificat de `mail.*` n'est pas suivi (A6). |
| D9 | **coffre** (Vaultwarden) | Servi derrière nginx : à suivre ; stockage éventuel d'une clé d'autorité interne (phase 2). |
| D10 | **planifie** | Autorise `certbot certificates` et `openssl` (listes de commandes) ; à aligner si la source `certbot` est gardée. |
| D11 | **voix, vue, notifications** | Mots-clés « certificat/SSL » ; `vue` composera le bureau avec `signal_jour`. |
| D12 | **droits / mandats** | Nouveaux droits (§5) ; un mandat d'agent doit pouvoir renouveler sans révoquer. |
| D13 | **V18 (référence)** | Routes `/api/ssl`, `/api/fp/ssl`, `/api/fp/ssl/issue`, `/api/fp/ssl/check`, `/api/site/ssl_quota` (liste blanche de routes : une route non déclarée répond 404 en silence) ; `fp_ssl_autorenew_*` (désactivé par défaut, car `certbot.timer` fait déjà le travail). |

## 4. Cartographie

### 4.1 Modules et fichiers
`certificats` (CN_module.py, CN_manifeste.toml, migrations/CN_001_init.sql, tests/CN_test_certificats.py) ← `fastpanel` (`ssl_renouveler`, `ssl_sonder`, `certificats`, événement `fastpanel.certificat_renouvele`) ← `dns` (requis) ; consommé par `affichage`, `agenda`, `proactif`, `vue`, `sensorium`, `journal`, `sites`.

### 4.2 Capacités (existantes, à créer)
| Capacité | État | Risque | Droit |
|---|---|---|---|
| `relire_expiration`, `etat`, `quota`, `seuil`, `signal_jour` | existent | lecture | utiliser |
| `lister`, `lire`, `historique` | à créer | lecture | utiliser |
| `demander`, `soumettre`, `valider`, `refuser` | à créer | faible / moyen | demander / valider |
| `renouveler` (délègue à `fastpanel.ssl_renouveler`) | à créer | **fort** (autorité externe, quota) | renouveler |
| `emettre`, `importer` | à créer | moyen / fort | renouveler / importer |
| `revoquer` | à créer | **fort**, non défaisable | revoquer |
| `archiver`, `desarchiver` | à créer | faible, défaisable | administrer |
| `exporter`, `rapport` | à créer | lecture | utiliser |

### 4.3 Événements
Émis : `certificat.proche_expiration`, `certificat.renouvele` (existants) ; à créer : `certificat.echu`, `certificat.demande` (soumise), `certificat.valide`, `certificat.refuse`, `certificat.emis`, `certificat.revoque`, `certificat.archive`, `certificat.ecart` (panneau ≠ servi). Consommés : `fastpanel.certificat_renouvele`, `fastpanel.injoignable`, `fastpanel.acces_refuse`.

### 4.4 Modèle de données (proposé ; l'existant en gras)
- **`emissions`** (id, ts, domaine, ok, acteur) — existe ; ajouter `motif` et enregistrer aussi `ok=0` (A2).
- **`curseur`** (cle, valeur) — existe.
- `certificat` (id, hote, sans JSON, source, autorite_id, modele_id, site_id, etat_force NULL|revoque|archive, auto 0/1, proprietaire_compte, id_panneau, empreinte, algo, emis_le, echeance, derniere_mesure, erreur).
- `demande` (id, hote, sans, modele_id, autorite_id, site_id, demandeur, etat, valideur, motif_refus, justification, cree_le, maj_le).
- `autorite` (id, nom, voie, etat, quota JSON).
- `modele` (id, nom, validite_j, algo, max_sans, renouvelle_a_j, approbation, autorite_id).
- `audit` (id, ts, acteur, acteur_type user|agent|cron, action, objet, resultat ok|echec|refus, note). **Écriture seule**, comme le registre officiel V19.
- Les certificats restent des objets du registre officiel V19 (`c.poser("certificat", …)`), avec provenance ; les nouvelles tables portent ce que le registre ne sait pas dire (demandes, modèles).
- **Aucune clé privée en base.** Seulement algorithme, empreinte, emplacement, âge.

### 4.5 États et transitions
```
Certificat :  [inconnu] ⇄ valide → proche → échu
                         │ renouvellement (preuve)          révoqué (final) ← depuis valide/proche/échu (hors sondé)
                         └──────────────→ valide            archivé ⇄ (désarchivage)  ← depuis tout état non révoqué
Demande    :  brouillon → à valider → validée → émise
                  ↑            │          └→ échec d'émission (quota, panneau, validation DNS)
                  └─ rouverte ← refusée (motif obligatoire)
```
« Expiré » et « archivé » sont des états distincts : un échu reste suivi et alerte ; un archivé n'alerte plus.

## 5. Droits et rôles (proposition)
| Droit | Existe | Admin | Validateur | Opérateur | Lecteur |
|---|---|---|---|---|---|
| `utiliser` | oui | ✓ | ✓ | ✓ | ✓ |
| `demander` | **non** | ✓ | ✓ | ✓ | – |
| `valider` | **non** | ✓ | ✓ | – | – |
| `renouveler` | **non** | ✓ | – | ✓ | – |
| `revoquer` | **non** | ✓ | – | – | – |
| `importer` | **non** | ✓ | – | – | – |
| `voir_cles` | **non** | ✓ | – | – | – |
| `administrer` | oui (sensible) | ✓ | – | – | – |

Règles : un demandeur ne valide pas sa propre demande (séparation des fonctions) ; un agent IA ne reçoit jamais `revoquer` ; `renouveler` passe par Proactivité (palier, fenêtre, disjoncteur) quand il est déclenché par un agent. Le menu n'est plus limité au rôle `admin` mais au droit `utiliser`, et la liste est **cloisonnée par compte** (un titulaire voit les certificats de ses sites).

## 6. Fidélité au design V19 et écarts
### Repris à l'identique
Barre haute verte à six groupes en icônes (titre au survol), colonne de gauche transparente avec entrées et sous-entrées, jetons de `CN_maquette-menus.html` (`--sol --halo --verre --encre --filet --accent …`), polices Public Sans et JetBrains Mono, boutons/pastilles/tuiles/champs/tableaux de `CN_habillage.css` (rayons 10/7/14/16, anneau de focus 3 px), états vide/chargement/erreur/refus, paliers du cadre (tiroir ≤ 900, tableaux en cartes ≤ 560), clair et sombre.

### Écarts, à valider
| # | Écart | Justification |
|---|---|---|
| E1 | **Sous-entrées** de Certificats (Vue d'ensemble, Certificats, Demandes, Autorités, Modèles, Clés, Rapports, Réglages) : la maquette des menus n'en propose que trois (Échéances, Domaines, Renouvellements, « à valider »). | Le cycle de vie complet ne tient pas en trois pages. Billetterie en a 14 : précédent. |
| E2 | Icône : le manifeste dit `lock`, la maquette des menus `cert`. La maquette utilise `cert`. | À trancher. |
| E3 | Libellé du groupe : « Sécurité » (CN_AFFICHAGE §4, validé 18-10) contre « Sécurisation » (ancienne maquette). La maquette suit CN_AFFICHAGE. | Corriger la maquette des menus ou le doc. |
| E4 | Menu `role = "admin"` → droit `utiliser` + cloisonnement. | A4. |
| E5 | **Aucun composant nouveau.** Le kanban des demandes utilise la carte de verre et les pastilles existantes ; le tableau garde l'habillage ; la fenêtre modale reprend le style des `.pop`. Si le design system n'a pas de modale ou de kanban officiels, ces deux-là sont à créer *avant* le développement. | À vérifier : je n'ai pas trouvé de composant modal documenté. |
| E6 | Confirmation par **saisie du nom de l'hôte** pour la révocation (au lieu d'un « OK »). | Geste irréversible ; le projet refuse les `confirm()` volatils (NOTES sites). |
| E7 | Fonts : la maquette charge les polices depuis Google Fonts (comme la maquette des menus) ; la V19 de production ne doit pas dépendre d'un CDN tiers. | Hors périmètre, signalé. |

## 7. Spécifications par écran
Tous les écrans : fil d'Ariane `Sécurité › Certificats › <sous-entrée>`, mêmes états (chargement = squelettes + « Lecture des certificats servis… » ; vide = « Aucun certificat suivi » + deux actions ; erreur panneau = bandeau rouge, dernière relève, gestes désactivés ; permission refusée = écran explicatif + « Demander l'accès » ; quota bloqué = geste désactivé avec date de libération).

**S1 · Vue d'ensemble** — *Qui* : tous (cloisonné). *But* : savoir en dix secondes si quelque chose brûle. Tuiles cliquables (Suivis, Valides, À renouveler, Échus, Inconnus → liste filtrée) ; échéancier en sept tranches ; conformité en pourcentage avec six critères ; « À traiter » (échus, proches, inconnus, avec geste direct) ; quotas par domaine enregistré ; synchronisation FastPanel (dernière relève, nombre de certificats, écarts). *Cas limites* : zéro certificat ; tous inconnus (panneau en panne) ; quota bloqué sur un domaine seulement.

**S2 · Certificats (liste)** — recherche (hôte, SAN, autorité), filtres état/source/autorité/renouvellement, archivés et révoqués en case à cocher, tri par colonne (`aria-sort`), pagination (10), sélection groupée (Relire, Renouveler, Exporter la sélection, Archiver), actions de ligne (Relire, Renouveler), export CSV de la vue filtrée, Importer, Demander. Le renouvellement groupé **ignore et liste** les certificats non renouvelables (sondés, importés, révoqués). Sous 560 px : cartes étiquetées, trois champs visibles.

**S3 · Détail** — en-tête (hôte, état, retour), gestes (Relire maintenant, Renouveler, Exporter la fiche, Archiver/Désarchiver, Révoquer…), onglets Résumé, Chaîne (feuille → intermédiaire → racine), Historique, Liens (site, hébergement, DNS, agenda, constat, Sensorium, journal letsencrypt), Clé (métadonnées, droit `voir_cles`), Audit. *Cas limites* : inconnu (« n'est pas sans certificat »), sondé seulement (bandeau), révoqué et archivé (gestes grisés avec raison en infobulle).

**S4 · Demandes** — colonnes Brouillon, À valider, Validée, Émise, Refusée. Valider/Refuser (motif obligatoire), Émettre (vérifie le quota avant d'appeler l'autorité), Soumettre, Rouvrir. Une demande sur un modèle sans approbation est validée d'office. Wildcard : justification obligatoire et DNS-01 requis (module `dns`).

**S5 · Autorités** — Let's Encrypt (via FastPanel, quota, révocation non prouvée), autorité importée, autorité interne (non retenue, décision Q1 : carte grisée). Chaque carte dit la voie, les gestes et la révocation.

**S6 · Modèles** — validité (≤ 398 j pour un certificat public), algorithme, noms, renouvellement, approbation, autorité par défaut.

**S7 · Clés** — `voir_cles` seulement. Algorithme, empreinte, emplacement, âge. **Jamais** de clé privée affichée, exportée ou collée (l'import la refuse).

**S8 · Rapports et audit** — quatre rapports (Conformité, Échéances à 90 jours, Quotas, Inventaire) en CSV ; PDF à brancher sur le noyau d'export. Journal d'audit filtrable (réussi / échec / refusé) et exportable ; les **refus de permission** sont journalisés.

**S9 · Réglages** (administrer) — Seuils et sonde (seuil 3–90, défaut 21 ; délai 1–30 s, défaut 5 ; hôtes en plus), Renouvellement automatique (renvoie à la règle Proactivité, ne la double pas), Notifications (cloche, courrier, Telegram × six événements), Rôles et droits (matrice), Intégration FastPanel.

**Modales** — Renouveler (liste, quota par domaine, case de confirmation, quatre étapes avec preuve, échec explicite), Révoquer (raison, saisie de l'hôte), Demander (validation de nom, SAN ≤ 20, justification), Importer (PEM public, clé refusée), Archiver, Refuser.

## 8. Intégration FastPanel
| Sens | Appel | Preuve | Gestion |
|---|---|---|---|
| Lire | `GET /api/certificates` | dans le code | liste ; rattachement par nom |
| Renouveler | `PUT /api/certificates/{id}/renew/external` | dans le code | preuve : `issued_at` doit changer (≤ 60 s) |
| Émettre (site sans certificat) | création de certificat Let's Encrypt | **hypothèse H1** | à lire dans le catalogue |
| Importer | téléversement personnalisé | **H2** | idem |
| Révoquer / retirer | suppression ou révocation | **H3** | à défaut : retrait du site + marque « révoqué » localement |
| Clé | réutilisation de la clé au renouvellement | **H4** | à documenter |

Cas limites traités à l'écran : 401/403 (événement `acces_refuse`, gestes désactivés) ; panneau injoignable (dernière relève, bandeau) ; demande acceptée mais date inchangée (échec, quota non décompté) ; quota épuisé (refus avant l'appel) ; identifiant changé après réémission (rattachement par nom) ; durée confondue avec date (`expires` = 90, lire `expired_at`) ; auto-signé du panneau (toléré sur la boucle locale seulement) ; certificat du panneau sans hôte suivi ; hôte suivi absent du panneau.
Synchronisation : relève du panneau toutes les 15 minutes (existant), sonde 443 toutes les heures (existant), bouton « Resynchroniser » qui respecte la limite d'une lecture par hôte et par heure.

## 9. Corrections et adaptations, priorisées
**P0**
1. Sonder l'expiration sans que la vérification de chaîne masque l'échu (A1) — *Certificats*.
2. Seuil unique : Sensorium et Proactivité lisent `certificats.seuil` (B1) — *Sensorium, Proactif, FastPanel*.

**P1** (nécessaires à la maquette)
3. Droits `demander`, `valider`, `renouveler`, `revoquer`, `importer`, `voir_cles` ; scinder `fastpanel.piloter` pour les certificats (A5, C4, C5) — *noyau droits, fastpanel*.
4. Tables et migrations 002 : certificat, demande, autorité, modèle, audit ; enregistrer les échecs d'émission (A2, A9).
5. Cloisonnement par compte et menu au droit (A4).
6. Un seul constat par certificat : fusion des détecteurs (B3).
7. Porter le calendrier des échéances dans `agenda` (A8, D2).
8. Relire le catalogue FastPanel pour lever H1–H4 avant d'écrire le moindre geste d'émission ou de révocation (C1).
9. Écran `vue_certificats` et ses huit sous-entrées (E1).

**P2**
10. Public Suffix List pour le quota (A3). 11. Comparaison nom ↔ SAN, chaîne, algorithme (A7). 12. Ports non 443 : courrier, coffre (A6, D8, D9). 13. Lien Sites ↔ Certificats (D6). 14. Rapport PDF par le noyau d'export. 15. Corriger la maquette des menus (libellé et icône, E2–E3).

**P3** — Autorité interne (phase 2), CRL/OCSP, import par glisser-déposer, étiquettes libres.

## 10. Hypothèses, risques, questions ouvertes
**Hypothèses** : H1–H4 (§8) ; le renouvellement automatique reste le travail de Proactivité ; `certbot.timer` peut déjà renouveler sur Orion (V18 : « désactivé par défaut, car il double »).
**Risques** : consommer le quota Let's Encrypt (un renouvellement groupé mal borné) ; afficher « réussi » sans preuve ; stocker ou afficher une clé privée ; deux seuils divergents qui produisent des alertes contradictoires ; démultiplication des constats ; une autorité interne mal protégée devient pire que pas de PKI.
**Décisions de Drisse (02-11-2026)**
- Q1. Autorité interne : **non** (reste grisée dans « Autorités » ; hors périmètre, la phase 2 ne sera rouverte que sur demande).
- Q2. Validation : droit `valider`, donnable à un rôle ou un groupe ; jamais le demandeur lui-même. Hôte déjà suivi par le panneau : validé d'office (modèle « Site public »). Wildcard et courrier : toujours un validateur.
- Q3. Un titulaire de site **demande pour ses propres sites** (cloisonnement par compte) ; il ne valide ni ne renouvelle.
- Q4. Certificats payants : **rappel seul**, l'achat et le renouvellement se font chez l'autorité.
- Q5. Les hôtes d'Orion et tout ce que la sonde peut joindre entrent au registre, **en totalité**, en « sondé seulement » (lecture seule) tant qu'ils ne sont pas gérés par FastPanel.
- Q6. PDF : par le moteur d'export du noyau ; à défaut, CSV d'abord, PDF ensuite. **À vérifier dans le noyau** avant de promettre.
- Q7. Icône `cert` (le manifeste passe de `lock` à `cert`) ; groupe « Sécurité » (l'ancienne maquette des menus est à corriger).

**Reste à vérifier par essai (pas des décisions)** : A1 (état « échu » via `expired.badssl.com`), H1 à H4 (catalogue FastPanel), existence d'un moteur d'export dans le noyau (Q6).

**Zones non lues, donc non auditées** : front-end V18 (`HTML_TEMPLATE`, écrans SSL), templates nginx et `install.sh`/`deploy.sh` côté certificats, Authentik, SearXNG, Dolibarr côté TLS, `modules/securite`, `modules/webauthn`, `modules/telegram` (TLS sortant), tests existants au-delà du nom de fichier.

## 11. Vérifications faites sur la maquette
Syntaxe JS contrôlée ; huit écrans rendus sans erreur avec deux rôles (administrateur, lecteur ; validateur et opérateur seulement par leurs droits, non parcourus) et cinq états ; parcours testés : renouvellement avec preuve (quota décompté), échec de renouvellement, quota bloqué, lecteur sans droit (boutons désactivés, Réglages refusé), révocation par saisie de l'hôte, validation de nom d'hôte ; aucun débordement horizontal à 375 px sur les neuf vues. Non fait : contrôle de contraste automatisé, test tactile réel, lecture d'écran. Les données sont fictives (domaines `exemple.*`). L'en-tête « BORNE CN » des fichiers du dépôt n'a pas été généré : l'outil d'empreinte du projet doit être passé sur ce fichier et sur ce document.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
