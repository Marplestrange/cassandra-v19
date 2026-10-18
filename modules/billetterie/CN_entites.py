# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #ad37b2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : les fiches du module, assemblées (salles, formules, artistes, revendeurs, événements, billets, passages, affectations, invitations).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=ad37b2 ▼▼▼
"""Billetterie : les fiches du module, assemblées (salles, formules, artistes, revendeurs, événements, billets, passages, affectations, invitations)."""
from __future__ import annotations

from . import CN_crud as crud
from . import CN_regles as r
from . import CN_ventes as ventes

CHAMPS_SALLE = ("nom", "adresse", "contact", "location", "acompte", "caution", "assis", "debout", "pmr", "erp", "heure_fin", "bruit", "alcool", "age", "equipements", "annulation", "assurance")
CHAMPS_FORMULE = ("nom", "role", "forfait", "com", "fixe", "palier_n", "palier_com", "note")
CHAMPS_ARTISTE = ("scene", "legal", "genre", "statut", "mail", "tel", "rider", "bio", "formule_id", "vend", "siret", "ape", "tva", "adresse", "code_postal", "ville", "pays", "adhesion_fin", "compte")
CHAMPS_REVENDEUR = ("nom", "statut", "mail", "tel", "compte", "siret", "ape", "tva", "adresse", "code_postal", "ville", "pays", "actif", "suspendu_motif")
CHAMPS_EVENEMENT = ("nom", "date_iso", "salle_id", "conf", "quota", "prix", "type", "description", "accroche", "tags", "portes", "debut", "fin", "age", "responsable", "projet_ref", "achat", "frais_sans_compte", "pause")
CHAMPS_TYPE = ("evenement_id", "nom", "description", "prix", "quota", "entrees", "visible", "ouverture", "fermeture", "canaux", "rang")
CHAMPS_PASSAGE = ("evenement_id", "artiste_id", "ordre", "duree", "formule_id")
CHAMPS_AFFECTATION = ("evenement_id", "revendeur_id", "formule_id", "quota")
CHAMPS_INVITATION = ("evenement_id", "categorie", "quota")


def construire(db):
    """Rend {nom: Entite}. Les règles de chacune sont dans CN_regles.py ; ce fichier ne fait que les assembler."""
    E = {}
    E["salle"] = crud.Entite(db, "salle", "salles", "salle", "la salle", CHAMPS_SALLE, r.preparer_salle, dependances=r.dependances_salle)
    E["formule"] = crud.Entite(db, "formule", "formules", "formule", "la formule", CHAMPS_FORMULE, r.preparer_formule, dependances=r.dependances_formule,
                               avant_maj=lambda tx, avant, vals: ventes.figer_formule(tx, avant["id"]))
    E["artiste"] = crud.Entite(db, "artiste", "artistes", "artiste", "l'artiste", CHAMPS_ARTISTE, r.preparer_artiste, dependances=r.dependances_artiste,
                               apres=r.apres_artiste, defaire_apres=r.defaire_apres_artiste, champ_libelle="scene")
    E["revendeur"] = crud.Entite(db, "revendeur", "revendeurs", "revendeur", "le revendeur", CHAMPS_REVENDEUR, r.preparer_revendeur, dependances=r.dependances_revendeur,
                                 tombes=(("code", "code"),))
    E["evenement"] = crud.Entite(db, "evenement", "evenements", "evenement", "l'événement", CHAMPS_EVENEMENT, r.preparer_evenement, dependances=r.dependances_evenement)
    E["type_billet"] = crud.Entite(db, "type_billet", "types_billets", "type", "le type de billet", CHAMPS_TYPE, r.preparer_type, dependances=r.dependances_type)
    E["passage"] = crud.Entite(db, "passage", "passages", "passage", "le passage", CHAMPS_PASSAGE, r.preparer_passage, champ_libelle="id")
    E["affectation"] = crud.Entite(db, "affectation", "affectations", "affectation", "l'affectation", CHAMPS_AFFECTATION, r.preparer_affectation, champ_libelle="id")
    E["invitation"] = crud.Entite(db, "invitation", "invitations", "invitation", "la catégorie d'invités", CHAMPS_INVITATION, r.preparer_invitation, champ_libelle="categorie")
    for e in E.values():
        e.sauver = r.integrite(e.sauver)
    return E
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : construire
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
