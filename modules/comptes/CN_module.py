"""Le module des comptes : l'identité et ses preuves. La logique vit dans noyau/CN_identite.py (portée de la V18) ; ici, les capacités.

Règle de la V18 gardée : le compte d'une action de session n'est JAMAIS un paramètre libre. C'est `ctx.compte`, le compte au nom duquel
l'exécuteur fait agir, sinon six caractères devinés fermeraient la session de quelqu'un d'autre.
"""


def brancher(ctx):
    idt = ctx.identite()

    def moi_ou_erreur(ctx):
        if not ctx.compte:
            raise ValueError("aucun compte n'agit : cette capacité s'exécute au nom d'un compte")
        return ctx.compte

    def ok_ou_erreur(r):
        if not r.get("ok"):
            raise ValueError(r.get("error", "refusé"))
        return r

    # ---- lectures ----
    def moi(ctx):
        c = moi_ou_erreur(ctx)
        return idt.lire(c)

    def lire(ctx, compte=""):
        return idt.lire(compte)

    def lister(ctx):
        return {"comptes": idt.lister()}

    def corbeille(ctx):
        return {"corbeille": idt.corbeille()}

    def regles_mdp(ctx):
        from noyau import CN_identite as identite
        return {"regles": identite.mdp_regles(), "legende": identite.mdp_legende()}

    def valider_session(ctx, jeton=""):
        return idt.valider(jeton)

    def mes_sessions(ctx, courant=""):
        return {"sessions": idt.sessions(moi_ou_erreur(ctx), courant)}

    # ---- créer ----
    def creer(ctx, compte="", mot_de_passe="", sites=None, superadmin=False, unix_user="", **profil):
        if superadmin:
            moi = idt.lire(ctx.compte) if ctx.compte else None
            if ctx.compte != "operateur" and not (moi and moi["superadmin"]):
                raise ValueError("Seul un superadministrateur (ou l'opérateur local) crée un superadministrateur")
        r = idt.creer(compte, mot_de_passe, sites, bool(superadmin), unix_user, **profil)
        ctx.emettre("compte.cree", objet=("compte", (compte or "").strip().lower()), donnees={"admin": r.get("admin"), "ok": r["ok"]}) if r["ok"] else None
        if not r["ok"]:
            raise ValueError(r["error"])
        return {"compte": r["compte"], "admin": r["admin"], "superadmin": r["superadmin"], "unix_user": r["unix_user"], "unix_demande": r["unix_demande"]}

    def prouver_creer(ctx, res):
        return idt.existe(res["compte"])

    def defaire_creer(ctx, res):
        idt.base.ecrire("DELETE FROM comptes WHERE compte=?", (res["compte"],))
        idt.base.ecrire("DELETE FROM sessions WHERE compte=?", (res["compte"],))
        idt.droits.regler_admin(res["compte"], False)

    def inviter_agent(ctx, nom="", libelle=""):
        r = ok_ou_erreur(idt.inviter_agent(nom, moi_ou_erreur(ctx), libelle))
        ctx.emettre("compte.cree" if r["nouveau"] else "compte.modifie", objet=("compte", r["compte"]), donnees={"type": "agent", "par": ctx.compte})
        return {"compte": r["compte"], "jeton": r["jeton"], "nouveau": r["nouveau"]}

    def prouver_invitation(ctx, res):
        return idt.valider_agent(res["jeton"]).get("compte") == res["compte"] or res["jeton"] == "***"

    def defaire_invitation(ctx, res):
        if res["jeton"] != "***":
            idt.base.ecrire("UPDATE agents_jetons SET actif=0 WHERE compte=?", (res["compte"],))

    def revoquer_agent(ctx, nom=""):
        r = ok_ou_erreur(idt.revoquer_agent(nom, moi_ou_erreur(ctx)))
        ctx.emettre("compte.modifie", objet=("compte", r["compte"]), donnees={"type": "agent", "revoque": True, "par": ctx.compte})
        return {"compte": r["compte"], "revoques": r["revoques"]}

    def prouver_revocation(ctx, res):
        return not idt.base.lire("SELECT 1 FROM agents_jetons WHERE compte=? AND actif=1", (res["compte"],))

    def mes_agents(ctx):
        c = moi_ou_erreur(ctx)
        return {"agents": idt.agents(c, tous=idt.droits.raison(c, "comptes.gerer")["accord"])}

    def valider_jeton_agent(ctx, jeton=""):
        return idt.valider_agent(jeton)

    # ---- modifier ----
    def modifier(ctx, compte="", sites=None, **profil):
        r = ok_ou_erreur(idt.modifier(compte, sites, **profil))
        ctx.emettre("compte.modifie", objet=("compte", compte.strip().lower()), donnees={"champs": sorted(profil) + (["sites"] if sites is not None else [])})
        return {"compte": compte.strip().lower(), "avant": r["avant"], "apres": r["apres"]}

    def modifier_moi(ctx, **profil):
        c = moi_ou_erreur(ctx)
        profil.pop("sites", None)                     # les sites d'un compte, c'est l'affaire de l'administrateur
        r = ok_ou_erreur(idt.modifier(c, None, **profil))
        ctx.emettre("compte.modifie", objet=("compte", c), donnees={"champs": sorted(profil)})
        return {"compte": c, "avant": r["avant"], "apres": r["apres"]}

    def prouver_modifier(ctx, res):
        a = idt.lire(res["compte"])
        return a is not None and all(a[k] == v for k, v in res["apres"].items())

    def defaire_modifier(ctx, res):
        av = dict(res["avant"])
        sites = av.pop("sites", None)
        idt.modifier(res["compte"], sites, **av)

    # ---- mot de passe ----
    def changer_mon_mot_de_passe(ctx, actuel="", nouveau=""):
        from noyau import CN_identite as identite
        c = moi_ou_erreur(ctx)
        if not identite.hash_ok(actuel, idt.hash_de(c) or ""):
            raise ValueError("Mot de passe actuel incorrect")
        r = ok_ou_erreur(idt.changer_mdp(c, nouveau))
        ctx.emettre("compte.mdp_change", objet=("compte", c), donnees={})
        return {"compte": c, "nouveau": nouveau, "ancien_hash": r["ancien_hash"]}

    def prouver_mdp(ctx, res):
        from noyau import CN_identite as identite
        return identite.hash_ok(res["nouveau"], idt.hash_de(res["compte"]) or "")

    def defaire_mdp(ctx, res):
        idt.poser_hash(res["compte"], res["ancien_hash"])

    def creer_jeton(ctx, compte="", heures=72):
        r = ok_ou_erreur(idt.jeton_creer(compte, int(heures)))
        return {"compte": r["compte"], "jeton": r["jeton"]}

    def prouver_jeton(ctx, res):
        return idt.jeton_compte(res["jeton"]) == res["compte"]

    def defaire_jeton(ctx, res):
        from noyau.CN_identite import _empreinte
        idt.base.ecrire("UPDATE jetons_mdp SET utilise=1 WHERE id=?", (_empreinte(res["jeton"]),))

    def reinitialiser(ctx, jeton="", nouveau=""):
        r = ok_ou_erreur(idt.reinitialiser(jeton, nouveau))
        ctx.emettre("compte.mdp_change", objet=("compte", r["compte"]), donnees={"par": "jeton"})
        return {"compte": r["compte"], "nouveau": nouveau, "ancien_hash": r["ancien_hash"], "jeton": jeton}

    # ---- supprimer, restaurer ----
    def supprimer(ctx, compte=""):
        r = ok_ou_erreur(idt.supprimer(compte))
        ctx.emettre("compte.supprime", objet=("compte", compte.strip().lower()), donnees={"corbeille": r["corbeille"]})
        return {"compte": compte.strip().lower(), "corbeille": r["corbeille"]}

    def prouver_supprimer(ctx, res):
        return (not idt.existe(res["compte"])) and any(x["id"] == res["corbeille"] for x in idt.corbeille())

    def defaire_supprimer(ctx, res):
        ok_ou_erreur(idt.restaurer(res["corbeille"]))

    def restaurer(ctx, corbeille=0):
        r = ok_ou_erreur(idt.restaurer(int(corbeille)))
        ctx.emettre("compte.restaure", objet=("compte", r["compte"]), donnees={})
        return {"compte": r["compte"]}

    def prouver_restaurer(ctx, res):
        return idt.existe(res["compte"])

    def defaire_restaurer(ctx, res):
        idt.supprimer(res["compte"])

    # ---- sessions ----
    def ouvrir_session(ctx, compte="", mot_de_passe="", ip="", agent="", preuve=None):
        r = idt.ouvrir(compte, mot_de_passe, ip, agent, preuve)
        c = (compte or "").strip().lower()
        if r["ok"]:
            ctx.emettre("session.ouverte", objet=("session", r["id"]), donnees={"compte": c, "ip": ip, "nature": __import__("noyau.CN_identite", fromlist=["x"]).ip_nature(ip)})
            return {"ok": True, "jeton": r["jeton"], "id": r["id"], "compte": c}
        if r.get("second_facteur"):
            return {"ok": False, "erreur": r["error"], "second_facteur": True, "methodes": r["methodes"], "invite": r["invite"]}
        ctx.emettre("session.refusee", objet=("compte", c), donnees={"ip": ip, "limite": bool(r.get("limite"))})
        return {"ok": False, "erreur": r["error"], "limite": bool(r.get("limite")), "attente_s": r.get("attente_s", 0)}

    def prouver_ouvrir(ctx, res):
        return (not res.get("ok")) or idt.valider(res.get("jeton", "")).get("ok", False) or res.get("jeton") == "***"

    def defaire_ouvrir(ctx, res):
        if res.get("ok") and res.get("jeton") != "***":
            idt.fermer(res["jeton"])

    def fermer_session(ctx, jeton=""):
        v = idt.valider(jeton)
        idt.fermer(jeton)
        if v.get("ok"):
            ctx.emettre("session.fermee", objet=("session", v["id"]), donnees={"compte": v["compte"]})
        return {"jeton": jeton}

    def prouver_fermer(ctx, res):
        return not idt.valider(res["jeton"]).get("ok", False)

    def revoquer_session(ctx, court=""):
        c = moi_ou_erreur(ctx)
        r = ok_ou_erreur(idt.revoquer(c, court))
        if r["ferme"]:
            ctx.emettre("session.fermee", objet=("session", court), donnees={"compte": c})
        return {"compte": c, "court": court, "ferme": r["ferme"]}

    def prouver_revoquer(ctx, res):
        return not any(s["id"] == res["court"] for s in idt.sessions(res["compte"]))

    def revoquer_autres(ctx, courant=""):
        c = moi_ou_erreur(ctx)
        n = idt.revoquer_autres(c, courant)
        return {"compte": c, "ferme": n, "courant": courant}

    def prouver_autres(ctx, res):
        restantes = idt.sessions(res["compte"], res["courant"])
        return all(s["current"] for s in restantes)

    for nom, f in (("moi", moi), ("lire", lire), ("lister", lister), ("corbeille", corbeille), ("regles_mdp", regles_mdp),
                   ("valider_session", valider_session), ("mes_sessions", mes_sessions)):
        ctx.implementer(nom, f)
    ctx.implementer("creer", creer, prouver_creer, defaire_creer)
    ctx.implementer("inviter_agent", inviter_agent, prouver_invitation, defaire_invitation)
    ctx.implementer("revoquer_agent", revoquer_agent, prouver_revocation, lambda ctx, res: None)
    ctx.implementer("mes_agents", mes_agents)
    ctx.implementer("valider_jeton_agent", valider_jeton_agent)
    ctx.implementer("modifier", modifier, prouver_modifier, defaire_modifier)
    ctx.implementer("modifier_moi", modifier_moi, prouver_modifier, defaire_modifier)
    ctx.implementer("changer_mon_mot_de_passe", changer_mon_mot_de_passe, prouver_mdp, defaire_mdp)
    ctx.implementer("creer_jeton", creer_jeton, prouver_jeton, defaire_jeton)
    ctx.implementer("reinitialiser_mot_de_passe", reinitialiser, prouver_mdp, defaire_mdp)
    ctx.implementer("supprimer", supprimer, prouver_supprimer, defaire_supprimer)
    ctx.implementer("restaurer", restaurer, prouver_restaurer, defaire_restaurer)
    ctx.implementer("ouvrir_session", ouvrir_session, prouver_ouvrir, defaire_ouvrir)
    ctx.implementer("fermer_session", fermer_session, prouver_fermer, lambda ctx, res: None)
    ctx.implementer("revoquer_session", revoquer_session, prouver_revoquer, lambda ctx, res: None)
    ctx.implementer("revoquer_autres_sessions", revoquer_autres, prouver_autres, lambda ctx, res: None)
