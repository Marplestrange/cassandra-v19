"""Génère manifeste.toml de la mémoire (script d'appoint, jetable)."""
import json
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
j = lambda x: json.dumps(x, ensure_ascii=False)
cap = []


def L(id, lib, extra=""):
    cap.append('[[capacites]]\nid = "%s"\nlibelle = "%s"\nrisque = "lecture"\n%s' % (id, lib, extra))


def W(id, lib, risque, per, preuve, retour, paliers, qui, extra=""):
    cap.append('[[capacites]]\nid = "%s"\nlibelle = "%s"\nrisque = "%s"\nperimetre = %s\npreuve = "%s"\nretour = "%s"\npaliers = %s\nqui = %s\n%s' % (id, lib, risque, j(per), preuve, retour, j(paliers), j(qui), extra))


P3 = ["raconter", "auto", "maitre"]
P2 = ["raconter", "auto"]
Q5 = ["humain", "compte", "cassandra", "itare", "agent"]
Q2 = ["humain", "compte"]
L("rappeler", "Le rappel : le noyau (épinglés, personne) d'abord, puis le plein texte sur l'actif seul, dans ma portée, avec le seuil de pertinence ; rend un bloc de prompt, les souvenirs cités et les doutes à poser", 'masque = ["bloc", "question"]\n')
L("lister", "Les souvenirs de ma portée, par statut et catégorie")
L("chercher", "La recherche plein texte de l'écran, dans ma portée")
L("lire", "La fiche d'un souvenir : versions, pièce, copies, journal (hors de ma portée : introuvable, jamais interdit)")
L("etat", "Les chiffres de l'écran : statuts, catégories, refus de la semaine, doutes ouverts, dernière vérification de la chaîne")
L("journal", "Le journal borné à ma portée")
L("exporter", "L'export JSON de ma portée avec l'empreinte de l'ensemble")
L("doutes", "Les questions que la mémoire se pose, à moi")
L("episodes", "Les épisodes de mes sessions, et la recherche « la dernière fois qu'on a parlé de… »")
L("rappels", "Les rappels conditionnés aux capteurs")
L("perception", "Ce que les capteurs disent MAINTENANT, avec l'âge de chaque relevé : un état se mesure, il ne se rappelle pas")
L("chaine_verifier", "Recalcule toute la chaîne du journal : une altération se voit, elle ne s'empêche pas")
W("ecrire", "LA porte d'écriture : catégorie, clé en mots-clés, nature (état courant avec sonde, ou constat), gardes (secret, consigne, données sensibles, sujet, quotas, plafond de confiance) ; un refus est un résultat, journalisé avec sa raison", "faible",
  ["dans ma portée seulement", "une catégorie du vocabulaire fermé", "la nature est exigée : un souvenir muet sur sa nature est refusé", "aucun secret, aucune consigne, aucune donnée sensible", "quotas par heure, par compte et par déclencheur", "la confiance est plafonnée par la provenance"],
  "relire le souvenir : valeur, statut et propriétaire conformes", "faire expirer la version écrite et rendre la précédente à l'état actif", P3, Q5, 'masque = ["valeur", "piece"]\n')
W("corriger", "Corriger : une version nouvelle liée à l'ancienne, jamais une édition en place", "faible", ["un souvenir de ma portée"], "la nouvelle version est active (ou en quarantaine) et liée", "faire expirer la correction et rendre la version d'avant", P3, Q5, 'masque = ["valeur"]\n')
W("oublier", "Oublier : expirer avec la raison, jamais de suppression ; j'ai le dernier mot", "faible", ["un souvenir de ma portée"], "le souvenir est expiré", "le restaurer s'il ne s'est pas fait remplacer", P3, Q5)
W("restaurer", "Restaurer un souvenir expiré (sauf si une version plus neuve occupe la clé)", "faible", ["un souvenir de ma portée"], "le souvenir est actif", "l'expirer de nouveau", P3, Q5)
W("forcer", "Épingler (force 1) ou relâcher : un réglage de rappel, la seule colonne qui se touche en place, et elle se journalise", "faible", ["un souvenir de ma portée", "force entre 0 et 1"], "la force est celle demandée", "remettre la force d'avant", P3, Q5)
W("donner", "Donner ou prêter un souvenir : une copie liée par la porte, jamais un transfert ; un compte ne donne qu'au partagé", "moyen",
  ["un souvenir actif de ma portée", "un compte ne donne qu'au partagé", "un prêt dure 7 jours par défaut, 30 au plus"], "la copie existe chez le destinataire et porte « donné par »", "expirer la copie", P2, Q2)
W("don_retirer", "Retirer un don : la copie expire, tracé chez les deux", "faible", ["une copie dont je vois l'original"], "la copie est expirée", "réactiver la copie", P3, Q2)
W("purger_secret", "Un secret entré par erreur : expiré tout de suite ET sa valeur retirée de la ligne, de la pièce et de l'index ; la seule réécriture en place que la mémoire admet", "moyen",
  ["un souvenir de ma portée"], "la valeur n'est plus lisible nulle part, le geste reste au journal", "aucun, voulu : la valeur d'un secret ne revient pas", ["raconter"], Q2)
W("douter_resoudre", "Répondre à un doute : garder l'ancienne, prendre la nouvelle, c'est faux, plus d'actualité, toujours vrai, écrire (un report est admis une fois)", "faible",
  ["un doute de ma portée", "un choix parmi ceux que le doute propose"], "le doute est résolu et son effet appliqué", "remettre les souvenirs et le doute dans leur état d'avant", P3, Q5)
W("doutes_depuis_reponse", "Résoudre les « doute N : choix » écrits dans la réponse d'un humain", "faible", ["des doutes de ma portée"], "chaque doute cité est résolu ou refusé avec sa raison", "défaire chaque résolution, dans l'ordre inverse", P3, Q5)
W("veto_lever", "Lever la quarantaine ou le contesté d'un souvenir : il devient la version active, l'ancienne expire", "faible", ["un souvenir en quarantaine ou contesté de ma portée"], "le souvenir est actif", "remettre le souvenir et l'ancienne version dans leur état d'avant", P3, Q5)
W("rappel_poser", "Poser un rappel conditionné à une mesure (métrique, opérateur, seuil) : il rappelle, il n'exécute rien", "faible", ["une métrique connue", "un opérateur connu", "un message sans secret ni consigne"], "le rappel est actif", "retirer le rappel posé, ou remettre l'ancien", P3, Q5)
W("rappel_oter", "Ôter un rappel (désactivé, la ligne reste lisible)", "faible", ["un rappel de ma portée"], "le rappel est inactif", "le réactiver", P3, Q5)
W("tour_commencer", "À l'entrée d'un tour de chat : ce qu'un tour précédent a cité ne signe jamais la réponse d'un autre ; la question se range par compte", "faible", ["le tour du compte qui agit"], "le tour est ouvert", "remettre le tour d'avant", P3, Q5)
W("apres_echange", "À la fin d'un échange : l'épisode s'allonge, les messages sont gardés, et une distillation est mise en file SEULEMENT si un déclencheur a eu lieu", "faible", ["l'épisode du compte qui agit"], "l'épisode et la file portent l'échange", "retirer le message gardé et la demande de distillation", P3, Q5, 'masque = ["question", "reponse"]\n')

head = '''[module]
id = "memoire"
nom = "Mémoire"
version = "0.1.0"
noyau_min = "0.1.0"
description = "La mémoire de Cassandra : un souvenir est un fait daté, prouvé, propriétaire, corrigeable d'une phrase. Une seule porte d'écriture avec ses gardes (secret, consigne, données sensibles, sujet, quotas), des versions liées plutôt que des éditions, un veto pour les écritures critiques, des doutes posés à l'humain, des épisodes, des rappels conditionnés aux capteurs, un journal chaîné par empreintes. Un état se mesure, il ne se rappelle pas : « je ne sais pas » est une réponse de succès. Cloisonnée : on ne voit que sa portée."
confiance = "interne"
famille = "agents"
auteur = "Drisse ATEK"
licence = "AGPL-3.0-or-later"

[[objets]]
type = "souvenir"
libelle = "Un souvenir"

[evenements]
emet = ["souvenir.ecrit", "souvenir.rappel"]

[[reglages]]
id = "veto_actif"
libelle = "Les écritures critiques d'un agent attendent le veto (quarantaine) avant d'entrer"
type = "booleen"
defaut = true

[[reglages]]
id = "seuil_rappel_pct"
libelle = "Seuil de pertinence du rappel, en centièmes (40 = 0,40)"
type = "entier"
defaut = 40
minimum = 5
maximum = 95

[[moteurs]]
id = "entretien"
libelle = "Doutes échus, prêts échus, relecture de la péremption, rappels conditionnés, épisodes à fermer"
mode = "periodique"
toutes_les_s = 300
duree_max_s = 280

[[moteurs]]
id = "veto"
libelle = "Examine les souvenirs en quarantaine : gardes mécaniques puis relecteur"
mode = "periodique"
toutes_les_s = 20
duree_max_s = 120

[[moteurs]]
id = "distiller"
libelle = "Distille les échanges mis en file (un déclencheur a eu lieu)"
mode = "periodique"
toutes_les_s = 30
duree_max_s = 120

[[detecteurs]]
id = "chaine_rompue"
libelle = "Le journal chaîné de la mémoire a été altéré"
frequence_s = 86400

'''
tail = '''[permissions]
stockage = true
lectures = true
introspection = true
'''
(RACINE / "modules" / "memoire" / "manifeste.toml").write_text(head + "\n".join(cap) + "\n" + tail, encoding="utf-8")
