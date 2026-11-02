# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le Centre de notifications, portée de la V18 (notif, notif_resoudre, notif_vu, notif_acqui
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : notifications
# ZONE       : CN
# VERSION CN : 0.3.0  #e3e3c9
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le Centre de notifications, portée de la V18 (notif, notif_resoudre, notif_vu, notif_acquitter, _nt_filtre_dest, _nt_expiration).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.3.0 empreinte=e3e3c9 ▼▼▼
"""Le Centre de notifications, portée de la V18 (notif, notif_resoudre, notif_vu, notif_acquitter, _nt_filtre_dest, _nt_expiration).

Ce qui change, et pourquoi :
  - la base est celle du MODULE (donnees/modules/notifications.db), plus une table au milieu de 169 ;
  - une notification liée à un détecteur n'a plus besoin d'une « sonde » rejouée pour savoir si elle tient encore : le constat se résout, la
    notification se referme avec lui ;
  - la gravité d'une notification n'est JAMAIS déduite de son titre (leçon de la V18 : un mot dans un titre déclenchait de fausses alertes de sécurité) ;
  - les canaux (courriel, Telegram, webhook, digest) ne sont pas ici : le module des canaux écoute « notification.emise ».
"""
import json
import re
import time

NIVEAUX = ("critique", "avoir", "info")
NATURES = ("etat", "evenement", "decision")
SYSTEME = ("cassandra", "itare", "noyau", "operateur")        # les comptes dont la vue n'est pas cloisonnée (comme « sans compte » en V18)
RE_SOURCE = re.compile(r"^[a-z][a-z0-9_]{1,30}$")
JOURS_INFO, JOURS_AUTRES = 7, 30


def brancher(ctx):
    db = ctx.stockage
    dr = ctx.droits()

    def gere(compte):
        return compte in SYSTEME or not compte or dr.raison(compte, "notifications.gerer")["accord"]

    def est_admin(compte):
        return dr.est_admin(compte)

    def normaliser(dest, defaut):
        """Les destinataires : « admins », ou des comptes. Une liste, ou un seul."""
        if dest in (None, "", []):
            return list(defaut)
        liste = [dest] if isinstance(dest, str) else list(dest)
        sortie = []
        for d in liste:
            d = str(d).strip().lower()
            if d and d not in sortie:
                sortie.append(d)
        if not sortie or len(sortie) > 20:
            raise ValueError("destinataires : de 1 à 20 (« admins » ou des comptes)")
        return sortie

    def visible(lecteur, dests):
        """Le cloisonnement : les comptes système voient tout ; un administrateur voit ce qui vise « admins » ou lui ; un compte, ce qui le vise."""
        if lecteur in SYSTEME or not lecteur:
            return True
        if lecteur in dests:
            return True
        return "admins" in dests and est_admin(lecteur)

    def ligne(r, lecteur):
        d = db.lire("SELECT vu_le, acquitte_le FROM notif_dest WHERE notif=? AND compte=?", (r["id"], lecteur))
        return {"id": r["id"], "ts": r["ts"], "maj": r["maj"], "source": r["source"], "niveau": r["niveau"], "titre": r["titre"], "corps": r["corps"],
                "cle": r["cle"], "n": r["n"], "sujet": r["sujet"], "nature": r["nature"], "destinataires": json.loads(r["destinataires"]),
                "resolue": bool(r["resolue"]), "resolue_le": r["resolue_le"], "resolue_par": r["resolue_par"],
                "lu": bool(d and d[0]["vu_le"]), "acquittee": bool(d and d[0]["acquitte_le"]), "auteur": r["auteur"], "provenance": r["provenance"]}

    def lire_une(nid):
        r = db.lire("SELECT * FROM notifs WHERE id=?", (nid,))
        return r[0] if r else None

    # ------------------------------------------------------------------ créer ou répéter
    def ecrire_notif(source, niveau, titre, corps, cle, sujet, nature, dests, auteur, provenance, expire_jours=0):
        if niveau not in NIVEAUX:
            raise ValueError("niveau : %s" % " | ".join(NIVEAUX))
        if nature not in NATURES:
            raise ValueError("nature : %s" % " | ".join(NATURES))
        if not RE_SOURCE.match(source or ""):
            raise ValueError("source : minuscules, chiffres et _ (2 à 31 caractères)")
        titre = (titre or "").strip()
        if not titre or len(titre) > 200:
            raise ValueError("titre : de 1 à 200 caractères")
        corps = (corps or "")[:2000]
        now = time.time()
        expire = now + (expire_jours or (JOURS_INFO if niveau == "info" else JOURS_AUTRES)) * 86400
        ouverte = db.lire("SELECT * FROM notifs WHERE cle=? AND resolue=0 AND supprimee=0", (cle,)) if cle else []
        if ouverte:                                   # la même panne qui se répète : on compte, on ne répète pas
            o = ouverte[0]
            avant = {"n": o["n"], "titre": o["titre"], "corps": o["corps"], "niveau": o["niveau"], "maj": o["maj"], "expire_le": o["expire_le"]}
            nouveau_niveau = niveau if NIVEAUX.index(niveau) < NIVEAUX.index(o["niveau"]) else o["niveau"]       # on ne baisse jamais la gravité en répétant
            db.ecrire("UPDATE notifs SET n=n+1, maj=?, titre=?, corps=?, niveau=?, expire_le=? WHERE id=?", (now, titre, corps, nouveau_niveau, expire, o["id"]))
            return {"id": o["id"], "repete": True, "avant": avant, "escalade": nouveau_niveau != o["niveau"]}
        nid = db.ecrire("INSERT INTO notifs(ts, maj, source, niveau, titre, corps, cle, sujet, nature, destinataires, expire_le, auteur, provenance) "
                        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (now, now, source, niveau, titre, corps, cle or "", sujet or "", nature, json.dumps(dests), expire, auteur, provenance))
        return {"id": nid, "repete": False, "avant": None, "escalade": False}

    def dire_emise(r, source, niveau, titre, dests, nature):
        if (not r["repete"]) or r["escalade"]:
            ctx.emettre("notification.emise", objet=("notification", r["id"]),
                        donnees={"id": r["id"], "source": source, "niveau": niveau, "titre": titre, "destinataires": dests, "nature": nature, "repetee": r["repete"]})

    def emettre(ctx, titre="", corps="", source="", niveau="avoir", sujet="", cle="", nature="evenement", dest=None, expire_jours=0):
        auteur = ctx.compte
        dests = normaliser(dest, ["admins"])
        if not gere(auteur) and any(d not in ("admins", auteur) for d in dests):
            raise PermissionError("viser un autre compte demande le droit notifications.gerer")
        r = ecrire_notif(source, niveau, titre, corps, cle, sujet, nature, dests, auteur, "capacite", int(expire_jours or 0))
        dire_emise(r, source, niveau, titre, dests, nature)
        return {"id": r["id"], "repete": r["repete"], "avant": r["avant"]}

    def prouver_emettre(ctx, res):
        return lire_une(res["id"]) is not None

    def defaire_emettre(ctx, res):
        if res["repete"]:
            a = res["avant"]
            db.ecrire("UPDATE notifs SET n=?, titre=?, corps=?, niveau=?, maj=?, expire_le=? WHERE id=?",
                      (a["n"], a["titre"], a["corps"], a["niveau"], a["maj"], a["expire_le"], res["id"]))
        else:
            db.ecrire("DELETE FROM notif_dest WHERE notif=?", (res["id"],))
            db.ecrire("DELETE FROM notifs WHERE id=?", (res["id"],))

    # ------------------------------------------------------------------ lire
    def lister(ctx, non_lues=False, source="", niveau="", resolues=False, limite=100):
        lecteur = ctx.compte
        rows = db.lire("SELECT * FROM notifs WHERE supprimee=0" + ("" if resolues else " AND resolue=0") +
                       (" AND source=?" if source else "") + (" AND niveau=?" if niveau else "") + " ORDER BY maj DESC LIMIT ?",
                       tuple(x for x in (source, niveau) if x) + (max(1, min(int(limite), 500)) * 3,))
        out = [ligne(r, lecteur) for r in rows if visible(lecteur, json.loads(r["destinataires"]))]
        if non_lues:
            out = [x for x in out if not x["lu"]]
        return {"notifications": out[:max(1, min(int(limite), 500))]}

    def compteurs(ctx):
        lecteur = ctx.compte
        vues = [ligne(r, lecteur) for r in db.lire("SELECT * FROM notifs WHERE supprimee=0 AND resolue=0")
                if visible(lecteur, json.loads(r["destinataires"]))]
        return {"ouvertes": len(vues), "non_lues": sum(1 for x in vues if not x["lu"]), "critiques": sum(1 for x in vues if x["niveau"] == "critique"),
                "a_decider": sum(1 for x in vues if x["nature"] == "decision" and not x["acquittee"])}

    # ------------------------------------------------------------------ lu / pris en compte, PAR PERSONNE
    def une_visible(nid, lecteur):
        r = lire_une(int(nid))
        if r is None or r["supprimee"] or not visible(lecteur, json.loads(r["destinataires"])):
            raise ValueError("notification inconnue : %s" % nid)
        return r

    def etat_dest(nid, compte):
        d = db.lire("SELECT vu_le, acquitte_le FROM notif_dest WHERE notif=? AND compte=?", (nid, compte))
        return {"vu_le": d[0]["vu_le"], "acquitte_le": d[0]["acquitte_le"]} if d else None

    def poser_dest(nid, compte, vu, acq):
        db.ecrire("INSERT INTO notif_dest(notif, compte, vu_le, acquitte_le) VALUES(?,?,?,?) "
                  "ON CONFLICT(notif, compte) DO UPDATE SET vu_le=excluded.vu_le, acquitte_le=excluded.acquitte_le", (nid, compte, vu, acq))

    def marquer(ctx, id=0, acquitter=False):
        c = ctx.compte
        if not c:
            raise ValueError("lu par qui ? aucun compte n'agit")
        une_visible(id, c)
        avant = etat_dest(int(id), c)
        now = time.time()
        poser_dest(int(id), c, (avant or {}).get("vu_le") or now, now if acquitter else (avant or {}).get("acquitte_le"))
        return {"id": int(id), "compte": c, "avant": avant, "apres": etat_dest(int(id), c)}

    def prouver_marque(ctx, res):
        return etat_dest(res["id"], res["compte"]) == res["apres"]

    def defaire_marque(ctx, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM notif_dest WHERE notif=? AND compte=?", (res["id"], res["compte"]))
        else:
            poser_dest(res["id"], res["compte"], res["avant"]["vu_le"], res["avant"]["acquitte_le"])

    # ------------------------------------------------------------------ résoudre, supprimer
    def trouver(id, cle):
        if id:
            r = lire_une(int(id))
            return r
        r = db.lire("SELECT * FROM notifs WHERE cle=? AND resolue=0 AND supprimee=0", (cle,)) if cle else []
        return r[0] if r else None

    def resoudre(ctx, id=0, cle=""):
        c = ctx.compte
        r = trouver(id, cle)
        if r is None or r["supprimee"]:
            raise ValueError("notification inconnue")
        if not gere(c) and not visible(c, json.loads(r["destinataires"])):
            raise PermissionError("cette notification ne vous est pas destinée")
        if r["resolue"]:
            return {"id": r["id"], "etait": True}
        db.ecrire("UPDATE notifs SET resolue=1, resolue_le=?, resolue_par=? WHERE id=?", (time.time(), c or "noyau", r["id"]))
        ctx.emettre("notification.resolue", objet=("notification", r["id"]), donnees={"id": r["id"], "cle": r["cle"], "par": c})
        return {"id": r["id"], "etait": False}

    def prouver_resolue(ctx, res):
        return bool(lire_une(res["id"])["resolue"])

    def defaire_resolue(ctx, res):
        if not res["etait"]:
            db.ecrire("UPDATE notifs SET resolue=0, resolue_le=NULL, resolue_par='' WHERE id=?", (res["id"],))

    def supprimer(ctx, id=0):
        c = ctx.compte
        r = une_visible(id, c)
        if not gere(c) and "admins" in json.loads(r["destinataires"]) and c not in json.loads(r["destinataires"]) and not est_admin(c):
            raise PermissionError("cette notification ne vous est pas destinée")
        db.ecrire("UPDATE notifs SET supprimee=1 WHERE id=?", (int(id),))
        ctx.emettre("notification.supprimee", objet=("notification", int(id)), donnees={"id": int(id), "par": c})
        return {"id": int(id)}

    def prouver_supprimee(ctx, res):
        return bool(lire_une(res["id"])["supprimee"])

    def defaire_supprimee(ctx, res):
        db.ecrire("UPDATE notifs SET supprimee=0 WHERE id=?", (res["id"],))

    # ------------------------------------------------------------------ les moteurs : les constats des détecteurs
    def constats_ouverts(ctx, ev):
        d = ev["donnees"]
        cle = "%s.%s:%s:%s" % (ev["source"], d.get("detecteur", ""), ev["objet_type"], ev["objet_id"])
        niveau = d.get("niveau") if d.get("niveau") in NIVEAUX else "avoir"          # JAMAIS déduit du titre
        dests = [ev["compte"]] if ev.get("compte") else ["admins"]
        r = ecrire_notif(re.sub(r"[^a-z0-9_]", "_", ev["source"].lower())[:31] or "noyau", niveau, d.get("titre", cle), d.get("detail", ""), cle,
                         "%s:%s" % (ev["objet_type"], ev["objet_id"]), "etat", dests, "noyau", "constat")
        dire_emise(r, ev["source"], niveau, d.get("titre", cle), dests, "etat")

    def droits_prevenus(ctx, ev):
        d = ev["donnees"]
        if not d.get("prevenir") or d.get("sujet_type") != "compte":
            return
        n = len(d.get("changes") or [])
        corps = "%d droit(s) réglé(s) sur votre compte" % n if n else ""
        if d.get("admin"):
            corps += (" ; " if corps else "") + ("vous êtes désormais administrateur" if d["admin"][1] else "vous n'êtes plus administrateur")
        r = ecrire_notif("droits", "avoir", "Vos droits ont changé", corps, "droits:%s:%s" % (d["sujet"], ev["id"]), "compte:%s" % d["sujet"],
                         "evenement", [d["sujet"]], ev.get("compte") or "noyau", "evenement")
        dire_emise(r, "droits", "avoir", "Vos droits ont changé", [d["sujet"]], "evenement")

    def constats_resolus(ctx, ev):
        cle = ev["donnees"].get("cle", "")
        r = db.lire("SELECT id FROM notifs WHERE cle=? AND resolue=0 AND supprimee=0", (cle,)) if cle else []
        if r:
            db.ecrire("UPDATE notifs SET resolue=1, resolue_le=?, resolue_par='constat' WHERE id=?", (time.time(), r[0]["id"]))
            ctx.emettre("notification.resolue", objet=("notification", r[0]["id"]), donnees={"id": r[0]["id"], "cle": cle, "par": "constat"})

    def expirer(ctx):
        now = time.time()
        vieux = [r["id"] for r in db.lire("SELECT id FROM notifs WHERE expire_le IS NOT NULL AND expire_le<?", (now,))]
        for nid in vieux:
            db.ecrire("DELETE FROM notif_dest WHERE notif=?", (nid,))
            db.ecrire("DELETE FROM notifs WHERE id=?", (nid,))

    ctx.moteur("constats_ouverts", constats_ouverts)
    ctx.moteur("droits_prevenus", droits_prevenus)
    ctx.moteur("constats_resolus", constats_resolus)
    ctx.moteur("expirer", expirer)
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

    def signal_jour(ctx):
        """Les lignes de la cloche qui attendent MA décision : elles brûlent tant qu'elles sont ouvertes. Ce que les agents font seuls ne brûle pas sur le bureau d'un humain : seul un critique remonte."""
        out = []
        for n in lister(ctx, limite=100)["notifications"]:
            if n["nature"] != "decision" or n["resolue"]:
                continue
            if n["source"] in ("proactivite", "autotache") and n["niveau"] != "critique":
                continue
            out.append(item_jour("brule", "decision", n["titre"], "%s — attend votre décision." % n["source"], "decision", n["id"], 85, "cloche", geste=("Décider", "ouvrir")))
        return {"items": out}

    # ------------------------------------------------------------------ les réglages de la personne et de la machine
    CANAUX = ("cloche", "mail", "telegram", "webhook")
    MACHINE = "*"
    DEFAUT = {"critique": ["cloche", "mail", "telegram"], "avoir": ["cloche", "mail"], "info": ["cloche"]}
    RE_HEURE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

    def compte_perso(c):
        compte = (c.compte or "").strip().lower()
        if not compte or compte in SYSTEME:
            raise ValueError("ces réglages sont ceux d'une personne : aucun compte n'agit")
        return compte

    def prefs_de(compte):
        r = db.lire("SELECT fuseau, calme_debut, calme_fin, calmes FROM notif_prefs WHERE compte=?", (compte,))
        if not r:
            return {"fuseau": "", "calme_debut": "22:00", "calme_fin": "08:00", "calmes": True}
        return {"fuseau": r[0]["fuseau"], "calme_debut": r[0]["calme_debut"], "calme_fin": r[0]["calme_fin"], "calmes": bool(r[0]["calmes"])}

    def poser_prefs(compte, p):
        db.ecrire("INSERT INTO notif_prefs(compte, fuseau, calme_debut, calme_fin, calmes) VALUES(?,?,?,?,?) ON CONFLICT(compte) DO UPDATE SET "
                  "fuseau=excluded.fuseau, calme_debut=excluded.calme_debut, calme_fin=excluded.calme_fin, calmes=excluded.calmes",
                  (compte, p["fuseau"], p["calme_debut"], p["calme_fin"], 1 if p["calmes"] else 0))

    def prefs(c, fuseau=None, calmes=None, calme_debut=None, calme_fin=None):
        compte = compte_perso(c)
        avant = prefs_de(compte)
        neuf = dict(avant)
        if fuseau is not None:
            fz = str(fuseau).strip()[:64]
            if fz:
                try:
                    from zoneinfo import ZoneInfo
                    ZoneInfo(fz)
                except Exception:
                    raise ValueError("fuseau inconnu")
            neuf["fuseau"] = fz
        if calmes is not None:
            neuf["calmes"] = bool(calmes)
        for cle, v in (("calme_debut", calme_debut), ("calme_fin", calme_fin)):
            if v is not None:
                if not RE_HEURE.match(str(v)):
                    raise ValueError("%s : une heure HH:MM" % cle)
                neuf[cle] = str(v)
        poser_prefs(compte, neuf)
        return {"compte": compte, "avant": avant, "apres": neuf}

    def prouver_prefs(c, res):
        return prefs_de(res["compte"]) == res["apres"]

    def defaire_prefs(c, res):
        poser_prefs(res["compte"], res["avant"])

    def politique_de(qui):
        pol = {k: list(v) for k, v in DEFAUT.items()}
        for q in ([MACHINE] + ([qui] if qui and qui != MACHINE else [])):
            for r in db.lire("SELECT niveau, canaux FROM notif_politique WHERE compte=?", (q,)):
                if r["niveau"] in pol:
                    try:
                        pol[r["niveau"]] = [x for x in json.loads(r["canaux"]) if x in CANAUX]
                    except ValueError:
                        pass
        return pol

    def politique_ecrire(c, niveau="", canaux=None, machine=False):
        compte = (c.compte or "").strip().lower()
        if niveau not in NIVEAUX:
            raise ValueError("niveau : %s" % " | ".join(NIVEAUX))
        if machine:
            if not est_admin(compte) and compte not in SYSTEME:
                raise PermissionError("la politique de la machine est réservée à un administrateur")
            qui = MACHINE
        else:
            qui = compte_perso(c)
        liste = [x for x in (canaux or []) if x in CANAUX]
        if "cloche" not in liste:
            liste.insert(0, "cloche")                                      # la cloche reçoit TOUJOURS
        r = db.lire("SELECT canaux FROM notif_politique WHERE compte=? AND niveau=?", (qui, niveau))
        db.ecrire("INSERT INTO notif_politique(compte, niveau, canaux) VALUES(?,?,?) ON CONFLICT(compte, niveau) DO UPDATE SET canaux=excluded.canaux", (qui, niveau, json.dumps(liste)))
        return {"qui": qui, "niveau": niveau, "avant": r[0]["canaux"] if r else None, "apres": liste}

    def prouver_politique(c, res):
        r = db.lire("SELECT canaux FROM notif_politique WHERE compte=? AND niveau=?", (res["qui"], res["niveau"]))
        return bool(r) and json.loads(r[0]["canaux"]) == res["apres"]

    def defaire_politique(c, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM notif_politique WHERE compte=? AND niveau=?", (res["qui"], res["niveau"]))
        else:
            db.ecrire("UPDATE notif_politique SET canaux=? WHERE compte=? AND niveau=?", (res["avant"], res["qui"], res["niveau"]))

    def sourdines_de(compte):
        db.ecrire("DELETE FROM notif_sourdines WHERE fin<=?", (time.time(),))
        return [{"portee": r["portee"], "cible": r["cible"], "cible_nom": r["cible"], "fin": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(r["fin"]))}
                for r in db.lire("SELECT portee, cible, fin FROM notif_sourdines WHERE compte=? ORDER BY fin", (compte,))]

    def sourdine(c, portee="source", cible="", heures=0):
        """Deux étages : une NOTIFICATION (« pas avant demain ») ou une SOURCE (N heures). Toujours une fin (1 h à 30 j) ; 0 heure = lever. La cloche reçoit toujours : seuls les canaux se taisent."""
        compte = compte_perso(c)
        portee = "notif" if portee == "notif" else "source"
        cible = str(cible or "").strip()[:160]
        if not cible:
            raise ValueError("une cible est requise")
        if portee == "source" and not RE_SOURCE.match(cible):
            raise ValueError("source inconnue")
        try:
            h = float(heures or 0)
        except (TypeError, ValueError):
            h = 0
        avant = db.lire("SELECT fin FROM notif_sourdines WHERE compte=? AND portee=? AND cible=?", (compte, portee, cible))
        db.ecrire("DELETE FROM notif_sourdines WHERE compte=? AND portee=? AND cible=?", (compte, portee, cible))
        fin = 0.0
        if h > 0:
            fin = time.time() + max(1.0, min(720.0, h)) * 3600
            db.ecrire("INSERT INTO notif_sourdines(compte, portee, cible, fin) VALUES(?,?,?,?)", (compte, portee, cible, fin))
        return {"compte": compte, "portee": portee, "cible": cible, "fin": fin, "levee": not fin, "avant": avant[0]["fin"] if avant else None}

    def prouver_sourdine(c, res):
        r = db.lire("SELECT fin FROM notif_sourdines WHERE compte=? AND portee=? AND cible=?", (res["compte"], res["portee"], res["cible"]))
        return (not r) if res["levee"] else bool(r)

    def defaire_sourdine(c, res):
        db.ecrire("DELETE FROM notif_sourdines WHERE compte=? AND portee=? AND cible=?", (res["compte"], res["portee"], res["cible"]))
        if res["avant"]:
            db.ecrire("INSERT INTO notif_sourdines(compte, portee, cible, fin) VALUES(?,?,?,?)", (res["compte"], res["portee"], res["cible"], res["avant"]))

    def essais():
        return {r["canal"]: {"ts": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["ts"])), "ok": bool(r["ok"]), "detail": r["detail"]} for r in db.lire("SELECT * FROM notif_essais")}

    def webhook_lu():
        r = db.lire("SELECT actif, url_chiffree, modele FROM notif_webhook WHERE id=1")
        if not r or not r[0]["url_chiffree"]:
            return {"declare": False, "url": "", "modele": ""}
        return {"declare": bool(r[0]["actif"]), "url": ctx.dechiffrer(r[0]["url_chiffree"], "webhook"), "modele": r[0]["modele"]}

    def politique(c):
        """Tout ce que l'écran des réglages montre : ma politique, celle de la machine, mes heures calmes, mes sourdines, l'état des canaux et de leurs essais."""
        compte = (c.compte or "").strip().lower()
        admin = est_admin(compte) or compte in SYSTEME
        perso = bool(compte) and compte not in SYSTEME
        canaux = {"mail": {"declare": False}, "telegram": {"declare": False}, "cloche": {"declare": True}, "essais": essais(),
                  "webhook": webhook_lu() if admin else {"declare": False},
                  "portes": "les canaux (courriel, Telegram, webhook) n'envoient pas encore : la politique est enregistrée pour eux"}
        return {"moi": politique_de(compte) if perso else {k: list(v) for k, v in DEFAUT.items()}, "machine": politique_de(MACHINE), "defaut": DEFAUT,
                "prefs": prefs_de(compte) if perso else {"fuseau": "", "calme_debut": "22:00", "calme_fin": "08:00", "calmes": True},
                "canaux": canaux, "sourdines": sourdines_de(compte) if perso else [], "grace_min": 5, "admin": bool(admin)}

    def sources(c):
        compte = (c.compte or "").strip().lower()
        if not (est_admin(compte) or compte in SYSTEME):
            raise PermissionError("réservé à un administrateur")
        out = []
        for r in db.lire("SELECT source, MAX(ts) AS dernier, COUNT(*) AS lignes, SUM(resolue=0) AS ouvertes FROM notifs GROUP BY source ORDER BY source"):
            out.append({"source": r["source"], "nom": r["source"], "c": "muet", "nature": "evenement", "sondes": [], "cadence_s": 0,
                        "dernier": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["dernier"])) if r["dernier"] else "", "lignes": r["lignes"], "ouvertes": r["ouvertes"] or 0, "action": ""})
        return {"sources": out}

    def webhook_ecrire(c, url="", actif=False, modele=""):
        compte = (c.compte or "").strip().lower()
        if not (est_admin(compte) or compte in SYSTEME):
            raise PermissionError("le webhook de la machine est réservé à un administrateur")
        url = str(url or "").strip()
        if url and not url.startswith(("http://", "https://")):
            raise ValueError("l'adresse doit commencer par http:// ou https://")
        avant = db.lire("SELECT actif, url_chiffree, modele FROM notif_webhook WHERE id=1")
        chiffree = ctx.chiffrer(url, "webhook") if url else ""
        db.ecrire("INSERT INTO notif_webhook(id, actif, url_chiffree, modele) VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET actif=excluded.actif, url_chiffree=excluded.url_chiffree, modele=excluded.modele",
                  (1 if (actif and url) else 0, chiffree, str(modele or "").strip()[:2000]))
        return {"declare": bool(actif and url), "avant": dict(avant[0]) if avant else None}

    def prouver_webhook(c, res):
        r = db.lire("SELECT actif FROM notif_webhook WHERE id=1")
        return bool(r) and bool(r[0]["actif"]) == res["declare"]

    def defaire_webhook(c, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM notif_webhook WHERE id=1")
        else:
            a = res["avant"]
            db.ecrire("UPDATE notif_webhook SET actif=?, url_chiffree=?, modele=? WHERE id=1", (a["actif"], a["url_chiffree"], a["modele"]))

    def essai(c, canal="cloche"):
        """L'essai prouve UN canal et écrit son résultat. Seule la cloche part pour l'instant : les autres le disent, au lieu de faire croire qu'ils ont envoyé."""
        compte = (c.compte or "").strip().lower()
        canal = canal if canal in CANAUX else "cloche"
        ok, detail, nid = False, "", None
        if canal == "cloche":
            if not compte or compte in SYSTEME:
                raise ValueError("l'essai de la cloche s'adresse à une personne")
            titre = "Essai — cette notification vient des réglages"
            r = ecrire_notif("systeme", "info", titre, "Émise par %s pour vérifier que la cloche reçoit. Acquittez-la, elle n'a aucune autre raison d'exister." % compte,
                             "essai:%s" % compte, "essai", "evenement", [compte], compte, "essai")
            dire_emise(r, "systeme", "info", titre, [compte], "evenement")
            ok, detail, nid = True, "ligne #%s" % r["id"], r["id"]
        else:
            detail = "ce canal n'envoie pas encore en V19 (la politique est enregistrée, l'envoi viendra avec le module des canaux)"
        db.ecrire("INSERT INTO notif_essais(canal, ts, ok, detail) VALUES(?,?,?,?) ON CONFLICT(canal) DO UPDATE SET ts=excluded.ts, ok=excluded.ok, detail=excluded.detail", (canal, time.time(), 1 if ok else 0, detail))
        return {"ok": ok, "canal": canal, "detail": detail, "notif": nid, "repete": bool(nid) and r["repete"]}

    def prouver_essai(c, res):
        r = db.lire("SELECT ok FROM notif_essais WHERE canal=?", (res["canal"],))
        return bool(r) and bool(r[0]["ok"]) == res["ok"]

    def defaire_essai(c, res):
        if res.get("notif") and not res.get("repete"):
            db.ecrire("DELETE FROM notif_dest WHERE notif=?", (res["notif"],))
            db.ecrire("DELETE FROM notifs WHERE id=?", (res["notif"],))
        db.ecrire("DELETE FROM notif_essais WHERE canal=?", (res["canal"],))

    ctx.implementer("lister", lister)
    ctx.implementer("signal_jour", signal_jour)
    ctx.implementer("compteurs", compteurs)
    ctx.implementer("emettre", emettre, prouver_emettre, defaire_emettre)
    ctx.implementer("vu", lambda ctx, id=0: marquer(ctx, id, False), prouver_marque, defaire_marque)
    ctx.implementer("acquitter", lambda ctx, id=0: marquer(ctx, id, True), prouver_marque, defaire_marque)
    ctx.implementer("resoudre", resoudre, prouver_resolue, defaire_resolue)
    ctx.implementer("supprimer", supprimer, prouver_supprimee, defaire_supprimee)
    ctx.implementer("politique", politique)
    ctx.implementer("sources", sources)
    ctx.implementer("prefs", prefs, prouver_prefs, defaire_prefs)
    ctx.implementer("politique_ecrire", politique_ecrire, prouver_politique, defaire_politique)
    ctx.implementer("sourdine", sourdine, prouver_sourdine, defaire_sourdine)
    ctx.implementer("webhook_ecrire", webhook_ecrire, prouver_webhook, defaire_webhook)
    ctx.implementer("essai", essai, prouver_essai, defaire_essai)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
