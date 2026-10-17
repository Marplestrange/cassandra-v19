# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module Sites
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sites
# ZONE       : CN
# VERSION CN : 0.1.1  #027b54
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module Sites.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=027b54 ▼▼▼
"""Le module Sites.

Ce qu'il tient de la V18 (sites, site_pass, site_fiche, site_history/availability, demandes, accords, liens) et les leçons qu'il garde :
  - la sonde CHRONOMÈTRE : un site qui répond 200 en huit secondes est en panne pour ses visiteurs ; le code seul ne suffit pas ;
  - le certificat se lit sur le port 443, pas dans la base : l'observation fait foi (au plus une fois par heure et par site) ;
  - un site n'est jugé qu'à sa TRANSITION (en ligne -> hors ligne), jamais à son état : la première observation est une découverte ;
  - un site qu'on ne mesure plus depuis deux jours n'entre plus dans les disponibilités (il n'a pas 100 % : il n'a pas de mesure) ;
  - chaque compte ne voit que ses sites ; l'administrateur voit l'état de tous, jamais le contenu (administrer n'est pas voir) ;
  - un site du panneau ne se déclare pas à la main : il appartient à son propriétaire du panneau, l'administrateur l'attribue ;
  - un site appartient à UN compte ; pour en changer, on transfère.

Les sites d'un compte sont : ceux qu'il a déclarés ici, ceux que l'administrateur lui a attribués, ceux inscrits dans sa fiche (module comptes, champ « sites »)
et ceux du panneau dont le propriétaire est le compte du panneau lié à sa fiche (« fp_account »). Les deux derniers se lisent, ils ne s'écrivent pas ici.
"""
from __future__ import annotations

import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

RE_DOMAINE = re.compile(r"^(?=.{4,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$")
SYSTEME = ("cassandra", "itare", "noyau", "operateur")
GENRES_LIEN = ("project", "contact", "machine", "note")
GESTES_ACCORD = ("restaurer", "supprimer", "transferer", "migrer")
RE_GESTE = re.compile(r"^[a-z][a-z0-9_]{1,31}$")
SUIVI_J = 2                     # un site sans mesure depuis ce nombre de jours n'entre plus dans les disponibilités
CERT_REFRAICHI_S = 3600
BUDGET_SONDE_S = 240


def nom_hote(d):
    d = (d or "").strip().lower()
    for p in ("http://", "https://"):
        if d.startswith(p):
            d = d[len(p):]
    d = d.split("/")[0]
    return d[4:] if d.startswith("www.") else d


def _sonder_http(domaine, delai):
    """(code, ms, erreur). Interroge le site et le chronomètre."""
    url = "https://%s/" % nom_hote(domaine)
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "Cassandra/site-check"})
        with urllib.request.urlopen(req, timeout=delai) as r:
            r.read(2048)
            return r.getcode(), int((time.time() - t0) * 1000), ""
    except urllib.error.HTTPError as ex:
        return ex.code, int((time.time() - t0) * 1000), ""
    except Exception as ex:
        return None, int((time.time() - t0) * 1000), str(ex)[:200]


def _cert_jours(domaine, delai):
    """Jours avant l'échéance du certificat SERVI, ou None si on ne sait pas le lire."""
    try:
        c = ssl.create_default_context()
        with socket.create_connection((nom_hote(domaine), 443), timeout=delai) as brut:
            with c.wrap_socket(brut, server_hostname=nom_hote(domaine)) as tls:
                fin = tls.getpeercert().get("notAfter")
        if not fin:
            return None
        return int((datetime.strptime(fin, "%b %d %H:%M:%S %Y %Z") - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() // 86400)
    except Exception:
        return None


def duree_texte(minutes):
    m = int(minutes or 0)
    if m < 1:
        return "moins d'une minute"
    if m < 120:
        return "%d min" % m
    return "%d h %02d" % (m // 60, m % 60) if m < 2880 else "%d jours" % (m // 1440)


def brancher(ctx):
    db = ctx.stockage
    dr = ctx.droits()

    # ------------------------------------------------------------------ réglages
    def entier(nom, defaut):
        try:
            return int(ctx.reglage(nom, "") or defaut)
        except (TypeError, ValueError):
            return defaut

    # ------------------------------------------------------------------ qui est qui
    def systeme(compte):
        return not compte or compte in SYSTEME

    def admin(compte):
        return systeme(compte) or dr.est_admin(compte)

    def comptes_connus():
        """[{compte, sites, fp_account}] d'après le module des comptes ; None s'il est absent (rien n'est alors vérifiable)."""
        r = ctx.executer_lecture("comptes.lister")
        return None if r is None else r.get("comptes", [])

    def panneau():
        """Les sites du panneau (module fastpanel), ou None s'il est absent ou muet : on le dit, on ne devine pas."""
        return ctx.executer_lecture("fastpanel.sites")

    # ------------------------------------------------------------------ la portée
    def portee(compte):
        """{domaine: {origine, comptes, panneau}} des sites que CE compte voit. L'administrateur voit l'état de tous."""
        tout = admin(compte)
        carte = {}

        def ajouter(d, origine, qui, pan=None):
            d = nom_hote(d)
            if not d:
                return
            e = carte.setdefault(d, {"origine": origine, "comptes": [], "panneau": None})
            if qui and qui not in e["comptes"]:
                e["comptes"].append(qui)
            if pan is not None:
                e["panneau"] = pan
                e["origine"] = "panneau"
        for r in db.lire("SELECT domaine, compte, origine FROM sites"):
            if tout or r["compte"] == compte:
                ajouter(r["domaine"], r["origine"], r["compte"])
        cs = comptes_connus() or []
        liens = {}
        for c in cs:
            for d in c.get("sites") or []:
                if tout or c["compte"] == compte:
                    ajouter(d, "compte", c["compte"])
            if c.get("fp_account"):
                liens.setdefault(str(c["fp_account"]).lower(), []).append(c["compte"])
        pan = panneau()
        for s in pan or []:
            proprietaires = liens.get(str(s.get("proprietaire") or "").lower(), [])
            if tout or compte in proprietaires:
                ajouter(s["domaine"], "panneau", None, s)
                for o in proprietaires:
                    if o not in carte[nom_hote(s["domaine"])]["comptes"]:
                        carte[nom_hote(s["domaine"])]["comptes"].append(o)
        return carte, pan is not None

    def dans(compte, domaine):
        """Le domaine est-il dans la portée du compte (lui-même ou un sous-domaine d'un de ses sites) ?"""
        d = nom_hote(domaine)
        if admin(compte):
            return d
        carte, _ = portee(compte)
        for s in carte:
            if d == s or d.endswith("." + s):
                return s if d == s else d
        return None

    def exiger_portee(compte, domaine):
        d = nom_hote(domaine)
        if not d or not RE_DOMAINE.match(d):
            raise ValueError("nom de domaine invalide")
        if not admin(compte) and not dans(compte, d):
            raise ValueError("site hors de ta portée")
        return d

    def noter(acteur, verbe, domaine, detail=""):
        db.ecrire("INSERT INTO journal(ts, acteur, verbe, domaine, detail) VALUES (?,?,?,?,?)", (time.time(), acteur or "?", verbe, nom_hote(domaine), str(detail)[:300]))

    def proprietaire_actuel(domaine):
        """Les comptes qui ont déjà ce site (déclaré, attribué, ou inscrit dans leur fiche)."""
        d = nom_hote(domaine)
        pris = {r["compte"] for r in db.lire("SELECT compte FROM sites WHERE domaine=?", (d,))}
        for c in comptes_connus() or []:
            if d in [nom_hote(x) for x in (c.get("sites") or [])]:
                pris.add(c["compte"])
        return pris

    def site_du_panneau(domaine):
        d = nom_hote(domaine)
        return any(nom_hote(s["domaine"]) == d for s in (panneau() or []))

    # ------------------------------------------------------------------ la sonde
    def derniere_mesure(d):
        r = db.lire("SELECT ts, code, ms, up, ssl_jours, erreur FROM mesures WHERE domaine=? ORDER BY id DESC LIMIT 1", (d,))
        return r[0] if r else None

    def tous_les_domaines():
        d = {nom_hote(r["domaine"]) for r in db.lire("SELECT domaine FROM sites")}
        for c in comptes_connus() or []:
            d |= {nom_hote(x) for x in (c.get("sites") or [])}
        d |= {nom_hote(s["domaine"]) for s in (panneau() or [])}
        return sorted(x for x in d if RE_DOMAINE.match(x))

    def sonde(c):
        delai = entier("delai_sonde_s", 8)
        debut = time.time()
        doms = tous_les_domaines()
        derniers = {r["domaine"]: r["t"] for r in db.lire("SELECT domaine, MAX(ts) t FROM mesures GROUP BY domaine")}
        doms.sort(key=lambda x: derniers.get(x, 0))                      # les moins récemment mesurés d'abord : un budget épuisé tourne
        vus = {r["domaine"]: (r["up"], r["depuis"]) for r in db.lire("SELECT domaine, up, depuis FROM etat_vu")}
        for d in doms:
            if time.time() - debut > BUDGET_SONDE_S:
                break
            code, ms, erreur = _sonder_http(d, delai)
            up = 1 if (code is not None and 200 <= int(code) < 400) else 0
            avant = derniere_mesure(d)
            if avant and avant["ssl_jours"] is not None and time.time() - avant["ts"] < CERT_REFRAICHI_S:
                jours = avant["ssl_jours"]
            else:
                jours = _cert_jours(d, delai)
            maintenant = time.time()
            db.ecrire("INSERT INTO mesures(ts, domaine, code, ms, up, ssl_jours, erreur) VALUES (?,?,?,?,?,?,?)", (maintenant, d, code, ms, up, jours, erreur))
            connu = vus.get(d)
            if connu is None:
                db.ecrire("INSERT OR REPLACE INTO etat_vu(domaine, up, depuis, ts) VALUES (?,?,?,?)", (d, up, maintenant, maintenant))
                db.ecrire("INSERT INTO evenements_site(ts, domaine, genre, detail) VALUES (?,?,?,?)",
                          (maintenant, d, "decouverte", "Première observation — %s (HTTP %s, %d ms)" % ("en ligne" if up else "hors ligne", code, ms)))
            elif connu[0] != up:
                minutes = int((maintenant - connu[1]) // 60)
                db.ecrire("INSERT OR REPLACE INTO etat_vu(domaine, up, depuis, ts) VALUES (?,?,?,?)", (d, up, maintenant, maintenant))
                if up:
                    db.ecrire("INSERT INTO evenements_site(ts, domaine, genre, detail, duree_min) VALUES (?,?,?,?,?)",
                              (maintenant, d, "retour", "De nouveau en ligne après %s (HTTP %s, %d ms)." % (duree_texte(minutes), code, ms), minutes))
                    c.emettre("site.retour", objet=("site", d), donnees={"domaine": d, "duree_min": minutes, "ms": ms})
                else:
                    db.ecrire("INSERT INTO evenements_site(ts, domaine, genre, detail, duree_min) VALUES (?,?,?,?,?)",
                              (maintenant, d, "panne", "Injoignable — %s" % (erreur or "HTTP %s" % code), minutes))
                    c.emettre("site.panne", objet=("site", d), donnees={"domaine": d, "code": code, "erreur": erreur})
            c.poser("site", d, d, etat="en_ligne" if up else "hors_ligne",
                    donnees={"code": code, "ms": ms, "ssl_jours": jours, "erreur": erreur, "mesure": maintenant})
        limite = time.time() - entier("retention_j", 90) * 86400
        db.ecrire("DELETE FROM mesures WHERE ts < ?", (limite,))
        db.ecrire("DELETE FROM evenements_site WHERE ts < ?", (limite,))

    def objets_site(c, etat=None):
        return c.lister(portee=c.TOUT, type="site", etat=etat or "")

    def det_panne(c):
        return [{"objet": ("site", o["id"]), "titre": "Site hors ligne : %s" % o["id"], "detail": o["donnees"].get("erreur") or ("code %s" % o["donnees"].get("code"))}
                for o in objets_site(c, "hors_ligne")]

    def det_lenteur(c):
        seuil = entier("lent_ms", 3000)
        return [{"objet": ("site", o["id"]), "titre": "Site lent : %s (%d ms)" % (o["id"], o["donnees"]["ms"]),
                 "detail": "le code HTTP est bon, mais pour un visiteur c'est déjà lent (au-delà de %d ms)" % seuil}
                for o in objets_site(c, "en_ligne") if (o["donnees"].get("ms") or 0) >= seuil]

    def det_certificat(c):
        seuil = entier("ssl_court_j", 21)
        sortie = []
        for o in objets_site(c):
            j = o["donnees"].get("ssl_jours")
            if isinstance(j, int) and j < seuil:
                sortie.append({"objet": ("site", o["id"]), "titre": "Certificat de %s : %d jour(s)" % (o["id"], j),
                               "detail": "renouvellement urgent" if j < 7 else "à renouveler avant l'échéance"})
        return sortie

    def det_demandes(c):
        return [{"objet": ("site", r["domaine"]), "titre": "Adossement demandé : %s" % r["domaine"], "detail": "%s demande que ce site passe au panneau. %s" % (r["compte"], r["message"])}
                for r in db.lire("SELECT domaine, compte, message FROM demandes WHERE statut='ouverte'")]

    # ------------------------------------------------------------------ lectures
    def disponibilites(jours, domaines=None):
        depuis = time.time() - jours * 86400
        suivi = time.time() - SUIVI_J * 86400
        lignes = db.lire("SELECT domaine, COUNT(*) n, SUM(up) u, AVG(CASE WHEN up=1 THEN ms END) moy, MAX(CASE WHEN up=1 THEN ms END) mx, MAX(ts) dernier "
                         "FROM mesures WHERE ts >= ? GROUP BY domaine ORDER BY domaine", (depuis,))
        pannes = {r["domaine"]: (r["n"], r["m"]) for r in db.lire("SELECT domaine, COUNT(*) n, COALESCE(SUM(duree_min),0) m FROM evenements_site WHERE genre='retour' AND ts >= ? GROUP BY domaine", (depuis,))}
        sortie, plus_suivis = [], []
        for r in lignes:
            if domaines is not None and r["domaine"] not in domaines:
                continue
            if r["dernier"] < suivi:
                plus_suivis.append(r["domaine"])
                continue
            n, m = pannes.get(r["domaine"], (0, 0))
            sortie.append({"domaine": r["domaine"], "mesures": r["n"], "disponibilite": round(100.0 * (r["u"] or 0) / r["n"], 2), "reponse_moy_ms": int(r["moy"]) if r["moy"] is not None else None,
                           "reponse_max_ms": int(r["mx"]) if r["mx"] is not None else None, "pannes": n, "indisponible_min": m, "indisponible": duree_texte(m)})
        return sortie, plus_suivis

    def vigilances(lignes, tout, demandes):
        vig = []
        for d in demandes:
            if tout:
                vig.append({"niveau": "regarder", "site": d["domaine"], "titre": "%s : adossement demandé par %s" % (d["domaine"], d["compte"]), "detail": d["message"] or "sans message", "geste": "repondre_demande", "demande": d["id"]})
            else:
                vig.append({"niveau": "info", "site": d["domaine"], "titre": "%s : demande d'adossement en attente" % d["domaine"], "detail": "", "geste": None})
        for x in lignes:
            d = x["domaine"]
            if x["up"] is False:
                vig.append({"niveau": "panne", "site": d, "titre": "%s ne répond pas" % d, "detail": ("code %s" % x["code"]) if x["code"] else "délai dépassé", "geste": None})
            j = x["ssl_jours"]
            if isinstance(j, int):
                if j < 7:
                    vig.append({"niveau": "panne", "site": d, "titre": "certificat de %s : %d jour(s)" % (d, j), "detail": "renouvellement urgent", "geste": None})
                elif j < entier("ssl_court_j", 21):
                    vig.append({"niveau": "regarder", "site": d, "titre": "certificat de %s : %d jours" % (d, j), "detail": "à renouveler avant l'échéance", "geste": None})
            if x["source"] != "panneau" and not x["demande"]:
                vig.append({"niveau": "info", "site": d, "titre": "%s : hors panneau" % d, "detail": "suivi à la main : sonde, historique et journal seulement", "geste": "attribuer" if tout else "demander"})
        ordre = {"panne": 0, "regarder": 1, "info": 2}
        vig.sort(key=lambda v: (ordre.get(v["niveau"], 9), v["site"]))
        return vig

    def vue(c):
        compte = c.compte
        tout = admin(compte)
        carte, panneau_ok = portee(compte)
        dispo, _ = disponibilites(30, set(carte))
        dispo = {x["domaine"]: x for x in dispo}
        demandes = [dict(r) for r in db.lire("SELECT id, domaine, compte, message, ts FROM demandes WHERE statut='ouverte'" + ("" if tout else " AND compte=?"), () if tout else (compte,))]
        parsite = {r["domaine"]: r for r in demandes}
        lignes = []
        for d in sorted(carte):
            e = carte[d]
            m = derniere_mesure(d)
            p = e["panneau"] or {}
            lignes.append({"domaine": d, "source": e["origine"] if e["origine"] == "panneau" else "declare", "origine": e["origine"],
                           "up": bool(m["up"]) if m else None, "code": m["code"] if m else None, "ms": m["ms"] if m else None,
                           "ssl_jours": m["ssl_jours"] if m and m["ssl_jours"] is not None else (p.get("ssl") or {}).get("jours"), "ssl_etat": (p.get("ssl") or {}).get("etat"),
                           "php": p.get("php", ""), "proprietaire_panneau": p.get("proprietaire", ""), "mesure": m["ts"] if m else None,
                           "dispo30": dispo.get(d), "comptes": e["comptes"] if tout else None, "demande": parsite.get(d)})
        return {"sites": lignes, "vigilances": vigilances(lignes, tout, demandes),
                "portee": {"admin": tout, "compte": compte, "sites": len(lignes), "panneau": sum(1 for x in lignes if x["source"] == "panneau"),
                           "declares": sum(1 for x in lignes if x["source"] != "panneau"), "panneau_lu": panneau_ok}}

    def historique(c, domaine, heures=24):
        d = exiger_portee(c.compte, domaine)
        h = max(1, min(int(heures or 24), 24 * 90))
        depuis = time.time() - h * 3600
        pts = db.lire("SELECT ts, code, ms, up, ssl_jours, erreur FROM mesures WHERE domaine=? AND ts >= ? ORDER BY ts", (d, depuis))
        ev = db.lire("SELECT ts, genre, detail, duree_min FROM evenements_site WHERE domaine=? AND ts >= ? ORDER BY ts DESC LIMIT 100", (d, depuis))
        tps = [p["ms"] for p in pts if p["up"] and p["ms"] is not None]
        return {"domaine": d, "heures": h, "mesures": len(pts), "disponibilite": round(100.0 * sum(1 for p in pts if p["up"]) / len(pts), 2) if pts else None,
                "reponse_moy_ms": int(sum(tps) / len(tps)) if tps else None, "reponse_max_ms": max(tps) if tps else None,
                "points": [dict(p, up=bool(p["up"])) for p in pts], "evenements": ev}

    def disponibilite(c, jours=30):
        carte, _ = portee(c.compte)
        j = max(1, min(int(jours or 30), 365))
        sites, plus = disponibilites(j, set(carte))
        return {"jours": j, "sites": sites, "plus_suivis": plus,
                "raison": "" if sites else "Aucune mesure enregistrée — la sonde n'a pas encore tourné."}

    def serie(c, mesure="", depuis="", jusqu_a=""):
        """Les points de la sonde pour l'historique : une courbe PAR SITE de la portée du compte (l'administrateur voit l'état de tous, jamais leur contenu)."""
        import datetime as _dt
        def epoque(t, defaut):
            try:
                return _dt.datetime.strptime(str(t)[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S").replace(tzinfo=_dt.timezone.utc).timestamp()
            except ValueError:
                return defaut
        a, b = epoque(depuis, time.time() - 86400), epoque(jusqu_a, time.time())
        carte, _ = portee(c.compte)
        doms = set(carte)
        def heure(ts):
            return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        if mesure == "site_down":
            ev = [r for r in db.lire("SELECT ts, domaine FROM evenements_site WHERE genre='panne' AND ts BETWEEN ? AND ? ORDER BY ts", (a, b)) if r["domaine"] in doms]
            return {"series": [{"nom": "pannes", "points": [[heure(r["ts"]), 1] for r in ev]}]}
        colonne = {"site_up": "up * 100.0", "site_ms": "ms", "site_ssl": "ssl_jours"}.get(mesure)
        if not colonne:
            raise ValueError("mesure inconnue : « %s »" % mesure)
        cond = " AND up = 1" if mesure == "site_ms" else (" AND ssl_jours IS NOT NULL" if mesure == "site_ssl" else "")
        par = {}
        for r in db.lire("SELECT ts, domaine, %s AS v FROM mesures WHERE ts BETWEEN ? AND ?%s ORDER BY ts" % (colonne, cond), (a, b)):
            if r["domaine"] in doms and r["v"] is not None:
                par.setdefault(r["domaine"], []).append([heure(r["ts"]), r["v"]])
        return {"series": [{"nom": d, "points": p} for d, p in sorted(par.items())]}

    def journal(c, domaine="", limite=60):
        compte = c.compte
        lim = max(10, min(int(limite or 60), 600))
        if domaine:
            d = exiger_portee(compte, domaine)
            lignes = db.lire("SELECT ts, acteur, verbe, domaine, detail FROM journal WHERE domaine=? OR domaine LIKE ? ORDER BY id DESC LIMIT ?", (d, "%." + d, lim))
            ev = db.lire("SELECT ts, genre verbe, domaine, detail FROM evenements_site WHERE domaine=? ORDER BY id DESC LIMIT ?", (d, lim))
        else:
            carte, _ = portee(compte)
            doms = set(carte)
            lignes = [r for r in db.lire("SELECT ts, acteur, verbe, domaine, detail FROM journal ORDER BY id DESC LIMIT ?", (lim * 3,)) if admin(compte) or r["domaine"] in doms]
            ev = [r for r in db.lire("SELECT ts, genre verbe, domaine, detail FROM evenements_site ORDER BY id DESC LIMIT ?", (lim * 3,)) if admin(compte) or r["domaine"] in doms]
        toutes = [dict(r, source="geste") for r in lignes] + [dict(r, acteur="sonde", source="veille") for r in ev]
        toutes.sort(key=lambda x: x["ts"], reverse=True)
        return {"domaine": nom_hote(domaine), "lignes": toutes[:lim]}

    def liens(c, domaine):
        d = exiger_portee(c.compte, domaine)
        return {"domaine": d, "liens": db.lire("SELECT genre, ref, note, ts FROM liens WHERE domaine=? ORDER BY genre, ts", (d,))}

    def demandes(c, statut="ouverte"):
        tout = admin(c.compte)
        cond, args = [], []
        if statut:
            cond.append("statut=?")
            args.append(statut)
        if not tout:
            cond.append("compte=?")
            args.append(c.compte)
        return {"demandes": db.lire("SELECT id, ts, domaine, compte, message, statut, reponse, traite_par, traite_ts FROM demandes"
                                    + (" WHERE " + " AND ".join(cond) if cond else "") + " ORDER BY id DESC LIMIT 200", tuple(args))}

    def accord_valide(domaine, geste):
        r = db.lire("SELECT compte, jusqu_a FROM accords WHERE domaine=? AND geste=? AND jusqu_a > ? ORDER BY id DESC LIMIT 1", (nom_hote(domaine), geste, time.time()))
        return {"par": r[0]["compte"], "jusqu_a": r[0]["jusqu_a"]} if r else None

    def accord(c, domaine, geste="restaurer"):
        d = exiger_portee(c.compte, domaine)
        return {"domaine": d, "geste": geste, "accord": accord_valide(d, geste)}

    def fiche(c, domaine):
        compte = c.compte
        d = exiger_portee(compte, domaine)
        v = vue(c)
        ligne = next((x for x in v["sites"] if x["domaine"] == d), None)
        if ligne is None:
            raise ValueError("site hors de ta portée")
        carte, _ = portee(compte)
        tout = admin(compte)
        mien = compte in (carte.get(d, {}).get("comptes") or [])
        hors = ligne["source"] != "panneau"
        rows = db.lire("SELECT compte, origine FROM sites WHERE domaine=?", (d,))
        h = historique(c, d, 24)
        return {"domaine": d, "site": ligne, "mien": mien, "admin_autrui": bool(tout and not mien), "hors_panneau": hors,
                "histoire": {k: h[k] for k in ("disponibilite", "reponse_moy_ms", "reponse_max_ms", "mesures")} | {"evenements": h["evenements"][:8]},
                "liens": liens(c, d)["liens"], "journal": journal(c, d, 12)["lignes"], "demande": ligne["demande"],
                "accord": accord_valide(d, "restaurer"),
                "gestes": {"retirer": bool(rows and (mien or tout)), "attribuer": tout, "transferer": bool(tout and (rows or ligne["comptes"])),
                           "demander": bool(mien and not tout and hors and not ligne["demande"]), "accorder": bool(mien and not tout and not hors)}}

    # ------------------------------------------------------------------ gestes
    def valider_compte_cible(cible):
        cible = str(cible or "").strip().lower()
        if not cible or len(cible) > 120:
            raise ValueError("compte invalide")
        cs = comptes_connus()
        if cs is not None and cible not in {x["compte"] for x in cs}:
            raise ValueError("compte inconnu")
        return cible

    def declarer(c, domaine):
        compte = c.compte
        if systeme(compte):
            raise ValueError("un site se déclare au nom d'un compte")
        d = nom_hote(domaine)
        if not RE_DOMAINE.match(d):
            raise ValueError("nom de domaine invalide")
        if site_du_panneau(d):
            raise ValueError("ce site est géré par le panneau : c'est à l'administrateur de te l'attribuer")
        pris = proprietaire_actuel(d)
        if compte in pris:
            raise ValueError("déjà dans la liste de ce compte")
        if pris:
            raise ValueError("ce site appartient déjà à un autre compte")
        db.ecrire("INSERT INTO sites(domaine, compte, origine, cree, par) VALUES (?,?,?,?,?)", (d, compte, "declare", time.time(), compte))
        noter(compte, "declare", d)
        c.emettre("site.declare", objet=("site", d), donnees={"domaine": d, "compte": compte})
        return {"domaine": d, "compte": compte}

    def prouver_ligne(compte_voulu):
        def f(c, res):
            r = db.lire("SELECT compte FROM sites WHERE domaine=?", (res["domaine"],))
            return bool(r) and r[0]["compte"] == res.get(compte_voulu or "compte")
        return f

    def defaire_declarer(c, res):
        db.ecrire("DELETE FROM sites WHERE domaine=? AND compte=?", (res["domaine"], res["compte"]))
        noter(res["compte"], "declare_annule", res["domaine"])

    def retirer(c, domaine):
        compte = c.compte
        d = nom_hote(domaine)
        r = db.lire("SELECT compte, origine, cree, par FROM sites WHERE domaine=?", (d,))
        if not r:
            if d in {nom_hote(x) for cc in (comptes_connus() or []) for x in (cc.get("sites") or [])}:
                raise ValueError("ce site est inscrit dans la fiche d'un compte : il s'enlève là-bas")
            raise ValueError("site absent de la liste")
        if r[0]["compte"] != compte and not admin(compte):
            raise ValueError("ce site n'est pas à toi")
        if r[0]["origine"] == "attribue" and not admin(compte):
            raise ValueError("ce site t'a été attribué : seul l'administrateur le reprend")
        db.ecrire("DELETE FROM sites WHERE domaine=?", (d,))
        noter(compte, "retire", d, r[0]["compte"])
        c.emettre("site.retire", objet=("site", d), donnees={"domaine": d, "compte": r[0]["compte"]})
        return {"domaine": d, "compte": r[0]["compte"], "origine": r[0]["origine"], "cree": r[0]["cree"], "par": r[0]["par"]}

    def prouver_retire(c, res):
        return not db.lire("SELECT 1 FROM sites WHERE domaine=?", (res["domaine"],))

    def defaire_retire(c, res):
        db.ecrire("INSERT OR IGNORE INTO sites(domaine, compte, origine, cree, par) VALUES (?,?,?,?,?)", (res["domaine"], res["compte"], res["origine"], res["cree"], res["par"]))

    def attribuer(c, domaine, compte):
        d = nom_hote(domaine)
        if not RE_DOMAINE.match(d):
            raise ValueError("nom de domaine invalide")
        cible = valider_compte_cible(compte)
        pris = proprietaire_actuel(d)
        if pris and cible not in pris:
            raise ValueError("ce site est déjà à un autre compte : il se transfère, il ne s'attribue pas")
        if cible in pris:
            raise ValueError("ce site est déjà à ce compte")
        db.ecrire("INSERT INTO sites(domaine, compte, origine, cree, par) VALUES (?,?,?,?,?)", (d, cible, "attribue", time.time(), c.compte))
        noter(c.compte, "attribue", d, cible)
        c.emettre("site.attribue", objet=("site", d), donnees={"domaine": d, "compte": cible, "par": c.compte})
        return {"domaine": d, "compte": cible}

    def transferer(c, domaine, vers):
        d = nom_hote(domaine)
        cible = valider_compte_cible(vers)
        r = db.lire("SELECT compte, origine, cree, par FROM sites WHERE domaine=?", (d,))
        if not r:
            raise ValueError("ce site n'est ni déclaré ni attribué ici : il s'attribue, il ne se transfère pas")
        if r[0]["compte"] == cible:
            raise ValueError("ce site est déjà à ce compte")
        db.ecrire("UPDATE sites SET compte=?, origine='attribue', par=? WHERE domaine=?", (cible, c.compte, d))
        noter(c.compte, "transfere", d, "%s -> %s" % (r[0]["compte"], cible))
        c.emettre("site.transfere", objet=("site", d), donnees={"domaine": d, "de": r[0]["compte"], "vers": cible})
        return {"domaine": d, "vers": cible, "de": r[0]["compte"], "origine_avant": r[0]["origine"], "par_avant": r[0]["par"], "compte": cible}

    def defaire_transfert(c, res):
        db.ecrire("UPDATE sites SET compte=?, origine=?, par=? WHERE domaine=?", (res["de"], res["origine_avant"], res["par_avant"], res["domaine"]))

    def demander(c, domaine, message=""):
        compte = c.compte
        d = nom_hote(domaine)
        if systeme(compte):
            raise ValueError("une demande se fait au nom d'un compte")
        if compte not in proprietaire_actuel(d):
            raise ValueError("ce site n'est pas déclaré par ton compte")
        if site_du_panneau(d):
            raise ValueError("ce site est déjà géré par le panneau")
        msg = str(message or "").strip()[:500]
        ouverte = db.lire("SELECT id FROM demandes WHERE domaine=? AND statut='ouverte'", (d,))
        if ouverte:
            db.ecrire("UPDATE demandes SET message=?, ts=?, compte=? WHERE id=?", (msg, time.time(), compte, ouverte[0]["id"]))
            did = ouverte[0]["id"]
        else:
            did = db.ecrire("INSERT INTO demandes(ts, domaine, compte, message) VALUES (?,?,?,?)", (time.time(), d, compte, msg))
        noter(compte, "demande", d)
        c.emettre("site.demande", objet=("site", d), donnees={"domaine": d, "compte": compte, "demande": did})
        return {"id": did, "domaine": d, "reprise": bool(ouverte)}

    def prouver_demande(c, res):
        return bool(db.lire("SELECT 1 FROM demandes WHERE id=? AND statut='ouverte'", (res["id"],)))

    def defaire_demande(c, res):
        if not res.get("reprise"):
            db.ecrire("DELETE FROM demandes WHERE id=? AND statut='ouverte'", (res["id"],))

    def repondre_demande(c, id, decision, reponse=""):
        decision = "fait" if str(decision or "").lower().startswith("f") else "refusee"
        r = db.lire("SELECT id, domaine, compte FROM demandes WHERE id=? AND statut='ouverte'", (int(id),))
        if not r:
            raise ValueError("demande introuvable ou déjà traitée")
        db.ecrire("UPDATE demandes SET statut=?, reponse=?, traite_par=?, traite_ts=? WHERE id=?", (decision, str(reponse or "")[:500], c.compte, time.time(), r[0]["id"]))
        noter(c.compte, "adossement_" + ("fait" if decision == "fait" else "refuse"), r[0]["domaine"], r[0]["compte"])
        c.emettre("site.adossement", objet=("site", r[0]["domaine"]), donnees={"domaine": r[0]["domaine"], "compte": r[0]["compte"], "decision": decision})
        return {"id": r[0]["id"], "domaine": r[0]["domaine"], "compte": r[0]["compte"], "statut": decision}

    def prouver_reponse(c, res):
        return bool(db.lire("SELECT 1 FROM demandes WHERE id=? AND statut=?", (res["id"], res["statut"])))

    def defaire_reponse(c, res):
        if not db.lire("SELECT 1 FROM demandes WHERE domaine=? AND statut='ouverte'", (res["domaine"],)):
            db.ecrire("UPDATE demandes SET statut='ouverte', reponse='', traite_par='', traite_ts=NULL WHERE id=?", (res["id"],))

    def accorder(c, domaine, geste="restaurer", heures=24):
        compte = c.compte
        d = nom_hote(domaine)
        if compte not in proprietaire_actuel(d) and compte not in (portee(compte)[0].get(d, {}).get("comptes") or []):
            raise ValueError("ce site n'est pas à toi")
        geste = str(geste or "restaurer").strip().lower()
        if not RE_GESTE.match(geste):
            raise ValueError("geste invalide")
        h = max(1, min(int(heures or 24), 168))
        fin = time.time() + h * 3600
        aid = db.ecrire("INSERT INTO accords(ts, domaine, compte, geste, jusqu_a) VALUES (?,?,?,?,?)", (time.time(), d, compte, geste, fin))
        noter(compte, "accord", d, "%s %d h" % (geste, h))
        c.emettre("site.accord", objet=("site", d), donnees={"domaine": d, "geste": geste, "compte": compte, "jusqu_a": fin})
        return {"id": aid, "domaine": d, "geste": geste, "jusqu_a": fin}

    def prouver_accord(c, res):
        return accord_valide(res["domaine"], res["geste"]) is not None

    def defaire_accord(c, res):
        db.ecrire("DELETE FROM accords WHERE id=?", (res["id"],))

    def lier(c, domaine, genre, ref, note=""):
        d = exiger_portee(c.compte, domaine)
        if genre not in GENRES_LIEN:
            raise ValueError("type de lien inconnu (%s)" % ", ".join(GENRES_LIEN))
        r = str(ref or "").strip()
        if not r:
            raise ValueError("référence obligatoire")
        avant = db.lire("SELECT note, ts FROM liens WHERE domaine=? AND genre=? AND ref=?", (d, genre, r))
        db.ecrire("INSERT OR REPLACE INTO liens(domaine, genre, ref, note, ts) VALUES (?,?,?,?,?)", (d, genre, r, str(note or "")[:300], time.time()))
        noter(c.compte, "lien", d, "%s %s" % (genre, r))
        return {"domaine": d, "genre": genre, "ref": r, "note": str(note or "")[:300], "avant": avant[0] if avant else None}

    def prouver_lien(c, res):
        return bool(db.lire("SELECT 1 FROM liens WHERE domaine=? AND genre=? AND ref=?", (res["domaine"], res["genre"], res["ref"])))

    def defaire_lien(c, res):
        if res.get("avant"):
            db.ecrire("INSERT OR REPLACE INTO liens(domaine, genre, ref, note, ts) VALUES (?,?,?,?,?)", (res["domaine"], res["genre"], res["ref"], res["avant"]["note"], res["avant"]["ts"]))
        else:
            db.ecrire("DELETE FROM liens WHERE domaine=? AND genre=? AND ref=?", (res["domaine"], res["genre"], res["ref"]))

    def delier(c, domaine, genre, ref):
        d = exiger_portee(c.compte, domaine)
        r = db.lire("SELECT note, ts FROM liens WHERE domaine=? AND genre=? AND ref=?", (d, genre, str(ref or "").strip()))
        if not r:
            raise ValueError("lien introuvable")
        db.ecrire("DELETE FROM liens WHERE domaine=? AND genre=? AND ref=?", (d, genre, str(ref).strip()))
        noter(c.compte, "delie", d, "%s %s" % (genre, ref))
        return {"domaine": d, "genre": genre, "ref": str(ref).strip(), "note": r[0]["note"], "ts": r[0]["ts"]}

    def prouver_delie(c, res):
        return not db.lire("SELECT 1 FROM liens WHERE domaine=? AND genre=? AND ref=?", (res["domaine"], res["genre"], res["ref"]))

    def defaire_delie(c, res):
        db.ecrire("INSERT OR REPLACE INTO liens(domaine, genre, ref, note, ts) VALUES (?,?,?,?,?)", (res["domaine"], res["genre"], res["ref"], res["note"], res["ts"]))

    def prouver_attribue(c, res):
        r = db.lire("SELECT compte FROM sites WHERE domaine=?", (res["domaine"],))
        return bool(r) and r[0]["compte"] == res["compte"]

    def defaire_attribue(c, res):
        db.ecrire("DELETE FROM sites WHERE domaine=? AND compte=? AND origine='attribue'", (res["domaine"], res["compte"]))

    def prouver_transfert(c, res):
        r = db.lire("SELECT compte FROM sites WHERE domaine=?", (res["domaine"],))
        return bool(r) and r[0]["compte"] == res["vers"]

    # ------------------------------------------------------------------ inscription
    c = ctx
    c.moteur("sonde", sonde)
    c.detecteur("panne", det_panne)
    c.detecteur("lenteur", det_lenteur)
    c.detecteur("certificat_court", det_certificat)
    c.detecteur("adossement_demande", det_demandes)
    for cid, f in (("vue", vue), ("fiche", fiche), ("historique", historique), ("disponibilite", disponibilite), ("serie", serie), ("journal", journal), ("liens", liens), ("demandes", demandes), ("accord", accord)):
        c.implementer(cid, f)
    c.implementer("declarer", declarer, prouver_ligne("compte"), defaire_declarer, simuler=lambda x, domaine="", **_: "déclarerait %s au compte" % domaine)
    c.implementer("retirer", retirer, prouver_retire, defaire_retire, simuler=lambda x, domaine="", **_: "retirerait %s de la liste" % domaine)
    c.implementer("attribuer", attribuer, prouver_attribue, defaire_attribue, simuler=lambda x, domaine="", compte="", **_: "attribuerait %s à %s" % (domaine, compte))
    c.implementer("transferer", transferer, prouver_transfert, defaire_transfert, simuler=lambda x, domaine="", vers="", **_: "transférerait %s à %s" % (domaine, vers))
    c.implementer("demander", demander, prouver_demande, defaire_demande, simuler=lambda x, domaine="", **_: "demanderait l'adossement de %s au panneau" % domaine)
    c.implementer("repondre_demande", repondre_demande, prouver_reponse, defaire_reponse, simuler=lambda x, id="", decision="", **_: "fermerait la demande %s (%s)" % (id, decision))
    c.implementer("accorder", accorder, prouver_accord, defaire_accord, simuler=lambda x, domaine="", geste="restaurer", **_: "accorderait « %s » sur %s" % (geste, domaine))
    c.implementer("lier", lier, prouver_lien, defaire_lien, simuler=lambda x, domaine="", genre="", ref="", **_: "lierait %s %s à %s" % (genre, ref, domaine))
    c.implementer("delier", delier, prouver_delie, defaire_delie, simuler=lambda x, domaine="", genre="", ref="", **_: "délierait %s %s de %s" % (genre, ref, domaine))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : nom_hote, _sonder_http, _cert_jours, duree_texte, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
