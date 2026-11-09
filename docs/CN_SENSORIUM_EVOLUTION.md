<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Évolution du Sensorium : des mesures de première classe, enfichables, cloisonnées -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Évolution du Sensorium : des mesures de première classe, enfichables, cloisonnées -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=d89221 ▼▼▼ -->
# Évolution du Sensorium : des mesures de première classe, enfichables, cloisonnées

Statut : note de conception, rédigée AVANT le code (09-11-2026). Chaque point porte un statut : **[décidé]** (je l'implémente, c'est écrit ici pourquoi),
**[proposé]** (non implémenté ou à valider par Drisse), **[à vérifier]** (je n'ai pas pu le prouver ici).
Public : les modules à venir (Serveur DNS, Kino, Bibliothèque, modules métier). Cadre : `docs/CN_NEXUS.md`, `docs/CN_MODULES_DEVELOPPEUR.md`.

## 0. Ce que j'ai constaté (lu dans le code ET essayé)

* **[constaté par essai] Fuite d'infrastructure vers un compte ordinaire.** Les lectures du Sensorium (`monde`, `entite`, `etat`, `historique`, `changements`, `demon`,
  `modules`, `gestes_journal`, `fenetres`, `erreurs_navigateur`, `metriques`, `sante`, `serie`) ne déclarent aucun `droit`. L'exécuteur ne vérifie un droit que si la capacité en
  déclare un (`if compte and c.droit`, `noyau/CN_executeur.py`). Essai sur un vrai noyau monté (comptes `premier` = administrateur, `simple` = ni administrateur ni superadministrateur, société « 1 ») :
  `simple` obtient `sensorium.monde`, `entite`, `etat`, `demon`, `gestes_journal`. Seule `secu` (qui déclare `voir_securite`) le refuse. Le menu « Sensorium » est réservé aux administrateurs,
  mais un menu n'est pas une porte : la capacité reste appelable. Un second chemin : le module Mémoire lit `sensorium.monde` au nom de l'utilisateur pour la « perception » qu'il met dans le contexte d'un modèle.
* **[constaté par essai] Le Sensorium est un module « d'instance »** (`instance = true`) : `Identite.module_ouvert` ne l'ouvre que dans la société principale (« 1 »). Un compte d'une autre société reçoit
  donc déjà « module non ouvert » pour TOUTE capacité du Sensorium. La fuite du §0 concerne les comptes ordinaires de la société principale (et, plus tard, un module installé qui lirait le Sensorium au nom d'un utilisateur).
  Conséquence de conception : une vue minimale servie par le Sensorium lui-même ne serait jamais joignable depuis une société secondaire ; elle l'est par `executer_lecture` depuis un module OUVERT dans cette société
  (la lecture « interne » saute le contrôle d'ouverture du module mais applique le droit du compte et la société de l'acte) : voir §6.
* Le registre d'objets a bien une colonne `compte` (pas de société) ; l'infrastructure est de l'instance, pas d'une société.
* Il existe déjà un module **`mesures`** (courbes, habitude, écarts, **prévision**, verdict) alimenté par les `[[mesures]]` des manifestes + une capacité `serie`. La « prévision généralisée » (point 7) doit
  s'appuyer sur lui et sur le point `pente`, pas le recréer.
* Le collecteur mesure déjà : la synchronisation NTP (`timedatectl`, ligne ~2891), le « DNS local » (`dns-local.conf`, `noms.hosts`). Il ne mesure pas la dérive d'horloge, la présence d'un résolveur,
  la comparaison résolveur local / public, ni les réponses « puits ».
* Un acte d'agent démarre au premier palier de la capacité (`paliers[0]`) ; une capacité d'alimentation doit donc déclarer `paliers = ["auto"]` pour ne pas être « racontée » sans rien faire.

## 1. Principes

1. **Additif, rétrocompatible** : aucune capacité existante ne change de nom, d'arguments ni de forme de réponse. Le seul retrait de droit est la correction de sécurité du §2.
2. **Le noyau ne change pas.** Suivi, relations, capteurs et vues vivent dans la base du module Sensorium (migration 004) ; aucune évolution du registre ni du bus n'est nécessaire. [décidé]
3. **Le silence n'est jamais un « ok »** : l'état d'une mesure est un tri-état `ok` / `alerte` / `inconnu`. Une lecture trop ancienne, de confiance trop basse, ou jugée avec une horloge non fiable donne `inconnu`.
4. **Le cloisonnement se décide à la déclaration, pas à la lecture** : une clé est invisible par défaut (`instance`) ; elle n'est montrée à une société que si un administrateur l'a publiée pour elle.

## 2. [décidé] Fermer la fuite : le droit `voir_infra`

Nouveau droit `voir_infra` (sensible, jamais attribué par défaut). Posé sur toutes les lectures d'infrastructure listées en §0 y compris `serie` (décision de Drisse, plus bas). Un administrateur passe tous les contrôles de droits
(constaté : l'essai du §0 le montre pour `premier`), donc **aucun administrateur ne perd rien**. Conséquences assumées :

* un compte non administrateur n'obtient plus `monde`, `etat`, etc. ; le module Mémoire, qui lit `sensorium.monde` au nom de l'utilisateur, reçoit « aucun relevé disponible » (c'est son comportement déjà prévu) : le contexte d'un
  modèle n'embarque plus l'infrastructure pour un utilisateur ordinaire ;
* `vue` n'appelle `sensorium.metriques` et `sensorium.sante` que pour un administrateur (`admin_seul` vrai dans `SOURCES`) : rien à changer ;
* **`serie` : [décidé par Drisse, option A, Sensorium 0.2.3]** la capacité exige le droit `voir_infra` (sensible, jamais par défaut, les administrateurs l'ont d'office). Le module `mesures` l'appelle au nom du compte qui regarde ses courbes : un
  compte qui a `mesures.voir` mais pas `sensorium.voir_infra` ne voit donc plus les courbes de la machine. Il reste UNE opération de réglage hors du code : un administrateur accorde `sensorium.voir_infra` au groupe qui détient
  `mesures.voir` (rien dans le dépôt n'attribue `mesures.voir` à un groupe : c'est un réglage d'instance). Bancs : `Fuite.test_serie_*` (compte ordinaire refusé, compte qui a le droit accepté et pas un autre, administrateur accepté).
  Options écartées : (B) droit propre `voir_courbes`, par défaut vrai (ne fermait rien) ; (C) laisser ouvert.
* **[à vérifier]** l'interface (pages Système, Tableaux) n'a pas pu être exercée ici ; ces pages sont derrière un menu d'administrateur.

## 3. [décidé] Mesures de première classe : tri-état, fraîcheur, confiance

Une mesure est identifiée par une **clé** `[a-z0-9_.:/-]{1,120}`, dans un espace de noms : `monde.<wkey>` (une ligne du modèle du monde du collecteur) ou `<espace>.<nom>` (un capteur enfichable, §5).

Pour chaque lecture : `valeur` (nombre ou texte court), `gravite` (`ok`, `warning`, `critical`, ou vide : alors calculée par les seuils du capteur), `observe_a` (l'instant revendiqué par l'émetteur), `recu_a` (l'instant où **nous**
l'avons reçue, avec notre horloge), `confiance` (0 à 1, déclarée par l'émetteur, plafonnée par nous).

État calculé (fonction **pure**, `CN_mesures_etat.py`, testée sans noyau) :

| situation | état | raison |
|---|---|---|
| aucune lecture | `inconnu` | « jamais lue » |
| notre horloge n'est pas fiable (avant 2025, ou a reculé) | `inconnu` | « horloge non fiable » |
| `maintenant - recu_a > fraicheur_s` | `inconnu` | « muette depuis … » |
| `confiance < confiance_min` du capteur | `inconnu` | « confiance insuffisante » |
| gravité `warning`/`critical` | `alerte` | |
| sinon | `ok` | |

La fraîcheur se juge sur `recu_a` (notre horloge), **jamais sur `observe_a`** : un satellite sans horloge matérielle (Raspberry Pi sans pile, Kino) peut dire n'importe quelle heure. Un écart `|observe_a − recu_a| > 300 s` est
gardé (`decalage_s`) et abaisse la confiance, sans jeter la lecture. `depuis` = l'instant de notre dernier **changement d'état**, pas de la dernière lecture.

## 4. [décidé] Événements de mesure sans inonder le bus

Registre des clés **suivies** (`sensorium_suivies`) : (clé, suiveur, motif). `mesure.change {avant, apres, depuis, raison}` n'est émis **que** pour une clé suivie, et au plus une fois toutes les 30 s par clé
(les va-et-vient plus rapides sont fusionnés : `avant` reste le dernier état ANNONCÉ). Un moteur périodique (`suivi_mesures`, 30 s) fait passer en `inconnu` une clé suivie dont l'émetteur s'est tu : sans lui, un capteur muet ne
produirait jamais d'événement. Droit dédié `suivre` (sensible). Plafonds : 50 clés par suiveur, 500 au total. Le module Mémoire écoute déjà des événements nommés ; il n'en dépend pas (il relit).

## 4 bis. [décidé, fait] Un suivi ne vaut pas droit de regard à vie

À chaque annonce, la visibilité de la clé est revérifiée pour CHAQUE suiveur (publication courante, société de son compte ; un administrateur ou un compte système voit tout). Un suiveur qui ne voit plus la clé ne reçoit RIEN ;
son suivi n'est pas retiré, il est **muet** (compteur `evenements_masques`) et redevient actif si la clé est republiée, avec un `avant` exact. Un suiveur non privilégié reçoit la raison COURTE (« muette », « confiance insuffisante »),
comme la vue minimale : jamais la fraîcheur attendue ni les niveaux de confiance. **Limite** : le droit `suivre` est vérifié à la souscription, pas à chaque annonce (le service des droits n'est pas lisible depuis un module sans permission dédiée) ;
retirer ce droit à un compte n'arrête pas un suivi existant tant que la clé reste visible pour lui. [à traiter si le besoin se présente]

## 5. [décidé] Capteurs enfichables : le contrat

Un capteur se **déclare** (`capteur_declarer` : clé, libellé, unité, `fraicheur_s`, seuils `alerte`/`critique`, sens `pire` haut ou bas, `confiance_min`) puis **s'alimente** (`capteur_alimenter` : jusqu'à 50 lectures par appel).
Le collecteur root n'est pas touché. Propriété : la clé commence par un **espace** (`dns`, `kino-lyon`…) lié au **compte** qui l'a déclaré en premier ; un autre compte ne peut ni déclarer ni alimenter cet espace.
Pour un module du noyau l'appelant est le compte système « noyau » (partagé) : un module installé tourne déjà dans le processus avec ses droits (`docs/CN_MODULES_DEVELOPPEUR.md`). **L'isolation réelle viendra avec un compte machine par
nœud Kino** : chaque nœud aura son compte, donc son espace. Droits `alimenter` (sensible). Plafonds : 200 capteurs, 50 par compte, 1 lecture par seconde et par clé (les autres sont comptées « refusées »),
500 points d'historique par clé et 14 jours. Le protocole réseau de Kino (signature, transport) n'est **pas** défini ici ; ce contrat est ce que ce protocole appellera. [proposé pour la suite]

## 6. [décidé] Vue minimale à droit propre, sûre entre sociétés

* `sensorium.vue_minimale` et `sensorium.mesure_etat` (droit `voir_etat`, attribué par défaut) ne rendent que `{cle, libelle, etat, depuis}`. Jamais la valeur, le détail, l'hôte, l'unité, la confiance ni l'émetteur.
* Une clé a une `visibilite` : `instance` (défaut : administrateurs et moteurs seulement), `societes:<id,id>` ou `toutes`. Seul un administrateur la change (`mesure_publier`, droit `publier`, sensible, avec preuve et retour).
* Une clé inconnue, une clé non publiée pour la société du demandeur et une clé suivie mais muette rendent la **même forme** `{etat: "inconnu"}` quand c'est le droit qui manque : pas d'oracle d'existence.
  (Une clé visible et muette dit `inconnu` avec sa raison ; une clé invisible dit `inconnu` sans raison.)
* La société est celle de l'acte (`ctx.societe`, posée par l'exécuteur à partir du compte) ; elle n'est jamais lue d'un argument.
* **Qui peut appeler quoi** : un compte de la société principale appelle `sensorium.vue_minimale` directement ; un compte d'une société secondaire ne le peut pas (module d'instance fermé, constaté) et passe par un module ouvert dans sa société
  qui fait `ctx.executer_lecture("sensorium.vue_minimale")` : la société de l'acte est alors celle du demandeur, le droit `voir_etat` est celui de son compte, et la publication décide du reste. Les bancs le simulent par `_intro["lecture"]`.
* Le détail (`mesure_detail`, valeurs, historique, confiance) exige `voir_infra`.

## 6 bis. [décidé, fait] La règle du compte vide

`privilegie()` vaut vrai pour un compte vide (un moteur du noyau), pour les comptes système (`noyau`, `cassandra`) et pour un administrateur. Chemins qui appellent le Sensorium avec un compte vide ou système, et règle de chacun :

| Chemin | Qui | Règle | Banc |
|---|---|---|---|
| lecture inter-modules faite par un moteur (`ctx.executer_lecture` hors capacité) | tout module | lit en privilégié ; **s'il travaille pour quelqu'un il DOIT passer `pour`** (un compte, ou `*` = personne) et ne regarde alors jamais plus que lui | `Privilege` |
| relecture de la Mémoire (`entretien`) | module Mémoire | lit au nom du PROPRIÉTAIRE du souvenir (`compte:x` -> x ; `partage`, `itare`, `cassandra` -> privilégié, un administrateur l'a écrit ; autre -> `*`) | `test_fuite_la_relecture…` (échouait avant) |
| `ctx.agir` depuis un moteur | module déclarant `agir_moteur` | agit sous le compte `noyau` : privilégié ; l'étendue est la liste `agir_moteur` du manifeste | `ViaUnModule` |
| capacité appelée par un utilisateur | tout compte | JAMAIS privilégié sauf administrateur ; `pour` ignoré | `Privilege` |
| futur module Bibliothèque | à définir | mêmes règles : s'il lit depuis un moteur (page qui se périme), il passe `pour` = l'auteur de la page ; sinon une page « vivante » montrerait à tous ce que son auteur seul voit | — |

`pour` n'est honoré que pour un appelant privilégié ; un compte ordinaire qui le passe n'en tire rien (jamais la vue d'un autre). Les autres lectures (`mesure_detail`, `vue_minimale`) n'ont pas de `pour` : elles se lisent au nom de l'acte.
**Reste ouvert** : un module installé qui lit en moteur sans `pour` voit tout, et c'est inévitable tant qu'il tourne dans le processus avec ses droits (même constat que `docs/CN_MODULES_DEVELOPPEUR.md`).

## 7. [décidé] Relations entre objets

Plutôt que d'élargir le registre du noyau (intouchable, et chaque module le lit), les relations vivent dans le Sensorium : `sensorium_liens (de, relation, vers)` avec des références `type/id` libres
(`site/exemple.test`, `monde.ssl.exemple.test`, `service/nginx`). Capacités `lien_poser` / `lien_retirer` (droit `alimenter`), `liens`, `impact` (qui est touché si X tombe : parcours borné, profondeur 6, 200 nœuds, sans boucle infinie).
**Cloisonnement des liens (voulu)** : les liens sont de l'INSTANCE, sans partition par société ; ils ne se lisent qu'avec `voir_infra` (jamais par une société secondaire, le module est d'instance). Un lien ne se retire que par son auteur ou
par un administrateur / compte système. Si la Bibliothèque veut montrer un impact à une société, elle le fera avec ses propres pages, pas avec ces liens. Aucun contrôle d'existence : une page de connaissance peut dépendre d'un objet qui n'est pas (encore) au registre. **[proposé]** : si la Bibliothèque veut des liens avec cascade sur `objet.retire`, ce sera une évolution du registre, à part et signalée.

## 8. [décidé] Prévisions généralisées

`prevision_mesure(cle)` : « combien de temps avant le seuil » pour toute mesure numérique d'un capteur, à partir de l'historique du capteur et du point d'évolution **`pente`** déjà là (pas de nouvelle maths). Rend
`{jours_avant_seuil, pente_par_jour, r2, confiance}` ou une raison de ne pas conclure (moins de 6 points, r² < 0,5, pente du mauvais côté) : **jamais une date inventée**.

## 9. [décidé] Auto-observation et robustesse

`autoobservation` (droit `voir_infra`) : capteurs, suivies, lectures reçues / refusées (par motif), événements émis / fusionnés, taille de l'historique, dernier tour du suivi, dernier relevé du collecteur, état de l'horloge.
Un détecteur `capteurs_suivis_muets` fait UN constat qui résume les clés suivies devenues muettes (pas un constat par clé). Collecteur muet : les clés `monde.*` suivies passent à `inconnu` par péremption, pas par invention.

## 9 bis. [décidé, fait] Le texte libre d'un capteur

`detail`, `valeur_txt` (valeur non numérique), `libelle`, `unite` et `motif` sont du texte écrit par un module ou un nœud satellite : jamais de confiance. À l'entrée (`texte_sur`, `CN_mesures_etat.py`), on retire les caractères
de contrôle (échappements de terminal compris), les marques de retournement du sens d'écriture (U+202A à U+202E, isolats U+2066 à U+2069), les caractères de largeur nulle et le BOM ; les retours à la ligne et tabulations deviennent un
espace ; le texte est coupé (500 pour `detail`, 200 pour une valeur texte, 120 pour un libellé, 20 pour une unité). **Les chevrons ne sont pas touchés** : échapper à l'entrée ferait un double échappement à l'affichage. L'écran doit donc
toujours poser ce texte comme du texte (`textContent`), jamais comme du balisage ; ce qui est stocké est sûr pour un terminal et un journal, pas pour `innerHTML`. **[à vérifier]** : je n'ai pas relu les écrans qui affichent ces champs.
Bancs : `TexteSur` (pur, 4) et `TexteLibre` (par un vrai capteur).

## 10. [décidé, fait] Mesures de collecteur : l'horloge et la résolution DNS

Deux fonctions ajoutées au collecteur (lecture seule, dans la boucle qui attrape déjà toute panne d'une mesure) :

* `horloge.synchronisation` : chrony (`chronyc tracking` : synchronisée, dérive > 0,5 s, non synchronisée) ; repli sur `timedatectl` (NTPSynchronized) ; « horloge non réglée » si la machine croit être avant 2025.
  `horloge.materielle` : pas de dossier `rtc*` = pas de pile ; alerte seulement si en plus le temps réseau n'est pas synchronisé (c'est le cas du Raspberry Pi sans horloge).
* `dns.sante` : le premier résolveur de `/etc/resolv.conf` (IPv4) est interrogé par `dig` pour deux noms ; sa réponse vide ou « puits » (127.x, 0.0.0.0) est comparée à un résolveur public (1.1.1.1, 9.9.9.9) AVANT d'alerter ;
  une différence d'adresses seule n'est pas une panne (les réseaux de diffusion répondent selon le lieu). Latence > 1,5 s : alerte.
* **Non fait** : le serve-stale d'un résolveur (il ne se voit pas d'ici sans le journal du résolveur, qui dépend du moteur : à mesurer par le module Serveur DNS lui-même, qui déclarera un capteur) ; la présence de SearXNG
  (l'adresse est un réglage du module Web, que le collecteur root ne lit pas : c'est au module Web de déclarer un capteur `web.moteur`, voir §13).
* **Non vérifié sur une vraie machine** : les bancs simulent `chronyc`, `timedatectl` et `dig` d'après le format de leur sortie tel que je le connais.

## 10 bis. [décidé, fait] SearXNG : la mesure `web.moteur`

Le Sensorium **tire** la santé du moteur : à chaque relève du monde (60 s), il lit la capacité `web.sante_moteur` du module Web (`ctx.executer_lecture`, une lecture, comme `modules.sante`). Le module Web n'a donc **aucun droit d'agir** à demander
(un module qui parle au dehors n'acquiert pas le pouvoir d'écrire ailleurs). `sante_moteur` fait une requête de recherche minimale avec les mêmes garde-fous que `rechercher` (adresse vérifiée, aucune redirection) et ne rend que
`{configure, ok, latence_ms, motif}` : ni l'adresse du moteur, ni un résultat. Le Sensorium en tire `web.moteur` : valeur = latence en ms, alerte au-delà de 3000 ms, `critical` si le moteur ne répond pas ou pas en JSON ; fraîcheur 180 s,
donc un moteur dont la relève s'arrête passe à `inconnu`. Pas de module Web, pas de moteur configuré, réponse illisible : **aucune lecture** (jamais un « ok » inventé). L'espace `web` est réservé au Sensorium (un capteur d'un autre compte ne peut
pas le prendre). La clé reste invisible aux comptes ordinaires tant qu'un administrateur ne l'a pas publiée.
**Constaté, non modifié** : le moteur configuré est dispensé en entier du refus des réseaux privés, y compris l'adresse locale des métadonnées d'hébergeur (comportement déjà présent de `rechercher`, l'URL étant posée par un administrateur).
Bancs : `CN_test_web` (6 : sonde seule, faux réseau), `MoteurWeb` (6 : la mesure), `MoteurWebDeBoutEnBout` (2 : vrai module Web monté dans un vrai noyau, faux réseau). **Non vérifié** : un vrai SearXNG.

## 11. Mémoire : la sonde `mesure_etat` [décidé]

Artefact `mesure:<clé>` (empreinte = l'état, qui ne bouge qu'au changement) et sonde `mesure_etat [clé, état attendu]` en vocabulaire fermé. Une mesure `inconnu` ne conclut RIEN (comme « la sonde ne répond plus » : ne pas savoir n'est pas une réfutation).

## 12. Ce qui est testé, et ce qui ne l'est pas

Testé (bancs dans `tests/`, voir le rapport pour les nombres) : les fonctions pures ; un VRAI noyau monté avec un administrateur, deux comptes ordinaires dont un dans une autre société, deux comptes « nœud » ; un faux émetteur ; capteur muet,
confiance, horloge fausse ou reculée, fusion des annonces, plafonds (capteurs, lectures, suivi, liens), clé non suivie, fuites (détail refusé, valeur absente de la vue minimale, inexistant = non publié), la voie directe depuis une société secondaire
(refusée), la voie par un module ouvert (`_intro["lecture"]`), retour arrière d'une déclaration et d'un suivi, les sondes de la Mémoire contre un Sensorium simulé puis contre le vrai, les mesures d'horloge et de DNS avec de fausses commandes.

**Non testé** : le collecteur sur une vraie machine Linux (chronyc, dig, timedatectl réels) ; l'interface (aucun écran n'a changé, mais les pages Système et Tableaux, derrière un menu d'administrateur, n'ont pas été exercées avec un compte
ordinaire) ; la charge (milliers de lectures par seconde) ; la concurrence réelle de plusieurs fils HTTP (les écritures partagent un verrou de processus, pas un verrou de base) ; Linux (la suite a tourné sous Windows 11 : deux bancs
`CodeScelle` y échouent déjà avant toute modification, seuls, et passent dans une exécution groupée — ordre dépendant, non expliqué).

## 13. Utiliser le contrat (pour le Serveur DNS, Kino, le module Web)

```python
# Dans le moteur d'un module du noyau. Manifeste : [permissions] agir = true, agir_moteur = ["sensorium.capteur_declarer", "sensorium.capteur_alimenter", "sensorium.mesure_suivre"].
# L'acteur doit être « cassandra » (le défaut « itare » n'est pas dans la liste des acteurs de ces capacités). Essayé tel quel par tests/CN_test_sensorium_mesures.py (ViaUnModule).
a = lambda cap, **args: ctx.agir(cap, args, acteur="cassandra")
a("sensorium.capteur_declarer", cle="dns.latence_locale", libelle="Latence du résolveur local", unite="ms", fraicheur_s=120, alerte=150, critique=800, pire="haut")
a("sensorium.capteur_alimenter", lectures=[{"cle": "dns.latence_locale", "valeur": 42, "observe_a": time.time(), "confiance": 0.9}])
a("sensorium.mesure_suivre", cle="dns.latence_locale", motif="la page Résolution en dépend")      # puis ctx.ecouter("mesure.change", ...) (à déclarer dans evenements.ecoute)
```

Un nœud Kino fera de même par l'API avec SON compte machine (droit `sensorium.alimenter`) : son espace (`kino-lyon.*`) lui appartient seul. **Limite assumée** : tous les modules du noyau agissent sous le même compte système
« noyau » ; deux modules du noyau peuvent donc se marcher sur un espace. Tant qu'un module installé tourne dans le processus avec ses droits, ce n'est pas une frontière de sécurité de plus.

## 15. Spécification du contrat, indépendante du langage (en vue d'un portage possible)

Statut : **[décidé] pour les formats ci-dessous, qui décrivent ce que le code Python rend AUJOURD'HUI** ; **[proposé]** pour tout ce qui est marqué ainsi. Rien de Go n'est écrit ni décidé : cette section fixe la forme, pas l'implémentation.
Transport : chaque message est un objet JSON (UTF-8). Aujourd'hui le « canal » est une capacité du noyau (`sensorium.<nom>`, arguments = champs de la requête, résultat = la réponse) ; un collecteur ou un nœud distant parlera
le même JSON par un autre transport (à définir avec le Kino). Les instants sont des secondes Unix (nombre) ; les durées des secondes. Les clés : `^[a-z0-9][a-z0-9_.:/-]{0,119}$` ; l'espace est ce qui précède le premier `.` ou `:`.

**Versions** [proposé] : aucune réponse ne porte encore de champ `version` ; ajouter `"v": 1` à chaque message est additif. Règle de compatibilité : un lecteur ignore les champs inconnus ; un champ n'est jamais retiré ni changé de sens dans une même version.

**Erreurs** : une faute de l'émetteur n'est JAMAIS une erreur de transport (sinon la capacité serait rétrogradée pour tous) : la réponse porte `ok: false` + `refuse` (texte), ou, par lecture, `refusees: [{cle, motif}]`. Motifs de lecture refusée :
`trop_vite` (plus d'une lecture par seconde et par clé), `capteur non déclaré`, `capteur d'un autre compte`, `lecture illisible`, `plus de 50 lectures par appel`. Les erreurs de transport/droit (`refuse`, `echec`) restent celles de l'exécuteur.

| Requête | Champs (obligatoire*) | Réponse |
|---|---|---|
| `capteur_declarer` | `cle*`, `libelle`, `unite`, `fraicheur_s` (5 à 604800, déf. 300), `alerte`, `critique`, `pire` (`haut`\|`bas`), `confiance_min` (0 à 1) | `{ok, cle, espace, nouveau, espace_nouveau}` ou `{ok:false, refuse, cle}` |
| `capteur_alimenter` | `lectures*` : liste (≤ 50) de `{cle*, valeur*, gravite (ok\|warning\|critical), observe_a, confiance (0..1), detail (≤ 500)}` | `{ok, acceptees:[cle], refusees:[{cle, motif}], t}` |
| `capteur_retirer` | `cle*` | `{ok, cle, avant}` ou `{ok:false, refuse}` |
| `mesure_suivre` / `mesure_ne_plus_suivre` | `cle*`, `motif` | `{ok, cle, nouveau}` / `{ok, cle, avant}` |
| `mesure_publier` | `cle*`, `visibilite*` (`instance`\|`toutes`\|`societes:<id>[,<id>…]`), `libelle` | `{ok, cle, visibilite, avant}` |
| `mesure_etat` | `cle*`, `pour` (appelant privilégié seulement, voir §6 bis) | `{cle, libelle, etat, depuis, raison}` |
| `vue_minimale` | `cles` (≤ 100, sinon tout ce qui est visible) | `{mesures:[{cle, libelle, etat, depuis, raison}], maintenant}` |
| `mesure_detail` | `cle*` | `{cle, libelle, unite, etat, raison, age_s, depuis, valeur, gravite, observe_a, recu_a, confiance, decalage_s, detail, capteur, visibilite, suivie_par}` |
| `prevision_mesure` | `cle*`, `niveau` (`alerte`\|`critique`) | `{conclu, raison, jours_avant_seuil?, pente_par_jour?, r2?, cle, niveau, seuil, points}` |
| `lien_poser` / `lien_retirer` (retrait : auteur ou administrateur ; sinon `{ok:false, refuse}`) | `de*`, `relation` (`depend_de`,`heberge_par`,`certifie_par`,`resout_par`,`decrit`), `vers*` | `{ok, de, relation, vers, nouveau}` |
| `impact` / `liens` | `objet*` (`impact` : `profondeur` ≤ 6) | `{depart, touches:[{objet, via, relation, distance}], tronque}` / `{objet, depend_de, dependants}` |

**Événement** `mesure.change` (un par suiveur) : `{cle, avant, apres, depuis, raison, suiveur}` ; `avant`/`apres` ∈ `ok`,`alerte`,`inconnu` ; `avant` vaut `inconnu` avant la première lecture.

**Sémantique normative (portable)** — c'est ce qu'un autre collecteur doit reproduire à l'identique :
1. État : `inconnu` si aucune lecture, ou horloge locale < 2025-01-01, ou lecture datée de plus de 300 s dans le futur, ou `maintenant − recu_a > fraicheur_s`, ou `confiance < confiance_min` ; sinon `alerte` si la gravité est `warning`/`critical`, sinon `ok`.
2. La fraîcheur se juge sur `recu_a` (l'horloge du récepteur), jamais sur `observe_a`. `decalage_s = observe_a − recu_a` ; au-delà de 300 s la confiance est plafonnée à 0,5.
3. Gravité par seuils (si l'émetteur n'en donne pas) : `pire = haut` : `critical` si valeur ≥ critique, `warning` si ≥ alerte ; `bas` : mêmes comparaisons avec ≤. Une valeur non numérique ne déclenche aucun seuil.
4. `depuis` = l'instant du dernier CHANGEMENT d'état (pour un silence : `recu_a + fraicheur_s`).
5. Annonce : seulement pour une clé suivie ; ne se répète pas ; au plus une par 30 s et par clé (le retour attend la lecture suivante passée la fusion).
6. Historique : un point numérique au plus toutes les 300 s (ou à chaque changement d'état), 2000 points, 14 jours. Prévision : régression linéaire (point `pente`, ≥ 6 points, r² ≥ 0,5), jamais de date si la pente s'éloigne du seuil.
7. Plafonds : 200 capteurs (50 par compte), 500 clés suivies (50 par suiveur), 1 lecture/s/clé, 50 lectures/appel, 5000 liens (500 par auteur).
8. Visibilité : un non-privilégié ne voit que `toutes` ou `societes:` contenant la société de l'acte ; une clé inconnue et une clé invisible répondent identiquement (`etat: inconnu`, libellé et raison vides).

**Noyau portable / collecteurs propres au système** (la séparation à respecter) :
* Portable : tout ce qui précède (protocole, états, fraîcheur, confiance, seuils, historique, tendance, fusion, plafonds, visibilité). Aujourd'hui `CN_mesures_etat.py` (pur, sans entrée/sortie) en est la référence exécutable ; `CN_capteurs.py` y ajoute le stockage.
* Propre au système : les collecteurs du modèle du monde (`systemd`, `dig`, `chronyc`, DSM, Windows) qui produisent des lectures. Interface commune [proposé] : un collecteur est une fonction `() -> [lecture]` avec la forme de `capteur_alimenter.lectures[]` ; il ne connaît ni les seuils d'affichage, ni les droits, ni le bus.
  Le collecteur Python actuel (~6 700 lignes, `GET_*` sur socket Unix) n'est PAS conforme à cette forme et n'est pas réécrit : un pont lui ferait émettre des lectures `monde.*` (déjà le cas pour les clés suivies, voir `ingerer_monde`).

**Tests de contrat** : `tests/CN_test_sensorium_contrat.py` vérifie, par le seul canal de la requête (l'exécuteur, comme un client distant), que chaque réponse porte les champs et types de la table ci-dessus et que la sémantique 1 à 8 tient sur des cas fixes. Il prend une fonction `appeler(nom, **champs) -> réponse` :
pour brancher une autre implémentation (Go), on remplace cette seule fonction par un client du protocole. **[proposé]** : la comparaison « mesure par mesure » entre le collecteur Python (étalon) et un futur collecteur sur la même machine se fera sur les lectures `monde.*` (clé, état, gravité) ; elle n'existe pas encore.

## 14. Ce qui n'est pas fait ici

Le protocole Kino réseau ; des relations avec cascade au registre ; toute modification de l'interface (écrans) ; l'exercice des écrans existants avec un compte ordinaire.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
