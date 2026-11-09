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
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=7a0742 ▼▼▼ -->
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

Nouveau droit `voir_infra` (sensible, jamais attribué par défaut). Posé sur toutes les lectures d'infrastructure listées en §0 **sauf `serie`** (voir plus bas). Un administrateur passe tous les contrôles de droits
(constaté : l'essai du §0 le montre pour `premier`), donc **aucun administrateur ne perd rien**. Conséquences assumées :

* un compte non administrateur n'obtient plus `monde`, `etat`, etc. ; le module Mémoire, qui lit `sensorium.monde` au nom de l'utilisateur, reçoit « aucun relevé disponible » (c'est son comportement déjà prévu) : le contexte d'un
  modèle n'embarque plus l'infrastructure pour un utilisateur ordinaire ;
* `vue` n'appelle `sensorium.metriques` et `sensorium.sante` que pour un administrateur (`admin_seul` vrai dans `SOURCES`) : rien à changer ;
* **`serie` reste ouverte** : le module `mesures` l'appelle au nom du compte qui regarde ses courbes, derrière son propre droit `mesures.voir`. La fermer casserait un usage légitime ; ce qu'elle expose se limite à neuf
  courbes de la machine (processeur, mémoire, disque…). **[proposé]** : la fermer elle aussi une fois que `mesures` aura son propre accès. Décision laissée à Drisse.
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

## 7. [décidé] Relations entre objets

Plutôt que d'élargir le registre du noyau (intouchable, et chaque module le lit), les relations vivent dans le Sensorium : `sensorium_liens (de, relation, vers)` avec des références `type/id` libres
(`site/exemple.test`, `monde.ssl.exemple.test`, `service/nginx`). Capacités `lien_poser` / `lien_retirer` (droit `alimenter`), `liens`, `impact` (qui est touché si X tombe : parcours borné, profondeur 6, 200 nœuds, sans boucle infinie).
Aucun contrôle d'existence : une page de connaissance peut dépendre d'un objet qui n'est pas (encore) au registre. **[proposé]** : si la Bibliothèque veut des liens avec cascade sur `objet.retire`, ce sera une évolution du registre, à part et signalée.

## 8. [décidé] Prévisions généralisées

`prevision_mesure(cle)` : « combien de temps avant le seuil » pour toute mesure numérique d'un capteur, à partir de l'historique du capteur et du point d'évolution **`pente`** déjà là (pas de nouvelle maths). Rend
`{jours_avant_seuil, pente_par_jour, r2, confiance}` ou une raison de ne pas conclure (moins de 6 points, r² < 0,5, pente du mauvais côté) : **jamais une date inventée**.

## 9. [décidé] Auto-observation et robustesse

`autoobservation` (droit `voir_infra`) : capteurs, suivies, lectures reçues / refusées (par motif), événements émis / fusionnés, taille de l'historique, dernier tour du suivi, dernier relevé du collecteur, état de l'horloge.
Un détecteur `capteurs_suivis_muets` fait UN constat qui résume les clés suivies devenues muettes (pas un constat par clé). Collecteur muet : les clés `monde.*` suivies passent à `inconnu` par péremption, pas par invention.

## 10. [proposé, selon le temps] Mesures de collecteur pour le DNS et l'horloge

Hors du noyau de ce travail : ajouter au collecteur (gardé entier) de petites fonctions `collect_*` : dérive d'horloge et source de temps, résolveur (présent, écoute), puits (`127.0.0.1`/`0.0.0.0`), latence local / public, serve-stale.
Vu l'ampleur du collecteur (6 710 lignes, root, Linux) je ne les ajoute que si les tests simulés sont possibles sans réseau. Statut final dans le rapport.

## 11. Mémoire : la sonde `mesure_etat` [décidé]

Artefact `mesure:<clé>` (empreinte = l'état, qui ne bouge qu'au changement) et sonde `mesure_etat [clé, état attendu]` en vocabulaire fermé. Une mesure `inconnu` ne conclut RIEN (comme « la sonde ne répond plus » : ne pas savoir n'est pas une réfutation).

## 12. Ce qui n'est pas fait ici

Le protocole Kino réseau ; la fermeture de `serie` ; des relations avec cascade au registre ; toute modification de l'interface (écrans) ; l'exercice des écrans existants avec un compte ordinaire.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
