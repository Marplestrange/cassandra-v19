# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #c671f0
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : la caisse (vente sur place, espèces et carte, session, clôture, vente sans réseau avec une réserve de numéros).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=c671f0 ▼▼▼
"""Billetterie : la caisse (vente sur place, espèces et carte, session, clôture, vente sans réseau avec une réserve de numéros).

Décisions tenues ici :
  - une vente en caisse s'encaisse sur le champ (espèces, terminal de carte, carte déclarée) et ne rapporte aucune commission : c'est une vente directe ;
  - les espèces se comptent : à la clôture, l'écart entre l'attendu (fond + espèces encaissées - espèces rendues par un remboursement) et le comptage est consigné, jamais effacé ;
  - sans réseau, la caisse vend avec des numéros réservés ; un numéro réservé n'est jamais réattribué ; une vente faite hors ligne est acceptée même si les places sont reparties
    entre-temps (l'argent est déjà pris) : elle est signalée comme sur-vente ;
  - une clôture est numérotée (Z-000001), continue, et ne se modifie pas.
"""
from __future__ import annotations

from . import CN_billets as bil
from . import CN_identifiants as ids
from . import CN_regles as r
from . import CN_ventes as v

MOYENS_CAISSE = ("especes", "carte_terminal", "carte_declaree")


def brancher(ctx, db):
    def caisse_de(tx, cid, ouverte=False):
        x = r.ligne(tx, "caisses", cid)
        if not x:
            raise ValueError("caisse introuvable")
        if ouverte and x["etat"] != "ouverte":
            raise ValueError("cette caisse est clôturée (%s)" % x["z"])
        return x

    def totaux(tx, cais):
        """Ce que la session a encaissé, par moyen, et ce qu'elle doit avoir en espèces dans son tiroir."""
        lignes = [dict(x) for x in tx.execute("SELECT moyen, etat, total, rendu FROM commandes WHERE caisse_id = ?", (cais["id"],)).fetchall()]
        pay = [x for x in lignes if x["etat"] == "payee"]
        par = {m: sum(x["total"] for x in pay if x["moyen"] == m) for m in MOYENS_CAISSE}
        remb = sum(x["total"] for x in lignes if x["etat"] == "remboursee" and x["moyen"] == "especes")
        nb = tx.execute("SELECT COUNT(*) FROM billets b JOIN commandes c ON c.id = b.commande_id WHERE c.caisse_id = ? AND b.etat = 'valide'", (cais["id"],)).fetchone()[0]
        return {"total": sum(par.values()), "billets": nb, "par_moyen": par, "remboursees": sum(1 for x in lignes if x["etat"] == "remboursee"), "especes_rendues_par_remboursement": remb,
                "attendu_especes": cais["fond"] + par["especes"], "a_rapprocher": par["carte_declaree"],
                "hors_ligne": tx.execute("SELECT COUNT(*) FROM commandes WHERE caisse_id = ? AND hors_ligne = 1", (cais["id"],)).fetchone()[0]}

    # ── lectures ─────────────────────────────────────────────────────────────
    def caisses(c, evenement_id=0, etat=""):
        sql, p = "SELECT * FROM caisses WHERE 1 = 1", []
        if evenement_id:
            sql, p = sql + " AND evenement_id = ?", p + [int(evenement_id)]
        if etat:
            sql, p = sql + " AND etat = ?", p + [etat]
        return {"caisses": db.lire(sql + " ORDER BY id DESC LIMIT 200", tuple(p))}

    def etat(c, caisse_id=0):
        with db.transaction() as tx:
            cais = caisse_de(tx, caisse_id)
            libres = tx.execute("SELECT COUNT(*) FROM reserves WHERE caisse_id = ? AND etat = 'libre'", (cais["id"],)).fetchone()[0]
            ventes = [dict(x) for x in tx.execute("SELECT ref, moyen, total, recu, rendu, etat, hors_ligne, cree_le FROM commandes WHERE caisse_id = ? ORDER BY id DESC LIMIT 50", (cais["id"],)).fetchall()]
            return {"caisse": cais, "totaux": totaux(tx, cais), "reserve_libre": libres, "ventes": ventes}

    # ── ouvrir ───────────────────────────────────────────────────────────────
    def ouvrir(c, evenement_id=0, caissier="", fond=0, appareil="K1"):
        with db.transaction() as tx:
            e = r.ligne(tx, "evenements", evenement_id)
            if not e:
                raise ValueError("événement introuvable")
            if e["statut"] != "en vente":
                raise ValueError("on n'ouvre pas la caisse d'un événement qui n'est pas en vente (état : %s)" % e["statut"])
            app = r.requis(appareil, "l'appareil", 20)
            if tx.execute("SELECT 1 FROM caisses WHERE evenement_id = ? AND appareil = ? AND etat = 'ouverte'", (e["id"], app)).fetchone():
                raise ValueError("une caisse est déjà ouverte sur l'appareil « %s » pour cet événement" % app)
            ref = ids.nouvelle_ref(tx, "caisse")
            cid = tx.execute("INSERT INTO caisses(ref, evenement_id, caissier, appareil, fond, par) VALUES (?,?,?,?,?,?)",
                             (ref, e["id"], r.texte(caissier or ctx.compte, 80), app, r.entier(fond, "fond de caisse"), ctx.compte)).lastrowid
        return {"id": cid, "ref": ref}

    def prouver_ouvrir(c, res):
        return bool(db.lire("SELECT 1 FROM caisses WHERE id = ? AND etat = 'ouverte'", (res["id"],)))

    def defaire_ouvrir(c, res):
        with db.transaction() as tx:
            if tx.execute("SELECT 1 FROM commandes WHERE caisse_id = ?", (res["id"],)).fetchone():
                raise ValueError("cette caisse a déjà vendu : on la clôture, on ne l'annule pas")
            tx.execute("UPDATE reserves SET etat = 'retire' WHERE caisse_id = ? AND etat = 'libre'", (res["id"],))
            tx.execute("DELETE FROM caisses WHERE id = ?", (res["id"],))
            ids.retirer(tx, "caisse", res["ref"], "", "ouverte puis annulée")

    # ── la réserve de numéros (pour vendre sans réseau) ──────────────────────
    def reserver(c, caisse_id=0):
        """Réserve un bloc de numéros de billets, déjà signés : la caisse pourra vendre sans réseau et imprimer le QR de chacun. Le bloc fait `reserve_caisse` numéros."""
        k = bil.cle(ctx, db)
        taille = int(ctx.reglage("reserve_caisse"))
        with db.transaction() as tx:
            cais = caisse_de(tx, caisse_id, ouverte=True)
            evt = r.ligne(tx, "evenements", cais["evenement_id"])
            nums = []
            for _ in range(taille):
                numero = "%s-%04d" % (bil.lettre_evenement(evt["id"]), ids.suivant(tx, "billet:%d" % evt["id"]))
                tx.execute("INSERT INTO reserves(caisse_id, numero) VALUES (?,?)", (cais["id"], numero))
                nums.append({"numero": numero, "qr": bil.contenu_qr(k, numero, 0), "code_controle": bil.code_controle(k, numero, 0)})
        return {"caisse_id": cais["id"], "numeros": nums}

    def prouver_reserver(c, res):
        return bool(db.lire("SELECT 1 FROM reserves WHERE numero = ?", (res["numeros"][0]["numero"],))) if res["numeros"] else True

    def defaire_reserver(c, res):
        with db.transaction() as tx:
            for n in res["numeros"]:
                tx.execute("UPDATE reserves SET etat = 'retire' WHERE numero = ? AND etat = 'libre'", (n["numero"],))

    # ── vendre ───────────────────────────────────────────────────────────────
    def vendre(c, caisse_id=0, lignes=None, moyen="especes", recu=0, nom="", mail="", code_promo="", numeros=None, hors_ligne=False, heure_appareil=""):
        if moyen not in MOYENS_CAISSE:
            raise ValueError("moyen : %s" % ", ".join(MOYENS_CAISSE))
        numeros = [str(n).strip().upper() for n in (numeros or [])]
        with db.transaction() as tx:
            cais = caisse_de(tx, caisse_id, ouverte=True)
            e = r.ligne(tx, "evenements", cais["evenement_id"])
            cid, d = v.creer_commande(ctx, tx, e, lignes, canal="caisse", nom=nom, mail=mail, code_promo=code_promo, par=ctx.compte, forcer=bool(hors_ligne))
            recu = r.entier(recu or 0, "montant reçu")
            if moyen == "especes" and recu < d["total"]:
                raise ValueError("le montant reçu (%d) est inférieur au total (%d)" % (recu, d["total"]))
            rendu = (recu - d["total"]) if moyen == "especes" else 0
            tx.execute("UPDATE commandes SET caisse_id = ?, recu = ?, rendu = ?, hors_ligne = ? WHERE id = ?", (cais["id"], recu if moyen == "especes" else 0, rendu, 1 if hors_ligne else 0, cid))
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (cid,)).fetchone())
            if numeros:
                if len(numeros) != d["places"]:
                    raise ValueError("%d numéro(s) réservé(s) donné(s) pour %d billet(s)" % (len(numeros), d["places"]))
                for n in numeros:
                    x = tx.execute("SELECT * FROM reserves WHERE numero = ? AND caisse_id = ?", (n, cais["id"])).fetchone()
                    if not x or x["etat"] != "libre":
                        raise ValueError("le numéro %s n'est pas un numéro libre de la réserve de cette caisse" % n)
            pay = v.encaisser(ctx, tx, cmd, moyen, par=ctx.compte, numeros=numeros or None)
            if numeros:
                for n in numeros:
                    tx.execute("UPDATE reserves SET etat = 'vendu', commande_id = ? WHERE numero = ?", (cid, n))
            if hors_ligne and v.stock(tx, e)["vendus"] > e["quota"]:
                tx.execute("UPDATE commandes SET note = 'sur-vente : vendue hors ligne alors que les places étaient reparties' WHERE id = ?", (cid,))
        return {"id": cid, "ref": cmd["ref"], "total": d["total"], "recu": recu if moyen == "especes" else 0, "rendu": rendu, "numeros": pay["numeros"], "moyen": moyen, "caisse_id": cais["id"]}

    def prouver_vendre(c, res):
        x = db.lire("SELECT etat FROM commandes WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "payee"

    def defaire_vendre(c, res):
        with db.transaction() as tx:
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (res["id"],)).fetchone())
            if cmd["etat"] == "payee":
                v.rembourser(ctx, tx, cmd, "vente annulée")
                tx.execute("UPDATE commandes SET etat = 'annulee' WHERE id = ?", (cmd["id"],))
                tx.execute("UPDATE reserves SET etat = 'retire' WHERE commande_id = ?", (cmd["id"],))

    # ── clôturer ─────────────────────────────────────────────────────────────
    def cloturer(c, caisse_id=0, compte_especes=0):
        compte = r.entier(compte_especes, "espèces comptées")
        with db.transaction() as tx:
            cais = caisse_de(tx, caisse_id, ouverte=True)
            t = totaux(tx, cais)
            attendu = t["attendu_especes"]          # fond + espèces des ventes encore payées : une vente remboursée est entrée puis ressortie, elle ne compte pas
            z = "Z-%06d" % ids.suivant(tx, "cloture")
            retires = tx.execute("UPDATE reserves SET etat = 'retire' WHERE caisse_id = ? AND etat = 'libre'", (cais["id"],)).rowcount
            tx.execute("UPDATE caisses SET etat = 'fermee', fermee_le = datetime('now'), compte_especes = ?, attendu_especes = ?, ecart = ?, z = ? WHERE id = ?",
                       (compte, attendu, compte - attendu, z, cais["id"]))
        return {"id": cais["id"], "z": z, "attendu": attendu, "compte": compte, "ecart": compte - attendu, "numeros_retires": retires, "totaux": t}

    def prouver_cloturer(c, res):
        return bool(db.lire("SELECT 1 FROM caisses WHERE id = ? AND etat = 'fermee'", (res["id"],)))

    def defaire_cloturer(c, res):
        """Rouvrir la caisse. Le numéro de clôture déjà attribué n'est pas rendu (une série continue ne revient pas en arrière) ; les numéros retirés le restent."""
        with db.transaction() as tx:
            x = r.ligne(tx, "caisses", res["id"])
            if x and x["etat"] == "fermee":
                ids.retirer(tx, "cloture", x["z"], "", "clôture annulée")
                tx.execute("UPDATE caisses SET etat = 'ouverte', fermee_le = '', compte_especes = NULL, attendu_especes = NULL, ecart = NULL, z = NULL WHERE id = ?", (res["id"],))

    ctx.implementer("caisses", caisses)
    ctx.implementer("caisse_etat", etat)
    ctx.implementer("caisse_ouvrir", ouvrir, prouver_ouvrir, defaire_ouvrir, simuler=lambda x, caissier="", **_: "ouvrirait la caisse de %s" % caissier)
    ctx.implementer("caisse_reserver", reserver, prouver_reserver, defaire_reserver, simuler=lambda x, caisse_id=0, **_: "réserverait un bloc de numéros pour la caisse %s" % caisse_id)
    ctx.implementer("caisse_vendre", vendre, prouver_vendre, defaire_vendre, simuler=lambda x, caisse_id=0, **_: "vendrait des billets à la caisse %s" % caisse_id)
    ctx.implementer("caisse_cloturer", cloturer, prouver_cloturer, defaire_cloturer, simuler=lambda x, caisse_id=0, **_: "clôturerait la caisse %s" % caisse_id)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
