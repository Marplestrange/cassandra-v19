# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #9d0660
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : la file de rattrapage de Dolibarr (l'empilement seulement).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9d0660 ▼▼▼
"""Billetterie : la file de rattrapage de Dolibarr (l'empilement seulement).

Une vente, un remboursement, un versement EMPILENT une écriture à faire ; ils ne parlent jamais à Dolibarr. Ce petit fichier ne dépend de rien d'autre pour que la vente puisse l'appeler sans cycle d'importation.
Rien n'est empilé si le pont est coupé : sans Dolibarr, la billetterie ne garde aucune file.
"""
from __future__ import annotations

OBJETS = {"facture": "dolibarr_factures", "avoir": "dolibarr_avoirs", "versement": "dolibarr_commissions", "adherent": "dolibarr_adherents"}


def relie(ctx) -> bool:
    return bool(ctx.reglage("dolibarr_actif") and str(ctx.reglage("dolibarr_url") or "").strip() and ctx.reglage("dolibarr_cle"))


def empiler(ctx, tx, objet: str, cible_id: int) -> bool:
    """Ajoute l'écriture à la file (une seule fois : la clé est unique). Rend vrai si elle a été empilée."""
    if objet not in OBJETS or not relie(ctx) or not ctx.reglage(OBJETS[objet]):
        return False
    return tx.execute("INSERT OR IGNORE INTO dolibarr_file(cle, objet, cible_id) VALUES (?,?,?)", ("%s:%d" % (objet, int(cible_id)), objet, int(cible_id))).rowcount > 0
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : relie, empiler
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
