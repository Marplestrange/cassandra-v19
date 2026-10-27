<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Bilan de session — portage V18 → V19 (16 octobre 2026) -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : (racine) -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Bilan de session — portage V18 → V19 (16 octobre 2026) -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=ccc07c ▼▼▼ -->
# Bilan de session — portage V18 → V19 (16 octobre 2026)

À lire en premier pour reprendre le chantier. Ce document est le point d'entrée ; la mémoire de l'agent
(`~/.claude/projects/C--Users-Admin-Documents-Cassandra/memory/`) porte les règles et leçons au fil de l'eau.

## Le contexte en une phrase

Cassandra est passé d'un monolithe (`V18/cassandra.py`, ~154 000 lignes) à une architecture **noyau + modules**
(V19). Le noyau (`CN_main.py` + `noyau/`) assemble ; le métier vit dans `modules/<id>/` ; l'interface est l'UI V18
extraite (`interface/`), branchée sur les modules par `interface/shell.js` et `interface/routes/*.js`.

- **Dépôt** : `C:\Users\Admin\Documents\Cassandra-V19`, privé sur `github.com/Marplestrange/cassandra-v19` (branche `main`).
- **Machine de test** : Amizo (198.51.100.9, root, clé `~/.ssh/id_ed25519_claude`, alias SSH `amizo`).
- **Serveur local** : `python CN_main.py demarrer` (port 9000), compte de test `drisse@exemple.test` / `Essai-Local-1234`.

## Ce qui est fait

Tous les modules sont **portés** (cœur), testés (bancs `unittest` dans `tests/`), avec leurs routes, et **déployés
sur Amizo** (en « non activé » — voir plus bas) :

| Module | Capacités | Famille | Notes |
|---|---|---|---|
| salon | 20 | echanges | fil, messages, résidents (Cassandra/Itare) |
| journal | 18 | supervision | fil des agents + lecteur multi-sources |
| ged | 27 | gestion | cœur local (fichiers, corbeille, règles) |
| coffre | 14 | securite | magasin de secrets (Vaultwarden) : un espace par compte et par société, rôles, auteur de chaque secret (27-10) |
| societes | 18 | socle | la fiche de chaque société, ses fonctions (groupes attachés), l'identité publique ; tout compte a une société (27-10) |
| proactif | 18 | supervision | autonomie + savoir + ombre + incidents + fil + automatisme (catalogue de gestes) |
| sauvegardes | 7 | supervision | plans, copies, couverture |
| securite | 6 | securite | gestes, journal, audits |
| mandats | 6 | echanges | autorisations d'envoi |
| canvas | 4 | gestion | départs, gestes, plan |
| voix | 7 | echanges | catalogue, choix par compte |
| canaux | 4 | canaux | état, miroir |

Les modules *déjà portés avant cette session* (fastpanel, sites, webauthn, telegram, dns, certificats, contacts,
courrier, projets, taches, notes, agenda, modeles, memoire, flotte, planifie) restent en place.

## Le noyau, enrichi au passage

- **Moteurs asynchrones sur événement** (une file, un fil à part, sans retenir l'émetteur) + `Noyau.arreter()`.
- **`stockage_lecture`** : un module peut lire (en lecture seule) la base d'un autre module (pour le journal).
- **Réversibilité systématique** : toute capacité qui écrit doit fournir `prouver` ET `defaire` (la sûreté vient de la réversibilité).
- **Courtier racine** : le noyau ne dit jamais *quoi* exécuter, seulement *quelle commande nommée* d'un module.

## Le courtier racine (patron à suivre)

`noyau/CN_racine.py` + `exploitation/CN_courtier.py` sont en place. Pour qu'un module fasse tourner du code à root :

1. `[[racine]]` dans `CN_manifeste.toml` (id, libelle, `lecture = true` si lecture seule) + `racine = true` dans `[permissions]`.
2. Le programme dans `commandes/<id>` (Python, valide ses propres arguments).
3. `CN_installer.sh` / `CN_verifier.sh` / `CN_retirer.sh` (posent/vérifient/retirent `/usr/libexec/cassandra/<module>/<id>`).
4. `[installation] script/verification/retrait` dans le manifeste.
5. La capacité appelle `ctx.racine("id", args, stdin=..., delai=...)`.

Déjà fait : sauvegardes (copier/lister/purger rclone), sécurité (mesurer : Lynis/Trivy/ClamAV/CrowdSec), voix
(ecouter/parler/telecharger), canaux (connecter Telethon — la session passe par **stdin**, jamais en argument).

## L'interface (et ses pièges)

- L'UI V18 a 15 onglets fixes. Les modules V19 **sans onglet V18** vont dans le groupe « Modules », **regroupé par famille**.
- La carte `CASS.couvre` (`interface/shell.js`) dit « ce module V19 est déjà couvert par tel onglet V18 » — pour ne pas doubler.
  Elle doit être tenue à jour quand on ajoute un module qui a un équivalent V18 (piège déjà rencontré deux fois : salon/journal, puis planifie/flotte).
- Le socle (`affichage`, `menus`) est `role = "admin"` : il n'apparaît que pour l'administrateur.
- **Attention** : un changement de `CN_manifeste.toml` (libellé, menu) ne se voit qu'après **redémarrage** du serveur local (l'arbre des menus se reconstruit au premier `tick`).

## Déploiement sur Amizo

```
bash outils/CN_pousser.sh amizo deploy
```
C'est **long** (~15 min : il rejoue toute la suite `unittest` sur Amizo), avec **retour arrière automatique** en cas
d'échec. Ne jamais lancer deux déploiements en parallèle (ils se marcheraient dessus sur la bascule). Un module
nouveau arrive « non activé » — le déploiement n'active jamais un module nouveau ; l'activation est un choix délibéré.

## Ce qui reste

1. **Évolution** — le seul gros chantier structurant. À **concevoir**, pas à porter : en V18 elle patche un seul
   fichier (`cassandra.py`), en V19 elle doit patcher des **modules**, chacun avec sa validation, en coordination
   avec le déploiement multi-modules. Écrire une note de conception AVANT de coder.
2. **Interface** : vue d'ensemble `/api/vue`, second facteur de connexion, onglets d'objet.
3. **Activation des modules** sur Amizo (ils sont « non activés »).

## Pièges déjà payés (à ne pas redécouvrir)

- **Bancs flaky du salon** : le `fin`/`erreur` d'un tour d'agent est écrit APRÈS le message. Un test qui lit l'état
  du tour juste après `attendre` doit d'abord attendre `fin IS NOT NULL`.
- **`set`/`list`/`get`/`delete`** en nom de fermeture masquent les builtins Python (`sorted(set(...))` appelait la
  capacité `set` → « nom requis »). Renommer les fermetures (`poser`, `lister`, `lire`, `retirer`).
- **`couvre` incomplet** → onglet en double.
- **Troncature `[:5]`** appliquée par erreur au palier (« maitrise » → « maitr »).
- **Un module avec `[installation]`** exige `verification` + `retrait`, et dans les bancs `etat_modules.poser(id, installe=True)` avant `activer`.
- **Objet type « savoir » réservé** au noyau (utiliser un autre type, ex. `savoir_faire`).
- **Ne jamais écrire de heredoc bash avec apostrophes** (utiliser Write).
- **`n.lancer(moteur)` avale l'erreur** : la lire dans le retour (`statut`).

## Règles de méthode (de Drisse, à respecter)

- **Pas de squelettes** : lire le code V18 du module en entier, porter toutes ses règles et leçons, écrire les bancs, *puis* ranger dans `modules/`. Les brouillons d'Orion vivent dans `brouillons/` et ne comptent pas comme portés.
- **Lire la source avant de coder** : chaque supposition coûte un aller-retour.
- **Sobriété** : les jetons de Drisse sont comptés — sorties courtes, ne lire en entier que ce qu'on modifie.
- **Tutoiement** partout.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
