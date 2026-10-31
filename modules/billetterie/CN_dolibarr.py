# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #102333
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : le pont facultatif vers Dolibarr (tiers, factures, paiements, avoirs, versements de commissions).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=102333 ▼▼▼
"""Billetterie : le pont facultatif vers Dolibarr (tiers, factures, paiements, avoirs, versements de commissions).

Règles qui tiennent tout (voir docs/CN_BILLETTERIE.md §5 ter) :
  - Dolibarr n'est JAMAIS sur le chemin d'un paiement : les écritures sont EMPILÉES (CN_file_dolibarr.py) et faites ici, en arrière-plan ;
  - chaque écriture est IDEMPOTENTE : avant de créer, on cherche par la référence extérieure (la référence de la commande) ; une écriture rejouée ne double rien ;
  - une écriture qui échoue attend et se retente (6 essais espacés), puis passe en « échec » avec sa raison : la vente n'est jamais touchée ;
  - Dolibarr garde son autorité : taux, numérotation, comptes comptables y restent ; la billetterie ne garde que des identifiants ;
  - un don n'est pas une vente : il n'entre pas dans la facture (le module Dons de Dolibarr n'a pas de route d'API, le reçu fiscal se fait comme dit au §5 quater) ;
  - ce qui n'a pas pu être éprouvé contre une vraie instance (l'avoir) est dit dans la capacité : à valider sur une entité de recette avant d'y croire.
Le transport (`HTTP`) se remplace dans les bancs : on ne parle pas à un vrai Dolibarr depuis un banc.
"""
from __future__ import annotations

import gzip
import json
import urllib.error
import urllib.parse
import urllib.request

from . import CN_file_dolibarr as fil
from . import CN_ventes as v

HTTP = {}                 # « dolibarr » : une fonction (methode, url, entetes, corps_octets_ou_None, delai) -> (code, json)
ESSAIS_MAX = 6
BASE_DELAI_S = 300
MODES = {"stripe": "CB", "paypal": "CB", "helloasso": "CB", "carte_terminal": "CB", "carte_declaree": "CB", "especes": "LIQ", "virement": "VIR"}
BANQUES = {"CB": "dolibarr_banque_carte", "LIQ": "dolibarr_banque_especes", "VIR": "dolibarr_banque_virement"}


class PontErreur(Exception):
    def __init__(self, message, injoignable=False):
        super().__init__(message)
        self.injoignable = injoignable


def http_reel(methode, url, entetes, corps, delai=15):
    req = urllib.request.Request(url, data=corps, headers=entetes, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            brut = r.read()
            code = r.status
    except urllib.error.HTTPError as ex:
        brut, code = ex.read(), ex.code
    except (urllib.error.URLError, OSError) as ex:
        raise PontErreur("Dolibarr est injoignable (%s)" % type(getattr(ex, "reason", ex)).__name__, injoignable=True)
    if brut[:2] == b"\x1f\x8b":
        brut = gzip.decompress(brut)
    texte = brut.decode("utf-8", "replace").strip()
    try:
        return code, (json.loads(texte) if texte else None)
    except ValueError:
        return code, texte


def appel(ctx, methode, chemin, corps=None, params=None):
    url = str(ctx.reglage("dolibarr_url")).rstrip("/") + chemin
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    entetes = {"DOLAPIKEY": str(ctx.reglage("dolibarr_cle")), "Accept": "application/json"}
    if str(ctx.reglage("dolibarr_hote") or "").strip():
        entetes["Host"] = str(ctx.reglage("dolibarr_hote")).strip()
    donnees = None
    if corps is not None:
        donnees = json.dumps(corps, ensure_ascii=False).encode("utf-8")
        entetes["Content-Type"] = "application/json"
    code, rep = (HTTP.get("dolibarr") or http_reel)(methode, url, entetes, donnees, 15)
    if code in (401, 403):
        raise PontErreur("Dolibarr refuse l'accès (HTTP %d) : vérifiez la clé d'API et l'entité" % code)
    if code == 404 and methode == "GET":
        return None                                   # Dolibarr répond 404 quand une recherche ne trouve rien
    if code >= 400:
        msg = ""
        if isinstance(rep, dict):
            msg = ((rep.get("error") or {}).get("message") if isinstance(rep.get("error"), dict) else rep.get("error")) or rep.get("message") or ""
        raise PontErreur("Dolibarr répond HTTP %d%s" % (code, " : " + str(msg)[:200] if msg else ""))
    return rep


def _eur(c):
    return round(int(c) / 100.0, 2)


def _filtre(champ, valeur):
    if "'" in str(valeur) or ")" in str(valeur) or "(" in str(valeur):
        raise PontErreur("valeur de recherche refusée : %r" % valeur)
    return "(t.%s:=:'%s')" % (champ, valeur)


def _premier_id(rep):
    if isinstance(rep, list) and rep and isinstance(rep[0], dict) and rep[0].get("id") is not None:
        return int(rep[0]["id"])
    return None


# ── les tiers ────────────────────────────────────────────────────────────────
def tiers_client(ctx, db, cmd):
    """Le tiers client de la commande : celui déjà rapproché, sinon retrouvé par courriel, sinon créé. Une vente sans fiche client va au tiers « Clients divers »."""
    cli = db.lire("SELECT * FROM clients WHERE id = ?", (cmd["client_id"],))[0] if cmd["client_id"] else None
    if not cli or not ctx.reglage("dolibarr_tiers"):
        return tiers_divers(ctx, db)
    if cli["dolibarr_id"]:
        return int(cli["dolibarr_id"])
    sid = _premier_id(appel(ctx, "GET", "/thirdparties", params={"sqlfilters": _filtre("email", cli["mail"]), "limit": 1})) if cli["mail"] else None
    if not sid:
        sid = appel(ctx, "POST", "/thirdparties", {"name": cli["nom"] or cli["mail"], "email": cli["mail"], "phone": cli["tel"], "client": 1, "code_client": "auto", "address": cli["adresse"], "zip": cli["code_postal"],
                                                    "town": cli["ville"], "country_code": cli["pays"] or "FR", "ref_ext": cli["ref"]})
    db.ecrire("UPDATE clients SET dolibarr_id = ? WHERE id = ?", (int(sid), cli["id"]))
    return int(sid)


def tiers_divers(ctx, db):
    x = db.lire("SELECT valeur FROM dolibarr_cles WHERE nom = 'tiers_divers'")
    if x:
        return int(x[0]["valeur"])
    sid = _premier_id(appel(ctx, "GET", "/thirdparties", params={"sqlfilters": _filtre("ref_ext", "BILLETTERIE-DIVERS"), "limit": 1}))
    if not sid:
        sid = appel(ctx, "POST", "/thirdparties", {"name": "Clients divers (billetterie)", "client": 1, "code_client": "auto", "ref_ext": "BILLETTERIE-DIVERS"})
    db.ecrire("INSERT OR REPLACE INTO dolibarr_cles(nom, valeur) VALUES ('tiers_divers', ?)", (str(int(sid)),))
    return int(sid)


def tiers_fournisseur(ctx, db, porteur, porteur_id):
    table = "revendeurs" if porteur == "revendeur" else "artistes"
    f = db.lire("SELECT * FROM %s WHERE id = ?" % table, (porteur_id,))[0]
    if f["dolibarr_id"]:
        return int(f["dolibarr_id"]), f
    sid = _premier_id(appel(ctx, "GET", "/thirdparties", params={"sqlfilters": _filtre("ref_ext", f["ref"]), "limit": 1}))
    if not sid:
        sid = appel(ctx, "POST", "/thirdparties", {"name": f.get("nom") or f.get("scene"), "email": f["mail"], "phone": f["tel"], "fournisseur": 1, "code_fournisseur": "auto", "client": 0, "address": f["adresse"],
                                                    "zip": f["code_postal"], "town": f["ville"], "country_code": f["pays"] or "FR", "idprof1": f["siret"], "ref_ext": f["ref"]})
    db.ecrire("UPDATE %s SET dolibarr_id = ? WHERE id = ?" % table, (int(sid), porteur_id))
    return int(sid), f


# ── les modes de paiement et les banques ─────────────────────────────────────
def mode_id(ctx, code):
    rep = appel(ctx, "GET", "/setup/dictionary/payment_types", params={"limit": 200}) or []
    for m in rep if isinstance(rep, list) else []:
        if str(m.get("code")).upper() == code:
            return int(m["id"])
    raise PontErreur("Dolibarr n'a pas de mode de paiement de code « %s » : créez-le dans Dolibarr (Configuration › Dictionnaires)" % code)


def banque(ctx, code):
    b = int(ctx.reglage(BANQUES[code]) or 0)
    if b <= 0:
        raise PontErreur("choisissez le compte bancaire Dolibarr des règlements « %s » dans les réglages du pont" % {"CB": "carte", "LIQ": "espèces", "VIR": "virement"}[code])
    return b


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
    lignes = _lignes_facture(ctx, db, cmd)
    fid = cmd["dolibarr_facture_id"] or _premier_id(appel(ctx, "GET", "/invoices", params={"sqlfilters": _filtre("ref_ext", cmd["ref"]), "limit": 1}))
    if not fid:
        socid = tiers_client(ctx, db, cmd)
        fid = int(appel(ctx, "POST", "/invoices", {"socid": socid, "type": 0, "date": _date_ts(cmd["payee_le"]), "ref_ext": cmd["ref"], "lines": lignes,
                                                    "note_private": "Billetterie — commande %s (%s)" % (cmd["ref"], cmd["moyen"] or "")}))
    f = appel(ctx, "GET", "/invoices/%d" % fid) or {}
    if str(f.get("statut", f.get("status", "0"))) == "0":                         # brouillon : on la valide (Dolibarr lui donne son numéro légal)
        f = appel(ctx, "POST", "/invoices/%d/validate" % fid, {"idwarehouse": 0, "notrigger": 0}) or f
    ref = str(f.get("ref") or "")
    db.ecrire("UPDATE commandes SET dolibarr_facture_id = ?, dolibarr_facture_ref = ? WHERE id = ?", (fid, ref, cmd["id"]))
    if ctx.reglage("dolibarr_paiements"):
        deja = appel(ctx, "GET", "/invoices/%d/payments" % fid)
        if not (isinstance(deja, list) and deja):
            code = MODES.get(cmd["moyen"] or "", "CB")
            appel(ctx, "POST", "/invoices/%d/payments" % fid, {"datepaye": _date_ts(cmd["payee_le"]), "paymentid": mode_id(ctx, code), "closepaidinvoices": "yes", "accountid": banque(ctx, code),
                                                                "num_payment": str(cmd["reference_externe"] or cmd["ref"])[:60], "comment": "Billetterie — commande %s" % cmd["ref"]})
    return "fait", json.dumps({"facture_id": fid, "facture": ref})


def ecrire_avoir(ctx, db, cible):
    cmd = db.lire("SELECT * FROM commandes WHERE id = ?", (cible,))[0]
    if not cmd["dolibarr_facture_id"]:
        return "ignore", "aucune facture n'a été écrite pour cette commande : rien à défaire"
    if cmd["dolibarr_avoir_id"]:
        return "fait", json.dumps({"avoir_id": cmd["dolibarr_avoir_id"], "avoir": cmd["dolibarr_avoir_ref"]})
    aid = _premier_id(appel(ctx, "GET", "/invoices", params={"sqlfilters": _filtre("ref_ext", "AVOIR-" + cmd["ref"]), "limit": 1}))
    if not aid:
        socid = tiers_client(ctx, db, cmd)
        lignes = [dict(l, subprice=-l["subprice"]) for l in _lignes_facture(ctx, db, cmd)]       # un avoir porte les montants de la facture, en négatif
        aid = int(appel(ctx, "POST", "/invoices", {"socid": socid, "type": 2, "fk_facture_source": cmd["dolibarr_facture_id"], "date": int(v.horloge()), "ref_ext": "AVOIR-" + cmd["ref"], "lines": lignes,
                                                    "note_private": "Billetterie — remboursement de la commande %s" % cmd["ref"]}))
    f = appel(ctx, "GET", "/invoices/%d" % aid) or {}
    if str(f.get("statut", f.get("status", "0"))) == "0":
        f = appel(ctx, "POST", "/invoices/%d/validate" % aid, {"idwarehouse": 0, "notrigger": 0}) or f
    ref = str(f.get("ref") or "")
    db.ecrire("UPDATE commandes SET dolibarr_avoir_id = ?, dolibarr_avoir_ref = ? WHERE id = ?", (aid, ref, cmd["id"]))
    return "fait", json.dumps({"avoir_id": aid, "avoir": ref})


def ecrire_versement(ctx, db, cible):
    r = db.lire("SELECT * FROM retraits WHERE id = ?", (cible,))[0]
    if r["etat"] != "payee":
        return "ignore", "le retrait n'est pas versé"
    socid, porteur = tiers_fournisseur(ctx, db, r["porteur"], r["porteur_id"])
    fid = _premier_id(appel(ctx, "GET", "/supplierinvoices", params={"sqlfilters": _filtre("ref_ext", r["ref"]), "limit": 1}))
    if not fid:
        fid = int(appel(ctx, "POST", "/supplierinvoices", {"socid": socid, "ref_supplier": r["ref"], "ref_ext": r["ref"], "date": _date_ts(r["traite_le"]),
                                                            "lines": [{"desc": "Commissions de vente de billets — %s (%s)" % (porteur.get("nom") or porteur.get("scene"), r["ref"]), "qty": 1, "subprice": _eur(r["montant"]), "tva_tx": 0}]}))
    f = appel(ctx, "GET", "/supplierinvoices/%d" % fid) or {}
    if str(f.get("statut", f.get("status", "0"))) == "0":
        f = appel(ctx, "POST", "/supplierinvoices/%d/validate" % fid, {"idwarehouse": 0, "notrigger": 0}) or f
    if ctx.reglage("dolibarr_paiements"):
        deja = appel(ctx, "GET", "/supplierinvoices/%d/payments" % fid)
        if not (isinstance(deja, list) and deja):
            appel(ctx, "POST", "/supplierinvoices/%d/payments" % fid, {"datepaye": _date_ts(r["traite_le"]), "payment_mode_id": mode_id(ctx, "VIR"), "closepaidinvoices": "yes", "accountid": banque(ctx, "VIR"),
                                                                        "num_payment": str(r["reference_virement"] or r["ref"])[:60], "comment": "Versement %s" % r["ref"]})
    return "fait", json.dumps({"facture_fournisseur_id": fid, "facture_fournisseur": str(f.get("ref") or "")})


def type_membre(ctx):
    """Le type de membre « Artiste » : retrouvé, ou créé la première fois (il n'existe pas dans une instance neuve)."""
    for t in appel(ctx, "GET", "/memberstypes", params={"limit": 100}) or []:
        if isinstance(t, dict) and str(t.get("label")).strip().lower() == "artiste":
            return int(t["id"])
    return int(appel(ctx, "POST", "/memberstypes", {"label": "Artiste", "subscription": 0, "vote": 0, "morphy": ""}))


def ecrire_adherent(ctx, db, cible):
    a = db.lire("SELECT * FROM artistes WHERE id = ?", (cible,))[0]
    mid = a["dolibarr_adherent_id"] or _premier_id(appel(ctx, "GET", "/members", params={"sqlfilters": _filtre("ref_ext", a["ref"]), "limit": 1}))
    if not mid:
        socid, _ = tiers_fournisseur(ctx, db, "artiste", a["id"])
        nom = (a["legal"] or a["scene"]).strip().split(" ", 1)
        mid = int(appel(ctx, "POST", "/members", {"login": a["ref"].lower(), "morphy": "mor" if a["statut"] in ("Association", "Société") else "phy", "typeid": type_membre(ctx),
                                                   "firstname": nom[0] if len(nom) > 1 else "", "lastname": nom[1] if len(nom) > 1 else nom[0], "societe": a["scene"] if a["statut"] != "Particulier" else "",
                                                   "email": a["mail"], "phone": a["tel"], "address": a["adresse"], "zip": a["code_postal"], "town": a["ville"], "country_code": a["pays"] or "FR",
                                                   "datefin": _date_ts(a["adhesion_fin"] + " 00:00:00") if a["adhesion_fin"] else None, "public": 0, "fk_soc": socid, "ref_ext": a["ref"]}))
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
    if not str(ctx.reglage("dolibarr_url") or "").strip() or not ctx.reglage("dolibarr_cle"):
        raise ValueError("renseignez l'adresse de l'API et la clé de Dolibarr dans les réglages du pont")
    etat = appel(ctx, "GET", "/status") or {}
    societe = appel(ctx, "GET", "/setup/company") or {}
    banques = appel(ctx, "GET", "/bankaccounts", params={"limit": 100}) or []
    modes = appel(ctx, "GET", "/setup/dictionary/payment_types", params={"limit": 200}) or []
    taux = appel(ctx, "GET", "/setup/dictionary/vat", params={"limit": 50}) or []
    succes = etat.get("success", {}) if isinstance(etat, dict) else {}
    bq = [{"id": int(b["id"]), "ref": b.get("ref"), "libelle": b.get("label")} for b in banques if isinstance(b, dict) and b.get("id") is not None]
    md = [{"id": int(m["id"]), "code": m.get("code"), "libelle": m.get("label") or m.get("libelle")} for m in modes if isinstance(m, dict) and m.get("id") is not None]
    ids_banques = {b["id"] for b in bq}
    codes = {str(m["code"]).upper() for m in md}
    points = [{"libelle": "Dolibarr répond avec cette clé", "ok": True, "detail": "version %s" % succes.get("dolibarr_version", "?")},
              {"libelle": "La société est renseignée", "ok": bool(societe.get("name")), "detail": societe.get("name") or "renseignez la société dans Dolibarr (Configuration › Société)"}]
    for code, lib in (("CB", "carte"), ("LIQ", "espèces"), ("VIR", "virement")):
        b = int(ctx.reglage(BANQUES[code]) or 0)
        points.append({"libelle": "Mode de paiement « %s » (%s) existe" % (code, lib), "ok": code in codes, "detail": "" if code in codes else "créez-le dans Dolibarr (Configuration › Dictionnaires › Types de paiement)"})
        points.append({"libelle": "Compte bancaire des règlements %s choisi" % lib, "ok": b in ids_banques, "detail": "compte n° %d" % b if b in ids_banques else "choisissez-le dans les réglages du pont (comptes : %s)" % (", ".join("%d %s" % (x["id"], x["libelle"]) for x in bq) or "aucun")})
    return {"ok": all(p["ok"] for p in points), "version": succes.get("dolibarr_version"), "societe": {k: societe.get(k) for k in ("name", "country_code", "idprof1", "tva_intra", "address", "zip", "town", "email")},
            "comptes_bancaires": bq, "modes_de_paiement": md, "taux_de_tva": [{"taux": t.get("taux"), "libelle": t.get("note") or t.get("code")} for t in taux if isinstance(t, dict)], "points": points}


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
# CN : tout ce fichier est du nexus : PontErreur, http_reel, appel, _eur, _filtre, _premier_id, tiers_client, tiers_divers …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
