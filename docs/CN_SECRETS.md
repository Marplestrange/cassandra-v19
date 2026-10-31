<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- TITRE      : Les secrets des modules : où est la clé, qui les lit, quel âge ils ont -->
<!-- LICENCE    : AGPL-3.0 -->
<!-- AUTEUR     : Atek Drisse -->
<!-- GIT        : github.com/Marplestrange -->
<!-- MAIL       : marplestrange@cassandra.center -->
<!-- MODULE     : docs -->
<!-- ZONE       : CN -->
<!-- VERSION CN : 0.1.0  #000000 -->
<!-- VERSION EC : néant -->
<!-- EC LIÉES   : néant -->
<!-- RÔLE       : Les secrets des modules : où est la clé, qui les lit, quel âge ils ont -->
<!-- MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend) -->
<!-- ══════════════════════════════════════════════════════════════════════════════ -->
<!-- ▼▼▼ BORNE CN version=0.1.0 empreinte=932611 ▼▼▼ -->
# Les secrets des modules : où est la clé, qui les lit, quel âge ils ont

Les secrets des modules (mots de passe de boîte, jetons d'API…) restent dans le noyau, dans la table des réglages, chiffrés au repos (AES-256-GCM). Ce
document dit comment on durcit ce mécanisme **sur place**, sans les envoyer ailleurs.

Ce que le chiffrement protège : les sauvegardes et les copies de la base. Ce qu'il ne protège pas : un attaquant qui lit **à la fois** la base et la clé.
D'où la première étape : ne pas ranger la clé à côté des données.

## 1. Sortir la clé du dossier des données

La clé fait 32 octets. Elle est cherchée dans cet ordre :

1. le **credential systemd** nommé `cassandra-secrets-key` (variable `CREDENTIALS_DIRECTORY`, remplie par systemd) ;
2. le fichier désigné par la variable d'environnement `CASSANDRA_SECRETS_KEY_FILE` ;
3. en repli seulement : `secrets.cle` dans le dossier des données, avec un **avertissement** à chaque démarrage dans le journal.

Le fichier peut contenir les 32 octets bruts, ou 64 chiffres hexadécimaux, ou ces 32 octets en base64. Une clé annoncée mais illisible ou invalide
**arrête les secrets** (l'erreur le dit, sans montrer la clé) : le noyau ne la remplace jamais en silence par une clé neuve, qui rendrait les secrets
illisibles.

### Mise en place sur un serveur

Générer la clé une fois, **hors** du dossier des données et hors du dépôt, lisible du seul administrateur :

```bash
sudo install -d -m 0700 /etc/cassandra
sudo sh -c 'umask 077; openssl rand -hex 32 > /etc/cassandra/secrets.key'
```

Dans l'unité systemd du noyau, la donner en credential (elle apparaît alors dans un dossier de mémoire propre au service, jamais dans les données) :

```ini
[Service]
LoadCredential=cassandra-secrets-key:/etc/cassandra/secrets.key
```

Au premier démarrage avec la clé fournie, si l'ancien `secrets.cle` existe encore, le noyau s'en sert pour **lire** les secrets d'avant, les rechiffre
sous la nouvelle clé (la date de pose ne bouge pas) et le dit dans le journal. Quand le journal annonce « 0 illisible(s) », l'ancien fichier se supprime :

```bash
sudo rm <dossier des données>/secrets.cle
```

Sauvegarder la clé **à part** de la base : sans elle, les secrets sont perdus (il suffit alors de les ressaisir ; le reste ne dépend pas d'eux).

## 2. Qui a lu quel secret

Chaque lecture d'un secret par un module (`ctx.reglage`) est notée : module, compte, nom du réglage, moment. **Jamais la valeur.** Le journal est élagué
au-delà de 180 jours. L'administrateur (droit `reglages.gerer`) le lit par la capacité `reglages.secrets_lectures`. Les agents n'y ont pas accès.

## 3. Âge et rotation

La date de pose de chaque secret est gardée (table `reglages_poses` ; pour un secret posé avant, la date de dernière modification en tient lieu et la
réponse le dit). La capacité `reglages.secrets_ages` rend l'âge de chacun et signale ceux qui dépassent `reglages.secret_age_max_jours` (90 jours par
défaut, réglable). Aucune valeur n'est affichée.

## 4. Secrets-pièges

Quelques noms de secrets plausibles, qu'aucun module ne déclare, rendent une valeur fausse. Personne n'a de raison de les lire : **toute lecture est
une alarme**. Le noyau écrit au journal en niveau critique et ouvre un constat critique (donc une notification aux administrateurs). La réaction est
volontairement mesurée : le noyau ne gèle rien seul, puisqu'une règle de gel doit être posée par l'administrateur (module `urgence`, frein « gel »)
et qu'un module légitime mais bogué peut toucher un nom par erreur. L'événement `noyau.piege_touche` porte le module, le compte et le nom lus ; une
règle de l'administrateur peut s'y accrocher.

## Ce que ces garde-fous ne font pas

- Un module est chargé dans le processus du noyau : il peut lire la mémoire du noyau, donc la clé. Seule la cage par processus (chantier H2 de l'audit) le
  réglera. Le journal des lectures et les pièges rendent un tel accès **visible**, pas impossible.
- Un secret n'est jamais rendu à un agent : un banc (`tests/CN_test_secrets_agents.py`) échoue si une capacité d'un module expose la valeur d'un secret à un agent.
<!-- ▲▲▲ FIN BORNE CN ▲▲▲ -->

<!-- ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════ -->
<!-- CN : tout ce fichier est du nexus : à compléter -->
<!-- EC : néant (aucun point d'évolution déclaré pour l'instant) -->
<!-- LIEN : à compléter (contrat, fichiers voisins) -->
