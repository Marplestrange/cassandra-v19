# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #4c793e
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : PayPal et HelloAsso, en pages de paiement hébergées chez eux (comme Stripe : Cassandra ne voit jamais une carte).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=4c793e ▼▼▼
"""Billetterie : PayPal et HelloAsso, en pages de paiement hébergées chez eux (comme Stripe : Cassandra ne voit jamais une carte).

Ni l'un ni l'autre n'est cru sur la parole de l'acheteur : au retour, la billetterie interroge le prestataire AVEC ses propres identifiants et ne livre que si
  - le paiement est bien terminé chez lui (PayPal : la capture de l'ordre réussit ; HelloAsso : l'intention de paiement porte une commande réglée) ;
  - l'ordre ou l'intention est celui qu'on a créé pour CETTE commande (un acheteur ne peut pas présenter le paiement d'une autre) ;
  - le montant payé égale EXACTEMENT le total de la commande.
Le transport (`HTTP`) se remplace dans les bancs : on ne parle pas à un vrai prestataire depuis un banc. D'après les documentations publiques de PayPal (Orders v2) et de HelloAsso
(API v5, checkout-intents) ; non éprouvé contre les services réels : à essayer en bac à sable avant de s'y fier.
"""
from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request

HTTP = {}                       # « paypal », « helloasso » : une fonction (methode, url, entetes, corps_octets_ou_None, delai) -> (code, dict)
URL_PAYPAL = {False: "https://api-m.paypal.com", True: "https://api-m.sandbox.paypal.com"}
URL_HELLOASSO = {False: "https://api.helloasso.com", True: "https://api.helloasso-sandbox.com"}


def http_reel(methode, url, entetes, corps, delai=20):
    req = urllib.request.Request(url, data=corps, headers=entetes, method=methode)
    try:
        with urllib.request.urlopen(req, timeout=delai) as r:
            brut = r.read().decode("utf-8") or "{}"
            return r.status, json.loads(brut)
    except urllib.error.HTTPError as ex:
        try:
            return ex.code, json.loads(ex.read().decode("utf-8") or "{}")
        except ValueError:
            return ex.code, {}
    except (urllib.error.URLError, OSError) as ex:
        raise RuntimeError("le prestataire est injoignable : %s" % ex)


def _appel(nom, methode, url, entetes, corps=None):
    code, rep = (HTTP.get(nom) or http_reel)(methode, url, entetes, corps, 20)
    return code, (rep if isinstance(rep, dict) else {})


def _montant(cts):
    return "%d.%02d" % (int(cts) // 100, int(cts) % 100)


def _refuse(nom, code, rep):
    msg = rep.get("message") or rep.get("error_description") or rep.get("error")
    d = rep.get("details")
    if not msg and isinstance(d, list) and d and isinstance(d[0], dict):
        msg = d[0].get("description") or d[0].get("issue")
    raise RuntimeError("%s a refusé la demande (%d) : %s" % (nom, code, msg or "sans détail"))


# ── PayPal ───────────────────────────────────────────────────────────────────
def paypal_regle(ctx) -> bool:
    return bool(ctx.reglage("paypal_actif") and ctx.reglage("paypal_client_id") and ctx.reglage("paypal_secret"))


def _paypal_base(ctx):
    return URL_PAYPAL[bool(ctx.reglage("paypal_sandbox"))]


def paypal_jeton(ctx) -> str:
    id_ = "%s:%s" % (ctx.reglage("paypal_client_id"), ctx.reglage("paypal_secret"))
    code, rep = _appel("paypal", "POST", _paypal_base(ctx) + "/v1/oauth2/token", {"Authorization": "Basic " + base64.b64encode(id_.encode()).decode(), "Content-Type": "application/x-www-form-urlencoded"},
                       urllib.parse.urlencode({"grant_type": "client_credentials"}).encode())
    if code != 200 or not rep.get("access_token"):
        _refuse("PayPal", code, rep)
    return rep["access_token"]


def paypal_creer(ctx, cmd, evt, retour, annulation) -> dict:
    """L'ordre PayPal : UNE ligne au montant exact. Rend {id, url}."""
    jeton = paypal_jeton(ctx)
    corps = {"intent": "CAPTURE", "purchase_units": [{"reference_id": cmd["ref"], "custom_id": cmd["ref"], "description": ("Billets · %s" % evt["nom"])[:120], "amount": {"currency_code": "EUR", "value": _montant(cmd["total"])}}],
             "payment_source": {"paypal": {"experience_context": {"return_url": retour, "cancel_url": annulation, "user_action": "PAY_NOW", "shipping_preference": "NO_SHIPPING", "brand_name": (ctx.reglage("titulaire_nom") or "Billetterie")[:127]}}}}
    code, rep = _appel("paypal", "POST", _paypal_base(ctx) + "/v2/checkout/orders", {"Authorization": "Bearer " + jeton, "Content-Type": "application/json", "PayPal-Request-Id": cmd["ref"]}, json.dumps(corps).encode())
    if code not in (200, 201) or not rep.get("id"):
        _refuse("PayPal", code, rep)
    lien = [x.get("href") for x in rep.get("links", []) if x.get("rel") in ("payer-action", "approve")]
    if not lien:
        raise RuntimeError("PayPal n'a pas rendu de page de paiement")
    return {"id": rep["id"], "url": lien[0]}


def paypal_capturer(ctx, ordre, cmd) -> dict:
    """Capture l'ordre APPROUVÉ par l'acheteur et vérifie référence et montant. Rend {ok, reference, detail}."""
    jeton = paypal_jeton(ctx)
    code, rep = _appel("paypal", "POST", _paypal_base(ctx) + "/v2/checkout/orders/%s/capture" % urllib.parse.quote(str(ordre), safe=""), {"Authorization": "Bearer " + jeton, "Content-Type": "application/json", "PayPal-Request-Id": "capture-" + cmd["ref"]}, b"{}")
    if code == 422 and any(d.get("issue") == "ORDER_ALREADY_CAPTURED" for d in (rep.get("details") or [])):
        code, rep = _appel("paypal", "GET", _paypal_base(ctx) + "/v2/checkout/orders/%s" % urllib.parse.quote(str(ordre), safe=""), {"Authorization": "Bearer " + jeton})
    if code not in (200, 201):
        return {"ok": False, "detail": "PayPal n'a pas confirmé le paiement (%d)" % code}
    unite = (rep.get("purchase_units") or [{}])[0]
    cap = ((unite.get("payments") or {}).get("captures") or [{}])[0]
    if rep.get("status") != "COMPLETED" or cap.get("status") != "COMPLETED":
        return {"ok": False, "detail": "paiement non terminé chez PayPal (%s)" % (cap.get("status") or rep.get("status"))}
    if unite.get("reference_id") != cmd["ref"] and unite.get("custom_id") != cmd["ref"]:
        return {"ok": False, "detail": "cet ordre PayPal n'est pas celui de cette commande"}
    montant = cap.get("amount") or {}
    if montant.get("currency_code") != "EUR" or montant.get("value") != _montant(cmd["total"]):
        return {"ok": False, "detail": "montant payé %s %s ≠ total de la commande %s : rien n'est livré" % (montant.get("value"), montant.get("currency_code"), _montant(cmd["total"]))}
    return {"ok": True, "reference": str(cap.get("id") or ordre), "detail": ""}


# ── HelloAsso ────────────────────────────────────────────────────────────────
def helloasso_regle(ctx) -> bool:
    return bool(ctx.reglage("helloasso_actif") and ctx.reglage("helloasso_client_id") and ctx.reglage("helloasso_secret") and ctx.reglage("helloasso_organisation"))


def _hello_base(ctx):
    return URL_HELLOASSO[bool(ctx.reglage("helloasso_sandbox"))]


def helloasso_jeton(ctx) -> str:
    code, rep = _appel("helloasso", "POST", _hello_base(ctx) + "/oauth2/token", {"Content-Type": "application/x-www-form-urlencoded"},
                       urllib.parse.urlencode({"client_id": ctx.reglage("helloasso_client_id"), "client_secret": ctx.reglage("helloasso_secret"), "grant_type": "client_credentials"}).encode())
    if code != 200 or not rep.get("access_token"):
        _refuse("HelloAsso", code, rep)
    return rep["access_token"]


def _slug(ctx):
    return urllib.parse.quote(str(ctx.reglage("helloasso_organisation")).strip(), safe="")


def helloasso_creer(ctx, cmd, evt, retour, annulation) -> dict:
    jeton = helloasso_jeton(ctx)
    nom = (cmd.get("nom") or "").strip().split(" ", 1)
    corps = {"totalAmount": int(cmd["total"]), "initialAmount": int(cmd["total"]), "itemName": ("Billets · %s" % evt["nom"])[:250], "backUrl": annulation, "errorUrl": annulation, "returnUrl": retour,
             "containsDonation": False, "metadata": {"commande": cmd["ref"]}}
    if cmd.get("mail"):
        corps["payer"] = {"firstName": nom[0][:80] if nom and nom[0] else "", "lastName": nom[1][:80] if len(nom) > 1 else "", "email": cmd["mail"]}
    code, rep = _appel("helloasso", "POST", _hello_base(ctx) + "/v5/organizations/%s/checkout-intents" % _slug(ctx), {"Authorization": "Bearer " + jeton, "Content-Type": "application/json"}, json.dumps(corps).encode())
    if code not in (200, 201) or not rep.get("id") or not rep.get("redirectUrl"):
        _refuse("HelloAsso", code, rep)
    return {"id": str(rep["id"]), "url": rep["redirectUrl"]}


def helloasso_verifier(ctx, intention, cmd) -> dict:
    """L'intention de paiement créée pour la commande porte-t-elle une commande réglée, au bon montant ? Rend {ok, reference, detail}."""
    jeton = helloasso_jeton(ctx)
    code, rep = _appel("helloasso", "GET", _hello_base(ctx) + "/v5/organizations/%s/checkout-intents/%s" % (_slug(ctx), urllib.parse.quote(str(intention), safe="")), {"Authorization": "Bearer " + jeton})
    if code != 200:
        return {"ok": False, "detail": "HelloAsso n'a pas pu confirmer le paiement (%d)" % code}
    meta = rep.get("metadata") or {}
    if meta.get("commande") and meta.get("commande") != cmd["ref"]:
        return {"ok": False, "detail": "cette intention de paiement n'est pas celle de cette commande"}
    ordre = rep.get("order")
    if not ordre:
        return {"ok": False, "detail": "paiement pas encore terminé chez HelloAsso"}
    total = (ordre.get("amount") or {}).get("total")
    if total is None:
        total = sum(int((x.get("amount") or 0)) for x in ordre.get("items") or [])
    if int(total) != int(cmd["total"]):
        return {"ok": False, "detail": "montant payé %s ≠ total de la commande %s : rien n'est livré" % (total, cmd["total"])}
    return {"ok": True, "reference": str(ordre.get("id") or intention), "detail": ""}
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : http_reel, _appel, _montant, _refuse, paypal_regle, _paypal_base, paypal_jeton, paypal_creer …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
