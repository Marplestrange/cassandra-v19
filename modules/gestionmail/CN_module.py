# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Gestion e-mail
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : gestionmail
# ZONE       : CN
# VERSION CN : 0.1.0  #afc79f
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Gestion e-mail : les boîtes e-mail du serveur, lues par le panneau détecté.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=afc79f ▼▼▼
"""Gestion e-mail : les boîtes e-mail du serveur, lues par le panneau détecté.

Ce module ne nomme aucun panneau. Il demande à Panel Detect quelle capacité sert la fonction « courrier » et lit la réponse pour le compte
qui regarde. Il est en lecture seule : le panneau ne sert, pour l'instant, ni création de boîte ni renvois.

Trois états, dits tels quels à l'écran, jamais confondus :
  - « absent » : aucun panneau piloté ne sert les boîtes (pas de panneau, deux panneaux, ou un panneau sans module) ;
  - « muet »   : le panneau les sert mais n'a pas répondu (ce n'est pas « aucune boîte ») ;
  - « ok »     : la liste, éventuellement vide.
"""
from __future__ import annotations

SEUIL_PRESQUE_PLEINE = 90.0                                           # en pour cent du quota


def _liste(valeur) -> list:
    if isinstance(valeur, dict):
        valeur = valeur.get("boites") or valeur.get("items") or []
    return [x for x in (valeur or []) if isinstance(x, dict)]


def _nombre(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def brancher(ctx):
    def lire(c):
        """(état, valeur) : « absent » (aucune route ou refus de droit), « muet » (la capacité ne répond pas), « ok »."""
        try:
            r = c.executer_lecture("paneldetect.route", fonction="courrier")
        except PermissionError:
            return "absent", None                                      # Panel Detect n'est pas là : comme un panneau absent
        cap = str(r.get("capacite") or "") if isinstance(r, dict) else ""
        if not cap:
            return "absent", None
        try:
            v = c.executer_lecture(cap)
        except PermissionError:
            return "absent", None
        return ("ok", v) if v is not None else ("muet", None)

    def boite(x: dict) -> dict:
        adresse = str(x.get("adresse") or "").strip()
        domaine = str(x.get("domaine") or "").strip() or (adresse.split("@", 1)[1] if "@" in adresse else "")
        quota, utilise = _nombre(x.get("quota_mo")), _nombre(x.get("utilise_mo"))
        pct = round(100.0 * utilise / quota, 1) if quota > 0 else None   # sans quota connu, aucun pourcentage n'est inventé
        statut = str(x.get("statut") or "active")
        return {"adresse": adresse, "domaine": domaine, "quota_mo": quota or None, "utilise_mo": utilise, "pct": pct, "statut": statut,
                "presque_pleine": pct is not None and pct >= SEUIL_PRESQUE_PLEINE, "suspendue": statut != "active"}

    def lister(c):
        etat, brut = lire(c)
        boites = sorted((b for b in (boite(x) for x in _liste(brut)) if b["adresse"]), key=lambda b: b["adresse"].lower())
        domaines: dict[str, dict] = {}
        for b in boites:
            d = domaines.setdefault(b["domaine"], {"domaine": b["domaine"], "boites": 0, "utilise_mo": 0.0})
            d["boites"] += 1
            d["utilise_mo"] = round(d["utilise_mo"] + b["utilise_mo"], 1)
        return {"etat": etat, "boites": boites, "domaines": sorted(domaines.values(), key=lambda d: d["domaine"].lower()),
                "total_mo": round(sum(b["utilise_mo"] for b in boites), 1), "pleines": sum(1 for b in boites if b["presque_pleine"]),
                "suspendues": sum(1 for b in boites if b["suspendue"])}

    ctx.implementer("lister", lister)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _liste, _nombre, brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
