"""Le module d'affichage : thème et mise en page, assemblés à partir de ce que les modules DÉCLARENT.

Un module ne dit jamais comment il s'affiche. Il déclare des écrans (avec un gabarit), des tuiles (avec un composant et une source de données) et
une touche de couleur. Ce module les assemble et sert à l'interface un descripteur générique : activer un module fait apparaître ses tuiles et son
accent, le désactiver les retire, sans toucher à l'interface.

  - le catalogue (écrans, tuiles, accents) est un objet du registre, rebâti par un moteur quand un module est branché ou débranché ;
  - un second moteur lit les sources des tuiles à leur rythme : l'interface lit une donnée prête, elle n'appelle jamais les modules ;
  - le thème est résolu ici : jetons du noyau, accent choisi, touches des modules ; un accent sans contraste suffisant est refusé.
"""
import copy
import hashlib
import json
import re
import time
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

    ctx.moteur("reconstruire", reconstruire)
    ctx.moteur("reconstruire_regulierement", reconstruire)
    ctx.moteur("donnees_widgets", donnees_widgets)
    ctx.implementer("lire_theme", lire_theme)
    ctx.implementer("lire_ecran", lire_ecran)
    ctx.implementer("lire_onglets", lire_onglets)
    ctx.implementer("lire_habillages", lire_habillages)
    ctx.implementer("personnaliser_theme", personnaliser_theme, prouver, defaire,
                    simuler=lambda ctx, **_: "personnaliserait le thème")
    ctx.implementer("personnaliser_widget", personnaliser_widget, prouver, defaire,
                    simuler=lambda ctx, widget="", **_: "personnaliserait la tuile %s" % widget)
