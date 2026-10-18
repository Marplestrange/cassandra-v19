# ══════════════════════════════════════════════════════════════════════════════
# TITRE      : Le module d'affichage
# LICENCE    : AGPL-3.0
# AUTEUR     : Atek Drisse
# GIT        : github.com/Marplestrange
# MAIL       : marplestrange@cassandra.center
# MODULE     : affichage
# ZONE       : CN
# VERSION CN : 0.2.1  #0265d6
# VERSION EC : néant
# EC LIÉES   : néant
# RÔLE       : Le module d'affichage : thème et mise en page, assemblés à partir de ce que les modules DÉCLARENT.
# MÉTHODE    : à compléter par l'auteur (comment le fichier s'y prend)
# ══════════════════════════════════════════════════════════════════════════════
# ▼▼▼ BORNE CN version=0.2.1 empreinte=0265d6 ▼▼▼
"""Le module d'affichage : thème et mise en page, assemblés à partir de ce que les modules DÉCLARENT.

Un module ne dit jamais comment il s'affiche. Il déclare des écrans (avec un gabarit), des tuiles (avec un composant et une source de données) et
une touche de couleur. Ce module les assemble et sert à l'interface un descripteur générique : activer un module fait apparaître ses tuiles et son
accent, le désactiver les retire, sans toucher à l'interface.

  - le catalogue (écrans, tuiles, accents) est un objet du registre, rebâti par un moteur quand un module est branché ou débranché ;
  - un second moteur lit les sources des tuiles à leur rythme : l'interface lit une donnée prête, elle n'appelle jamais les modules ;
  - le thème est résolu ici : jetons du noyau, accent choisi, touches des modules ; un accent sans contraste suffisant est refusé ;
  - la DISPOSITION des menus (groupes de la barre du haut, entrées et sous-entrées de la colonne, menu de l'avatar) : le nexus lit l'arbre des menus pour le compte,
    appelle le point d'évolution `disposition` (qui range, sans rien décider d'accès), puis retire lui-même ce que le rôle ou le droit ne permet pas ;
  - les IDÉES du panneau conversationnel (point `idees`), les pages épinglées, l'organisation (nom, logo), les fils du panneau liés à une page.
"""
import base64
import copy
import hashlib
import json
import re
import time
import zoneinfo
from pathlib import Path

BASES = {
    "clair": {"bg": "#eef1f5", "halo": "#e3e9f1", "surf": "rgba(255,255,255,.72)", "surf2": "rgba(255,255,255,.5)", "ink": "#101828",
              "ink2": "#475467", "faint": "#8b95a3", "line": "rgba(16,24,40,.09)", "accent": "#0b7c74", "on-accent": "#ffffff",
              "ok": "#047857", "warn": "#b45309", "danger": "#be123c", "info": "#3b5bdb"},
    "sombre": {"bg": "#0c1116", "halo": "#142029", "surf": "rgba(28,36,46,.72)", "surf2": "rgba(28,36,46,.45)", "ink": "#e8edf3",
               "ink2": "#a9b4c2", "faint": "#6f7b8a", "line": "rgba(232,237,243,.10)", "accent": "#34c3b6", "on-accent": "#06201d",
               "ok": "#3ddc97", "warn": "#f2a23c", "danger": "#ff6b8b", "info": "#8da2ff"},
}
DENSITES = {"normale": {"gap": "16px", "pad": "14px", "rayon": "16px"}, "compacte": {"gap": "10px", "pad": "9px", "rayon": "12px"}}
THEMES = ("clair", "sombre", "auto")
ZONES = ("entete", "principal", "lateral")
TAILLES = ("s", "m", "l")
CATALOGUE = ("affichage_catalogue", "global")
_COULEUR = re.compile(r"^#[0-9a-fA-F]{6}$")

VERSION_AFFICHEE = "19.0"
INTERLOCUTEURS = ("itare", "cassandra", "inv")
RANG_NIVEAU = {"": 0, "alerte": 1, "danger": 2}
PERSONNELS = ("tache", "rappel", "event", "decision", "mandat", "note", "mail")      # ce qu'Itare voit : le poste de travail du compte, jamais l'état du parc
MAX_EPINGLES = 12
ORG_DEFAUT = {"nom": "Cassandra", "forme": "", "identifiant": "", "adresse": "", "fuseau": "Europe/Paris", "langue": "fr", "logo": ""}
ORG_LONGUEURS = {"nom": 60, "forme": 60, "identifiant": 40, "adresse": 160}
LOGO_MAX = 180000
_LOGO = re.compile(r"^data:image/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/]+={0,2}$")
_FUSEAU = re.compile(r"^[A-Za-z]+(/[A-Za-z0-9_+-]+){1,2}$|^UTC$")
_CLE_EPINGLE = re.compile(r"^[a-z0-9_:.|-]{1,120}$", re.I)
# Les gestes que le panneau a le droit de PROPOSER : une table fermée du nexus. Proposer n'est pas faire : l'exécution passe par l'exécuteur, qui refait toute vérification de droit.
ACTES = {
    "relire_cert": {"capacite": "certificats.relire_expiration", "arg": "hote", "nat": "ssl", "qui": "cassandra", "admin": True, "risque": "lecture",
                    "titre": "Relire l’expiration du certificat", "perimetre": "un hôte, en lecture seule",
                    "preuve": "l’expiration est relue sur le certificat réellement servi", "retour": "aucun : c’est une lecture"},
}


# ------------------------------------------------------------------ contraste (WCAG)
def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _luminance(h):
    def c(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (c(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def meilleur_texte(fond):
    """Le texte (blanc ou presque noir) le plus lisible sur ce fond."""
    return "#ffffff" if contraste("#ffffff", fond) >= contraste("#101828", fond) else "#101828"


def accent_ok(accent, mode):
    """Un accent doit se distinguer du fond (3:1, composants d'interface) et porter un texte lisible (4,5:1)."""
    if not _COULEUR.match(accent or ""):
        return False
    return contraste(accent, BASES[mode]["bg"]) >= 3.0 and contraste(meilleur_texte(accent), accent) >= 4.5


def _rgba(h, a):
    r, g, b = _rgb(h)
    return "rgba(%d,%d,%d,%s)" % (r, g, b, a)


def _empreinte(x):
    return hashlib.sha1(json.dumps(x, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------------------ le catalogue
_VAR = re.compile(r"(--[a-z][a-z0-9-]{0,40})\s*:\s*([^;{}]*);")
_VALEUR_VAR = re.compile(r"^[A-Za-z0-9#%.,()/ _+*-]{1,200}$")
TAILLE_HABILLAGE = 40000


def lire_habillage(chemin):
    """Les variables d'un fichier de thème, et ce qui a été refusé. Un thème ne porte QUE des variables : une valeur avec adresse, accolade, point-virgule,
    barre inverse ou chevron est écartée (rien ne s'exécute, rien n'est chargé du réseau), un fichier trop gros est refusé en entier."""
    try:
        texte = Path(chemin).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as ex:
        return {}, ["fichier illisible : %s" % ex]
    if len(texte) > TAILLE_HABILLAGE:
        return {}, ["fichier trop gros (%d signes, %d au plus)" % (len(texte), TAILLE_HABILLAGE)]
    texte = re.sub(r"/\*.*?\*/", "", texte, flags=re.S)
    variables, refus = {}, []
    for nom, valeur in _VAR.findall(texte):
        v = valeur.strip()
        if not _VALEUR_VAR.match(v) or "url(" in v.lower() or "expression" in v.lower() or "@" in v:
            refus.append(nom)
            continue
        variables[nom] = v
        if len(variables) >= 400:
            refus.append("(au-delà de 400 variables)")
            break
    return variables, refus


def construire_catalogue(manifestes):
    ecrans, widgets, themes, onglets, habillages = [], [], [], [], []
    for m in manifestes:
        for e in m.ecrans:
            ecrans.append({"id": "%s:%s" % (m.id, e.id), "module": m.id, "libelle": e.libelle, "titre": e.titre or e.libelle,
                           "gabarit": e.gabarit, "famille": m.famille or "autres"})
        for w in m.widgets:
            widgets.append({"id": "%s:%s" % (m.id, w.id), "module": m.id, "libelle": w.libelle,
                            "ecran": "accueil" if w.ecran == "accueil" else "%s:%s" % (m.id, w.ecran), "zone": w.zone, "taille": w.taille,
                            "ordre": w.ordre, "role": w.role, "composant": w.composant,
                            "source": ("%s.%s" % (m.id, w.source)) if w.source else "", "rafraichir_s": w.rafraichir_s})
        for o in m.onglets:
            onglets.append({"id": "%s:%s" % (m.id, o.id), "module": m.id, "libelle": o.libelle, "objet": o.objet if ":" in o.objet else "%s:%s" % (m.id, o.objet),
                            "ecran": ("%s:%s" % (m.id, o.ecran)) if o.ecran else "", "ordre": o.ordre, "role": o.role, "icone": o.icone, "droit": o.droit})
        for h in m.habillages:
            variables, refus = lire_habillage(Path(m.source).parent / h.fichier) if m.source else ({}, ["module sans dossier"])
            habillages.append({"id": "%s:%s" % (m.id, h.id), "module": m.id, "libelle": h.libelle, "base": h.base, "variables": variables, "refus": refus})
        if m.theme.accent or m.theme.tokens:
            themes.append({"module": m.id, "accent": m.theme.accent,
                           "tokens": {"mod-%s-%s" % (m.id, k): v for k, v in m.theme.tokens}})
    ecrans.sort(key=lambda x: x["id"])
    widgets.sort(key=lambda x: x["id"])
    themes.sort(key=lambda x: x["module"])
    onglets.sort(key=lambda x: (x["ordre"], x["libelle"].lower(), x["id"]))
    habillages.sort(key=lambda x: x["id"])
    return {"ecrans": ecrans, "widgets": widgets, "themes": themes, "onglets": onglets, "habillages": habillages}


def _fusion(objets, compte, cle):
    """Les personnalisations d'abord globales (compte vide), puis celles du compte, qui l'emportent."""
    sortie = {}
    for o in sorted(objets, key=lambda o: (o["compte"] != "", o["id"])):
        if o["compte"] in ("", compte):
            sortie.setdefault(o["donnees"].get(cle, ""), {}).update({k: v for k, v in o["donnees"].items() if k != cle})
    return sortie


def _moi(ctx, role, compte):
    """Qui regarde : le compte qui AGIT, jamais celui qu'on déclare. Un compte ne peut pas se dire administrateur pour voir les tuiles d'un administrateur ;
    seul un acteur sans compte (un agent, le noyau) choisit le rôle et le compte qu'il demande."""
    if ctx.compte:
        return ("admin" if ctx.est_admin(ctx.compte) else "utilisateur"), ctx.compte
    return role, compte


def brancher(ctx):
    dernier = {}

    def catalogue_actuel(ctx):
        o = ctx.lire(*CATALOGUE, portee=ctx.TOUT)
        return o["donnees"] if o else {"etag": "", "ecrans": [], "widgets": [], "themes": []}

    def reconstruire(ctx, ev=None):
        cat = construire_catalogue(ctx.manifestes_actifs())
        etag = _empreinte(cat)
        actuel = ctx.lire(*CATALOGUE, portee=ctx.TOUT)
        if actuel and actuel["donnees"].get("etag") == etag:
            return
        ctx.poser(CATALOGUE[0], CATALOGUE[1], "Catalogue d'affichage", etat=etag, donnees=dict(cat, etag=etag))
        ids = {w["id"] for w in cat["widgets"]}
        for o in ctx.lister(portee=ctx.TOUT, type="widget_donnees"):      # une tuile dont le module n'est plus là n'a plus de donnée
            if o["id"] not in ids:
                ctx.retirer("widget_donnees", o["id"])
        for k in [k for k in dernier if k not in ids]:
            del dernier[k]
        ctx.emettre("affichage_catalogue.change", objet=CATALOGUE, donnees={"etag": etag, "ecrans": len(cat["ecrans"]), "tuiles": len(cat["widgets"])})

    def donnees_widgets(ctx):
        maintenant = time.time()
        for w in catalogue_actuel(ctx)["widgets"]:
            if not w["source"]:
                continue
            due = w["id"] not in dernier or (w["rafraichir_s"] and maintenant - dernier[w["id"]] >= w["rafraichir_s"])
            if not due:
                continue
            dernier[w["id"]] = maintenant
            try:
                valeur = ctx.executer_lecture(w["source"])
                ctx.poser("widget_donnees", w["id"], w["libelle"], etat="ok" if valeur is not None else "vide",
                          donnees={"valeur": valeur, "erreur": ""})
            except Exception as ex:           # une source qui plante ne casse ni l'écran ni les autres tuiles : on le dit dans la tuile
                ctx.poser("widget_donnees", w["id"], w["libelle"], etat="erreur", donnees={"valeur": None, "erreur": str(ex)[:200]})

    def lire_theme(ctx, compte="", systeme="clair"):
        p = _fusion([o for o in ctx.lister(portee=ctx.TOUT, type="theme_perso")], compte, "_")
        p = p.get("", {})
        choix = p.get("theme", "auto")
        mode = choix if choix in BASES else (systeme if systeme in BASES else "clair")
        v = dict(BASES[mode])
        accent = p.get("accent")
        if accent and accent_ok(accent, mode):
            v["accent"], v["on-accent"] = accent, meilleur_texte(accent)
        v["accent-bg"] = _rgba(v["accent"], ".12")
        v.update(DENSITES.get(p.get("densite", "normale"), DENSITES["normale"]))
        for t in catalogue_actuel(ctx)["themes"]:
            if t["accent"] and accent_ok(t["accent"], mode):
                v["accent-" + t["module"]] = t["accent"]
            v.update(t["tokens"])
        css = {"--" + k: val for k, val in sorted(v.items())}
        return {"etag": _empreinte([mode, css]), "mode": mode, "densite": p.get("densite", "normale"), "variables": css}

    def lire_ecran(ctx, ecran="accueil", role="utilisateur", compte=""):
        role, compte = _moi(ctx, role, compte)
        cat = catalogue_actuel(ctx)
        if ecran == "accueil":
            titre, gabarit = "Accueil", "tableau"
        else:
            e = next((x for x in cat["ecrans"] if x["id"] == ecran), None)
            if e is None:
                return {"id": ecran, "existe": False, "titre": "", "gabarit": "libre", "etag": cat.get("etag", ""),
                        "zones": {z: [] for z in ZONES}}
            titre, gabarit = e["titre"], e["gabarit"]
        persos = _fusion(ctx.lister(portee=ctx.TOUT, type="widget_perso"), compte, "widget")
        donnees = {o["id"]: o["donnees"] for o in ctx.lister(portee=ctx.TOUT, type="widget_donnees")}
        zones = {z: [] for z in ZONES}
        for w in cat["widgets"]:
            if w["ecran"] != ecran or (role != "admin" and w["role"] != "utilisateur"):
                continue
            w = dict(w, **{k: v for k, v in persos.get(w["id"], {}).items() if k in ("masque", "ordre", "zone", "taille")})
            if w.get("masque"):
                continue
            w["donnees"] = donnees.get(w["id"])
            zones.setdefault(w["zone"], []).append(w)
        for xs in zones.values():
            xs.sort(key=lambda w: (w["ordre"], w["libelle"].lower(), w["id"]))
        return {"id": ecran, "existe": True, "titre": titre, "gabarit": gabarit, "etag": cat.get("etag", ""), "zones": zones}

    def lire_onglets(ctx, objet="", role="utilisateur", compte=""):
        """Les onglets que les modules ajoutent à la fiche d'un objet (« note » : tous ceux dont le type se termine ainsi ; « notes:note » : exactement celui-là)."""
        role, compte = _moi(ctx, role, compte)
        cat = catalogue_actuel(ctx)
        detenus = None
        if compte:
            try:
                d = ctx.executer_lecture("droits.mes_droits", compte=compte)
            except (PermissionError, KeyError):
                d = None
            detenus = set(d["droits"]) if d else set()
        out = []
        for o in cat.get("onglets", []):
            if objet and o["objet"] != objet and o["objet"].split(":", 1)[1] != objet:
                continue
            if role != "admin" and o["role"] != "utilisateur":
                continue
            if o["droit"] and detenus is not None and o["droit"] not in detenus:
                continue
            out.append(o)
        return {"objet": objet, "onglets": out}

    def lire_habillages(ctx):
        """Les thèmes complets que les modules livrent : variables CSS prêtes, avec ce qui a été refusé dans leur fichier."""
        return {"habillages": copy.deepcopy(catalogue_actuel(ctx).get("habillages", []))}

    # ---------------------------------------------------------------- écritures : toujours avec preuve et retour arrière
    def _ecrire(ctx, type_, oid, libelle, nouveau, compte, reinitialiser):
        existant = ctx.lire(type_, oid, portee=ctx.TOUT)
        avant = copy.deepcopy(existant["donnees"]) if existant else None
        if reinitialiser:
            ctx.retirer(type_, oid)
            return {"type": type_, "id": oid, "compte": compte, "libelle": libelle, "avant": avant, "attendu": None}
        ctx.poser(type_, oid, libelle, etat="perso", donnees=nouveau, compte=compte)
        return {"type": type_, "id": oid, "compte": compte, "libelle": libelle, "avant": avant, "attendu": nouveau}

    def personnaliser_theme(ctx, theme=None, densite=None, accent=None, reinitialiser=False, compte=""):
        if theme is not None and theme not in THEMES:
            raise ValueError("thème : %s" % " | ".join(THEMES))
        if densite is not None and densite not in DENSITES:
            raise ValueError("densité : %s" % " | ".join(DENSITES))
        oid = compte or "global"
        existant = ctx.lire("theme_perso", oid, portee=ctx.TOUT)
        nouveau = dict(existant["donnees"]) if existant else {}
        nouveau["_"] = ""
        for k, v in (("theme", theme), ("densite", densite), ("accent", accent)):
            if v is not None:
                nouveau[k] = v
        if accent is not None:
            modes = [nouveau.get("theme", "auto")]
            modes = ["clair", "sombre"] if modes[0] == "auto" else modes
            for m in modes:
                if not accent_ok(accent, m):
                    raise ValueError("l'accent %s manque de contraste en thème %s (3:1 sur le fond, 4,5:1 pour le texte dessus)" % (accent, m))
        return _ecrire(ctx, "theme_perso", oid, "Thème de %s" % (compte or "tous"), nouveau, compte, reinitialiser)

    def personnaliser_widget(ctx, widget, masque=None, ordre=None, zone=None, taille=None, reinitialiser=False, compte=""):
        if widget not in {w["id"] for w in catalogue_actuel(ctx)["widgets"]}:
            raise ValueError("tuile inconnue : %s" % widget)
        if zone is not None and zone not in ZONES:
            raise ValueError("zone : %s" % " | ".join(ZONES))
        if taille is not None and taille not in TAILLES:
            raise ValueError("taille : %s" % " | ".join(TAILLES))
        if ordre is not None and (not isinstance(ordre, int) or isinstance(ordre, bool) or not 0 <= ordre <= 9999):
            raise ValueError("ordre : un entier entre 0 et 9999")
        oid = "%s|%s" % (compte or "global", widget)
        existant = ctx.lire("widget_perso", oid, portee=ctx.TOUT)
        nouveau = dict(existant["donnees"]) if existant else {"widget": widget}
        for k, v in (("masque", masque), ("ordre", ordre), ("zone", zone), ("taille", taille)):
            if v is not None:
                nouveau[k] = v
        return _ecrire(ctx, "widget_perso", oid, "Tuile %s" % widget, nouveau, compte, reinitialiser)

    def prouver(ctx, res):
        o = ctx.lire(res["type"], res["id"], portee=ctx.TOUT)
        return (o is None) if res["attendu"] is None else (o is not None and o["donnees"] == res["attendu"])

    def defaire(ctx, res):
        if res["avant"] is None:
            ctx.retirer(res["type"], res["id"])
        else:
            ctx.poser(res["type"], res["id"], res["libelle"], etat="perso", donnees=res["avant"], compte=res["compte"])


    # ---------------------------------------------------------------- la disposition des menus
    def _aplatir(arbre):
        """L'arbre des menus (familles, entrées, enfants) en une liste d'entrées, avec leur famille : c'est ce que le point d'évolution range."""
        plat = []

        def marcher(e, famille):
            plat.append({"id": e["id"], "module": e.get("module", ""), "libelle": e["libelle"], "ecran": e.get("ecran", ""), "ordre": e.get("ordre", 100),
                         "role": e.get("role", "utilisateur"), "icone": e.get("icone", ""), "parent": e.get("parent", ""), "droit": e.get("droit", ""),
                         "famille": famille, "groupe": e.get("groupe", ""), "zone": e.get("zone", "principal")})
            for f in e.get("enfants", []):
                marcher(f, famille)
        for fam in arbre or []:
            for e in fam.get("enfants", []):
                marcher(e, fam.get("famille", ""))
        return plat

    def _alertes_du_jour(ctx):
        """Les alertes du compte (jour.aujourdhui, pour LUI) comptées par origine : {ou: {brule: n, regarder: n}}. Une source muette ne dit rien."""
        try:
            j = ctx.executer_lecture("jour.aujourdhui")
        except (PermissionError, KeyError, ValueError):
            return [], {}
        items = [x for b in (j or {}).get("bandes", []) for x in b.get("items", [])]
        comptes = {}
        for x in items:
            cle = x.get("ou") or x.get("quoi") or ""
            if x.get("bande") in ("brule", "regarder") and cle:
                comptes.setdefault(cle, {"brule": 0, "regarder": 0})[x["bande"]] += 1
        return items, comptes

    def _droits_du(ctx, compte):
        if not compte:
            return None
        try:
            d = ctx.executer_lecture("droits.mes_droits", compte=compte)
        except (PermissionError, KeyError, ValueError):
            d = None
        return set(d["droits"]) if d else set()

    def _permis(e, admin, detenus):
        return not ((e.get("role") == "admin" and not admin) or (e.get("droit") and detenus is not None and e["droit"] not in detenus))

    def _niveau_de(entrees):
        niv = ""
        for e in entrees:
            for x in [e] + e.get("enfants", []):
                if RANG_NIVEAU[x["badge"]["niveau"]] > RANG_NIVEAU[niv]:
                    niv = x["badge"]["niveau"]
        return niv

    def _filtrer(sortie, admin, detenus):
        """Le nexus retire ce que le rôle ou le droit ne permet pas, puis recalcule lui-même les niveaux : le point d'évolution ne décide d'aucun accès."""
        groupes = []
        for g in sortie["groupes"]:
            xs = []
            for e in g["entrees"]:
                if not _permis(e, admin, detenus):
                    continue
                e = dict(e, enfants=[f for f in e["enfants"] if _permis(f, admin, detenus)])
                xs.append(e)
            if xs:
                niv = _niveau_de(xs)
                groupes.append(dict(g, entrees=xs, niveau=niv, interlocuteur=g["interlocuteur"] if admin else "itare"))
        avatar = [e for e in sortie["avatar"] if _permis(e, admin, detenus)]
        niveau = ""
        for g in groupes:
            if RANG_NIVEAU[g["niveau"]] > RANG_NIVEAU[niveau]:
                niveau = g["niveau"]
        niveau = niveau or "ok"
        return {"groupes": groupes, "avatar": avatar, "orphelines": sortie["orphelines"], "niveau": niveau}

    def _epingles_de(ctx, compte):
        xs = [o["donnees"] for o in ctx.lister(portee=ctx.TOUT, type="epingle") if o["compte"] == compte]
        return sorted(xs, key=lambda d: (d.get("ts", 0), d.get("cle", "")))

    def _organisation(ctx):
        o = ctx.lire("organisation", "global", portee=ctx.TOUT)
        return dict(ORG_DEFAUT, **{k: v for k, v in ((o or {}).get("donnees") or {}).items() if k in ORG_DEFAUT})

    def lire_disposition(ctx, role="utilisateur", compte=""):
        role, compte = _moi(ctx, role, compte)
        admin = role == "admin"
        m = ctx.executer_lecture("menus.lire_menu", role=role, compte=compte) or {"arbre": [], "badges": {}}
        detenus = _droits_du(ctx, compte)
        _, alertes = _alertes_du_jour(ctx)
        entree = {"entrees": _aplatir(m["arbre"]), "modules": sorted(x.id for x in ctx.manifestes_actifs()), "badges": m.get("badges", {}), "signaux": alertes}
        sortie = _filtrer(ctx.point("disposition", entree)["valeur"], admin, detenus)
        return {"etag": _empreinte([m.get("etag", ""), sortie]), "groupes": sortie["groupes"], "avatar": sortie["avatar"], "orphelines": sortie["orphelines"],
                "niveau": sortie["niveau"], "cassandra_ok": admin, "organisation": _organisation(ctx), "epingles": _epingles_de(ctx, compte),
                "version": VERSION_AFFICHEE}

    def lire_organisation(ctx):
        return _organisation(ctx)

    def modifier_organisation(ctx, nom=None, forme=None, identifiant=None, adresse=None, fuseau=None, langue=None, logo=None, reinitialiser=False):
        if not ctx.est_admin(ctx.compte or ""):
            raise PermissionError("l'organisation se règle par un administrateur")
        existant = ctx.lire("organisation", "global", portee=ctx.TOUT)
        avant = copy.deepcopy(existant["donnees"]) if existant else None
        if reinitialiser:
            ctx.retirer("organisation", "global")
            return {"avant": avant, "attendu": None}
        nouveau = dict(avant or {})
        for champ, v in (("nom", nom), ("forme", forme), ("identifiant", identifiant), ("adresse", adresse)):
            if v is None:
                continue
            v = str(v).strip()
            if len(v) > ORG_LONGUEURS[champ] or (champ == "nom" and not v):
                raise ValueError("%s : %s" % (champ, "un texte de 1 à %d caractères" % ORG_LONGUEURS[champ] if champ == "nom" else "au plus %d caractères" % ORG_LONGUEURS[champ]))
            nouveau[champ] = v
        if fuseau is not None:
            connus = zoneinfo.available_timezones()            # vide sur une machine sans base des fuseaux : on ne juge alors que la forme
            if not _FUSEAU.match(str(fuseau)) or (connus and str(fuseau) not in connus):
                raise ValueError("fuseau horaire inconnu : %s" % fuseau)
            nouveau["fuseau"] = str(fuseau)
        if langue is not None:
            if langue not in ("fr", "en"):
                raise ValueError("langue : fr | en")
            nouveau["langue"] = langue
        if logo is not None:
            if logo != "":
                if len(logo) > LOGO_MAX or not _LOGO.match(logo):
                    raise ValueError("logo : une image png, jpeg, webp ou gif de %d Ko au plus (en data:image/…;base64)" % (LOGO_MAX // 1000))
                try:
                    base64.b64decode(logo.split(",", 1)[1], validate=True)
                except ValueError:
                    raise ValueError("logo : image illisible")
            nouveau["logo"] = logo
        ctx.poser("organisation", "global", "Organisation", etat="perso", donnees=nouveau)
        return {"avant": avant, "attendu": nouveau}

    def prouver_org(ctx, res):
        o = ctx.lire("organisation", "global", portee=ctx.TOUT)
        return (o is None) if res["attendu"] is None else (o is not None and o["donnees"] == res["attendu"])

    def defaire_org(ctx, res):
        if res["avant"] is None:
            ctx.retirer("organisation", "global")
        else:
            ctx.poser("organisation", "global", "Organisation", etat="perso", donnees=res["avant"])

    # ---------------------------------------------------------------- les pages épinglées (par compte)
    def epingler(ctx, cle, groupe, entree, vue="", libelle=""):
        compte = ctx.compte or ""
        if not compte:
            raise ValueError("une épingle appartient à un compte")
        if not _CLE_EPINGLE.match(str(cle or "")) or not _CLE_EPINGLE.match(str(groupe or "")) or not _CLE_EPINGLE.match(str(entree or "")):
            raise ValueError("épingle : clé, groupe et entrée invalides")
        libelle = str(libelle or "").strip()[:80] or str(cle)
        oid = "%s|%s" % (compte, cle)
        existant = ctx.lire("epingle", oid, portee=ctx.TOUT)
        avant = copy.deepcopy(existant["donnees"]) if existant else None
        if not existant and len(_epingles_de(ctx, compte)) >= MAX_EPINGLES:
            raise ValueError("au plus %d pages épinglées" % MAX_EPINGLES)
        nouveau = {"cle": str(cle), "groupe": str(groupe), "entree": str(entree), "vue": str(vue or "")[:60], "libelle": libelle, "ts": (avant or {}).get("ts") or int(time.time())}
        ctx.poser("epingle", oid, libelle, etat="perso", donnees=nouveau, compte=compte)
        return {"id": oid, "compte": compte, "avant": avant, "attendu": nouveau}

    def desepingler(ctx, cle):
        compte = ctx.compte or ""
        oid = "%s|%s" % (compte, cle)
        existant = ctx.lire("epingle", oid, portee=ctx.TOUT)
        if not existant:
            raise ValueError("cette page n'est pas épinglée")
        ctx.retirer("epingle", oid)
        return {"id": oid, "compte": compte, "avant": copy.deepcopy(existant["donnees"]), "attendu": None}

    def prouver_ep(ctx, res):
        o = ctx.lire("epingle", res["id"], portee=ctx.TOUT)
        return (o is None) if res["attendu"] is None else (o is not None and o["donnees"] == res["attendu"])

    def defaire_ep(ctx, res):
        if res["avant"] is None:
            ctx.retirer("epingle", res["id"])
        else:
            ctx.poser("epingle", res["id"], res["avant"]["libelle"], etat="perso", donnees=res["avant"], compte=res["compte"])

    # ---------------------------------------------------------------- les idées du panneau
    def lire_idees(ctx, mode="", groupe="", entree="", sous="", page="", heure=-1, faits=None, refuses=None, nombre=4):
        role, compte = _moi(ctx, "utilisateur", "")
        admin = role == "admin"
        mode = mode if mode in ("itare", "cassandra") else ("itare" if groupe in ("", "desk") else "cassandra")
        if mode == "cassandra" and not admin:                    # Cassandra ne répond qu'à un administrateur : le nexus tranche, pas la page
            mode = "itare"
        items, _ = _alertes_du_jour(ctx)
        if mode == "itare":
            items = [x for x in items if x.get("quoi") in PERSONNELS]
        faits = {k for k in (faits or []) if k in ACTES}
        refuses = {k for k in (refuses or []) if k in ACTES}
        actes = [{"id": k, "titre": a["titre"], "nat": a["nat"], "qui": a["qui"], "risque": a["risque"],
                  "etat": "fait" if k in faits else ("refuse" if k in refuses else "")}
                 for k, a in sorted(ACTES.items()) if admin or not a["admin"]]
        h = int(heure) if isinstance(heure, int) and 0 <= heure < 24 else time.localtime().tm_hour
        entree_pt = {"contexte": {"groupe": str(groupe)[:30], "entree": str(entree)[:40], "sous": str(sous)[:40], "mode": mode, "heure": h, "page": str(page)[:80]},
                     "items": items, "actes": actes, "max": nombre if isinstance(nombre, int) and not isinstance(nombre, bool) else 4}
        sortie = ctx.point("idees", entree_pt)["valeur"]
        proposes = {i["acte"] for i in sortie["idees"] if i.get("acte")}
        return {"mode": mode, "idees": sortie["idees"], "urgent": sortie["urgent"],
                "actes": {k: {x: ACTES[k][x] for x in ("capacite", "arg", "titre", "risque", "perimetre", "preuve", "retour")} for k in sorted(proposes)}}

    # ---------------------------------------------------------------- la session
    def lire_session(ctx, ip_session=""):
        role, compte = _moi(ctx, "utilisateur", "")
        sessions = []
        try:
            r = ctx.executer_lecture("comptes.mes_sessions")
            sessions = [{"cree": s.get("created"), "derniere": s.get("last_used"), "ip": s.get("ip", ""), "agent": s.get("agent", "")} for s in (r or {}).get("sessions", [])][:5]
        except (PermissionError, KeyError, ValueError):
            pass
        org = _organisation(ctx)
        return {"compte": compte, "role": role, "ip": ip_session, "organisation": org["nom"], "fuseau": org["fuseau"], "langue": org["langue"],
                "version": VERSION_AFFICHEE, "modules": len(ctx.manifestes_actifs()), "sessions": sessions}

    # ---------------------------------------------------------------- les fils du panneau, liés à une page
    def _fils_du_salon(ctx):
        try:
            r = ctx.executer_lecture("salon.fils")
        except (PermissionError, KeyError, ValueError):
            return {}
        return {f["id"]: f for f in (r or {}).get("fils", [])}

    def lire_fils(ctx, agent="itare"):
        if agent not in INTERLOCUTEURS:
            raise ValueError("agent : %s" % " | ".join(INTERLOCUTEURS))
        compte = ctx.compte or ""
        salon = _fils_du_salon(ctx)
        out = []
        for o in ctx.lister(portee=ctx.TOUT, type="fil_page"):
            d = o["donnees"]
            if o["compte"] == compte and d.get("agent") == agent and d.get("fil") in salon:
                f = salon[d["fil"]]
                out.append({"fil": d["fil"], "titre": f.get("titre", ""), "dernier": f.get("dernier", 0), "n": f.get("n", 0), "page": d.get("page", "")})
        return {"fils": sorted(out, key=lambda x: -(x["dernier"] or 0))}

    def lier_fil(ctx, fil, agent, page=""):
        compte = ctx.compte or ""
        if not compte:
            raise ValueError("un fil du panneau appartient à un compte")
        if agent not in INTERLOCUTEURS:
            raise ValueError("agent : %s" % " | ".join(INTERLOCUTEURS))
        if not isinstance(fil, int) or isinstance(fil, bool) or fil <= 0 or fil not in _fils_du_salon(ctx):
            raise ValueError("fil inconnu, ou qui n'est pas à ce compte")
        oid = "%s|%s|%d" % (compte, agent, fil)
        existant = ctx.lire("fil_page", oid, portee=ctx.TOUT)
        avant = copy.deepcopy(existant["donnees"]) if existant else None
        nouveau = {"fil": fil, "agent": agent, "page": str(page or "")[:120]}
        ctx.poser("fil_page", oid, "Fil %d du panneau" % fil, etat=agent, donnees=nouveau, compte=compte)
        return {"id": oid, "compte": compte, "avant": avant, "attendu": nouveau}

    def prouver_fp(ctx, res):
        o = ctx.lire("fil_page", res["id"], portee=ctx.TOUT)
        return (o is None) if res["attendu"] is None else (o is not None and o["donnees"] == res["attendu"])

    def defaire_fp(ctx, res):
        if res["avant"] is None:
            ctx.retirer("fil_page", res["id"])
        else:
            ctx.poser("fil_page", res["id"], "Fil %d du panneau" % res["avant"]["fil"], etat=res["avant"]["agent"], donnees=res["avant"], compte=res["compte"])

    ctx.moteur("reconstruire", reconstruire)
    ctx.moteur("reconstruire_regulierement", reconstruire)
    ctx.moteur("donnees_widgets", donnees_widgets)
    ctx.implementer("lire_disposition", lire_disposition)
    ctx.implementer("lire_organisation", lire_organisation)
    ctx.implementer("lire_idees", lire_idees)
    ctx.implementer("lire_session", lire_session)
    ctx.implementer("lire_fils", lire_fils)
    ctx.implementer("modifier_organisation", modifier_organisation, prouver_org, defaire_org,
                    simuler=lambda ctx, **_: "modifierait l'organisation")
    ctx.implementer("epingler", epingler, prouver_ep, defaire_ep, simuler=lambda ctx, cle="", **_: "épinglerait %s" % cle)
    ctx.implementer("desepingler", desepingler, prouver_ep, defaire_ep, simuler=lambda ctx, cle="", **_: "retirerait l'épingle %s" % cle)
    ctx.implementer("lier_fil", lier_fil, prouver_fp, defaire_fp, simuler=lambda ctx, fil=0, **_: "lierait le fil %s à une page" % fil)
    ctx.implementer("lire_theme", lire_theme)
    ctx.implementer("lire_ecran", lire_ecran)
    ctx.implementer("lire_onglets", lire_onglets)
    ctx.implementer("lire_habillages", lire_habillages)
    ctx.implementer("personnaliser_theme", personnaliser_theme, prouver, defaire,
                    simuler=lambda ctx, **_: "personnaliserait le thème")
    ctx.implementer("personnaliser_widget", personnaliser_widget, prouver, defaire,
                    simuler=lambda ctx, widget="", **_: "personnaliserait la tuile %s" % widget)
# ▲▲▲ FIN BORNE CN ▲▲▲

# ═══ EXPLICATIF CN / EC ═══════════════════════════════════════════════════════
# CN : tout ce fichier est du nexus : _rgb, _luminance, contraste, meilleur_texte, accent_ok, _rgba, _empreinte, lire_habillage, et la façade des menus (lire_disposition, lire_idees, épingles, organisation, fils) …
# EC : deux points d'évolution, `disposition` (points/EC_disposition.py) et `idees` (points/EC_idees.py), appelés par ctx.point ; ils rangent et classent, ils ne décident d'aucun accès.
# LIEN : à compléter (contrat, fichiers voisins)
