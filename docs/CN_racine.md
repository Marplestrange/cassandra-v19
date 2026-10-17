# La racine : demander du root sans en donner

Un module qui doit faire quelque chose que le noyau (sans privilège) ne peut pas faire — lire les tâches planifiées de tous les utilisateurs, régler le pare-feu, relancer un service système — **déclare des commandes nommées** :

```toml
[[racine]]
id = "lire_crons"
libelle = "Lire les tâches planifiées de tous les utilisateurs"
lecture = true

[permissions]
racine = true
```

Le module les appelle par `ctx.racine("lire_crons", ["--tous"])` et reçoit `{ok, code, sortie, erreur}`.

## Ce qui rend cela sûr

* Le noyau ne dit **jamais quoi exécuter**, seulement quelle commande nommée de ce module, avec quels arguments (de simples chaînes).
* La commande est un petit programme que le **script d'installation du module** — lancé en root par l'administrateur, en connaissance de cause — a posé dans `/usr/libexec/cassandra/<module>/<commande>`. Il appartient à root, n'est modifiable par personne d'autre ; le noyau ne peut ni le créer ni le changer.
* Le courtier (`exploitation/CN_courtier.py`, root, réveillé par systemd) vérifie les noms, les tailles, que le programme et ses dossiers appartiennent à root sans être modifiables par d'autres, qu'aucun lien symbolique n'est en jeu ; puis lance le programme **sans shell**, environnement réduit, délai borné.
* Chaque programme **valide lui-même ses arguments** : c'est lui qui sait ce qu'il peut casser.
* Le résultat revient par un fichier créé sans suivre de lien (le noyau ne peut pas faire écrire root ailleurs).
* Sans programme posé : « commande absente ». Une mise à jour du noyau ou d'un module ne donne donc jamais de nouveau pouvoir : seule une installation en root le fait.

## Écrire une commande

```sh
#!/bin/sh
# /usr/libexec/cassandra/planifie/lire_crons — posé par CN_installer.sh du module, root:root 0755
set -eu
for u in $(cut -d: -f1 /etc/passwd); do crontab -l -u "$u" 2>/dev/null | sed "s/^/$u\t/"; done
```

Un script d'installation de module la pose avec `install -D -m 0755 -o root -g root commandes/lire_crons /usr/libexec/cassandra/planifie/lire_crons` ; son script de retrait la retire.
