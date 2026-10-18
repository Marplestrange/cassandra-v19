# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #1f8c94
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : le contrôle à l'entrée (l'ouvreur, ses portes, le mode hors ligne et ses conflits).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1f8c94 ▼▼▼
"""Billetterie : le contrôle à l'entrée (l'ouvreur, ses portes, le mode hors ligne et ses conflits).

Ce qui est décidé ici : un billet est-il authentique (signature), de cet événement, valable, déjà utilisé ? À quelle porte, selon la règle hors ligne choisie par le titulaire ?
Trois règles quand le réseau tombe et que deux portes ne se parlent plus :
  portes    une catégorie de billets par porte : un même billet ne peut pas se présenter à deux portes, aucun conflit n'est possible (la règle recommandée) ;
  signaler  toutes les portes acceptent tout : un billet peut entrer deux fois, le conflit est signalé à la synchronisation et le titulaire l'arbitre ;
  secours   pas de contrôle hors ligne : on bascule sur la liste de secours papier.
Chaque présentation est consignée, acceptée ou refusée : le journal des passages ne s'efface pas.
"""
from __future__ import annotations

from . import CN_billets as bil
from . import CN_identifiants as ids
from . import CN_regles as r

REGLES = ("portes", "signaler", "secours")


def _res(niveau, titre, detail="", billet=None):
    return {"niveau": niveau, "titre": titre, "detail": detail, "billet": billet}


def porte_du_billet(tx, b):
    if b["categorie_invite"]:
        x = tx.execute("SELECT porte FROM invitations WHERE evenement_id = ? AND categorie = ?", (b["evenement_id"], b["categorie_invite"])).fetchone()
        return x[0] if x else "Backstage"
    x = tx.execute("SELECT porte FROM types_billets WHERE id = ?", (b["type_billet_id"],)).fetchone()
    return x[0] if x else "Entrée principale"


def decider(tx, k, evt_id, texte, *, manuel=False, porte="", hors_ligne=False, regle="portes"):
    """Rend (resultat, billet ou None, entre) : `entre` dit si une entrée doit être comptée. N'écrit rien."""
    t = str(texte or "").strip()
    if not t:
        return _res("ko", "Aucun code lu", "Scannez un QR code ou saisissez le numéro de contrôle imprimé sous le QR."), None, False
    lu = bil.lire(t)
    if lu["source"] == "nu" and not manuel:
        return _res("warn", "Numéro incomplet", "Saisissez le numéro de contrôle complet imprimé sous le QR code (avec ses 6 caractères de fin), ou cherchez le billet par nom."), None, False
    b = tx.execute("SELECT * FROM billets WHERE numero = ?", (lu["numero"],)).fetchone()
    b = dict(b) if b else None
    if lu["source"] in ("qr", "num"):
        if not b or not bil.authentique(k, b["numero"], b["version"], lu["signature"]):
            if lu["source"] == "qr":
                return _res("ko", "Billet invalide", "Signature incorrecte : QR falsifié, copié ou ancien (billet réémis)."), None, False
            return _res("ko", "Numéro de contrôle incorrect", "Faute de frappe ou billet falsifié : ressaisissez le numéro complet."), None, False
    elif not b:
        return _res("ko", "Billet invalide", "Ce numéro n'existe pas dans la billetterie."), None, False
    if b["evenement_id"] != evt_id:
        e = r.ligne(tx, "evenements", b["evenement_id"])
        return _res("warn", "Autre événement", "Ce billet est pour « %s »." % (e["nom"] if e else "un autre événement"), b), b, False
    if b["etat"] != "valide":
        return _res("ko", "Billet annulé", "Remboursé ou bloqué : ne pas laisser entrer.", b), b, False
    if hors_ligne and regle == "secours":
        return _res("warn", "Contrôle hors ligne désactivé", "Sans réseau, vérifiez avec la liste de secours papier.", b), b, False
    if hors_ligne and regle == "portes":
        voulue = porte_du_billet(tx, b)
        if porte != voulue:
            return _res("warn", "Mauvaise porte", "Hors ligne, ce billet ne s'accepte qu'à « %s » (règle : une catégorie par porte)." % voulue, b), b, False
    if b["entrees_faites"] >= b["entrees"]:
        d = tx.execute("SELECT le, porte, ouvreur FROM controles WHERE billet_id = ? AND niveau = 'ok' AND annule = 0 ORDER BY id DESC LIMIT 1", (b["id"],)).fetchone()
        return _res("ko", "Déjà utilisé", ("Entré à %s · %s · %s" % (d["le"][11:16], d["porte"], d["ouvreur"])) if d else "Toutes les entrées de ce billet ont servi.", b), b, False
    return _res("ok", "Entrée autorisée", "", b), b, True


def _type_nom(tx, b):
    if b["categorie_invite"]:
        return "invitation « %s »" % b["categorie_invite"]
    x = tx.execute("SELECT nom FROM types_billets WHERE id = ?", (b["type_billet_id"],)).fetchone()
    return x[0] if x else ""


def brancher(ctx, db):
    def controler(c, evenement_id=0, texte="", porte="Entrée principale", manuel=False, hors_ligne=False, ouvreur="", heure_appareil=""):
        k = bil.cle(ctx, db)
        regle = ctx.reglage("regle_hors_ligne")
        with db.transaction() as tx:
            if not r.ligne(tx, "evenements", evenement_id):
                raise ValueError("événement introuvable")
            res, b, entre = decider(tx, k, int(evenement_id), texte, manuel=bool(manuel), porte=str(porte), hors_ligne=bool(hors_ligne), regle=regle)
            who = (ouvreur or ctx.compte)[:80]
            if entre:
                tx.execute("UPDATE billets SET entrees_faites = entrees_faites + 1 WHERE id = ?", (b["id"],))
                nb = tx.execute("SELECT entrees_faites FROM billets WHERE id = ?", (b["id"],)).fetchone()[0]
                res["detail"] = "%s · %s%s%s" % (b["nom"] or "—", _type_nom(tx, b), (" · entrée %d sur %d" % (nb, b["entrees"])) if b["entrees"] > 1 else "", " · validé à la main" if manuel else "")
            cid = tx.execute("INSERT INTO controles(evenement_id, billet_id, numero, porte, ouvreur, niveau, titre, detail, manuel, hors_ligne, heure_appareil) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                             (int(evenement_id), b["id"] if b else None, (b["numero"] if b else bil.lire(texte)["numero"])[:40], str(porte)[:40], who, res["niveau"], res["titre"], res["detail"], 1 if manuel else 0,
                              1 if hors_ligne else 0, str(heure_appareil)[:30])).lastrowid
        out = {"controle_id": cid, "niveau": res["niveau"], "titre": res["titre"], "detail": res["detail"], "entre": entre}
        if b:
            out.update(numero=b["numero"], nom=b["nom"], billet_id=b["id"])
        return out

    def prouver_controler(c, res):
        return bool(db.lire("SELECT 1 FROM controles WHERE id = ?", (res["controle_id"],)))

    def defaire_controler(c, res):
        """Annuler cette entrée : l'entrée est rendue au billet (il pourra de nouveau entrer), la ligne du journal reste, marquée annulée."""
        with db.transaction() as tx:
            x = tx.execute("SELECT * FROM controles WHERE id = ?", (res["controle_id"],)).fetchone()
            if x and x["niveau"] == "ok" and not x["annule"]:
                tx.execute("UPDATE billets SET entrees_faites = MAX(0, entrees_faites - 1) WHERE id = ?", (x["billet_id"],))
                tx.execute("UPDATE controles SET annule = 1 WHERE id = ?", (x["id"],))

    def etat(c, evenement_id=0):
        with db.transaction() as tx:
            e = r.ligne(tx, "evenements", evenement_id)
            if not e:
                raise ValueError("événement introuvable")
            s = tx.execute("SELECT COALESCE(SUM(entrees),0) AS att, COALESCE(SUM(entrees_faites),0) AS ent, "
                           "COALESCE(SUM(CASE WHEN categorie_invite <> '' THEN entrees_faites ELSE 0 END),0) AS inv FROM billets WHERE evenement_id = ? AND etat = 'valide'", (e["id"],)).fetchone()
            ref = tx.execute("SELECT COUNT(*) FROM controles WHERE evenement_id = ? AND niveau = 'ko' AND annule = 0", (e["id"],)).fetchone()[0]
            dern = [dict(x) for x in tx.execute("SELECT * FROM controles WHERE evenement_id = ? ORDER BY id DESC LIMIT 30", (e["id"],)).fetchall()]
            cf = tx.execute("SELECT COUNT(*) FROM conflits WHERE evenement_id = ? AND etat = 'a_arbitrer'", (e["id"],)).fetchone()[0]
        return {"entrees": s["ent"], "attendus": s["att"], "restants": s["att"] - s["ent"], "invites_entres": s["inv"], "refuses": ref, "conflits_a_arbitrer": cf,
                "regle_hors_ligne": ctx.reglage("regle_hors_ligne"), "derniers": dern}

    def chercher(c, evenement_id=0, q=""):
        if len(str(q).strip()) < 2:
            return {"billets": []}
        rows = db.lire("SELECT numero, nom, mail, etat, entrees, entrees_faites, type_billet_id, categorie_invite FROM billets WHERE evenement_id = ? AND (nom LIKE ? OR numero LIKE ?) ORDER BY id LIMIT 10",
                       (int(evenement_id), "%" + str(q).strip() + "%", "%" + str(q).strip().upper() + "%"))
        return {"billets": rows}

    def liste(c, evenement_id=0):
        """Le téléchargement avant de passer hors ligne : pour chaque billet valide, ce qu'il faut pour le reconnaître sans réseau, et la règle choisie."""
        k = bil.cle(ctx, db)
        with db.transaction() as tx:
            e = r.ligne(tx, "evenements", evenement_id)
            if not e:
                raise ValueError("événement introuvable")
            out = []
            for b in tx.execute("SELECT * FROM billets WHERE evenement_id = ? AND etat = 'valide' ORDER BY id", (e["id"],)).fetchall():
                b = dict(b)
                out.append({"numero": b["numero"], "signature": bil.signature(k, b["numero"], b["version"]), "nom": b["nom"], "type": _type_nom(tx, b), "porte": porte_du_billet(tx, b),
                            "entrees": b["entrees"], "entrees_faites": b["entrees_faites"]})
        return {"evenement": {"id": e["id"], "nom": e["nom"]}, "regle": ctx.reglage("regle_hors_ligne"), "billets": out}

    def synchroniser(c, evenement_id=0, entrees=None, ouvreur=""):
        """Les entrées prises hors ligne arrivent : chacune est rejouée DANS L'ORDRE de l'heure de son appareil. Un billet déjà entièrement utilisé par une entrée plus ancienne devient un conflit."""
        who = (ouvreur or ctx.compte)[:80]
        lignes = sorted([x for x in (entrees or []) if isinstance(x, dict)], key=lambda x: str(x.get("heure_appareil", "")))
        faites, conflits, refus, appliquees = 0, [], 0, []
        with db.transaction() as tx:
            if not r.ligne(tx, "evenements", evenement_id):
                raise ValueError("événement introuvable")
            for x in lignes:
                numero, porte, h = str(x.get("numero", "")).strip().upper(), str(x.get("porte", ""))[:40], str(x.get("heure_appareil", ""))[:30]
                b = tx.execute("SELECT * FROM billets WHERE numero = ?", (numero,)).fetchone()
                if not b or b["evenement_id"] != int(evenement_id) or b["etat"] != "valide":
                    tx.execute("INSERT INTO controles(evenement_id, numero, porte, ouvreur, niveau, titre, detail, hors_ligne, heure_appareil) VALUES (?,?,?,?,'ko','Entrée hors ligne refusée','billet inconnu ou annulé depuis',1,?)", (int(evenement_id), numero, porte, who, h))
                    refus += 1
                    continue
                if b["entrees_faites"] >= b["entrees"]:
                    d = tx.execute("SELECT porte, heure_appareil, le FROM controles WHERE billet_id = ? AND niveau = 'ok' AND annule = 0 ORDER BY id LIMIT 1", (b["id"],)).fetchone()
                    cid = tx.execute("INSERT INTO conflits(ref, evenement_id, billet_id, numero, porte1, heure1, porte2, heure2) VALUES (?,?,?,?,?,?,?,?)",
                                     (ids.nouvelle_ref(tx, "conflit"), int(evenement_id), b["id"], numero, d["porte"] if d else "", (d["heure_appareil"] or d["le"]) if d else "", porte, h)).lastrowid
                    tx.execute("INSERT INTO controles(evenement_id, billet_id, numero, porte, ouvreur, niveau, titre, detail, hors_ligne, heure_appareil) VALUES (?,?,?,?,?,'warn','Conflit d''entrée','vu à deux portes pendant la coupure',1,?)",
                               (int(evenement_id), b["id"], numero, porte, who, h))
                    conflits.append(cid)
                    continue
                tx.execute("UPDATE billets SET entrees_faites = entrees_faites + 1 WHERE id = ?", (b["id"],))
                kid = tx.execute("INSERT INTO controles(evenement_id, billet_id, numero, porte, ouvreur, niveau, titre, detail, hors_ligne, heure_appareil) VALUES (?,?,?,?,?,'ok','Entrée autorisée','entrée prise hors ligne',1,?)",
                                 (int(evenement_id), b["id"], numero, porte, who, h)).lastrowid
                appliquees.append(kid)
                faites += 1
        return {"appliquees": faites, "conflits": len(conflits), "refusees": refus, "controle_ids": appliquees, "conflit_ids": conflits}

    def prouver_sync(c, res):
        return True

    def defaire_sync(c, res):
        with db.transaction() as tx:
            for cid in res["controle_ids"]:
                x = tx.execute("SELECT * FROM controles WHERE id = ?", (cid,)).fetchone()
                if x and not x["annule"]:
                    tx.execute("UPDATE billets SET entrees_faites = MAX(0, entrees_faites - 1) WHERE id = ?", (x["billet_id"],))
                    tx.execute("UPDATE controles SET annule = 1 WHERE id = ?", (cid,))
            for fid in res["conflit_ids"]:
                tx.execute("DELETE FROM conflits WHERE id = ? AND etat = 'a_arbitrer'", (fid,))

    def conflits(c, evenement_id=0, etat=""):
        sql, p = "SELECT * FROM conflits WHERE 1 = 1", []
        if evenement_id:
            sql, p = sql + " AND evenement_id = ?", p + [int(evenement_id)]
        if etat:
            sql, p = sql + " AND etat = ?", p + [etat]
        return {"conflits": db.lire(sql + " ORDER BY id DESC LIMIT 500", tuple(p))}

    def arbitrer(c, id=0, decision=""):
        if decision not in ("accepter", "bloquer"):
            raise ValueError("décision : accepter (même personne ou erreur) ou bloquer (le billet ne passera plus)")
        with db.transaction() as tx:
            x = r.ligne(tx, "conflits", id)
            if not x:
                raise ValueError("conflit introuvable")
            if x["etat"] != "a_arbitrer":
                raise ValueError("ce conflit est déjà arbitré")
            if decision == "bloquer":
                tx.execute("UPDATE billets SET etat = 'annule' WHERE id = ?", (x["billet_id"],))
            tx.execute("UPDATE conflits SET etat = ?, decide_par = ?, decide_le = datetime('now') WHERE id = ?", ("bloque" if decision == "bloquer" else "accepte", ctx.compte, x["id"]))
        return {"id": x["id"], "billet_id": x["billet_id"], "decision": decision}

    def prouver_arbitrer(c, res):
        x = db.lire("SELECT etat FROM conflits WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] in ("accepte", "bloque")

    def defaire_arbitrer(c, res):
        with db.transaction() as tx:
            if res["decision"] == "bloquer":
                tx.execute("UPDATE billets SET etat = 'valide' WHERE id = ?", (res["billet_id"],))
            tx.execute("UPDATE conflits SET etat = 'a_arbitrer', decide_par = '', decide_le = '' WHERE id = ?", (res["id"],))

    ctx.implementer("controle_etat", etat)
    ctx.implementer("controle_chercher", chercher)
    ctx.implementer("controle_liste", liste)
    ctx.implementer("conflits", conflits)
    ctx.implementer("controler", controler, prouver_controler, defaire_controler, simuler=lambda x, texte="", **_: "présenterait le billet « %s » à l'entrée" % texte)
    ctx.implementer("controle_synchroniser", synchroniser, prouver_sync, defaire_sync, simuler=lambda x, evenement_id=0, **_: "rejouerait les entrées prises hors ligne")
    ctx.implementer("conflit_arbitrer", arbitrer, prouver_arbitrer, defaire_arbitrer, simuler=lambda x, id=0, decision="", **_: "arbitrerait le conflit %s : %s" % (id, decision))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _res, porte_du_billet, decider, _type_nom, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
