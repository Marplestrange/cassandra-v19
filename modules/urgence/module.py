"""Les gestes d'urgence : geler, couper les envois, fermer les sessions des autres, lever la crise, confiner.

Porté de la V18 (`notif_geler`, `notif_envois`, `confiner`, `confinement_lever`, `confinement_confirmer`), avec ses leçons :
  - AUCUN n'est un outil d'agent : une session humaine, et pour le confinement un mot tapé et une justification ;
  - le danger du confinement est de SE couper soi-même : l'adresse de la session vient de la connexion (jamais de la demande), elle est autorisée AVANT toute règle qui ferme, relue après ;
  - une échéance, pas une intention : sans confirmation, tout se lève seul — par une minuterie systemd, hors de Cassandra ;
  - le retour est la liste lue à l'envers ; ce qui ne se rend pas (des sessions fermées) vient en DERNIER, quand tout le reste a réussi ;
  - un geste qui échoue défait ceux d'avant : rien n'est laissé en place.
Ce que la V18 faisait avec ufw (absent de bien des machines) se fait ici dans une chaîne iptables à nous, que la levée retire en entier.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone

NIVEAUX = (1, 2, 3)


def minutes_ts(epoque):
    """L'échéance comme l'écran la lit (« AAAA-MM-JJ HH:MM », UTC)."""
    return datetime.fromtimestamp(float(epoque), timezone.utc).strftime("%Y-%m-%d %H:%M") if epoque else ""


def brancher(ctx):
    u = ctx.urgence()
    ident = ctx.identite()

    def racine(verbe, args=None, delai=120):
        """(ok, dict) : le programme root répond une ligne de JSON. Un courtier muet est une erreur dite, jamais un état inventé."""
        r = ctx.racine("confiner", [verbe] + ([json.dumps(args, ensure_ascii=False)] if args is not None else []), delai=delai)
        try:
            d = json.loads((r.get("sortie") or "").strip().splitlines()[-1])
        except Exception:
            d = {}
        if not d:
            raise ValueError(r.get("erreur") or "le courtier n'a pas répondu")
        return bool(r.get("ok")) and bool(d.get("ok")), d

    def objet_courant():
        return ctx.lire("confinement", "courant", portee=ctx.TOUT)

    def freins():
        return u.freins()

    # ── l'état ──
    def etat(c, ip_session=""):
        o = objet_courant()
        try:
            _, rd = racine("etat", delai=20)
        except ValueError as ex:
            rd = {"actif": False, "lecture_impossible": str(ex)}
        actif = bool(rd.get("actif"))
        if actif:
            d = (o or {}).get("donnees") or {}
            conf = {"ok": True, "actif": True, "niveau": rd.get("niveau") or d.get("niveau"), "fin": minutes_ts(rd.get("fin") or d.get("fin")), "ip": rd.get("ip") or d.get("ip"),
                    "par": rd.get("par") or d.get("par", ""), "motif": rd.get("motif") or d.get("motif", ""), "faites": rd.get("faites") or d.get("faites") or [], "confirme": bool(rd.get("confirme")),
                    "echu": bool(rd.get("echu")), "orphelin": bool(rd.get("orphelin"))}
        else:
            conf = {"ok": True, "actif": False}
            if rd.get("lecture_impossible"):
                conf["lecture_impossible"] = rd["lecture_impossible"]
        f = freins()
        return {"ok": True, "etat": {"gel": "gel" in f, "envois_coupes": "envois" in f, "confine": actif, "confinement": conf,
                                     "crise": {"actif": bool(u.en_crise())}, "usages": {}}, "ip": ip_session or ""}

    # ── les freins du noyau ──
    def frein(nom):
        def faire(c, actif=True):
            avant = nom in freins()
            u.freiner(nom, bool(actif), "geste d'urgence", ctx.compte or "humain")
            ctx.emettre("confinement.gel" if nom == "gel" else "confinement.envois", objet=("compte", ctx.compte or ""), donnees={"actif": bool(actif)})
            return {"frein": nom, "actif": bool(actif), "avant": avant}

        def prouver(c, res):
            return (nom in freins()) == res["actif"]

        def defaire(c, res):
            u.freiner(nom, res["avant"], "retour arrière", ctx.compte or "humain")
        return faire, prouver, defaire

    geler, prouver_gel, defaire_gel = frein("gel")
    couper_envois, prouver_envois, defaire_envois = frein("envois")

    # ── les sessions ──
    def sessions_revoquer(c, courant=""):
        if not str(courant or "").strip():
            raise ValueError("la session courante n'est pas connue : sans elle, vous fermeriez la vôtre")
        n = ident.revoquer_toutes_autres(str(courant))
        ctx.emettre("confinement.sessions", objet=("compte", ctx.compte or ""), donnees={"revoquees": n})
        return {"revoquees": n}

    def prouver_sessions(c, res):
        return ident.base.lire("SELECT COUNT(*) AS n FROM sessions")[0]["n"] <= 1

    def sans_retour(c, res):
        raise ValueError("aucun retour : des sessions fermées se rouvrent par une connexion")

    # ── la crise du noyau ──
    def crise_lever(c):
        avant = bool(u.en_crise())
        u.crise(False, "levée par un geste d'urgence", ctx.compte or "humain")
        ctx.emettre("confinement.crise_levee", objet=("compte", ctx.compte or ""), donnees={})
        return {"avant": avant}

    def prouver_crise(c, res):
        return not u.en_crise()

    def defaire_crise(c, res):
        if res["avant"]:
            u.crise(True, "retour arrière", ctx.compte or "humain")

    # ── le confinement ──
    def lever_tout(par):
        """Rend tout : le réseau et SSH par le programme root, puis les freins que CE confinement avait posés."""
        o = objet_courant()
        d = (o or {}).get("donnees") or {}
        ok, rd = racine("lever")
        if not ok:
            raise ValueError(rd.get("erreur") or "la levée a échoué")
        if d.get("gel_pose"):
            u.freiner("gel", False, "confinement levé", par)
        if d.get("envois_pose"):
            u.freiner("envois", False, "confinement levé", par)
        if o:
            ctx.retirer("confinement", "courant")
        ctx.emettre("confinement.leve", objet=("confinement", "courant"), donnees={"par": par, "defaits": rd.get("defaits", [])})
        return rd

    def confiner(c, niveau=0, mot="", motif="", minutes=30, ip_session="", courant=""):
        if str(mot or "").strip().upper() != "CONFINER":
            raise ValueError("confirmation attendue : tapez CONFINER")
        motif = " ".join(str(motif or "").split())[:400]
        if len(motif) < 10:
            raise ValueError("justification attendue : dites pourquoi vous estimez le serveur compromis (10 caractères au moins)")
        try:
            niveau = int(niveau)
        except (TypeError, ValueError):
            niveau = 0
        if niveau not in NIVEAUX:
            raise ValueError("niveau inconnu (1, 2 ou 3)")
        if not str(ip_session or "").strip():
            raise ValueError("l'adresse de votre session est illisible : refus prudent, sans elle vous vous couperiez vous-même")
        if not str(courant or "").strip():
            raise ValueError("la session courante n'est pas connue : sans elle, vous fermeriez la vôtre")
        if courant_objet := ctx.lire("confinement", "courant", portee=ctx.TOUT):
            raise ValueError("déjà confiné (niveau %s)" % (courant_objet["donnees"].get("niveau")))
        par = ctx.compte or "humain"
        ok, rd = racine("poser", {"niveau": niveau, "ip": str(ip_session).strip(), "minutes": minutes, "par": par, "motif": motif}, delai=240)
        if not ok:
            raise ValueError(rd.get("erreur") or "le confinement a échoué : rien n'est laissé en place")
        faites = list(rd.get("faites") or [])
        info = {"niveau": niveau, "ip": str(ip_session).strip(), "fin": rd.get("fin"), "par": par, "motif": motif, "faites": faites, "gel_pose": False, "envois_pose": False}
        ctx.poser("confinement", "courant", "Confinement niveau %d" % niveau, etat="actif", donnees=info)         # d'abord l'objet : un arrêt en route laisse de quoi lever
        try:
            f = freins()
            if "gel" not in f:
                u.freiner("gel", True, "confinement : " + motif, par)
                info["gel_pose"] = True
                faites.append("gel")
            if niveau >= 2 and "envois" not in f:
                u.freiner("envois", True, "confinement : " + motif, par)
                info["envois_pose"] = True
                faites.append("envois")
            ctx.poser("confinement", "courant", "Confinement niveau %d" % niveau, etat="actif", donnees=info)
            n = ident.revoquer_toutes_autres(str(courant))                   # ce qui ne se rend pas vient EN DERNIER
            faites.append("sessions")
            info["sessions"] = n
            ctx.poser("confinement", "courant", "Confinement niveau %d" % niveau, etat="actif", donnees=info)
        except Exception:
            lever_tout(par)
            raise
        ctx.emettre("confinement.pose", objet=("confinement", "courant"), donnees={"niveau": niveau, "ip": info["ip"], "par": par, "motif": motif, "faites": faites})
        return {"niveau": niveau, "fin": minutes_ts(info["fin"]), "fin_epoque": info["fin"], "faites": faites, "ip": info["ip"], "sessions": n}

    def prouver_confinement(c, res):
        ok, rd = racine("etat", delai=20)
        if not rd.get("actif") or rd.get("echu"):
            return False
        if res["niveau"] >= 2 and not rd.get("chaine"):
            return False
        return "gel" in freins()

    def defaire_confinement(c, res):
        lever_tout(ctx.compte or "retour arrière")

    def lever(c):
        rd = lever_tout(ctx.compte or "humain")
        return {"defaits": rd.get("defaits", []), "etait_actif": bool(rd.get("etait_actif"))}

    def prouver_levee(c, res):
        return not racine("etat", delai=20)[1].get("actif") and objet_courant() is None

    def refaire(c, res):
        raise ValueError("confiner de nouveau est un nouveau geste (avec son mot et sa justification) : il ne se rejoue pas tout seul")

    def confirmer(c, minutes=240):
        o = objet_courant()
        if not o:
            raise ValueError("aucun confinement en cours")
        avant = (o["donnees"] or {}).get("fin")
        ok, rd = racine("confirmer", {"minutes": minutes})
        if not ok:
            raise ValueError(rd.get("erreur") or "l'échéance n'a pas pu être repoussée")
        d = dict(o["donnees"], fin=rd.get("fin"), confirme=True)
        ctx.poser("confinement", "courant", o["libelle"], etat="actif", donnees=d)
        ctx.emettre("confinement.confirme", objet=("confinement", "courant"), donnees={"fin": rd.get("fin")})
        return {"fin": minutes_ts(rd.get("fin")), "fin_epoque": rd.get("fin"), "avant": avant}

    def prouver_confirme(c, res):
        return racine("etat", delai=20)[1].get("fin") == res["fin_epoque"]

    def defaire_confirme(c, res):
        if res.get("avant") and objet_courant():
            mn = max(5, int((float(res["avant"]) - time.time()) // 60))
            racine("confirmer", {"minutes": mn})

    # ── le moteur : à l'échéance, ce que Cassandra avait gelé ou coupé se rend aussi ──
    def echeance(c):
        o = objet_courant()
        if not o:
            return
        try:
            _, rd = racine("etat", delai=20)
        except ValueError:
            return                                                             # le courtier ne répond pas : on ne devine pas, on réessaie à la minute suivante
        if rd.get("echu"):                                                     # la minuterie n'a pas joué : on lève nous-mêmes
            lever_tout("échéance")
        elif not rd.get("actif"):                                              # levé par la minuterie (ou à la main, ailleurs) : les freins de Cassandra se rendent avec
            lever_tout("échéance")

    ctx.moteur("echeance", echeance)
    ctx.implementer("etat", etat)
    ctx.implementer("geler", geler, prouver_gel, defaire_gel)
    ctx.implementer("couper_envois", couper_envois, prouver_envois, defaire_envois)
    ctx.implementer("sessions_revoquer", sessions_revoquer, prouver_sessions, sans_retour)
    ctx.implementer("crise_lever", crise_lever, prouver_crise, defaire_crise)
    ctx.implementer("confiner", confiner, prouver_confinement, defaire_confinement)
    ctx.implementer("lever", lever, prouver_levee, refaire)
    ctx.implementer("confirmer", confirmer, prouver_confirme, defaire_confirme)
