# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #8e9f2e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : l'événement dans le bureau de Cassandra (un projet et ses tâches).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8e9f2e ▼▼▼
"""Billetterie : l'événement dans le bureau de Cassandra (un projet et ses tâches).

Organiser une soirée, c'est surtout des tâches : le contrat de la salle, l'assurance, la déclaration à la SACEM, la sécurité, la buvette, les bénévoles, la communication, la décision de maintenir
ou d'annuler, puis le solde. Cette capacité crée dans le module Projets le projet de l'événement et, dans le module Tâches, ces étapes avec leurs échéances calculées sur la date de la soirée.
Elle agit au nom du compte qui la demande, comme un agent (Itare, Cassandra), avec les droits de ce compte sur Projets et Tâches : la billetterie n'écrit jamais dans leurs bases.
Le retour détache le projet de l'événement ; le projet et ses tâches restent (on les archive depuis Projets : un agent n'y supprime rien).
"""
from __future__ import annotations

from datetime import date, timedelta

from . import CN_regles as r
from . import CN_ventes as v

# (jours avant la soirée — négatif — ou après, intitulé)
MODELE = ((-60, "Contrat de la salle signé"), (-45, "Assurance de l'événement"), (-45, "Déclaration SACEM / droits d'auteur"), (-30, "Sécurité et secours"), (-30, "Buvette : licence et approvisionnement"),
          (-21, "Bénévoles : planning et consignes"), (-14, "Communication : affiche, réseaux, mailing"), (-7, "Décision : maintenir, annuler ou reporter (seuil de rentabilité)"),
          (-1, "Dernière vérification : liste d'invitations, caisse, contrôle"), (7, "Solde : factures, règlements, retraits des revendeurs, bilan"))


def brancher(ctx, db):
    class Raconte(Exception):
        """Le module visé n'a pas encore laissé les agents agir seuls sur cette capacité (palier « raconter ») : l'acte est raconté, pas fait."""

    def agir(capacite, args):
        rep = ctx.agir(capacite, args, acteur="itare")
        if rep.get("statut") == "racontee":
            raise Raconte(capacite)
        if rep.get("statut") != "faite":
            raise ValueError(rep.get("erreur") or rep.get("raison") or "« %s » n'a pas abouti (%s)" % (capacite, rep.get("statut")))
        return rep["resultat"]

    def projet(c, evenement_id=0, avec_taches=True):
        with db.transaction() as tx:
            e = r.ligne(tx, "evenements", evenement_id)
            if not e:
                raise ValueError("événement introuvable")
            if e["projet_ref"]:
                raise ValueError("cet événement a déjà son projet (%s)" % e["projet_ref"])
            if not e["date_iso"]:
                raise ValueError("fixez la date de l'événement : les échéances des tâches en dépendent")
        aujourd_hui = date.fromisoformat(v.aujourdhui())
        soiree = date.fromisoformat(e["date_iso"])
        try:
            p = agir("projets.creer", {"nom": "Événement · %s" % e["nom"], "debut": aujourd_hui.isoformat(), "fin": (soiree + timedelta(days=14)).isoformat(),
                                       "resume": "Organisation de « %s » le %s." % (e["nom"], e["date_iso"]), "objectif": "Une soirée maintenue, bien tenue et soldée."})
        except Raconte:
            return {"evenement_id": e["id"], "projet_id": None, "taches": [], "racontee": True,
                    "message": "Le module Projets demande encore une validation pour ce que font les agents (palier « raconter ») : rien n'a été créé. Passez-le en « auto » (Autonomie des modules), ou créez le projet vous-même."}
        taches = []
        if avec_taches:
            for rang, (decalage, texte) in enumerate(MODELE, 1):
                echeance = max(aujourd_hui, soiree + timedelta(days=decalage))           # une étape déjà en retard est à faire aujourd'hui
                try:
                    t = agir("taches.creer", {"texte": texte, "projet_id": p["id"], "echeance": echeance.isoformat(), "source": "billetterie", "origine": "%s:%d" % (e["ref"], rang)})            # une origine par tâche : Tâches ne crée jamais deux fois la même
                except Raconte:
                    break                                                                 # le projet existe, les tâches attendent la validation du module Tâches
                taches.append(t["id"])
        with db.transaction() as tx:
            tx.execute("UPDATE evenements SET projet_ref = ? WHERE id = ?", ("projet:%s" % p["id"], e["id"]))
        return {"evenement_id": e["id"], "projet_id": p["id"], "taches": taches}

    def prouver_projet(c, res):
        if res.get("racontee"):
            return True
        x = db.lire("SELECT projet_ref FROM evenements WHERE id = ?", (res["evenement_id"],))
        return bool(x) and x[0]["projet_ref"] == "projet:%s" % res["projet_id"]

    def defaire_projet(c, res):
        if res.get("racontee"):
            return
        db.ecrire("UPDATE evenements SET projet_ref = '' WHERE id = ? AND projet_ref = ?", (res["evenement_id"], "projet:%s" % res["projet_id"]))

    ctx.implementer("evenement_projet", projet, prouver_projet, defaire_projet, simuler=lambda x, evenement_id=0, **_: "créerait le projet de l'événement %s et ses tâches dans le bureau" % evenement_id)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
