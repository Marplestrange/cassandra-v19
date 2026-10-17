<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Le module store de Cassandra -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Le module store de Cassandra -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=0e5237 ▼▼▼ -->
# Le module store de Cassandra

Un jour, des modules viendront d'ailleurs : un éditeur les publie, un administrateur les installe, Cassandra elle-même peut les choisir.
Ce document dit ce que le noyau garantit déjà pour que ce jour arrive sans rien casser, et ce qui reste à construire.

## Les rôles

| Rôle | Fait | Ne peut pas |
|---|---|---|
| **Éditeur** | écrit un module, le publie en paquet, le signe de sa clé | faire confiance à sa propre clé : c'est l'administrateur qui la déclare |
| **Store** | publie un index et des paquets (un simple dossier web suffit), peut avoir des miroirs | installer quoi que ce soit chez quelqu'un |
| **Noyau** (client) | cherche, compare, vérifie, installe, active, met à jour | se fier au store : il vérifie tout lui-même |
| **Administrateur** (humain, ou Cassandra dans son périmètre) | déclare les éditeurs de confiance, approuve les permissions | |

## Ce qui est construit

- **Le contrat du module** (`CN_manifeste.toml`) porte tout ce qu'une vitrine affiche : `auteur`, `licence`, `site`, `famille`, `version`, `api`
  (la version majeure de l'API du noyau visée ; un module d'une autre API est refusé), `requiert`, `[permissions]`.
- **Les permissions sont dites avant l'installation** : `espace_utilisateur` (appliqué : sans elle, `ctx.espace()` refuse), `reseau`, `ecritures`,
  `privileges` (déclaratifs jusqu'à la cage par processus, ci-dessous). Le menu des modules les montre.
- **Le paquet** (`.cmod`, tar.gz) : le dossier du module, `SOMMES` (empreinte de chaque fichier), `SIGNATURE` (Ed25519 par OpenSSL). Construction
  reproductible. `python CN_main.py paquet construire | verifier | extraire`.
- **La chaîne de confiance** : une clé publique d'éditeur dans `config/cles/<editeur>.pub`. Un paquet est accepté s'il est intègre ET signé par l'une
  d'elles ; un paquet falsifié, démesuré, qui sort de son dossier ou contient un lien est refusé. Un paquet non signé n'entre qu'avec `--non-signe`.
- **La greffe à chaud, l'état installé / actif, l'activation et la désactivation à chaud** : voir le README.

## Ce qui reste à construire

1. **L'index et le client.** `index.json`, signé par le store :
   ```json
   {"format": 1, "emis": "2026-10-11T18:00:00Z", "modules": [
     {"id": "sentinelle", "nom": "Sentinelle du disque", "famille": "supervision", "auteur": "…", "licence": "AGPL-3.0",
      "versions": [{"version": "0.2.0", "api": "1", "url": "…/sentinelle-0.2.0.cmod", "sha256": "…", "taille": 1688,
                    "requiert": [{"id": "proactif", "version": ">=0.1"}], "permissions": {"reseau": [], "espace_utilisateur": false},
                    "changelog": "…"}]}],
    "signature": "…"}
   ```
   Le client (`python CN_main.py store chercher | voir | installer | mettre-a-jour`) vérifie l'index, résout les dépendances, affiche les permissions, télécharge,
   compare `sha256`, vérifie la signature, puis installe.
2. **Installer sans être root.** Le noyau tourne sans privilège et `extensions/` appartient à root. Un petit **courtier** (service root, activé par
   socket, liste blanche d'opérations : « déposer un paquet vérifié », « lancer l'CN_installer.sh de ce module », « retirer ») permet à Cassandra d'installer
   un module du store seule, avec preuve et retour arrière, et sans jamais élargir ses droits.
3. **Les versions côte à côte.** `extensions/<id>@<version>/` et un lien `extensions/<id>` : une mise à jour qui ne passe pas sa preuve revient à la
   version précédente, comme `CN_deploy.sh` le fait pour le noyau. Les mises à jour de module ne redémarrent pas le noyau.
4. **Le stockage propre du module et ses migrations.** Un fichier SQLite par module (`donnees/modules/<id>.db`), des migrations numérotées appliquées à
   l'activation, supprimé à la purge : la désinstallation est nette, la sauvegarde isole le module.
5. **La cage par processus.** Aujourd'hui un module tourne dans le processus du noyau : acceptable pour un module livré (« interne ») ou déposé par
   l'administrateur (« local »), **pas pour un module de tiers**. Le module tournera dans son propre processus, sous des limites tirées de ses permissions
   (`ReadWritePaths` depuis `ecritures`, réseau fermé sauf `reseau`, aucun privilège), et parlera au noyau par un canal local. Le contrat est déjà prêt pour
   cela : `ctx` est étroit, et les arguments et résultats des capacités sont de simples valeurs JSON.
6. **Révocation.** Une liste de clés et de paquets révoqués (`config/cles/revoquees`), relue à chaque vérification.
7. **La note de risque.** Cassandra évalue un module à partir de ses permissions et de sa provenance avant de décider seule de l'installer.

## Règles qui ne bougeront pas

- Le noyau ne se fie jamais au store : tout est revérifié localement.
- Une clé n'est de confiance que si l'administrateur l'a posée dans `config/cles/`.
- Un module du store ne s'élève jamais seul : ni « interne », ni plus de permissions qu'il n'en a déclaré.
- Rien n'est supprimé sans retour : désactiver garde les données, désinstaller les purge seulement sur demande explicite.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
