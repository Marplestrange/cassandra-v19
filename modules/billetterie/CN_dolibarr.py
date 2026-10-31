# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #96fd09
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : le pont facultatif vers Dolibarr (tiers, factures, paiements, avoirs, versements de commissions), par le module « dolibarr ».
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=96fd09 ▼▼▼
"""Billetterie : le pont facultatif vers Dolibarr (tiers, factures, paiements, avoirs, versements de commissions), par le module « dolibarr ».

Règles qui tiennent tout (voir docs/CN_BILLETTERIE.md §5 ter) :
  - Dolibarr n'est JAMAIS sur le chemin d'un paiement : les écritures sont EMPILÉES (CN_file_dolibarr.py) et faites ici, en arrière-plan ;
  - chaque écriture est IDEMPOTENTE : avant de créer, on cherche par la référence extérieure (la référence de la commande) ; une écriture rejouée ne double rien ;
  - une écriture qui échoue attend et se retente (6 essais espacés), puis passe en « échec » avec sa raison : la vente n'est jamais touchée ;
  - Dolibarr garde son autorité : taux, numérotation, comptes comptables y restent ; la billetterie ne garde que des identifiants ;
  - un don n'est pas une vente : il n'entre pas dans la facture (le module Dons de Dolibarr n'a pas de route d'API, le reçu fiscal se fait comme dit au §5 quater) ;
  - ce qui n'a pas pu être éprouvé contre une vraie instance (l'avoir) est dit dans la capacité : à valider sur une entité de recette avant d'y croire.
Elle n'a ni adresse ni clé de Dolibarr : chaque écriture passe par une capacité du module « dolibarr » (ctx.agir, acteur « cassandra », compte système « noyau »), donc par SON palier, SON journal et SA garde de société.
"""
from __future__ import annotations

import json

from . import CN_file_dolibarr as fil
from . import CN_ventes as v

ESSAIS_MAX = 6
BASE_DELAI_S = 300
MODES = {"stripe": "CB", "paypal": "CB", "helloasso": "CB", "carte_terminal": "CB", "carte_declaree": "CB", "especes": "LIQ", "virement": "VIR"}
BANQUES = {"CB": "dolibarr_banque_carte", "LIQ": "dolibarr_banque_especes", "VIR": "dolibarr_banque_virement"}


class PontErreur(Exception):
    def __init__(self, message, injoignable=False):
        super().__init__(message)
        self.injoignable = injoignable


def agir(ctx, capacite, args):
    """UNE porte vers Dolibarr : une capacité du module « dolibarr » (son adresse, sa clé, sa garde de société, son palier, son journal). Rend son résultat ; sinon dit pourquoi, et la file attend."""
    r = ctx.agir("dolibarr." + capacite, args, acteur="cassandra")
    statut = r.get("statut")
    if statut == "faite":
        res = r.get("resultat")
        if isinstance(res, dict) and res.get("differe"):                # une panne de Dolibarr est rendue comme un report : la capacité n'est pas en faute, la file se retente
            raise PontErreur(str(res["differe"])[:300], injoignable="injoignable" in str(res["differe"]))
        return res
    if statut == "racontee":
        raise PontErreur("le palier de « dolibarr.%s » est « raconter » : la billetterie n'écrit pas dans la comptabilité tant que l'administrateur n'a pas choisi « auto » (Dolibarr › Capacités)" % capacite)
    raison = str(r.get("erreur") or r.get("raison") or r.get("motif") or statut or "refusé")
    raise PontErreur(raison[:300], injoignable="injoignable" in raison)


def _eur(c):
    return round(int(c) / 100.0, 2)


# ── les tiers ────────────────────────────────────────────────────────────────
def tiers_client(ctx, db, cmd):
    """Le tiers client de la commande : celui déjà rapproché, sinon retrouvé par courriel, sinon créé. Une vente sans fiche client va au tiers « Clients divers »."""
    cli = db.lire("SELECT * FROM clients WHERE id = ?", (cmd["client_id"],))[0] if cmd["client_id"] else None
    if not cli or not ctx.reglage("dolibarr_tiers"):
        return tiers_divers(ctx, db)
    if cli["dolibarr_id"]:
        return int(cli["dolibarr_id"])
    sid = agir(ctx, "bil_tiers", {"genre": "client", "ref": cli["ref"], "nom": cli["nom"] or cli["mail"], "mail": cli["mail"], "tel": cli["tel"], "adresse": cli["adresse"],
                                  "code_postal": cli["code_postal"], "ville": cli["ville"], "pays": cli["pays"] or "FR"})["id"]
    db.ecrire("UPDATE clients SET dolibarr_id = ? WHERE id = ?", (int(sid), cli["id"]))
    return int(sid)


def tiers_divers(ctx, db):
    x = db.lire("SELECT valeur FROM dolibarr_cles WHERE nom = 'tiers_divers'")
    if x:
        return int(x[0]["valeur"])
    sid = agir(ctx, "bil_tiers", {"genre": "client", "ref": "BILLETTERIE-DIVERS", "divers": True})["id"]
    db.ecrire("INSERT OR REPLACE INTO dolibarr_cles(nom, valeur) VALUES ('tiers_divers', ?)", (str(int(sid)),))
    return int(sid)


def tiers_fournisseur(ctx, db, porteur, porteur_id):
    table = "revendeurs" if porteur == "revendeur" else "artistes"
    f = db.lire("SELECT * FROM %s WHERE id = ?" % table, (porteur_id,))[0]
    if f["dolibarr_id"]:
        return int(f["dolibarr_id"]), f
    sid = agir(ctx, "bil_tiers", {"genre": "fournisseur", "ref": f["ref"], "nom": f.get("nom") or f.get("scene"), "mail": f["mail"], "tel": f["tel"], "adresse": f["adresse"],
                                  "code_postal": f["code_postal"], "ville": f["ville"], "pays": f["pays"] or "FR", "siret": f["siret"]})["id"]
    db.ecrire("UPDATE %s SET dolibarr_id = ? WHERE id = ?" % table, (int(sid), porteur_id))
    return int(sid), f


# ── les banques ──────────────────────────────────────────────────────────────
def banque(ctx, code):
    b = int(ctx.reglage(BANQUES[code]) or 0)
    if b <= 0:
        raise PontErreur("choisissez le compte bancaire Dolibarr des règlements « %s » dans les réglages du pont" % {"CB": "carte", "LIQ": "espèces", "VIR": "virement"}[code])
    return b


def _reglement(ctx, code, date, num, commentaire):
    return {"mode": code, "banque": banque(ctx, code), "date": date, "num": num, "commentaire": commentaire}


# ── les écritures ────────────────────────────────────────────────────────────
def _lignes_facture(ctx, db, cmd):
    evt = db.lire("SELECT nom, date_iso FROM evenements WHERE id = ?", (cmd["evenement_id"],))[0]
    taux = float(str(ctx.reglage("dolibarr_tva") or "0").replace(",", ".") or 0)
    lignes = []
    for l in db.lire("SELECT * FROM lignes_commande WHERE commande_id = ? ORDER BY id", (cmd["id"],)):
        lignes.append({"desc": "Billet « %s » — %s (%s)" % (l["nom"], evt["nom"], evt["date_iso"] or "date à venir"), "qty": l["quantite"], "subprice": _eur(l["prix"]), "tva_tx": taux})
    if cmd["remise"]:
        lignes.append({"desc": "Remise%s" % (" " + cmd["promo_code"] if cmd["promo_code"] else ""), "qty": 1, "subprice": -_eur(cmd["remise"]), "tva_tx": taux})
    if cmd["frais"]:
        lignes.append({"desc": "Frais d'achat sans compte", "qty": 1, "subprice": _eur(cmd["frais"]), "tva_tx": taux})
    return lignes


def _date_ts(texte):
    from datetime import datetime, timezone
    t = (texte or "")[:19].replace("T", " ")
    try:
        return int(datetime.strptime(t, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return int(v.horloge())


def ecrire_facture(ctx, db, cible):
    cmd = db.lire("SELECT * FROM commandes WHERE id = ?", (cible,))[0]
    if cmd["etat"] != "payee":
        return "ignore", "commande non payée à l'heure de l'écriture (remboursée ou annulée avant facturation)"
    if cmd["moyen"] == "offert":
        return "ignore", "billets offerts : aucune vente à facturer"
    if cmd["total"] - cmd["don"] <= 0:
        return "ignore", "rien à facturer : commande gratuite, ou seulement un don (le don ne s'écrit pas ici)"
    code = MODES.get(cmd["moyen"] or "", "CB")
    reglement = _reglement(ctx, code, _date_ts(cmd["payee_le"]), str(cmd["reference_externe"] or cmd["ref"])[:60], "Billetterie — commande %s" % cmd["ref"]) if ctx.reglage("dolibarr_paiements") else None
    r = agir(ctx, "bil_facture", {"socid": tiers_client(ctx, db, cmd), "ref_ext": cmd["ref"], "date": _date_ts(cmd["payee_le"]), "lignes": _lignes_facture(ctx, db, cmd),
                                  "note": "Billetterie — commande %s (%s)" % (cmd["ref"], cmd["moyen"] or ""), "reglement": reglement})
    db.ecrire("UPDATE commandes SET dolibarr_facture_id = ?, dolibarr_facture_ref = ? WHERE id = ?", (r["facture_id"], r["facture"], cmd["id"]))
    return "fait", json.dumps({"facture_id": r["facture_id"], "facture": r["facture"]})


def ecrire_avoir(ctx, db, cible):
    cmd = db.lire("SELECT * FROM commandes WHERE id = ?", (cible,))[0]
    if not cmd["dolibarr_facture_id"]:
        return "ignore", "aucune facture n'a été écrite pour cette commande : rien à défaire"
    if cmd["dolibarr_avoir_id"]:
        return "fait", json.dumps({"avoir_id": cmd["dolibarr_avoir_id"], "avoir": cmd["dolibarr_avoir_ref"]})
    lignes = [dict(l, subprice=-l["subprice"]) for l in _lignes_facture(ctx, db, cmd)]       # un avoir porte les montants de la facture, en négatif
    r = agir(ctx, "bil_avoir", {"socid": tiers_client(ctx, db, cmd), "ref_ext": "AVOIR-" + cmd["ref"], "source_id": cmd["dolibarr_facture_id"], "date": int(v.horloge()), "lignes": lignes,
                                "note": "Billetterie — remboursement de la commande %s" % cmd["ref"]})
    db.ecrire("UPDATE commandes SET dolibarr_avoir_id = ?, dolibarr_avoir_ref = ? WHERE id = ?", (r["avoir_id"], r["avoir"], cmd["id"]))
    return "fait", json.dumps({"avoir_id": r["avoir_id"], "avoir": r["avoir"]})


def ecrire_versement(ctx, db, cible):
    r = db.lire("SELECT * FROM retraits WHERE id = ?", (cible,))[0]
    if r["etat"] != "payee":
        return "ignore", "le retrait n'est pas versé"
    socid, porteur = tiers_fournisseur(ctx, db, r["porteur"], r["porteur_id"])
    reglement = _reglement(ctx, "VIR", _date_ts(r["traite_le"]), str(r["reference_virement"] or r["ref"])[:60], "Versement %s" % r["ref"]) if ctx.reglage("dolibarr_paiements") else None
    f = agir(ctx, "bil_versement", {"socid": socid, "ref_ext": r["ref"], "date": _date_ts(r["traite_le"]), "montant": _eur(r["montant"]), "reglement": reglement,
                                    "libelle": "Commissions de vente de billets — %s (%s)" % (porteur.get("nom") or porteur.get("scene"), r["ref"])})
    return "fait", json.dumps({"facture_fournisseur_id": f["facture_fournisseur_id"], "facture_fournisseur": f["facture_fournisseur"]})


def ecrire_adherent(ctx, db, cible):
    a = db.lire("SELECT * FROM artistes WHERE id = ?", (cible,))[0]
    mid = a["dolibarr_adherent_id"]
    if not mid:
        socid, _ = tiers_fournisseur(ctx, db, "artiste", a["id"])
        nom = (a["legal"] or a["scene"]).strip().split(" ", 1)
        mid = agir(ctx, "bil_adherent", {"ref": a["ref"], "socid": socid, "login": a["ref"].lower(), "morphy": "mor" if a["statut"] in ("Association", "Société") else "phy",
                                         "firstname": nom[0] if len(nom) > 1 else "", "lastname": nom[1] if len(nom) > 1 else nom[0], "societe": a["scene"] if a["statut"] != "Particulier" else "",
                                         "email": a["mail"], "phone": a["tel"], "address": a["adresse"], "zip": a["code_postal"], "town": a["ville"], "country_code": a["pays"] or "FR",
                                         "datefin": _date_ts(a["adhesion_fin"] + " 00:00:00") if a["adhesion_fin"] else None})["adherent_id"]
    db.ecrire("UPDATE artistes SET dolibarr_adherent_id = ? WHERE id = ?", (mid, a["id"]))
    return "fait", json.dumps({"adherent_id": mid})


OPERATIONS = {"facture": ecrire_facture, "avoir": ecrire_avoir, "versement": ecrire_versement, "adherent": ecrire_adherent}


def traiter(ctx, db, maximum=10):
    """Fait les écritures dues, dans l'ordre. S'arrête au premier « injoignable » (on ne martèle pas un Dolibarr tombé). Rend {faits, echecs, reportes, ignores, raison}."""
    out = {"faits": 0, "echecs": 0, "reportes": 0, "ignores": 0, "raison": ""}
    if not fil.relie(ctx):
        out["raison"] = "le pont Dolibarr n'est pas relié"
        return out
    dus = db.lire("SELECT * FROM dolibarr_file WHERE etat = 'a_faire' AND prochain_essai <= ? ORDER BY id LIMIT ?", (v.horloge(), max(1, min(int(maximum), 50))))
    for ligne in dus:
        try:
            etat, resultat = OPERATIONS[ligne["objet"]](ctx, db, ligne["cible_id"])
        except (PontErreur, ValueError, KeyError, IndexError) as ex:
            essais = ligne["essais"] + 1
            with db.transaction() as tx:
                if essais >= ESSAIS_MAX:
                    tx.execute("UPDATE dolibarr_file SET etat = 'echec', essais = ?, erreur = ? WHERE id = ?", (essais, str(ex)[:300], ligne["id"]))
                    out["echecs"] += 1
                else:
                    tx.execute("UPDATE dolibarr_file SET essais = ?, erreur = ?, prochain_essai = ? WHERE id = ?", (essais, str(ex)[:300], v.horloge() + BASE_DELAI_S * 2 ** (essais - 1), ligne["id"]))
                    out["reportes"] += 1
            if getattr(ex, "injoignable", False):
                out["raison"] = str(ex)
                break
            continue
        with db.transaction() as tx:
            tx.execute("UPDATE dolibarr_file SET etat = ?, resultat = ?, erreur = '', fait_le = datetime('now'), essais = essais + 1 WHERE id = ?", (etat, resultat[:500], ligne["id"]))
        out["ignores" if etat == "ignore" else "faits"] += 1
    return out


def tester(ctx):
    """Ce que Dolibarr dit de lui et ce qu'il faut pour que le pont marche : société, banques, modes de paiement, taux de TVA ; chaque point manquant dit ce qu'il faut faire."""
    return agir(ctx, "bil_tester", {"banque_" + code: int(ctx.reglage(BANQUES[code]) or 0) for code in BANQUES})


def brancher(ctx, db):
    def etat(c):
        cnt = {x["etat"]: x["n"] for x in db.lire("SELECT etat, COUNT(*) AS n FROM dolibarr_file GROUP BY etat")}
        doms = {k: bool(ctx.reglage("dolibarr_" + k)) for k in ("tiers", "factures", "paiements", "avoirs", "commissions", "adherents")}
        return {"relie": fil.relie(ctx), "domaines": doms, "a_faire": cnt.get("a_faire", 0), "faits": cnt.get("fait", 0), "echecs": cnt.get("echec", 0), "ignores": cnt.get("ignore", 0),
                "derniers_echecs": db.lire("SELECT id, cle, essais, erreur FROM dolibarr_file WHERE etat IN ('echec','a_faire') AND erreur <> '' ORDER BY id DESC LIMIT 5")}

    def tester_cap(c):
        try:
            return tester(ctx)
        except PontErreur as ex:
            raise ValueError(str(ex))

    def file(c, etat_="", limite=100):
        sql, p = "SELECT * FROM dolibarr_file WHERE 1 = 1", []
        if etat_:
            sql, p = sql + " AND etat = ?", p + [etat_]
        return {"file": db.lire(sql + " ORDER BY id DESC LIMIT ?", tuple(p) + (max(1, min(int(limite or 100), 500)),))}

    def rattraper(c, maximum=10):
        return traiter(ctx, db, maximum)

    def prouver_rattraper(c, res):
        return True

    def defaire_rattraper(c, res):
        return None                                    # une écriture comptable se corrige dans Dolibarr (avoir, annulation) : le retour de la capacité le dit

    def relancer(c, id=0):
        with db.transaction() as tx:
            x = tx.execute("SELECT * FROM dolibarr_file WHERE id = ?", (int(id),)).fetchone()
            if not x:
                raise ValueError("écriture introuvable")
            if x["etat"] != "echec":
                raise ValueError("seule une écriture en échec se relance")
            tx.execute("UPDATE dolibarr_file SET etat = 'a_faire', essais = 0, prochain_essai = 0 WHERE id = ?", (x["id"],))
        return {"id": int(id)}

    def prouver_relancer(c, res):
        x = db.lire("SELECT etat FROM dolibarr_file WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] == "a_faire"

    def defaire_relancer(c, res):
        db.ecrire("UPDATE dolibarr_file SET etat = 'echec' WHERE id = ? AND etat = 'a_faire'", (res["id"],))

    def adherent(c, artiste_id=0):
        a = db.lire("SELECT id, ref, scene FROM artistes WHERE id = ?", (int(artiste_id),))
        if not a:
            raise ValueError("artiste introuvable")
        with db.transaction() as tx:
            if not fil.relie(ctx) or not ctx.reglage("dolibarr_adherents"):
                raise ValueError("le pont Dolibarr n'est pas relié ou le domaine « artistes → adhérents » est coupé (réglages du pont)")
            x = tx.execute("SELECT * FROM dolibarr_file WHERE cle = ?", ("adherent:%d" % a[0]["id"],)).fetchone()
            if x:
                if x["etat"] == "echec":
                    tx.execute("UPDATE dolibarr_file SET etat = 'a_faire', essais = 0, prochain_essai = 0 WHERE id = ?", (x["id"],))
                    return {"id": x["id"], "ref": a[0]["ref"], "deja": False, "relance": True}
                return {"id": x["id"], "ref": a[0]["ref"], "deja": True, "relance": False}
            fil.empiler(ctx, tx, "adherent", a[0]["id"])
            x = tx.execute("SELECT id FROM dolibarr_file WHERE cle = ?", ("adherent:%d" % a[0]["id"],)).fetchone()
        return {"id": x["id"], "ref": a[0]["ref"], "deja": False, "relance": False}

    def prouver_adherent(c, res):
        x = db.lire("SELECT etat FROM dolibarr_file WHERE id = ?", (res["id"],))
        return bool(x) and x[0]["etat"] in ("a_faire", "fait")

    def defaire_adherent(c, res):
        if res.get("deja"):
            return
        db.ecrire("DELETE FROM dolibarr_file WHERE id = ? AND etat = 'a_faire' AND essais = 0", (res["id"],))

    def moteur(c):
        return traiter(ctx, db)

    ctx.implementer("dolibarr_adherent", adherent, prouver_adherent, defaire_adherent, simuler=lambda x, artiste_id=0, **_: "empilerait l'écriture de l'artiste %s comme adhérent dans Dolibarr" % artiste_id)
    ctx.implementer("dolibarr_etat", etat)
    ctx.implementer("dolibarr_tester", tester_cap)
    ctx.implementer("dolibarr_file", file)
    ctx.implementer("dolibarr_rattraper", rattraper, prouver_rattraper, defaire_rattraper, simuler=lambda x, **_: "ferait les écritures dues dans Dolibarr")
    ctx.implementer("dolibarr_relancer", relancer, prouver_relancer, defaire_relancer, simuler=lambda x, id=0, **_: "remettrait l'écriture %s dans la file" % id)
    ctx.moteur("dolibarr", moteur)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : PontErreur, agir, _eur, tiers_client, tiers_divers …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
