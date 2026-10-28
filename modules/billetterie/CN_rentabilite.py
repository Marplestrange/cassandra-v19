# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #a6da53
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : la rentabilité d'un événement et la décision avant la soirée.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=a6da53 ▼▼▼
"""Billetterie : la rentabilité d'un événement et la décision avant la soirée.

Ce que le titulaire veut savoir avant de s'engager : combien coûte la soirée (salle, forfaits et cachets des artistes), combien rapportent les places déjà vendues, à partir de combien
de places elle s'équilibre, et — à la date de décision (J-7 par défaut) — si l'on maintient ou si l'on annule ou reporte, avec ce que l'annulation coûterait au plus (l'acompte de la salle).
Cette capacité ne DÉCIDE rien : elle éclaire. Annuler ou reporter reste un geste du titulaire (evenement_annuler, evenement_reporter), toujours précédé de ses chiffres.
Les commissions des revendeurs se lisent dans le registre (ce qui est réellement dû) ; le seuil tient compte de la commission moyenne observée par place vendue.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from . import CN_regles as r
from . import CN_ventes as v


def brancher(ctx, db):
    def calculer(e, salle, artistes, ventes, commissions):
        """Les chiffres. `artistes` : [(nom, montant fixe en centimes)] ; `ventes` : (places vendues, recettes en centimes hors don) ; `commissions` : dû aux revendeurs et artistes (centimes)."""
        vendus, recettes = ventes
        couts_salle = salle["location"] if salle else 0
        couts_artistes = sum(m for _, m in artistes)
        couts_fixes = couts_salle + couts_artistes
        prix = (recettes / vendus) if vendus else e["prix"]
        comm_place = (commissions / vendus) if vendus else 0
        net_place = prix - comm_place
        seuil = math.ceil(couts_fixes / net_place) if net_place > 0 and couts_fixes > 0 else (0 if couts_fixes <= 0 else None)
        seuil_direct = math.ceil(couts_fixes / prix) if prix > 0 and couts_fixes > 0 else 0
        resultat = recettes - couts_fixes - commissions
        return {"vendus": vendus, "recettes": recettes, "couts_salle": couts_salle, "couts_artistes": couts_artistes, "couts_fixes": couts_fixes, "commissions": commissions,
                "prix_moyen": round(prix), "commission_par_place": round(comm_place), "resultat": resultat, "seuil_places": seuil, "seuil_sans_commission": seuil_direct,
                "places_manquantes": (max(0, seuil - vendus) if seuil is not None else None), "capacite_en_vente": e["quota"],
                "seuil_atteignable": (seuil is not None and seuil <= e["quota"])}

    def rentabilite(c, evenement_id=0):
        with db.transaction() as tx:
            e = r.ligne(tx, "evenements", evenement_id)
            if not e:
                raise ValueError("événement introuvable")
            salle = r.ligne(tx, "salles", e["salle_id"]) if e["salle_id"] else None
            artistes, vus = [], set()
            for p in tx.execute("SELECT p.artiste_id, p.formule_id AS fp, a.scene, a.formule_id AS fa FROM passages p JOIN artistes a ON a.id = p.artiste_id WHERE p.evenement_id = ? ORDER BY p.ordre", (e["id"],)).fetchall():
                if p["artiste_id"] in vus:
                    continue                                              # un artiste qui joue deux fois n'est payé qu'une fois
                vus.add(p["artiste_id"])
                f = r.ligne(tx, "formules", p["fp"] or p["fa"]) if (p["fp"] or p["fa"]) else None
                artistes.append((p["scene"], f["forfait"] if f else 0))
            ligne = tx.execute("SELECT COUNT(*) AS n FROM billets b JOIN commandes c ON c.id = b.commande_id WHERE b.evenement_id = ? AND b.etat = 'valide' AND c.etat = 'payee'", (e["id"],)).fetchone()
            rec = tx.execute("SELECT COALESCE(SUM(total - don), 0) FROM commandes WHERE evenement_id = ? AND etat = 'payee'", (e["id"],)).fetchone()[0]
            comm = tx.execute("SELECT COALESCE(SUM(montant), 0) FROM mouvements WHERE evenement_id = ? AND porteur = 'revendeur' AND nature IN ('commission','fixe')", (e["id"],)).fetchone()[0]
            out = calculer(e, salle, artistes, (ligne["n"], rec), comm)
            out["artistes"] = [{"scene": n, "montant": m} for n, m in artistes]
            out["acompte_salle"] = salle["acompte"] if salle else 0
            out["evenement"] = {"id": e["id"], "nom": e["nom"], "date": e["date_iso"], "statut": e["statut"]}
            jours = int(ctx.reglage("decision_jours"))
            decision = ""
            if e["date_iso"]:
                decision = (date.fromisoformat(e["date_iso"]) - timedelta(days=jours)).isoformat()
            aujourdhui = v.aujourdhui()
            out["date_decision"] = decision
            out["decision_due"] = bool(decision) and aujourdhui >= decision and e["statut"] in ("en vente", "complet")
            sous = out["seuil_places"] is None or out["vendus"] < out["seuil_places"]
            out["sous_le_seuil"] = bool(sous and out["couts_fixes"] > 0)
            if e["statut"] in ("annulé", "terminé"):
                out["conseil"] = "Événement clos."
            elif not out["couts_fixes"]:
                out["conseil"] = "Aucun coût renseigné (salle, artistes) : le seuil de rentabilité n'est pas calculable."
            elif not out["decision_due"]:
                out["conseil"] = ("À ce jour, %d place(s) vendue(s) sur %s nécessaires." % (out["vendus"], out["seuil_places"] if out["seuil_places"] is not None else "?")) + (" Décision le %s." % decision if decision else "")
            elif out["sous_le_seuil"]:
                out["conseil"] = "Sous le seuil à la date de décision : annuler ou reporter limite la perte à l'acompte de la salle (%d centimes) ; maintenir risque un résultat de %d centimes." % (out["acompte_salle"], out["resultat"])
            else:
                out["conseil"] = "Au-dessus du seuil à la date de décision : on maintient."
            return out

    ctx.implementer("evenement_rentabilite", rentabilite)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
