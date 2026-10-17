# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Jetable
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : outils
# ZONE       : CN
# VERSION CN : 0.1.0  #d53a83
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Jetable : écrit modules/flotte/CN_manifeste.toml.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=d53a83 ▼▼▼
"""Jetable : écrit modules/flotte/CN_manifeste.toml."""
LECT = [
    ("parc", "Le parc fusionné : une machine par nom, les sources côte à côte (registre, Tailscale, SSH, relevés) avec leur âge, l'engagement, la disponibilité mesurée", False),
    ("verdict", "Ce que le parc dit à l'ouverture : pannes, machines sans contrôle, pertes répétées, disparues ; « tout répond » seulement si la présence tourne", False),
    ("machines", "Le registre des machines déclarées (les secrets ne ressortent jamais : seulement lesquels sont posés)", False),
    ("historique", "L'historique d'une machine : disponibilité, mesures, événements, liens, derniers relevés", False),
    ("disponibilite", "Le taux de disponibilité de chaque machine sur N jours, avec les pannes et le temps d'indisponibilité", False),
    ("evenements", "Les derniers événements de la flotte (pertes, retours, découvertes, disparitions, contrôles, actions)", False),
    ("liens", "Les liens d'une machine vers un projet, un contact, un domaine, une note", False),
    ("actions", "Les commandes nommées qu'on peut lancer sur une machine, et lesquelles modifient", False),
    ("ping", "La latence jusqu'à une machine du tailnet, à l'instant", True),
    ("diagnostic", "Une commande nommée de LECTURE sur une machine, par SSH (diagnostic, disques, mémoire, services, journal, réseau)", True),
]
ECR = [
    ("machine_ajouter", "Déclarer (ou mettre à jour) une machine au registre : SSH, ping ou autre Cassandra ; clé, mot de passe et jeton chiffrés", "moyen", ["raconter", "auto"], "une ligne du registre", "la machine est au registre", "remettre la ligne d'avant, ou la retirer si elle était nouvelle"),
    ("machine_retirer", "Retirer une machine du registre (son historique reste)", "moyen", ["raconter", "auto"], "une ligne du registre", "la machine n'est plus au registre", "remettre la ligne retirée, secrets chiffrés compris"),
    ("machine_basculer", "Suspendre ou réactiver la surveillance d'une machine du registre", "faible", ["raconter", "auto", "maitre"], "une ligne du registre", "l'état actif relu est celui demandé", "remettre l'état d'avant"),
    ("engagement", "Poser le statut (attendue, intermittente, retirée) et le niveau de contrôle d'une machine", "faible", ["raconter", "auto", "maitre"], "l'engagement d'une machine", "l'engagement relu est celui posé", "remettre l'engagement d'avant, ou l'effacer"),
    ("lien_enregistrer", "Lier une machine à un projet, un contact, un domaine ou une note", "faible", ["raconter", "auto", "maitre"], "un lien de machine", "le lien existe", "retirer le lien, ou remettre sa note d'avant"),
    ("lien_retirer", "Retirer le lien d'une machine", "faible", ["raconter", "auto", "maitre"], "un lien de machine", "le lien n'existe plus", "remettre le lien retiré"),
    ("oublier", "Oublier une machine DISPARUE du tailnet : ses traces s'effacent, l'historique reste", "moyen", ["raconter", "auto"], "les traces d'une machine absente du tailnet et du registre", "plus aucune trace de présence, de sonde, de relevé ni d'engagement", "remettre les traces effacées"),
    ("service_agir", "Démarrer, arrêter ou redémarrer un service d'une machine par SSH (jamais ce qui coupe le lien : sshd, réseau)", "eleve", ["raconter", "auto"], "un service d'une machine du parc", "l'état du service relu est celui attendu", "remettre le service dans l'état où il était avant"),
]
t = '''[module]
id = "flotte"
nom = "Flotte"
version = "0.1.1"
noyau_min = "0.1.0"
description = "Le parc de machines : le registre déclaré, Tailscale et les relevés SSH côte à côte, la présence mesurée, la disponibilité, le verdict d'ouverture, les commandes nommées sur une machine. Réservé à l'administrateur."
confiance = "interne"
famille = "reseau"

[[droits]]
id = "gerer"
libelle = "Déclarer, retirer, engager, oublier une machine ; démarrer ou arrêter un service à distance"
sensible = true

[[objets]]
type = "serveur"
libelle = "Une machine du parc"

[evenements]
emet = ["serveur.perte", "serveur.retour", "serveur.disparition", "serveur.controle"]

[[reglages]]
id = "presence_active"
libelle = "Relever la présence des machines (sans elle, le parc ne peut pas dire qu'il répond)"
type = "booleen"
defaut = true

[[reglages]]
id = "presence_s"
libelle = "Période de la présence, en secondes"
type = "entier"
defaut = 300

[[reglages]]
id = "delai_s"
libelle = "Délai global d'une passe sur le registre, en secondes (une machine lente ne retient pas les autres)"
type = "entier"
defaut = 20

[[reglages]]
id = "sonde_utilisateurs"
libelle = "Utilisateurs essayés par la sonde Tailscale SSH (séparés par des virgules)"
defaut = "root"

[[moteurs]]
id = "presence"
libelle = "Relève la présence (Tailscale et registre), date les transitions, constate le contrôle SSH, oublie les disparues"
mode = "periodique"
toutes_les_s = 300
duree_max_s = 120

[[moteurs]]
id = "releve"
libelle = "Une sonde SSH par machine contrôlable : disques, mémoire, charge, redémarrage requis, services en échec, RAID, température"
mode = "periodique"
toutes_les_s = 900
duree_max_s = 600

[[detecteurs]]
id = "machine_muette"
libelle = "Une machine attendue ne répond plus"
frequence_s = 300
'''
for cid, lib, ext in LECT:
    t += '\n[[capacites]]\nid = "%s"\nlibelle = "%s"\nrisque = "lecture"\n' % (cid, lib)
    if ext:
        t += "externe = true\n"
for cid, lib, risque, paliers, perim, preuve, retour in ECR:
    t += '\n[[capacites]]\nid = "%s"\nlibelle = "%s"\nrisque = "%s"\ndroit = "gerer"\nperimetre = ["%s"]\npreuve = "%s"\nretour = "%s"\npaliers = [%s]\nqui = ["humain", "cassandra"]\n' % (
        cid, lib, risque, perim, preuve, retour, ", ".join('"%s"' % p for p in paliers))
t += '''
[[ecrans]]
id = "vue_flotte"
libelle = "Flotte"
domaine = "reseau"
gabarit = "tableau"

[[menus]]
id = "flotte"
libelle = "Flotte"
ecran = "vue_flotte"
ordre = 40
role = "admin"
icone = "server"
badge = "constats"

[[widgets]]
id = "etat_parc"
libelle = "Le parc"
ecran = "accueil"
zone = "principal"
taille = "m"
role = "admin"
composant = "etat"
source = "verdict"
rafraichir_s = 60

[[capacites]]
id = "serie"
libelle = "Les points de présence et de ressources de chaque machine (une courbe par machine) et les pertes, pour l'historique"
risque = "lecture"

[[mesures]]
id = "fleet_up"
libelle = "Flotte — disponibilité"
capacite = "serie"
unite = "%"
famille = "Flotte"
groupee = true
pire = "bas"
description = "Part du temps où chaque machine a répondu."

[[mesures]]
id = "fleet_cpu"
libelle = "Flotte — processeur"
capacite = "serie"
unite = "%"
famille = "Flotte"
groupee = true
description = "Charge processeur, une courbe par machine."

[[mesures]]
id = "fleet_ram"
libelle = "Flotte — mémoire"
capacite = "serie"
unite = "%"
famille = "Flotte"
groupee = true
description = "Mémoire occupée, une courbe par machine."

[[mesures]]
id = "fleet_disk"
libelle = "Flotte — disque"
capacite = "serie"
unite = "%"
famille = "Flotte"
groupee = true
description = "Remplissage disque par machine."

[[mesures]]
id = "fleet_down"
libelle = "Flotte — pertes"
capacite = "serie"
genre = "compteur"
unite = "/j"
famille = "Flotte"
vide = "rien_a_signaler"
description = "Machines tombées. Une seule occurrence mérite qu'on regarde."

[permissions]
stockage = true
secrets = true
reseau = ["Tailscale (binaire local), les machines déclarées par SSH, TCP ou HTTP"]
'''
open("modules/flotte/CN_manifeste.toml", "w", encoding="utf-8", newline="\n").write(t)
print("ok")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : constantes et configuration
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
