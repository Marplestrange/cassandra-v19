"""Sentinelle du disque : l'exemple le plus court d'une greffe.

Un moteur périodique mesure, un détecteur ouvre un constat, un type d'objet donne une fiche au registre.
Rien ici n'ouvre de thread, n'importe un autre module ni n'écrit hors de ce que le manifeste déclare.
"""
import shutil

SEUIL = 90.0


def brancher(ctx):
    def mesurer(ctx):
        u = shutil.disk_usage("/")
        pct = round(100.0 * u.used / u.total, 1)
        ctx.poser("disque", "/", "Disque racine", etat="plein" if pct >= SEUIL else "ok",
                  donnees={"pct": pct, "libre_go": round(u.free / 2 ** 30, 1)})
        ctx.emettre("disque.mesure", objet=("disque", "/"), donnees={"pct": pct})

    def plein(ctx):
        d = ctx.lire("disque", "/", portee=ctx.TOUT)
        if d and d["etat"] == "plein":
            return [{"objet": ("disque", "/"), "titre": "Disque racine occupé à %s %%" % d["donnees"]["pct"]}]
        return []

    def lire_mesure(ctx):
        d = ctx.lire("disque", "/", portee=ctx.TOUT)
        return d["donnees"] if d else None

    ctx.implementer("lire_mesure", lire_mesure)
    ctx.moteur("mesurer", mesurer)
    ctx.detecteur("disque_plein", plein)
