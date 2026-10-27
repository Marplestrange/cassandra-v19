# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module des droits
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : droits
# ZONE       : CN
# VERSION CN : 0.2.0  #82ded7
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module des droits : l'administration des droits des comptes. La DÉCISION, elle, est prise par l'exécuteur (noyau/CN_droits.py).
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.0 empreinte=82ded7 ▼▼▼
"""Le module des droits : l'administration des droits des comptes. La DÉCISION, elle, est prise par l'exécuteur (noyau/CN_droits.py).

Chaque écriture rend de quoi se défaire : l'état d'avant et l'état attendu. Rien n'est jamais interdit ici par un plafond codé :
l'administrateur règle le palier de chaque capacité (`python CN_main.py palier`).
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
    def groupe(ctx, groupe="", libelle=None, supprimer=False, description=None):
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
            d.regler_groupe(groupe, str(libelle).strip(), description)
        ctx.emettre("droit.change", objet=("groupe", groupe), donnees={"groupe": groupe, "supprime": bool(supprimer)})
        return ecrire(sauve, None, groupe=groupe, supprime=bool(supprimer))

    def prouver_groupe(ctx, res):
        return (d.groupe(res["groupe"]) is None) if res["supprime"] else (d.groupe(res["groupe"]) is not None)

    def defaire_groupe(ctx, res):
        avant = res["avant"]
        if avant is None:
            d.regler_groupe(res["groupe"], None)             # on l'avait créé : on le retire
            return
        d.regler_groupe(res["groupe"], avant["groupe"]["libelle"], avant["groupe"].get("description") or "")
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

    # ---- lire pour décider : ce que montre l'écran des utilisateurs et des groupes ----
    def decisions(ctx, compte=""):
        """Chaque droit du catalogue pour ce compte : la décision, son pourquoi, et ce qui est réglé sur le compte lui-même."""
        tout = d.decisions_de(compte)
        out = [dict(c, accord=tout[c["droit"]]["accord"], parce=tout[c["droit"]]["parce"], propre=tout[c["droit"]]["propre"]) for c in d.catalogue() if c["droit"] in tout]
        return {"compte": compte, "admin": bool(compte) and d.est_admin(compte), "groupes": d.groupes_de(compte) if compte else [], "droits": out}

    def qui_peut(ctx, droit=""):
        """Tous les comptes, avec leur décision pour ce droit et son pourquoi : l'audit en une question."""
        if droit not in d.connus:
            raise ValueError("droit inconnu (aucun module actif ne le déclare) : %s" % droit)
        out = []
        for c in ctx.identite().lister():
            r = d.decisions_de(c["compte"])[droit]
            out.append({"compte": c["compte"], "nom": c.get("display_name") or c["compte"], "type": c.get("type", "humain"),
                        "desactive": bool(c.get("desactive")), "accord": r["accord"], "parce": r["parce"]})
        return {"droit": droit, "comptes": out}

    def voir_comme(ctx, compte=""):
        """La STRUCTURE seulement : quels modules ce compte ouvre, et combien de leurs droits il détient. Jamais un contenu : administrer un compte, ce n'est pas le lire."""
        det = d.detenus(compte)
        tenus = set(det["droits"])
        mods = []
        for m in ctx.manifestes_actifs():
            ids = ["%s.%s" % (m.id, x.id) for x in m.droits]
            if ids:
                mods.append({"module": m.id, "nom": m.nom, "accordes": sum(1 for i in ids if i in tenus), "total": len(ids)})
        return {"compte": compte, "admin": det["admin"], "modules": sorted(mods, key=lambda x: x["nom"].lower())}

    TYPES_JOURNAL = ("droit.change", "compte.cree", "compte.modifie", "compte.supprime", "compte.restaure", "compte.desactive", "compte.reactive")

    def journal(ctx, limite=100):
        """Les changements de droits et de comptes, les plus récents d'abord, avec QUI les a faits (un utilisateur ou un agent)."""
        evs = [e for e in ctx.evenements("droit.", 500) + ctx.evenements("compte.", 500) if e["type"] in TYPES_JOURNAL]
        evs.sort(key=lambda e: e["id"], reverse=True)
        return {"journal": [{"id": e["id"], "ts": e["ts"], "type": e["type"], "par": e.get("compte") or "", "acteur": e["acteur"],
                             "agent": e["acteur"] in ("cassandra", "itare"), "objet": e["objet_id"], "donnees": e["donnees"]}
                            for e in evs[:max(1, min(int(limite or 100), 500))]]}

    # ---- appliquer d'un coup les réglages d'un compte ou d'un groupe : une écriture, un retour, un événement ----
    VALEURS_OK = ("accorde", "refuse", "herite")

    def appliquer(ctx, sujet_type="compte", sujet="", accords=None, admin=None, confirme=False, prevenir=True):
        accords = dict(accords or {})
        if sujet_type not in ("compte", "groupe"):
            raise ValueError("sujet_type : compte | groupe")
        if not sujet or not str(sujet).strip():
            raise ValueError("sujet vide")
        for k, v in accords.items():
            if k not in d.connus:
                raise ValueError("droit inconnu (aucun module actif ne le déclare) : %s" % k)
            if v not in VALEURS_OK:
                raise ValueError("valeur : accorde | refuse | herite")
        avant = {k: d.accord(sujet_type, sujet, k) or "herite" for k in accords}
        admin_avant = d.est_admin(sujet) if sujet_type == "compte" else None
        gerait = sujet_type == "compte" and bool(ctx.compte) and sujet == ctx.compte and d.a(sujet, "droits.gerer")

        def retour():
            for k, v in avant.items():
                d.regler(sujet_type, sujet, k, v)
            if admin_avant is not None and d.est_admin(sujet) != admin_avant:
                d.regler_admin(sujet, admin_avant)

        if admin is not None:
            if sujet_type != "compte":
                raise ValueError("seul un compte est administrateur")
            if bool(admin) != admin_avant and not d.a(ctx.compte, "droits.nommer_admin"):
                raise PermissionError("nommer ou révoquer un administrateur demande le droit droits.nommer_admin")
            d.regler_admin(sujet, bool(admin))              # le dernier administrateur est refusé ici
        try:
            for k, v in accords.items():
                if avant[k] != v:
                    d.regler(sujet_type, sujet, k, v)
            if gerait and not confirme and ((admin_avant and not d.est_admin(sujet)) or not d.a(sujet, "droits.gerer")):
                raise ValueError("confirmation renforcée requise : ces réglages vous retirent le droit de gérer les droits (confirme = vrai pour passer outre)")
        except Exception:
            retour()
            raise
        changes = [{"droit": k, "de": avant[k], "a": v} for k, v in accords.items() if avant[k] != v]
        apres_admin = d.est_admin(sujet) if sujet_type == "compte" else None
        ctx.emettre("droit.change", objet=(sujet_type, sujet),
                    donnees={"sujet_type": sujet_type, "sujet": sujet, "changes": changes,
                             "admin": [admin_avant, apres_admin] if admin_avant != apres_admin else None,
                             "prevenir": bool(prevenir) and sujet_type == "compte" and bool(changes or admin_avant != apres_admin)})
        return ecrire(avant, {k: accords[k] for k in avant}, sujet_type=sujet_type, sujet=sujet, changes=changes,
                      admin_avant=admin_avant, admin_apres=apres_admin)

    def prouver_appliquer(ctx, res):
        return all((d.accord(res["sujet_type"], res["sujet"], k) or "herite") == v for k, v in res["attendu"].items()) and \
            (res["admin_avant"] is None or d.est_admin(res["sujet"]) == res["admin_apres"])

    def defaire_appliquer(ctx, res):
        for k, v in res["avant"].items():
            d.regler(res["sujet_type"], res["sujet"], k, v)
        if res["admin_avant"] is not None and d.est_admin(res["sujet"]) != res["admin_avant"]:
            d.regler_admin(res["sujet"], res["admin_avant"])

    FENETRE_S = 900

    def sans_compte(ctx):
        """Un constat tant qu'au moins un acte refusé faute de compte date de moins de quinze minutes."""
        import time
        depuis = time.time() - FENETRE_S
        faits = [e for e in ctx.evenements("capacite.refusee", 500)
                 if e["ts"] >= depuis and e["donnees"].get("alerte") and e["donnees"].get("raison") in ("sans compte", "compte inconnu")]
        if not faits:
            return []
        dernier = faits[-1]
        prets = sorted({"%s (%s)" % (e["objet_id"], e["acteur"]) for e in faits})[:5]
        return [{"objet": ("securite", "sans_compte"),
                 "titre": "%d acte(s) refusé(s) faute de compte en %d min" % (len(faits), FENETRE_S // 60),
                 "detail": "Dernier : %s par %s (%s). Parmi : %s." % (dernier["objet_id"], dernier["acteur"], dernier["donnees"].get("raison"), ", ".join(prets))}]

    ctx.detecteur("sans_compte", sans_compte)
    ctx.implementer("mes_droits", mes_droits)
    ctx.implementer("verifier", verifier)
    ctx.implementer("catalogue", catalogue)
    ctx.implementer("etat", etat)
    ctx.implementer("regler", regler, prouver_regler, defaire_regler)
    ctx.implementer("groupe", groupe, prouver_groupe, defaire_groupe)
    ctx.implementer("membre", membre, prouver_membre, defaire_membre)
    ctx.implementer("admin", admin, prouver_admin, defaire_admin)
    ctx.implementer("decisions", decisions)
    ctx.implementer("qui_peut", qui_peut)
    ctx.implementer("voir_comme", voir_comme)
    ctx.implementer("journal", journal)
    ctx.implementer("appliquer", appliquer, prouver_appliquer, defaire_appliquer)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
