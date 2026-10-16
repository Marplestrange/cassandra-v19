"""Le canvas de notes : les départs, les gestes, le plan.

Porté de la V18 (`cv_*`), avec ses leçons :
  - il PROPOSE, l'écran MONTRE, la personne DÉCIDE : rien n'écrit sans elle ;
  - on GARDE ce qu'on ne comprend pas (reconstruire avec les seuls champs connus efface en silence) ;
  - ce qu'on JETTE, on le DIT (une flèche dont la cible a disparu ne s'évapore pas) ;
  - un plan vide EFFACE le fichier : le laisser ferait rouvrir des cartes qu'on vient de retirer.

Différé proprement : les appels au modèle (amorcer, retoucher, cartes tirées des sources) et la section vivante.
"""
from __future__ import annotations

import json

DEPARTS = {
    "reunion": {
        "n": "Compte rendu de réunion", "ic": "📋", "c": "info", "f": "Consigner",
        "plan": "## Présents\n\n## Ce qui s'est dit\n\n## Décisions\n\n## Tâches\n",
        "sources": ("projet",), "demande": ("projet",),
        "consigne": "Rédige un compte rendu de réunion en suivant EXACTEMENT le plan donné.",
        "quand": "Vous sortez d'une réunion et vous voulez la fixer avant de l'oublier.",
        "quoi": "Reprend la réunion du projet.",
    },
    "decision": {
        "n": "Fiche de décision", "ic": "⚖️", "c": "ok", "f": "Consigner",
        "plan": "## Question\n\n## Réponse\n\n## Pourquoi\n\n## Écarté\n\n## À revoir si\n",
        "sources": ("projet",), "demande": ("projet",),
        "consigne": "Rédige une fiche de décision. « À revoir si » doit contenir un SEUIL vérifiable.",
        "quand": "Un choix vient d'être fait.",
        "quoi": "Reprend la décision du projet et son seuil de révision.",
    },
    "lecture": {
        "n": "Note de lecture", "ic": "📖", "c": "vio", "f": "Consigner",
        "plan": "## Source\n\n## Ce que j'en retiens\n\n## Citations\n\n## À relire le\n",
        "sources": ("doc", "site"), "demande": (),
        "consigne": "Rends compte de la lecture, sans rien attribuer que le document ne dise.",
        "quand": "Vous venez de lire quelque chose.",
        "quoi": "Lit le document déposé ou la page relevée.",
    },
    "procedure": {
        "n": "Procédure", "ic": "🧭", "c": "warn", "f": "Fabriquer",
        "plan": "## But\n\n## Prérequis\n\n## Étapes\n\n## Retour arrière\n",
        "sources": ("journal",), "demande": (),
        "consigne": "Écris la procédure d'après ce qui a RÉELLEMENT été fait.",
        "quand": "Vous voulez pouvoir refaire ou défaire.",
        "quoi": "Reprend ce qui a réellement été fait.",
    },
}

GESTES = {
    "reformuler": {"n": "Reformuler", "pose": "remplace",
                   "dir": "Réécris le passage en gardant EXACTEMENT le même sens. Ne rends que le passage réécrit."},
    "resserrer": {"n": "Resserrer", "pose": "remplace",
                  "dir": "Resserre le passage : même sens, moins de mots. Ne rends que le passage resserré."},
    "developper": {"n": "Développer", "pose": "remplace",
                   "dir": "Développe le passage en explicitant ce qu'il sous-entend. Ne rends que le passage développé."},
    "continuer": {"n": "Continuer", "pose": "dessous",
                  "dir": "Écris LA SUITE du texte, dans la même voix. Ne rends que la suite."},
    "resumer": {"n": "Résumer en tête", "pose": "entete",
                "dir": "Rends un résumé de trois lignes au plus, à poser en tête de la note."},
}

PL_MAX = 200
PL_OCTETS = 900000
PL_TYPES = ("text", "file", "link", "group")


def _nombre(v, defaut=0):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return defaut


def _plan_valider(d, soucis=None):
    """Ce qu'on accepte d'écrire. Rend le plan NETTOYÉ, ou lève."""
    if soucis is None:
        soucis = []
    if not isinstance(d, dict):
        raise ValueError("le plan n'est pas un objet")
    nds, edg = d.get("nodes"), d.get("edges")
    nds = nds if isinstance(nds, list) else []
    edg = edg if isinstance(edg, list) else []
    if len(nds) > PL_MAX:
        raise ValueError("au-delà de %d cartes : réduisez le plan plutôt que d'en perdre la moitié" % PL_MAX)
    vus, propres = set(), []
    for x in nds:
        if not isinstance(x, dict):
            soucis.append("une entrée de `nodes` n'est pas un objet : ignorée")
            continue
        i = str(x.get("id") or "")[:64]
        t = str(x.get("type") or "text")
        if not i:
            soucis.append("une carte sans identifiant : ignorée")
            continue
        if i in vus:
            soucis.append("deux cartes portent l'identifiant « %s » : la seconde est ignorée" % i)
            continue
        if t not in PL_TYPES:
            soucis.append("carte « %s » de type « %s », hors spécification : ignorée" % (i, t))
            continue
        vus.add(i)
        n = dict(x)
        n["id"], n["type"] = i, t
        n["x"], n["y"] = _nombre(x.get("x")), _nombre(x.get("y"))
        n["width"] = max(40, min(4000, _nombre(x.get("width"), 200)))
        n["height"] = max(30, min(4000, _nombre(x.get("height"), 100)))
        if x.get("color") is not None:
            n["color"] = str(x["color"])[:24]
        if t == "text":
            n["text"] = str(x.get("text") or "")[:8000]
        elif t == "file":
            n["file"] = str(x.get("file") or "")[:200]
        elif t == "link":
            n["url"] = str(x.get("url") or "")[:200]
        elif t == "group":
            n["label"] = str(x.get("label") or "")[:200]
        propres.append(n)
    fl = []
    for e in edg:
        if not isinstance(e, dict):
            continue
        a, b = str(e.get("fromNode") or ""), str(e.get("toNode") or "")
        if a not in vus or b not in vus:
            soucis.append("une flèche vers une carte disparue est retirée (%s → %s)" % (a or "?", b or "?"))
            continue
        e = dict(e)
        e["fromNode"], e["toNode"] = a, b
        fl.append(e)
    return {"nodes": propres, "edges": fl}


def brancher(ctx):
    db = ctx.stockage

    def departs(c):
        return {"departs": [dict(v, cle=k) for k, v in DEPARTS.items()]}

    def gestes(c):
        return {"gestes": [{"cle": k, "n": v["n"], "pose": v["pose"]} for k, v in GESTES.items()]}

    def plan_lire(c, ref=""):
        ref = str(ref or "").strip()
        if not ref:
            raise ValueError("référence de note requise")
        r = db.lire("SELECT plan FROM cv_plans WHERE ref=?", (ref,))
        if not r:
            return {"plan": {"nodes": [], "edges": []}, "neuf": True}
        try:
            d = json.loads(r[0]["plan"])
        except ValueError:
            return {"plan": {"nodes": [], "edges": []}, "neuf": False, "illisible": True}
        soucis = []
        try:
            plan = _plan_valider(d, soucis)
        except ValueError as e:
            raise ValueError(str(e))
        return {"plan": plan, "neuf": False, "soucis": soucis}

    def plan_ecrire(c, ref="", plan=None):
        ref = str(ref or "").strip()
        if not ref:
            raise ValueError("référence de note requise")
        soucis = []
        propre = _plan_valider(plan if isinstance(plan, dict) else {}, soucis)
        txt = json.dumps(propre, ensure_ascii=False, indent=1)
        if len(txt.encode("utf-8")) > PL_OCTETS:
            raise ValueError("plan trop lourd : réduisez le texte des cartes plutôt qu'en perdre")
        avant = db.lire("SELECT plan FROM cv_plans WHERE ref=?", (ref,))
        if not propre["nodes"] and not propre["edges"]:
            db.ecrire("DELETE FROM cv_plans WHERE ref=?", (ref,))
            return {"ref": ref, "vide": True, "cartes": 0, "liens": 0, "soucis": soucis, "avant": (avant[0]["plan"] if avant else None)}
        db.ecrire("INSERT INTO cv_plans (ref, plan) VALUES (?,?) ON CONFLICT(ref) DO UPDATE SET plan=excluded.plan, maj=datetime('now')",
                  (ref, txt))
        return {"ref": ref, "vide": False, "soucis": soucis, "cartes": len(propre["nodes"]), "liens": len(propre["edges"]),
                "avant": (avant[0]["plan"] if avant else None)}

    def prouver_plan(c, res):
        r = db.lire("SELECT plan FROM cv_plans WHERE ref=?", (res.get("ref"),))
        return (not r) if res.get("vide") else bool(r)

    def defaire_plan(c, res):
        if res.get("avant") is None:
            db.ecrire("DELETE FROM cv_plans WHERE ref=?", (res.get("ref"),))
        else:
            db.ecrire("INSERT INTO cv_plans (ref, plan) VALUES (?,?) ON CONFLICT(ref) DO UPDATE SET plan=excluded.plan, maj=datetime('now')",
                      (res.get("ref"), res["avant"]))

    for cid, f in (("departs", departs), ("gestes", gestes), ("plan_lire", plan_lire)):
        ctx.implementer(cid, f)
    ctx.implementer("plan_ecrire", plan_ecrire, prouver_plan, defaire_plan,
                    simuler=lambda x, ref="", **_: "rangerait le plan de %s" % ref)
