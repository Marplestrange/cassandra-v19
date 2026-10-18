# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #5f9755
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : la liste d'attente d'un billet épuisé.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=5f9755 ▼▼▼
"""Billetterie : la liste d'attente d'un billet épuisé.

Une personne s'inscrit quand le billet qu'elle veut n'est plus disponible ; dès qu'une place se libère (réservation expirée, remboursement, quota augmenté), la première inscrite
qui peut être servie reçoit une OFFRE : une commande en cours qui retient vraiment ses places pendant `offre_attente_heures`, et un courriel avec le lien pour payer.
Une offre non payée dans les temps expire, et la place passe à la suivante. Tout se rejoue dans l'ordre d'inscription : ni passe-droit, ni hasard.
"""
from __future__ import annotations

import hmac
import secrets

from . import CN_identifiants as ids
from . import CN_regles as r
from . import CN_ventes as v
from .CN_boutique import limiter

LIMITE_INSCRIPTIONS_IP = (10, 3600)
LIMITE_INSCRIPTIONS_MAIL = (5, 3600)


def _type_pour(tx, s, ligne):
    """Le type de billet à proposer pour cette inscription, s'il y a de la place maintenant : le type demandé, ou à défaut le moins cher qui en a assez."""
    q = ligne["quantite"]
    if s["restant"] < q:
        return None
    infos = {t["id"]: r.ligne(tx, "types_billets", t["id"]) for t in s["types"]}
    candidats = [t for t in s["types"] if (not ligne["type_billet_id"] or t["id"] == ligne["type_billet_id"]) and (t["restant"] is None or t["restant"] >= q)]
    for t in sorted(candidats, key=lambda x: (infos[x["id"]]["prix"], x["id"])):
        i = infos[t["id"]]
        if i["visible"] and "boutique" in i["canaux"].split(",") and not (i["ouverture"] and v.aujourdhui() < i["ouverture"]) and not (i["fermeture"] and v.aujourdhui() > i["fermeture"]):
            return t["id"]
    return None


def reconcilier(tx):
    """Les offres faites : payée => convertie ; réservation écoulée ou abandonnée => expirée."""
    n = 0
    for a in [dict(x) for x in tx.execute("SELECT a.id, c.etat AS cetat, c.expire_le AS cexp FROM attente a LEFT JOIN commandes c ON c.id = a.commande_id WHERE a.etat = 'offerte'").fetchall()]:
        if a["cetat"] == "payee":
            nouveau = "convertie"
        elif a["cetat"] in ("retenue", "en_attente") and a["cexp"] > v.horloge():
            continue
        else:
            nouveau = "expiree"
        tx.execute("UPDATE attente SET etat = ? WHERE id = ?", (nouveau, a["id"]))
        n += 1
    return n


def proposer(ctx, tx, evenement_id=None):
    """Fait les offres que le stock permet, dans l'ordre d'inscription. Rend les offres faites."""
    v.expirer(tx)
    reconcilier(tx)
    heures = int(ctx.reglage("offre_attente_heures"))
    offres = []
    sql = "SELECT * FROM evenements WHERE statut IN ('en vente','complet') AND publie = 1"
    if evenement_id:
        sql += " AND id = %d" % int(evenement_id)
    for e in [dict(x) for x in tx.execute(sql).fetchall()]:
        for a in [dict(x) for x in tx.execute("SELECT * FROM attente WHERE evenement_id = ? AND etat = 'attente' ORDER BY id", (e["id"],)).fetchall()]:
            tid = _type_pour(tx, v.stock(tx, e), a)
            if tid is None:
                continue
            try:
                cid, d = v.creer_commande(ctx, tx, e, [{"type_billet_id": tid, "quantite": a["quantite"]}], canal="boutique", nom=a["nom"], mail=a["mail"], sans_compte=True, par="attente")
            except ValueError:
                continue                    # par exemple : l'achat sans compte est interdit pour cet événement
            fin = v.horloge() + heures * 3600
            tx.execute("UPDATE commandes SET expire_le = ? WHERE id = ?", (fin, cid))
            tx.execute("UPDATE attente SET etat = 'offerte', commande_id = ?, offre_jusqua = ? WHERE id = ?", (cid, fin, a["id"]))
            cmd = dict(tx.execute("SELECT * FROM commandes WHERE id = ?", (cid,)).fetchone())
            corps = ("Bonjour %s,\n\nBonne nouvelle : %d place(s) se sont libérées pour « %s » (%s), et nous vous les avons réservées.\n\nVous avez %d heure(s) pour payer (%s) : %s\n"
                     "Passé ce délai, les places seront proposées à la personne suivante.\n\n%s"
                     % (a["nom"], a["quantite"], e["nom"], e["date_iso"] or "date à venir", heures, ("%.2f €" % (d["total"] / 100)).replace(".", ","),
                        v.url(ctx, "/c/%s?s=%s" % (cmd["ref"], cmd["suivi"])), ctx.reglage("titulaire_nom")))
            mid = tx.execute("INSERT INTO courriels(a, objet, corps, commande_ref) VALUES (?,?,?,?)", (a["mail"], "Des places se sont libérées · %s" % e["nom"], corps, cmd["ref"])).lastrowid
            offres.append({"attente": a["id"], "ref": a["ref"], "commande_id": cid, "commande": cmd["ref"], "mail": a["mail"], "courriel_id": mid})
    return offres


def fermer_evenement(tx, evenement_id):
    """L'événement est annulé : plus personne n'attend. Rend l'état d'avant de chaque inscription (pour défaire)."""
    avant = [{"id": x["id"], "etat": x["etat"]} for x in tx.execute("SELECT id, etat FROM attente WHERE evenement_id = ? AND etat IN ('attente','offerte')", (evenement_id,)).fetchall()]
    for a in avant:
        tx.execute("UPDATE attente SET etat = 'retiree' WHERE id = ?", (a["id"],))
    return avant


def brancher(ctx, db, boutique):
    en_ligne, evt_pub = boutique["en_ligne"], boutique["evt_pub"]

    def rang(tx, a):
        return tx.execute("SELECT COUNT(*) FROM attente WHERE evenement_id = ? AND etat = 'attente' AND id <= ?", (a["evenement_id"], a["id"])).fetchone()[0]

    # ── public : s'inscrire, suivre, se retirer ──────────────────────────────
    def inscrire(c, evenement="", type="", quantite=1, nom="", mail="", ip=""):
        en_ligne()
        if not ctx.reglage("liste_attente"):
            raise ValueError("la liste d'attente n'est pas ouverte")
        nom = r.requis(nom, "votre nom")
        mail = r.mail_valide(mail)
        if not mail:
            raise ValueError("votre courriel est obligatoire : c'est là que nous vous préviendrons")
        q = r.entier(quantite, "nombre de places", 1, 20)
        ip = str(ip or "")[:64]
        with db.transaction() as tx:
            e = evt_pub(tx, evenement)
            if e["statut"] not in ("en vente", "complet"):
                raise ValueError("cet événement n'est pas en vente")
            tid = None
            if type:
                t = tx.execute("SELECT id FROM types_billets WHERE ref = ? AND evenement_id = ?", (str(type).strip().upper(), e["id"])).fetchone()
                if not t:
                    raise ValueError("ce billet n'existe pas pour cet événement")
                tid = t[0]
            if ip:
                limiter(tx, "att:ip:" + ip, *LIMITE_INSCRIPTIONS_IP)
            limiter(tx, "att:mail:" + mail.lower(), *LIMITE_INSCRIPTIONS_MAIL)
            if tx.execute("SELECT 1 FROM attente WHERE evenement_id = ? AND lower(mail) = ? AND etat IN ('attente','offerte')", (e["id"], mail.lower())).fetchone():
                raise ValueError("vous êtes déjà sur la liste d'attente de cet événement")
            if _type_pour(tx, v.stock(tx, e), {"quantite": q, "type_billet_id": tid}) is not None:
                raise ValueError("il reste des places : vous pouvez les commander directement")
            jeton = secrets.token_urlsafe(18)
            aid = tx.execute("INSERT INTO attente(ref, evenement_id, type_billet_id, nom, mail, quantite, jeton, ip) VALUES (?,?,?,?,?,?,?,?)",
                             (ids.nouvelle_ref(tx, "attente"), e["id"], tid, r.texte(nom, 120), mail, q, jeton, ip)).lastrowid
            a = dict(tx.execute("SELECT * FROM attente WHERE id = ?", (aid,)).fetchone())
            pos = rang(tx, a)
        return {"attente": a["ref"], "suivi": jeton, "rang": pos}

    def prouver_inscrire(c, res):
        return bool(db.lire("SELECT 1 FROM attente WHERE ref = ?", (res["attente"],)))

    def defaire_inscrire(c, res):
        with db.transaction() as tx:
            tx.execute("UPDATE attente SET etat = 'retiree' WHERE ref = ? AND etat = 'attente'", (res["attente"],))

    def _par_jeton(tx, jeton):
        for a in tx.execute("SELECT * FROM attente WHERE jeton = ?", (str(jeton),)).fetchall():
            if hmac.compare_digest(a["jeton"], str(jeton)):
                return dict(a)
        raise ValueError("inscription introuvable")

    def suivre(c, suivi=""):
        with db.transaction() as tx:
            reconcilier(tx)                       # une offre payée ou écoulée se lit telle qu'elle est maintenant
            a = _par_jeton(tx, suivi)
            e = r.ligne(tx, "evenements", a["evenement_id"])
            out = {"attente": a["ref"], "etat": a["etat"], "evenement": {"ref": e["ref"], "nom": e["nom"], "date": e["date_iso"]}, "places": a["quantite"]}
            if a["etat"] == "attente":
                out["rang"] = rang(tx, a)
            if a["etat"] == "offerte":
                cmd = tx.execute("SELECT ref, suivi FROM commandes WHERE id = ?", (a["commande_id"],)).fetchone()
                out["offre"] = {"commande": cmd["ref"], "suivi": cmd["suivi"], "jusqua": a["offre_jusqua"]}
        return out

    def retirer(c, suivi=""):
        with db.transaction() as tx:
            a = _par_jeton(tx, suivi)
            if a["etat"] not in ("attente", "offerte"):
                raise ValueError("cette inscription n'est plus active")
            if a["etat"] == "offerte":
                tx.execute("UPDATE commandes SET etat = 'annulee', note = 'offre refusée' WHERE id = ? AND etat IN ('retenue','en_attente')", (a["commande_id"],))
            tx.execute("UPDATE attente SET etat = 'retiree' WHERE id = ?", (a["id"],))
            offres = proposer(ctx, tx, a["evenement_id"])
        return {"attente": a["ref"], "avant": a["etat"], "commande_id": a["commande_id"], "offres_suivantes": len(offres), "offres": offres}

    def prouver_retirer(c, res):
        x = db.lire("SELECT etat FROM attente WHERE ref = ?", (res["attente"],))
        return bool(x) and x[0]["etat"] == "retiree"

    def defaire_retirer(c, res):
        with db.transaction() as tx:
            for o in res["offres"]:                # les offres faites au suivant grâce à ce retrait retombent
                tx.execute("UPDATE commandes SET etat = 'annulee', note = 'offre défaite' WHERE id = ? AND etat IN ('retenue','en_attente')", (o["commande_id"],))
                tx.execute("UPDATE attente SET etat = 'attente', commande_id = NULL, offre_jusqua = 0 WHERE id = ? AND etat = 'offerte'", (o["attente"],))
                tx.execute("DELETE FROM courriels WHERE id = ? AND etat = 'a_envoyer'", (o["courriel_id"],))
            tx.execute("UPDATE attente SET etat = ? WHERE ref = ? AND etat = 'retiree'", (res["avant"], res["attente"]))
            if res["avant"] == "offerte" and res["commande_id"]:
                tx.execute("UPDATE commandes SET etat = 'retenue', note = '' WHERE id = ? AND etat = 'annulee' AND expire_le > ?", (res["commande_id"], v.horloge()))

    # ── côté titulaire ───────────────────────────────────────────────────────
    def liste(c, evenement_id=0, etat=""):
        sql, p = "SELECT a.*, t.nom AS billet FROM attente a LEFT JOIN types_billets t ON t.id = a.type_billet_id WHERE 1 = 1", []
        if evenement_id:
            sql, p = sql + " AND a.evenement_id = ?", p + [int(evenement_id)]
        if etat:
            sql, p = sql + " AND a.etat = ?", p + [etat]
        return {"attente": db.lire(sql + " ORDER BY a.evenement_id, a.id", tuple(p))}

    def proposer_cap(c, evenement_id=0):
        with db.transaction() as tx:
            offres = proposer(ctx, tx, int(evenement_id) or None)
        return {"offres": offres}

    def prouver_proposer(c, res):
        return all(db.lire("SELECT etat FROM attente WHERE id = ?", (o["attente"],))[0]["etat"] in ("offerte", "convertie") for o in res["offres"])

    def defaire_proposer(c, res):
        with db.transaction() as tx:
            for o in res["offres"]:
                tx.execute("UPDATE commandes SET etat = 'annulee', note = 'offre défaite' WHERE id = ? AND etat IN ('retenue','en_attente')", (o["commande_id"],))
                tx.execute("UPDATE attente SET etat = 'attente', commande_id = NULL, offre_jusqua = 0 WHERE id = ? AND etat = 'offerte'", (o["attente"],))
                tx.execute("DELETE FROM courriels WHERE id = ? AND etat = 'a_envoyer'", (o["courriel_id"],))

    def moteur(c):
        with db.transaction() as tx:
            return {"offres": len(proposer(ctx, tx))}

    ctx.implementer("public_attente_inscrire", inscrire, prouver_inscrire, defaire_inscrire, simuler=lambda x, evenement="", **_: "inscrirait quelqu'un sur la liste d'attente de %s" % evenement)
    ctx.implementer("public_attente_suivre", suivre)
    ctx.implementer("public_attente_retirer", retirer, prouver_retirer, defaire_retirer, simuler=lambda x, **_: "retirerait une inscription de la liste d'attente")
    ctx.implementer("attente_liste", liste)
    ctx.implementer("attente_proposer", proposer_cap, prouver_proposer, defaire_proposer, simuler=lambda x, evenement_id=0, **_: "ferait les offres que le stock permet pour l'événement %s" % evenement_id)
    ctx.moteur("attente", moteur)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _type_pour, reconcilier, proposer, fermer_evenement, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
