# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le Centre de notifications, portée de la V18 (notif, notif_resoudre, notif_vu, notif_acqui
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : notifications
# ZONE       : CN
# VERSION CN : 0.2.0  #9f84b2
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le Centre de notifications, portée de la V18 (notif, notif_resoudre, notif_vu, notif_acquitter, _nt_filtre_dest, _nt_expiration).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=9f84b2 ▼▼▼
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

    ctx.implementer("lister", lister)
    ctx.implementer("signal_jour", signal_jour)
    ctx.implementer("compteurs", compteurs)
    ctx.implementer("emettre", emettre, prouver_emettre, defaire_emettre)
    ctx.implementer("vu", lambda ctx, id=0: marquer(ctx, id, False), prouver_marque, defaire_marque)
    ctx.implementer("acquitter", lambda ctx, id=0: marquer(ctx, id, True), prouver_marque, defaire_marque)
    ctx.implementer("resoudre", resoudre, prouver_resolue, defaire_resolue)
    ctx.implementer("supprimer", supprimer, prouver_supprimee, defaire_supprimee)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
