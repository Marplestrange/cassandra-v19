# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les canaux
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : canaux
# ZONE       : CN
# VERSION CN : 0.2.0  #0faa32
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les canaux : porter une notification hors de la cloche (Telegram), et le miroir Telegram.
# MÉTHODE    : une file en base ; un moteur sur événement y range, un moteur périodique sous le compte « noyau » demande la politique à notifications puis porte
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=0faa32 ▼▼▼
"""Les canaux : porter une notification hors de la cloche, et le miroir Telegram.

La livraison, et pourquoi elle est faite ainsi :
  - DEUX moteurs, parce qu'un moteur sur événement tourne au nom du compte de l'événement : pour une panne adressée au propriétaire d'un site, il ne pourrait
    écrire qu'à ce propriétaire. « noter » range donc seulement la notification dans une file ; « livrer », périodique, agit sous le compte « noyau » et peut
    porter à chacun. La file porte aussi ce qui doit attendre (heures calmes, grâce du démarrage, envois coupés) ;
  - ce module ne juge PAS : qui doit recevoir quoi, par où, et ce qui le retient, c'est « notifications.livraison » qui le dit, à chaque passe (une sourdine
    posée ou une notification résolue entre-temps est donc vue). Il ne lit jamais la base des notifications ;
  - il ne parle PAS à Telegram : il demande « telegram.prevenir », la porte que ce module-là réserve à ce moteur. Son journal, sa preuve et le frein « envois »
    de l'exécuteur s'appliquent comme à tout acte ;
  - une notification ne part qu'UNE fois par destinataire, par canal et par niveau atteint : celle qui se répète sous la même clé n'est pas réémise, et la
    file refuse le doublon ;
  - un échec ne casse rien et se voit : il reste dans la file avec son motif, il se retente (trois fois), puis il se dit au bus (« livraison.echouee »).

Le miroir, porté de la V18 (`tg_miroir_*`), avec sa leçon :
  - il est ÉTEINT PAR DÉFAUT, et c'est délibéré : relier Telegram pour recevoir des alertes n'est pas consentir à y voir surgir ses conversations — deux
    usages du même canal, et confondre les deux enverrait chez un tiers ce que personne n'y a mis.

Différé proprement : la connexion MTProto/Telethon et la session (qui ne vit QUE dans le coffre, jamais dans la base), le courriel et le webhook.
"""
from __future__ import annotations

import time

SYSTEME = ("cassandra", "itare", "noyau", "operateur")
LIBELLES = {"critique": "Critique", "avoir": "À voir", "info": "Information"}
LIVRE = ("telegram",)                 # les canaux que ce module sait porter ; les autres disent ce qu'il leur manque
MANQUE = {"mail": "il manque à l'instance un serveur d'envoi qui ne soit pas la boîte d'une personne",
          "webhook": "son adresse est enregistrée, il lui manque le moteur qui poste"}
TENTATIVES_MAX = 3
RETENTE_S = (60, 300)                 # l'attente après le premier refus de Telegram, puis après le deuxième
RETENUE_S = 300                       # ce qu'on attend avant de redemander quand le noyau refuse (gel, crise) ou que notifications ne répond pas
VIE_MAX_S = 48 * 3600                 # une alerte retenue plus longtemps ne part plus : elle ne dirait plus rien de vrai
GARDE_S = 30 * 86400                  # ce qu'on garde des livraisons closes, pour pouvoir les relire


def brancher(ctx):
    db = ctx.stockage
    ne = time.time()                  # le branchement : c'est de là que court la grâce du démarrage

    def _miroir(compte):
        r = db.lire("SELECT miroir FROM canal_prefs WHERE compte=?", (compte,))
        return bool(r[0]["miroir"]) if r else False

    def connecter(c, session="", api_id="", api_hash=""):
        if not session:
            raise ValueError("session requise (elle vit dans le coffre)")
        if not api_id or not api_hash:
            raise ValueError("api_id et api_hash requis")
        r = ctx.racine("connecter", [str(api_id), str(api_hash)], stdin=session, delai=120)
        if not r.get("ok"):
            raise ValueError(r.get("erreur") or "connexion impossible")
        return {"identifiant": (r.get("sortie") or "").strip()}

    def etat(c):
        compte = (ctx.compte or "").strip().lower()
        return {"client": False, "connecte": False, "miroir": _miroir(compte),
                "detail": "le client Telegram (Telethon) n'est pas encore branché"}

    def miroir(c):
        compte = (ctx.compte or "").strip().lower()
        return {"miroir": _miroir(compte)}

    def miroir_ecrire(c, actif=False):
        compte = (ctx.compte or "").strip().lower()
        if not compte:
            raise ValueError("aucun compte n'agit")
        avant = _miroir(compte)
        db.ecrire("INSERT INTO canal_prefs (compte, miroir) VALUES (?,?) "
                  "ON CONFLICT(compte) DO UPDATE SET miroir=excluded.miroir",
                  (compte, 1 if actif else 0))
        return {"compte": compte, "avant": avant, "apres": bool(actif)}

    def prouver_miroir(c, res):
        r = db.lire("SELECT miroir FROM canal_prefs WHERE compte=?", (res["compte"],))
        return bool(r[0]["miroir"]) == res["apres"]

    def defaire_miroir(c, res):
        db.ecrire("INSERT INTO canal_prefs (compte, miroir) VALUES (?,?) "
                  "ON CONFLICT(compte) DO UPDATE SET miroir=excluded.miroir",
                  (res["compte"], 1 if res["avant"] else 0))

    # ------------------------------------------------------------------ la file
    def ranger(notif, niveau, compte, canal, essai, cree):
        """Une ligne par notification, niveau, destinataire et canal : la base refuse le doublon, c'est elle qui garantit qu'on ne sonne pas deux fois."""
        db.ecrire("INSERT OR IGNORE INTO canal_livraisons(notif, niveau, compte, canal, est_essai, etat, cree, maj) VALUES(?,?,?,?,?,'attente',?,?)",
                  (notif, niveau, compte, canal, 1 if essai else 0, cree, time.time()))

    def clore(l, etat_, motif=""):
        db.ecrire("UPDATE canal_livraisons SET etat=?, motif=?, maj=? WHERE id=?", (etat_, str(motif or "")[:300], time.time(), l["id"]))

    def retenir(l, pas_avant, motif):
        db.ecrire("UPDATE canal_livraisons SET pas_avant=?, motif=?, maj=? WHERE id=?", (pas_avant, str(motif or "")[:300], time.time(), l["id"]))

    def noter(c, ev):
        """Le moteur sur « notification.emise » : il range, il n'envoie rien (voir l'en-tête). La ligne sans destinataire est une notification À DÉVELOPPER :
        c'est « livrer » qui demandera à notifications qui la reçoit. Un essai lancé depuis les réglages désigne, lui, son canal et sa personne."""
        d = ev.get("donnees") or {}
        try:
            nid = int(d.get("id") or 0)
        except (TypeError, ValueError):
            nid = 0
        if not nid or ev.get("source") != "notifications":                 # seul le Centre de notifications dit ce qui est une notification
            return
        niveau = d.get("niveau") if d.get("niveau") in LIBELLES else "avoir"
        if d.get("essai"):
            dests = [str(x) for x in (d.get("destinataires") or [])]
            if d["essai"] in LIVRE and len(dests) == 1 and dests[0] not in SYSTEME and dests[0] != "admins":
                ranger(nid, niveau, dests[0], d["essai"], True, time.time())
            return
        ranger(nid, niveau, "", "", False, time.time())

    def plan_de(nid, plans):
        """Ce que notifications dit de cette notification, demandé une fois par passe. None : il ne répond pas (on redemandera)."""
        if nid not in plans:
            try:
                plans[nid] = ctx.executer_lecture("notifications.livraison", id=nid)
            except PermissionError:
                plans[nid] = None
        return plans[nid]

    def composer(p):
        tete = "%s — %s" % (LIBELLES.get(p.get("niveau"), "À voir"), p.get("titre") or "")
        pied = "Cassandra · %s" % (p.get("source") or "") + (" · signalée %d fois" % p["n"] if int(p.get("n") or 1) > 1 else "")
        return "\n".join(x for x in (tete, str(p.get("corps") or "").strip()[:1500], pied) if x)

    def echouer(l, motif):
        """Telegram a refusé, ou l'acte n'a pas abouti : on retente, puis on le dit. Jamais une exception : le moteur doit finir sa passe pour les autres."""
        n = int(l["tentatives"]) + 1
        if n >= TENTATIVES_MAX:
            db.ecrire("UPDATE canal_livraisons SET etat='echec', tentatives=?, motif=?, maj=? WHERE id=?", (n, str(motif or "")[:300], time.time(), l["id"]))
            ctx.emettre("livraison.echouee", objet=("livraison", l["id"]), compte=l["compte"],
                        donnees={"notif": l["notif"], "compte": l["compte"], "canal": l["canal"], "motif": str(motif or "")[:300], "tentatives": n})
            return
        db.ecrire("UPDATE canal_livraisons SET tentatives=?, pas_avant=?, motif=?, maj=? WHERE id=?",
                  (n, time.time() + RETENTE_S[min(n, len(RETENTE_S)) - 1], str(motif or "")[:300], time.time(), l["id"]))

    def porter(l, p):
        try:
            r = ctx.agir("telegram.prevenir", {"compte": l["compte"], "texte": composer(p)}, acteur="cassandra")
        except Exception as ex:
            r = {"statut": "echec", "erreur": str(ex)}
        statut, res = r.get("statut"), (r.get("resultat") or {})
        if statut == "faite" and res.get("ok"):
            clore(l, "livree")
            ctx.emettre("livraison.faite", objet=("livraison", l["id"]), compte=l["compte"],
                        donnees={"notif": l["notif"], "compte": l["compte"], "canal": l["canal"], "essai": bool(l["est_essai"])})
        elif statut == "faite" and res.get("cause") in ("sans-robot", "sans-destinataire"):
            clore(l, "tue", res.get("erreur") or res.get("cause"))                  # pas une panne : ce compte n'a pas (ou pas fini de brancher) son robot
        elif statut == "faite":
            echouer(l, res.get("erreur") or res.get("cause") or "Telegram a refusé")
        elif statut == "refuse" and ("inconnue" in str(r.get("raison")) or "désactivé" in str(r.get("raison"))):
            clore(l, "tue", "le module Robot Telegram n'est pas actif")
        elif statut == "refuse":                                                    # le noyau retient (crise, envois coupés entre-temps) : ce n'est pas un échec de Telegram
            retenir(l, time.time() + RETENUE_S, r.get("raison"))
        elif statut == "racontee":
            echouer(l, "le palier de « telegram.prevenir » est redescendu à « raconter » : remettez-le en « auto » (Autonomie des modules)")
        else:
            echouer(l, r.get("erreur") or r.get("motif") or statut or "l'acte n'a pas abouti")

    def livrer(c):
        """Le moteur périodique, sous le compte « noyau ». Une passe : développer ce qui vient d'arriver, puis porter ce qui est dû."""
        now = time.time()
        db.ecrire("DELETE FROM canal_livraisons WHERE etat!='attente' AND maj<?", (now - GARDE_S,))
        dues = db.lire("SELECT * FROM canal_livraisons WHERE etat='attente' AND pas_avant<=? ORDER BY id LIMIT 300", (now,))
        if not dues:
            return
        # Un moteur n'a pas de compte : l'exécuteur lui appliquerait bien le frein à l'envoi, mais autant ne rien tenter et dire pourquoi on attend.
        for frein, motif in (("envois", "les envois sont coupés : rien ne sort de la maison"), ("gel", "l'autonomie est gelée : rien ne part sans une personne")):
            if ctx.frein_actif(frein):
                db.ecrire("UPDATE canal_livraisons SET motif=?, maj=? WHERE etat='attente' AND motif!=?", (motif, now, motif))
                return
        plans = {}
        for l in [x for x in dues if not x["compte"]]:                              # à développer : qui la reçoit, et par où ?
            p = plan_de(l["notif"], plans)
            if p is None:
                if now - l["cree"] > VIE_MAX_S:
                    db.ecrire("DELETE FROM canal_livraisons WHERE id=?", (l["id"],))
                else:
                    retenir(l, now + RETENUE_S, "le Centre de notifications ne répond pas")
                continue
            if p.get("connue") and not p.get("resolue"):
                for d in p.get("destinataires") or []:
                    for canal in d.get("canaux") or []:
                        if canal in LIVRE:
                            ranger(l["notif"], l["niveau"], d["compte"], canal, False, l["cree"])
            db.ecrire("DELETE FROM canal_livraisons WHERE id=?", (l["id"],))
        for l in db.lire("SELECT * FROM canal_livraisons WHERE etat='attente' AND compte!='' AND pas_avant<=? ORDER BY id LIMIT 300", (now,)):
            p = plan_de(l["notif"], plans)
            if now - l["cree"] > VIE_MAX_S:
                clore(l, "tue", "retenue plus de 48 heures : elle ne part plus")
            elif p is None:
                retenir(l, now + RETENUE_S, "le Centre de notifications ne répond pas")
            elif not p.get("connue") or p.get("resolue"):
                clore(l, "tue", "résolue ou retirée avant l'envoi")
            elif l["est_essai"]:                                                    # un essai ne regarde ni la politique ni les heures calmes : la personne vient de le demander
                porter(l, p)
            else:
                d = next((x for x in p.get("destinataires") or [] if x.get("compte") == l["compte"]), None)
                if d is None or l["canal"] not in (d.get("canaux") or []):
                    clore(l, "tue", "la politique du compte ne demande plus ce canal")
                elif d.get("sourdine"):
                    clore(l, "tue", "sourdine posée par le compte")
                elif d.get("lu"):
                    clore(l, "tue", "déjà lue dans la cloche")
                elif float(d.get("calme_jusqua") or 0) > now:
                    retenir(l, float(d["calme_jusqua"]), "heures calmes : elle part à leur fin")
                elif now < ne + float(p.get("grace_min") or 0) * 60:
                    retenir(l, ne + float(p["grace_min"]) * 60, "grâce du démarrage : elle part si elle tient encore")
                else:
                    porter(l, p)

    # ------------------------------------------------------------------ ce qui se voit
    def quand(t):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t)) if t else ""

    def portes(c):
        """Pour le compte qui agit : quels canaux portent vraiment, ce qui est branché pour lui, et ce qu'il manque aux autres. C'est ce que l'écran des
        notifications affiche sous la matrice : il ne doit jamais laisser croire qu'un canal envoie."""
        compte = (ctx.compte or "").strip().lower()
        tg = {"livre": True, "declare": False, "detail": "le robot Telegram est celui d'une personne"}
        if compte and compte not in SYSTEME:
            try:
                e = ctx.executer_lecture("telegram.etat")
            except PermissionError:
                e = None
            if e is None:
                tg["detail"] = "le module Robot Telegram n'est pas actif"
            elif not (e.get("robot") and e.get("actif")):
                tg["detail"] = "aucun robot Telegram n'est branché sur votre compte"
            elif not e.get("destinataire"):
                tg["detail"] = "votre robot est branché, mais sans destinataire : écrivez-lui « /start » depuis Telegram, ou déclarez votre identifiant"
            else:
                tg["declare"], tg["detail"] = True, "par votre robot @%s" % (e.get("nom_robot") or "")
            r = db.lire("SELECT etat, motif, maj FROM canal_livraisons WHERE compte=? AND canal='telegram' AND est_essai=1 ORDER BY id DESC LIMIT 1", (compte,))
            if r:
                tg["essai"] = {"ts": quand(r[0]["maj"]), "ok": r[0]["etat"] == "livree",
                               "detail": {"livree": "arrivé sur Telegram", "attente": r[0]["motif"] or "confié au moteur, il part en une minute environ"}.get(r[0]["etat"], r[0]["motif"])}
        phrase = ("Telegram porte vos notifications (%s)" % tg["detail"] if tg["declare"] else "Telegram portera vos notifications quand il sera prêt (%s)" % tg["detail"])
        return {"telegram": tg, "mail": {"livre": False, "declare": False, "manque": MANQUE["mail"]}, "webhook": {"livre": False, "declare": False, "manque": MANQUE["webhook"]},
                "portes": phrase + " ; le courriel et le webhook n'envoient pas encore, la politique est enregistrée pour eux"}

    def livraisons(c, limite=50):
        """Ce qui est parti, ce qui attend et pourquoi, ce qui a échoué : les miennes, ou toutes pour un administrateur."""
        compte = (ctx.compte or "").strip().lower()
        tout = (not compte) or compte in SYSTEME or ctx.est_admin(compte)
        lim = max(1, min(int(limite or 50), 500))
        ou, args = ("compte!=''", ()) if tout else ("compte=?", (compte,))
        rows = db.lire("SELECT id, notif, niveau, compte, canal, est_essai, etat, motif, tentatives, pas_avant, cree, maj FROM canal_livraisons WHERE %s ORDER BY id DESC LIMIT ?" % ou, args + (lim,))
        n = {r["etat"]: r["n"] for r in db.lire("SELECT etat, COUNT(*) AS n FROM canal_livraisons WHERE %s GROUP BY etat" % ou, args)}
        # Tant qu'un frein retient, les notifications arrivées ne sont pas encore développées par destinataire : on les compte, et on dit ce qui retient.
        a_developper = db.lire("SELECT COUNT(*) AS n FROM canal_livraisons WHERE compte=''")[0]["n"] if tout else 0
        frein = next((f for f in ("envois", "gel") if ctx.frein_actif(f)), "")
        return {"livraisons": [dict(r, est_essai=bool(r["est_essai"]), cree=quand(r["cree"]), maj=quand(r["maj"]), pas_avant=quand(r["pas_avant"])) for r in rows],
                "attente": n.get("attente", 0) + a_developper, "livrees": n.get("livree", 0), "tues": n.get("tue", 0), "echecs": n.get("echec", 0), "frein": frein, "tout": bool(tout)}

    ctx.moteur("noter", noter)
    ctx.moteur("livrer", livrer)
    for cid, f in (("etat", etat), ("miroir", miroir), ("connecter", connecter), ("portes", portes), ("livraisons", livraisons)):
        ctx.implementer(cid, f)
    ctx.implementer("miroir_ecrire", miroir_ecrire, prouver_miroir, defaire_miroir,
                    simuler=lambda x, actif=False, **_: "allumerait le miroir Telegram" if actif else "éteindrait le miroir Telegram")
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
