# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module des comptes
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : comptes
# ZONE       : CN
# VERSION CN : 0.5.0  #f5d069
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module des comptes : l'identité et ses preuves. La logique vit dans noyau/CN_identite.py (portée de la V18) ; ici, les capacités.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.5.0 empreinte=f5d069 ▼▼▼
"""Le module des comptes : l'identité et ses preuves. La logique vit dans noyau/CN_identite.py (portée de la V18) ; ici, les capacités.

Règle de la V18 gardée : le compte d'une action de session n'est JAMAIS un paramètre libre. C'est `ctx.compte`, le compte au nom duquel
l'exécuteur fait agir, sinon six caractères devinés fermeraient la session de quelqu'un d'autre.
"""


import json
import time


def _b64(octets):
    """Une image défaite part dans le résultat (donc au journal) en texte, jamais en octets bruts."""
    return __import__("base64").b64encode(octets).decode("ascii") if octets else None


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

    # ---- le cloisonnement par société : seul le superadministrateur voit et administre les comptes de toutes les sociétés ----
    def _large(ctx):
        return not ctx.compte or ctx.compte == "operateur" or idt.est_superadmin(ctx.compte)

    def _meme_societe(ctx, cible):
        """Un administrateur de société n'agit que sur les comptes de SA société. Un refus ne dit pas si le compte existe."""
        if _large(ctx):
            return
        if idt.societe_de(str(cible or "").strip().lower()) != (ctx.societe or idt.societe_de(ctx.compte)) or not idt.existe(str(cible or "").strip().lower()):
            raise ValueError("Ce compte n'est pas dans votre société")

    # ---- lectures ----
    PERSONNELS = ("personal_email", "personal_mobile", "birth", "address", "zip", "town", "state_code", "country_code")      # les coordonnées PRIVÉES : le droit « fiche_voir_perso » pour celles d'un autre

    # « Qui voit ma fiche » : quatre groupes de champs, trois publics. Moi voit tout ; mes collègues et les administrateurs voient ce que j'ai ouvert (par défaut : tout sauf le privé).
    # Le privé demande en plus le droit « fiche_voir_perso » : l'ouverture par son titulaire ne suffit pas, le droit ne suffit pas non plus.
    GROUPES_FICHE = {
        "identite": ("civility_code", "gender", "lastname", "firstname", "job"),
        "pro": ("email", "office_phone", "user_mobile", "office_fax", "employee", "ref_employee", "dateemployment", "dateemploymentend"),
        "presentation": ("lang", "color", "tz", "signature", "socialnetworks", "note_public"),
        "perso": PERSONNELS,
    }
    PUBLICS = ("collegues", "admins")
    DEFAUT_VIS = {"identite": {"collegues": True, "admins": True}, "pro": {"collegues": True, "admins": True},
                  "presentation": {"collegues": True, "admins": True}, "perso": {"collegues": False, "admins": False}}

    def _visibilite(cible):
        v = idt.pref(cible, "fiche_visibilite", {}) or {}
        sortie = {}
        for g, d in DEFAUT_VIS.items():
            x = v.get(g) if isinstance(v.get(g), dict) else {}
            sortie[g] = {a: bool(x.get(a, d[a])) for a in PUBLICS}
        return {"groupes": sortie, "journaliser": bool(idt.pref(cible, "fiche_journaliser", True))}

    def _fiche_visible(ctx, cible, tout=False):
        """La fiche de `cible` telle que `ctx.compte` a le droit de la voir : la sienne en entier ; celle d'un autre selon ce que son titulaire a ouvert à ce public."""
        f = idt.fiche(cible)
        if f is None or tout or cible == ctx.compte:
            return f
        public = "admins" if (_large(ctx) or idt.droits.est_admin(ctx.compte)) else "collegues"
        vis = _visibilite(cible)["groupes"]
        caches = set()
        for g, champs in GROUPES_FICHE.items():
            ouvert = vis[g][public]
            if g == "perso":
                ouvert = ouvert and (_large(ctx) or idt.droits.raison(ctx.compte, "comptes.fiche_voir_perso")["accord"])
            if not ouvert:
                caches.update(champs)
        return {k: ("" if k in caches else v) for k, v in f.items()}

    def fiche_visibilite(ctx):
        return _visibilite(moi_ou_erreur(ctx))

    def fiche_visibilite_regler(ctx, groupe="", public="", ouvert=True, journaliser=None):
        c = moi_ou_erreur(ctx)
        avant = _visibilite(c)
        if journaliser is not None:
            idt.pref_poser(c, "fiche_journaliser", bool(journaliser))
        if groupe or public:
            if groupe not in GROUPES_FICHE or public not in PUBLICS:
                raise ValueError("groupe (%s) et public (%s) attendus" % (", ".join(GROUPES_FICHE), ", ".join(PUBLICS)))
            v = dict(idt.pref(c, "fiche_visibilite", {}) or {})
            g = dict(v.get(groupe) or {})
            g[public] = bool(ouvert)
            v[groupe] = g
            idt.pref_poser(c, "fiche_visibilite", v)
        ctx.emettre("compte.modifie", objet=("compte", c), donnees={"champs": ["visibilite_fiche"]})
        return {"compte": c, "avant": avant, "apres": _visibilite(c)}

    def prouver_visibilite(ctx, res):
        return _visibilite(res["compte"]) == res["apres"]

    def defaire_visibilite(ctx, res):
        idt.pref_poser(res["compte"], "fiche_visibilite", res["avant"]["groupes"])
        idt.pref_poser(res["compte"], "fiche_journaliser", res["avant"]["journaliser"])

    def moi(ctx):
        c = moi_ou_erreur(ctx)
        d = idt.lire(c)
        if d is not None:
            d["fiche"] = idt.fiche(c)
            d["nom_affiche"] = idt.nom_affiche(c)
        return d

    def lire(ctx, compte=""):
        _meme_societe(ctx, compte)
        d = idt.lire(compte)
        if d is not None:
            cible = d["compte"]
            d["fiche"] = _fiche_visible(ctx, cible)
            d["nom_affiche"] = idt.nom_affiche(cible)
            if ctx.compte and cible != ctx.compte and d["fiche"] is not None and _visibilite(cible)["journaliser"]:
                ctx.emettre("compte.fiche_vue", objet=("compte", cible), donnees={"par": ctx.compte})      # l'accès à la fiche d'un autre se journalise : elle le voit dans « Mon compte »
        return d

    def fiche_modifier(ctx, compte="", champs=None):
        """Écrit des champs de la fiche d'un AUTRE compte (la sienne : modifier_moi). Réservé au droit « fiche_modifier_autres », dans sa société."""
        cible = str(compte or "").strip().lower()
        if cible == ctx.compte:
            raise ValueError("Votre propre fiche se modifie par « modifier_moi »")
        if not (_large(ctx) or idt.droits.raison(ctx.compte, "comptes.fiche_modifier_autres")["accord"]):
            raise PermissionError("modifier la fiche d'un autre compte demande le droit comptes.fiche_modifier_autres")
        _meme_societe(ctx, cible)
        r = ok_ou_erreur(idt.fiche_ecrire(cible, champs or {}))
        ctx.emettre("compte.modifie", objet=("compte", cible), donnees={"champs": sorted(r["apres"]), "par": ctx.compte})
        return {"compte": cible, "fiche_avant": r["avant"], "fiche_apres": r["apres"]}

    def prouver_fiche_modifier(ctx, res):
        f = idt.fiche(res["compte"]) or {}
        return all(f.get(k) == v for k, v in res["fiche_apres"].items())

    def defaire_fiche_modifier(ctx, res):
        if res["fiche_avant"]:
            idt.fiche_ecrire(res["compte"], res["fiche_avant"])

    # ---- les identités liées : le pseudo FastPanel et l'utilisateur système (bash). Réservées aux administrateurs : elles ouvrent l'hébergement et le shell ----
    def _admin(ctx):
        if not (_large(ctx) or idt.droits.est_admin(ctx.compte)):
            raise PermissionError("lier une identité (FastPanel, système) est réservé aux administrateurs")

    def identites(ctx, compte=""):
        c = moi_ou_erreur(ctx)
        cible = str(compte or c).strip().lower()
        if cible != c:
            _admin(ctx)
            _meme_societe(ctx, cible)
        d = idt.lire(cible)
        if d is None:
            raise ValueError("Ce compte n'existe pas")
        peut = bool(_large(ctx) or idt.droits.est_admin(c))
        return {"compte": cible, "fp_account": d.get("fp_account", ""), "unix_user": d.get("unix_user", ""), "unix_etat": d.get("unix_etat", ""),
                "superadmin": bool(d.get("superadmin")), "admin": bool(d.get("admin")), "peut_modifier": peut,
                "bash_autorise": bool(d.get("admin")) or bool(d.get("superadmin"))}

    def identite_lier(ctx, compte="", fp_account=None, unix_user=None):
        _admin(ctx)
        cible = str(compte or "").strip().lower()
        _meme_societe(ctx, cible)
        avant, apres = {}, {}
        if fp_account is not None:
            r = ok_ou_erreur(idt.lier_fastpanel(cible, str(fp_account)))
            avant["fp_account"], apres["fp_account"] = r["avant"], r["apres"]
        if unix_user is not None:
            r = ok_ou_erreur(idt.lier_unix(cible, str(unix_user)))
            avant["unix_user"], apres["unix_user"] = r["avant"], r["apres"]
        if not apres:
            raise ValueError("rien à lier : fp_account et/ou unix_user")
        ctx.emettre("compte.modifie", objet=("compte", cible), donnees={"champs": sorted(apres), "par": ctx.compte})
        return {"compte": cible, "avant": avant, "apres": apres}

    def prouver_identite_lier(ctx, res):
        d = idt.lire(res["compte"]) or {}
        return all(d.get(k) == v for k, v in res["apres"].items())

    def defaire_identite_lier(ctx, res):
        if "fp_account" in res["avant"]:
            idt.lier_fastpanel(res["compte"], res["avant"]["fp_account"])
        if "unix_user" in res["avant"]:
            idt.base.ecrire("UPDATE comptes SET unix_user=? WHERE compte=?", (res["avant"]["unix_user"], res["compte"]))

    # ---- les appareils : « se souvenir de cet appareil » (30 jours) et l'approbation d'un appareil neuf pour un administrateur ----
    def appareils(ctx, courant=""):
        c = moi_ou_erreur(ctx)
        return {"appareils": idt.appareils(c, str(courant or "")), "mode_admin": str(idt.parametre("admin_nouvel_appareil", "alerter")),
                "admin": bool(idt.droits.est_admin(c)), "jours": __import__("noyau.CN_identite", fromlist=["x"]).APPAREIL_CONFIANCE_JOURS}

    def appareil_confiance(ctx, appareil="", oui=True):
        c = moi_ou_erreur(ctx)
        r = ok_ou_erreur(idt.appareil_confiance(c, str(appareil), bool(oui)))
        return {"compte": c, "appareil": str(appareil), "avant": r["avant"], "apres": r["apres"]}

    def prouver_confiance(ctx, res):
        return any(a["id"] == res["appareil"] and bool(a["confiance_jusqua"]) == bool(res["apres"]) for a in idt.appareils(res["compte"]))

    def defaire_confiance(ctx, res):
        idt.base.ecrire("UPDATE appareils SET confiance=? WHERE compte=? AND empreinte=?", (res["avant"], res["compte"], res["appareil"]))

    def appareil_decider(ctx, appareil="", approuver=True, compte=""):
        c = moi_ou_erreur(ctx)
        cible = str(compte or c).strip().lower()
        if cible != c:
            _admin(ctx)
            _meme_societe(ctx, cible)
        r = ok_ou_erreur(idt.appareil_decider(cible, str(appareil), bool(approuver)))
        ctx.emettre("compte.modifie", objet=("compte", cible), donnees={"champs": ["appareil"], "par": c})
        return {"compte": cible, "appareil": str(appareil), "approuve": bool(approuver), "avant": r["avant"]}

    def prouver_decision(ctx, res):
        ligne = [a for a in idt.appareils(res["compte"]) if a["id"] == res["appareil"]]
        return (bool(ligne) and ligne[0]["statut"] == "approuve") if res["approuve"] else not ligne

    def defaire_decision(ctx, res):
        pass                      # un appareil refusé se retire ; il se représentera et attendra de nouveau

    # ---- « À faire sur mon compte » : chaque module déclare ses attentes ([[attentes]], une lecture qui rend faux ou {titre, texte}) ; ici on les rassemble ----
    def attente_cle(ctx):
        """La seconde clé de sécurité, vue par le module webauthn (qui sait si une clé peut se poser ici)."""
        e = ctx.executer_lecture("webauthn.etat")
        if not e or e.get("disponible") is False:
            return False
        n = len(e.get("cles") or [])
        if n >= 2:
            return False
        return {"titre": "Ajouter une seconde clé de sécurité" if n else "Poser une clé de sécurité",
                "texte": "Si la première est perdue, vous ne pouvez plus entrer." if n else "Votre mot de passe est aujourd'hui votre seul verrou.", "par": "webauthn"}

    def attente_fiche(ctx):
        f = idt.fiche(moi_ou_erreur(ctx))
        if f is None or f.get("lastname"):
            return False
        return {"titre": "Compléter ma fiche", "texte": "Votre nom n'est pas renseigné : il s'affiche partout où l'on vous nomme."}

    def attente_appareils(ctx):
        n = [a for a in idt.appareils(moi_ou_erreur(ctx)) if a["statut"] == "attente"]
        if not n:
            return False
        return {"titre": "%d appareil(s) attendent votre approbation" % len(n), "texte": "Un administrateur ne peut entrer sur un appareil neuf que si une session déjà ouverte l'approuve."}

    def mes_attentes(ctx):
        sortie = []
        for man in ctx.manifestes_actifs():
            for a in getattr(man, "attentes", ()) or ():
                try:
                    r = ctx.executer_lecture("%s.%s" % (man.id, a.capacite))
                except Exception:
                    r = None
                if r:
                    r = r if isinstance(r, dict) else {}
                    sortie.append({"module": man.id, "id": a.id, "titre": r.get("titre", a.id), "texte": r.get("texte", ""), "vers": a.vers, "action": a.action,
                                   "niveau": a.niveau, "par": r.get("par", man.id)})
        return {"attentes": sortie}

    # ---- le journal de MON compte : les mêmes événements que le registre de la machine, filtrés sur moi (connexions, sessions, mot de passe, fiche, droits) ----
    TEXTES = {"session.ouverte": "Connexion", "session.refusee": "Connexion refusée", "session.fermee": "Session fermée", "compte.mdp_change": "Mot de passe changé",
              "compte.modifie": "Fiche ou profil modifié", "compte.nouvel_appareil": "Connexion depuis un appareil jamais vu", "compte.fiche_vue": "Fiche consultée par un autre compte",
              "compte.desactive": "Compte désactivé", "compte.reactive": "Compte réactivé", "droit.change": "Droits modifiés"}

    def mon_journal(ctx, limite=30):
        c = moi_ou_erreur(ctx)
        limite = max(1, min(int(limite or 30), 200))
        lignes = idt.base.lire(
            "SELECT ts, type, acteur, objet_type, objet_id, compte, donnees FROM evenements WHERE (type LIKE 'session.%' OR type LIKE 'compte.%' OR type='droit.change') AND "
            "((objet_type='compte' AND objet_id=?) OR compte=? OR donnees LIKE ?) ORDER BY id DESC LIMIT ?", (c, c, '%"' + c.replace("%", "").replace("_", "") + '"%', limite * 3))
        sortie = []
        for r in lignes:
            try:
                d = json.loads(r["donnees"] or "{}")
            except ValueError:
                d = {}
            if r["type"].startswith("session.") and d.get("compte", r["objet_id"] if r["objet_type"] == "compte" else "") != c:
                continue                                     # une session d'un autre compte qui cite mon adresse dans un détail : pas la mienne
            if r["type"] == "droit.change" and d.get("sujet") != c:
                continue
            if r["type"].startswith("compte.") and not (r["objet_type"] == "compte" and r["objet_id"] == c):
                continue                                     # ce que j'ai fait sur le compte d'un autre n'est pas l'histoire du mien
            if r["type"] == "compte.fiche_vue":
                par = d.get("par") or ""
                texte = "Fiche consultée par %s" % idt.nom_affiche(par) if par else TEXTES[r["type"]]
            else:
                texte = TEXTES.get(r["type"], r["type"])
            sortie.append({"ts": r["ts"], "type": r["type"], "texte": texte, "ip": d.get("ip", ""), "champs": d.get("champs", [])})
            if len(sortie) >= limite:
                break
        return {"evenements": sortie}

    # ---- le portrait : UN résolveur. La source choisie d'abord, puis le repli ; une image téléversée par le compte n'est jamais écrasée par une source externe ----
    SOURCES = ("propre", "dolibarr", "fastpanel", "telegram")
    CAPACITE_SOURCE = {"dolibarr": "dolibarr.portrait", "fastpanel": "fastpanel.avatar", "telegram": "telegram.portrait"}
    CACHE = {}                                                                                 # (compte, source) -> (instant, image) : clé PAR COMPTE, jamais un global sans compte
    DUREE_CACHE = 300

    def _initiales(c):
        mots = (idt.nom_affiche(c) or c).split()
        return ("".join(m[0] for m in mots[:2]) if len(mots) > 1 else (mots[0][:2] if mots else c[:2])).upper()

    def _image_source(ctx, c, source):
        if source == "propre":
            p = idt.portrait_lire(c)
            return {"type": p[0], "base64": __import__("base64").b64encode(p[1]).decode("ascii")} if p else None
        cap = CAPACITE_SOURCE.get(source)
        if not cap:
            return None
        cle = (c, source)
        vu = CACHE.get(cle)
        if vu and time.time() - vu[0] < DUREE_CACHE:
            return vu[1]
        try:
            r = ctx.executer_lecture(cap)
        except Exception:
            r = None                                     # le module est absent ou en panne : cette source n'a pas d'image, la suivante prend le relais
        r = r if (r and r.get("present")) else None
        CACHE[cle] = (time.time(), r)
        return r

    def portrait(ctx, source="", detail=False):
        """Mon portrait : l'image de la source choisie (dans ma fiche, ou celle que l'on demande), sinon la première qui en a une, sinon mes initiales."""
        c = moi_ou_erreur(ctx)
        f = idt.fiche(c)
        if f is None:
            raise ValueError("un agent ou un compte système n'a pas de portrait")
        demandee = str(source or f.get("photo_source") or "").strip().lower()
        if demandee and demandee not in SOURCES + ("initiales",):
            raise ValueError("source de portrait inconnue : %s" % demandee)
        chaine = [] if demandee == "initiales" else ([demandee] if demandee else []) + [s for s in SOURCES if s != demandee]
        sortie = {"demandee": demandee, "source": "initiales", "present": False, "initiales": _initiales(c)}
        for s in chaine:
            img = _image_source(ctx, c, s)
            if img:
                sortie.update({"source": s, "present": True, "type": img["type"], "base64": img["base64"]})
                break
        if detail:
            sortie["disponibles"] = {s: bool(_image_source(ctx, c, s)) for s in SOURCES}
        return sortie

    def portrait_poser(ctx, image=""):
        c = moi_ou_erreur(ctx)
        try:
            brut = __import__("base64").b64decode(str(image or ""), validate=True)
        except Exception:
            raise ValueError("image : du base64 attendu")
        r = ok_ou_erreur(idt.portrait_poser(c, brut))
        avant_source = (idt.fiche(c) or {}).get("photo_source", "")
        idt.portrait_source_poser(c, "propre")           # téléverser, c'est choisir : la source repasse sur l'image propre
        CACHE.pop((c, "propre"), None)
        ctx.emettre("compte.modifie", objet=("compte", c), donnees={"champs": ["portrait"]})
        return {"compte": c, "type": r["type"], "octets": r["octets"], "avant": _b64(r["avant"]), "avant_source": avant_source}

    def prouver_portrait_poser(ctx, res):
        p = idt.portrait_lire(res["compte"])
        return p is not None and len(p[1]) == res["octets"]

    def defaire_portrait_poser(ctx, res):
        if res["avant"]:
            idt.portrait_poser(res["compte"], __import__("base64").b64decode(res["avant"]))
        else:
            idt.portrait_retirer(res["compte"])
        idt.portrait_source_poser(res["compte"], res["avant_source"])

    def portrait_retirer(ctx):
        c = moi_ou_erreur(ctx)
        r = idt.portrait_retirer(c)
        source = (idt.fiche(c) or {}).get("photo_source", "")
        if source == "propre":
            idt.portrait_source_poser(c, "")
        ctx.emettre("compte.modifie", objet=("compte", c), donnees={"champs": ["portrait"]})
        return {"compte": c, "avant": _b64(r["avant"]), "avant_source": source}

    def prouver_portrait_retire(ctx, res):
        return idt.portrait_lire(res["compte"]) is None

    def defaire_portrait_retire(ctx, res):
        if res["avant"]:
            idt.portrait_poser(res["compte"], __import__("base64").b64decode(res["avant"]))
            idt.portrait_source_poser(res["compte"], res["avant_source"])

    def portrait_source(ctx, source=""):
        c = moi_ou_erreur(ctx)
        r = ok_ou_erreur(idt.portrait_source_poser(c, source))
        ctx.emettre("compte.modifie", objet=("compte", c), donnees={"champs": ["photo_source"]})
        return {"compte": c, "avant": r["avant"], "apres": r["apres"]}

    def prouver_portrait(ctx, res):
        return (idt.fiche(res["compte"]) or {}).get("photo_source") == res["apres"]

    def defaire_portrait(ctx, res):
        idt.portrait_source_poser(res["compte"], res["avant"])

    def lister(ctx):
        tous = idt.lister()
        if not _large(ctx):
            soc = ctx.societe or idt.societe_de(ctx.compte)
            tous = [c for c in tous if c.get("societe", "1") == soc]
        return {"comptes": tous}

    def corbeille(ctx):
        return {"corbeille": idt.corbeille("" if _large(ctx) else (ctx.societe or idt.societe_de(ctx.compte)))}

    def regles_mdp(ctx):
        from noyau import CN_identite as identite
        return {"regles": identite.mdp_regles(), "legende": identite.mdp_legende()}

    def valider_session(ctx, jeton=""):
        return idt.valider(jeton)

    def mes_sessions(ctx, courant=""):
        return {"sessions": idt.sessions(moi_ou_erreur(ctx), courant)}

    # ---- créer ----
    def creer(ctx, compte="", mot_de_passe="", sites=None, superadmin=False, unix_user="", societe="", **profil):
        # Tout compte appartient à une société. Sans précision : celle dans laquelle on agit (la principale sinon). Choisir une AUTRE société que la sienne
        # est réservé au superadministrateur : l'administrateur d'une société n'ajoute des utilisateurs que chez lui.
        societe = (societe or "").strip()
        if societe and ctx.compte and societe != (ctx.societe or "1") and not idt.est_superadmin(ctx.compte) and ctx.compte != "operateur":
            raise ValueError("Seul le superadministrateur range un compte dans une autre société que la sienne")
        if not societe:
            societe = ctx.societe or ""
        if superadmin:
            moi = idt.lire(ctx.compte) if ctx.compte else None
            if ctx.compte != "operateur" and not (moi and moi["superadmin"]):
                raise ValueError("Seul un superadministrateur (ou l'opérateur local) crée un superadministrateur")
        r = idt.creer(compte, mot_de_passe, sites, bool(superadmin), unix_user, societe=societe, **profil)
        ctx.emettre("compte.cree", objet=("compte", (compte or "").strip().lower()), donnees={"admin": r.get("admin"), "ok": r["ok"]}) if r["ok"] else None
        if not r["ok"]:
            raise ValueError(r["error"])
        return {"compte": r["compte"], "admin": r["admin"], "superadmin": r["superadmin"], "unix_user": r["unix_user"], "unix_demande": r["unix_demande"]}

    def prouver_creer(ctx, res):
        return idt.existe(res["compte"])

    def transferer(ctx, compte="", societe=""):
        """Rattache un compte à une autre société. Réservé au superadministrateur. Les fonctions qu'il tenait dans son ancienne société tombent."""
        if ctx.compte and ctx.compte != "operateur" and not idt.est_superadmin(ctx.compte):
            raise ValueError("Seul le superadministrateur change un compte de société")
        cible = str(compte or "").strip().lower()
        if not idt.existe(cible):
            raise ValueError("compte inconnu")
        soc = idt.societe_valide(societe)
        if soc is None:
            raise ValueError("Société inconnue ou archivée : tout compte appartient à une société")
        avant = idt.societe_de(cible)
        if avant == soc:
            raise ValueError("ce compte est déjà dans cette société")
        retires = [g["groupe"] for g in idt.droits.tous_groupes_de(cible) if g["societe"] == avant]
        for g in retires:
            idt.droits.regler_membre(cible, g, False)
        import time
        idt.base.ecrire("UPDATE comptes SET societe=?, maj=? WHERE compte=?", (soc, time.time(), cible))
        return {"compte": cible, "avant": avant, "apres": soc, "retires": retires}

    def prouver_transferer(ctx, res):
        return idt.societe_de(res["compte"]) == res["apres"]

    def defaire_transferer(ctx, res):
        idt.base.ecrire("UPDATE comptes SET societe=? WHERE compte=?", (res["avant"], res["compte"]))
        for g in res.get("retires", []):
            if idt.droits.groupe(g):
                idt.droits.regler_membre(res["compte"], g, True)

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
        _meme_societe(ctx, compte)
        r = ok_ou_erreur(idt.modifier(compte, sites, **profil))
        ctx.emettre("compte.modifie", objet=("compte", compte.strip().lower()), donnees={"champs": sorted(profil) + (["sites"] if sites is not None else [])})
        return {"compte": compte.strip().lower(), "avant": r["avant"], "apres": r["apres"], "fiche_avant": r.get("fiche_avant", {}), "fiche_apres": r.get("fiche_apres", {})}

    def modifier_moi(ctx, **profil):
        c = moi_ou_erreur(ctx)
        profil.pop("sites", None)                     # les sites d'un compte, c'est l'affaire de l'administrateur
        r = ok_ou_erreur(idt.modifier(c, None, **profil))
        ctx.emettre("compte.modifie", objet=("compte", c), donnees={"champs": sorted(profil)})
        return {"compte": c, "avant": r["avant"], "apres": r["apres"], "fiche_avant": r.get("fiche_avant", {}), "fiche_apres": r.get("fiche_apres", {})}

    def prouver_modifier(ctx, res):
        a = idt.lire(res["compte"])
        if a is None or not all(a[k] == v for k, v in res["apres"].items()):
            return False
        f = idt.fiche(res["compte"]) or {}
        return all(f.get(k) == v for k, v in (res.get("fiche_apres") or {}).items())        # et la fiche dit ce que l'on vient d'écrire

    def defaire_modifier(ctx, res):
        av = dict(res["avant"])
        sites = av.pop("sites", None)
        fa = res.get("fiche_avant") or {}
        if fa:                                                   # la fiche se remet par ses propres champs : les anciens n'en sont que le reflet
            for k in ("display_name", "role_label", "contact_email", "phone", "lang"):
                av.pop(k, None)
        idt.modifier(res["compte"], sites, **av)
        if fa:
            idt.fiche_ecrire(res["compte"], fa)

    # ---- mot de passe ----
    def changer_mon_mot_de_passe(ctx, actuel="", nouveau="", courant=""):
        # Un mot de passe changé ferme les autres sessions du compte (comme la réinitialisation par lien) ; celle qui sert au geste reste.
        # Sans session courante connue (appel hors navigateur), on ne ferme rien : on ne devine pas laquelle garder.
        from noyau import CN_identite as identite
        c = moi_ou_erreur(ctx)
        if not identite.hash_ok(actuel, idt.hash_de(c) or ""):
            raise ValueError("Mot de passe actuel incorrect")
        r = ok_ou_erreur(idt.changer_mdp(c, nouveau))
        fermees = idt.revoquer_autres(c, courant) if courant else 0
        ctx.emettre("compte.mdp_change", objet=("compte", c), donnees={"sessions_fermees": fermees})
        return {"compte": c, "nouveau": nouveau, "ancien_hash": r["ancien_hash"], "courant": courant, "sessions_fermees": fermees}

    def prouver_mdp(ctx, res):
        from noyau import CN_identite as identite
        if not identite.hash_ok(res["nouveau"], idt.hash_de(res["compte"]) or ""):
            return False
        return not res.get("courant") or len(idt.sessions(res["compte"], res["courant"])) <= 1      # aucune autre session ne survit

    def defaire_mdp(ctx, res):
        idt.poser_hash(res["compte"], res["ancien_hash"])

    def creer_jeton(ctx, compte="", heures=72):
        _meme_societe(ctx, compte)
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
        _meme_societe(ctx, compte)
        r = ok_ou_erreur(idt.supprimer(compte))
        ctx.emettre("compte.supprime", objet=("compte", compte.strip().lower()), donnees={"corbeille": r["corbeille"]})
        return {"compte": compte.strip().lower(), "corbeille": r["corbeille"]}

    def prouver_supprimer(ctx, res):
        return (not idt.existe(res["compte"])) and any(x["id"] == res["corbeille"] for x in idt.corbeille())

    def defaire_supprimer(ctx, res):
        ok_ou_erreur(idt.restaurer(res["corbeille"]))

    # ---- désactiver, réactiver : le départ d'un utilisateur, sans rien supprimer ----
    def desactiver(ctx, compte="", vers="", agents="revoquer"):
        _meme_societe(ctx, compte)
        compte = compte.strip().lower()
        r = ok_ou_erreur(idt.desactiver(compte, vers, agents))
        ctx.emettre("compte.desactive", objet=("compte", compte),
                    donnees={"vers": r["vers"], "agents": r["agents"], "agents_touches": len(r["agents_touches"]), "sites": len(r["sites_avant"])})
        return dict(r, compte=compte)

    def prouver_desactiver(ctx, res):
        return idt.desactive(res["compte"])

    def defaire_desactiver(ctx, res):
        idt.restituer_depart(res["compte"], res)

    def reactiver(ctx, compte=""):
        _meme_societe(ctx, compte)
        compte = compte.strip().lower()
        ok_ou_erreur(idt.reactiver(compte))
        ctx.emettre("compte.reactive", objet=("compte", compte), donnees={})
        return {"compte": compte}

    def prouver_reactiver(ctx, res):
        return not idt.desactive(res["compte"])

    def defaire_reactiver(ctx, res):
        idt.desactiver(res["compte"])

    def restaurer(ctx, corbeille=0):
        if not _large(ctx) and int(corbeille) not in {c["id"] for c in idt.corbeille(ctx.societe or idt.societe_de(ctx.compte))}:
            raise ValueError("Rien de tel dans la corbeille de votre société")
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
            bloquer = str(idt.parametre("admin_nouvel_appareil", "alerter")) == "bloquer" and idt.droits.est_admin(c) and not idt.est_superadmin(c)      # jamais le superadministrateur : qui approuverait ?
            vu = idt.appareil_vu(c, ip, agent, bloquer=bloquer)
            if vu == "attente":                                  # un administrateur sur un appareil neuf : il attend l'approbation d'une session déjà ouverte
                idt.fermer(r["jeton"])
                ctx.emettre("compte.nouvel_appareil", objet=("compte", c), donnees={"ip": ip, "agent": (agent or "")[:60], "bloque": True})
                return {"ok": False, "erreur": "Appareil jamais vu : un administrateur doit l'approuver depuis une session déjà ouverte (Mon compte › Sécurité › Appareils)", "appareil_attente": True}
            if vu == "nouveau":                                  # un appareil jamais vu pour ce compte : le module des notifications en parle au titulaire
                ctx.emettre("compte.nouvel_appareil", objet=("compte", c), donnees={"ip": ip, "agent": (agent or "")[:60], "session": r["id"]})
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
    ctx.implementer("transferer", transferer, prouver_transferer, defaire_transferer)
    ctx.implementer("inviter_agent", inviter_agent, prouver_invitation, defaire_invitation)
    ctx.implementer("revoquer_agent", revoquer_agent, prouver_revocation, lambda ctx, res: None)
    ctx.implementer("mes_agents", mes_agents)
    ctx.implementer("valider_jeton_agent", valider_jeton_agent)
    ctx.implementer("modifier", modifier, prouver_modifier, defaire_modifier)
    ctx.implementer("modifier_moi", modifier_moi, prouver_modifier, defaire_modifier)
    ctx.implementer("fiche_modifier", fiche_modifier, prouver_fiche_modifier, defaire_fiche_modifier)
    ctx.implementer("portrait_source", portrait_source, prouver_portrait, defaire_portrait)
    ctx.implementer("mon_journal", mon_journal)
    ctx.implementer("attente_cle", attente_cle)
    ctx.implementer("attente_fiche", attente_fiche)
    ctx.implementer("attente_appareils", attente_appareils)
    ctx.implementer("mes_attentes", mes_attentes)
    ctx.implementer("fiche_visibilite", fiche_visibilite)
    ctx.implementer("fiche_visibilite_regler", fiche_visibilite_regler, prouver_visibilite, defaire_visibilite)
    ctx.implementer("identites", identites)
    ctx.implementer("identite_lier", identite_lier, prouver_identite_lier, defaire_identite_lier, simuler=lambda x, compte="", **_: "lierait les identités (FastPanel, système) du compte %s" % compte)
    ctx.implementer("appareils", appareils)
    ctx.implementer("appareil_confiance", appareil_confiance, prouver_confiance, defaire_confiance)
    ctx.implementer("appareil_decider", appareil_decider, prouver_decision, defaire_decision)
    ctx.implementer("portrait", portrait)
    ctx.implementer("portrait_poser", portrait_poser, prouver_portrait_poser, defaire_portrait_poser)
    ctx.implementer("portrait_retirer", portrait_retirer, prouver_portrait_retire, defaire_portrait_retire)
    ctx.implementer("changer_mon_mot_de_passe", changer_mon_mot_de_passe, prouver_mdp, defaire_mdp)
    ctx.implementer("creer_jeton", creer_jeton, prouver_jeton, defaire_jeton)
    ctx.implementer("reinitialiser_mot_de_passe", reinitialiser, prouver_mdp, defaire_mdp)
    ctx.implementer("supprimer", supprimer, prouver_supprimer, defaire_supprimer)
    ctx.implementer("desactiver", desactiver, prouver_desactiver, defaire_desactiver)
    ctx.implementer("reactiver", reactiver, prouver_reactiver, defaire_reactiver)
    ctx.implementer("restaurer", restaurer, prouver_restaurer, defaire_restaurer)
    ctx.implementer("ouvrir_session", ouvrir_session, prouver_ouvrir, defaire_ouvrir)
    ctx.implementer("fermer_session", fermer_session, prouver_fermer, lambda ctx, res: None)
    ctx.implementer("revoquer_session", revoquer_session, prouver_revoquer, lambda ctx, res: None)
    ctx.implementer("revoquer_autres_sessions", revoquer_autres, prouver_autres, lambda ctx, res: None)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : brancher
# EC : néant (aucun point d'évolution déclaré pour l'instant)
# LIEN : à compléter (contrat, fichiers voisins)
