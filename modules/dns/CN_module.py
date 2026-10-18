# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Domaines et DNS
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : dns
# ZONE       : CN
# VERSION CN : 0.2.0  #4b1631
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Domaines et DNS.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=4b1631 ▼▼▼
"""Domaines et DNS.

Porté de la V18 (`_dns_*`, `_detect_dns`, `_aut_dns_corriger`, `_dom_expiration`), avec ses leçons :
  - on interroge le serveur de noms FAISANT FOI (l'autoritaire), pas un cache : un cache périmé fait croire à une dérive qui n'existe pas ;
  - une référence VERSIONNÉE : accepter un changement pose une nouvelle version, rien n'est écrasé, le retour remet la précédente ;
  - la première relève d'une zone devient sa référence (rien à comparer avant) ;
  - l'adresse publique n'est crue que si DEUX services s'accordent ; elle change -> les A qui portaient l'ancienne sont à corriger ;
  - Cassandra ne corrige QUE un A existant, d'une zone suivie, non proxifié, vers l'adresse publique actuelle ; jamais un nom réservé, jamais le courrier
    (mail, smtp, _dmarc, DKIM relèvent du fournisseur de courrier) ; elle ne crée ni ne supprime, ne change pas le « proxifié » ;
  - l'écriture est PROUVÉE sur le serveur de noms (pas seulement acceptée par l'API) ;
  - les adresses Cloudflare sont normalisées (« <cloudflare> ») : derrière un proxy, l'adresse n'est pas celle du serveur ;
  - un domaine qui expire éteint tous ses sites d'un coup, sans erreur avant le jour J : surveillé par RDAP, une lecture par domaine et par jour.
Changements V19 : plus de `dig` (un client DNS en Python pur, UDP puis TCP si tronqué) ; une résolution qui ÉCHOUE n'est plus lue comme « enregistrement absent »
(un résolveur qui flanche ne doit pas déclencher une dérive) ; les noms réservés sont un réglage de l'administrateur, pas une liste codée.
"""
from __future__ import annotations

import base64
import ipaddress
import json
import os
import random
import re
import socket
import struct
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

TYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16, "AAAA": 28, "CAA": 257}
SELECTEURS_DKIM = ("dkim", "default", "mail", "selector1", "selector2", "s1", "s2", "google", "k1")
CLOUDFLARE = ("173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22", "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20",
              "188.114.96.0/20", "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/13", "104.24.0.0/14", "172.64.0.0/13", "131.0.72.0/22",
              "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32", "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29", "2c0f:f248::/32")
SERVICES_IP = ("https://api.ipify.org", "https://ipv4.icanhazip.com")
RE_NOM = re.compile(r"^(?:[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?\.)+[a-z]{2,24}$")
ETIQUETTES_COURRIER = ("mail", "smtp", "imap", "pop", "pop3", "mx", "webmail", "autodiscover")
PORT_DNS = 53
ATTENTE_PREUVE_S = 30
PAS_PREUVE_S = 5


# ------------------------------------------------------------------ un client DNS en Python pur
def construire(nom, typ):
    ident = random.randint(0, 65535)
    q = b"".join(bytes([len(p)]) + p.encode("ascii") for p in nom.strip(".").split(".")) + b"\x00"
    return ident, struct.pack(">HHHHHH", ident, 0x0100, 1, 0, 0, 0) + q + struct.pack(">HH", TYPES[typ], 1)


_point = None          # le point d'évolution `analyser`, posé par brancher() : interroger() n'a pas de ctx


def analyser(b, ident):
    """Rend (code de réponse, tronqué, [(type, valeur normalisée)]). Le décodage est un POINT D'ÉVOLUTION : points/EC_analyser.py."""
    if _point is None:
        raise RuntimeError("le module dns n'est pas branché : pas de point d'évolution")
    sortie = _point("analyser", {"reponse": base64.b64encode(bytes(b)).decode("ascii"), "ident": ident})
    if "erreur" in sortie:
        raise ValueError(sortie["erreur"])
    return sortie["rcode"], sortie["tronque"], [(x[0], x[1]) for x in sortie["enregistrements"]]


def interroger(nom, typ, serveur, delai=4.0):
    """Les valeurs d'un enregistrement, triées. [] : le serveur dit qu'il n'y en a pas. None : on n'a PAS pu le savoir (réseau, serveur muet, réponse illisible)."""
    if not RE_NOM.match(nom or "") or typ not in TYPES or not serveur:
        return None
    ident, req = construire(nom, typ)
    try:
        fam = socket.AF_INET6 if ":" in serveur else socket.AF_INET
        with socket.socket(fam, socket.SOCK_DGRAM) as s:
            s.settimeout(delai)
            s.sendto(req, (serveur, PORT_DNS))
            rep, _ = s.recvfrom(4096)
        rcode, tronque, rr = analyser(rep, ident)
        if tronque:
            with socket.create_connection((serveur, PORT_DNS), timeout=delai) as t:
                t.sendall(struct.pack(">H", len(req)) + req)
                n = struct.unpack(">H", t.recv(2))[0]
                tampon = b""
                while len(tampon) < n:
                    morceau = t.recv(n - len(tampon))
                    if not morceau:
                        return None
                    tampon += morceau
            rcode, _, rr = analyser(tampon, ident)
        if rcode not in (0, 3):                       # NOERROR, NXDOMAIN ; le reste (SERVFAIL, REFUSED) = on ne sait pas
            return None
        return sorted({v for t, v in rr if t == typ})
    except (OSError, ValueError, struct.error):
        return None


def resolveurs_systeme():
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            return [l.split()[1] for l in f if l.startswith("nameserver") and len(l.split()) > 1]
    except OSError:
        return []


def dom_enregistre(domaine):
    """Le domaine qu'on RENOUVELLE : « app.exemple.org » -> « exemple.org » ; « x.co.uk » -> « x.co.uk ». Le calcul est un POINT D'ÉVOLUTION : points/EC_dom_enregistre.py."""
    return _point("dom_enregistre", {"domaine": domaine})["valeur"]


def normaliser(typ, val):
    if typ in ("A", "AAAA"):
        try:
            ip = ipaddress.ip_address(val)
            if any(ip in ipaddress.ip_network(r) for r in CLOUDFLARE):
                return "<cloudflare>"
        except ValueError:
            pass
    return val.lower() if typ in ("MX", "CNAME", "NS") else val


def ip_publique():
    """L'adresse IPv4 publique vue de l'extérieur : deux services doivent s'accorder, sinon on ne dit rien."""
    vues = []
    for url in SERVICES_IP:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "curl/8"}), timeout=8) as r:
                v = r.read(64).decode().strip()
            if ipaddress.ip_address(v).version == 4:
                vues.append(v)
        except Exception:
            continue
    return vues[0] if len(vues) == 2 and vues[0] == vues[1] else ""


def expiration_rdap(domaine):
    """La date d'expiration (datetime UTC) lue par RDAP, ou None."""
    try:
        req = urllib.request.Request("https://rdap.org/domain/%s" % domaine, headers={"User-Agent": "Cassandra-Veille/1.0", "Accept": "application/rdap+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read(400000).decode("utf-8", "replace"))
        for ev in d.get("events") or []:
            if str(ev.get("eventAction")).lower() == "expiration":
                return datetime.strptime(str(ev.get("eventDate"))[:19], "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None
    return None


def brancher(ctx):
    global _point
    _point = ctx.point
    db = ctx.stockage
    memoire = {"exp_t": {}}

    def liste(nom):
        return {x.strip().lower() for x in str(ctx.reglage(nom, "") or "").split(",") if x.strip()}

    # ------------------------------------------------------------------ les zones suivies
    def hotes_panneau():
        r = ctx.executer_lecture("fastpanel.sites")
        return [str(s.get("domaine") or "").lower() for s in (r or [])]

    def domaines():
        d = {dom_enregistre(h) for h in hotes_panneau()} | {dom_enregistre(x) for x in liste("domaines")}
        return sorted(x for x in d if x)

    def protege(nom):
        """Pourquoi Cassandra ne touche JAMAIS à ce nom ('' si elle peut) : ce que l'administrateur a réservé, et le courrier."""
        nom = str(nom or "").lower().strip(".")
        if nom in liste("ne_pas_toucher"):
            return "« %s » est réservé par l'administrateur" % nom
        if dom_enregistre(nom) in liste("courrier_libre"):
            return ""
        etiquette = nom.split(".")[0]
        if etiquette in ETIQUETTES_COURRIER or etiquette.startswith("_dmarc") or "._domainkey." in nom:
            return "« %s » relève du courrier (géré par le fournisseur de courrier) : jamais touché" % nom
        return ""

    # ------------------------------------------------------------------ résolution
    def resolveurs():
        r = str(ctx.reglage("serveur_noms", "") or "").strip()
        return [r] if r else (resolveurs_systeme() or ["1.1.1.1"])

    def via_resolveur(nom, typ):
        for s in resolveurs():
            v = interroger(nom, typ, s)
            if v is not None:
                return v
        return None

    def autoritaire(dom):
        """(nom, ip) du serveur de noms faisant foi de la zone, ou ('', '') s'il est introuvable (on retombe alors sur le résolveur)."""
        for ns in via_resolveur(dom, "NS") or []:
            ips = via_resolveur(ns, "A") or []
            if ips:
                return ns, ips[0]
        return "", ""

    def serveur_pour(dom, ns_ip=None):
        return ns_ip or resolveurs()[0]

    def releve(dom, hotes):
        """({ 'nom|TYPE': [valeurs] }, [noms|TYPE non lus], serveur). Un nom sans enregistrement est ABSENT ; un nom qu'on n'a pas pu lire est INCONNU."""
        ns, ip = autoritaire(dom)
        serveur = ip or resolveurs()[0]
        noms = [(dom, t) for t in ("A", "AAAA", "MX", "TXT", "CAA")] + [("www." + dom, "A"), ("_dmarc." + dom, "TXT")]
        noms += [("%s._domainkey.%s" % (sel, dom), "TXT") for sel in SELECTEURS_DKIM]
        noms += [(h, t) for h in hotes for t in ("A", "AAAA", "CNAME")]
        rel, inconnus = {}, []
        for nom, t in dict.fromkeys(noms):
            v = interroger(nom, t, serveur)
            if v is None:
                inconnus.append("%s|%s" % (nom, t))
            elif v:
                rel["%s|%s" % (nom, t)] = sorted({normaliser(t, x) for x in v})
        return rel, inconnus, ns or serveur

    # ------------------------------------------------------------------ la référence versionnée
    def reference(dom):
        r = db.lire("SELECT id, contenu, ts, auteur FROM reference WHERE domaine=? AND annulee=0 ORDER BY id DESC LIMIT 1", (dom,))
        return (json.loads(r[0]["contenu"]), r[0]["id"]) if r else (None, 0)

    def reference_poser(dom, contenu, auteur):
        return db.ecrire("INSERT INTO reference(ts, domaine, contenu, auteur) VALUES (?,?,?,?)", (time.time(), dom, json.dumps(contenu, ensure_ascii=False, sort_keys=True), auteur[:60]))

    def valeur_etat(cle, defaut=""):
        r = db.lire("SELECT valeur FROM etat WHERE cle=?", (cle,))
        return r[0]["valeur"] if r else defaut

    def poser_etat(cle, valeur):
        db.ecrire("INSERT INTO etat(cle, valeur, ts) VALUES (?,?,?) ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur, ts=excluded.ts", (cle, str(valeur), time.time()))

    # ------------------------------------------------------------------ le moteur
    def calculer_derives(rel, inconnus, ref, ip_now, ip_ref):
        derives = []
        for cle in sorted(set(ref) | set(rel)):
            if cle in inconnus:
                continue                                       # on n'a pas pu lire ce nom : ni dérive ni conformité
            att, obs = ref.get(cle), rel.get(cle)
            nom, typ = cle.split("|")
            ip_derivee = bool(typ == "A" and ip_now and ip_ref and ip_now != ip_ref and att == [ip_ref] and obs == [ip_ref])
            if att == obs and not ip_derivee:
                continue
            derives.append({"cle": cle, "nom": nom, "type": typ, "attendu": att or [], "observe": obs or [], "ip_derivee": ip_derivee})
        return derives

    def moteur_releve(c):
        ip_now = ip_publique()
        ip_ref = valeur_etat("ip_reference")
        if ip_now and not ip_ref:
            poser_etat("ip_reference", ip_now)
            ip_ref = ip_now
        if ip_now:
            poser_etat("ip_actuelle", ip_now)
        hotes = hotes_panneau()
        seuil = int(ctx.reglage("expire_jours", 45) or 45)
        for dom in domaines():
            mine = [h for h in hotes if h == dom or h.endswith("." + dom)]
            rel, inconnus, serveur = releve(dom, mine)
            ref, _ = reference(dom)
            if not rel and not ref:
                continue
            if ref is None:
                reference_poser(dom, rel, "premier relevé")
                ref = rel
            avant = {d["cle"] for d in json.loads((db.lire("SELECT derives FROM releves WHERE domaine=?", (dom,)) or [{"derives": "[]"}])[0]["derives"])}
            derives = calculer_derives(rel, inconnus, ref, ip_now, ip_ref)
            db.ecrire("INSERT INTO releves(domaine, ts, contenu, serveur, derives) VALUES (?,?,?,?,?) ON CONFLICT(domaine) DO UPDATE SET ts=excluded.ts, contenu=excluded.contenu, "
                      "serveur=excluded.serveur, derives=excluded.derives", (dom, time.time(), json.dumps(rel, sort_keys=True), serveur, json.dumps(derives)))
            c.poser("domaine", dom, dom, etat="derive" if derives else "conforme", donnees={"derives": len(derives), "serveur": serveur, "inconnus": len(inconnus)})
            for d in derives:
                if d["cle"] not in avant:
                    c.emettre("dns.derive", objet=("dns", d["cle"]), donnees={"domaine": dom, "nom": d["nom"], "type": d["type"], "attendu": d["attendu"], "observe": d["observe"]})
            if time.time() - memoire["exp_t"].get(dom, 0) > 86400:
                memoire["exp_t"][dom] = time.time()
                exp = expiration_rdap(dom)
                if exp:
                    poser_etat("expiration:" + dom, exp.strftime("%Y-%m-%d"))
                    jours = (exp - datetime.now(timezone.utc).replace(tzinfo=None)).days
                    if jours <= seuil:
                        c.emettre("domaine.proche_expiration", objet=("domaine", dom), donnees={"domaine": dom, "jours": jours, "expiration": exp.strftime("%Y-%m-%d")})

    def det_derive(c):
        jeton = bool(str(ctx.reglage("jeton_cloudflare", "") or "").strip())
        ip_now = valeur_etat("ip_actuelle")
        sortie = []
        for r in db.lire("SELECT domaine, derives FROM releves"):
            for d in json.loads(r["derives"]):
                att, obs = ", ".join(d["attendu"]) or "absent", ", ".join(d["observe"]) or "absent"
                if d["ip_derivee"]:
                    if protege(d["nom"]):
                        continue                                # ce nom n'est pas à ce serveur : on ne propose rien dessus
                    if jeton:
                        sortie.append({"objet": ("dns", d["cle"]), "titre": "%s pointe encore sur l'ancienne adresse du serveur" % d["nom"],
                                       "detail": "L'adresse publique est passée de %s à %s ; %s (A) porte toujours %s." % (valeur_etat("ip_reference"), ip_now, d["nom"], att),
                                       "capacite": "corriger_enregistrement", "args": {"nom": d["nom"], "type": "A", "valeur": ip_now}})
                    else:
                        sortie.append({"objet": ("dns", d["cle"]), "titre": "%s pointe encore sur l'ancienne adresse du serveur" % d["nom"],
                                       "detail": "L'adresse publique est passée à %s ; %s (A) porte toujours %s. Pas de jeton Cloudflare (réglage dns.jeton_cloudflare) : à corriger chez le fournisseur." % (ip_now, d["nom"], att)})
                    continue
                sortie.append({"objet": ("dns", d["cle"]), "titre": "DNS : %s (%s) a changé" % (d["nom"], d["type"]),
                               "detail": "Référence : %s · observé : %s. Si c'est voulu, acceptez le changement (il devient la nouvelle référence) ; sinon, c'est à rétablir." % (att, obs)})
        return sortie

    def det_expiration(c):
        seuil = int(ctx.reglage("expire_jours", 45) or 45)
        sortie = []
        for r in db.lire("SELECT cle, valeur FROM etat WHERE cle LIKE 'expiration:%'"):
            dom = r["cle"].split(":", 1)[1]
            jours = (datetime.strptime(r["valeur"], "%Y-%m-%d") - datetime.now(timezone.utc).replace(tzinfo=None)).days
            if jours <= seuil:
                sortie.append({"objet": ("domaine", dom), "titre": "Le domaine %s expire dans %d jours" % (dom, max(jours, 0)),
                               "detail": "expire le %s (registre, par RDAP) : à renouveler chez le registraire, tous ses sites s'éteignent le jour dit" % r["valeur"],
                               "niveau": "critique" if jours <= 14 else "attention"})
        return sortie

    # ------------------------------------------------------------------ lectures
    def exiger_zone(dom):
        d = dom_enregistre(dom)
        if d not in domaines():
            raise ValueError("domaine non suivi : %s" % (dom or "?"))
        return d

    def relever_zone(c, domaine=""):
        d = exiger_zone(domaine)
        hotes = [h for h in hotes_panneau() if h == d or h.endswith("." + d)]
        rel, inconnus, serveur = releve(d, hotes)
        return {"domaine": d, "serveur": serveur, "enregistrements": rel, "non_lus": inconnus}

    def reference_lire(c, domaine="", historique=False):
        d = exiger_zone(domaine)
        if historique:
            return {"domaine": d, "versions": db.lire("SELECT id, ts, auteur, annulee FROM reference WHERE domaine=? ORDER BY id DESC LIMIT 50", (d,))}
        ref, vid = reference(d)
        return {"domaine": d, "version": vid, "contenu": ref}

    def etat(c):
        sortie = []
        for dom in domaines():
            r = db.lire("SELECT ts, serveur, derives FROM releves WHERE domaine=?", (dom,))
            sortie.append({"domaine": dom, "releve": r[0]["ts"] if r else None, "serveur": r[0]["serveur"] if r else "", "derives": json.loads(r[0]["derives"]) if r else [],
                           "expiration": valeur_etat("expiration:" + dom) or None, "version": reference(dom)[1]})
        return {"zones": sortie, "ip_publique": valeur_etat("ip_actuelle") or None, "ip_reference": valeur_etat("ip_reference") or None}

    # ------------------------------------------------------------------ accepter la référence
    def accepter_reference(c, domaine=""):
        d = exiger_zone(domaine)
        hotes = [h for h in hotes_panneau() if h == d or h.endswith("." + d)]
        rel, inconnus, _ = releve(d, hotes)
        if not rel:
            raise ValueError("relevé vide : rien n'est accepté")
        precedent = reference(d)[1]
        vid = reference_poser(d, rel, "accepté par %s" % (ctx.compte or "l'administrateur"))
        db.ecrire("UPDATE releves SET derives='[]' WHERE domaine=?", (d,))
        return {"domaine": d, "version": vid, "precedente": precedent}

    def prouver_acceptee(c, res):
        return reference(res["domaine"])[1] == res["version"]

    def defaire_acceptee(c, res):
        db.ecrire("UPDATE reference SET annulee=1 WHERE id=?", (res["version"],))

    # ------------------------------------------------------------------ corriger chez Cloudflare
    def cf(methode, chemin, corps=None):
        tok = str(ctx.reglage("jeton_cloudflare", "") or "").strip()
        if not tok:
            raise ValueError("pas de jeton Cloudflare (réglage dns.jeton_cloudflare)")
        base = str(ctx.reglage("api_cloudflare", "") or "https://api.cloudflare.com/client/v4").rstrip("/")
        req = urllib.request.Request(base + chemin, method=methode, data=(json.dumps(corps).encode() if corps is not None else None),
                                     headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json", "User-Agent": "Cassandra/19"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read(500000).decode("utf-8", "replace"))
        except urllib.error.HTTPError as ex:
            try:
                d = json.loads(ex.read(20000).decode("utf-8", "replace"))
            except Exception:
                d = {}
            raise ValueError("Cloudflare a refusé (%s) : %s" % (ex.code, str(((d.get("errors") or [{}])[0]).get("message") or "")[:120]))
        except Exception as ex:
            raise ValueError("Cloudflare injoignable : %s" % str(ex).replace(tok, "***")[:100])
        if not d.get("success"):
            raise ValueError("Cloudflare : %s" % str(d.get("errors"))[:150])
        return d.get("result")

    def corriger(c, nom="", type="A", valeur=""):
        nom = str(nom or "").lower().strip(".")
        dom = dom_enregistre(nom)
        if type != "A" or dom not in domaines() or not RE_NOM.match(nom):
            raise ValueError("enregistrement refusé : seuls les A des zones suivies se corrigent")
        if protege(nom):
            raise ValueError("refusé : %s" % protege(nom))
        try:
            ip = ipaddress.ip_address(str(valeur))
        except ValueError:
            raise ValueError("adresse illisible")
        actuelle = ip_publique() or valeur_etat("ip_actuelle")
        if ip.version != 4 or not actuelle or ip != ipaddress.ip_address(actuelle):
            raise ValueError("la valeur n'est pas l'adresse publique actuelle de ce serveur : rien n'est écrit")
        z = cf("GET", "/zones?name=%s" % dom)
        if not z:
            raise ValueError("zone introuvable chez Cloudflare : %s" % dom)
        zid = z[0]["id"]
        r = cf("GET", "/zones/%s/dns_records?type=A&name=%s" % (zid, nom))
        if not r:
            raise ValueError("aucun enregistrement A « %s » à corriger" % nom)
        rec = r[0]
        if rec.get("proxied"):
            raise ValueError("« %s » est proxifié : son adresse n'est pas celle du serveur, rien à corriger" % nom)
        cf("PUT", "/zones/%s/dns_records/%s" % (zid, rec["id"]), {"type": "A", "name": nom, "content": str(ip), "ttl": rec.get("ttl", 1), "proxied": False})
        return {"nom": nom, "domaine": dom, "zone": zid, "enregistrement": rec["id"], "ancien": rec.get("content"), "nouveau": str(ip), "ttl": rec.get("ttl", 1),
                "ip_reference_avant": valeur_etat("ip_reference"), "reference_avant": reference(dom)[1]}

    def prouver_corrige(c, res):
        """Le serveur de noms faisant foi doit rendre la nouvelle valeur ; alors la référence suit."""
        fin = time.time() + ATTENTE_PREUVE_S
        while True:
            _, ip = autoritaire(res["domaine"])
            if interroger(res["nom"], "A", ip or resolveurs()[0]) == [res["nouveau"]]:
                hotes = [h for h in hotes_panneau() if h == res["domaine"] or h.endswith("." + res["domaine"])]
                rel, _, _ = releve(res["domaine"], hotes)
                res["reference_posee"] = reference_poser(res["domaine"], rel, "correction %s" % res["nom"]) if rel else 0
                poser_etat("ip_reference", res["nouveau"])
                c.emettre("dns.corrige", objet=("dns", res["nom"] + "|A"), donnees={"nom": res["nom"], "de": res["ancien"], "a": res["nouveau"]})
                return True
            if time.time() >= fin:
                return False
            time.sleep(PAS_PREUVE_S)

    def defaire_corrige(c, res):
        cf("PUT", "/zones/%s/dns_records/%s" % (res["zone"], res["enregistrement"]), {"type": "A", "name": res["nom"], "content": res["ancien"], "ttl": res["ttl"], "proxied": False})
        if res.get("reference_posee"):
            db.ecrire("UPDATE reference SET annulee=1 WHERE id=?", (res["reference_posee"],))
        if res.get("ip_reference_avant"):
            poser_etat("ip_reference", res["ip_reference_avant"])

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.moteur("releve", moteur_releve)
    c.detecteur("derive_dns", det_derive)
    c.detecteur("domaine_expire", det_expiration)
    c.implementer("relever_zone", relever_zone)
    c.implementer("reference", reference_lire)
    c.implementer("etat", etat)
    c.implementer("accepter_reference", accepter_reference, prouver_acceptee, defaire_acceptee, simuler=lambda x, domaine="", **_: "poserait l'état observé de %s comme nouvelle référence" % domaine)
    c.implementer("corriger_enregistrement", corriger, prouver_corrige, defaire_corrige, simuler=lambda x, nom="", valeur="", **_: "corrigerait %s (A) vers %s chez Cloudflare" % (nom, valeur))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : construire, lire_nom, analyser, interroger, resolveurs_systeme, dom_enregistre, normaliser, ip_publique …
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
