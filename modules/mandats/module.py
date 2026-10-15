"""Les mandats d'envoi : l'autorisation d'envoyer, avec ses bornes.

Porté de la V18 (`mandat_*`), avec ses leçons :
  - l'adresse ne vient JAMAIS de la demande (une adresse libre impose le mode « accord requis ») ;
  - un mandat se relit à voix haute : un réglage de permission qu'on ne peut pas relire n'est jamais vérifié ;
  - une variable employée mais non déclarée partirait littéralement dans le message : refusée à l'écriture ;
  - le journal des envois survit au mandat.

Différé proprement : la résolution du destinataire (carnet/courrier) et l'envoi réel.
"""
from __future__ import annotations

import json
import re

DECLENCHEURS = ("chat", "regle", "horaire")
SOURCES_DST = ("document", "liste", "domaine", "fil", "libre")
CONTROLES = ("auto", "differe", "accord")
TYPES_VAR = ("texte", "nombre", "date", "entier")
VAR_RE = re.compile(r"\{\{([a-z_][a-z0-9_]{0,29})\}\}")


def _lignes(v):
    return [x.strip() for x in str(v or "").split(",") if x.strip()]


def brancher(ctx):
    db = ctx.stockage

    def _get(mid):
        r = db.lire("SELECT * FROM mandats WHERE id=?", (int(mid),))
        return dict(r[0]) if r else None

    # ── lectures ─────────────────────────────────────────────────────────────
    def mandats(c):
        return {"mandats": db.lire("SELECT * FROM mandats ORDER BY id")}

    def plan(c, mid=0):
        m = _get(int(mid))
        if not m:
            raise ValueError("mandat introuvable")
        d = {"chat": "je le demande dans le chat", "regle": "une règle le décide", "horaire": "l'horaire arrive"}
        src = {"document": "contact rattaché au document", "liste": "une liste fermée",
               "domaine": "un domaine autorisé", "fil": "l'expéditeur du fil", "libre": "une adresse libre"}
        ctl = {"auto": "sans moi", "differe": "après %d min pendant lesquelles je peux l'arrêter" % int(m.get("differe_min") or 10),
               "accord": "après mon accord"}
        return {"id": m["id"], "nom": m["nom"],
                "quand": " ou ".join(d.get(x, x) for x in _lignes(m.get("declencheurs"))) or "jamais",
                "qui": src.get(m.get("dst_source"), "?") + ((" (%s)" % m["dst_valeur"]) if m.get("dst_valeur") else ""),
                "quoi": m.get("objet") or "(sans objet)",
                "piece": m.get("pj_motif") or "aucune pièce",
                "controle": ctl.get(m.get("controle"), "?"),
                "limite": "%d fois par jour" % int(m.get("quota_jour") or 0),
                "suspendu": bool(m.get("suspendu"))}

    def envois(c, mid=0, limite=100):
        if int(mid or 0):
            rows = db.lire("SELECT * FROM mandat_envois WHERE mandat_id=? ORDER BY id DESC LIMIT ?", (int(mid), max(1, min(int(limite or 100), 500))))
        else:
            rows = db.lire("SELECT * FROM mandat_envois ORDER BY id DESC LIMIT ?", (max(1, min(int(limite or 100), 500)),))
        return {"envois": rows}

    # ── écritures réversibles ────────────────────────────────────────────────
    def save(c, **d):
        if d.get("id") and not _get(d.get("id")):
            raise ValueError("mandat introuvable")
        nom = str(d.get("nom", "")).strip()[:80]
        if not nom:
            raise ValueError("nom du mandat requis")
        dec = [x for x in (d.get("declencheurs") or []) if x in DECLENCHEURS]
        if not dec:
            raise ValueError("au moins un déclencheur (%s)" % ", ".join(DECLENCHEURS))
        src = str(d.get("dst_source", "document"))
        if src not in SOURCES_DST:
            raise ValueError("source de destinataire inconnue")
        ctl = str(d.get("controle", "accord"))
        if ctl not in CONTROLES:
            raise ValueError("mode de contrôle inconnu")
        if src in ("liste", "domaine") and not str(d.get("dst_valeur", "")).strip():
            raise ValueError("cette source exige une valeur (liste ou domaine)")
        if src == "libre" and ctl != "accord":
            raise ValueError("une adresse libre impose le mode « accord requis » : sans cela le destinataire viendrait de la demande")
        variables, declarees = [], set()
        for v in (d.get("variables") or [])[:12]:
            n = str((v or {}).get("nom", "")).strip().lower()
            if not re.match(r"^[a-z_][a-z0-9_]{0,29}$", n):
                raise ValueError("nom de variable invalide : « %s »" % n)
            t = str(v.get("type", "texte"))
            if t not in TYPES_VAR:
                raise ValueError("type inconnu pour {{%s}}" % n)
            declarees.add(n)
            variables.append({"nom": n, "type": t, "source": str(v.get("source", "agent"))[:40],
                              "max": min(200, int(v.get("max", 60) or 60))})
        utilisees = set(VAR_RE.findall(str(d.get("objet", "")) + "\n" + str(d.get("corps", ""))))
        manquantes = utilisees - declarees
        if manquantes:
            raise ValueError("variables employées mais non déclarées : %s" % ", ".join("{{%s}}" % x for x in sorted(manquantes)))
        champs = ("nom", "actif", "declencheurs", "dst_source", "dst_valeur", "objet", "corps",
                  "variables", "libre", "libre_max", "pj_dossier", "pj_motif", "pj_types",
                  "pj_max", "pj_obligatoire", "controle", "differe_min",
                  "quota_jour", "dst_max", "heure_debut", "heure_fin", "unique_par", "suspendre_incident")
        vals = (nom, 1 if d.get("actif", 1) else 0, ",".join(dec), src,
                str(d.get("dst_valeur", ""))[:400], str(d.get("objet", ""))[:300], str(d.get("corps", ""))[:8000],
                json.dumps(variables, ensure_ascii=False),
                1 if d.get("libre") else 0, min(2000, int(d.get("libre_max", 400) or 400)),
                str(d.get("pj_dossier", "")).strip(), str(d.get("pj_motif", ""))[:200],
                str(d.get("pj_types", "pdf"))[:80], int(d.get("pj_max", 2097152) or 2097152),
                1 if d.get("pj_obligatoire", 1) else 0, ctl,
                max(1, min(1440, int(d.get("differe_min", 10) or 10))),
                max(0, min(200, int(d.get("quota_jour", 5) or 5))),
                max(1, min(20, int(d.get("dst_max", 1) or 1))),
                str(d.get("heure_debut", "08:00"))[:5], str(d.get("heure_fin", "19:00"))[:5],
                str(d.get("unique_par", ""))[:40], 1 if d.get("suspendre_incident", 1) else 0)
        avant = _get(int(d["id"])) if d.get("id") else None
        if d.get("id"):
            db.ecrire("UPDATE mandats SET " + ", ".join("%s=?" % c for c in champs) + ", suspendu='' WHERE id=?", vals + (int(d["id"]),))
            mid = int(d["id"])
        else:
            mid = db.ecrire("INSERT INTO mandats (" + ",".join(champs) + ") VALUES (" + ",".join("?" * len(champs)) + ")", vals)
        return {"id": mid, "avant": avant}

    def prouver_save(c, res):
        return bool(_get(res["id"]))

    def defaire_save(c, res):
        if res.get("avant") is None:
            db.ecrire("DELETE FROM mandats WHERE id=?", (res["id"],))
        else:
            a = res["avant"]
            champs = ("nom", "actif", "declencheurs", "dst_source", "dst_valeur", "objet", "corps",
                      "variables", "libre", "libre_max", "pj_dossier", "pj_motif", "pj_types",
                      "pj_max", "pj_obligatoire", "controle", "differe_min",
                      "quota_jour", "dst_max", "heure_debut", "heure_fin", "unique_par", "suspendre_incident", "suspendu")
            db.ecrire("UPDATE mandats SET " + ", ".join("%s=?" % c for c in champs) + " WHERE id=?",
                      tuple(a.get(c) for c in champs) + (res["id"],))

    def delete(c, mid=0):
        avant = _get(int(mid))
        if not avant:
            raise ValueError("mandat introuvable")
        db.ecrire("DELETE FROM mandats WHERE id=?", (int(mid),))
        db.ecrire("UPDATE mandat_envois SET etat='annule' WHERE mandat_id=? AND etat IN ('attente','differe')", (int(mid),))
        return {"id": int(mid), "avant": avant}

    def prouver_delete(c, res):
        return not _get(res["id"])

    def defaire_delete(c, res):
        a = res["avant"]
        champs = ("id", "nom", "actif", "declencheurs", "dst_source", "dst_valeur", "objet", "corps",
                  "variables", "libre", "libre_max", "pj_dossier", "pj_motif", "pj_types",
                  "pj_max", "pj_obligatoire", "controle", "differe_min",
                  "quota_jour", "dst_max", "heure_debut", "heure_fin", "unique_par", "suspendre_incident", "suspendu", "cree_le")
        db.ecrire("INSERT INTO mandats (" + ",".join(champs) + ") VALUES (" + ",".join("?" * len(champs)) + ")",
                  tuple(a.get(c) for c in champs))

    def suspendre(c, mid=0, motif="", reprendre=False):
        avant = _get(int(mid))
        if not avant:
            raise ValueError("mandat introuvable")
        db.ecrire("UPDATE mandats SET suspendu=? WHERE id=?",
                  ("" if reprendre else (str(motif)[:200] or "suspendu à la main"), int(mid)))
        return {"id": int(mid), "avant_suspendu": avant.get("suspendu")}

    def prouver_suspendre(c, res):
        return bool(_get(res["id"]))

    def defaire_suspendre(c, res):
        db.ecrire("UPDATE mandats SET suspendu=? WHERE id=?", (res.get("avant_suspendu") or "", res["id"]))

    for cid, f in (("mandats", mandats), ("plan", plan), ("envois", envois)):
        ctx.implementer(cid, f)
    ctx.implementer("save", save, prouver_save, defaire_save,
                    simuler=lambda x, nom="", **_: "enregistrerait le mandat « %s »" % nom)
    ctx.implementer("delete", delete, prouver_delete, defaire_delete,
                    simuler=lambda x, mid=0, **_: "supprimerait le mandat %s" % mid)
    ctx.implementer("suspendre", suspendre, prouver_suspendre, defaire_suspendre,
                    simuler=lambda x, mid=0, **_: "suspendrait le mandat %s" % mid)
