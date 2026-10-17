# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : La flotte
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : flotte
# ZONE       : CN
# VERSION CN : 0.1.1  #9b2b9d
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : La flotte : le parc de machines, fusionné, avec ce qu'on peut en faire.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.1 empreinte=9b2b9d ▼▼▼
"""La flotte : le parc de machines, fusionné, avec ce qu'on peut en faire.

Porté de la V18 (`flotte_*`, `fleet_*`, `ms_*`), avec ses leçons :
  - TROIS sources décrivaient le même parc sans se lire (le registre des machines, Tailscale, le sensorium) : on les met CÔTE À CÔTE, chacune avec son âge ;
  - Tailscale fait foi pour la PRÉSENCE : une machine que le tailnet voit en ligne n'est pas hors ligne parce que sa sonde SSH a échoué ; la sonde est la source des
    mesures et du contrôle, pas de la présence ;
  - une mesure absente est NULL, jamais zéro (un ping ne mesure pas de processeur) ; « tout le parc répond » ne se dit que si la présence tourne ;
  - une alerte par TRANSITION, pas toutes les cinq minutes ; une machine volontairement absente (intermittente) ne crie pas, mais l'absence est datée ;
  - une machine que Tailscale ne liste plus est DISPARUE (ni en ligne, ni en panne) ; ses traces s'oublient seules après 30 jours ; l'historique, lui, reste ;
  - la machine distante n'est pas un terminal libre : des commandes NOMMÉES, un accord explicite pour ce qui modifie, et jamais l'arrêt de ce qui coupe le lien ;
  - les secrets (clé, mot de passe, jeton) sont chiffrés au repos et ne ressortent jamais d'une lecture ; un mot de passe SSH passe par l'environnement, jamais par la ligne de commande.
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import socket
import time
from datetime import timedelta

from . import CN_outils as o

SYSTEME = ("cassandra", "itare", "noyau", "operateur")
CHAMPS_SECRETS = ("cle", "mot_de_passe", "jeton")
AUTHS = ("tailscale", "cle", "mot_de_passe", "defaut")
RE_NOM = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")


def brancher(ctx):
    db = ctx.stockage
    acces = o.Acces()
    ctx.acces = acces
    ctx.hote_nom = None

    def hote():
        return o.nom(ctx.hote_nom or socket.gethostname())

    def reservee():
        c = ctx.compte
        if c and c not in SYSTEME and not ctx.est_admin(c):
            raise PermissionError("la flotte est réservée à l'administrateur : une machine n'est pas l'affaire d'un compte")

    def reglage(nom, defaut):
        try:
            v = ctx.reglage(nom)
            return defaut if v in (None, "") else v
        except Exception:
            return defaut

    def evt(nom, genre, detail, duree=None, ts=None):
        db.ecrire("INSERT INTO evenements(ts, nom, genre, detail, duree_min) VALUES (?,?,?,?,?)", (ts or o.horodate(), nom, genre, detail, duree))

    # ------------------------------------------------------------------ le registre
    def registre():
        return [dict(r) for r in db.lire("SELECT * FROM machines ORDER BY nom")]

    def secrets_de(m):
        if not m.get("secrets"):
            return {}
        try:
            return json.loads(ctx.dechiffrer(m["secrets"], "machine:" + m["nom"]))
        except Exception:
            return {}

    def machine_acces(nom):
        """La machine telle que le SSH la veut (secrets déchiffrés), ou une machine virtuelle si la sonde a obtenu un shell sans clé (Tailscale SSH)."""
        n = o.nom(nom)
        r = db.lire("SELECT * FROM machines WHERE nom=?", (n,))
        if r and r[0]["type"] == "ssh":
            m = dict(r[0])
            m.update(secrets_de(m))
            return m
        s = db.lire("SELECT * FROM sonde_ssh WHERE nom=?", (n,))
        if s and s[0]["ok"]:
            return {"nom": n, "type": "ssh", "hote": s[0]["ip"], "port": 22, "utilisateur": s[0]["utilisateur"] or "root", "auth": "tailscale", "systeme": "linux"}
        if r:
            raise ValueError("les actions à distance passent par SSH ; « %s » est de type %s" % (n, r[0]["type"]))
        raise ValueError("machine « %s » introuvable dans la flotte" % nom)

    # ------------------------------------------------------------------ le parc
    def engagements():
        return {r["nom"]: (r["statut"], r["niveau"]) for r in db.lire("SELECT nom, statut, niveau FROM engagements")}

    def dispo(jours):
        depuis = o.horodate(o.utc() - timedelta(days=jours))
        rows = db.lire("SELECT nom, COUNT(*) AS n, SUM(en_ligne) AS en FROM mesures WHERE ts>=? GROUP BY nom ORDER BY nom", (depuis,))
        pannes = {r["nom"]: (r["n"], r["m"]) for r in db.lire("SELECT nom, COUNT(*) AS n, COALESCE(SUM(duree_min),0) AS m FROM evenements WHERE genre='retour' AND ts>=? GROUP BY nom", (depuis,))}
        out = []
        for r in rows:
            n_p, minutes = pannes.get(r["nom"], (0, 0))
            out.append({"nom": r["nom"], "releves": r["n"], "disponibilite": round(100.0 * (r["en"] or 0) / r["n"], 2) if r["n"] else None, "pannes": n_p, "indispo_min": minutes, "indispo": o.duree(minutes)})
        return out

    def parc(c):
        reservee()
        eng, h, M, live = engagements(), hote(), {}, acces.tailscale_live()

        def m(n):
            return M.setdefault(n, {"nom": n, "sources": {}, "os": "", "ip": "", "type": "", "en_ligne": None, "dernier_contact": "", "registre": None})
        for r in registre():
            n = o.nom(r["nom"])
            x = m(n)
            x["type"] = r["type"]
            x["os"] = x["os"] or r["systeme"]
            x["registre"] = {"type": r["type"], "actif": bool(r["actif"]), "hote": r["hote"] or r["url"], "auth": r["auth"] if r["type"] == "ssh" else ""}
            x["sources"]["registre"] = {"etat": "ok" if r["actif"] else "avert", "texte": "%s%s" % (r["type"], "" if r["actif"] else " · suspendue"), "observe": ""}
            if r["type"] == "ssh":
                x["sources"]["ssh"] = {"etat": "ok", "texte": {"cle": "clé déclarée", "mot_de_passe": "mot de passe déclaré", "tailscale": "Tailscale SSH déclaré"}.get(r["auth"], "accès déclaré"), "observe": ""}
        for n, p in live.items():
            if n.startswith("_"):
                continue
            x = m(n)
            x["os"] = x["os"] or p.get("os", "")
            x["ip"] = x["ip"] or p.get("ip", "")
            x["en_ligne"] = bool(p.get("online"))
            x["dernier_contact"] = "maintenant" if p.get("online") else (p.get("last_seen") or x["dernier_contact"])
            x["sources"]["tailscale"] = {"etat": "ok" if p.get("online") else "avert", "texte": ("self · " if p.get("self") else ("en ligne · " if p.get("online") else "hors ligne · ")) + (p.get("ip") or ""), "observe": p.get("observe", "")}
            if p.get("self"):
                x["type"] = x["type"] or "hote"
        for r in db.lire("SELECT nom, COUNT(*) AS n, MAX(ts) AS ts, SUM(CASE WHEN gravite='warning' THEN 1 ELSE 0 END) AS w FROM releves GROUP BY nom"):
            x = m(o.nom(r["nom"]))
            x["sources"]["releves"] = {"etat": "avert" if r["w"] else "ok", "texte": "%d relevé(s)%s" % (r["n"], " · alerte" if r["w"] else ""), "observe": r["ts"]}
        dd = {a["nom"]: a for a in dispo(30)}
        vus = {r["nom"]: r for r in db.lire("SELECT nom, en_ligne, depuis, ts FROM vus")}
        for n, v in vus.items():
            if n not in M:
                m(n)["dernier_contact"] = v["ts"]
        sonde = {r["nom"]: r for r in db.lire("SELECT * FROM sonde_ssh")}
        recente = o.horodate(o.utc() - timedelta(days=1))
        out = []
        for n, x in M.items():
            statut, niv_decl = eng.get(n, ("attendue", ""))
            sd = sonde.get(n)
            if n == h:
                niveau = "agent"
            elif niv_decl in o.NIVEAUX:
                niveau = niv_decl
            elif x["registre"] and x["registre"]["type"] == "ssh":
                niveau = "ssh"
            elif sd and sd["ok"]:
                niveau = "ssh"
            elif x["registre"]:
                niveau = "observation"
            else:
                niveau = "signal"
            osl = (x["os"] or "").lower()
            mobile = "ios" in osl or "android" in osl
            disparue = n != h and not x["registre"] and "tailscale" not in x["sources"] and statut != "retiree"
            if "ssh" not in x["sources"] and sd:
                x["sources"]["ssh"] = ({"etat": "ok", "texte": "Tailscale SSH · %s · sans clé déclarée" % (sd["utilisateur"] or "root"), "observe": sd["ts"]} if sd["ok"] else {"etat": "erreur", "texte": "aucune clé · Tailscale SSH refusé", "observe": sd["ts"]})
            if "ssh" not in x["sources"]:
                x["sources"]["ssh"] = {"etat": "neutre" if (n == h or mobile) else "erreur", "texte": "local" if n == h else ("sans objet" if mobile else "aucune clé"), "observe": ""}
            if "registre" not in x["sources"]:
                x["sources"]["registre"] = {"etat": "neutre" if n == h else "erreur", "texte": "hôte, implicite" if n == h else "absente", "observe": ""}
            if "tailscale" not in x["sources"]:
                x["sources"]["tailscale"] = {"etat": "neutre", "texte": "absente du tailnet", "observe": ""}
            if "releves" not in x["sources"]:
                x["sources"]["releves"] = {"etat": "neutre", "texte": "aucun relevé", "observe": ""}
            v, d = vus.get(n), dd.get(n)
            if disparue:
                x["en_ligne"] = False
            elif x["en_ligne"] is None and v:
                x["en_ligne"] = bool(v["en_ligne"]) if str(v["ts"] or "") >= recente else False
            groupe = ("Disparues" if disparue else "Retirées" if statut == "retiree" else "Mobiles" if mobile else
                      "Postes" if ("windows" in osl or "macos" in osl or "darwin" in osl) else "Serveurs")
            if disparue:
                libelle, etat = "disparue du tailnet · renommée ou retirée", "neutre"
            elif statut == "retiree" and not x["en_ligne"]:
                libelle, etat = "retirée", "retiree"
            elif x["en_ligne"] is None:
                libelle, etat = "inconnue", "neutre"
            elif x["en_ligne"]:
                libelle, etat = "en ligne", "ok"
            elif statut == "intermittente":
                libelle, etat = "hors ligne · volontaire", "avert"
            else:
                libelle, etat = "hors ligne · panne", "erreur"
            out.append({"nom": n, "os": x["os"], "ip": x["ip"], "type": x["type"] or ("hote" if n == h else ""), "hote": n == h, "en_ligne": x["en_ligne"], "etat": etat, "libelle": libelle,
                        "dernier_contact": x["dernier_contact"] or (v["ts"] if v else ""), "statut": statut, "niveau": niveau, "groupe": groupe, "tailscale_ssh": bool(sd and sd["ok"]),
                        "registre": x["registre"], "sources": x["sources"], "dispo": d["disponibilite"] if d else None, "pannes": d["pannes"] if d else None,
                        "indispo": d["indispo"] if d else "", "releves": d["releves"] if d else 0, "disparue": disparue,
                        "depuis": ((v["ts"] if v else (x["sources"]["releves"].get("observe") or "")) if disparue else (v["depuis"] if v else ""))})
        ordre = {"Serveurs": 0, "Postes": 1, "Mobiles": 2, "Retirées": 3, "Disparues": 4}
        out.sort(key=lambda z: (ordre.get(z["groupe"], 9), not z["hote"], z["nom"]))
        return {"releve": o.horodate(), "hote": h, "machines": out,
                "compte": {"declarees": sum(1 for z in out if not z["disparue"]), "tailscale": sum(1 for z in out if z["sources"]["tailscale"]["etat"] in ("ok", "avert")),
                           "disparues": sum(1 for z in out if z["disparue"]), "en_ligne": sum(1 for z in out if z["en_ligne"]),
                           "attendues_hors_ligne": sum(1 for z in out if z["etat"] == "erreur"), "ssh": sum(1 for z in out if z["niveau"] == "ssh"),
                           "volontaires": sum(1 for z in out if z["statut"] in ("intermittente", "retiree")), "mesurees": sum(1 for z in out if z["dispo"] is not None)},
                "tailscale_sante": live.get("_sante") or [],
                "presence": {"active": bool(reglage("presence_active", True)), "periode_s": int(reglage("presence_s", 300))}}

    def verdict(c):
        reservee()
        p = parc(c)
        depuis = o.horodate(o.utc() - timedelta(hours=24))
        pertes = [(r["nom"], r["n"], r["t0"], r["t1"]) for r in db.lire("SELECT nom, COUNT(*) AS n, MIN(ts) AS t0, MAX(ts) AS t1 FROM evenements WHERE genre='perte' AND ts>=? GROUP BY nom HAVING COUNT(*)>=2 ORDER BY COUNT(*) DESC", (depuis,))]
        return o.verdict(p, pertes)

    def serie(c, mesure="", depuis="", jusqu_a=""):
        """Les points de présence et de ressources des machines (une courbe par machine) ; les pertes en compteur."""
        a, b = str(depuis)[:19].replace("T", " "), str(jusqu_a)[:19].replace("T", " ")
        if mesure == "fleet_down":
            ev = db.lire("SELECT ts FROM evenements WHERE genre='perte' AND ts BETWEEN ? AND ? ORDER BY ts", (a, b))
            return {"series": [{"nom": "pertes", "points": [[r["ts"], 1] for r in ev]}]}
        col = {"fleet_up": "en_ligne * 100.0", "fleet_cpu": "cpu", "fleet_ram": "ram", "fleet_disk": "disque"}.get(mesure)
        if not col:
            raise ValueError("mesure inconnue : « %s »" % mesure)
        cond = "" if mesure == "fleet_up" else " AND %s IS NOT NULL" % col
        par = {}
        for r in db.lire("SELECT ts, nom, %s AS v FROM mesures WHERE ts BETWEEN ? AND ?%s ORDER BY ts" % (col, cond), (a, b)):
            par.setdefault(r["nom"], []).append([r["ts"], r["v"]])
        return {"series": [{"nom": n, "points": p} for n, p in sorted(par.items())]}

    def machines(c):
        reservee()
        return {"machines": [{k: v for k, v in r.items() if k != "secrets"} | {"secrets_poses": sorted(secrets_de(r))} for r in registre()]}

    def historique(c, nom="", heures=24):
        reservee()
        n = o.nom(nom)
        h = max(1, min(int(heures or 24), 24 * 90))
        depuis = o.horodate(o.utc() - timedelta(hours=h))
        pts = db.lire("SELECT ts, en_ligne, cpu, ram, disque, sante, erreur FROM mesures WHERE nom=? AND ts>=? ORDER BY ts", (n, depuis))
        evs = db.lire("SELECT ts, genre, detail, duree_min FROM evenements WHERE nom=? AND ts>=? ORDER BY ts DESC LIMIT 100", (n, depuis))
        en = sum(1 for p in pts if p["en_ligne"])
        return {"nom": n, "heures": h, "releves": len(pts), "disponibilite": round(100.0 * en / len(pts), 2) if pts else None,
                "points": [{"ts": p["ts"], "en_ligne": bool(p["en_ligne"]), "cpu": p["cpu"], "ram": p["ram"], "disque": p["disque"], "sante": p["sante"], "erreur": p["erreur"]} for p in pts],
                "evenements": [dict(e) for e in evs], "liens": liens(c, n)["liens"],
                "releves_detail": [dict(r) for r in db.lire("SELECT cle, valeur, gravite, ts FROM releves WHERE nom=? ORDER BY cle", (n,))]}

    def disponibilite(c, jours=30):
        reservee()
        j = max(1, min(int(jours or 30), 365))
        out = dispo(j)
        return {"jours": j, "machines": out, "raison": "" if out else "Aucune mesure enregistrée — la passe n'a pas encore tourné."}

    def evenements(c, limite=100, nom=""):
        reservee()
        if nom:
            rows = db.lire("SELECT ts, nom, genre, detail, duree_min FROM evenements WHERE nom=? ORDER BY id DESC LIMIT ?", (o.nom(nom), max(1, min(int(limite), 500))))
        else:
            rows = db.lire("SELECT ts, nom, genre, detail, duree_min FROM evenements ORDER BY id DESC LIMIT ?", (max(1, min(int(limite), 500)),))
        return {"evenements": [dict(r) for r in rows]}

    def liens(c, nom=""):
        reservee()
        if nom:
            rows = db.lire("SELECT nom, genre, ref, note, ts FROM liens WHERE nom=? ORDER BY genre, ts", (o.nom(nom),))
        else:
            rows = db.lire("SELECT nom, genre, ref, note, ts FROM liens ORDER BY nom, genre, ts")
        return {"liens": [dict(r) for r in rows]}

    def actions(c):
        reservee()
        return {"actions": [{"cle": k, "modifie": v[1], "description": v[2], "service_requis": "%(service)s" in v[0]} for k, v in sorted(o.ACTIONS.items())]}

    def ping(c, nom=""):
        reservee()
        n = o.nom(nom)
        p = acces.tailscale_live().get(n)
        if not p or not p.get("ip"):
            raise ValueError("machine inconnue de Tailscale")
        if p.get("self"):
            return {"nom": n, "latence_ms": 0, "detail": "c'est l'hôte"}
        try:
            txt = acces.tailscale_ping(p["ip"])
        except Exception as ex:
            raise ValueError(str(ex)[:200])
        ms = [float(x) for x in re.findall(r"in (\d+(?:\.\d+)?)ms", txt)]
        if not ms:
            raise ValueError("pas de réponse : " + txt[-200:])
        return {"nom": n, "latence_ms": round(min(ms), 1), "essais": len(ms), "via": "direct" if "direct" in txt else ("DERP" if "DERP" in txt else "")}

    def diagnostic(c, nom="", action="diagnostic", service=""):
        """Une commande de LECTURE sur une machine, par SSH (les commandes qui modifient passent par service_agir)."""
        reservee()
        spec = o.ACTIONS.get(action)
        if not spec:
            raise ValueError("action inconnue (%s)" % ", ".join(sorted(o.ACTIONS)))
        if spec[1]:
            raise ValueError("« %s » modifie la machine : elle passe par service_agir, avec preuve et retour" % action)
        cmd, svc = spec[0], ""
        if "%(service)s" in cmd:
            svc = str(service or "").strip()
            if not o.RE_SERVICE.match(svc):
                raise ValueError("nom de service invalide")
            cmd = cmd % {"service": svc}
        m = machine_acces(nom)
        t0 = time.time()
        out, err, rc = acces.ssh_exec(m, cmd, 45)
        ms = int((time.time() - t0) * 1000)
        evt(o.nom(nom), "action", "%s%s → code %s (%d ms)" % (action, (" " + svc) if svc else "", rc, ms))
        return {"action": action, "machine": o.nom(nom), "service": svc, "code": rc, "duree_ms": ms, "commande": cmd, "sortie": ((out or "") + (("\n--- stderr ---\n" + err) if err else ""))[:8000]}

    # ------------------------------------------------------------------ écritures
    def secrets_chiffres(nom, a):
        d = {k: a[k] for k in CHAMPS_SECRETS if a.get(k)}
        return ctx.chiffrer(json.dumps(d), "machine:" + nom) if d else ""

    def machine_ajouter(c, nom="", type="ssh", hote="", port=22, utilisateur="root", auth="tailscale", systeme="", url="", cle="", mot_de_passe="", jeton=""):
        reservee()
        n = o.nom(nom)
        if not RE_NOM.match(n):
            raise ValueError("un nom de machine : minuscules, chiffres, - et _ (comme sur le tailnet)")
        if type not in o.TYPES:
            raise ValueError("type : %s" % " | ".join(o.TYPES))
        if type in ("ssh", "ping") and not str(hote).strip():
            raise ValueError("l'adresse de la machine est requise")
        if type == "cassandra" and not str(url).startswith(("http://", "https://")):
            raise ValueError("l'adresse d'une autre Cassandra commence par http:// ou https://")
        if type == "ssh" and auth not in AUTHS:
            raise ValueError("authentification : %s" % " | ".join(AUTHS))
        port = int(22 if port in (None, "") else port)
        if not 1 <= port <= 65535:
            raise ValueError("port hors plage")
        avant = db.lire("SELECT * FROM machines WHERE nom=?", (n,))
        secrets = secrets_chiffres(n, {"cle": cle, "mot_de_passe": mot_de_passe, "jeton": jeton}) or (avant[0]["secrets"] if avant else "")
        db.ecrire("INSERT OR REPLACE INTO machines(nom, type, actif, hote, port, utilisateur, auth, systeme, url, secrets, cree) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (n, type, 1, str(hote).strip(), port, str(utilisateur or "root").strip(), auth, str(systeme or "").lower(), str(url).rstrip("/"), secrets, avant[0]["cree"] if avant else time.time()))
        return {"nom": n, "avant": dict(avant[0]) if avant else None, "action": "mise à jour" if avant else "ajout"}

    def prouver_machine(c, res):
        return bool(db.lire("SELECT 1 FROM machines WHERE nom=?", (res["nom"],)))

    def rendre_machine(res):
        db.ecrire("DELETE FROM machines WHERE nom=?", (res["nom"],))
        a = res.get("avant")
        if a:
            db.ecrire("INSERT INTO machines(nom, type, actif, hote, port, utilisateur, auth, systeme, url, secrets, cree) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                      (a["nom"], a["type"], a["actif"], a["hote"], a["port"], a["utilisateur"], a["auth"], a["systeme"], a["url"], a["secrets"], a["cree"]))

    def defaire_machine_ajoutee(c, res):
        rendre_machine(res)

    def machine_retirer(c, nom=""):
        reservee()
        n = o.nom(nom)
        r = db.lire("SELECT * FROM machines WHERE nom=?", (n,))
        if not r:
            raise ValueError("machine « %s » non trouvée au registre" % nom)
        db.ecrire("DELETE FROM machines WHERE nom=?", (n,))
        return {"nom": n, "avant": dict(r[0])}

    def prouver_retiree(c, res):
        return not db.lire("SELECT 1 FROM machines WHERE nom=?", (res["nom"],))

    def defaire_retiree(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO machines(nom, type, actif, hote, port, utilisateur, auth, systeme, url, secrets, cree) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (a["nom"], a["type"], a["actif"], a["hote"], a["port"], a["utilisateur"], a["auth"], a["systeme"], a["url"], a["secrets"], a["cree"]))

    def machine_basculer(c, nom="", actif=True):
        reservee()
        n = o.nom(nom)
        r = db.lire("SELECT actif FROM machines WHERE nom=?", (n,))
        if not r:
            raise ValueError("machine « %s » non trouvée au registre" % nom)
        db.ecrire("UPDATE machines SET actif=? WHERE nom=?", (1 if actif else 0, n))
        return {"nom": n, "avant": r[0]["actif"], "actif": 1 if actif else 0}

    def prouver_bascule(c, res):
        return db.lire("SELECT actif FROM machines WHERE nom=?", (res["nom"],))[0]["actif"] == res["actif"]

    def defaire_bascule(c, res):
        db.ecrire("UPDATE machines SET actif=? WHERE nom=?", (res["avant"], res["nom"]))

    def engagement(c, nom="", statut="", niveau=""):
        """L'engagement par machine, lu par TOUS. Statut : attendue | intermittente | retiree. Niveau : signal | observation | ssh | agent (ssh exige un accès, agent est l'hôte)."""
        reservee()
        n = o.nom(nom)
        if not n:
            raise ValueError("nom manquant")
        statut = str(statut or "").strip().lower().replace("é", "e")
        niveau = str(niveau or "").strip().lower()
        if statut and statut not in o.STATUTS:
            raise ValueError("statut inconnu : %s" % statut)
        if niveau and niveau not in o.NIVEAUX:
            raise ValueError("niveau inconnu : %s" % niveau)
        if niveau == "agent" and n != hote():
            raise ValueError("« agent » est le niveau de l'hôte seulement")
        if niveau == "ssh":
            ok_ssh = bool(db.lire("SELECT 1 FROM machines WHERE nom=? AND type='ssh'", (n,))) or bool(db.lire("SELECT 1 FROM sonde_ssh WHERE nom=? AND ok=1", (n,)))
            if not ok_ssh:
                raise ValueError("SSH exige une machine de type ssh au registre (clé ou mot de passe), ou un accès Tailscale SSH constaté par la sonde")
        if not statut and not niveau:
            raise ValueError("un statut ou un niveau")
        avant = db.lire("SELECT statut, niveau FROM engagements WHERE nom=?", (n,))
        a = dict(avant[0]) if avant else None
        nv = {"statut": statut or (a["statut"] if a else "attendue"), "niveau": niveau or (a["niveau"] if a else "")}
        db.ecrire("INSERT OR REPLACE INTO engagements(nom, statut, niveau) VALUES (?,?,?)", (n, nv["statut"], nv["niveau"]))
        return {"nom": n, "avant": a, "statut": nv["statut"], "niveau": nv["niveau"]}

    def prouver_engagement(c, res):
        r = db.lire("SELECT statut, niveau FROM engagements WHERE nom=?", (res["nom"],))
        return bool(r) and r[0]["statut"] == res["statut"] and r[0]["niveau"] == res["niveau"]

    def defaire_engagement(c, res):
        if res["avant"] is None:
            db.ecrire("DELETE FROM engagements WHERE nom=?", (res["nom"],))
        else:
            db.ecrire("INSERT OR REPLACE INTO engagements(nom, statut, niveau) VALUES (?,?,?)", (res["nom"], res["avant"]["statut"], res["avant"]["niveau"]))

    def lien_enregistrer(c, nom="", genre="", ref="", note=""):
        reservee()
        n, g, r = o.nom(nom), str(genre or "").strip(), str(ref or "").strip()
        if not n or not r:
            raise ValueError("machine et référence obligatoires")
        if g not in o.LIENS:
            raise ValueError("type de lien inconnu (%s)" % ", ".join(o.LIENS))
        avant = db.lire("SELECT * FROM liens WHERE nom=? AND genre=? AND ref=?", (n, g, r))
        db.ecrire("INSERT OR REPLACE INTO liens(nom, genre, ref, note, ts) VALUES (?,?,?,?,?)", (n, g, r, str(note or "")[:300], o.horodate()))
        return {"nom": n, "genre": g, "ref": r, "avant": dict(avant[0]) if avant else None}

    def prouver_lien(c, res):
        return bool(db.lire("SELECT 1 FROM liens WHERE nom=? AND genre=? AND ref=?", (res["nom"], res["genre"], res["ref"])))

    def defaire_lien(c, res):
        db.ecrire("DELETE FROM liens WHERE nom=? AND genre=? AND ref=?", (res["nom"], res["genre"], res["ref"]))
        a = res.get("avant")
        if a:
            db.ecrire("INSERT INTO liens(nom, genre, ref, note, ts) VALUES (?,?,?,?,?)", (a["nom"], a["genre"], a["ref"], a["note"], a["ts"]))

    def lien_retirer(c, nom="", genre="", ref=""):
        reservee()
        n, g, r = o.nom(nom), str(genre or "").strip(), str(ref or "").strip()
        avant = db.lire("SELECT * FROM liens WHERE nom=? AND genre=? AND ref=?", (n, g, r))
        if not avant:
            raise ValueError("lien introuvable")
        db.ecrire("DELETE FROM liens WHERE nom=? AND genre=? AND ref=?", (n, g, r))
        return {"nom": n, "genre": g, "ref": r, "avant": dict(avant[0])}

    def prouver_lien_retire(c, res):
        return not db.lire("SELECT 1 FROM liens WHERE nom=? AND genre=? AND ref=?", (res["nom"], res["genre"], res["ref"]))

    def defaire_lien_retire(c, res):
        a = res["avant"]
        db.ecrire("INSERT OR REPLACE INTO liens(nom, genre, ref, note, ts) VALUES (?,?,?,?,?)", (a["nom"], a["genre"], a["ref"], a["note"], a["ts"]))

    def oublier(c, nom=""):
        """Oublier une machine DISPARUE : ses traces (présence, sonde, relevés, engagement) s'effacent, l'historique reste. Refusé si Tailscale la liste encore, si elle est au registre ou si c'est l'hôte."""
        reservee()
        n = o.nom(nom)
        if not n:
            raise ValueError("nom manquant")
        if n == hote():
            raise ValueError("l'hôte ne s'oublie pas")
        if n in acces.tailscale_live():
            raise ValueError("Tailscale liste encore %s : ce n'est pas une disparue. Pour la sortir du parc, passe-la « retirée »." % n)
        if db.lire("SELECT 1 FROM machines WHERE nom=?", (n,)):
            raise ValueError("%s est au registre : retire-la du registre d'abord." % n)
        return oublier_traces(n, "à la demande")

    def oublier_traces(n, pourquoi):
        sauve = {t: [dict(r) for r in db.lire("SELECT * FROM %s WHERE nom=?" % t, (n,))] for t in ("vus", "sonde_ssh", "releves", "engagements")}
        with db.transaction() as cx:
            for t in sauve:
                cx.execute("DELETE FROM %s WHERE nom=?" % t, (n,))
        evt(n, "oubli", "Traces effacées %s." % pourquoi)
        return {"nom": n, "efface": [t for t, v in sauve.items() if v], "avant": sauve}

    def prouver_oubli(c, res):
        return all(not db.lire("SELECT 1 FROM %s WHERE nom=?" % t, (res["nom"],)) for t in ("vus", "sonde_ssh", "releves", "engagements"))

    def defaire_oubli(c, res):
        for t, rows in res["avant"].items():
            for r in rows:
                cols = list(r)
                db.ecrire("INSERT OR REPLACE INTO %s(%s) VALUES (%s)" % (t, ",".join(cols), ",".join("?" * len(cols))), [r[k] for k in cols])

    def etat_service(m, svc):
        out, err, rc = acces.ssh_exec(m, "systemctl is-active %s" % svc, 20)
        return (out or "").strip() or "inconnu"

    def service_agir(c, nom="", action="", service=""):
        """Démarrer, arrêter ou redémarrer un service d'une machine. Jamais ce qui coupe le lien (sshd, réseau) ; le retour remet l'état d'AVANT."""
        reservee()
        spec = o.ACTIONS.get(action)
        if not spec or not spec[1]:
            raise ValueError("action : svc_start | svc_stop | svc_restart")
        svc = str(service or "").strip()
        if not o.RE_SERVICE.match(svc):
            raise ValueError("nom de service invalide")
        if action == "svc_stop" and svc.replace(".service", "") in o.SERVICES_VITAUX:
            raise ValueError("%s est vital pour l'accès à %s : l'arrêter couperait le lien SSH et la machine deviendrait injoignable" % (svc, nom))
        m = machine_acces(nom)
        avant = etat_service(m, svc)
        t0 = time.time()
        out, err, rc = acces.ssh_exec(m, spec[0] % {"service": svc}, 45)
        ms = int((time.time() - t0) * 1000)
        evt(o.nom(nom), "action", "%s %s → code %s (%d ms)" % (action, svc, rc, ms))
        if rc != 0:
            raise ValueError("%s %s a échoué (code %s) : %s" % (action, svc, rc, ((err or out) or "")[:300]))
        return {"nom": o.nom(nom), "service": svc, "action": action, "etat_avant": avant, "code": rc, "duree_ms": ms, "sortie": (out or "")[:2000]}

    def prouver_service(c, res):
        attendu = "inactive" if res["action"] == "svc_stop" else "active"
        return etat_service(machine_acces(res["nom"]), res["service"]) == attendu

    def defaire_service(c, res):
        m = machine_acces(res["nom"])
        cmd = "systemctl start %s" % res["service"] if res["etat_avant"] == "active" else "systemctl stop %s" % res["service"]
        acces.ssh_exec(m, cmd, 45)

    # ------------------------------------------------------------------ les passes (moteurs)
    def passe_registre():
        """Une ligne par machine du registre : en ligne ou non, et ses mesures. Tailscale fait foi pour la présence quand il voit la machine."""
        actives = [dict(r) for r in db.lire("SELECT * FROM machines WHERE actif=1")]
        if not actives:
            return 0
        live = acces.tailscale_live()
        limite = max(5, int(reglage("delai_s", 20)))

        def une(r):
            m = dict(r)
            m.update(secrets_de(m))
            if r["type"] == "ssh":
                cmd = o.COMMANDE_METRIQUES
                out, err, rc = acces.ssh_exec(m, cmd, 15)
                if rc != 0 and not out:
                    return {"nom": r["nom"], "type": "ssh", "en_ligne": False, "erreur": (err or "SSH sans réponse").strip()[:120]}
                return dict({"nom": r["nom"], "type": "ssh", "en_ligne": True, "erreur": ""}, **o.lire_metriques(out, ctx.point))
            if r["type"] == "ping":
                return {"nom": r["nom"], "type": "ping", "en_ligne": acces.tcp(r["hote"], r["port"] or 22), "erreur": ""}
            d = acces.http_json(r["url"] + "/api/dashboard", m.get("jeton", ""))
            mt = acces.http_json(r["url"] + "/api/metrics", m.get("jeton", ""))
            ok = "_error" not in d
            mt = mt if "_error" not in mt else {}
            return {"nom": r["nom"], "type": "cassandra", "en_ligne": ok, "erreur": d.get("_error", "") if not ok else "", "cpu": mt.get("cpu"), "ram": mt.get("ram"), "disque": mt.get("disk"), "sante": d.get("health_score")}
        res, pool = [], concurrent.futures.ThreadPoolExecutor(max_workers=10)
        try:
            futs = {pool.submit(une, r): r for r in actives}
            try:
                for f in concurrent.futures.as_completed(futs, timeout=limite):
                    try:
                        res.append(f.result(timeout=1))
                    except Exception as ex:
                        res.append({"nom": futs[f]["nom"], "type": futs[f]["type"], "en_ligne": False, "erreur": str(ex)[:120]})
            except concurrent.futures.TimeoutError:
                pass
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
        faits = {r["nom"] for r in res}
        for r in actives:
            if r["nom"] not in faits:
                res.append({"nom": r["nom"], "type": r["type"], "en_ligne": False, "erreur": "délai dépassé (%d s) — machine injoignable ou très lente" % limite})
        maintenant, transitions = o.horodate(), []
        vus = {r["nom"]: r for r in db.lire("SELECT nom, en_ligne, depuis FROM vus")}
        for e in sorted(res, key=lambda x: x["nom"]):
            n = o.nom(e["nom"])
            en = 1 if e["en_ligne"] else 0
            p = live.get(n)
            if isinstance(p, dict) and "online" in p:
                en = 1 if p["online"] else 0                                      # Tailscale d'abord : la sonde mesure, elle ne décide pas de la présence
            db.ecrire("INSERT INTO mesures(ts, nom, type, en_ligne, cpu, ram, disque, sante, erreur) VALUES (?,?,?,?,?,?,?,?,?)",
                      (maintenant, n, e["type"], en, o.mesure(e.get("cpu")), o.mesure(e.get("ram")), o.mesure(e.get("disque")), o.mesure(e.get("sante")), str(e.get("erreur") or "")[:400]))
            av = vus.get(n)
            if av is None:
                db.ecrire("INSERT OR REPLACE INTO vus(nom, en_ligne, depuis, ts) VALUES (?,?,?,?)", (n, en, maintenant, maintenant))
                evt(n, "decouverte", "Première observation — %s" % ("en ligne" if en else "hors ligne"), ts=maintenant)
            elif av["en_ligne"] == en:
                db.ecrire("UPDATE vus SET ts=? WHERE nom=?", (maintenant, n))
            else:
                dm = o.minutes_entre(av["depuis"], maintenant)
                db.ecrire("INSERT OR REPLACE INTO vus(nom, en_ligne, depuis, ts) VALUES (?,?,?,?)", (n, en, maintenant, maintenant))
                evt(n, "retour" if en else "perte", ("Revenue après %s." % o.duree(dm)) if en else "Ne répond plus : %s" % (e.get("erreur") or "hors ligne"), dm, maintenant)
                transitions.append((n, bool(en), dm))
        return transitions

    def passe_presence_tailscale(live, eng, registre_noms):
        """Une ligne par machine vue par Tailscale (hors registre, que la passe du registre couvre, et hors retirées), transitions datées, disparues, oubli."""
        maintenant, transitions, disparues, oubliees = o.horodate(), [], [], []
        vus = {r["nom"]: r for r in db.lire("SELECT nom, en_ligne, depuis, ts FROM vus")}
        for n, p in live.items():
            if n.startswith("_") or p.get("self") or n in registre_noms or eng.get(n, ("", ""))[0] == "retiree":
                continue
            en = 1 if p.get("online") else 0
            db.ecrire("INSERT INTO mesures(ts, nom, type, en_ligne, erreur) VALUES (?,?,?,?,?)", (maintenant, n, "signal", en, ""))
            av = vus.get(n)
            if av is None:
                db.ecrire("INSERT OR REPLACE INTO vus(nom, en_ligne, depuis, ts) VALUES (?,?,?,?)", (n, en, maintenant, maintenant))
                evt(n, "decouverte", "Première observation par Tailscale — %s" % ("en ligne" if en else "hors ligne"), ts=maintenant)
            elif av["en_ligne"] == en:
                db.ecrire("UPDATE vus SET ts=? WHERE nom=?", (maintenant, n))
            else:
                dm = o.minutes_entre(av["depuis"], maintenant)
                db.ecrire("INSERT OR REPLACE INTO vus(nom, en_ligne, depuis, ts) VALUES (?,?,?,?)", (n, en, maintenant, maintenant))
                evt(n, "retour" if en else "perte", ("Revenue sur le tailnet après %s." % o.duree(dm)) if en else "Hors du tailnet (Tailscale).", dm, maintenant)
                transitions.append((n, bool(en), dm))
        seuil = o.horodate(o.utc() - timedelta(days=o.OUBLI_JOURS))
        for n, av in vus.items():
            if n in live or n in registre_noms or eng.get(n, ("", ""))[0] == "retiree":
                continue
            if av["en_ligne"]:
                db.ecrire("UPDATE vus SET en_ligne=0, depuis=? WHERE nom=?", (av["ts"] or maintenant, n))
                evt(n, "disparition", "N'est plus dans la liste Tailscale (renommée ou retirée du tailnet) ; dernière trace le %s." % str(av["ts"] or "")[:16], ts=maintenant)
                disparues.append(n)
            elif av["ts"] and str(av["ts"]) < seuil:
                oubliees.append(n)
        for n in oubliees:
            oublier_traces(n, "d'elle-même, sans trace depuis %d jours" % o.OUBLI_JOURS)
        return transitions, disparues, oubliees

    def passe_sonde_ssh(live, eng, registre_ssh):
        """La sonde de contrôle : pour chaque pair Linux EN LIGNE, hors hôte, hors registre SSH et hors retirées, un ssh sans identité. Rien d'écrit au registre, aucun secret ; une transition par obtention ou perte."""
        users = [u.strip() for u in str(reglage("sonde_utilisateurs", "root")).split(",") if u.strip()] or ["root"]
        avant = {r["nom"]: r for r in db.lire("SELECT * FROM sonde_ssh")}
        maintenant, transitions = o.horodate(), []
        for n, p in live.items():
            if n.startswith("_") or p.get("self") or n in registre_ssh or eng.get(n, ("", ""))[0] == "retiree":
                continue
            if not p.get("online") or "linux" not in str(p.get("os") or "").lower():
                continue
            ok, user, detail = False, "", ""
            for u in users:
                ok, detail = acces.ssh_sonde(p.get("ip", ""), u)
                if ok:
                    user = u
                    break
            db.ecrire("INSERT OR REPLACE INTO sonde_ssh(nom, ok, utilisateur, ip, detail, ts) VALUES (?,?,?,?,?,?)", (n, 1 if ok else 0, user, p.get("ip", ""), detail, maintenant))
            a = avant.get(n)
            if (a is None and ok) or (a is not None and bool(a["ok"]) != ok):
                evt(n, "controle", ("Contrôle SSH obtenu par Tailscale (%s), sans clé déclarée." % user) if ok else ("Contrôle SSH par Tailscale perdu : %s" % detail), ts=maintenant)
                transitions.append((n, ok, user, detail))
        return transitions

    def presence(c):
        if not reglage("presence_active", True):
            return {"desactivee": True}
        live, eng = acces.tailscale_live(), engagements()
        reg = registre()
        noms = {o.nom(r["nom"]) for r in reg}
        ssh = {o.nom(r["nom"]) for r in reg if r["type"] == "ssh"}
        t1, disparues, oubliees = passe_presence_tailscale(live, eng, noms)
        t2 = passe_registre() or []
        sondes = passe_sonde_ssh(live, eng, ssh)
        for n, en, dm in t1 + t2:
            if eng.get(n, ("", ""))[0] == "intermittente":
                continue
            ctx.emettre("serveur.retour" if en else "serveur.perte", objet=("serveur", n), donnees={"nom": n, "duree_min": dm})
        for n in disparues:
            ctx.emettre("serveur.disparition", objet=("serveur", n), donnees={"nom": n})
        for n, ok, user, detail in sondes:
            ctx.emettre("serveur.controle", objet=("serveur", n), donnees={"nom": n, "ok": ok, "utilisateur": user, "detail": detail})
        return {"transitions": len(t1) + len(t2), "sondes": len(sondes), "disparues": len(disparues), "oubliees": len(oubliees)}

    def releve(c):
        """Toutes les 15 minutes, une sonde SSH par machine contrôlable : ce qui compte (disques, mémoire, charge, redémarrage, services en échec, RAID, température), daté. Une machine injoignable le dit, ses anciens relevés gardent leur âge."""
        faits = 0
        cibles = {r["nom"]: dict(r) for r in db.lire("SELECT * FROM machines WHERE actif=1 AND type='ssh'")}
        for r in db.lire("SELECT * FROM sonde_ssh WHERE ok=1"):
            cibles.setdefault(r["nom"], {"nom": r["nom"], "type": "ssh", "hote": r["ip"], "port": 22, "utilisateur": r["utilisateur"] or "root", "auth": "tailscale", "systeme": "linux"})
        for n, m in cibles.items():
            m = dict(m)
            m.update(secrets_de(m))
            windows = str(m.get("systeme") or "").lower() == "windows"
            out, err, rc = acces.ssh_exec(m, o.commande_sonde(windows), 40)
            maintenant = o.horodate()
            if rc != 0 and not out:
                db.ecrire("INSERT OR REPLACE INTO releves(nom, cle, valeur, gravite, ts) VALUES (?,?,?,?,?)", (n, "joignable", "injoignable : %s" % (err or "sans réponse").strip()[:100], "warning", maintenant))
                continue
            lignes = o.lire_sortie(out, ctx.point)
            lignes.append(("joignable", "oui", "info"))
            db.ecrire("DELETE FROM releves WHERE nom=? AND cle LIKE 'disque.%'", (n,))
            for k, v, g in lignes:
                db.ecrire("INSERT OR REPLACE INTO releves(nom, cle, valeur, gravite, ts) VALUES (?,?,?,?,?)", (n, k, v, g, maintenant))
            faits += 1
        return {"machines": faits}

    def det_muettes(c):
        """Une machine ATTENDUE qui ne répond plus."""
        try:
            p = parc(c)
        except Exception:
            return []
        out = []
        for m in p["machines"]:
            if m["etat"] == "erreur":
                out.append({"objet": ("serveur", m["nom"]), "titre": "%s est attendue et ne répond plus" % m["nom"], "detail": "Dernier contact %s." % ((m.get("dernier_contact") or "inconnu")[:16]), "niveau": "critique"})
        return out

    c = ctx
    c.moteur("presence", presence)
    c.moteur("releve", releve)
    c.detecteur("machine_muette", det_muettes)
    for cid, f in (("parc", parc), ("verdict", verdict), ("machines", machines), ("historique", historique), ("disponibilite", disponibilite), ("serie", serie), ("evenements", evenements), ("liens", liens),
                   ("actions", actions), ("ping", ping), ("diagnostic", diagnostic)):
        c.implementer(cid, f)
    c.implementer("machine_ajouter", machine_ajouter, prouver_machine, defaire_machine_ajoutee, simuler=lambda x, nom="", **_: "déclarerait la machine « %s » au registre" % nom)
    c.implementer("machine_retirer", machine_retirer, prouver_retiree, defaire_retiree, simuler=lambda x, nom="", **_: "retirerait la machine « %s » du registre" % nom)
    c.implementer("machine_basculer", machine_basculer, prouver_bascule, defaire_bascule, simuler=lambda x, nom="", actif=True, **_: "%s la machine « %s »" % ("activerait" if actif else "suspendrait", nom))
    c.implementer("engagement", engagement, prouver_engagement, defaire_engagement, simuler=lambda x, nom="", statut="", niveau="", **_: "poserait sur « %s » : %s %s" % (nom, statut, niveau))
    c.implementer("lien_enregistrer", lien_enregistrer, prouver_lien, defaire_lien, simuler=lambda x, nom="", genre="", ref="", **_: "lierait « %s » à %s %s" % (nom, genre, ref))
    c.implementer("lien_retirer", lien_retirer, prouver_lien_retire, defaire_lien_retire, simuler=lambda x, nom="", **_: "retirerait un lien de « %s »" % nom)
    c.implementer("oublier", oublier, prouver_oubli, defaire_oubli, simuler=lambda x, nom="", **_: "effacerait les traces de « %s » (l'historique reste)" % nom)
    c.implementer("service_agir", service_agir, prouver_service, defaire_service, simuler=lambda x, nom="", action="", service="", **_: "lancerait %s %s sur « %s »" % (action, service, nom))
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
