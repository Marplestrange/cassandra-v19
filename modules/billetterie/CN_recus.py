# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #859e7f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : les reçus fiscaux de don, produits par la billetterie quand Dolibarr n'est pas relié.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=859e7f ▼▼▼
"""Billetterie : les reçus fiscaux de don, produits par la billetterie quand Dolibarr n'est pas relié.

Règles qui tiennent tout :
  - un reçu ne couvre QUE la part « don » d'une commande payée, jamais un billet ;
  - il n'est émis que si l'organisateur est une association déclarée éligible, avec la mention de sa base légale (sans elle, aucun reçu n'est proposé) ;
  - son numéro est continu et ne se réutilise jamais ; son contenu est une copie figée ; un reçu ne s'efface pas, il s'annule (don remboursé) en gardant son numéro ;
  - quand Dolibarr est relié (réglage « reçu fiscal sans Dolibarr » coupé), c'est le Cerfa de Dolibarr qui fait foi et la billetterie n'en fabrique pas.
"""
from __future__ import annotations

import csv
import hmac
import io
import json

from . import CN_identifiants as ids
from . import CN_regles as r

MODES = {"stripe": "carte bancaire", "helloasso": "carte bancaire", "paypal": "PayPal", "carte_terminal": "carte bancaire", "carte_declaree": "carte bancaire",
         "especes": "espèces", "virement": "virement"}


def conditions(ctx):
    """Ce qui doit être vrai pour émettre un reçu : lève la phrase de ce qui manque."""
    if not ctx.reglage("recu_fiscal_autonome"):
        raise ValueError("le reçu fiscal est émis par Dolibarr (le pont est relié) : la billetterie n'en fabrique pas")
    if ctx.reglage("titulaire_statut") != "association":
        raise ValueError("seule une association peut émettre un reçu de don")
    if not ctx.reglage("dons_eligible"):
        raise ValueError("l'organisateur n'est pas déclaré éligible aux reçus de dons (Réglages › Titulaire)")
    base = (ctx.reglage("dons_base_legale") or "").strip()
    if not base:
        raise ValueError("indiquez la base légale de l'éligibilité (article du code général des impôts, reconnaissance d'intérêt général) avant d'émettre un reçu")
    for k, lib in (("titulaire_nom", "le nom"), ("titulaire_adresse", "l'adresse")):
        if not (ctx.reglage(k) or "").strip():
            raise ValueError("renseignez %s de l'organisme (Réglages › Titulaire) avant d'émettre un reçu" % lib)
    return base


def emettre(ctx, tx, cmd, adresse, nom="", par=""):
    """Émet le reçu du don d'une commande payée. Rend la ligne du reçu."""
    base = conditions(ctx)
    if cmd["etat"] != "payee":
        raise ValueError("seule une commande payée donne un reçu (état : %s)" % cmd["etat"])
    if cmd["don"] <= 0:
        raise ValueError("cette commande ne contient pas de don : un billet ne donne jamais de reçu fiscal")
    if cmd["moyen"] == "offert":
        raise ValueError("un don offert ne donne pas de reçu")
    adresse = r.requis(adresse, "l'adresse postale du donateur", 300)
    if len(adresse) < 8:
        raise ValueError("l'adresse postale du donateur est incomplète")
    nom = r.requis(nom or cmd["nom"], "le nom du donateur")
    deja = tx.execute("SELECT * FROM recus_fiscaux WHERE commande_id = ? AND etat = 'emis'", (cmd["id"],)).fetchone()
    if deja:
        return dict(deja), True
    date_don = (cmd["payee_le"] or "")[:10]
    mode = MODES.get(cmd["moyen"], cmd["moyen"] or "autre")
    n = ids.suivant(tx, "recu_fiscal")
    numero = "RF-%06d" % n
    contenu = {"numero": numero, "modele": "Cerfa 11580 (don aux œuvres) — reçu produit par la billetterie",
               "organisme": {"nom": ctx.reglage("titulaire_nom"), "adresse": ctx.reglage("titulaire_adresse"), "siret": ctx.reglage("titulaire_siret"),
                             "base_legale": base},
               "donateur": {"nom": nom, "adresse": adresse}, "montant_centimes": cmd["don"], "date_don": date_don, "forme": "don manuel", "nature": "numéraire", "mode": mode,
               "commande": cmd["ref"], "mention": "Le bénéficiaire certifie sur l'honneur que les dons et versements qu'il reçoit ouvrent droit à la réduction d'impôt prévue aux articles 200 et 238 bis du code général des impôts."}
    rid = tx.execute("INSERT INTO recus_fiscaux(numero, commande_id, montant, nom, adresse, mail, date_don, mode, contenu, par) VALUES (?,?,?,?,?,?,?,?,?,?)",
                     (numero, cmd["id"], cmd["don"], nom, adresse, cmd["mail"], date_don, mode, json.dumps(contenu, ensure_ascii=False, sort_keys=True), par)).lastrowid
    return dict(tx.execute("SELECT * FROM recus_fiscaux WHERE id = ?", (rid,)).fetchone()), False


def annuler(tx, recu_id, motif):
    tx.execute("UPDATE recus_fiscaux SET etat = 'annule', motif = ?, annule_le = datetime('now') WHERE id = ? AND etat = 'emis'", (r.texte(motif, 200), recu_id))


def annuler_pour_commande(tx, commande_id, motif):
    """Un don remboursé n'a plus de reçu en vigueur. Rend les identifiants annulés (pour pouvoir les rouvrir)."""
    ids_ = [x[0] for x in tx.execute("SELECT id FROM recus_fiscaux WHERE commande_id = ? AND etat = 'emis'", (commande_id,)).fetchall()]
    for i in ids_:
        annuler(tx, i, motif)
    return ids_


def rouvrir(tx, recu_id):
    tx.execute("UPDATE recus_fiscaux SET etat = 'emis', motif = '', annule_le = '' WHERE id = ? AND etat = 'annule'", (recu_id,))


def rouvrir_pour_commande(tx, commande_id, motif):
    """Un remboursement défait : les reçus annulés POUR ce motif reviennent en vigueur (pas ceux qu'on a annulés à la main)."""
    for (i,) in tx.execute("SELECT id FROM recus_fiscaux WHERE commande_id = ? AND etat = 'annule' AND motif = ?", (commande_id, motif)).fetchall():
        rouvrir(tx, i)


def vue(rec):
    """Le reçu tel qu'on le montre : ses champs et son contenu figé déplié."""
    out = {k: rec[k] for k in ("numero", "montant", "nom", "date_don", "mode", "etat", "motif", "emis_le")}
    out["contenu"] = json.loads(rec["contenu"])
    return out


def brancher(ctx, db):
    def _commande(tx, ref):
        c = tx.execute("SELECT * FROM commandes WHERE ref = ?", (str(ref).strip().upper(),)).fetchone()
        if not c:
            raise ValueError("commande introuvable")
        return dict(c)

    # ── côté titulaire ───────────────────────────────────────────────────────
    def emettre_cap(c, commande="", adresse="", nom=""):
        with db.transaction() as tx:
            cmd = _commande(tx, commande)
            rec, deja = emettre(ctx, tx, cmd, adresse, nom, ctx.compte)
        return {"numero": rec["numero"], "id": rec["id"], "deja": deja}

    def prouver_emettre(c, res):
        x = db.lire("SELECT etat FROM recus_fiscaux WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "emis"

    def defaire_emettre(c, res):
        if res.get("deja"):
            return
        with db.transaction() as tx:
            annuler(tx, res["id"], "émission défaite")

    def annuler_cap(c, numero="", motif=""):
        motif = r.requis(motif, "le motif d'annulation", 200)
        with db.transaction() as tx:
            x = tx.execute("SELECT * FROM recus_fiscaux WHERE numero = ?", (str(numero).strip().upper(),)).fetchone()
            if not x:
                raise ValueError("reçu introuvable")
            if x["etat"] != "emis":
                raise ValueError("ce reçu est déjà annulé")
            annuler(tx, x["id"], motif)
        return {"numero": x["numero"], "id": x["id"]}

    def prouver_annuler(c, res):
        x = db.lire("SELECT etat FROM recus_fiscaux WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "annule"

    def defaire_annuler(c, res):
        with db.transaction() as tx:
            deja = tx.execute("SELECT commande_id FROM recus_fiscaux WHERE id = ?", (res["id"],)).fetchone()
            if tx.execute("SELECT 1 FROM recus_fiscaux WHERE commande_id = ? AND etat = 'emis'", (deja["commande_id"],)).fetchone():
                raise ValueError("un autre reçu est en vigueur pour cette commande")
            rouvrir(tx, res["id"])

    def liste(c, annee="", etat=""):
        sql, p = "SELECT numero, montant, nom, date_don, mode, etat, motif, emis_le, commande_id FROM recus_fiscaux WHERE 1 = 1", []
        if annee:
            sql, p = sql + " AND substr(date_don, 1, 4) = ?", p + [str(annee)[:4]]
        if etat:
            sql, p = sql + " AND etat = ?", p + [etat]
        rows = db.lire(sql + " ORDER BY id", tuple(p))
        return {"recus": rows, "total_emis": sum(x["montant"] for x in rows if x["etat"] == "emis")}

    def un(c, numero=""):
        x = db.lire("SELECT * FROM recus_fiscaux WHERE numero = ?", (str(numero).strip().upper(),))
        if not x:
            raise ValueError("reçu introuvable")
        return vue(x[0])

    def exporter(c, annee=""):
        """Le registre des reçus de l'année, en CSV : de quoi tenir la comptabilité et répondre à un contrôle (conservation : 10 ans)."""
        sortie = io.StringIO()
        w = csv.writer(sortie, delimiter=";", lineterminator="\n")
        w.writerow(["numero", "date_don", "donateur", "adresse", "montant_eur", "mode", "etat", "motif_annulation", "commande"])
        sql, p = "SELECT rf.*, c.ref AS cref FROM recus_fiscaux rf JOIN commandes c ON c.id = rf.commande_id WHERE 1 = 1", []
        if annee:
            sql, p = sql + " AND substr(rf.date_don, 1, 4) = ?", p + [str(annee)[:4]]
        for x in db.lire(sql + " ORDER BY rf.id", tuple(p)):
            w.writerow([x["numero"], x["date_don"], x["nom"], x["adresse"].replace("\n", " "), "%.2f" % (x["montant"] / 100), x["mode"], x["etat"], x["motif"], x["cref"]])
        return {"csv": sortie.getvalue()}

    # ── côté donateur : par le jeton de suivi de sa commande ─────────────────
    def _publique(tx, commande, suivi):
        cmd = tx.execute("SELECT * FROM commandes WHERE ref = ?", (str(commande).strip().upper(),)).fetchone()
        if not cmd or not cmd["suivi"] or not hmac.compare_digest(str(cmd["suivi"]), str(suivi)):
            raise ValueError("commande introuvable")
        return dict(cmd)

    def demander(c, commande="", suivi="", adresse="", nom=""):
        with db.transaction() as tx:
            cmd = _publique(tx, commande, suivi)
            rec, deja = emettre(ctx, tx, cmd, adresse, nom, "donateur")
        return {"numero": rec["numero"], "id": rec["id"], "deja": deja}

    def lire_public(c, commande="", suivi=""):
        with db.transaction() as tx:
            cmd = _publique(tx, commande, suivi)
            x = tx.execute("SELECT * FROM recus_fiscaux WHERE commande_id = ? AND etat = 'emis'", (cmd["id"],)).fetchone()
        if not x:
            raise ValueError("aucun reçu pour cette commande")
        return vue(dict(x))

    ctx.implementer("recu_fiscal_emettre", emettre_cap, prouver_emettre, defaire_emettre, simuler=lambda x, commande="", **_: "émettrait le reçu fiscal du don de la commande %s" % commande)
    ctx.implementer("recu_fiscal_annuler", annuler_cap, prouver_annuler, defaire_annuler, simuler=lambda x, numero="", **_: "annulerait le reçu fiscal %s" % numero)
    ctx.implementer("recus_fiscaux", liste)
    ctx.implementer("recu_fiscal", un)
    ctx.implementer("recus_export", exporter)
    ctx.implementer("public_recu_demander", demander, prouver_emettre, defaire_emettre, simuler=lambda x, commande="", **_: "émettrait le reçu fiscal du don de la commande %s" % commande)
    ctx.implementer("public_recu", lire_public)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : conditions, emettre, annuler, annuler_pour_commande, rouvrir, rouvrir_pour_commande, vue, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
