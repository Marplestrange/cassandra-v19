# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module des modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : modules
# ZONE       : CN
# VERSION CN : 0.1.0  #8acea6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module des modules : l'état de chacun, et le geste de l'activer ou de le désactiver.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=8acea6 ▼▼▼
"""Le module des modules : l'état de chacun, et le geste de l'activer ou de le désactiver.

Le travail (plan d'activation avec dépendances, refus d'un essentiel, branchement à chaud) est celui du noyau ; ce module en fait des
capacités. L'état s'écrit seul : le noyau en marche le voit au prochain tour et branche ou débranche, comme pour la ligne de commande.
"""


def brancher(ctx):
    g = ctx.gestion_modules()

    def entree(mid):
        return next((m for m in g.catalogue() if m["id"] == mid), None)

    def lister(ctx):
        return dict({"modules": g.catalogue(), "gere": bool(g.gere())}, **g.sections())      # gere=False : instance de développement, tous les modules sont branchés et l'état n'y change rien

    def fiche(ctx, module=""):
        m = entree(module)
        if m is None:
            raise ValueError("module inconnu : « %s »" % module)
        # une fiche n'expose ni permissions ni versions de plus que le catalogue public ; les capacités sont filtrées par les droits du compte
        return {"module": {k: m[k] for k in ("id", "nom", "description", "version", "famille", "etat", "essentiel", "importance", "sans", "requiert", "requis_par", "conflits", "suggere", "fournit", "contraintes") if k in m},
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

    # ---------------------------------------------------------------- le cycle de vie d'un module venu d'une archive (le travail est celui de noyau/CN_cycle.py)
    cy = g.cycle

    def politique():
        v = str(ctx.reglage("politique_confiance", "signes") or "signes")
        return v if v in ("signes", "tous") else "signes"

    def examiner(ctx, corps_octets=b"", nom=""):
        if not isinstance(corps_octets, (bytes, bytearray)):
            raise ValueError("une archive (octets) est attendue : elle se téléverse par /api/televerser/modules.examiner")
        return cy.examiner(bytes(corps_octets), politique())

    def prouver_examiner(ctx, res):
        return (cy.quarantaine / (res["jeton"] + ".cmod")).is_file()

    def defaire_examiner(ctx, res):
        cy.abandonner(res["jeton"])

    def abandonner(ctx, jeton=""):
        cy.abandonner(str(jeton))
        return {"jeton": str(jeton)}

    def prouver_abandonne(ctx, res):
        return not (cy.quarantaine / (res["jeton"] + ".cmod")).exists()

    def defaire_abandonne(ctx, res):
        cy.restaurer(res["jeton"])

    def installer(ctx, jeton="", consentement=""):
        return cy.installer(str(jeton), str(consentement), politique(), par=ctx.compte or "humain")

    def prouver_installe(ctx, res):
        e = entree(res["id"])
        return bool(e) and e.get("version") == res["version"]

    def defaire_installe(ctx, res):
        if res.get("ancienne"):
            cy.retour_arriere(res["id"], par=ctx.compte or "retour arrière")
        else:
            cy.desinstaller(res["id"], par=ctx.compte or "retour arrière")

    def retour_arriere(ctx, module="", cle=""):
        return cy.retour_arriere(str(module), str(cle), par=ctx.compte or "humain")

    def prouver_retour(ctx, res):
        e = entree(res["id"])
        return bool(e) and e.get("version") == res["version"]

    def defaire_retour(ctx, res):
        cy.retour_arriere(res["id"], par=ctx.compte or "retour arrière")

    def desinstaller(ctx, module="", purger_donnees=False):
        r = cy.desinstaller(str(module), par=ctx.compte or "humain")
        if purger_donnees:
            r["purge"] = cy.purger_donnees(str(module), par=ctx.compte or "humain")["purge"]
        return r

    def prouver_desinstalle(ctx, res):
        return entree(res["id"]) is None

    def defaire_desinstalle(ctx, res):
        cy.retour_arriere(res["id"], par=ctx.compte or "retour arrière")

    def versions(ctx, module=""):
        return dict(cy.versions(str(module)), en_place=entree(str(module)))

    ctx.implementer("examiner", examiner, prouver_examiner, defaire_examiner)
    ctx.implementer("installer", installer, prouver_installe, defaire_installe)
    ctx.implementer("retour_arriere", retour_arriere, prouver_retour, defaire_retour)
    ctx.implementer("desinstaller", desinstaller, prouver_desinstalle, defaire_desinstalle)
    ctx.implementer("abandonner", abandonner, prouver_abandonne, defaire_abandonne)
    ctx.implementer("versions", versions)
    def sante(ctx, module=""):
        if entree(str(module)) is None:
            raise ValueError("module inconnu : « %s »" % module)
        return g.sante(str(module))

    ctx.implementer("sante", sante)
    def contributions(ctx, point=""):
        return g.contributions(str(point))

    ctx.implementer("contributions", contributions)
    def registre(ctx):
        """Le registre OFFICIEL (en dur : adresse et clé racine du noyau) toujours en premier ; un registre de l'administrateur (registre_url) en plus, marqué non officiel."""
        try:
            off = cy.registre_officiel()
        except ValueError as ex:
            off = {"url": cy.url_officielle, "officiel": True, "erreur": str(ex), "modules": [], "editeurs": [], "revocations": [], "installes_revoques": []}
        url = str(ctx.reglage("registre_url", "") or "").strip()
        autre = {"url": url, "officiel": False, "modules": []}
        if url:
            try:
                autre["modules"] = cy.registre_lire(url)
            except ValueError as ex:
                autre["erreur"] = str(ex)
        return {"politique": politique(), "officiel": off, "autre": autre}

    def telecharger(ctx, module="", source="officiel"):
        if str(source) == "officiel":
            return cy.telecharger_officiel(str(module), politique())
        url = str(ctx.reglage("registre_url", "") or "").strip()
        if not url:
            raise ValueError("aucun autre registre : renseignez le réglage « Adresse d'un autre registre de modules »")
        return cy.telecharger(url, str(module), politique())

    ctx.implementer("registre", registre)
    ctx.implementer("telecharger", telecharger, prouver_examiner, defaire_examiner)
    ctx.implementer("lister", lister)
    ctx.implementer("fiche", fiche)
    ctx.implementer("activer", activer, prouver_activer, defaire_activer)
    ctx.implementer("desactiver", desactiver, prouver_desactiver, defaire_desactiver)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
