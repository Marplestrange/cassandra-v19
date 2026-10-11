"""Le module des droits : l'administration des droits des comptes. La DÉCISION, elle, est prise par l'exécuteur (noyau/droits.py).

Chaque écriture rend de quoi se défaire : l'état d'avant et l'état attendu. Rien n'est jamais interdit ici par un plafond codé :
l'administrateur règle le palier de chaque capacité (`python main.py palier`).
"""


def brancher(ctx):
    d = ctx.droits()

    def ecrire(avant, attendu, **plus):
        return dict({"avant": avant, "attendu": attendu}, **plus)

    # ---- lectures ----
    def mes_droits(ctx, compte=""):
        return d.detenus(compte)

    def verifier(ctx, compte="", droit=""):
        return dict(d.raison(compte, droit), compte=compte, droit=droit)

    def catalogue(ctx):
        return {"droits": d.catalogue()}

    def etat(ctx):
        return d.etat()

    # ---- accorder, refuser, hériter ----
    def regler(ctx, sujet_type="compte", sujet="", droit="", valeur="accorde"):
        avant = d.accord(sujet_type, sujet, droit)
        d.regler(sujet_type, sujet, droit, valeur)
        apres = d.accord(sujet_type, sujet, droit)
        ctx.emettre("droit.change", objet=(sujet_type, sujet),
                    donnees={"sujet_type": sujet_type, "sujet": sujet, "droit": droit, "de": avant, "a": apres})
        return ecrire(avant, apres, sujet_type=sujet_type, sujet=sujet, droit=droit)

    def prouver_regler(ctx, res):
        return d.accord(res["sujet_type"], res["sujet"], res["droit"]) == res["attendu"]

    def defaire_regler(ctx, res):
        d.regler(res["sujet_type"], res["sujet"], res["droit"], res["avant"])

    # ---- groupes ----
    def groupe(ctx, groupe="", libelle=None, supprimer=False):
        avant = d.groupe(groupe)
        sauve = None
        if avant is not None:
            etat_ = d.etat()
            sauve = {"groupe": avant,
                     "membres": [g["membres"] for g in etat_["groupes"] if g["groupe"] == groupe][0],
                     "accords": [a for a in etat_["accords"] if a["sujet_type"] == "groupe" and a["sujet"] == groupe]}
        if supprimer:
            if avant is None:
                raise ValueError("groupe inconnu : %s" % groupe)
            d.regler_groupe(groupe, None)
        else:
            if not libelle or not str(libelle).strip():
                raise ValueError("libellé du groupe obligatoire")
            d.regler_groupe(groupe, str(libelle).strip())
        ctx.emettre("droit.change", objet=("groupe", groupe), donnees={"groupe": groupe, "supprime": bool(supprimer)})
        return ecrire(sauve, None, groupe=groupe, supprime=bool(supprimer))

    def prouver_groupe(ctx, res):
        return (d.groupe(res["groupe"]) is None) if res["supprime"] else (d.groupe(res["groupe"]) is not None)

    def defaire_groupe(ctx, res):
        avant = res["avant"]
        if avant is None:
            d.regler_groupe(res["groupe"], None)             # on l'avait créé : on le retire
            return
        d.regler_groupe(res["groupe"], avant["groupe"]["libelle"])
        for m in avant["membres"]:
            d.regler_membre(m, res["groupe"], True)
        for a in avant["accords"]:
            d.regler("groupe", res["groupe"], a["droit"], "accorde" if a["accord"] else "refuse")

    # ---- membres ----
    def membre(ctx, compte="", groupe="", present=True):
        avant = d.membre(compte, groupe)
        d.regler_membre(compte, groupe, bool(present))
        ctx.emettre("droit.change", objet=("compte", compte), donnees={"compte": compte, "groupe": groupe, "membre": bool(present)})
        return ecrire(avant, d.membre(compte, groupe), compte=compte, groupe=groupe)

    def prouver_membre(ctx, res):
        return d.membre(res["compte"], res["groupe"]) == res["attendu"]

    def defaire_membre(ctx, res):
        d.regler_membre(res["compte"], res["groupe"], res["avant"])

    # ---- administrateurs ----
    def admin(ctx, compte="", admin=True):
        avant = d.est_admin(compte)
        d.regler_admin(compte, bool(admin))
        ctx.emettre("droit.change", objet=("compte", compte), donnees={"compte": compte, "admin": bool(admin)})
        return ecrire(avant, d.est_admin(compte), compte=compte)

    def prouver_admin(ctx, res):
        return d.est_admin(res["compte"]) == res["attendu"]

    def defaire_admin(ctx, res):
        d.regler_admin(res["compte"], res["avant"])

    ctx.implementer("mes_droits", mes_droits)
    ctx.implementer("verifier", verifier)
    ctx.implementer("catalogue", catalogue)
    ctx.implementer("etat", etat)
    ctx.implementer("regler", regler, prouver_regler, defaire_regler)
    ctx.implementer("groupe", groupe, prouver_groupe, defaire_groupe)
    ctx.implementer("membre", membre, prouver_membre, defaire_membre)
    ctx.implementer("admin", admin, prouver_admin, defaire_admin)
