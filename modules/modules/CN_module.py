# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module des modules
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : modules
# ZONE       : CN
# VERSION CN : 0.1.0  #5dfd65
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module des modules : l'état de chacun, et le geste de l'activer ou de le désactiver.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.1.0 empreinte=5dfd65 ▼▼▼
"""Le module des modules : l'état de chacun, et le geste de l'activer ou de le désactiver.

Le travail (plan d'activation avec dépendances, refus d'un essentiel, branchement à chaud) est celui du noyau ; ce module en fait des
capacités. L'état s'écrit seul : le noyau en marche le voit au prochain tour et branche ou débranche, comme pour la ligne de commande.
"""
from . import CN_autonomie as au


def brancher(ctx):
    g = ctx.gestion_modules()

    # ---------------------------------------------------------------- l'autonomie : jusqu'où Cassandra va seule (voir CN_autonomie.py)
    def niveau():
        return au.niveau_de(ctx.reglage("autonomie", "reine"))

    def acteur(ctx):
        return ctx.acteur or "humain"

    def qui(ctx):                                    # le nom porté au journal : Cassandra, Itare... ou le compte humain
        a = acteur(ctx)
        return a if a in au.ACTEURS_REINE else (ctx.compte or "humain")

    def fenetre():
        return au.fenetre_de(ctx.reglage("fenetre", "nuit"))

    def pourquoi_de(ctx, dit=""):                    # le pourquoi d'un geste : celui qu'on a donné, sinon ce qu'on sait de qui le fait
        if str(dit or "").strip():
            return str(dit).strip()[:300]
        a = acteur(ctx)
        return "Geste de l'utilisateur." if a in au.HUMAINS else "Décision de %s." % a.capitalize()

    def refus(ctx, geste, module="", **kw):          # un refus de la règle n'est PAS un échec : il se dit, sans rétrograder la capacité
        ok, raison = au.verdict(niveau(), acteur(ctx), geste, verrouille=bool(module) and str(module) in cy.verrous(), **kw)
        return None if ok else {"refuse": raison}

    def sauf_refus_p(prouver):
        return lambda ctx, res: ("refuse" in res) or prouver(ctx, res)

    def sauf_refus_d(defaire):
        return lambda ctx, res: None if "refuse" in res else defaire(ctx, res)

    def entree(mid):
        return next((m for m in g.catalogue() if m["id"] == mid), None)

    def lister(ctx):
        verrous = cy.verrous()
        return dict({"modules": [dict(m, verrou=m["id"] in verrous) for m in g.catalogue()], "gere": bool(g.gere()), "autonomie": niveau()}, **g.sections())      # gere=False : instance de développement, tous les modules sont branchés et l'état n'y change rien

    def fiche(ctx, module=""):
        m = entree(module)
        if m is None:
            raise ValueError("module inconnu : « %s »" % module)
        # une fiche n'expose ni permissions ni versions de plus que le catalogue public ; les capacités sont filtrées par les droits du compte
        return {"module": {k: m[k] for k in ("id", "nom", "description", "version", "famille", "etat", "essentiel", "importance", "sans", "requiert", "requis_par", "conflits", "suggere", "fournit", "contraintes") if k in m},
                "capacites": g.capacites(module, ctx.compte)}

    def activer(ctx, module="", avec_dependances=True, pourquoi=""):
        if not module:
            raise ValueError("quel module ?")
        if entree(module) is None:
            raise ValueError("module inconnu : « %s »" % module)
        n = refus(ctx, "activer", module)
        if n:
            return dict(n, module=module)
        r = g.activer(module, acteur=qui(ctx), avec_dependances=bool(avec_dependances), appliquer=False)
        if not r.get("ok"):
            raise ValueError(r.get("raison") or ("« %s » ne peut pas être activé : il faut d'abord installer « %s »" % (module, r.get("a_installer", "?"))))
        cy.noter_acte("active", module, qui(ctx), pourquoi=pourquoi_de(ctx, pourquoi), avec=[x for x in r["actives"] if x != module])
        return {"module": module, "actives": r["actives"]}

    def prouver_activer(ctx, res):
        return all((entree(x) or {}).get("etat") == "actif" for x in res["actives"])

    def defaire_activer(ctx, res):
        for x in reversed(res["actives"]):                                   # les dépendances en dernier : elles servaient les autres
            g.desactiver(x, acteur=ctx.compte or "retour arrière", forcer=True, appliquer=False)

    def desactiver(ctx, module="", cascade=False, pourquoi=""):
        if not module:
            raise ValueError("quel module ?")
        if entree(module) is None:
            raise ValueError("module inconnu : « %s »" % module)
        n = refus(ctx, "desactiver", module)
        if n:
            return dict(n, module=module)
        r = g.desactiver(module, acteur=qui(ctx), cascade=bool(cascade), appliquer=False)
        if not r.get("ok"):
            raise ValueError(r.get("raison") or ("« %s » ne peut pas être désactivé" % module))
        cy.noter_acte("desactive", module, qui(ctx), pourquoi=pourquoi_de(ctx, pourquoi), avec=[x for x in r["desactives"] if x != module])
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
        n = refus(ctx, "abandonner")
        if n:
            return dict(n, jeton=str(jeton))
        cy.abandonner(str(jeton))
        return {"jeton": str(jeton)}

    def prouver_abandonne(ctx, res):
        return not (cy.quarantaine / (res["jeton"] + ".cmod")).exists()

    def defaire_abandonne(ctx, res):
        cy.restaurer(res["jeton"])

    def installer(ctx, jeton="", consentement="", pourquoi=""):
        r = cy.installer(str(jeton), str(consentement), politique(), par=qui(ctx))
        cy.annoter(r["id"], "installe", pourquoi_de(ctx, pourquoi or "Archive examinée et installée avec ton consentement aux permissions montrées."))
        return r

    def prouver_installe(ctx, res):
        e = entree(res["id"])
        return bool(e) and e.get("version") == res["version"]

    def defaire_installe(ctx, res):
        if res.get("ancienne"):
            cy.retour_arriere(res["id"], par=ctx.compte or "retour arrière")
        else:
            cy.desinstaller(res["id"], par=ctx.compte or "retour arrière")

    def retour_arriere(ctx, module="", cle="", pourquoi=""):
        n = refus(ctx, "retour_arriere", module)
        if n:
            return dict(n, module=str(module))
        r = cy.retour_arriere(str(module), str(cle), par=qui(ctx))
        cy.annoter(str(module), "retour", pourquoi_de(ctx, pourquoi))
        return r

    def prouver_retour(ctx, res):
        e = entree(res["id"])
        return bool(e) and e.get("version") == res["version"]

    def defaire_retour(ctx, res):
        cy.retour_arriere(res["id"], par=ctx.compte or "retour arrière")

    def revoque(mid):
        try:
            return any(x["id"] == mid for x in cy.registre_officiel().get("installes_revoques", []))
        except Exception:
            return False

    def desinstaller(ctx, module="", purger_donnees=False, pourquoi=""):
        n = refus(ctx, "desinstaller", module, revoque=revoque(str(module)))
        if n:
            return dict(n, module=str(module))
        r = cy.desinstaller(str(module), par=qui(ctx))
        cy.annoter(str(module), "desinstalle", pourquoi_de(ctx, pourquoi))
        if purger_donnees and acteur(ctx) in au.HUMAINS:                  # purger des données reste un geste humain : rien d'autre ne les efface pour de bon
            r["purge"] = cy.purger_donnees(str(module), par=qui(ctx))["purge"]
        return r

    def prouver_desinstalle(ctx, res):
        return entree(res["id"]) is None

    def defaire_desinstalle(ctx, res):
        cy.retour_arriere(res["id"], par=ctx.compte or "retour arrière")

    def versions(ctx, module=""):
        return dict(cy.versions(str(module)), en_place=entree(str(module)))

    ctx.implementer("examiner", examiner, prouver_examiner, defaire_examiner)
    ctx.implementer("installer", installer, prouver_installe, defaire_installe)
    ctx.implementer("retour_arriere", retour_arriere, sauf_refus_p(prouver_retour), sauf_refus_d(defaire_retour))
    ctx.implementer("desinstaller", desinstaller, sauf_refus_p(prouver_desinstalle), sauf_refus_d(defaire_desinstalle))
    ctx.implementer("abandonner", abandonner, sauf_refus_p(prouver_abandonne), sauf_refus_d(defaire_abandonne))
    ctx.implementer("versions", versions)
    def sante(ctx, module=""):
        if not str(module):                                                  # sans module : la santé de tous, en une passe
            return {"modules": g.sante_tous()}
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
        n = refus(ctx, "telecharger", module)
        if n:
            return dict(n, jeton="")
        if str(source) == "officiel":
            return cy.telecharger_officiel(str(module), politique())
        url = str(ctx.reglage("registre_url", "") or "").strip()
        if not url:
            raise ValueError("aucun autre registre : renseignez le réglage « Adresse d'un autre registre de modules »")
        return cy.telecharger(url, str(module), politique())

    ctx.implementer("registre", registre)
    ctx.implementer("telecharger", telecharger, lambda c, r: ("refuse" in r) or prouver_examiner(c, r), sauf_refus_d(defaire_examiner))
    ctx.implementer("lister", lister)
    ctx.implementer("fiche", fiche)
    ctx.implementer("activer", activer, sauf_refus_p(prouver_activer), sauf_refus_d(defaire_activer))
    ctx.implementer("desactiver", desactiver, sauf_refus_p(prouver_desactiver), sauf_refus_d(defaire_desactiver))

    # ---------------------------------------------------------------- ajouter : le geste de Cassandra pour mettre un module du registre en service, d'un seul tenant
    def ajouter(ctx, module="", source="officiel", activer_apres=True, pourquoi=""):
        mid = str(module)
        if not mid:
            raise ValueError("quel module ?")
        n = refus(ctx, "telecharger", mid)
        if n:
            return dict(n, module=mid)
        exam = telecharger(ctx, mid, source)
        if "refuse" in exam:
            return dict(exam, module=mid)
        en_place = entree(mid)
        ok, raison = au.verdict(niveau(), acteur(ctx), "mettre_a_jour" if en_place else "ajouter", source=exam.get("niveau", ""), elargit=bool(exam.get("permissions_elargies")), nouveau=en_place is None)
        if not ok or not exam.get("autorise"):
            cy.abandonner(exam["jeton"])
            return {"refuse": raison or "l'examen refuse cette archive : %s" % "; ".join(exam.get("raisons", []))[:200], "module": mid}
        r = cy.installer(exam["jeton"], exam["empreinte_permissions"], politique(), par=qui(ctx))
        cy.annoter(mid, "installe", pourquoi_de(ctx, pourquoi or "Ajout demandé : %s, signature vérifiée, permissions dans ma règle." % ("registre officiel" if exam.get("niveau") == "officiel" else "éditeur vérifié")))
        actives = []
        if activer_apres and (en_place is None or en_place.get("etat") != "actif"):
            a = g.activer(mid, acteur=qui(ctx), avec_dependances=True, appliquer=False)
            actives = a.get("actives", []) if a.get("ok") else []
            if actives:
                cy.noter_acte("active", mid, qui(ctx), pourquoi="Activé juste après son installation.", avec=[x for x in actives if x != mid])
        return dict(r, module=mid, actives=actives, permissions_elargies=exam.get("permissions_elargies", []))

    def prouver_ajoute(ctx, res):
        e = entree(res["id"])
        return bool(e) and e.get("version") == res["version"] and all((entree(x) or {}).get("etat") == "actif" for x in res.get("actives", []))

    def defaire_ajoute(ctx, res):
        for x in reversed(res.get("actives", [])):
            g.desactiver(x, acteur=qui(ctx) or "retour arrière", forcer=True, appliquer=False)
        defaire_installe(ctx, res)

    ctx.implementer("ajouter", ajouter, sauf_refus_p(prouver_ajoute), sauf_refus_d(defaire_ajoute))

    # ---------------------------------------------------------------- l'entretien : la passe que Cassandra fait seule (aussi un geste, que n'importe qui peut déclencher)
    def appliquer_inverse(inv, par, pourquoi="Défait : le geste inverse d'un acte du récit."):
        if not inv:
            return
        cap, a = inv["capacite"], inv["args"]
        if cap == "modules.desactiver":
            g.desactiver(a["module"], acteur=par, forcer=True, appliquer=False)
            cy.noter_acte("desactive", a["module"], par, pourquoi=pourquoi)
        elif cap == "modules.activer":
            g.activer(a["module"], acteur=par, avec_dependances=bool(a.get("avec_dependances", True)), appliquer=False)
            cy.noter_acte("active", a["module"], par, pourquoi=pourquoi)
        elif cap == "modules.retour_arriere":
            cy.retour_arriere(a["module"], par=par)
            cy.annoter(a["module"], "retour", pourquoi)
        elif cap == "modules.desinstaller":
            cy.desinstaller(a["module"], par=par)
            cy.annoter(a["module"], "desinstalle", pourquoi)

    def faire_entretien(ctx, simuler=False, forcer=False):
        return au.entretien(g, cy, politique(), niveau(), agir=not simuler, acteur=qui(ctx) if acteur(ctx) in au.ACTEURS_REINE else "cassandra",
                            fenetre=fenetre(), forcer=bool(forcer))

    def defaire_entretien(ctx, res):
        for x in reversed(res.get("actions", [])):
            appliquer_inverse(x.get("inverse"), "retour arrière")

    ctx.implementer("entretien", faire_entretien, lambda c, r: True, defaire_entretien)
    ctx.moteur("entretien", lambda c: faire_entretien(c))

    # ---------------------------------------------------------------- le récit, et le geste « défaire » (le même pour tous : un humain rassuré, Cassandra qui se corrige)
    def activite(ctx, limite=40):
        return {"autonomie": niveau(), "fenetre": fenetre(), "gel": bool(g.gel()), "verrous": sorted(cy.verrous()), "actes": au.recit(cy, int(limite))}

    def annuler(ctx, module="", geste=""):
        inv = au.inverse(str(geste), {"module": str(module), "id": str(module), "ancienne": "?" if str(geste) in ("installe", "retour") else ""})
        if not inv:
            raise ValueError("rien à défaire pour « %s »" % geste)
        appliquer_inverse(inv, qui(ctx))
        return {"module": str(module), "defait": str(geste), "refaire": au.inverse(inv["capacite"].split(".", 1)[1], {"module": str(module), "id": str(module)})}

    def defaire_annule(ctx, res):
        appliquer_inverse(res.get("refaire"), "retour arrière")

    def verrouiller(ctx, module="", verrou=True):
        if entree(str(module)) is None:
            raise ValueError("module inconnu : « %s »" % module)
        cy.verrouiller(str(module), bool(verrou), par=qui(ctx))
        return {"module": str(module), "verrou": bool(verrou)}

    def prouver_verrou(ctx, res):
        return (res["module"] in cy.verrous()) == res["verrou"]

    def defaire_verrou(ctx, res):
        cy.verrouiller(res["module"], not res["verrou"], par="retour arrière")

    ctx.implementer("verrouiller", verrouiller, prouver_verrou, defaire_verrou)
    ctx.implementer("activite", activite)
    ctx.implementer("annuler", annuler, lambda c, r: True, defaire_annule)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
