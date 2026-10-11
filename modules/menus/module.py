"""Le module de menus : assemble l'arbre de navigation à partir de ce que les modules actifs DÉCLARENT.

Un module ne touche jamais à l'interface pour s'y inscrire : il déclare ses entrées dans son manifeste ([[menus]]), et ce module les
assemble. Activer un module ajoute ses entrées, le désactiver les retire, sans redémarrer ni rien modifier à l'interface.

  - l'arbre brut (« plat ») est un objet du registre, rebâti par un moteur quand un module est branché ou débranché ;
  - lire_menu applique les personnalisations (globales, puis celles du compte), filtre par rôle, assemble et rend l'arbre ;
  - les compteurs (constats ouverts, moteurs à surveiller) sont tenus à jour par un second moteur.
"""
import copy
import hashlib
import json

FAMILLES = ["socle", "moteurs", "reseau", "securite", "sites", "communication", "travail", "gestion", "supervision"]
LIBELLES = {"socle": "Socle", "moteurs": "Moteurs", "reseau": "Réseau", "securite": "Sécurité", "sites": "Sites",
            "communication": "Communication", "travail": "Travail", "gestion": "Gestion", "supervision": "Supervision", "autres": "Autres"}
ARBRE = ("menu_arbre", "global")
BADGES = ("menu_arbre", "badges")


def _cle_famille(f):
    return (FAMILLES.index(f) if f in FAMILLES else len(FAMILLES), f)


def construire_plat(manifestes):
    """La liste à plat des entrées déclarées par les modules donnés, avec leur parent qualifié (« module:menu »)."""
    plat = {}
    for m in manifestes:
        for mn in m.menus:
            qid = "%s:%s" % (m.id, mn.id)
            parent = ""
            if mn.parent:
                parent = mn.parent if ":" in mn.parent else "%s:%s" % (m.id, mn.parent)
            plat[qid] = {"id": qid, "module": m.id, "libelle": mn.libelle, "ecran": ("%s:%s" % (m.id, mn.ecran)) if mn.ecran else "",
                         "ordre": mn.ordre, "role": mn.role, "icone": mn.icone, "badge": mn.badge, "parent": parent,
                         "famille": m.famille or "autres"}
    return _corriger(plat)


def _corriger(plat):
    """Un parent absent (module inactif) : l'entrée remonte au premier niveau de sa famille. Une boucle de parents est coupée."""
    for e in plat.values():
        if e["parent"] and e["parent"] not in plat:
            e["orpheline_de"], e["parent"] = e["parent"], ""
    for e in plat.values():
        vu, cur = {e["id"]}, e["parent"]
        while cur:
            if cur in vu:
                e["parent"] = ""
                e["boucle"] = True
                break
            vu.add(cur)
            cur = plat[cur]["parent"] if cur in plat else ""
    return sorted(plat.values(), key=lambda e: e["id"])


def assembler(plat, role="utilisateur"):
    """L'arbre : familles, puis entrées du module, puis leurs enfants. Filtré par rôle ; une entrée sans page et sans enfant visible disparaît."""
    voit = (lambda e: True) if role == "admin" else (lambda e: e["role"] == "utilisateur")
    par_id = {e["id"]: dict(e, enfants=[]) for e in plat if voit(e)}
    racines = []
    for e in par_id.values():
        if e["parent"] and e["parent"] in par_id:
            par_id[e["parent"]]["enfants"].append(e)
        elif not e["parent"]:
            racines.append(e)
        # un parent masqué ou hors de la vue : l'entrée avec lui

    def trier(xs):
        xs.sort(key=lambda e: (e["ordre"], e["libelle"].lower(), e["id"]))
        for x in xs:
            trier(x["enfants"])

    def elaguer(xs):
        sortie = []
        for x in xs:
            x["enfants"] = elaguer(x["enfants"])
            if x["ecran"] or x["enfants"]:
                sortie.append(x)
        return sortie
    familles = {}
    for e in racines:
        familles.setdefault(e["famille"], []).append(e)
    arbre = []
    for f in sorted(familles, key=_cle_famille):
        xs = familles[f]
        trier(xs)
        xs = elaguer(xs)
        if xs:
            arbre.append({"id": "famille:" + f, "libelle": LIBELLES.get(f, f.capitalize()), "famille": f, "enfants": xs})
    return arbre


def _empreinte(plat):
    return hashlib.sha1(json.dumps(plat, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]


def _appliquer_perso(plat, persos):
    """Les personnalisations d'abord globales, puis celles du compte (qui l'emportent). Masquer une entrée masque ses enfants."""
    par_id = {e["id"]: dict(e) for e in plat}
    masques = set()
    for p in persos:
        cible = par_id.get(p.get("entree"))
        if cible is None:
            continue
        if p.get("masque"):
            masques.add(cible["id"])
        elif "masque" in p:
            masques.discard(cible["id"])
        for champ in ("libelle", "ordre"):
            if p.get(champ) is not None:
                cible[champ] = p[champ]
        if p.get("parent") is not None:
            cible["parent"] = p["parent"]

    def cache(e):
        vu, cur = set(), e
        while cur and cur["id"] not in vu:
            if cur["id"] in masques:
                return True
            vu.add(cur["id"])
            cur = par_id.get(cur["parent"]) if cur["parent"] else None
        return False
    return _corriger({i: e for i, e in par_id.items() if not cache(e)})


def _aplatir(arbre):
    for n in arbre:
        yield n
        yield from _aplatir(n.get("enfants", []))


def brancher(ctx):
    def reconstruire(ctx, ev=None):
        plat = construire_plat(ctx.manifestes_actifs())
        etag = _empreinte(plat)
        actuel = ctx.lire(*ARBRE, portee=ctx.TOUT)
        if actuel and actuel["donnees"].get("etag") == etag:
            return
        ctx.poser(ARBRE[0], ARBRE[1], "Arbre des menus", etat=etag, donnees={"etag": etag, "plat": plat})
        ctx.emettre("menu_arbre.change", objet=ARBRE, donnees={"etag": etag, "entrees": len(plat)})

    def badges(ctx):
        actuel = ctx.lire(*ARBRE, portee=ctx.TOUT)
        if not actuel:
            return
        valeurs = {}
        for e in actuel["donnees"]["plat"]:
            if e.get("badge"):
                n = ctx.compteurs(e["module"]).get(e["badge"], 0)
                if n:
                    valeurs[e["id"]] = n
        ctx.poser(BADGES[0], BADGES[1], "Compteurs des menus", etat=str(sum(valeurs.values())), donnees=valeurs)

    def lire_menu(ctx, role="utilisateur", compte=""):
        actuel = ctx.lire(*ARBRE, portee=ctx.TOUT)
        if not actuel:
            return {"etag": "", "arbre": [], "badges": {}}
        persos = [o["donnees"] for o in sorted(ctx.lister(portee=ctx.TOUT, type="menu_perso"), key=lambda o: (o["compte"] != "", o["id"]))
                  if o["compte"] in ("", compte)]
        plat = _appliquer_perso(actuel["donnees"]["plat"], persos)
        bd = ctx.lire(*BADGES, portee=ctx.TOUT)
        return {"etag": actuel["donnees"]["etag"], "arbre": assembler(plat, "admin" if role == "admin" else "utilisateur"),
                "badges": copy.deepcopy(bd["donnees"]) if bd else {}}

    def _plat_courant(ctx):
        actuel = ctx.lire(*ARBRE, portee=ctx.TOUT)
        return {e["id"]: e for e in (actuel["donnees"]["plat"] if actuel else [])}

    def personnaliser(ctx, entree, masque=None, libelle=None, ordre=None, parent=None, reinitialiser=False, compte=""):
        plat = _plat_courant(ctx)
        if entree not in plat:
            raise ValueError("entrée de menu inconnue : %s" % entree)
        if ordre is not None and (not isinstance(ordre, int) or isinstance(ordre, bool) or not 0 <= ordre <= 9999):
            raise ValueError("ordre : un entier entre 0 et 9999")
        if libelle is not None and (not isinstance(libelle, str) or not libelle.strip() or len(libelle) > 60):
            raise ValueError("libellé : un texte de 1 à 60 caractères")
        if parent not in (None, "") and parent not in plat:
            raise ValueError("parent inconnu : %s" % parent)
        if parent == entree:
            raise ValueError("une entrée ne peut pas être son propre parent")
        oid = "%s|%s" % (compte or "global", entree)
        existant = ctx.lire("menu_perso", oid, portee=ctx.TOUT)
        avant = copy.deepcopy(existant["donnees"]) if existant else None
        if reinitialiser:
            ctx.retirer("menu_perso", oid)
            return {"id": oid, "compte": compte, "avant": avant, "attendu": None}
        nouveau = dict(avant or {"entree": entree})
        for champ, v in (("masque", masque), ("libelle", libelle), ("ordre", ordre), ("parent", parent)):
            if v is not None:
                nouveau[champ] = v
        ctx.poser("menu_perso", oid, "Menu %s" % entree, etat="masque" if nouveau.get("masque") else "visible", donnees=nouveau, compte=compte)
        return {"id": oid, "compte": compte, "avant": avant, "attendu": nouveau}

    def prouver(ctx, res):
        o = ctx.lire("menu_perso", res["id"], portee=ctx.TOUT)
        return (o is None) if res["attendu"] is None else (o is not None and o["donnees"] == res["attendu"])

    def defaire(ctx, res):
        if res["avant"] is None:
            ctx.retirer("menu_perso", res["id"])
        else:
            ctx.poser("menu_perso", res["id"], "Menu %s" % res["avant"]["entree"], etat="masque" if res["avant"].get("masque") else "visible",
                      donnees=res["avant"], compte=res["compte"])

    ctx.moteur("reconstruire", reconstruire)
    ctx.moteur("reconstruire_regulierement", reconstruire)
    ctx.moteur("badges", badges)
    ctx.implementer("lire_menu", lire_menu)
    ctx.implementer("personnaliser_entree", personnaliser, prouver, defaire,
                    simuler=lambda ctx, entree, **_: "personnaliserait l'entrée %s" % entree)
