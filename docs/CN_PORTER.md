# Porter un module de la V18 vers la V19

Ce guide est donné tel quel à qui porte (une personne, ou un Claude). Il dit CE QUE LE NOYAU FAIT DÉJÀ, pour ne pas le réécrire.

## Le principe

On **porte la logique** de la V18 (`cassandra.py`), on ne la réécrit pas : mêmes règles, mêmes cas limites, mêmes leçons (elles sont dans les
commentaires de la V18, et ce sont des bogues déjà payés). On change la **forme** : un module = un dossier `modules/<id>/` avec un manifeste, du code, ses migrations.

```
modules/<id>/CN_manifeste.toml     le contrat : ce que le module est, offre, demande
modules/<id>/CN_module.py          def brancher(ctx): ... ctx.implementer(...), ctx.moteur(...), ctx.detecteur(...)
modules/<id>/migrations/001_*.sql   le schéma de SA base (donnees/modules/<id>.db)
tests/test_<id>.py              les bancs (voir plus bas)
```

## Ce que le noyau fait déjà (ne pas le refaire)

| En V18 | En V19 |
|---|---|
| route `/api/xxx`, `CassandraHandler`, vérification de session | **rien à écrire** : toute capacité est joignable par `POST /api/agir/<module>.<capacite>` (passerelle), le compte vient du jeton |
| `get_current_user()`, `is_admin()`, `_request_user` | `ctx.compte` (le compte au nom duquel on agit, PAR FIL, jamais global) ; droits : `[[droits]]` + `droit = "..."` sur la capacité |
| thread `while True: ... sleep`, `threading.Thread` | `[[moteurs]]` (périodique, sur événement, à la demande) : le noyau l'ordonnance, le borne en durée, le suspend s'il échoue. **Jamais de thread dans un module.** |
| sonde / boucle de surveillance qui crée une alerte | `[[detecteurs]]` : une fonction `ctx.detecteur(id, f)` qui RENVOIE la liste des constats `{"objet": (type, id), "titre": ..., "detail": ..., "niveau": "critique"|"avoir"|"info", "capacite": ..., "args": ...}`. Le constat se résout seul quand il n'est plus rendu. Le module Notifications en fait la cloche. |
| `notif(...)`, `_itare_proactive_add`, `save_alert` | un constat (ci-dessus), ou un événement émis (`ctx.emettre`) |
| `log_user_activity`, `journal_agents_ecrire` | rien : `ctx.emettre(type, ...)` ; tout acte exécuté par une capacité est déjà au journal avec son compte et son acteur |
| `get_cassandra_config()` / `save_cassandra_config()` (config.json réécrit en entier) | `[[reglages]]` dans le manifeste, lus par `ctx.reglage("nom")` ; types texte/entier/booleen/choix/secret, portée global ou compte |
| `sqlite3.connect(MEMORY_DB_PATH)` + `CREATE TABLE IF NOT EXISTS` | `ctx.stockage` (une base à soi) + `migrations/NNN_nom.sql` ; permission `[permissions] stockage = true`. **Jamais la table d'un autre module.** |
| envoi de courriel / Telegram | émettre un événement ou un constat ; les canaux (module à venir) livrent. Ne pas envoyer soi-même. |
| mot de passe, jeton, clé d'API dans un journal | `masque = ["nom_de_l_argument"]` sur la capacité : jamais au journal |
| `subprocess` en root, `systemctl`, écriture système | pas dans le noyau : un module qui en a besoin passe par un `CN_installer.sh` / `CN_verifier.sh` (voir modules/sensorium) ou par le courtier |

## Le manifeste (`CN_manifeste.toml`)

```toml
[module]
id = "sauvegardes"            # minuscules, chiffres, _ ; = nom du dossier
nom = "Sauvegardes"
version = "0.1.0"
noyau_min = "0.1.0"
description = "..."
confiance = "interne"
famille = "securite"          # regroupement dans le menu des modules
requiert = ["droits"]         # modules dont celui-ci dépend (jamais d'import entre modules)

[[droits]]                    # ce qu'un COMPTE doit détenir pour utiliser les capacités qui y renvoient
id = "gerer"
libelle = "..."
sensible = true               # defaut = true : accordé à tous les comptes d'office

[[reglages]]                  # id, libelle, type (texte|entier|booleen|choix|secret), defaut, portee (global|compte), minimum, maximum, choix, aide

[[objets]]                    # types d'objets que CE module possède au registre ; un événement émis doit commencer par un type possédé
type = "sauvegarde"
libelle = "..."

[evenements]
emet = ["sauvegarde.faite"]   # <type d'objet>.<verbe>
ecoute = ["constat.ouvert"]   # un moteur « sur événement » n'écoute que ce qui est ici

[[moteurs]]                   # id, libelle, mode = periodique (toutes_les_s >= 10) | evenement (sur = [...]) | demande, duree_max_s
[[detecteurs]]                # id, libelle, frequence_s (>= 10), capacite (facultative : l'action proposée)

[[capacites]]
id = "lancer"
libelle = "..."
risque = "lecture"            # lecture | faible | moyen | eleve
droit = "gerer"               # facultatif
masque = ["mot_de_passe"]     # facultatif : arguments/résultats qui ne vont jamais au journal
# Une capacité qui ÉCRIT (risque != lecture) DOIT déclarer :
perimetre = ["ce qu'elle touche, et rien d'autre"]
preuve = "comment on vérifie après coup que c'est fait"
retour = "comment on défait"
paliers = ["raconter", "auto"]            # jusqu'où Cassandra peut agir SEULE (choix de l'administrateur) ; "eleve" ne va pas à "maitre"
qui = ["humain", "compte", "cassandra", "itare"]    # acteurs permis (agent = agent invité)

[permissions]
stockage = true               # sa base ; droits = true pour ctx.droits() ; lectures = true pour ctx.executer_lecture ; introspection = true pour ctx.evenements/manifestes
```

## `CN_module.py`

```python
def brancher(ctx):
    db = ctx.stockage                       # Stockage : db.lire(sql, params) -> [dict], db.ecrire(sql, params) -> lastrowid, with db.transaction() as c
    def lancer(ctx, plan=0):                # (ctx, **arguments) ; rend un dict JSON-sérialisable
        ...
        return {"id": ..., "avant": ..., "apres": ...}     # ce dont la preuve et le retour arrière ont besoin
    def prouver(ctx, res): return ...       # vrai si c'est bien fait (relire ce qui a été écrit)
    def defaire(ctx, res): ...              # remet l'état d'avant (res vient de lancer ; l'état d'avant y est)
    ctx.implementer("lancer", lancer, prouver, defaire)    # une lecture : ctx.implementer("lister", lister)
```

Règles dures :
- Une capacité qui écrit **rend de quoi se défaire** (l'état d'avant) ; la suppression garde une copie (corbeille) quand c'est possible.
- Le compte vient de `ctx.compte` ; toute lecture de données personnelles est bornée à ce compte, sauf droit explicite.
- Une exception levée = un échec propre (statut `echec`, rien ne tombe). Lever `ValueError("message clair")` pour un refus de validation.
- Pas de `print`, pas de globaux qui portent un compte, pas de `time.sleep` long, pas d'appel réseau sans délai.
- Les chemins et valeurs d'infrastructure (hôtes, ports, dossiers) viennent des **réglages**, jamais en dur (le projet est générique).
- Pas de HTML ni de JS : l'interface est un chantier à part, qui lit les capacités.

## Les bancs (`tests/test_<id>.py`)

`unittest`, bibliothèque standard seule. Modèle : monter un `Noyau` dans un dossier temporaire avec les modules voulus copiés depuis `modules/`, `exiger_compte=True`,
créer les comptes par `comptes.creer`, agir par `n.executeur.executer(capacite, acteur, args, compte=...)`. Voir `monde_notifs()` et la classe `CentreDeNotifications`
dans `tests/CN_test_noyau.py`. Tester : le cas nominal, chaque refus de validation, le cloisonnement entre deux comptes, le droit manquant, la preuve et le retour arrière
(`n.catalogue.get("<module>.<capacite>").defaire(n.executeur.contextes["<module>"], resultat)`), et **chaque leçon écrite dans les commentaires de la V18**.

## Ce qu'on ne porte pas

Le code d'interface (HTML/JS/CSS de `HTML_TEMPLATE`), les routes (`CassandraHandler`), les caches en attribut de fonction, les `ALTER TABLE` d'anciennes migrations
(la V19 repart d'une base vide : `001_init.sql` crée l'état final), les fonctions qui n'appartiennent pas au module (les appeler par une capacité d'un autre module, ou les laisser).
