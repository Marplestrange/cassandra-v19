# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Billetterie
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : billetterie
# ZONE       : CN
# VERSION CN : 0.1.0  #1fe86d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Billetterie : le prestataire de paiement Stripe (page de paiement hébergée, retour par webhook signé).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=1fe86d ▼▼▼
"""Billetterie : le prestataire de paiement Stripe (page de paiement hébergée, retour par webhook signé).

Cassandra ne voit jamais un numéro de carte : le client paie chez Stripe (page hébergée), et Stripe PRÉVIENT la billetterie par un webhook. Ce qui décide ici :
  - un webhook n'est cru que si sa signature (HMAC-SHA256 du secret, d'après la documentation de Stripe : en-tête `Stripe-Signature: t=<horodatage>,v1=<signature>`) est exacte et récente ;
  - un paiement n'est accepté que si le montant payé égale EXACTEMENT le total de la commande ;
  - un même événement reçu deux fois n'agit qu'une fois.
La construction de la page de paiement passe par `transport`, que les bancs remplacent : on ne parle pas à Stripe depuis un banc.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.stripe.com/v1/checkout/sessions"
TOLERANCE_S = 300


def transport(url: str, donnees: dict, cle: str, timeout: int = 15) -> dict:
    """POST d'un formulaire à l'API de Stripe, authentifié par la clé secrète. Rend le JSON de la réponse ou lève RuntimeError avec la phrase de Stripe."""
    req = urllib.request.Request(url, data=urllib.parse.urlencode(donnees).encode(), headers={"Authorization": "Bearer " + cle, "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as ex:
        try:
            msg = json.loads(ex.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        raise RuntimeError("Stripe a refusé la demande (%d) : %s" % (ex.code, msg or "sans détail"))
    except (urllib.error.URLError, OSError) as ex:
        raise RuntimeError("Stripe est injoignable : %s" % ex)


def creer_page_de_paiement(cle: str, commande: dict, evenement: dict, succes: str, annulation: str, http=None) -> dict:
    """Crée la page de paiement : UNE ligne au montant exact de la commande. Rend {id, url}."""
    donnees = {"mode": "payment", "success_url": succes, "cancel_url": annulation, "client_reference_id": commande["ref"],
               "line_items[0][quantity]": "1", "line_items[0][price_data][currency]": "eur", "line_items[0][price_data][unit_amount]": str(int(commande["total"])),
               "line_items[0][price_data][product_data][name]": ("Billets · %s" % evenement["nom"])[:120],
               "payment_intent_data[metadata][commande]": commande["ref"], "expires_at": str(int(time.time()) + 1800)}
    if commande.get("mail"):
        donnees["customer_email"] = commande["mail"]
    rep = (http or transport)(API, donnees, cle)
    if not rep.get("url") or not rep.get("id"):
        raise RuntimeError("Stripe n'a pas rendu de page de paiement")
    return {"id": rep["id"], "url": rep["url"]}


def verifier_signature(corps: bytes, entete: str, secret: str, maintenant: float) -> bool:
    """La signature d'un webhook Stripe : exacte (comparaison à temps constant) et récente (5 minutes)."""
    if not entete or not secret:
        return False
    parts = {}
    for p in str(entete).split(","):
        if "=" in p:
            k, v = p.split("=", 1)
            parts.setdefault(k.strip(), []).append(v.strip())
    try:
        t = int(parts.get("t", [""])[0])
    except ValueError:
        return False
    if abs(maintenant - t) > TOLERANCE_S:
        return False
    attendu = hmac.new(secret.encode("utf-8"), ("%d." % t).encode("utf-8") + corps, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(attendu, s) for s in parts.get("v1", []))


def signer(corps: bytes, secret: str, t: int) -> str:
    """Fabrique l'en-tête qu'enverrait Stripe (pour les bancs)."""
    return "t=%d,v1=%s" % (t, hmac.new(secret.encode("utf-8"), ("%d." % t).encode("utf-8") + corps, hashlib.sha256).hexdigest())
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : transport, creer_page_de_paiement, verifier_signature, signer
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
