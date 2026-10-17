# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La page « Les moteurs » de la mémoire
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : memoire
# ZONE       : CN
# VERSION CN : 0.1.0  #bfe0da
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La page « Les moteurs » de la mémoire : jamais une page écrite à la main, chaque nombre est LU dans les constantes en service (quotas, plafonds, seuils, durées). Portée de la V18 (memoire_moteurs) : le texte est le même, les valeurs viennen
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=bfe0da ▼▼▼
"""La page « Les moteurs » de la mémoire : jamais une page écrite à la main, chaque nombre est LU dans les constantes en service (quotas, plafonds, seuils, durées).
Portée de la V18 (memoire_moteurs) : le texte est le même, les valeurs viennent du module."""


def page(o) -> dict:
    """LA PAGE « LES MOTEURS » de la mémoire (20-09, t48 : jamais une page écrite à la main) : onze moteurs
    et le chemin d'un fait, chaque nombre LU dans le code en service — quotas, plafonds, seuils, durées."""
    d = o.duree_txt
    prov = " · ".join("%s %.2f" % (k, v[2]) for k, v in sorted(o.PROVENANCES.items(), key=lambda kv: kv[1][0]))
    routes = ", ".join(str(r[0]) for r in o.ROUTES)
    return {"ok": True,
        "regle": "<b>Un souvenir est un fait daté, prouvé, propriétaire, corrigeable d'une phrase.</b> Rien n'y entre sans passer la "
                 "porte, rien n'en sort comme présent s'il est périmé, rien ne s'y réécrit en place, tout s'y trace dans une chaîne "
                 "qu'une altération brise visiblement. Un état se mesure, il ne se rappelle pas. « Je ne sais pas » est une réponse de succès.",
        "flux": [
            {"n": "déclencheur", "t": "Liste fermée", "d": "%s. Une page lue, un mail, une vigie ne déclenchent rien." % ", ".join(o.DECLENCHEURS)},
            {"n": "candidat", "t": "Le modèle propose", "d": "Il reçoit l'échange en données, jamais en instructions, et rend un JSON : catégorie, clé, fait, confiance."},
            {"n": "gardes", "t": "Sous la milliseconde", "d": "Catégorie, clé en mots-clés, nature, anti-secret, anti-consigne, anti-données sensibles, sujet du compte, pièce contemporaine, quotas, plafond.", "garde": True},
            {"n": "réconciliation", "t": "Plus récent et plus fort", "d": "Humain > preuve d'outil > observé > inféré. Plus fort ou égal : remplace. Plus faible : contesté, et un doute s'ouvre."},
            {"n": "veto", "t": "Critiques d'agent", "d": "%s : quarantaine, gardes mécaniques puis Itare. Ta parole n'attend pas." % ", ".join(o.CRITIQUES)},
            {"n": "écriture", "t": "Une transaction", "d": "La ligne entre, l'ancienne expire avec le lien, la ligne du journal chaîné est dans la même transaction."},
            {"n": "rappel", "t": "Par règles, sans modèle", "d": "Route, noyau, plein texte sur l'actif, seuil ; bloc dans le prompt, pied gris sous la réponse."}],
        "moteurs": [
            {"n": "porte", "t": "La porte d'écriture", "p": "Une seule fonction écrit dans la mémoire. Tout ce qui apprend la traverse. Un refus se journalise avec sa raison et ne se négocie pas.",
             "valeurs": [["catégories", "%d, vocabulaire fermé" % len(o.CATEGORIES)], ["natures", " · ".join(o.NATURES)], ["valeur", "%d signes au plus" % o.VALEUR_MAX],
                         ["quotas", "%d écritures par heure · %d par compte et par jour · %d par déclencheur et par heure" % (o.QUOTA_GLOBAL_HEURE, o.QUOTA_COMPTE_JOUR, o.QUOTA_DECLENCHEUR_HEURE)],
                         ["confiance plafonnée", prov]],
             "non": "un filtre a posteriori : il n'y a pas de seconde porte, et rien ne réécrit une valeur en place, sauf la purge d'un secret entré par erreur, tracée."},
            {"n": "propriétaire", "t": "Le cloisonnement", "p": "Chaque souvenir a un propriétaire, jamais vide : ton compte, le partagé des administrateurs, Cassandra pour ce qu'elle apprend seule, Itare pour ses leçons. La portée du lecteur est dans la requête, pas dans le masquage de l'écran.",
             "valeurs": [["administrateur", "compte:x · partage · cassandra"], ["compte", "compte:x seulement ; son Itare pareil"], ["Itare Citadelle", "itare · partage · cassandra"], ["hors portée", "introuvable (404), jamais interdit (403)"]],
             "non": "une case « tout voir » : elle serait une faille par conception ; l'administrateur ne voit pas les comptes."},
            {"n": "rappel", "t": "Le rappel par règles", "p": "Zéro appel de modèle. La question est routée par motifs ; le noyau (épinglés, personne) entre toujours ; puis le plein texte sur l'actif seul, propriétaire dans la portée, fenêtre de vérité respectée.",
             "valeurs": [["routes", routes], ["seuil", "%.2f · personne %.2f · question ouverte %.2f" % (o.seuil("defaut", ""), o.seuil("personne", ""), o.seuil("episode", ""))],
                         ["bloc", "%d octets au plus, chaque [M:id] cliquable" % o.BLOC_MAX], ["cadran", "rappels vides et blocs saturés comptés, hors chaîne"]],
             "non": "un moteur vectoriel : le plein texte suffit à cette taille."},
            {"n": "perception", "t": "La perception, hors mémoire", "p": "Les capteurs de la vigie et du collecteur n'écrivent jamais un souvenir. Une question d'état lit le dernier relevé, avec son âge et sa durée de validité.",
             "valeurs": [["validité", "service %s · machine hors ligne %s · en ligne %s · site %s · disque %s · RAM et charge %s · certificat %s" % (d(o.PERCEPTION_TTL["service"]), d(o.PERCEPTION_TTL["machine_hors_ligne"]), d(o.PERCEPTION_TTL["machine_en_ligne"]), d(o.PERCEPTION_TTL["site"]), d(o.PERCEPTION_TTL["disque"]), d(o.PERCEPTION_TTL["ram"]), d(o.PERCEPTION_TTL["certificat"]))],
                         ["périmé", "« je ne sais plus, dernier relevé à T », jamais l'ancien état rendu comme présent"], ["sources", "tables « vues » de la vigie, puis world_model du collecteur"]],
             "non": "une mémoire des états : le Sensorium est un renvoi vers elle."},
            {"n": "distillation", "t": "La distillation par déclencheur", "p": "Un fait naît d'un événement de la liste fermée. Ce que tu dis de retenir entre comme « dit » ; un geste de cage comme « observé » ; l'outil et le déclencheur ne repassent pas l'un derrière l'autre.",
             "valeurs": [["déclencheurs", ", ".join(o.DECLENCHEURS)], ["quota", "%d souvenirs par déclencheur et par heure" % o.QUOTA_DECLENCHEUR_HEURE], ["pièce", "le message ou la commande qui fonde le fait, avec sa date"]],
             "non": "une horloge."},
            {"n": "doute", "t": "Le doute comme objet", "p": "Une contradiction ne dort pas dans un statut : elle se pose. Le doute naît d'une réconciliation, d'une revalidation, d'un veto ou d'un agent qui doute.",
             "valeurs": [["cadence", "%d par tour, à un humain seulement, jamais deux fois le même jour, trois fois au plus" % o.DOUTES_PAR_TOUR], ["sources", ", ".join(o.DOUTE_SOURCES)], ["silence", "à %d jours le doute expire sans effet" % o.DOUTE_ECHEANCE_J]],
             "non": "une relance : il n'insiste pas, il ne décide pas à ta place."},
            {"n": "veto", "t": "Le second avis", "p": "Une écriture critique qui ne vient pas de toi entre en quarantaine, hors du chemin de la réponse ; l'ancienne version reste servie. Les gardes mécaniques passent d'abord, puis Itare répond en JSON strict.",
             "valeurs": [["critiques", ", ".join(o.CRITIQUES) + ", ou force ≥ 0,9"], ["levée", "la ligne devient active, tracé « veto_leve »"], ["refus", "contestée, et un doute te le dit"]],
             "non": "un juge persuadable : Itare ne reçoit que des données."},
            {"n": "journal", "t": "Le journal chaîné", "p": "Chaque geste porte son empreinte et celle du précédent depuis une genèse constante. Une vérification quotidienne recalcule tout ; une rupture est une alerte critique.",
             "valeurs": [["empreinte", "sha256(précédente | date | acteur | verbe | souvenir | détails)"], ["genèse", o.GENESE[:16] + "…"], ["vérifié", "une fois par jour, et à la demande depuis l'écran"]],
             "non": "une protection : elle rend visible, elle n'empêche pas."},
            {"n": "épisodes", "t": "Les épisodes", "p": "Un segment continu d'une session, fermé par le silence, au relevé de cinq minutes. À la fermeture, le modèle en écrit le résumé.",
             "valeurs": [["silence", d(o.EPISODE_SILENCE_S)], ["sans modèle", "un repli honnête : la première question, marquée « résumé indisponible »"], ["portée", "les épisodes d'un compte lui appartiennent"]],
             "non": "une transcription : le fil garde les messages, l'épisode garde ce qui s'est passé."},
            {"n": "rappels", "t": "La mémoire adressée", "p": "Une condition mécanique sur une mesure des capteurs, évaluée à chaque relevé, jamais par le modèle. Quand elle devient vraie, une notification, au plus une par jour.",
             "valeurs": [["métriques", ", ".join(o.METRIQUES) + ", machine_hors_ligne:x, site_hors_ligne:x"], ["opérateurs", " ".join(o.RAPPEL_OPS)], ["posé par", "l'outil memoire_rappel de Cassandra, ou l'écran"]],
             "non": "un automatisme : le rappel rappelle, il n'exécute rien."},
            {"n": "don", "t": "Le don et le prêt", "p": "Donner un souvenir, c'est en copier une version liée chez le destinataire, par la porte. Corriger l'original retire ses copies ; retirer un don l'expire, tracé chez les deux.",
             "valeurs": [["prêt", "%d jours par défaut, %d au plus" % (o.PRET_JOURS, o.PRET_JOURS_MAX)], ["qui donne", "un compte au partagé seulement ; l'administrateur à un compte ou au partagé"]],
             "non": "un transfert : l'original reste à son propriétaire."},
            {"n": "oubli", "t": "L'oubli et la correction", "p": "Tu as le dernier mot. Oublier expire la ligne avec sa raison, réversible. Corriger écrit une version nouvelle liée à l'ancienne. Un secret entré par erreur est la seule exception : sa valeur est effacée, le geste reste.",
             "valeurs": [["jamais", "de DELETE automatique"], ["compte supprimé", "ses souvenirs expirent, tracés"], ["export", "JSON par portée avec l'empreinte de l'ensemble"]],
             "non": "un sermon : l'agent le dit en une phrase, puis obéit."}]}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : page
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
