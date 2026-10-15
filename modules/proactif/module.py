"""La Proactivité : l'autonomie qui se gagne, le savoir-faire mesuré, l'ombre et les incidents.

Porté de la V18 (`pf_*`), avec ses leçons :
  - l'autonomie est un PALIER et un budget, pas un interrupteur ; un geste devient éprouvé à dix réussites
    et retombe à deux échecs d'affilée (une autonomie qui ne se retire jamais toute seule est un pari) ;
  - l'ombre est ce qu'elle AURAIT fait : rien n'est exécuté, c'est la façon honnête d'accorder de l'autonomie ;
  - un refus n'est jamais un silence : il devient une ligne dans l'ombre ;
  - un incident a un début, une cause, une chaîne et une fin PROUVÉE (toutes ses conséquences retombées),
    pas l'absence de nouvelle alerte.

Différé proprement : la porte de décision par domaine/geste (catalogue ~100 gestes), les projections/le
tableau (métriques), et le moteur d'évolution (auto-modification) — voir le module « evolution ».
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

PALIERS = ("observer", "proposer", "maitrise", "raconter")
PALIER_NOM = {
    "observer": "Observer — elle remarque et prévient, elle n'agit jamais",
    "proposer": "Proposer — elle prépare le geste et attend un appui",
    "maitrise": "Agir sur ce qu'elle maîtrise — savoir-faire éprouvés seulement",
    "raconter": "Agir puis raconter — tout ce qui est réversible",
}
SEUIL_PROMO = 10
SEUIL_RETRO = 2


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def brancher(ctx):
    db = ctx.stockage

    def _lire(nom, defaut):
        try:
            v = ctx.reglage(nom)
            return defaut if v in (None, "") else v
        except Exception:
            return defaut

    def _ecrire(nom, valeur):
        try:
            ctx.service_reglages().poser("proactif." + nom, valeur, par=ctx.compte or "")
            return True
        except Exception:
            return False

    # ── l'autonomie ─────────────────────────────────────────────────────────
    def autonomie(c):
        p = str(_lire("palier", "proposer"))
        if p not in PALIERS:
            p = "proposer"
        return {"palier": p, "palier_nom": PALIER_NOM[p],
                "budget_jour": int(_lire("budget_jour", 9) or 9),
                "pause_debut": str(_lire("pause_debut", "09:00")),
                "pause_fin": str(_lire("pause_fin", "18:00")),
                "pause": bool(_lire("pause", True)),
                "reversible": bool(_lire("reversible", True)),
                "retrograde": bool(_lire("retrograde", True)),
                "paliers": list(PALIERS), "noms": PALIER_NOM}

    def autonomie_set(c, **d):
        avant = autonomie(c)
        if "palier" in d and d["palier"] not in PALIERS:
            raise ValueError("palier inconnu (%s)" % " | ".join(PALIERS))
        if "palier" in d:
            _ecrire("palier", str(d["palier"]))
        for k in ("pause_debut", "pause_fin"):
            if k in d:
                _ecrire(k, str(d[k])[:5])
        for k in ("pause", "reversible", "retrograde"):
            if k in d:
                _ecrire(k, bool(d[k]))
        if "budget_jour" in d:
            _ecrire("budget_jour", max(0, min(100, int(d["budget_jour"] or 0))))
        return {"avant": avant, "autonomie": autonomie(c)}

    def prouver_autonomie(c, res):
        return autonomie(c) != res.get("avant")

    def defaire_autonomie(c, res):
        for k, v in (res.get("avant") or {}).items():
            if k in ("palier", "pause_debut", "pause_fin", "pause", "reversible", "retrograde", "budget_jour"):
                _ecrire(k, v)

    # ── le savoir-faire ─────────────────────────────────────────────────────
    def _savoir(signature):
        r = db.lire("SELECT * FROM proactive_playbooks WHERE signature=?", (signature,))
        return dict(r[0]) if r else None

    def savoirs(c):
        out = []
        for r in db.lire("SELECT * FROM proactive_playbooks ORDER BY successes DESC"):
            d = dict(r)
            t = (d.get("successes") or 0) + (d.get("failures") or 0)
            d["total"] = t
            d["taux"] = round(100.0 * (d.get("successes") or 0) / t) if t else 0
            d["etat"] = d.get("etat") or "proposition"
            d["promouvable"] = bool((d.get("successes") or 0) >= SEUIL_PROMO and not (d.get("echecs_suite") or 0) and d["etat"] != "auto")
            out.append(d)
        props = db.lire("SELECT * FROM pf_savoir_props WHERE etat='propose' AND vu >= 3 ORDER BY vu DESC LIMIT 6")
        return {"savoirs": out, "propositions": props, "seuil_promo": SEUIL_PROMO, "seuil_retro": SEUIL_RETRO}

    def savoir_etat(c, signature="", etat=""):
        if etat not in ("auto", "proposition", "manuel"):
            raise ValueError("état inconnu")
        sav = _savoir(signature)
        if not sav:
            raise ValueError("savoir-faire inconnu")
        if etat == "auto" and (sav.get("successes") or 0) < SEUIL_PROMO:
            raise ValueError("il faut %d réussites pour confier ce geste (actuellement %d)" % (SEUIL_PROMO, sav.get("successes") or 0))
        db.ecrire("UPDATE proactive_playbooks SET etat=?, promu_le=?, echecs_suite=0 WHERE signature=?",
                  (etat, _utcnow().strftime("%Y-%m-%d %H:%M") if etat == "auto" else "", signature))
        return {"signature": signature, "avant": sav["etat"], "etat": etat}

    def prouver_savoir_etat(c, res):
        return (_savoir(res["signature"]) or {}).get("etat") == res["etat"]

    def defaire_savoir_etat(c, res):
        db.ecrire("UPDATE proactive_playbooks SET etat=?, promu_le='', echecs_suite=0 WHERE signature=?",
                  (res["avant"], res["signature"]))

    def savoir_resultat(c, signature="", reussi=False):
        r = db.lire("SELECT etat, echecs_suite FROM proactive_playbooks WHERE signature=?", (signature,))
        suite = 0 if reussi else ((r[0]["echecs_suite"] if r else 0) or 0) + 1
        db.ecrire("UPDATE proactive_playbooks SET echecs_suite=?, successes=successes+?, failures=failures+? WHERE signature=?",
                  (suite, 1 if reussi else 0, 0 if reussi else 1, signature))
        retro = bool(r and r[0]["etat"] == "auto" and suite >= SEUIL_RETRO and bool(_lire("retrograde", True)))
        if retro:
            db.ecrire("UPDATE proactive_playbooks SET etat='proposition', promu_le='' WHERE signature=?", (signature,))
        return {"signature": signature, "reussi": bool(reussi), "retrograde": retro}

    def savoir_observe(c, signature="", action_kind="", action=""):
        if not signature or not action:
            raise ValueError("signature et action requises")
        if _savoir(signature):
            return {"deja_connu": True}
        cur = db.ecrire("UPDATE pf_savoir_props SET vu = vu + 1, dernier=datetime('now'), action=? WHERE signature=? AND etat='propose'",
                        (str(action)[:400], signature))
        if not cur:
            db.ecrire("INSERT OR IGNORE INTO pf_savoir_props (signature, action_kind, action) VALUES (?,?,?)",
                      (signature, str(action_kind or "")[:40], str(action)[:400]))
        vu = db.lire("SELECT vu FROM pf_savoir_props WHERE signature=?", (signature,))
        return {"signature": signature, "vu": vu[0]["vu"] if vu else 0, "propose": bool(vu and vu[0]["vu"] >= 3)}

    def savoir_accepter(c, signature=""):
        p = db.lire("SELECT * FROM pf_savoir_props WHERE signature=?", (signature,))
        if not p:
            raise ValueError("proposition inconnue")
        db.ecrire("INSERT OR IGNORE INTO proactive_playbooks (signature, action_kind, action, successes, failures, etat) VALUES (?,?,?,0,0,'proposition')",
                  (signature, p[0]["action_kind"], p[0]["action"]))
        db.ecrire("UPDATE pf_savoir_props SET etat='accepte' WHERE signature=?", (signature,))
        return {"signature": signature, "avant": p[0]["etat"]}

    def prouver_savoir_accepter(c, res):
        return bool(_savoir(res["signature"]))

    def defaire_savoir_accepter(c, res):
        db.ecrire("DELETE FROM proactive_playbooks WHERE signature=?", (res["signature"],))
        db.ecrire("UPDATE pf_savoir_props SET etat='propose' WHERE signature=?", (res["signature"],))

    def savoir_ecarter(c, signature=""):
        p = db.lire("SELECT etat FROM pf_savoir_props WHERE signature=?", (signature,))
        if not p:
            raise ValueError("proposition inconnue")
        db.ecrire("UPDATE pf_savoir_props SET etat='ecarte' WHERE signature=?", (signature,))
        return {"signature": signature, "avant": p[0]["etat"]}

    def prouver_savoir_ecarter(c, res):
        return db.lire("SELECT etat FROM pf_savoir_props WHERE signature=?", (res["signature"],))[0]["etat"] == "ecarte"

    def defaire_savoir_ecarter(c, res):
        db.ecrire("UPDATE pf_savoir_props SET etat=? WHERE signature=?", (res["avant"], res["signature"]))

    # ── l'ombre ─────────────────────────────────────────────────────────────
    def ombre_ajouter(c, fkey="", signature="", action_kind="", action="", titre="", motif=""):
        db.ecrire("INSERT INTO pf_ombre (fkey, signature, action_kind, action, titre, motif) VALUES (?,?,?,?,?,?)",
                  (str(fkey or ""), str(signature or ""), str(action_kind or ""), str(action or "")[:400],
                   str(titre or "")[:200], str(motif or "")[:250]))
        db.ecrire("DELETE FROM pf_ombre WHERE id NOT IN (SELECT id FROM pf_ombre ORDER BY id DESC LIMIT 200)")
        return {"ajoutee": True}

    def ombre(c, limit=40):
        rows = db.lire("SELECT * FROM pf_ombre ORDER BY id DESC LIMIT ?", (max(1, min(int(limit or 40), 200)),))
        return {"ombre": rows, "justes": len([r for r in rows if r.get("avis") == "juste"]),
                "discutables": len([r for r in rows if r.get("avis") == "discutable"])}

    def ombre_avis(c, oid=0, avis=""):
        if avis not in ("juste", "discutable", ""):
            raise ValueError("avis inconnu")
        avant = db.lire("SELECT avis FROM pf_ombre WHERE id=?", (int(oid),))
        if not avant:
            raise ValueError("geste de l'ombre inconnu")
        db.ecrire("UPDATE pf_ombre SET avis=? WHERE id=?", (avis, int(oid)))
        return {"oid": int(oid), "avant": avant[0]["avis"], "avis": avis}

    def prouver_ombre_avis(c, res):
        return db.lire("SELECT avis FROM pf_ombre WHERE id=?", (res["oid"],))[0]["avis"] == res["avis"]

    def defaire_ombre_avis(c, res):
        db.ecrire("UPDATE pf_ombre SET avis=? WHERE id=?", (res["avant"], res["oid"]))

    # ── les incidents ───────────────────────────────────────────────────────
    def incidents_batir(c):
        """Regroupe les découvertes ouvertes en incidents. Les découvertes viennent du noyau (constats) ;
        ici on ne fait que regrouper ce qu'on a déjà corrélé (les liens sont posés par le noyau ou l'humain)."""
        ouverts, fermes = [], []
        for inc in db.lire("SELECT * FROM pf_incidents WHERE statut='ouvert'"):
            liens = db.lire("SELECT fkey FROM pf_incident_liens WHERE incident_id=?", (inc["id"],))
            ouverts.append(inc["cle"])
        return {"ok": True, "ouverts": ouverts, "fermes": fermes}

    def incidents(c, limit=20, tout=False):
        q = "SELECT * FROM pf_incidents %s ORDER BY id DESC LIMIT ?" % ("" if tout else "WHERE statut='ouvert'")
        out = []
        for r in db.lire(q, (max(1, min(int(limit or 20), 100)),)):
            d = dict(r)
            d["chaine"] = db.lire("SELECT fkey, role, ts FROM pf_incident_liens WHERE incident_id=? ORDER BY ts", (d["id"],))
            out.append(d)
        return {"incidents": out}

    # ── le fil ──────────────────────────────────────────────────────────────
    def fil(c, heures=24, limit=80):
        depuis = (_utcnow() - timedelta(hours=max(1, min(168, int(heures or 24))))).strftime("%Y-%m-%d %H:%M:%S")
        out = []

        def _add(ts, src, couleur, titre, detail, par_elle=0, gros=0):
            if ts:
                out.append({"ts": str(ts)[:19], "source": src, "couleur": couleur, "titre": str(titre)[:180],
                            "detail": str(detail or "")[:260], "par_elle": par_elle, "gros": gros})

        for r in db.lire("SELECT * FROM pf_ombre WHERE ts >= ?", (depuis,)):
            _add(r["ts"], "OMBRE", "warn", (r["titre"] or r["signature"] or "geste retenu"), r["motif"])
        for r in db.lire("SELECT * FROM pf_incidents WHERE ouvert_le >= ? OR ferme_le >= ?", (depuis, depuis)):
            _add(r["ouvert_le"], "INCIDENT", "danger", "Incident : " + str(r["cause"]), str(r["titre"]), 0, 1)
            if r["ferme_le"]:
                _add(r["ferme_le"], "INCIDENT", "ok", "Incident clos : " + str(r["cause"]), str(r["preuve"] or ""), 0, 1)
        for r in db.lire("SELECT * FROM proactive_playbooks WHERE promu_le >= ?", (depuis,)):
            _add(r["promu_le"], "SAVOIR", "ok", "Savoir-faire confié : " + str(r["signature"]), "éprouvé à %d réussites" % (r["successes"] or 0), 1, 1)
        out.sort(key=lambda x: x["ts"], reverse=True)
        return {"fil": out[:int(limit)], "par_elle": len([x for x in out if x["par_elle"]])}

    # ── enregistrement ──────────────────────────────────────────────────────
    for cid, f in (("autonomie", autonomie), ("savoirs", savoirs), ("ombre", ombre),
                   ("incidents", incidents), ("fil", fil)):
        ctx.implementer(cid, f)
    ctx.implementer("autonomie_set", autonomie_set, prouver_autonomie, defaire_autonomie,
                    simuler=lambda x, **_: "réglerait l'autonomie")
    ctx.implementer("savoir_etat", savoir_etat, prouver_savoir_etat, defaire_savoir_etat,
                    simuler=lambda x, signature="", etat="", **_: "passerait « %s » à %s" % (signature, etat))
    ctx.implementer("savoir_accepter", savoir_accepter, prouver_savoir_accepter, defaire_savoir_accepter,
                    simuler=lambda x, signature="", **_: "accepterait le savoir-faire « %s »" % signature)
    ctx.implementer("savoir_ecarter", savoir_ecarter, prouver_savoir_ecarter, defaire_savoir_ecarter,
                    simuler=lambda x, signature="", **_: "écarterait la proposition « %s »" % signature)
    ctx.implementer("ombre_avis", ombre_avis, prouver_ombre_avis, defaire_ombre_avis,
                    simuler=lambda x, oid=0, avis="", **_: "jugerait le geste %s : %s" % (oid, avis))
