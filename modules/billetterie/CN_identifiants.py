# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #cc3b19
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : des identifiants qui ne sont JAMAIS réutilisés.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=cc3b19 ▼▼▼
"""Billetterie : des identifiants qui ne sont JAMAIS réutilisés.

Une référence (EVT-000001) ou un code de vente (LEA-00A3) désigne une chose pour toujours. `sequences` compte, `retires` se souvient : une fiche
supprimée ou une création annulée laisse sa référence au registre des retirés, et personne d'autre ne la reçoit. C'est ce qui permet de la porter
telle quelle dans Dolibarr (champ ref_ext) sans jamais confondre deux fiches.
"""
from __future__ import annotations

import re
import unicodedata

PREFIXES = {"salle": "SAL", "artiste": "ART", "revendeur": "REV", "formule": "FOR", "evenement": "EVT", "type": "TYP",
            "client": "CLI", "commande": "CMD", "billet": "BIL", "promo": "PRO", "retrait": "RET", "mouvement": "MOU",
            "caisse": "CAI", "versement": "VER", "attente": "ATT", "passage": "PAS", "affectation": "AFF", "invitation": "INV"}
_BASE36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def suivant(tx, type_: str) -> int:
    """Le numéro suivant d'une série. À appeler DANS une transaction : le numéro est consommé même si l'opération est annulée ensuite par une défaite."""
    tx.execute("INSERT INTO sequences(type, n) VALUES(?, 1) ON CONFLICT(type) DO UPDATE SET n = n + 1", (type_,))
    return tx.execute("SELECT n FROM sequences WHERE type = ?", (type_,)).fetchone()[0]


def nouvelle_ref(tx, type_: str) -> str:
    if type_ not in PREFIXES:
        raise ValueError("type d'identifiant inconnu : %s" % type_)
    return "%s-%06d" % (PREFIXES[type_], suivant(tx, type_))


def _base36(n: int, largeur: int) -> str:
    s = ""
    while n:
        n, r = divmod(n, 36)
        s = _BASE36[r] + s
    return s.rjust(largeur, "0")


def nouveau_code(tx, nom: str) -> str:
    """Le code de vente d'un revendeur : trois lettres de son nom et quatre caractères de la série (« LEA-0001 »). Unique, jamais réutilisé."""
    plat = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode("ascii")
    lettres = re.sub(r"[^A-Za-z]", "", plat).upper()[:3].ljust(3, "X")
    while True:
        code = "%s-%s" % (lettres, _base36(suivant(tx, "code"), 4))
        pris = tx.execute("SELECT 1 FROM revendeurs WHERE code = ? UNION SELECT 1 FROM retires WHERE type = 'code' AND ref = ?", (code, code)).fetchone()
        if not pris:
            return code


def retirer(tx, type_: str, ref: str, nom: str = "", motif: str = "") -> None:
    """Inscrit une référence au registre des retirés : plus personne ne la recevra."""
    tx.execute("INSERT INTO retires(type, ref, nom, motif) VALUES(?,?,?,?) ON CONFLICT(type, ref) DO UPDATE SET nom=excluded.nom, motif=excluded.motif, le=datetime('now')",
               (type_, ref, str(nom)[:120], str(motif)[:120]))


def restaurer(tx, type_: str, ref: str) -> None:
    """Retire une référence du registre des retirés (seulement quand on REMET la fiche, jamais pour la donner à une autre)."""
    tx.execute("DELETE FROM retires WHERE type = ? AND ref = ?", (type_, ref))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : suivant, nouvelle_ref, _base36, nouveau_code, retirer, restaurer
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
