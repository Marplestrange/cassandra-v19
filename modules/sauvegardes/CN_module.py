# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Les sauvegardes
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : sauvegardes
# ZONE       : CN
# VERSION CN : 0.1.0  #b1dff5
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Les sauvegardes : les plans, l'historique des copies, les destinations, la couverture.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=b1dff5 ▼▼▼
"""Les sauvegardes : les plans, l'historique des copies, les destinations, la couverture.

Porté de la V18 (`sauv_*`), avec ses leçons :
  - une portée décide du moteur : un site ou une base passe par FastPanel (lui seul fige proprement), le reste par rclone ;
  - l'état d'une sauvegarde se juge à l'ÂGE, jamais à l'existence : une destination qui s'est tue est le pire scénario ;
  - sans rotation, une sauvegarde datée remplit la destination jusqu'au quota puis échoue en silence.

Différé proprement : l'exécution rclone (plan_run, verifier, purger, restaurer) et la planification (tick) — elles
passent par le courtier racine et les outils système, pas par ce module.
"""
from __future__ import annotations

from datetime import datetime

PORTEES = ("doc", "site", "db", "systeme")
RYTHMES = ("quotidien", "hebdomadaire", "mensuel")


def _age_h(ts):
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            d = datetime.strptime(str(ts)[:19].replace("T", " "), fmt)
            return max(0.0, (datetime.now() - d).total_seconds() / 3600.0)
        except Exception:
            continue
    return None


_point = None          # posé par brancher() : les points d'évolution du module (ctx.point)


def _age_mot(h):
    """_age_mot. Le calcul est un POINT D'ÉVOLUTION : points/EC_age_mot.py."""
    return _point("age_mot", {"h": h})["valeur"]


def _etat(h, seuil_h=24.0):
    """_etat. Le calcul est un POINT D'ÉVOLUTION : points/EC_etat.py."""
    return _point("etat", {"h": h, "seuil_h": seuil_h})["valeur"]


def brancher(ctx):
    global _point
    _point = ctx.point
    db = ctx.stockage

    def _plan(pid):
        r = db.lire("SELECT * FROM sauv_plans WHERE id=?", (int(pid),))
        return dict(r[0]) if r else None

    def _octets(n):
        n = float(n or 0)
        for u in ("o", "Ko", "Mo", "Go", "To"):
            if n < 1024 or u == "To":
                return ("%.0f %s" % (n, u)) if u == "o" else ("%.1f %s" % (n, u))
            n /= 1024.0
        return "%.0f o" % n

    # ── lectures ─────────────────────────────────────────────────────────────
    def plans(c):
        out = []
        for r in db.lire("SELECT * FROM sauv_plans ORDER BY id"):
            p = dict(r)
            p["age_h"] = _age_h(p.get("dernier"))
            p["age"] = _age_mot(p["age_h"])
            p["etat"] = _etat(p["age_h"])
            out.append(p)
        return {"plans": out}

    def copies(c, plan_id=0):
        if int(plan_id or 0):
            rows = db.lire("SELECT * FROM sauv_copies WHERE plan_id=? ORDER BY id DESC LIMIT 200", (int(plan_id),))
        else:
            rows = db.lire("SELECT * FROM sauv_copies ORDER BY id DESC LIMIT 200")
        for r in rows:
            r["octets_h"] = _octets(r.get("octets"))
        return {"copies": rows}

    def destinations(c):
        out, vus = [], set()
        for r in db.lire("SELECT destination FROM sauv_plans WHERE destination<>''"):
            d = str(r["destination"]).rstrip("/")
            if d and d not in vus:
                vus.add(d)
                out.append(d)
        return {"destinations": sorted(out)}

    def couverture(c):
        par_portee = {}
        for r in db.lire("SELECT portee, COUNT(*) AS n FROM sauv_plans WHERE actif=1 GROUP BY portee"):
            par_portee[r["portee"]] = r["n"]
        sans = [p for p in PORTEES if not par_portee.get(p)]
        return {"par_portee": par_portee, "non_couverts": sans,
                "total": sum(par_portee.values())}

    # ── écritures réversibles ────────────────────────────────────────────────
    def plan_save(c, **d):
        nom = str(d.get("nom", "")).strip()[:80]
        portee = str(d.get("portee", "doc")).strip().lower()
        source = str(d.get("source", "")).strip()
        dest = str(d.get("destination", "")).strip()
        rythme = str(d.get("rythme", "")).strip().lower()
        if not nom:
            raise ValueError("nom du plan requis")
        if portee not in PORTEES:
            raise ValueError("portée inconnue (%s)" % ", ".join(PORTEES))
        if rythme and rythme not in RYTHMES:
            raise ValueError("rythme inconnu (%s, ou vide pour manuel)" % ", ".join(RYTHMES))
        if not source or not dest:
            raise ValueError("source et destination requises")
        moteur = "fastpanel" if portee in ("site", "db") else "rclone"
        champs = ("nom", "portee", "source", "destination", "moteur", "rythme", "heure",
                  "garder", "date_dossier", "verifier", "actif")
        vals = (nom, portee, source, dest, moteur, rythme,
                str(d.get("heure", "03:30"))[:5], int(d.get("garder", 7) or 7),
                1 if d.get("date_dossier", 1) else 0, 1 if d.get("verifier", 1) else 0,
                1 if d.get("actif", 1) else 0)
        avant = _plan(int(d["id"])) if d.get("id") else None
        if d.get("id"):
            db.ecrire("UPDATE sauv_plans SET " + ", ".join("%s=?" % c for c in champs) + " WHERE id=?",
                      vals + (int(d["id"]),))
            pid = int(d["id"])
        else:
            pid = db.ecrire("INSERT INTO sauv_plans (" + ",".join(champs) + ") VALUES (" + ",".join("?" * len(champs)) + ")", vals)
        return {"id": pid, "avant": avant, "moteur": moteur}

    def prouver_plan(c, res):
        return bool(_plan(res["id"]))

    def defaire_plan(c, res):
        if res.get("avant") is None:
            db.ecrire("DELETE FROM sauv_plans WHERE id=?", (res["id"],))
        else:
            a = res["avant"]
            champs = ("nom", "portee", "source", "destination", "moteur", "rythme", "heure",
                      "garder", "date_dossier", "verifier", "actif")
            db.ecrire("UPDATE sauv_plans SET " + ", ".join("%s=?" % c for c in champs) + " WHERE id=?",
                      tuple(a[c] for c in champs) + (res["id"],))

    def plan_delete(c, pid=0):
        avant = _plan(int(pid))
        if not avant:
            raise ValueError("plan introuvable")
        db.ecrire("DELETE FROM sauv_plans WHERE id=?", (int(pid),))
        db.ecrire("DELETE FROM sauv_copies WHERE plan_id=?", (int(pid),))
        return {"id": int(pid), "avant": avant}

    def prouver_plan_delete(c, res):
        return not _plan(res["id"])

    def defaire_plan_delete(c, res):
        a = res["avant"]
        db.ecrire("INSERT INTO sauv_plans (id, nom, portee, source, destination, moteur, rythme, heure, garder, date_dossier, verifier, actif, dernier, dernier_res) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (a["id"], a["nom"], a["portee"], a["source"], a["destination"], a["moteur"], a["rythme"],
                   a["heure"], a["garder"], a["date_dossier"], a["verifier"], a["actif"], a["dernier"], a["dernier_res"]))

    def _dest_datee(p):
        d = str(p.get("destination") or "").rstrip("/")
        if p.get("date_dossier"):
            return d + "/" + datetime.now().strftime("%Y-%m-%d")
        return d

    def plan_run(c, pid=0, blanc=True):
        p = _plan(int(pid))
        if not p:
            raise ValueError("plan introuvable")
        if p.get("moteur") == "fastpanel":
            raise ValueError("ce plan est exécuté par FastPanel — lancez-le depuis le panneau")
        cible = _dest_datee(p)
        r = ctx.racine("copier", [p["source"], cible, "1" if blanc else "0"], delai=1800)
        sortie = (r.get("sortie") or "") + (r.get("erreur") or "")
        copies = len(re.findall(r"(?mi)\bCopied\b", sortie))
        res = ("test à blanc : %d à copier" % copies) if blanc else ("%d copié(s)" % copies)
        if not r.get("ok"):
            res = "échec — " + ((sortie.strip().splitlines() or ["?"])[-1][:160])
        cid = db.ecrire("INSERT INTO sauv_copies (plan_id, resultat, fichiers, octets, duree, destination, blanc, sortie) VALUES (?,?,?,?,?,?,?,?)",
                        (int(pid), res, copies, 0, 0, cible, 1 if blanc else 0, sortie[-4000:]))
        if not blanc:
            db.ecrire("UPDATE sauv_plans SET dernier=datetime('now'), dernier_res=? WHERE id=?", (res, int(pid)))
        return {"ok": r.get("ok"), "blanc": bool(blanc), "resultat": res, "copies": copies, "copie_id": cid,
                "sortie": sortie[-2000:]}

    def prouver_run(c, res):
        return bool(db.lire("SELECT 1 FROM sauv_copies WHERE id=?", (res["copie_id"],)))

    def defaire_run(c, res):
        db.ecrire("DELETE FROM sauv_copies WHERE id=?", (res["copie_id"],))

    # ── enregistrement ──────────────────────────────────────────────────────
    for cid, f in (("plans", plans), ("copies", copies), ("destinations", destinations), ("couverture", couverture)):
        ctx.implementer(cid, f)
    ctx.implementer("plan_save", plan_save, prouver_plan, defaire_plan,
                    simuler=lambda x, nom="", **_: "enregistrerait le plan « %s »" % nom)
    ctx.implementer("plan_delete", plan_delete, prouver_plan_delete, defaire_plan_delete,
                    simuler=lambda x, pid=0, **_: "supprimerait le plan %s" % pid)
    ctx.implementer("plan_run", plan_run, prouver_run, defaire_run,
                    simuler=lambda x, pid=0, **_: "exécuterait le plan %s" % pid)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _age_h, _age_mot, _etat, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
