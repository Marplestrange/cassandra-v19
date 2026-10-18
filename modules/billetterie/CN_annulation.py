# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #3c4228
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : annuler ou reporter un événement, par une seule procédure.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=3c4228 ▼▼▼
"""Billetterie : annuler ou reporter un événement, par une seule procédure.

Deux gestes, une seule règle : on annonce d'abord les chiffres (`evenement_impact`, qui n'écrit rien), puis on agit.
  - ANNULER : la vente se ferme, les commandes en cours sont abandonnées, chaque commande payée est remboursée (billets annulés, places rendues, commission reprise par une ligne contraire),
    les invitations sont annulées, les acheteurs, artistes et revendeurs sont prévenus. L'argent rendu CHEZ le prestataire (carte) ou à la main (espèces, virement) reste à faire : le retour le liste.
  - REPORTER : la date change, les billets restent valables (le remboursement se fait sur demande), les commissions sont conservées mais ne deviennent retirables qu'après la NOUVELLE date.
Chaque geste se prouve et se défait ; défaire un courriel déjà parti est impossible, et le retour le dit.
"""
from __future__ import annotations

from . import CN_regles as r
from . import CN_registre as reg
from . import CN_ventes as v

STATUTS_OUVERTS = ("brouillon", "en vente", "complet", "reporté")


def _evt(tx, ident):
    e = r.ligne(tx, "evenements", ident)
    if not e:
        raise ValueError("événement introuvable")
    return e


def _euros(c):
    return ("%.2f €" % (c / 100)).replace(".", ",")


def impact(tx, e):
    """Les chiffres annoncés avant de confirmer : rien n'est écrit."""
    payees = [dict(x) for x in tx.execute("SELECT * FROM commandes WHERE evenement_id = ? AND etat = 'payee'", (e["id"],)).fetchall()]
    par_moyen = {}
    for c in payees:
        a = par_moyen.setdefault(c["moyen"] or "inconnu", {"commandes": 0, "montant": 0})
        a["commandes"] += 1
        a["montant"] += c["total"]
    en_cours = tx.execute("SELECT COUNT(*) FROM commandes WHERE evenement_id = ? AND etat IN ('retenue','en_attente')", (e["id"],)).fetchone()[0]
    invites = tx.execute("SELECT COUNT(*) FROM billets WHERE evenement_id = ? AND commande_id IS NULL AND etat = 'valide'", (e["id"],)).fetchone()[0]
    commission = tx.execute("SELECT COALESCE(SUM(montant), 0) FROM mouvements WHERE evenement_id = ? AND porteur = 'revendeur' AND nature IN ('commission','fixe')", (e["id"],)).fetchone()[0]
    artistes = [dict(x) for x in tx.execute("SELECT DISTINCT a.id, a.scene, a.mail FROM passages p JOIN artistes a ON a.id = p.artiste_id WHERE p.evenement_id = ?", (e["id"],)).fetchall()]
    revendeurs = [dict(x) for x in tx.execute("SELECT DISTINCT v.id, v.nom, v.mail FROM affectations f JOIN revendeurs v ON v.id = f.revendeur_id WHERE f.evenement_id = ?", (e["id"],)).fetchall()]
    return {"evenement": {"id": e["id"], "ref": e["ref"], "nom": e["nom"], "date": e["date_iso"], "statut": e["statut"]},
            "commandes_payees": len(payees), "a_rembourser": sum(c["total"] for c in payees), "par_moyen": par_moyen,
            "commandes_en_cours": en_cours, "invitations": invites, "commissions_a_reprendre": commission,
            "artistes": artistes, "revendeurs": revendeurs, "salle": r.ligne(tx, "salles", e["salle_id"])}


def _courriel(tx, a, objet, corps, ref=""):
    if not a or not r.mail_valide(a):
        return None
    return tx.execute("INSERT INTO courriels(a, objet, corps, commande_ref) VALUES (?,?,?,?)", (a, objet, corps, ref)).lastrowid


def brancher(ctx, db):
    org = lambda: ctx.reglage("titulaire_nom") or "L'organisation"

    def lire_impact(c, id=0):
        with db.transaction() as tx:
            return impact(tx, _evt(tx, id))

    # ── annuler ──────────────────────────────────────────────────────────────
    def annuler(c, id=0, motif="", confirme=False):
        if not confirme:
            raise ValueError("confirmez l'annulation (confirme=true) après avoir lu les chiffres de evenement_impact")
        motif = r.requis(motif, "le motif (il est envoyé aux acheteurs)", 300)
        with db.transaction() as tx:
            e = _evt(tx, id)
            if e["statut"] not in STATUTS_OUVERTS:
                raise ValueError("cet événement ne peut plus s'annuler (état : %s)" % e["statut"])
            chiffres = impact(tx, e)
            remboursees, abandonnees, courriels, restes = [], [], [], []
            for cmd in [dict(x) for x in tx.execute("SELECT * FROM commandes WHERE evenement_id = ? AND etat IN ('payee','retenue','en_attente') ORDER BY id", (e["id"],)).fetchall()]:
                if cmd["etat"] == "payee":
                    out = v.rembourser(ctx, tx, cmd, "événement annulé : " + motif)
                    remboursees.append(cmd["id"])
                    if cmd["total"]:
                        restes.append({"commande": cmd["ref"], "montant": cmd["total"], "moyen": cmd["moyen"], "chez_le_prestataire": out["chez_le_prestataire"]})
                    cid = _courriel(tx, cmd["mail"], "Annulation · %s" % e["nom"],
                                    "Bonjour %s,\n\nNous sommes au regret d'annuler « %s » (%s).\nMotif : %s\n\nVotre commande %s (%s) est remboursée%s.\n\n%s"
                                    % (cmd["nom"] or "", e["nom"], e["date_iso"] or "date à venir", motif, cmd["ref"], _euros(cmd["total"]),
                                       "" if not cmd["total"] else (" sur votre moyen de paiement" if out["chez_le_prestataire"] else " : nous reviendrons vers vous pour le versement"), org()), cmd["ref"])
                    if cid:
                        courriels.append(cid)
                else:
                    abandonnees.append({"id": cmd["id"], "etat": cmd["etat"], "expire_le": cmd["expire_le"]})
                    tx.execute("UPDATE commandes SET etat = 'annulee', note = ? WHERE id = ?", ("événement annulé", cmd["id"]))
            invites = [x[0] for x in tx.execute("SELECT id FROM billets WHERE evenement_id = ? AND commande_id IS NULL AND etat = 'valide'", (e["id"],)).fetchall()]
            for bid in invites:
                tx.execute("UPDATE billets SET etat = 'annule' WHERE id = ?", (bid,))
            for a in chiffres["artistes"]:
                cid = _courriel(tx, a["mail"], "Annulation · %s" % e["nom"], "Bonjour %s,\n\n« %s » (%s) est annulé.\nMotif : %s\n\n%s" % (a["scene"], e["nom"], e["date_iso"], motif, org()))
                if cid:
                    courriels.append(cid)
            for rv in chiffres["revendeurs"]:
                cid = _courriel(tx, rv["mail"], "Annulation · %s" % e["nom"],
                                "Bonjour %s,\n\n« %s » (%s) est annulé.\nMotif : %s\nLes ventes que vous avez faites sont remboursées et les commissions correspondantes sont reprises.\n\n%s" % (rv["nom"], e["nom"], e["date_iso"], motif, org()))
                if cid:
                    courriels.append(cid)
            tx.execute("UPDATE evenements SET statut = 'annulé', publie = 0, motif_annulation = ? WHERE id = ?", (motif, e["id"]))
        return {"id": e["id"], "avant": {"statut": e["statut"], "publie": e["publie"], "motif": e["motif_annulation"]}, "remboursees": remboursees, "abandonnees": abandonnees,
                "invitations_annulees": invites, "courriels": courriels, "reste_a_faire": restes, "chiffres": chiffres}

    def prouver_annuler(c, res):
        x = db.lire("SELECT statut FROM evenements WHERE id = ?", (res["id"],))
        vivants = db.lire("SELECT COUNT(*) AS n FROM billets WHERE evenement_id = ? AND etat = 'valide'", (res["id"],))[0]["n"]
        ouvertes = db.lire("SELECT COUNT(*) AS n FROM commandes WHERE evenement_id = ? AND etat IN ('payee','retenue','en_attente')", (res["id"],))[0]["n"]
        return bool(x) and x[0]["statut"] == "annulé" and vivants == 0 and ouvertes == 0

    def defaire_annuler(c, res):
        with db.transaction() as tx:
            for cid in res["remboursees"]:
                cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (cid,)).fetchone())
                if cmd["etat"] == "remboursee":
                    v.rejouer(ctx, tx, cmd)
            for a in res["abandonnees"]:
                tx.execute("UPDATE commandes SET etat = ?, note = '' WHERE id = ? AND etat = 'annulee'", (a["etat"], a["id"]))
            for bid in res["invitations_annulees"]:
                tx.execute("UPDATE billets SET etat = 'valide' WHERE id = ?", (bid,))
            for mid in res["courriels"]:
                tx.execute("DELETE FROM courriels WHERE id = ? AND etat = 'a_envoyer'", (mid,))
            tx.execute("UPDATE evenements SET statut = ?, publie = ?, motif_annulation = ? WHERE id = ?", (res["avant"]["statut"], res["avant"]["publie"], res["avant"]["motif"], res["id"]))

    # ── reporter ─────────────────────────────────────────────────────────────
    def reporter(c, id=0, nouvelle_date="", motif="", confirme=False):
        if not confirme:
            raise ValueError("confirmez le report (confirme=true) après avoir lu les chiffres de evenement_impact")
        motif = r.requis(motif, "le motif (il est envoyé aux acheteurs)", 300)
        nd = r.jour(nouvelle_date, "nouvelle date")
        if not nd:
            raise ValueError("un report demande la nouvelle date")
        with db.transaction() as tx:
            e = _evt(tx, id)
            if e["statut"] not in ("brouillon", "en vente", "complet"):
                raise ValueError("cet événement ne peut pas être reporté (état : %s)" % e["statut"])
            if nd == e["date_iso"]:
                raise ValueError("c'est déjà la date de l'événement")
            if nd < v.aujourdhui():
                raise ValueError("la nouvelle date est déjà passée")
            chiffres = impact(tx, e)
            courriels = []
            for cmd in [dict(x) for x in tx.execute("SELECT * FROM commandes WHERE evenement_id = ? AND etat = 'payee' AND mail <> ''", (e["id"],)).fetchall()]:
                cid = _courriel(tx, cmd["mail"], "Report · %s" % e["nom"],
                                "Bonjour %s,\n\n« %s » est reporté : il aura lieu le %s au lieu du %s.\nMotif : %s\n\nVos billets restent valables à la nouvelle date. Si elle ne vous convient pas, répondez à ce message : votre commande %s sera remboursée.\n\n%s"
                                % (cmd["nom"] or "", e["nom"], nd, e["date_iso"] or "la date prévue", motif, cmd["ref"], org()), cmd["ref"])
                if cid:
                    courriels.append(cid)
            for a in chiffres["artistes"]:
                cid = _courriel(tx, a["mail"], "Report · %s" % e["nom"], "Bonjour %s,\n\n« %s » est reporté au %s (au lieu du %s).\nMotif : %s\n\n%s" % (a["scene"], e["nom"], nd, e["date_iso"], motif, org()))
                if cid:
                    courriels.append(cid)
            for rv in chiffres["revendeurs"]:
                cid = _courriel(tx, rv["mail"], "Report · %s" % e["nom"],
                                "Bonjour %s,\n\n« %s » est reporté au %s (au lieu du %s).\nMotif : %s\nVos ventes et commissions sont conservées ; les commissions ne seront retirables qu'après la nouvelle date.\n\n%s" % (rv["nom"], e["nom"], nd, e["date_iso"], motif, org()))
                if cid:
                    courriels.append(cid)
            plancher = reg.disponible_apres(nd, int(ctx.reglage("retrait_delai_jours")))
            tx.execute("UPDATE evenements SET date_iso = ?, ancienne_date = ?, motif_report = ?, dispo_min = ? WHERE id = ?", (nd, e["date_iso"], motif, plancher, e["id"]))
        return {"id": e["id"], "avant": {k: e[k] for k in ("date_iso", "ancienne_date", "motif_report", "dispo_min")}, "nouvelle_date": nd, "courriels": courriels,
                "billets_a_rembourser_sur_demande": chiffres["commandes_payees"], "salle": chiffres["salle"]}

    def prouver_reporter(c, res):
        x = db.lire("SELECT date_iso FROM evenements WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["date_iso"] == res["nouvelle_date"]

    def defaire_reporter(c, res):
        a = res["avant"]
        with db.transaction() as tx:
            tx.execute("UPDATE evenements SET date_iso = ?, ancienne_date = ?, motif_report = ?, dispo_min = ? WHERE id = ?", (a["date_iso"], a["ancienne_date"], a["motif_report"], a["dispo_min"], res["id"]))
            for mid in res["courriels"]:
                tx.execute("DELETE FROM courriels WHERE id = ? AND etat = 'a_envoyer'", (mid,))

    ctx.implementer("evenement_impact", lire_impact)
    ctx.implementer("evenement_annuler", annuler, prouver_annuler, defaire_annuler, simuler=lambda x, id=0, **_: "annulerait l'événement %s : toutes ses commandes payées seraient remboursées" % id)
    ctx.implementer("evenement_reporter", reporter, prouver_reporter, defaire_reporter, simuler=lambda x, id=0, nouvelle_date="", **_: "reporterait l'événement %s au %s" % (id, nouvelle_date))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _evt, _euros, impact, _courriel, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
