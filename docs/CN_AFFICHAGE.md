<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Module affichage : la disposition (menus du haut, colonne de gauche, menu avatar) -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Module affichage : la disposition (menus du haut, colonne de gauche, menu avatar) -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=d64178 ▼▼▼ -->
# Module affichage : la disposition (menus du haut, colonne de gauche, menu avatar)

Note de conception, 18-10. Maquette de référence (interactive) : `brouillons/maquette-menus-artifact.html`, publiée en page privée.

## 1. Principe

- **`menus` dit QUOI** : l'arbre des entrées que les modules actifs déclarent (parent, ordre, rôle, droit, badge). Il existe déjà.
- **`affichage` dit OÙ et COMMENT** : il range cet arbre dans une disposition (barre haute, colonne de gauche, menu avatar) et la sert à l'interface. C'est le « gestionnaire de menu courant » de la page Info Cassandra : un autre module pourra en livrer un autre.
- L'interface (`shell.js`) ne connaît aucun module : elle dessine ce que `affichage.lire_disposition` rend. Plus de liste d'onglets écrite en dur dans `index.html`.

## 2. Les trois zones

| Zone | Contenu | Source |
|---|---|---|
| Barre haute | ☰, ‹ › ↻, logo, **les 6 groupes en icône** (titre au survol), cloche, thème, avatar | disposition |
| Colonne de gauche | les **entrées** du groupe choisi, chacune dépliable sur ses **sous-entrées** | arbre `menus` |
| Menu avatar | identité, session, paramètres généraux, compte, coffre, raccourcis, verrouiller, déconnecter, version | entrées de zone `avatar` |

Trois niveaux : **groupe** (haut, icône seule : Desk…) → **entrée** (gauche : Accueil…) → **sous-entrée** (gauche, sous l'entrée dépliée : Salon…). Décision 18-10 : les groupes 1 à 6 sont toujours dans la barre haute, représentés par une icône (style de la barre Dolibarr : barre pleine couleur, pictogrammes blancs au trait, petite encoche sous le groupe actif, titre en infobulle ; jetons `--barre`, `--barre-haut`, `--barre-encre`) avec le titre au survol ; 

## 3. Ce qui manque au noyau (contrat)

Les familles actuelles (`socle`, `Flotte`, `Système hôte`, `gestion`…) sont techniques et incohérentes entre modules : on ne s'en sert PAS pour les groupes du haut.

1. **`Menu.groupe`** (optionnel) : id d'un groupe d'affichage. Vide : le groupe vient de la table de repli famille → groupe (§4).
2. **`Menu.zone`** : `principal` (défaut) | `avatar`. Les entrées `avatar` forment le menu de l'avatar.
3. **Groupes déclarés par `affichage`**, pas par chaque module : ordre, libellé et icône sont à l'affichage, les modules s'y rattachent par id. Un module ne crée pas de groupe ; sans groupe connu, il va dans « Modules ».
4. Validation au manifeste : groupe inconnu = avertissement et repli, jamais un échec de branchement.

## 4. Les groupes

Répartition validée le 18-10, groupée par intention (travailler, vendre, faire tourner, protéger, comprendre, déléguer) :

| Id | Libellé | Entrées (module) |
|---|---|---|
| `desk` | Desk | Accueil (Aujourd'hui, Suivre, Courrier, Répertoire, Documents), Agenda. Le Salon n'est plus une page : il vit dans le panneau conversationnel (§7 ter) |
| `metier` | Métier | Billetterie, puis les modules métier futurs |
| `parc` | Parc | Panorama (vue), Flotte, Sites, Hébergement et DNS (fastpanel, dns), Automatismes (planifie) |
| `secu` | Sécurité | Sécurité (securite), Certificats, Sauvegardes, Urgence |
| `obs` | Observatoire | Sensorium, Historique (mesures), Journaux |
| `auto` | Autonomie | Évolution, Proactivité, Mémoire, Agents (agents, mandats) |
| `modules` | Modules | groupe de repli, visible seulement si un module non classé est actif |

- Les groupes `Personnalisé 1` et `Personnalisé 2` sont **supprimés** : un module tiers sans groupe connu va dans « Modules ». La barre ne dépasse pas 7 groupes.
- **Pastille d'alerte sur le groupe** : le pire niveau (`danger`, `alerte`) des badges de ses entrées remonte sur l'icône du groupe.
- **Ordre fixe** : les groupes ne bougent pas selon les modules actifs ; un groupe sans entrée visible pour le compte est masqué.
- Chaque entrée appartient à un module : désactiver le module retire l'entrée (et le groupe s'il se vide). La maquette le montre dans Paramètres › Modules.
- **Repli** : un module sans `groupe` dont la famille n'est pas dans la table va dans un groupe final **Modules** (comme aujourd'hui), jamais perdu.
- Les groupes de l'admin sont réordonnables et renommables : réutiliser `menu_perso` (champs `groupe`, `ordre`, `libelle`, `masque`), global ou par compte.

## 5. Capacités du module

| Capacité | Risque | Rôle |
|---|---|---|
| `lire_disposition(role, compte, ip_session)` | lecture | rend `{groupes:[{id,libelle,entrees:[{id,libelle,icone,badge,ecran,enfants}]}], avatar:[…], reglages_compte}`, filtré par rôle et droits |
| `lire_session()` | lecture, sensible | les lignes de la page Info (§7) |
| `personnaliser_theme`, `personnaliser_widget` | faible | existantes, inchangées |
| `personnaliser_disposition(menu_replie, groupe_ouvert…)` | faible | l'état de la colonne et des replis, par compte (preuve : relire ; retour : valeur précédente) |

- Le calcul de la disposition est **pur** (fichier `disposition.py`, comme `composer.py` de `vue`) : entrées de `menus.lire_menu` + table des groupes + persos → disposition. C'est ce qu'on teste.
- Cache invalidé par `menu_arbre.change` (déjà émis par `menus`) et par `affichage_catalogue.change`.
- `lire_disposition` appelle `menus` par capacité ; `affichage` ne lit pas le manifeste des autres modules pour les menus.

## 6. La colonne de gauche

- **Transparente** : aucun fond de colonne ni de filet. Seuls l'entrée survolée et l'entrée active portent du verre (ombre douce). Raison : un bloc blanc plein jure avec le halo ; le sol est commun et ce sont les cartes qui portent la matière (règle de `design-cassandra`).
- Jetons nouveaux : `--colonne-fond` (transparent par défaut), `--colonne-entree-survol`, `--colonne-entree-active`. Un habillage de module peut les redéfinir ; le contraste du texte sur le halo est vérifié par `affichage.contraste` (déjà là) pour chaque thème.
- ☰ replie/déplie (état gardé par compte). Sur téléphone (≤ 900 px) : tiroir en verre fort avec voile, comme le tiroir actuel (`sb-scrim`).
- Entrée active : suit `switchTab` et l'historique ; ‹ › s'appuient sur l'historique du navigateur, ↻ recharge la scène seule (pas la page).
- Une entrée sans écran ni enfant visible disparaît (règle d'`elaguer` de `menus`, conservée).

## 6 bis. Responsive : posé dès le départ

La disposition est calculée UNE fois côté serveur (mêmes groupes, mêmes entrées) ; seul le rendu change. Les paliers se mesurent sur le **cadre de l'appli** (`data-w`), pas sur la fenêtre : la maquette peut donc montrer tablette et téléphone côte à côte avec la même logique.

| Palier (largeur du cadre) | Barre haute | Colonne de gauche | Panneau ✦ |
|---|---|---|---|
| `xl` > 1500 px | complète | pleine, contenu borné à 1100 px | 3e colonne ancrée, **la colonne reste pleine** |
| `l` 1201–1500 | complète | pleine ; **rail d'icônes** (64 px, infobulles) quand le panneau est ouvert | ancré à droite, scène décalée |
| `m` 901–1200 | complète | idem | idem |
| `s` 561–900 | logo, ☰, ✦, recherche, cloche, avatar ; groupes en dalles | tiroir en verre fort de 280 px au plus (80 % du cadre), voile | par-dessus la scène |
| `xs` ≤ 560 | logo, recherche, cloche, avatar, ☰ ; se masque en descendant | **plus de tiroir** : un bandeau sous la barre (bouton de l'entrée courante ▾ puis **pastilles** défilantes des sous-entrées) et une **feuille de menu** pleine largeur, à hauteur du contenu, qui liste les entrées du groupe et les pages épinglées | **plein écran** (mode conversation) : fermé par ✕ ou en glissant la poignée vers le bas ; réglages repliés derrière ⓘ, **aucune bulle de suggestion** (règle générale, voir §7 ter) : un bouton ✦ dans la saisie ouvre au besoin un menu d'idées et de gestes au-dessus du champ ; saisie collée en bas |

- **Barre du bas (xs)** : deux groupes, le **bouton ✦ central** surélevé, deux groupes, puis « Plus » (feuille en grille) quand il y a plus de quatre groupes. Pastilles d'alerte conservées.
- **Navigation téléphone** : toucher un groupe de la barre du bas y va ; toucher le groupe déjà actif, le bouton de l'entrée ou ☰ ouvre la feuille de menu ; toucher une pastille change de page sans rien ouvrir.
- **Gestes** : sur tablette, glisser depuis le bord gauche ouvre le tiroir et glisser vers la gauche le ferme ; glisser la poignée vers le bas ferme le panneau, tirer la scène vers le bas actualise (remplace ↻).
- **Tableaux sous 560 px** : chaque ligne devient une carte étiquetée (trois champs visibles, les suivants repliés, un toucher déplie). Une cellule d'action reste toujours visible.
- **Tactile** : décidé par `pointer: coarse` et non par la largeur : cibles de 44 px, pas de survol (donc pas d'aperçu au survol des dalles). Un grand écran tactile garde des boutons larges.
- **Cartes qui suivent leur conteneur** (`container-type: inline-size`) : deux colonnes de cartes et heures masquées quand la scène est étroite, même sur grand écran avec panneau ouvert.
- **Économie** : le verre dépoli (`backdrop-filter`) est coupé par `prefers-reduced-transparency` ou par le réglage « Verre dépoli » du menu avatar ; les surfaces deviennent opaques.
- **Préférences par appareil** (`localStorage`, jamais par compte) : thème, habillage, écran allégé, verre, mode tactile.
- **Zones sûres et clavier** : `100dvh`, marges `env(safe-area-inset-*)`, champ de saisie du panneau collé au bas de la feuille.
- **Contrôle** (automatisé dans la maquette) : trois cadres (ordinateur, tablette 768, téléphone 390) × clair/sombre × cinq groupes, aucun défilement horizontal ; à refaire à 200 % de texte et sur un vrai appareil tactile avant de coder.
- Le contrat ne dit rien du rendu : `lire_disposition` rend, par entrée, un `prioritaire` (booléen) pour décider qui reste dans la barre du bas ; défaut = l'ordre déclaré.

## 7. Le menu avatar (groupe 9)

On **garde le menu de l'avatar actuel** (identité, session, apparence, écran allégé, coffre, paramètres, raccourcis, verrouiller, déconnecter) et on le range en sections dans cet ordre :

Décision 18-10 (Drisse) : le menu de l'avatar **reste celui de l'ancienne interface**, avec seulement **deux entrées ajoutées** : **Modules / Applications** (la page Modules de Réglages) et **Société / Organisation**, une page à quatre rubriques en colonne de gauche, chacune un tableau (libellé, valeur) avec son bouton Enregistrer : **Mon organisation** (raison sociale, devise principale, pays, adresse, code postal, ville, département / canton, téléphone, tél portable, fax, email, web, code-barres, logo, logo carré, note), **Réseaux sociaux** (Facebook, Instagram, Linkedin, Skype, Snapchat, Twitter, Whatsapp, Youtube : identifiant et url), **Heures d'ouverture** (un champ par jour) et **Sous-traitants** (un tableau pour le fournisseur du service de comptabilité, un pour le fournisseur informatique). Un administrateur seulement les règle ; les autres comptes ne lisent que le nom et les logos. Le nom et le logo s'affichent en tête de la barre, le favicon suit le logo carré (ou le logo), par défaut le toit de Cassandra. Le reste est inchangé : identité, session, apparence, écran allégé, Mon coffre-fort, Paramètres généraux, Raccourcis clavier, Verrouiller, Se déconnecter. **Modules et Applications** est une page à part entière (ce n'est plus une vision de Réglages) : titre et légende comme les autres pages, fil d'Ariane (Paramètres › Modules et Applications › famille), et une colonne de gauche propre à la page qui classe les modules par famille (Tous les modules, Socle, Sécurité, Réseau…, avec leur nombre) ; sur téléphone, ces familles deviennent les pastilles du bandeau. Le catalogue, les fiches, l'activation et les réglages sont ceux de l'ancien écran (`CASS.modulesUi`, exposé par `modules-ui.js`). **Info Cassandra** n'est pas une entrée : c'est un lien tout en bas, à côté du numéro de version. L'apparence perd ses initiales : un thème en icônes (clair, crème, sombre, système) et un sélecteur d'habillage (Cassandra, Ardoise, Papier, puis ceux des modules).

Apparence (segments clair / crème / sombre / thèmes de modules) et Écran allégé restent dans le menu (blocs actuels) ; le bouton thème de la barre haute reste un raccourci vers le même sélecteur.

**Page Info Cassandra**
- Cassandra : version actuelle (noyau), dernière version stable en dépôt, version d'installation initiale.
- Session : session de, adresse IP, entité de connexion, mode d'authentification, connecté depuis, connexion précédente, thème courant, gestionnaire de menu courant, langue, fuseau horaire, navigateur, présentation, écran.
- Origine des valeurs : serveur (`lire_session`) pour compte, IP, entité, authentification, connexions ; navigateur pour fuseau, navigateur, écran, présentation. **L'adresse IP vient de la connexion** (`ip_session` injecté par la passerelle, jamais de la demande).
- « Dernière version stable en dépôt » suppose une lecture réseau sortante : voir questions ouvertes.

## 7 bis. Fonctions de confort retenues (maquette v6)

- **Logo en tête, avec anneau d'état** : vert tout est en ordre, orange à regarder, rouge urgent (pire badge des modules visibles par le compte).
- **Dalles en relief** sur toute la hauteur de la barre ; pastille d'alerte par groupe ; infobulle « Titre · Alt+n » ; Alt+1 à 9 ouvre le groupe.
- **Aperçu au survol d'une dalle** (ordinateur seulement) : les entrées du groupe et leurs six premières sous-entrées avec compteurs, « Tout voir (n) » au-delà.
- **Pages épinglées** : étoile dans le fil d'Ariane ; section « Épinglés » en tête de la colonne, par compte (objet `menu_perso`, champ `epingle`).
- **Panneau Cassandra** (bouton ✦) : tiroir à droite qui connaît la page courante et propose des gestes. Chaque acte montre risque, périmètre, **preuve** et **retour** ; un geste de risque moyen exige une confirmation ; le retour est un bouton. C'est l'affichage des capacités du noyau (`risque`, `preuve`, `retour`, `paliers`), pas une logique propre à l'interface.
- **Palette Ctrl+K** : pages, **récents**, et **actes** (verbes) qui ouvrent le panneau ; les actes réservés à l'admin disparaissent pour un compte.
- **Modules activables à chaud** : l'écran Modules ajoute ou retire entrées et groupes sans recharger.
- **Habillages** : Ardoise et Papier changent les jetons de la barre et des dalles (`--barre*`, `--dalle*`).

## 7 ter. Le panneau conversationnel remplace le Salon

Décision 18-10 : plus d'entrée « Salon ». Le bouton ✦ de la barre haute ouvre un tiroir à droite, avec **trois options** qui se règlent seules :

| Option | Quand | Réglages |
|---|---|---|
| **Itare** | pages du groupe Desk, et toujours pour un compte non admin | pris automatiquement dans les réglages du **compte** (modèle, mémoire personnelle, ton, accès : ses documents, son courrier, son agenda) ; rien à choisir dans le panneau, lien vers Mon compte |
| **Cassandra** | tous les autres groupes (admin seulement) | tout le parc ; palier d'autonomie (raconter / auto) ; ses actes montrent risque, périmètre, preuve et retour |
| **Invités** | à la demande | fil à plusieurs : on invite Itare ou un agent (Veille, Billetterie, Courrier…) ; chaque réponse porte le nom de son auteur et utilise les accès de cet agent |

- Le mode **suit la page** : changer de groupe remet l'automatique ; un choix manuel dure jusqu'au prochain changement de groupe. Un indicateur « auto / manuel » le dit.
- Un acte de Cassandra demandé depuis le Desk (par la palette) bascule le panneau en manuel sur Cassandra.
- **Visibilité** : ouvrir le panneau **replie la colonne de gauche** et décale la scène (le panneau est ancré, il ne recouvre rien) ; le fermer rouvre la colonne, sauf si tu l'as repliée ou rouverte toi-même pendant ce temps (ton choix manuel prime). Sur tablette et téléphone, le panneau passe par-dessus la scène et la colonne reste un tiroir.
- **Pas de bulles de suggestion, nulle part** (décision 18-10) : rien ne s'affiche de lui-même dans le fil ; un bouton ✦ à gauche du champ de saisie ouvre, à la demande, un menu d'idées et de gestes proposés selon la page et l'interlocuteur (il se ferme au choix, au clic ailleurs ou par Échap). Même comportement à toutes les tailles.
- **Sélecteur de fil** (sous le nom de l'agent, menu déroulant) : trois choix.
  1. **Page en cours** (défaut) : un fil lié à la page (clé groupe | entrée | sous-page), créé au premier message ; il **suit la navigation** : changer de page change de fil, y revenir retrouve son fil.
  2. **Nouveau fil** : vide, nommé « Nouveau fil » puis par les premiers mots du premier message.
  3. **Fils récents avec cet agent** : les fils déjà tenus (titre, date, nombre de messages, mention « page » s'il est lié à une page), classés du plus récent ; un fil vide n'est jamais listé.
  Choisir un fil précis **fige** la conversation : la navigation ne le quitte plus tant qu'on ne repasse pas sur « Page en cours ». Chaque interlocuteur (Itare, Cassandra, Invités) a **ses propres fils** ; un acte reste dans son fil avec sa preuve et son retour. Le menu se ferme au choix, au clic ailleurs ou par Échap, et s'exclut avec le menu d'idées. Côté noyau : les fils sont les fils du module `salon` (objet fil, borné au compte pour Itare), `affichage` ne fait que les lister (`affichage.lire_fils(agent, compte)`) et lier un fil à une page (`page_cle`).
- **Idées dynamiques** (menu ✦) : jamais une liste figée. À chaque changement d'état, le panneau recalcule au plus quatre idées, classées par urgence, chacune avec sa **raison** (« expire dans 6 j », « 3 non lus », « 9 h de retard ») et, pour un acte, son risque. Entrées du calcul : la **page** et la sous-page courantes, l'**état réel** des modules (échéances, compteurs, alertes, tâches), l'**heure** (matin / fin de journée), ce qui vient d'être **fait** (l'idée disparaît, une idée de suivi la remplace, et elle revient si on annule) ou **refusé** (elle ne revient pas dans la session). L'urgence globale reste devant sur toutes les pages ; l'idée propre à la page passe devant les idées ordinaires. Un **point orange** sur ✦ signale une idée urgente, sans rien afficher d'autre.
- **Côté noyau** : `affichage.lire_idees(contexte, compte)` rend `[{id, titre, raison, score, acte?}]`. Chaque module déclare ses **signaux** (déjà au contrat : `[[signaux]]`, voir le module `jour`) et, au besoin, un acte proposable ; `affichage` ne connaît aucun module, il classe. Le score est borné et expliqué (une idée sans raison n'est pas affichée). Les idées d'Itare ne lisent que les signaux du **compte** ; celles de Cassandra, tous ceux du parc.
- **Un fil par option** : Itare, Cassandra et Invités gardent chacun leur conversation.
- Côté noyau : le module `salon` reste la source des fils ; `affichage` ne fait que choisir l'interlocuteur par contexte (`lire_disposition` rend `interlocuteur_auto` selon le groupe et le rôle). Itare s'exécute avec l'identité du compte (cloisonnement par compte conservé : l'admin ne voit pas les fils des autres comptes).
- À prévoir : le panneau en plein écran sur téléphone ; l'historique des fils (liste) ; les mentions @agent dans un fil d'invités.

## 8. Transition depuis l'interface actuelle

`shell.js` filtre aujourd'hui les `.sb-item[data-tab]` de la V18 et ajoute un groupe « Modules ». Les écrans V18 s'ouvrent par `switchTab(nom)` et ne seront pas réécrits.

1. **Table de pont** `onglet V18 → entrée de menu` (dans `interface/`, à côté de `CASS.couvre`) : tant qu'un module ne déclare pas son menu, l'entrée est fabriquée depuis l'onglet V18 existant, dans le bon groupe.
2. Le nouveau rendu appelle `switchTab` avec les noms V18 ; aucun écran n'est touché.
3. Quand un module déclare ses `[[menus]]` avec `groupe`, la ligne du pont est retirée.
4. Ancien rail (`#sidebar`, groupes repliables) gardé derrière un interrupteur `disposition = "v18"` le temps de valider : la refonte doit pouvoir se défaire.

## 9. Phases

1. **Contrat noyau** : `Menu.groupe`, `Menu.zone` dans `manifeste.py`, validation, bancs.
2. **`disposition.py` pur** + capacités `lire_disposition`, `lire_session`, bancs (groupe vide masqué ; orphelin ; rôle ; droit ; repli « Modules » ; perso ; entrée sans écran).
3. **Déclarations** : `groupe` posé sur les `[[menus]]` des modules existants (une passe) ; entrées de zone `avatar` pour `modules`, `comptes`, `coffre`.
4. **Interface** : `interface/disposition.js` + `disposition.css` tirés de la maquette, **responsive inclus dès cette phase** (§6 bis : icônes seules, tiroir, barre du bas) ; table de pont ; interrupteur v18/v19.
5. **Page Info** + `lire_session` ; état de la colonne par compte.
6. **Essai local** (`python main.py demarrer`, port 9000) au Browser pane : clair/sombre, téléphone 375 px, compte non admin ; **puis** déploiement Amizo, module non activé tant que tu ne l'as pas décidé.

## 10. Questions ouvertes (à trancher par toi)

1. **Suivre** (Accueil) : projets et tâches ? Agenda ?
2. **Automatismes** (crons, module `planifie`) et **Hébergement** (FastPanel) ne sont pas dans ton plan : sous Sites ? sous Sécurisation ? dans le menu de gauche de Sites ?
3. **Mon Bureau**, la page d'arrivée actuelle : devient-il Accueil › Salon, ou Accueil a-t-il sa propre vue d'ensemble ?
4. **Menus de gauche** de tous les modules hors Accueil et Billetterie : ceux de la maquette sont des propositions tirées des onglets actuels.
5. *(tranchée)* Plus de groupes Personnalisé : un seul groupe « Modules », visible à la demande.
6. **Dernière version stable en dépôt** : lecture de GitHub par le serveur (sortant, à plafonner) ou valeur posée par le module `modules` ?
7. Le **logo de la société** : réglage admin (téléversement) dans `affichage`, ou dans `reglages` ?
8. **Rôle utilisateur** : voit-il la même barre, avec seulement ses groupes non vides ? (proposition : oui, filtrée par `role`/`droit`).
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->

## Le plan du jour (0.4.0)

La page **Aujourd'hui** (`interface/CN_aujourdhui.js`) est un cadran : un anneau de la journée (agenda, tâches placées, heure présente), la suite, trois chiffres (temps libre, tâches faites, journée passée), une frise à trois voies (Agenda, À faire, Échéances) et les tâches **à placer**.

Seul le **plan** s'écrit : deux capacités du module `affichage`, pour le compte qui agit et nul autre.

- `affichage.lire_plan(jour)` — les blocs posés sur la journée (lecture).
- `affichage.modifier_plan(jour, blocs)` — remplace les blocs : `id`, `titre`, `deb` (minutes depuis minuit), `duree` (5 à 480), `tache` (numéro de tâche, facultatif), `fait`, `couleur`. Au plus 60 blocs ; un plan vidé se retire ; les plans de plus de 30 jours s'effacent. Palier « faible », retour = restaurer le plan précédent.

Les agendas, tâches, rappels et alertes restent ceux de l'ancienne interface. La durée d'une tâche (sa « charge » serveur est un poids, pas des minutes) est retenue par le navigateur ; le plan, lui, est au serveur. Le placement automatique est côté page pour l'instant ; il deviendra un point d'évolution (EC) quand son classement s'apprendra.

## Le réglage d'Aujourd'hui (0.5.0)

Par compte, pas par navigateur : `affichage.lire_reglage_jour` et `affichage.modifier_reglage_jour` (objet `reglage_jour`). Il porte l'heure où la journée commence et finit (`debut`, `fin`, 0 à 23 ; une fin avant le début passe minuit ; 0 → 0 est le cadran de 24 h par défaut), la durée de concentration (`focus`, 1 à 240 min) et la durée des tâches (`durees`, {numéro: 5 à 480 min}, 0 retire). Ce qui n'est pas dit ne change pas. Ce qu'un navigateur avait retenu avant (localStorage) passe au compte à la première ouverture, puis n'est plus lu.
