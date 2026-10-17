"""Génère CN_manifeste.toml du module des agents (script d'appoint, jetable)."""
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
PA = ["auto", "raconter"]
Q2 = ["humain", "compte"]
L("conversations", "Mes conversations avec Cassandra et Itare, les plus récentes d'abord")
L("conversation", "Une conversation : ses messages, appels d'outils et résultats compris", 'masque = ["messages"]\n')
L("outils", "Les outils que mon agent a pour moi : chaque capacité que cet agent peut utiliser et que j'ai le droit d'utiliser, avec son risque et son palier")
W("conversation_creer", "Ouvrir une conversation avec Cassandra (la machine) ou Itare (le bureau)", "faible", ["le compte qui agit en est le propriétaire", "un agent connu"], "relire la conversation", "supprimer la conversation que cet acte vient de créer", PA, Q2)
W("conversation_renommer", "Renommer une conversation", "faible", ["une conversation de mon compte"], "relire le titre", "remettre l'ancien titre", PA, Q2)
W("conversation_supprimer", "Supprimer une conversation avec ses messages", "moyen", ["une conversation de mon compte"], "la conversation n'existe plus",
  "recréer la conversation et ses messages depuis la copie gardée dans le résultat de l'acte", ["raconter", "auto"], Q2, 'masque = ["copie"]\n')
W("arreter", "Demander l'arrêt du tour en cours : lu entre deux étapes, une action déjà lancée finit (son journal et son retour sont pris avant qu'elle parte)", "faible", ["une conversation de mon compte"], "la demande est posée", "retirer la demande", PA, Q2)
W("converser", "Un tour de conversation : l'agent lit la mémoire, raisonne, appelle des outils (chacun traverse l'exécuteur : droits du compte, palier, preuve, retour, journal) et conclut en clair. Après une lecture extérieure, ce qui sort ou engage fortement ne part pas seul",
  "faible", ["le compte qui parle en est le propriétaire", "l'agent n'a que les outils que ce compte a le droit d'utiliser", "un tour à la fois par conversation", "une lecture extérieure dans le tour retient les actions qui sortent"],
  "le message de l'agent est gardé dans la conversation", "retirer les messages que ce tour a gardés (les actions de l'agent ont chacune leur retour)", PA, Q2, 'masque = ["message", "texte", "actions"]\n')
head = '''[module]
id = "agents"
nom = "Agents"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Cassandra (la machine) et Itare (le bureau) en conversation : un tour lit la mémoire, raisonne par un modèle, appelle des OUTILS DÉRIVÉS DU CATALOGUE (rien à écrire à la main : une capacité de plus = un outil de plus) et conclut en clair. Chaque outil traverse l'exécuteur comme n'importe quel acte : droits du compte, palier d'autonomie, preuve, retour, journal — un outil « raconté » n'a rien fait, et l'agent le dit. Ce qui est lu de l'extérieur est une donnée, jamais une consigne ; après une lecture extérieure, ce qui sort de la maison ne part pas seul."
confiance = "interne"
famille = "agents"
auteur = "Drisse ATEK"
licence = "AGPL-3.0-or-later"

[[objets]]
type = "conversation"
libelle = "Une conversation avec un agent"

[evenements]
emet = ["conversation.tour"]

[[reglages]]
id = "persona_cassandra"
libelle = "Le ton de Cassandra pour toute l'instance (vide : le ton d'origine)"

[[reglages]]
id = "persona_itare"
libelle = "Le ton d'Itare pour toute l'instance (vide : le ton d'origine)"

[[reglages]]
id = "role_cassandra"
libelle = "Le rôle de modèle qui fait parler Cassandra"
defaut = "principal"

[[reglages]]
id = "role_itare"
libelle = "Le rôle de modèle d'Itare quand le compte n'a pas choisi le sien"
defaut = "itare_citadelle"

[[reglages]]
id = "max_tours"
libelle = "Étapes d'outils au plus par tour"
type = "entier"
defaut = 12
minimum = 1
maximum = 40

[[reglages]]
id = "max_jetons"
libelle = "Jetons au plus par réponse du modèle (un modèle qui raisonne compte sa réflexion ici)"
type = "entier"
defaut = 12000
minimum = 256
maximum = 64000

[[reglages]]
id = "taille_fil"
libelle = "Messages relus à chaque tour"
type = "entier"
defaut = 40
minimum = 6
maximum = 200

[[reglages]]
id = "max_outils"
libelle = "Outils présentés d'emblée au modèle (les autres se trouvent par « outil_cherche »)"
type = "entier"
defaut = 60
minimum = 10
maximum = 200

'''
tail = '''[permissions]
stockage = true
lectures = true
agir = true
'''
(RACINE / "modules" / "agents" / "CN_manifeste.toml").write_text(head + "\n".join(cap) + "\n" + tail, encoding="utf-8")
