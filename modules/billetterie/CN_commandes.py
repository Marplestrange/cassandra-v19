# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #8e4f34
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : les capacités des ventes (commandes, billets, codes promo, invitations) offertes au titulaire, aux agents et, plus tard, à la caisse.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8e4f34 ▼▼▼
"""Billetterie : les capacités des ventes (commandes, billets, codes promo, invitations) offertes au titulaire, aux agents et, plus tard, à la caisse.

Chaque écriture se prouve et se défait. Les règles sont dans CN_ventes.py ; ici on enchaîne : ouvrir UNE transaction, appeler la règle, rendre de quoi relire et défaire.
La boutique publique (lot suivant) appelle les MÊMES règles : une vente par la boutique et une vente à la main obéissent aux mêmes contrôles.
"""
from __future__ import annotations

from . import CN_billets as bil
from . import CN_crud as crud
from . import CN_identifiants as ids
from . import CN_regles as r
from . import CN_ventes as v

CHAMPS_PROMO = ("code", "type", "valeur", "evenement_id", "max_usages", "fin", "actif")


# ── les codes promo ──────────────────────────────────────────────────────────
def preparer_promo(tx, d, avant):
    g = lambda k, df=None: r.pris(d, avant, k, df)
    code = "".join(c for c in str(g("code", "")).upper() if c.isalnum() or c in "_-")[:24]
    if not code:
        raise ValueError("le code est obligatoire (lettres, chiffres, tiret)")
    if avant and "code" in d and d["code"] is not None and code != avant["code"]:
        raise ValueError("le code d'une promotion ne change pas : créez-en une autre")
    if avant is None:
        if tx.execute("SELECT 1 FROM promos WHERE code = ?", (code,)).fetchone() or tx.execute("SELECT 1 FROM retires WHERE type = 'code_promo' AND ref = ?", (code,)).fetchone():
            raise ValueError("le code %s existe déjà ou a déjà servi : un code n'est jamais réutilisé" % code)
    t = g("type", "pct")
    if t not in ("pct", "eur"):
        raise ValueError("type : pct (pourcentage) ou eur (euros par billet, en centimes)")
    val = r.entier(g("valeur", 0), "valeur", 1, 100 if t == "pct" else 10 ** 6)
    eid = g("evenement_id")
    if eid and not r.ligne(tx, "evenements", eid):
        raise ValueError("événement introuvable")
    vals = {"type": t, "valeur": val, "evenement_id": int(eid) if eid else None, "max_usages": r.entier(g("max_usages", 0), "utilisations maximales"),
            "fin": r.jour(g("fin", ""), "date de fin"), "actif": r.booleen(g("actif", 1))}
    if avant is None:
        vals["code"] = code
    return vals


def dependances_promo(tx, p):
    n = tx.execute("SELECT COUNT(*) FROM commandes WHERE promo_code = ?", (p["code"],)).fetchone()[0]
    return ["servie dans %d commande(s) : désactivez-la plutôt" % n] if n else []


def brancher(ctx, db):
    promo = crud.Entite(db, "promo", "promos", "promo", "le code promo", CHAMPS_PROMO, preparer_promo, dependances=dependances_promo, champ_libelle="code", tombes=(("code_promo", "code"),))
    promo.sauver = r.integrite(promo.sauver)
    promo.brancher(ctx)

    def evt(tx, eid):
        e = r.ligne(tx, "evenements", eid)
        if not e:
            raise ValueError("événement introuvable")
        return e

    def commande_de(tx, ref):
        c = tx.execute("SELECT * FROM commandes WHERE ref = ?", (str(ref).strip().upper(),)).fetchone()
        if not c:
            raise ValueError("commande introuvable")
        return dict(c)

    # ── lectures ─────────────────────────────────────────────────────────────
    def stock(c, evenement_id=0):
        with db.transaction() as tx:
            return v.stock(tx, evt(tx, evenement_id))

    def panier_devis(c, evenement_id=0, lignes=None, canal="titulaire", code_promo="", don=0, sans_compte=False):
        with db.transaction() as tx:
            return v.devis(ctx, tx, evt(tx, evenement_id), lignes, canal=canal, code_promo=code_promo, don=don, sans_compte=sans_compte)

    def commandes(c, evenement_id=0, etat="", q="", limite=200):
        sql, p = "SELECT * FROM commandes WHERE 1 = 1", []
        if evenement_id:
            sql, p = sql + " AND evenement_id = ?", p + [int(evenement_id)]
        if etat:
            sql, p = sql + " AND etat = ?", p + [etat]
        if q:
            sql, p = sql + " AND (ref LIKE ? OR nom LIKE ? OR mail LIKE ?)", p + ["%" + str(q) + "%"] * 3
        return {"commandes": db.lire(sql + " ORDER BY id DESC LIMIT ?", tuple(p) + (max(1, min(int(limite or 200), 1000)),))}

    def commande(c, ref=""):
        with db.transaction() as tx:
            x = commande_de(tx, ref)
            return {"commande": x, "lignes": [dict(l) for l in tx.execute("SELECT * FROM lignes_commande WHERE commande_id = ? ORDER BY id", (x["id"],)).fetchall()],
                    "billets": [dict(b) for b in tx.execute("SELECT * FROM billets WHERE commande_id = ? ORDER BY id", (x["id"],)).fetchall()]}

    def billets(c, evenement_id=0, q="", etat="", limite=200):
        sql, p = "SELECT * FROM billets WHERE 1 = 1", []
        if evenement_id:
            sql, p = sql + " AND evenement_id = ?", p + [int(evenement_id)]
        if etat:
            sql, p = sql + " AND etat = ?", p + [etat]
        if q:
            sql, p = sql + " AND (numero LIKE ? OR nom LIKE ? OR mail LIKE ?)", p + ["%" + str(q) + "%"] * 3
        return {"billets": db.lire(sql + " ORDER BY id DESC LIMIT ?", tuple(p) + (max(1, min(int(limite or 200), 2000)),))}

    def billet(c, numero=""):
        k = bil.cle(ctx, db)
        x = db.lire("SELECT * FROM billets WHERE numero = ?", (str(numero).strip().upper(),))
        if not x:
            raise ValueError("billet introuvable")
        b = x[0]
        return {"billet": b, "code_controle": bil.code_controle(k, b["numero"], b["version"]), "qr": bil.contenu_qr(k, b["numero"], b["version"])}

    # ── créer une commande (à la main, à la caisse, par un agent) ────────────
    def creer(c, evenement_id=0, lignes=None, canal="titulaire", nom="", mail="", revendeur_code="", code_promo="", don=0, moyen="", encaisser=False):
        if canal not in ("titulaire", "caisse", "revendeur"):
            raise ValueError("canal : titulaire, caisse ou revendeur (la boutique a sa propre porte)")
        if encaisser and moyen not in v.MOYENS_IMMEDIATS:
            raise ValueError("on n'encaisse sur le champ qu'un moyen immédiat : %s" % ", ".join(v.MOYENS_IMMEDIATS))
        with db.transaction() as tx:
            e = evt(tx, evenement_id)
            cid, d = v.creer_commande(ctx, tx, e, lignes, canal=canal, nom=nom, mail=mail, revendeur_code=revendeur_code, code_promo=code_promo, don=don, moyen=moyen if moyen == "virement" else "", par=ctx.compte)
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (cid,)).fetchone())
            res = {"id": cid, "ref": cmd["ref"], "total": d["total"], "places": d["places"], "attribution": cmd["attribution"], "etat": cmd["etat"], "numeros": [], "encaisse": False}
            if encaisser:
                pay = v.encaisser(ctx, tx, cmd, moyen, par=ctx.compte)
                res.update(etat="payee", numeros=pay["numeros"], encaisse=True)
        return res

    def prouver_creer(c, res):
        x = db.lire("SELECT etat FROM commandes WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] in (("payee",) if res["encaisse"] else ("retenue", "en_attente"))

    def defaire_creer(c, res):
        with db.transaction() as tx:
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (res["id"],)).fetchone())
            if cmd["etat"] == "payee":
                v.rembourser(ctx, tx, cmd, "créée puis annulée")
                tx.execute("UPDATE commandes SET etat = 'annulee' WHERE id = ?", (cmd["id"],))
            elif cmd["etat"] in v.RETENANT:
                tx.execute("UPDATE commandes SET etat = 'annulee' WHERE id = ?", (cmd["id"],))

    # ── encaisser, rembourser, annuler ───────────────────────────────────────
    def encaisser(c, ref="", moyen="", reference_externe=""):
        if moyen not in v.MOYENS_IMMEDIATS + v.MOYENS_PRESTATAIRE + ("virement",):
            raise ValueError("moyen de paiement inconnu")
        with db.transaction() as tx:
            cmd = commande_de(tx, ref)
            pay = v.encaisser(ctx, tx, cmd, moyen, reference_externe, ctx.compte)
        return {"id": cmd["id"], "ref": cmd["ref"], "numeros": pay["numeros"], "deja": pay["deja"], "avant": cmd["etat"]}

    def prouver_encaisser(c, res):
        x = db.lire("SELECT etat FROM commandes WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "payee"

    def defaire_encaisser(c, res):
        if res.get("deja"):
            return
        with db.transaction() as tx:
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (res["id"],)).fetchone())
            if cmd["etat"] == "payee":
                v.rembourser(ctx, tx, cmd, "encaissement annulé")
                tx.execute("UPDATE commandes SET etat = ?, reference_externe = NULL, payee_le = '' WHERE id = ?", (res["avant"] if res["avant"] in v.RETENANT else "retenue", cmd["id"]))

    def rembourser(c, ref="", motif=""):
        with db.transaction() as tx:
            cmd = commande_de(tx, ref)
            out = v.rembourser(ctx, tx, cmd, motif)
        return dict(out, id=cmd["id"], ref=cmd["ref"])

    def prouver_rembourser(c, res):
        x = db.lire("SELECT etat FROM commandes WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "remboursee"

    def defaire_rembourser(c, res):
        with db.transaction() as tx:
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (res["id"],)).fetchone())
            if cmd["etat"] != "remboursee":
                return
            e = tx.execute("SELECT statut FROM evenements WHERE id = ?", (cmd["evenement_id"],)).fetchone()
            if e["statut"] != "en vente":
                raise ValueError("l'événement n'est plus en vente : on ne rouvre pas cette commande")
            s = v.stock(tx, r.ligne(tx, "evenements", cmd["evenement_id"]))
            qte = tx.execute("SELECT COUNT(*) FROM billets WHERE commande_id = ?", (cmd["id"],)).fetchone()[0]
            if qte > s["restant"]:
                raise ValueError("les places ont été revendues : on ne peut plus rouvrir cette commande")
            v.rejouer(ctx, tx, cmd)

    def annuler(c, ref=""):
        with db.transaction() as tx:
            cmd = commande_de(tx, ref)
            if cmd["etat"] not in v.RETENANT:
                raise ValueError("seule une commande en cours s'annule (état : %s) ; une commande payée se rembourse" % cmd["etat"])
            tx.execute("UPDATE commandes SET etat = 'annulee' WHERE id = ?", (cmd["id"],))
        return {"id": cmd["id"], "ref": cmd["ref"], "avant": cmd["etat"], "expire_le": cmd["expire_le"]}

    def prouver_annuler(c, res):
        x = db.lire("SELECT etat FROM commandes WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "annulee"

    def defaire_annuler(c, res):
        with db.transaction() as tx:
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (res["id"],)).fetchone())
            if cmd["etat"] != "annulee":
                return
            e = r.ligne(tx, "evenements", cmd["evenement_id"])
            qte = tx.execute("SELECT COALESCE(SUM(quantite),0) FROM lignes_commande WHERE commande_id = ?", (cmd["id"],)).fetchone()[0]
            if qte > v.stock(tx, e)["restant"]:
                raise ValueError("les places ont été reprises : on ne rouvre pas cette commande")
            tx.execute("UPDATE commandes SET etat = ? WHERE id = ?", (res["avant"], cmd["id"]))

    # ── les billets : réémettre, transférer, inviter ─────────────────────────
    def reemettre(c, numero=""):
        with db.transaction() as tx:
            b = tx.execute("SELECT * FROM billets WHERE numero = ?", (str(numero).strip().upper(),)).fetchone()
            if not b:
                raise ValueError("billet introuvable")
            if b["etat"] != "valide":
                raise ValueError("un billet annulé ne se réémet pas")
            tx.execute("UPDATE billets SET version = version + 1 WHERE id = ?", (b["id"],))
        return {"id": b["id"], "numero": b["numero"], "version": b["version"] + 1}

    def prouver_reemettre(c, res):
        x = db.lire("SELECT version FROM billets WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["version"] == res["version"]

    def defaire_reemettre(c, res):
        db.ecrire("UPDATE billets SET version = ? WHERE id = ? AND version = ?", (res["version"] - 1, res["id"], res["version"]))

    def transferer(c, numero="", nom="", mail=""):
        mail = r.mail_valide(mail)
        nom = r.requis(nom, "le nom du nouveau porteur")
        with db.transaction() as tx:
            b = tx.execute("SELECT * FROM billets WHERE numero = ?", (str(numero).strip().upper(),)).fetchone()
            if not b or b["etat"] != "valide":
                raise ValueError("billet introuvable ou annulé")
            tx.execute("UPDATE billets SET nom = ?, mail = ? WHERE id = ?", (nom, mail, b["id"]))
        return {"id": b["id"], "numero": b["numero"], "avant": {"nom": b["nom"], "mail": b["mail"]}, "apres": {"nom": nom, "mail": mail}}

    def prouver_transferer(c, res):
        x = db.lire("SELECT nom, mail FROM billets WHERE id = ?", (res["id"],))
        return bool(x) and x[0] == res["apres"]

    def defaire_transferer(c, res):
        db.ecrire("UPDATE billets SET nom = ?, mail = ? WHERE id = ?", (res["avant"]["nom"], res["avant"]["mail"], res["id"]))

    def inviter(c, evenement_id=0, categorie="", nom="", mail=""):
        with db.transaction() as tx:
            e = evt(tx, evenement_id)
            inv = tx.execute("SELECT * FROM invitations WHERE evenement_id = ? AND categorie = ?", (e["id"], str(categorie).strip())).fetchone()
            if not inv:
                raise ValueError("cette catégorie d'invités n'existe pas pour cet événement")
            if inv["emises"] >= inv["quota"]:
                raise ValueError("le quota d'invitations « %s » est atteint (%d)" % (inv["categorie"], inv["quota"]))
            numero = v.creer_billet(ctx, tx, e, categorie=inv["categorie"], nom=nom, mail=mail)
            tx.execute("UPDATE invitations SET emises = emises + 1 WHERE id = ?", (inv["id"],))
        return {"numero": numero, "invitation_id": inv["id"], "evenement_id": e["id"]}

    def prouver_inviter(c, res):
        return bool(db.lire("SELECT 1 FROM billets WHERE numero = ? AND etat = 'valide'", (res["numero"],)))

    def defaire_inviter(c, res):
        with db.transaction() as tx:
            n = tx.execute("UPDATE billets SET etat = 'annule' WHERE numero = ? AND etat = 'valide'", (res["numero"],)).rowcount
            if n:
                tx.execute("UPDATE invitations SET emises = MAX(0, emises - 1) WHERE id = ?", (res["invitation_id"],))

    for cid, f in (("stock", stock), ("panier_devis", panier_devis), ("commandes", commandes), ("commande", commande), ("billets", billets), ("billet", billet)):
        ctx.implementer(cid, f)
    ctx.implementer("commande_creer", creer, prouver_creer, defaire_creer, simuler=lambda x, evenement_id=0, **_: "créerait une commande pour l'événement %s" % evenement_id)
    ctx.implementer("commande_encaisser", encaisser, prouver_encaisser, defaire_encaisser, simuler=lambda x, ref="", **_: "encaisserait la commande %s" % ref)
    ctx.implementer("commande_rembourser", rembourser, prouver_rembourser, defaire_rembourser, simuler=lambda x, ref="", **_: "rembourserait la commande %s" % ref)
    ctx.implementer("commande_annuler", annuler, prouver_annuler, defaire_annuler, simuler=lambda x, ref="", **_: "annulerait la commande %s" % ref)
    ctx.implementer("billet_reemettre", reemettre, prouver_reemettre, defaire_reemettre, simuler=lambda x, numero="", **_: "réémettrait le billet %s (l'ancien QR ne passerait plus)" % numero)
    ctx.implementer("billet_transferer", transferer, prouver_transferer, defaire_transferer, simuler=lambda x, numero="", **_: "transférerait le billet %s" % numero)
    ctx.implementer("invitation_emettre", inviter, prouver_inviter, defaire_inviter, simuler=lambda x, categorie="", **_: "émettrait une invitation « %s »" % categorie)

    def expirer(c):
        with db.transaction() as tx:
            return {"expirees": v.expirer(tx)}
    ctx.moteur("expirer", expirer)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : preparer_promo, dependances_promo, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
