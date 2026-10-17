"""Le module des mesures : lit ce que les modules déclarent ([[mesures]]) et le met en courbes, habitudes, écarts, tendance et verdict (CN_moteur.py).

Chaque module répond à sa propre capacité de lecture, {mesure, depuis, jusqu_a} -> {"series": [...]}. Ici on ne sait rien de la source : un module qui se tait
donne une mesure « muette », jamais une courbe plate."""
from datetime import datetime, timedelta

from . import CN_moteur as mo


def brancher(ctx):
    def declarees():
        """Les mesures de tous les modules actifs : {clé: déclaration}. Une clé en double est qualifiée par son module."""
        sortie = {}
        for m in sorted(ctx.manifestes_actifs(), key=lambda m: m.id):
            for d in getattr(m, "mesures", ()):
                cle = d.id if d.id not in sortie else "%s.%s" % (m.id, d.id)
                sortie[cle] = {"id": cle, "module": m.id, "local": d.id, "libelle": d.libelle, "capacite": d.capacite, "genre": d.genre, "unite": d.unite,
                               "famille": d.famille or "Autres", "agregat": d.agregat, "groupee": d.groupee, "pire": d.pire, "plafond": d.plafond, "nature": d.nature,
                               "fraicheur_s": d.fraicheur_s, "vide": d.vide, "description": d.description}
        return sortie

    def lire(m, jours, maintenant):
        """Les séries brutes d'une mesure sur `jours` jours, ou None si le module ne répond pas."""
        try:
            r = ctx.executer_lecture("%s.%s" % (m["module"], m["capacite"]), mesure=m["local"], depuis=mo.ecrire_ts(maintenant - timedelta(days=jours)), jusqu_a=mo.ecrire_ts(maintenant))
        except Exception:
            return None
        if not isinstance(r, dict) or not isinstance(r.get("series"), list):
            return None
        return r["series"]

    def une(cle):
        d = declarees()
        if cle not in d:
            raise ValueError("mesure inconnue : « %s »" % cle)
        return d[cle]

    def sources(ctx):
        maintenant = datetime.utcnow()
        fiches = [mo.fiche_source(m, lire(m, 30, maintenant), maintenant) for m in declarees().values()]
        return {"ok": True, "metrics": fiches, "periods": mo.PERIODES, "families": list(dict.fromkeys(f["family"] for f in fiches)),
                "seuil_ecart": mo.SEUIL_ECART, "habitude_jours": mo.HABITUDE_JOURS, "habitude_min": mo.HABITUDE_MIN}

    def serie(ctx, cle="", periode="24h", top=6):
        m = une(cle)
        maintenant = datetime.utcnow()
        jours = max(1, mo.PERIODES.get(periode, mo.PERIODES["24h"])["minutes"] // 1440 + 1)
        return mo.serie(m, lire(m, jours, maintenant), periode, maintenant, top)

    def profil(ctx, cle=""):
        m = une(cle)
        maintenant = datetime.utcnow()
        return mo.profil(m, lire(m, 29, maintenant), maintenant)

    def ecarts(ctx, seuil=mo.SEUIL_ECART):
        maintenant = datetime.utcnow()
        sortie = []
        for m in declarees().values():
            if m["groupee"] or m["nature"] == "etat":
                continue
            p = mo.profil(m, lire(m, 29, maintenant), maintenant)
            if p.get("enough") and p.get("deviation_pct") is not None and abs(p["deviation_pct"]) >= int(seuil):
                sortie.append({"key": m["id"], "label": m["libelle"], "family": m["famille"], "unit": m["unite"], "current": p["current"], "baseline": p["baseline"], "deviation_pct": p["deviation_pct"]})
        sortie.sort(key=lambda x: -abs(x["deviation_pct"]))
        return {"ok": True, "threshold": int(seuil), "deviations": sortie, "coinciding": []}

    def prevision(ctx, cle="disk"):
        m = une(cle)
        maintenant = datetime.utcnow()
        return mo.prevision(m, lire(m, 15, maintenant), maintenant)

    def verdict(ctx):
        maintenant = datetime.utcnow()
        d = declarees()
        return mo.verdict(list(d.values()), {k: lire(m, 29, maintenant) for k, m in d.items()}, maintenant)

    ctx.implementer("sources", sources)
    ctx.implementer("serie", serie)
    ctx.implementer("profil", profil)
    ctx.implementer("ecarts", ecarts)
    ctx.implementer("prevision", prevision)
    ctx.implementer("verdict", verdict)
