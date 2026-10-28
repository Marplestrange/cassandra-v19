# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #7e2641
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : « Mon espace » du revendeur et de l'artiste.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=7e2641 ▼▼▼
"""Billetterie : « Mon espace » du revendeur et de l'artiste.

Un revendeur ou un artiste a un COMPTE (le champ « compte » de sa fiche, posé par le titulaire). Avec lui il voit ses propres chiffres et rien d'autre :
  - le revendeur : son code, les événements où il est affecté (formule, quota, ce qu'il a vendu), ses ventes, son portefeuille, ses retraits, et il demande un retrait ;
  - l'artiste : son programme (événements, ordre et heure de passage, durée), sa formule, son portefeuille et ses retraits ; s'il vend lui-même, ses ventes aussi.
Le compte vient TOUJOURS de l'acte (jamais d'un paramètre) : on ne peut pas demander la fiche d'un autre, ni forger une date de retrait.
Le nom de l'acheteur est montré à celui qui a vendu ; son courriel ne l'est pas.
"""
from __future__ import annotations

from . import CN_boutique as boutique
from . import CN_regles as r


def brancher(ctx, db, retrait):
    def moi(tx, table):
        if not ctx.compte:
            raise ValueError("aucun compte : connectez-vous")
        x = tx.execute("SELECT * FROM %s WHERE compte = ? AND compte <> ''" % table, (ctx.compte,)).fetchone()
        if not x:
            raise ValueError("aucune fiche %s n'est liée à votre compte : demandez au titulaire de la relier" % ("de revendeur" if table == "revendeurs" else "d'artiste"))
        return dict(x)

    def portefeuille(tx, porteur, pid):
        from . import CN_registre as reg
        s = reg.soldes(tx, porteur, pid)
        return {"disponible": s["disponible"], "en_attente": s["en_attente"], "du": s["du"], "retraits_en_cours": s["retraits_en_cours"], "verse": s["verse"],
                "mouvements": [dict(x) for x in tx.execute("SELECT ref, nature, montant, disponible_le, note, cree_le FROM mouvements WHERE porteur = ? AND porteur_id = ? ORDER BY id DESC LIMIT 50", (porteur, pid)).fetchall()],
                "retraits": [dict(x) for x in tx.execute("SELECT ref, montant, etat, motif, demande_le, traite_le FROM retraits WHERE porteur = ? AND porteur_id = ? ORDER BY id DESC LIMIT 50", (porteur, pid)).fetchall()]}

    def ventes_de(tx, rid, limite=200):
        out = []
        for cmd in tx.execute("SELECT c.*, e.ref AS eref, e.nom AS enom FROM commandes c JOIN evenements e ON e.id = c.evenement_id WHERE c.revendeur_id = ? ORDER BY c.id DESC LIMIT ?", (rid, limite)).fetchall():
            billets = tx.execute("SELECT COUNT(*) FROM billets WHERE commande_id = ? AND etat = 'valide'", (cmd["id"],)).fetchone()[0]
            com = tx.execute("SELECT COALESCE(SUM(montant), 0) FROM mouvements WHERE origine = ? AND porteur = 'revendeur' AND porteur_id = ?", (cmd["ref"], rid)).fetchone()[0]
            out.append({"commande": cmd["ref"], "evenement": cmd["enom"], "evenement_ref": cmd["eref"], "etat": cmd["etat"], "billets": billets, "total": cmd["total"],
                        "acheteur": cmd["nom"], "commission": com, "date": cmd["payee_le"] or ""})
        return out

    # ── le revendeur ─────────────────────────────────────────────────────────
    def mon_revendeur(c):
        with db.transaction() as tx:
            rv = moi(tx, "revendeurs")
            aff = []
            for a in tx.execute("SELECT f.*, e.ref AS eref, e.nom AS enom, e.date_iso, e.statut AS estatut, fo.nom AS formule FROM affectations f JOIN evenements e ON e.id = f.evenement_id "
                                "JOIN formules fo ON fo.id = f.formule_id WHERE f.revendeur_id = ? ORDER BY e.date_iso, f.id", (rv["id"],)).fetchall():
                vendus = tx.execute("SELECT COUNT(*) FROM billets WHERE revendeur_id = ? AND evenement_id = ? AND etat = 'valide'", (rv["id"], a["evenement_id"])).fetchone()[0]
                gagne = tx.execute("SELECT COALESCE(SUM(montant), 0) FROM mouvements WHERE porteur = 'revendeur' AND porteur_id = ? AND evenement_id = ? AND nature IN ('commission','fixe')", (rv["id"], a["evenement_id"])).fetchone()[0]
                aff.append({"evenement": a["enom"], "evenement_ref": a["eref"], "date": a["date_iso"], "etat": a["estatut"], "formule": a["formule"], "quota": a["quota"],
                            "vendus": vendus, "restant": max(0, a["quota"] - vendus) if a["quota"] else None, "commission": gagne})
            out = {"ref": rv["ref"], "nom": rv["nom"], "code": rv["code"], "actif": bool(rv["actif"]), "motif_suspension": rv["suspendu_motif"], "type": rv["type"], "affectations": aff,
                   "portefeuille": portefeuille(tx, "revendeur", rv["id"]), "ventes": ventes_de(tx, rv["id"], 50)}
            out["lien_de_vente"] = "?r=" + rv["code"]
        return out

    def mes_ventes(c, limite=200):
        with db.transaction() as tx:
            rv = moi(tx, "revendeurs")
            return {"ventes": ventes_de(tx, rv["id"], max(1, min(int(limite or 200), 500)))}

    def retrait_revendeur(c, montant=0):
        with db.transaction() as tx:
            rv = moi(tx, "revendeurs")
        return retrait["demander"](c, "revendeur", rv["id"], montant)

    # ── l'artiste ────────────────────────────────────────────────────────────
    def mon_artiste(c):
        with db.transaction() as tx:
            a = moi(tx, "artistes")
            f = r.ligne(tx, "formules", a["formule_id"]) if a["formule_id"] else None
            programme = []
            for e in tx.execute("SELECT DISTINCT e.* FROM passages p JOIN evenements e ON e.id = p.evenement_id WHERE p.artiste_id = ? ORDER BY e.date_iso, e.id", (a["id"],)).fetchall():
                tous = [dict(x) for x in tx.execute("SELECT id, artiste_id, ordre, duree FROM passages WHERE evenement_id = ? ORDER BY ordre", (e["id"],)).fetchall()]
                heures = boutique.horaires(e["debut"], tous, e["pause"])
                for p, h in zip(tous, heures):
                    if p["artiste_id"] == a["id"]:
                        programme.append({"evenement": e["nom"], "evenement_ref": e["ref"], "date": e["date_iso"], "etat": e["statut"], "ordre": p["ordre"], "sur": len(tous),
                                          "heure": h, "duree": p["duree"], "portes": e["portes"]})
            out = {"ref": a["ref"], "scene": a["scene"], "genre": a["genre"], "rider": a["rider"],
                   "formule": ({"nom": f["nom"], "forfait": f["forfait"], "commission": f["com"], "fixe": f["fixe"]} if f else None),
                   "programme": programme, "portefeuille": portefeuille(tx, "artiste", a["id"]), "vend": bool(a["vend"])}
            if a["vend"] and a["revendeur_id"]:
                rv = r.ligne(tx, "revendeurs", a["revendeur_id"])
                out["vente"] = {"code": rv["code"], "lien_de_vente": "?r=" + rv["code"], "ventes": ventes_de(tx, rv["id"], 50), "portefeuille": portefeuille(tx, "revendeur", rv["id"])}
        return out

    def retrait_artiste(c, montant=0):
        with db.transaction() as tx:
            a = moi(tx, "artistes")
        return retrait["demander"](c, "artiste", a["id"], montant)

    ctx.implementer("mon_revendeur", mon_revendeur)
    ctx.implementer("mes_ventes", mes_ventes)
    ctx.implementer("mon_retrait_revendeur", retrait_revendeur, retrait["prouver"], retrait["defaire"], simuler=lambda x, montant=0, **_: "demanderait un retrait de %s centimes" % montant)
    ctx.implementer("mon_artiste", mon_artiste)
    ctx.implementer("mon_retrait_artiste", retrait_artiste, retrait["prouver"], retrait["defaire"], simuler=lambda x, montant=0, **_: "demanderait un retrait de %s centimes" % montant)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
