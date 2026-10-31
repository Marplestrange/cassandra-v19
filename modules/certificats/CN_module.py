# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Certificats TLS
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : certificats
# ZONE       : CN
# VERSION CN : 0.2.0  #cd918b
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Certificats TLS : ce que les visiteurs voient, et combien d'émissions il reste.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=cd918b ▼▼▼
"""Certificats TLS : ce que les visiteurs voient, et combien d'émissions il reste.

Porté de la V18 (`_ssl_probe`, `ssl_quota_state`, `_ssl_quota_note`, `_cert_sonde_jours`), avec ses leçons :
  - le certificat SERVI sur le port 443 fait foi : la base d'un panneau peut affirmer n'importe quoi (« expires » y est une DURÉE de validité, pas une date) ;
  - « sans certificat » ne se dit que sur constat de la sonde : un hôte qu'on n'a pas pu joindre est INCONNU, il n'est pas « sans » ;
  - Let's Encrypt compte cinq certificats par semaine et par domaine enregistré : on compte les émissions ABOUTIES (un échec pour une autre raison ne bloque
    pas les suivantes), et on dit quand le quota se libère ;
  - on ne harcèle pas : une lecture par hôte et par heure, sans dépasser un budget de temps.
Le renouvellement se fait par le panneau (fastpanel.ssl_renouveler, qui émet fastpanel.certificat_renouvele) ; ce module tient le registre et la veille.
"""
from __future__ import annotations

import socket
import ssl
import time
from datetime import datetime, timezone

LIMITE_SEMAINE = 5
FENETRE_S = 7 * 24 * 3600
BUDGET_S = 540


def nom_hote(d):
    d = (d or "").strip().lower()
    for p in ("http://", "https://"):
        if d.startswith(p):
            d = d[len(p):]
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d


def domaine_enregistre(domaine):
    p = [x for x in nom_hote(domaine).strip(".").split(".") if x]
    if len(p) < 2:
        return ""
    if len(p) >= 3 and len(p[-1]) == 2 and p[-2] in ("co", "com", "org", "net", "gov", "ac"):
        return ".".join(p[-3:])
    return ".".join(p[-2:])


def lire_certificat(hote, delai):
    """{jours, echeance, emetteur, noms} du certificat servi, ou {erreur}. Jamais une exception."""
    try:
        c = ssl.create_default_context()
        with socket.create_connection((hote, 443), timeout=delai) as brut:
            with c.wrap_socket(brut, server_hostname=hote) as tls:
                cert = tls.getpeercert()
    except (OSError, ssl.SSLError, ValueError) as ex:
        return {"erreur": str(ex)[:160]}
    fin = cert.get("notAfter", "")
    if not fin:
        return {"erreur": "le certificat ne dit pas son échéance"}
    d = datetime.strptime(fin, "%b %d %H:%M:%S %Y %Z")
    emetteur = next((v for champ in (cert.get("issuer") or ()) for k, v in champ if k == "organizationName"), "")
    return {"jours": (d - datetime.now(timezone.utc).replace(tzinfo=None)).days, "echeance": d.strftime("%Y-%m-%d"), "emetteur": emetteur,
            "noms": [v for k, v in (cert.get("subjectAltName") or ()) if k == "DNS"]}


def brancher(ctx):
    db = ctx.stockage

    def entier(nom, defaut):
        try:
            return int(ctx.reglage(nom, "") or defaut)
        except (TypeError, ValueError):
            return defaut

    def hotes():
        s = {nom_hote(x.get("domaine")) for x in (ctx.executer_lecture("fastpanel.sites") or [])}
        s |= {nom_hote(x) for x in str(ctx.reglage("hotes", "") or "").split(",") if x.strip()}
        return sorted(x for x in s if x and "." in x)

    # ------------------------------------------------------------------ le quota
    def quota_de(domaine):
        d = domaine_enregistre(domaine) or nom_hote(domaine)
        depuis = time.time() - FENETRE_S
        lignes = db.lire("SELECT ts FROM emissions WHERE domaine=? AND ok=1 AND ts>=? ORDER BY ts", (d, depuis))
        utilisees = len(lignes)
        libre = ""
        if utilisees >= LIMITE_SEMAINE:
            libre = datetime.fromtimestamp(lignes[utilisees - LIMITE_SEMAINE]["ts"] + FENETRE_S).strftime("%d/%m/%Y à %H:%M")
        return {"domaine": d, "utilisees": utilisees, "restantes": max(0, LIMITE_SEMAINE - utilisees), "limite": LIMITE_SEMAINE, "bloque": utilisees >= LIMITE_SEMAINE, "libre_le": libre}

    def emission(c):
        """Les émissions faites par le panneau, lues dans le journal du bus : on ne dépend pas de ce module (il peut être absent ou débranché),
        et un événement n'est compté qu'une fois grâce au curseur."""
        curseur = db.lire("SELECT valeur FROM curseur WHERE cle='evenement'")
        dernier = int(curseur[0]["valeur"]) if curseur else 0
        neufs = sorted((e for e in ctx.evenements("fastpanel.certificat_renouvele", 500) if e["id"] > dernier), key=lambda e: e["id"])
        for e in neufs:
            domaine = nom_hote((e.get("donnees") or {}).get("domaine") or "")
            if domaine:
                db.ecrire("INSERT INTO emissions(ts, domaine, ok, acteur) VALUES (?,?,1,?)", (e["ts"], domaine_enregistre(domaine) or domaine, str(e.get("acteur") or "")[:60]))
                c.emettre("certificat.renouvele", objet=("certificat", domaine), donnees={"domaine": domaine})
        if neufs:
            db.ecrire("INSERT INTO curseur(cle, valeur) VALUES ('evenement', ?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur", (str(neufs[-1]["id"]),))

    # ------------------------------------------------------------------ la sonde
    def sonde(c):
        emission(c)
        debut = time.time()
        delai = entier("delai_s", 5)
        seuil = entier("seuil_jours", 21)
        for h in hotes():
            if time.time() - debut > BUDGET_S:
                break
            r = lire_certificat(h, delai)
            avant = c.lire("certificat", h, portee=c.TOUT)
            if "erreur" in r:
                c.poser("certificat", h, h, etat="inconnu", donnees={"erreur": r["erreur"], "mesure": time.time()})        # on n'a pas pu le lire : ni « sans », ni « ok »
                continue
            etat = "echu" if r["jours"] <= 0 else ("proche" if r["jours"] <= seuil else "valide")
            c.poser("certificat", h, h, etat=etat, donnees=dict(r, mesure=time.time(), erreur=""))
            if etat in ("echu", "proche") and (not avant or avant["etat"] not in ("echu", "proche")):
                c.emettre("certificat.proche_expiration", objet=("certificat", h), donnees={"hote": h, "jours": r["jours"], "echeance": r["echeance"]})

    def det_expiration(c):
        sortie = []
        for o in c.lister(portee=c.TOUT, type="certificat"):
            if o["etat"] not in ("echu", "proche"):
                continue
            q = quota_de(o["id"])
            note = ("Quota Let's Encrypt épuisé pour %s : libre le %s." % (q["domaine"], q["libre_le"])) if q["bloque"] else ("Il reste %d émission(s) cette semaine pour %s." % (q["restantes"], q["domaine"]))
            sortie.append({"objet": ("certificat", o["id"]), "titre": ("Certificat échu : %s" % o["id"]) if o["etat"] == "echu" else "Certificat de %s : %d jour(s)" % (o["id"], o["donnees"]["jours"]),
                           "detail": "échéance le %s. %s" % (o["donnees"]["echeance"], note), "niveau": "critique" if o["etat"] == "echu" or o["donnees"]["jours"] < 7 else "attention"})
        return sortie

    # ------------------------------------------------------------------ lectures
    def relire(c, hote=""):
        h = nom_hote(hote)
        if "." not in h or " " in h or "/" in h:
            raise ValueError("nom d'hôte invalide")
        return dict(lire_certificat(h, entier("delai_s", 5)), hote=h)

    def etat(c):
        return {"certificats": [dict(o["donnees"], hote=o["id"], etat=o["etat"]) for o in c.lister(portee=c.TOUT, type="certificat")]}

    def quota(c, domaine=""):
        if not nom_hote(domaine):
            raise ValueError("domaine requis")
        return quota_de(domaine)

    def seuil(c):
        """Le seuil d'alerte, tel que CE module le tient : les autres modules (fastpanel) le LISENT ici, ils n'en gardent pas un second."""
        return {"jours": entier("seuil_jours", 21), "defaut": 21}

    def jours_de(quand):
        """Le nombre de jours entre aujourd'hui et une date « AAAA-MM-JJ… » (négatif : dépassée) ; None si elle est illisible."""
        s = str(quand or "")[:10]
        try:
            t = time.mktime(time.strptime(s, "%Y-%m-%d"))
        except Exception:
            return None
        return int(round((t - time.mktime(time.strptime(time.strftime("%Y-%m-%d"), "%Y-%m-%d"))) / 86400))

    def item_jour(bande, quoi, titre, detail="", nat="", ref="", poids=0, ou="", geste=("Ouvrir", "ouvrir")):
        return {"bande": bande, "quoi": quoi, "titre": str(titre or "")[:160], "detail": str(detail or "")[:200], "nat": nat, "ref": str(ref or ""), "poids": int(poids), "ou": ou,
                "geste": list(geste) if geste else None}

    def signal_jour(c):
        """Les certificats qui expirent dans les 21 jours (la machine : administrateur seulement)."""
        out = []
        for o in c.lister(portee=c.TOUT, type="certificat"):
            d = o["donnees"].get("jours")
            if not isinstance(d, int) or d < 0 or d > 21:
                continue
            out.append(item_jour("brule" if d <= 7 else "regarder", "ssl", o["id"], "Certificat : %d jour(s)." % d, "site", o["id"], 200 - d, "sites", geste=("Voir le site", "ouvrir")))
        return {"items": out}

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.moteur("sonde", sonde)
    c.moteur("emission", emission)
    c.detecteur("expiration_proche", det_expiration)
    c.implementer("relire_expiration", relire)
    c.implementer("etat", etat)
    c.implementer("signal_jour", signal_jour)
    c.implementer("quota", quota)
    c.implementer("seuil", seuil)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : nom_hote, domaine_enregistre, lire_certificat, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
