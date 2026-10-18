# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #db22e1
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : la fiche complète d'un événement, sa mise en vente, son programme, et ce que rapporte une formule.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=db22e1 ▼▼▼
"""Billetterie : la fiche complète d'un événement, sa mise en vente, son programme, et ce que rapporte une formule.

Le calcul de la commission n'est PAS ici : il vit dans le point d'évolution `commission` (points/EC_commission.py), que ce fichier appelle par `ctx.point`.
Ici, on décide (publier ou refuser), on assemble et on lit.
"""
from __future__ import annotations

from . import CN_regles as r

TYPES_PAR_DEFAUT = (("Plein tarif", "Entrée simple", 1), ("Tarif réduit", "Moins de 18 ans, étudiants", 2))      # (nom, description, tiers du prix : 1 = plein, 2 = deux tiers)


def brancher(ctx, db, E):
    # ── la fiche entière ─────────────────────────────────────────────────────
    def fiche(c, id=0):
        with db.transaction() as tx:
            e = r.ligne(tx, "evenements", id)
            if not e:
                raise ValueError("événement introuvable")
            q = lambda sql, p=(): [dict(x) for x in tx.execute(sql, p).fetchall()]
            return {"evenement": e, "salle": r.ligne(tx, "salles", e["salle_id"]), "jauge": r.jauge(tx, e),
                    "types": q("SELECT * FROM types_billets WHERE evenement_id = ? ORDER BY rang, id", (e["id"],)),
                    "programme": q("SELECT p.*, a.scene, a.ref AS artiste_ref FROM passages p JOIN artistes a ON a.id = p.artiste_id WHERE p.evenement_id = ? ORDER BY p.ordre", (e["id"],)),
                    "affectations": q("SELECT f.*, v.nom AS revendeur, v.code, fo.nom AS formule FROM affectations f JOIN revendeurs v ON v.id = f.revendeur_id JOIN formules fo ON fo.id = f.formule_id WHERE f.evenement_id = ? ORDER BY f.id", (e["id"],)),
                    "invitations": q("SELECT * FROM invitations WHERE evenement_id = ? ORDER BY id", (e["id"],))}

    # ── mise en vente ────────────────────────────────────────────────────────
    def publier(c, id=0):
        with db.transaction() as tx:
            e = r.ligne(tx, "evenements", id)
            if not e:
                raise ValueError("événement introuvable")
            if e["statut"] not in ("brouillon",):
                raise ValueError("seul un brouillon se met en vente (état actuel : %s)" % e["statut"])
            manque = [lib for lib, v in (("une date", e["date_iso"]), ("une salle", e["salle_id"]), ("un nombre de places", e["quota"])) if not v]
            if manque:
                raise ValueError("avant de publier, il faut : %s" % ", ".join(manque))
            j = r.jauge(tx, e)
            if j["depasse"]:
                raise ValueError("la jauge de la salle est dépassée : %d places (vente %d + invitations %d) pour %d" % (j["total"], j["quota"], j["invitations"], j["capacite"]))
            crees = []
            if not tx.execute("SELECT 1 FROM types_billets WHERE evenement_id = ?", (e["id"],)).fetchone():
                from . import CN_identifiants as ids
                for rang, (nom, desc, tiers) in enumerate(TYPES_PAR_DEFAUT):
                    prix = e["prix"] if tiers == 1 else round(e["prix"] * 2 / 3)
                    tid = tx.execute("INSERT INTO types_billets(ref, evenement_id, nom, description, prix, rang) VALUES (?,?,?,?,?,?)",
                                     (ids.nouvelle_ref(tx, "type"), e["id"], nom, desc, prix, rang)).lastrowid
                    crees.append(tid)
            tx.execute("UPDATE evenements SET statut = 'en vente', publie = 1 WHERE id = ?", (e["id"],))
        return {"id": e["id"], "avant": {"statut": e["statut"], "publie": e["publie"]}, "types_crees": crees}

    def prouver_publier(c, res):
        x = db.lire("SELECT statut, publie FROM evenements WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["statut"] == "en vente" and x[0]["publie"] == 1

    def defaire_publier(c, res):
        with db.transaction() as tx:
            for tid in res["types_crees"]:
                tx.execute("DELETE FROM types_billets WHERE id = ?", (tid,))
            tx.execute("UPDATE evenements SET statut = ?, publie = ? WHERE id = ?", (res["avant"]["statut"], res["avant"]["publie"], res["id"]))

    def depublier(c, id=0):
        with db.transaction() as tx:
            e = r.ligne(tx, "evenements", id)
            if not e:
                raise ValueError("événement introuvable")
            if e["statut"] not in ("en vente", "complet"):
                raise ValueError("seul un événement en vente se retire de la vente (état actuel : %s)" % e["statut"])
            tx.execute("UPDATE evenements SET statut = 'brouillon', publie = 0 WHERE id = ?", (e["id"],))
        return {"id": e["id"], "avant": {"statut": e["statut"], "publie": e["publie"]}}

    def prouver_depublier(c, res):
        x = db.lire("SELECT statut FROM evenements WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["statut"] == "brouillon"

    def defaire_depublier(c, res):
        db.ecrire("UPDATE evenements SET statut = ?, publie = ? WHERE id = ?", (res["avant"]["statut"], res["avant"]["publie"], res["id"]))

    # ── programme : l'ordre de passage ───────────────────────────────────────
    def ordonner(c, evenement_id=0, passages=None):
        """`passages` : les identifiants des passages dans le nouvel ordre (tous ceux de l'événement, une seule fois chacun)."""
        with db.transaction() as tx:
            avant = [dict(x) for x in tx.execute("SELECT id, ordre FROM passages WHERE evenement_id = ? ORDER BY ordre", (int(evenement_id),)).fetchall()]
            voulu = [int(x) for x in (passages or [])]
            if sorted(voulu) != sorted(a["id"] for a in avant) or not avant:
                raise ValueError("donnez tous les passages de l'événement, une seule fois chacun")
            for i, pid in enumerate(voulu, 1):
                tx.execute("UPDATE passages SET ordre = ? WHERE id = ?", (1000 + i, pid))       # d'abord hors de la plage : l'unicité du rang ne se heurte pas en route
            for i, pid in enumerate(voulu, 1):
                tx.execute("UPDATE passages SET ordre = ? WHERE id = ?", (i, pid))
        return {"evenement_id": int(evenement_id), "avant": avant, "apres": voulu}

    def prouver_ordonner(c, res):
        return [x["id"] for x in db.lire("SELECT id FROM passages WHERE evenement_id = ? ORDER BY ordre", (res["evenement_id"],))] == res["apres"]

    def defaire_ordonner(c, res):
        with db.transaction() as tx:
            for a in res["avant"]:
                tx.execute("UPDATE passages SET ordre = ? WHERE id = ?", (1000 + a["ordre"], a["id"]))
            for a in res["avant"]:
                tx.execute("UPDATE passages SET ordre = ? WHERE id = ?", (a["ordre"], a["id"]))

    # ── ce que rapporte une formule : le calcul est un POINT d'évolution ─────
    def commission(c, formule_id=0, places=0):
        f = db.lire("SELECT role, forfait, com, fixe, palier, palier_n, palier_com FROM formules WHERE id = ?", (int(formule_id),))
        if not f:
            raise ValueError("formule introuvable")
        g = dict(f[0], palier=bool(f[0]["palier"]))
        return ctx.point("commission", {"formule": g, "places": int(places or 0)})["valeur"]

    ctx.implementer("evenement_fiche", fiche)
    ctx.implementer("commission", commission)
    ctx.implementer("evenement_publier", publier, prouver_publier, defaire_publier, simuler=lambda x, id=0, **_: "mettrait l'événement %s en vente" % id)
    ctx.implementer("evenement_depublier", depublier, prouver_depublier, defaire_depublier, simuler=lambda x, id=0, **_: "retirerait l'événement %s de la vente" % id)
    ctx.implementer("programme_ordonner", ordonner, prouver_ordonner, defaire_ordonner, simuler=lambda x, evenement_id=0, **_: "réordonnerait le programme de l'événement %s" % evenement_id)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
