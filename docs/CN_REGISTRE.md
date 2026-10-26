<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Le registre officiel de Cassandra -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Le registre officiel de Cassandra : sa racine de confiance embarquée, son index signé, ses éditeurs vérifiés, ses révocations et ses niveaux de confiance. -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ═══════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=10fc12 ▼▼▼ -->
# Le registre officiel de Cassandra

Le magasin de modules officiel vit dans un dépôt à part, **`cassandra-registre`** (source de vérité : archives signées, éditeurs vérifiés, révocations, outil de publication), publié en page statique. L'application le connaît **en dur** : ce n'est pas un réglage.

## Ce qui est dans l'application (`noyau/CN_registre_officiel.py`)
- **`URL_OFFICIELLE`** : l'adresse de l'index. Elle changera de domaine un jour, pas de forme.
- **`CLES_RACINE`** : deux clés publiques Ed25519, *principale* et *secours*. La confiance de tout ce que le registre dit vient d'elles. Les clés privées sont hors ligne, hors dépôt, hors intégration continue.
- La lecture de l'index : `index.json` + `index.json.sig` (base64, signature des octets exacts). Un index non signé par la racine embarquée, modifié, périmé (`expire`), daté du futur (`emis`) ou d'un format inconnu est **refusé**.

## L'index (format 1)
`{"format": 1, "emis": ts, "expire": ts, "modules": [...], "editeurs": [...], "revocations": [...]}`. Les éditeurs vérifiés et les révocations sont **dans** l'index signé : ils sont donc couverts par la même signature. Une archive vit chez l'hôte de l'index et de lui seul.

## Les niveaux de confiance (le nom de la clé qui a signé fait le niveau)
| Niveau | Signée par | Affichage |
|---|---|---|
| officiel | une clé racine (`cassandra-*`) | Officiel |
| verifie | un éditeur que l'index signé déclare vérifié (`ed_<id>`) | Éditeur vérifié · nom |
| local | une clé posée par l'administrateur dans `config/cles` | Clé de l'administrateur |
| — | personne | Non signé (refusé par la politique « signés ») |

Une clé posée à la main dont le nom commence par `cassandra-` ou `ed_` est **ignorée** : elle ne peut pas se faire passer pour l'officiel.

## Révocations
Une entrée `{id, versions, raison}` de l'index signé : le client **refuse d'installer** une version révoquée et **signale**, dans la Logithèque, les modules installés qui le sont. Il ne désinstalle rien seul : c'est un geste de l'administrateur (désinstaller, ou garder en connaissance de cause).

## Autre registre
Le réglage `modules.registre_url` ajoute un registre tiers, toujours affiché **non officiel** (son index n'est pas signé par la racine). Chaque archive reste examinée de la même façon.

## Publier (côté dépôt `cassandra-registre`)
`python outils/registre.py verifier` contrôle tout ; `python outils/registre.py publier --cle racine-principale.pem` signe l'index (60 jours) et écrit `docs/`. Le renouvellement est automatique : `outils/renouveler.py` (tâche planifiée quotidienne sur la machine qui garde la clé racine) republie l'index quand il reste moins de 30 jours et le pousse. Si cette machine reste éteinte plus de 30 jours, l'index expire et le magasin de TOUTES les instances se coupe : la clé doit rester disponible, et une sauvegarde chiffrée existe en deux endroits.

## Ce que cela ne fait pas
Un module installé tourne dans Cassandra, avec ses droits ; ses permissions sont déclaratives. La signature dit **qui** a publié, pas que le code est inoffensif : la relecture et la révocation sont la protection.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : la description du registre officiel -->
<!-- EC : néant (aucun point d'évolution) -->
<!-- LIEN : noyau/CN_registre_officiel.py, noyau/CN_cycle.py, interface/CN_appstore.js, tests/CN_test_registre_officiel.py, cassandra-registre (le dépôt) -->
