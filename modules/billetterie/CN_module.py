# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #043440
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La billetterie : branchement du module.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=043440 ▼▼▼
"""La billetterie : branchement du module.

Un événement, une salle, des artistes et des revendeurs, des formules de rémunération, des billets, une caisse, un contrôle à l'entrée, une boutique publique,
et un portefeuille des commissions tenu en centimes dans un registre en écriture seule. Le titulaire de l'instance est l'organisateur.

Lot 1 (ce fichier) : les bases (salles, artistes, revendeurs), les formules de rémunération (deux groupes qui ne se mélangent pas), les événements et ce qui s'y
rattache (types de billets, programme, affectations des revendeurs, invitations), la mise en vente. Rien n'est jamais supprimé en silence, aucun identifiant
n'est réutilisé, chaque écriture se défait. La suite (registre, ventes, caisse, contrôle, boutique) s'ajoute par migrations, jamais en retouchant celles-ci.
"""
from __future__ import annotations

from . import CN_entites as entites
from . import CN_evenements as evenements


def brancher(ctx):
    db = ctx.stockage
    E = entites.construire(db)
    for e in E.values():
        e.brancher(ctx)
    evenements.brancher(ctx, db, E)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
