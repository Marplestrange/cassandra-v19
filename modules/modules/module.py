"""Le module des modules : l'état de chacun, et le geste de l'activer ou de le désactiver.

Le travail (plan d'activation avec dépendances, refus d'un essentiel, branchement à chaud) est celui du noyau ; ce module en fait des
capacités. L'état s'écrit seul : le noyau en marche le voit au prochain tour et branche ou débranche, comme pour la ligne de commande.
"""


def brancher(ctx):
    g = ctx.gestion_modules()

    def entree(mid):
        return next((m for m in g.catalogue() if m["id"] == mid), None)

    def lister(ctx):
        return {"modules": g.catalogue(), "gere": bool(g.gere())}      # gere=False : instance de développement, tous les modules sont branchés et l'état n'y change rien

    def fiche(ctx, module=""):
        m = entree(module)
        if m is None:
            raise ValueError("module inconnu : « %s »" % module)
        # une fiche n'expose ni permissions ni versions de plus que le catalogue public ; les capacités sont filtrées par les droits du compte
        return {"module": {k: m[k] for k in ("id", "nom", "description", "version", "famille", "etat", "essentiel", "requiert", "requis_par") if k in m},
                "capacites": g.capacites(module, ctx.compte)}

    def activer(ctx, module="", avec_dependances=True):
        if not module:
            raise ValueError("quel module ?")
        if entree(module) is None:
            raise ValueError("module inconnu : « %s »" % module)
        r = g.activer(module, acteur=ctx.compte or "humain", avec_dependances=bool(avec_dependances), appliquer=False)
        if not r.get("ok"):
            raise ValueError(r.get("raison") or ("« %s » ne peut pas être activé : il faut d'abord installer « %s »" % (module, r.get("a_installer", "?"))))
        return {"module": module, "actives": r["actives"]}

    def prouver_activer(ctx, res):
        return all((entree(x) or {}).get("etat") == "actif" for x in res["actives"])

    def defaire_activer(ctx, res):
        for x in reversed(res["actives"]):                                   # les dépendances en dernier : elles servaient les autres
            g.desactiver(x, acteur=ctx.compte or "retour arrière", forcer=True, appliquer=False)

    def desactiver(ctx, module="", cascade=False):
        if not module:
            raise ValueError("quel module ?")
        if entree(module) is None:
            raise ValueError("module inconnu : « %s »" % module)
        r = g.desactiver(module, acteur=ctx.compte or "humain", cascade=bool(cascade), appliquer=False)
        if not r.get("ok"):
            raise ValueError(r.get("raison") or ("« %s » ne peut pas être désactivé" % module))
        return {"module": module, "desactives": r["desactives"]}

    def prouver_desactiver(ctx, res):
        return all((entree(x) or {}).get("etat") != "actif" for x in res["desactives"])

    def defaire_desactiver(ctx, res):
        for x in reversed(res["desactives"]):
            g.activer(x, acteur=ctx.compte or "retour arrière", avec_dependances=False, appliquer=False)

    ctx.implementer("lister", lister)
    ctx.implementer("fiche", fiche)
    ctx.implementer("activer", activer, prouver_activer, defaire_activer)
    ctx.implementer("desactiver", desactiver, prouver_desactiver, defaire_desactiver)
