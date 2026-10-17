# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module des réglages
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : reglages
# ZONE       : CN
# VERSION CN : 0.1.0  #9f6045
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module des réglages : l'administration des réglages que les modules déclarent. La logique vit dans noyau/CN_reglages.py.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=9f6045 ▼▼▼
"""Le module des réglages : l'administration des réglages que les modules déclarent. La logique vit dans noyau/CN_reglages.py.

Qui peut quoi : un réglage de portée COMPTE se pose pour son propre compte sans autre droit ; un réglage GLOBAL, ou celui d'un autre compte,
demande le droit « reglages.gerer ». Les secrets ne se posent que par `regler_secret`, dont la valeur ne va jamais au journal.
"""


def brancher(ctx):
    rg = ctx.service_reglages()
    dr = ctx.droits()

    def gere(compte):
        return (not compte) or dr.raison(compte, "reglages.gerer")["accord"]

    def autorise(cle, pour, ctx):
        """Peut-on écrire ce réglage pour ce compte ? Rend la portée du compte visé ('' = global)."""
        d = rg._def(cle)
        if d.portee == "global":
            if pour:
                raise ValueError("« %s » est un réglage global : il n'a pas de valeur par compte" % cle)
            if not gere(ctx.compte):
                raise PermissionError("le réglage global « %s » demande le droit reglages.gerer" % cle)
            return ""
        cible = pour or ctx.compte
        if not cible:
            raise ValueError("un réglage par compte s'écrit pour un compte : aucun n'agit")
        if cible != ctx.compte and not gere(ctx.compte):
            raise PermissionError("écrire le réglage d'un autre compte demande le droit reglages.gerer")
        return cible

    # ---- lectures ----
    def lire(ctx, module="", pour_compte=""):
        c = pour_compte or ctx.compte
        if c != ctx.compte and not gere(ctx.compte):
            raise PermissionError("lire les réglages d'un autre compte demande le droit reglages.gerer")
        return {"reglages": rg.liste(module, c, global_visible=gere(ctx.compte))}

    def historique(ctx, cle="", pour_compte="", limite=20):
        return {"historique": rg.historique(cle, pour_compte, int(limite))}

    # ---- écrire ----
    def regler(ctx, cle="", valeur=None, pour_compte=""):
        if rg._def(cle).type == "secret":
            raise ValueError("« %s » est un secret : il s'écrit par regler_secret" % cle)
        cible = autorise(cle, pour_compte, ctx)
        r = rg.poser(cle, valeur, cible, ctx.compte)
        ctx.emettre("reglage.change", objet=("reglage", cle), donnees={"cle": cle, "compte": cible, "de": r["avant"], "a": r["apres"]})
        return {"cle": cle, "compte": cible, "avant": r["avant"], "avait": r["avait"], "apres": r["apres"]}

    def regler_secret(ctx, cle="", valeur="", pour_compte=""):
        if rg._def(cle).type != "secret":
            raise ValueError("« %s » n'est pas un secret : il s'écrit par regler" % cle)
        cible = autorise(cle, pour_compte, ctx)
        r = rg.poser(cle, valeur, cible, ctx.compte)
        ctx.emettre("reglage.change", objet=("reglage", cle), donnees={"cle": cle, "compte": cible, "secret": True})
        return {"cle": cle, "compte": cible, "avant": r["avant"], "avait": r["avait"], "apres": "***", "avant_chiffre": r.get("avant_chiffre")}

    def reinitialiser(ctx, cle="", pour_compte=""):
        cible = autorise(cle, pour_compte, ctx)
        r = rg.retirer(cle, cible, ctx.compte)
        ctx.emettre("reglage.change", objet=("reglage", cle), donnees={"cle": cle, "compte": cible, "reinitialise": True, "secret": rg._def(cle).type == "secret"})
        return {"cle": cle, "compte": cible, "avant": r.get("avant"), "avait": r["avait"], "avant_chiffre": r.get("avant_chiffre")}

    def prouver_regler(ctx, res):
        ok, v = rg._brut(res["cle"], res["compte"])
        return ok and (res["apres"] == "***" or v == res["apres"])

    def defaire_regler(ctx, res):
        if res["avait"] and res.get("avant_chiffre") is not None:               # un secret : on remet la valeur chiffrée d'avant, sans jamais la déchiffrer
            rg.poser_chiffre(res["cle"], res["compte"], res["avant_chiffre"], ctx.compte or "retour arrière")
        elif res["avait"]:
            rg.poser(res["cle"], res["avant"], res["compte"], ctx.compte or "retour arrière")
        else:
            rg.retirer(res["cle"], res["compte"], ctx.compte or "retour arrière")

    def prouver_reinit(ctx, res):
        return not rg._brut(res["cle"], res["compte"])[0]

    def defaire_reinit(ctx, res):
        if res["avait"] and res.get("avant_chiffre") is not None:
            rg.poser_chiffre(res["cle"], res["compte"], res["avant_chiffre"], ctx.compte or "retour arrière")
        elif res["avait"]:
            rg.poser(res["cle"], res["avant"], res["compte"], ctx.compte or "retour arrière")

    ctx.implementer("lire", lire)
    ctx.implementer("historique", historique)
    ctx.implementer("regler", regler, prouver_regler, defaire_regler)
    ctx.implementer("regler_secret", regler_secret, prouver_regler, defaire_regler)
    ctx.implementer("reinitialiser", reinitialiser, prouver_reinit, defaire_reinit)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
