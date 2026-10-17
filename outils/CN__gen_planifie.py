"""Jetable : écrit modules/planifie/CN_manifeste.toml."""
LECT = [
    ("unifiee", "Toutes les tâches planifiées, quelle que soit leur origine, avec leur état (cassé, échec, muet, inconnu, ok, désactivé), leur prochaine exécution et leur criticité"),
    ("fiche", "Tout ce qu'une tâche peut dire d'elle-même : exécutions, réglages, prochaines dates, cibles présentes, dérive de durée, modifications"),
    ("historique", "Les dernières exécutions d'une tâche, avec code de sortie et sortie"),
    ("reglages", "Verrou, fenêtre, réessais, motif d'échec et enchaînement d'une tâche (ou de toutes)"),
    ("chevauchements", "Les tâches dont la durée moyenne dépasse leur propre intervalle"),
    ("audit", "Les créneaux saturés de tâches lourdes (avec une répartition proposée) et les projets d'infrastructure sans sauvegarde planifiée"),
    ("apercu", "Les prochaines exécutions d'une expression cron, avant de l'enregistrer"),
    ("maintenance_etat", "Le mode maintenance : actif ou non, et sa date de fin"),
    ("resume", "Le recensement : combien de tâches, combien en panne, la maintenance"),
]
ECR = [
    ("sauver", "Créer ou modifier une tâche planifiée : la base d'abord, puis la crontab ; si la crontab refuse, la base revient comme avant. Une commande destructrice exige un accord explicite", "eleve", ["raconter", "auto"], "une ligne de la crontab d'un utilisateur permis, et sa définition en base", "la ligne est (ou n'est plus) dans la crontab et la définition est celle posée", "remettre la définition d'avant et la ligne d'avant, ou retirer la tâche si elle était nouvelle"),
    ("basculer", "Désactiver ou réactiver une tâche (sa définition reste en base)", "moyen", ["raconter", "auto"], "une ligne de crontab", "la ligne est présente ou absente comme demandé", "remettre l'état d'avant"),
    ("supprimer", "Retirer une tâche de la crontab et de la base (la crontab d'abord)", "eleve", ["raconter", "auto"], "une ligne de crontab et sa définition", "la ligne n'est plus dans la crontab et la définition n'est plus en base", "remettre la définition, ses rattachements et la ligne"),
    ("critique", "Marquer une tâche critique (exemptée du mode maintenance)", "faible", ["raconter", "auto", "maitre"], "la criticité d'une tâche", "la marque relue est celle posée", "remettre la marque d'avant"),
    ("lier", "Rattacher une tâche à un projet", "faible", ["raconter", "auto", "maitre"], "un rattachement", "le rattachement existe", "retirer le rattachement"),
    ("delier", "Détacher une tâche d'un projet", "faible", ["raconter", "auto", "maitre"], "un rattachement", "le rattachement n'existe plus", "remettre le rattachement"),
    ("reglages_poser", "Régler verrou, fenêtre, réessais, motif d'échec et enchaînement d'une tâche (une boucle d'enchaînement est refusée)", "moyen", ["raconter", "auto"], "les réglages d'une tâche et les options lues par l'enrobage", "les réglages relus sont ceux posés", "remettre les réglages d'avant"),
    ("maintenance", "Suspendre toutes les tâches journalisées sauf les critiques, jusqu'à une date de fin (retour automatique), ou lever la maintenance", "moyen", ["raconter", "auto"], "la sentinelle lue par l'enrobage", "la date de fin relue est celle posée", "remettre la date d'avant"),
    ("executer", "Lancer UNE fois, tout de suite, une tâche déjà planifiée, et garder sa sortie (un essai n'écrit pas au journal). Ce que la commande a fait n'est pas défait par le retour", "eleve", ["raconter", "auto"], "l'exécution d'une commande déjà présente dans une table de planification", "la ligne du journal d'exécution existe (ou l'essai a rendu sa sortie)", "retirer la ligne du journal (l'effet de la commande, lui, ne se défait pas)"),
]
t = '''[module]
id = "planifie"
nom = "Tâches planifiées"
version = "0.1.1"
noyau_min = "0.1.0"
description = "Tout ce qui tourne tout seul sur la machine, et est-ce que ça va : les tâches de Cassandra et celles du système (crontabs, cron.d) fusionnées, l'état de chacune (cassée, en échec, muette), les exécutions réelles consignées par un enrobage, le verrou et la fenêtre, l'enchaînement, la maintenance, les collisions. Réservé à l'administrateur ; privilégié par nature, il passe par le courtier."
confiance = "interne"
famille = "systeme"

[[droits]]
id = "gerer"
libelle = "Créer, modifier, supprimer, lancer une tâche planifiée (elle s'exécute en root)"
sensible = true

[[objets]]
type = "tache_planifiee"
libelle = "Une tâche planifiée en panne, en dérive ou qui se chevauche"

[[moteurs]]
id = "passe"
libelle = "Range les comptes rendus de l'enrobage dans le journal, lance les tâches enchaînées dont l'amont a réussi, lève la maintenance échue"
mode = "periodique"
toutes_les_s = 60
duree_max_s = 600

[[detecteurs]]
id = "taches_en_panne"
libelle = "Une tâche cassée, en échec ou muette ; une durée qui dérive ; un chevauchement"
frequence_s = 600

[[racine]]
id = "lire_crontabs"
libelle = "Lire les tâches planifiées de tous les utilisateurs (crontabs et /etc/cron.d), cibles manquantes constatées par root"
lecture = true

[[racine]]
id = "lire_table"
libelle = "Lire le texte brut de la crontab d'un utilisateur, pour la réécrire sans rien perdre"
lecture = true

[[racine]]
id = "ecrire_crontab"
libelle = "Remplacer la crontab d'un utilisateur permis par un texte qui ne contient que commentaires, environnement et lignes de planning"

[[racine]]
id = "lancer"
libelle = "Lancer une fois une commande déjà présente dans une table de planification, avec un délai"
'''
for cid, lib in LECT:
    t += '\n[[capacites]]\nid = "%s"\nlibelle = "%s"\nrisque = "lecture"\n' % (cid, lib)
for cid, lib, risque, paliers, perim, preuve, retour in ECR:
    t += '\n[[capacites]]\nid = "%s"\nlibelle = "%s"\nrisque = "%s"\ndroit = "gerer"\nperimetre = ["%s"]\npreuve = "%s"\nretour = "%s"\npaliers = [%s]\nqui = ["humain", "cassandra"]\n' % (
        cid, lib, risque, perim, preuve, retour, ", ".join('"%s"' % p for p in paliers))
t += '''
[[ecrans]]
id = "vue_taches"
libelle = "Automatismes"
domaine = "systeme"
gabarit = "tableau"

[[menus]]
id = "taches"
libelle = "Automatismes"
ecran = "vue_taches"
ordre = 50
role = "admin"
icone = "clock"
badge = "constats"

[[widgets]]
id = "etat_taches"
libelle = "Les tâches planifiées"
ecran = "accueil"
zone = "principal"
taille = "s"
role = "admin"
composant = "etat"
source = "resume"
rafraichir_s = 120

[[capacites]]
id = "serie"
libelle = "Les exécutions planifiées et leurs échecs, pour l'historique"
risque = "lecture"

[[mesures]]
id = "cron_runs"
libelle = "Exécutions planifiées"
capacite = "serie"
genre = "compteur"
unite = "/h"
famille = "Infrastructure"
description = "Tâches planifiées réellement exécutées."

[[mesures]]
id = "cron_fail"
libelle = "Échecs planifiés"
capacite = "serie"
genre = "compteur"
unite = "/h"
famille = "Infrastructure"
vide = "rien_a_signaler"
description = "Tâches planifiées terminées en erreur."

[permissions]
stockage = true
lectures = true
racine = true
privileges = ["installer : trois commandes et un enrobage posés en root", "retirer : les défaire"]

[installation]
script = "CN_installer.sh"
verification = "CN_verifier.sh"
retrait = "CN_retirer.sh"
migrations = "migrations"
'''
open("modules/planifie/CN_manifeste.toml", "w", encoding="utf-8", newline="\n").write(t)
print("ok")
