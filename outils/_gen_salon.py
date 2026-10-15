"""Jetable : écrit modules/salon/manifeste.toml, et ouvre agents.converser aux résidents (ils répondent dans un fil)."""
LECT = [
    ("fils", "Mes fils de travail (ceux dont je suis membre) : non-lus, voix, membres, rangement"),
    ("lire", "Les messages d'un fil : les derniers, ceux qui suivent un id, ou la page qui précède"),
    ("chercher", "Chercher dans les messages de mes fils, par l'index plein texte"),
    ("etat", "Le panneau de présence : chaque résident (en tour ou en veille, son dernier mot), le budget de tours, les terrains"),
    ("journal", "Les gestes que j'ai faits sur les fils (suppressions, statuts, terrains), avec ce qui disparaissait"),
    ("resume", "Le résumé roulant du passé d'un fil long"),
    ("membres", "Le propriétaire d'un fil et les comptes invités"),
    ("attendre", "Attendre un nouveau message dans un fil (bloque, borné à 55 s) : pour un agent invité qui veille"),
]
ECR = [
    ("fil_creer", "Ouvrir un fil de travail : titre, but, terrain", "faible", ["raconter", "auto", "maitre"], "un fil du compte", "le fil existe", "supprimer le fil et ses messages"),
    ("fil_supprimer", "Supprimer un fil et ses messages (le propriétaire) : la trace est écrite avant le geste", "moyen", ["raconter", "auto"], "un fil du compte, ses messages et ses membres", "le fil n'existe plus", "remettre le fil, ses membres et ses messages"),
    ("fil_statut", "Passer un fil à ouvert, en attente, terminé ou archivé", "faible", ["raconter", "auto", "maitre"], "le statut d'un fil", "le statut relu est celui posé", "remettre le statut d'avant"),
    ("fil_mode", "Passer un fil en mode « plan d'abord » (les agents proposent, n'exécutent rien) ou « agir »", "faible", ["raconter", "auto", "maitre"], "le mode d'un fil", "le mode relu est celui posé", "remettre le mode d'avant"),
    ("fil_terrain", "Poser le terrain d'un fil (créatif, desk, citadelle, cherche) : un nom, jamais une permission", "faible", ["raconter", "auto", "maitre"], "le terrain d'un fil", "le terrain relu est celui posé", "remettre le terrain d'avant"),
    ("dire", "Poster un message dans un fil, avec ses destinataires (un champ : le corps n'est jamais lu pour router) ; adresser un résident le réveille", "faible", ["raconter", "auto", "maitre"], "un message d'un fil du compte", "le message existe", "supprimer le message"),
    ("message_supprimer", "Supprimer un message (son auteur, ou le propriétaire du fil) : la trace est écrite avant le geste", "moyen", ["raconter", "auto"], "un message d'un fil du compte", "le message n'existe plus", "remettre le message"),
    ("membre_inviter", "Inviter un autre compte dans un fil (le propriétaire)", "faible", ["raconter", "auto", "maitre"], "un fil du compte", "le compte est membre", "retirer le membre"),
    ("membre_retirer", "Retirer un membre d'un fil (le propriétaire), ou quitter le fil", "faible", ["raconter", "auto", "maitre"], "un fil du compte", "le compte n'est plus membre", "remettre le membre"),
    ("ranger", "Ranger un fil dans les archives de ce compte (ou l'en sortir) : le fil vit pour tous", "faible", ["raconter", "auto", "maitre"], "le rangement d'un compte", "le rangement relu est celui posé", "remettre le rangement d'avant"),
    ("vu", "Marquer un fil comme lu jusqu'ici", "faible", ["raconter", "auto", "maitre"], "ce que ce compte a lu", "le point de lecture relu est celui posé", "remettre le point de lecture d'avant"),
    ("relancer", "Demander à un résident de répondre maintenant dans un fil (le budget de tours entre agents s'applique)", "faible", ["raconter", "auto", "maitre"], "un tour d'un agent résident", "un tour s'est terminé", "retirer le message que ce tour a posé"),
]
t = '''[module]
id = "salon"
nom = "Le Salon"
version = "0.1.0"
noyau_min = "0.1.0"
description = "Des fils de travail où les personnes et les agents se parlent : un message a un auteur, des destinataires et un corps ; adresser un agent résident (Cassandra, Itare) le fait répondre dans le fil, un tour à la fois, avec un budget qui borne la conversation d'agents entre eux. Cloisonné : un compte ne voit que ses fils."
confiance = "interne"
famille = "echanges"

[[objets]]
type = "fil"
libelle = "Un fil de travail du salon"

[evenements]
emet = ["fil.message"]

[[reglages]]
id = "budget_tours"
libelle = "Messages d'agents de suite, sans humain, au-delà desquels plus aucun agent ne répond (deux agents qui se répondent ne s'arrêteraient jamais)"
type = "entier"
defaut = 8

[[moteurs]]
id = "reveil"
libelle = "Un message est posté : chaque agent résident adressé répond dans le fil, à tour de rôle, au nom du compte qui a parlé"
mode = "evenement"
sur = ["fil.message"]
duree_max_s = 900
asynchrone = true
'''
for cid, lib in LECT:
    t += '\n[[capacites]]\nid = "%s"\nlibelle = "%s"\nrisque = "lecture"\n' % (cid, lib)
for cid, lib, risque, paliers, perim, preuve, retour in ECR:
    qui = '["humain", "compte", "cassandra", "itare", "agent"]' if cid in ("dire", "fil_creer") else '["humain", "compte", "cassandra", "itare"]'
    if cid == "dire":
        paliers = ["raconter", "auto", "maitre"]
    t += '\n[[capacites]]\nid = "%s"\nlibelle = "%s"\nrisque = "%s"\nperimetre = ["%s"]\npreuve = "%s"\nretour = "%s"\npaliers = [%s]\nqui = %s\n' % (
        cid, lib, risque, perim, preuve, retour, ", ".join('"%s"' % p for p in paliers), qui)
t += '''
[[ecrans]]
id = "vue_salon"
libelle = "Le Salon"
domaine = "echanges"
gabarit = "liste_detail"

[[menus]]
id = "salon"
libelle = "Le Salon"
ecran = "vue_salon"
ordre = 5
icone = "chat"

[permissions]
stockage = true
lectures = true
agir = true
'''
open("modules/salon/manifeste.toml", "w", encoding="utf-8", newline="\n").write(t)

p = "modules/agents/manifeste.toml"
s = open(p, encoding="utf-8").read()
a = s.index('id = "converser"')
b = s.index('qui = ["humain", "compte"]', a)
s = s[:b] + 'qui = ["humain", "compte", "cassandra", "itare"]' + s[b + len('qui = ["humain", "compte"]'):]
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
